"""ZeroDrive 网盘上传插件：绑定、解绑、目录设置、图片自动/手动上传。"""

from __future__ import annotations

from nonebot import on_command, on_message
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent, MessageSegment
from nonebot.params import CommandArg
from nonebot.rule import Rule

from repositories import zerodrive_repository
from services.zerodrive_service import login, resolve_path_to_id, upload_file, ROOT_ID

bind_cmd = on_command("网盘绑定", priority=14, block=True)
unbind_cmd = on_command("网盘解绑", priority=14, block=True)
status_cmd = on_command("网盘状态", priority=14, block=True)
set_dir_cmd = on_command("网盘目录", priority=14, block=True)
upload_cmd = on_command("网盘上传", priority=14, block=True)

# ---------------------------------------------------------------------------
# 上传会话：/上传 [目录] 进入持续上传模式，发文字退出
# ---------------------------------------------------------------------------
_upload_sessions: dict[str, dict] = {}


def _session_key(event: MessageEvent) -> str:
    return f"{event.self_id}:{event.get_user_id()}"


upload_session_cmd = on_command("上传", priority=14, block=True)


# ---------------------------------------------------------------------------
# 绑定
# ---------------------------------------------------------------------------
@bind_cmd.handle()
async def _handle_bind(event: MessageEvent, args: Message = CommandArg()) -> None:
    parts = args.extract_plain_text().strip().split()
    if len(parts) < 2:
        await bind_cmd.finish("用法：/网盘绑定 用户名 密码")
    username, password = parts[0], " ".join(parts[1:])
    result = await login(username, password)
    if result.get("error"):
        await bind_cmd.finish(result["error"])
    await zerodrive_repository.upsert_credentials(
        bot_self_id=str(event.self_id),
        qq_user_id=str(event.get_user_id()),
        username=result["username"],
        access_token=result["access_token"],
        token_type=result.get("token_type", "bearer"),
    )
    await bind_cmd.finish(
        f"已绑定 ZeroDrive 账号：{result['username']}\n"
        f"请设置默认上传目录：/网盘目录 路径\n"
        f"例：/网盘目录 /图片/奶龙"
    )


# ---------------------------------------------------------------------------
# 解绑
# ---------------------------------------------------------------------------
@unbind_cmd.handle()
async def _handle_unbind(event: MessageEvent) -> None:
    ok = await zerodrive_repository.delete_credentials(
        bot_self_id=str(event.self_id),
        qq_user_id=str(event.get_user_id()),
    )
    if ok:
        await unbind_cmd.finish("已解除 ZeroDrive 绑定。")
    await unbind_cmd.finish("当前没有绑定记录。")


# ---------------------------------------------------------------------------
# 状态
# ---------------------------------------------------------------------------
@status_cmd.handle()
async def _handle_status(event: MessageEvent) -> None:
    creds = await zerodrive_repository.get_credentials(
        bot_self_id=str(event.self_id),
        qq_user_id=str(event.get_user_id()),
    )
    if creds is None:
        await status_cmd.finish("尚未绑定 ZeroDrive。请先 /网盘绑定 用户名 密码")
    lines = [f"账号：{creds['username']}"]
    if creds.get("default_path"):
        lines.append(f"默认上传目录：{creds['default_path']}")
    else:
        lines.append("默认上传目录：未设置（发送图片不会自动上传）")
    await status_cmd.finish("\n".join(lines))


# ---------------------------------------------------------------------------
# 设置默认目录
# ---------------------------------------------------------------------------
@set_dir_cmd.handle()
async def _handle_set_dir(event: MessageEvent, args: Message = CommandArg()) -> None:
    path = args.extract_plain_text().strip()
    if not path:
        await set_dir_cmd.finish("用法：/网盘目录 路径（如 /网盘目录 /图片/奶龙）")
    creds = await zerodrive_repository.get_credentials(
        bot_self_id=str(event.self_id),
        qq_user_id=str(event.get_user_id()),
    )
    if creds is None:
        await set_dir_cmd.finish("尚未绑定 ZeroDrive。请先 /网盘绑定 用户名 密码")
    resolved = await resolve_path_to_id(creds["access_token"], path)
    if resolved.get("error"):
        await set_dir_cmd.finish(resolved["error"])
    canonical_path = resolved["resolved_path"]
    await zerodrive_repository.update_default_dir(
        bot_self_id=str(event.self_id),
        qq_user_id=str(event.get_user_id()),
        parent_id=resolved["parent_id"],
        path=canonical_path,
    )
    await set_dir_cmd.finish(f"默认上传目录已设为：{canonical_path}")


