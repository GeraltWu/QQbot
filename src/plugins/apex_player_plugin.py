"""Apex 玩家查询与 QQ 绑定（/bridge）。"""

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg

from services.apex_player_service import (
    fetch_player_bridge_summary,
    handle_apex_bind,
    handle_apex_unbind,
)

apex_player = on_command("apex玩家", aliases={"apex查"}, priority=14, block=True)
apex_bind = on_command("apex绑定", priority=14, block=True)
apex_unbind = on_command("apex解绑", priority=14, block=True)


@apex_player.handle()
async def _handle_apex_player(event: MessageEvent, args: Message = CommandArg()) -> None:
    raw = args.extract_plain_text()
    msg = await fetch_player_bridge_summary(
        raw,
        bot_self_id=str(event.self_id),
        qq_user_id=str(event.get_user_id()),
    )
    await apex_player.finish(msg)


@apex_bind.handle()
async def _handle_apex_bind(event: MessageEvent, args: Message = CommandArg()) -> None:
    raw = args.extract_plain_text().strip()
    if not raw:
        await apex_bind.finish("/apex绑定 游戏昵称 [PC|PS4|X1]")
    msg = await handle_apex_bind(
        raw,
        bot_self_id=str(event.self_id),
        qq_user_id=str(event.get_user_id()),
    )
    await apex_bind.finish(msg)


@apex_unbind.handle()
async def _handle_apex_unbind(event: MessageEvent) -> None:
    msg = await handle_apex_unbind(
        bot_self_id=str(event.self_id),
        qq_user_id=str(event.get_user_id()),
    )
    await apex_unbind.finish(msg)
