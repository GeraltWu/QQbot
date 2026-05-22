"""ZeroDrive 网盘 API 调用：登录、目录解析、文件上传。"""

from __future__ import annotations

import os

import httpx

from bot_core.help_registry import register_help_section

__all__ = [
    "login",
    "random_file",
    "resolve_path_to_id",
    "upload_file",
    "ROOT_ID",
]

ROOT_ID = "00000000-0000-4000-8000-000000000001"


def _base_url() -> str:
    return os.environ.get("ZERODRIVE_BASE_URL", "http://localhost:8000").rstrip("/")


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}



# ---------------------------------------------------------------------------
# 登录
# ---------------------------------------------------------------------------
async def login(username: str, password: str) -> dict:
    """成功返回 {"access_token":"...","token_type":"bearer","username":"..."}，失败 {"error":"..."}。"""
    url = f"{_base_url()}/api/auth/login"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={"username": username, "password": password},
                timeout=15.0,
            )
    except httpx.TimeoutException:
        return {"error": "连接 ZeroDrive 超时，请稍后再试。"}
    except httpx.RequestError as e:
        return {"error": f"网络请求失败：{e}"}

    try:
        data = resp.json()
    except ValueError:
        return {"error": "ZeroDrive 返回了非 JSON 内容。"}

    if resp.status_code == 401:
        return {"error": "用户名或密码错误。"}
    if resp.status_code >= 400:
        msg = data.get("msg", f"HTTP {resp.status_code}")
        return {"error": f"登录失败：{msg}"}

    token_data = data.get("data")
    if not isinstance(token_data, dict):
        return {"error": "登录响应格式异常。"}
    return token_data


# ---------------------------------------------------------------------------
# 路径解析（调 /api/bot/resolve-path）
# ---------------------------------------------------------------------------
async def resolve_path_to_id(token: str, path: str) -> dict:
    """调 GET /api/bot/resolve-path?path= 校验并解析路径。
    成功返回 {"parent_id":"...","resolved_path":"/..."}，失败 {"error":"..."}。"""
    api_path = path.strip()
    url = f"{_base_url()}/api/bot/resolve-path"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers=_auth_headers(token),
                params={"path": api_path},
                timeout=15.0,
            )
    except httpx.TimeoutException:
        return {"error": "连接 ZeroDrive 超时。"}
    except httpx.RequestError as e:
        return {"error": f"网络请求失败：{e}"}

    if resp.status_code == 401:
        return {"error": "登录已过期，请重新绑定：/网盘绑定 用户名 密码"}

    try:
        body = resp.json()
    except ValueError:
        return {"error": "路径解析返回了非 JSON 内容。"}

    if resp.status_code >= 400:
        code = body.get("code")
        if code in (404, 40402):
            return {"error": f"目录不存在：{path}"}
        return {"error": f"路径解析失败：{body.get('msg', f'HTTP {resp.status_code}')}"}

    data = body.get("data")
    if not isinstance(data, dict) or not data.get("id"):
        return {"error": "路径解析响应格式异常。"}
    return {
        "parent_id": data["id"],
        "resolved_path": data.get("resolved_path", api_path),
    }


# ---------------------------------------------------------------------------
# 随机文件（调 /api/bot/random-file）
# ---------------------------------------------------------------------------
async def random_file(
    *,
    token: str,
    path: str,
    mime_prefix: str,
    extensions: str | None = None,
) -> dict:
    """path 有后缀则精确匹配，无后缀则在文件夹内随机选一个匹配 mime_prefix 的文件。
    成功返回 {"node_id":"...","name":"...","mime_type":"...","download_url":"...","folder":{...},"picked":"random"|"exact"}，
    失败 {"error":"..."}。"""
    api_path = path.strip()
    url = f"{_base_url()}/api/bot/random-file"
    params: dict[str, str] = {"path": api_path, "mime_prefix": mime_prefix}
    if extensions:
        params["extensions"] = extensions

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers=_auth_headers(token),
                params=params,
                timeout=15.0,
            )
    except httpx.TimeoutException:
        return {"error": "连接 ZeroDrive 超时。"}
    except httpx.RequestError as e:
        return {"error": f"网络请求失败：{e}"}

    if resp.status_code == 401:
        return {"error": "登录已过期，请重新绑定：/网盘绑定 用户名 密码"}

    try:
        body = resp.json()
    except ValueError:
        return {"error": "随机文件返回了非 JSON 内容。"}

    if resp.status_code >= 400:
        code = body.get("code")
        if code in (404, 40402):
            return {"error": f"路径不存在：{path}"}
        if code == 40403:
            return {"error": f"该目录下无符合条件的文件：{path}"}
        return {"error": f"随机文件失败：{body.get('msg', f'HTTP {resp.status_code}')}"}

    data = body.get("data")
    if not isinstance(data, dict) or not data.get("download_url"):
        return {"error": "随机文件响应格式异常。"}
    return data


# ---------------------------------------------------------------------------
# 文件上传
# ---------------------------------------------------------------------------
async def upload_file(
    *,
    token: str,
    parent_id: str,
    file_bytes: bytes,
    filename: str,
) -> dict:
    """上传文件到 ZeroDrive。成功 {"node":{...}}，失败 {"error":"..."}。"""
    url = f"{_base_url()}/api/nodes/upload"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=_auth_headers(token),
                data={"parent_id": parent_id},
                files={"file": (filename, file_bytes)},
                timeout=60.0,
            )
    except httpx.TimeoutException:
        return {"error": "上传超时，文件可能较大，请稍后重试。"}
    except httpx.RequestError as e:
        return {"error": f"上传网络请求失败：{e}"}

    if resp.status_code == 401:
        return {"error": "登录已过期，请重新绑定：/网盘绑定 用户名 密码"}

    try:
        body = resp.json()
    except ValueError:
        return {"error": "上传返回了非 JSON 内容。"}

    if resp.status_code >= 400:
        return {"error": f"上传失败：{body.get('msg', f'HTTP {resp.status_code}')}"}

    node = body.get("data")
    if not isinstance(node, dict):
        return {"error": "上传响应格式异常。"}
    return {"node": node}


register_help_section(
    order=50,
    title="ZeroDrive 网盘",
    body=(
        "/网盘绑定 用户名 密码 · /网盘解绑\n"
        "/网盘目录 /图片/奶龙（设置默认上传目录）\n"
        "/网盘状态（查看当前绑定和目录）\n"
        "/上传 /图片/奶龙（进入上传模式，发图片上传，发文字退出）\n"
        "/上传（使用默认目录进入上传模式）\n"
        "关键词随机图：在 config/zerodrive_random.yaml 配置\n"
        "关键词语音：在 config/zerodrive_audio.yaml 配置"
    ),
)
