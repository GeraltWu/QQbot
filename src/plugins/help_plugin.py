"""帮助插件：文案由各模块注册到 bot_core.help_registry。"""

import services.ai_service  # noqa: F401  # 侧效应：注册「规划中」帮助块

from nonebot import on_command, on_message
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot.rule import Rule

from bot_core.help_registry import render_help_text

help_cmd = on_command("帮助", aliases={"help", "菜单", "功能"}, priority=5, block=True)


@help_cmd.handle()
async def _handle_help() -> None:
    await help_cmd.finish(render_help_text())


async def _at_bot_help_rule(event: Event) -> bool:
    """群内消息只要 @ 到本机器人即回复帮助。"""
    if not isinstance(event, GroupMessageEvent):
        return False
    self_id = str(event.self_id)
    for seg in event.message:
        if seg.type != "at":
            continue
        qq = seg.data.get("qq")
        if str(qq) == self_id:
            return True
    return False


at_help = on_message(Rule(_at_bot_help_rule), priority=6, block=True)


@at_help.handle()
async def _handle_at_help(matcher: Matcher) -> None:
    await matcher.finish(render_help_text())