# ---------------------------------------------------------------------------
# 上传命令（显式）
# ---------------------------------------------------------------------------
@upload_cmd.handle()
async def _handle_upload(
    bot: Bot,
    event: MessageEvent,
    args: Message = CommandArg(),
) -> None:
    creds = await zerodrive_repository.get_credentials(
        bot_self_id=str(event.self_id),
        qq_user_id=str(event.get_user_id()),
    )
    if creds is None:
        await upload_cmd.finish("尚未绑定 ZeroDrive。请先 /网盘绑定 用户名 密码")

    path_arg = args.extract_plain_text().strip()
    images = _extract_images(event.message)

    if not images and event.reply:
        images = _extract_images(event.reply.message)
        if not images:
            await upload_cmd.finish("未找到图片。请在同一条消息中附带图片，或回复一条图片消息后使用 /网盘上传")
    elif not images:
        await upload_cmd.finish("未找到图片。请在消息中附带图片，或回复一条图片消息。")

    parent_id: str | None = None
    display_path: str | None = None

    if path_arg:
        resolved = await resolve_path_to_id(creds["access_token"], path_arg)
        if resolved.get("error"):
            await upload_cmd.finish(resolved["error"])
        parent_id = resolved["parent_id"]
        display_path = resolved["resolved_path"]
    elif creds.get("default_parent_id"):
        parent_id = creds["default_parent_id"]
        display_path = creds.get("default_path") or "默认目录"
    else:
        await upload_cmd.finish("请指定上传目录：/网盘上传 路径 或先设置默认目录 /网盘目录 路径")

    await _do_upload_images(bot, event, images, creds["access_token"], parent_id, display_path)


# ---------------------------------------------------------------------------
# 上传会话：/上传 [目录] 进入持续上传模式，发文字退出
# ---------------------------------------------------------------------------
@upload_session_cmd.handle()
async def _handle_upload_session_start(
    bot: Bot,
    event: MessageEvent,
    args: Message = CommandArg(),
) -> None:
    creds = await zerodrive_repository.get_credentials(
        bot_self_id=str(event.self_id),
        qq_user_id=str(event.get_user_id()),
    )
    if creds is None:
        await upload_session_cmd.finish("尚未绑定 ZeroDrive。请先 /网盘绑定 用户名 密码")

    path_arg = args.extract_plain_text().strip()

    if path_arg:
        resolved = await resolve_path_to_id(creds["access_token"], path_arg)
        if resolved.get("error"):
            await upload_session_cmd.finish(resolved["error"])
        parent_id: str = resolved["parent_id"]
        display_path: str = resolved["resolved_path"]
    elif creds.get("default_parent_id"):
        parent_id = creds["default_parent_id"]
        display_path = creds.get("default_path") or "默认目录"
    else:
        await upload_session_cmd.finish("请指定上传目录：/上传 目录 或先设置默认目录 /网盘目录 路径")

    key = _session_key(event)
    _upload_sessions[key] = {
        "token": creds["access_token"],
        "parent_id": parent_id,
        "display_path": display_path,
        "count": 0,
    }

    images = _extract_images(event.message)
    if images:
        await _do_upload_images(bot, event, images, creds["access_token"], parent_id, display_path)
        _upload_sessions[key]["count"] += len(images)
        msg = f"已进入上传模式 → {display_path}\n继续发送图片上传，发送任意文字退出"
    else:
        msg = f"已进入上传模式 → {display_path}\n发送图片即可上传，发送任意文字退出"
    await upload_session_cmd.finish(msg)


# ---------------------------------------------------------------------------
# 上传会话消息处理（发图片=上传，发文字=退出）
# ---------------------------------------------------------------------------
async def _upload_session_rule(event: MessageEvent) -> bool:
    return _session_key(event) in _upload_sessions


_upload_session_handler = on_message(rule=Rule(_upload_session_rule), priority=15, block=True)


