"""Apex 地图轮换插件：数据来自 Mozambique API（见 services.apex_map_service）。"""

from nonebot import on_command

from services.apex_map_service import fetch_map_rotation_text  # noqa: F401  # 侧效应：注册帮助

apex_map = on_command("apex地图", aliases={"apex图"}, priority=14, block=True)


@apex_map.handle()
async def _handle_apex_map() -> None:
    msg = await fetch_map_rotation_text()
    await apex_map.finish(msg)
