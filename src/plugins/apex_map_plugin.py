"""Apex 地图轮换插件：数据来自 Mozambique API（见 services.apex_map_service）。"""

from __future__ import annotations

import base64

from nonebot import get_driver, on_command
from nonebot.adapters.onebot.v11 import MessageSegment

from services.apex_map_card import close_map_card_renderer
from services.apex_map_service import fetch_map_rotation_card

apex_map = on_command("apex地图", aliases={"apex图"}, priority=14, block=True)


@apex_map.handle()
async def _handle_apex_map() -> None:
    result = await fetch_map_rotation_card()
    if isinstance(result, bytes):
        encoded = base64.b64encode(result).decode("ascii")
        msg = MessageSegment.image(file=f"base64://{encoded}")
    else:
        msg = result
    await apex_map.finish(msg)


@get_driver().on_shutdown
async def _close_renderer() -> None:
    await close_map_card_renderer()