@_upload_session_handler.handle()
async def _handle_upload_session_message(bot: Bot, event: MessageEvent) -> None:
    key = _session_key(event)
    session = _upload_sessions.get(key)
    if session is None:
        return

    images = _extract_images(event.message)
    if images:
        await _do_upload_images(
            bot, event, images,
            session["token"], session["parent_id"], session["display_path"],
        )
        session["count"] += len(images)
    else:
        count = session["count"]
        del _upload_sessions[key]
        target_kind, target_id = _target(event)
        msg = MessageSegment.text(f"已退出上传模式，本次共上传 {count} 个文件")
        if target_kind == "group":
            await bot.send_group_msg(group_id=int(target_id), message=msg)
        else:
            await bot.send_private_msg(user_id=int(target_id), message=msg)


# ---------------------------------------------------------------------------
# 自动上传（绑定用户发图片时自动上传到默认目录）
# ---------------------------------------------------------------------------
async def _auto_upload_rule(event: MessageEvent) -> bool:
    if not _extract_images(event.message):
        return False
    text = event.get_plaintext().strip()
    if text.startswith("/"):
        return False
    creds = await zerodrive_repository.get_credentials(
        bot_self_id=str(event.self_id),
        qq_user_id=str(event.get_user_id()),
    )
    if creds is None:
        return False
    if creds.get("default_parent_id") is None:
        return False
    return True


auto_upload = on_message(rule=Rule(_auto_upload_rule), priority=20, block=False)


@auto_upload.handle()
async def _handle_auto_upload(bot: Bot, event: MessageEvent) -> None:
    creds = await zerodrive_repository.get_credentials(
        bot_self_id=str(event.self_id),
        qq_user_id=str(event.get_user_id()),
    )
    if creds is None or creds.get("default_parent_id") is None:
        return
    images = _extract_images(event.message)
    if not images:
        return
    parent_id = creds["default_parent_id"]
    display_path = creds.get("default_path") or "默认目录"
    await _do_upload_images(bot, event, images, creds["access_token"], parent_id, display_path)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _extract_images(message: Message) -> list[dict[str, str]]:
    """从消息中提取所有图片段，返回 [{url, filename}] 列表。"""
    images: list[dict[str, str]] = []
    for seg in message:
        if seg.type == "image":
            url = seg.data.get("url", "")
            filename = seg.data.get("file", "image.jpg")
            if "." not in filename:
                filename += ".jpg"
            if url:
                images.append({"url": url, "filename": filename})
    return images


def _target(event: MessageEvent) -> tuple[str, str]:
    if isinstance(event, GroupMessageEvent):
        return "group", str(event.group_id)
    return "private", str(event.get_user_id())


async def _do_upload_images(
    bot: Bot,
    event: MessageEvent,
    images: list[dict[str, str]],
    token: str,
    parent_id: str,
    display_path: str,
) -> None:
    target_kind, target_id = _target(event)
    success: list[str] = []
    failed: list[str] = []

    for img in images:
        result = await _upload_one(token=token, parent_id=parent_id, url=img["url"], filename=img["filename"])
        if result.get("error"):
            failed.append(f"{img['filename']}: {result['error']}")
        else:
            node = result["node"]
            success.append(f"{node['name']} ({_size_str(node.get('size', 0))})")

    lines = [f"上传到：{display_path}"]
    if success:
        lines.append("成功：" + "、".join(success))
    if failed:
        lines.append("失败：" + "、".join(failed))
    msg = MessageSegment.text("\n".join(lines))
    if target_kind == "group":
        await bot.send_group_msg(group_id=int(target_id), message=msg)
    else:
        await bot.send_private_msg(user_id=int(target_id), message=msg)


async def _upload_one(*, token: str, parent_id: str, url: str, filename: str) -> dict:
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            dl_resp = await client.get(url, timeout=30.0)
            if dl_resp.status_code >= 400:
                return {"error": f"下载失败 HTTP {dl_resp.status_code}"}
            file_bytes = dl_resp.content
    except httpx.TimeoutException:
        return {"error": "下载图片超时"}
    except httpx.RequestError as e:
        return {"error": f"下载失败：{e}"}

    return await upload_file(token=token, parent_id=parent_id, file_bytes=file_bytes, filename=filename)


def _size_str(size: int) -> str:
    if size < 1024:
        return f"{size}B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    return f"{size / (1024 * 1024):.1f}MB"
