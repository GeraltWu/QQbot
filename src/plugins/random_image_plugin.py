"""关键词触发随机图片：检测消息中的关键词，从 ZeroDrive 对应目录随机发送一张图片。

配置：
    .env                  ZERODRIVE_ADMIN_USERNAME / ZERODRIVE_ADMIN_PASSWORD
    config/zerodrive_random.yaml  关键词映射（path + keywords）
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

import httpx
import yaml
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent, MessageSegment
from nonebot.rule import Rule

from repositories import zerodrive_repository
from services.zerodrive_service import login, random_image as zd_random_image

_CONFIG_PATH = Path("config") / "zerodrive_random.yaml"


def _admin_credentials() -> tuple[str, str] | None:
    username = os.environ.get("ZERODRIVE_ADMIN_USERNAME", "").strip()
    password = os.environ.get("ZERODRIVE_ADMIN_PASSWORD", "").strip()
    if username and password:
        return username, password
    return None


def _load_keywords() -> list[tuple[str, str]]:
    """读取 YAML 配置，返回 [(关键词, 路径), ...]，长关键词优先。"""
    try:
        with _CONFIG_PATH.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return []

    if not isinstance(data, dict):
        return []

    result: list[tuple[str, str]] = []
    for item in data.get("random_images") or []:
        if not isinstance(item, dict):
            continue
        path = (item.get("path") or "").strip()
        keywords = item.get("keywords")
        if not path or not isinstance(keywords, list):
            continue
        for kw in keywords:
            kw = str(kw).strip()
            if kw:
                result.append((kw, path))

    result.sort(key=lambda x: -len(x[0]))
    return result


def _match_keyword(text: str) -> str | None:
    for kw, path in _load_keywords():
        if kw in text:
            return path
    return None


def _rule(event: MessageEvent) -> bool:
    text = event.get_plaintext()
    if not text or text.startswith("/"):
        return False
    if _match_keyword(text) is None:
        return False
    return _admin_credentials() is not None


_random_image = on_message(rule=Rule(_rule), priority=20, block=True)


async def _get_or_refresh_admin_token() -> str | None:
    token = await zerodrive_repository.get_admin_token()
    if token is not None:
        return token

    creds = _admin_credentials()
    if creds is None:
        return None

    username, password = creds
    result = await login(username, password)
    if result.get("error"):
        return None

    await zerodrive_repository.set_admin_token(
        access_token=result["access_token"],
        username=result["username"],
    )
    return result["access_token"]


async def _refresh_admin_token() -> str | None:
    creds = _admin_credentials()
    if creds is None:
        return None

    username, password = creds
    result = await login(username, password)
    if result.get("error"):
        return None

    await zerodrive_repository.set_admin_token(
        access_token=result["access_token"],
        username=result["username"],
    )
    return result["access_token"]


@_random_image.handle()
async def _handle(bot: Bot, event: MessageEvent) -> None:
    text = event.get_plaintext()
    path = _match_keyword(text)
    if path is None:
        return

    token = await _get_or_refresh_admin_token()
    if token is None:
        return

    result = await zd_random_image(token=token, path=path)
    if isinstance(result.get("error"), str):
        if "登录已过期" in result["error"] or "401" in result["error"]:
            token = await _refresh_admin_token()
            if token is None:
                await _send_text(bot, event, "管理员登录失败，请检查 ZeroDrive 账号配置。")
                return
            result = await zd_random_image(token=token, path=path)
            if isinstance(result.get("error"), str):
                await _send_text(bot, event, f"随机图片失败：{result['error']}")
                return
        else:
            await _send_text(bot, event, f"随机图片失败：{result['error']}")
            return

    try:
        async with httpx.AsyncClient() as client:
            dl_resp = await client.get(result["download_url"], timeout=30.0)
            if dl_resp.status_code >= 400:
                await _send_text(bot, event, f"下载图片失败 HTTP {dl_resp.status_code}")
                return
            image_bytes = dl_resp.content
    except httpx.TimeoutException:
        await _send_text(bot, event, "下载图片超时。")
        return
    except httpx.RequestError as e:
        await _send_text(bot, event, f"下载图片失败：{e}")
        return

    b64 = base64.b64encode(image_bytes).decode()
    msg = MessageSegment.image(file=f"base64://{b64}")
    await _send(bot, event, msg)


async def _send(bot: Bot, event: MessageEvent, msg: MessageSegment) -> None:
    if isinstance(event, GroupMessageEvent):
        await bot.send_group_msg(group_id=event.group_id, message=msg)
    else:
        await bot.send_private_msg(user_id=event.user_id, message=msg)


async def _send_text(bot: Bot, event: MessageEvent, text: str) -> None:
    await _send(bot, event, MessageSegment.text(text))
