"""未识别以 / 开头的输入时给出简短指引（优先级最低，在所有指令之后尝试）。"""

from __future__ import annotations

from nonebot import on_message
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.matcher import Matcher
from nonebot.rule import Rule

from bot_core.help_registry import register_help_section

UNKNOWN_SLASH_HINT = "未知指令，发 /帮助"


async def _looks_like_slash_command(event: MessageEvent) -> bool:
    text = event.get_plaintext().strip()
    return len(text) >= 1 and text.startswith("/")


# 数值越大优先级越低，确保在 ping、帮助、提醒等之后处理
unknown_slash = on_message(
    Rule(_looks_like_slash_command),
    priority=10000,
    block=True,
)


@unknown_slash.handle()
async def _handle_unknown_slash(matcher: Matcher) -> None:
    await matcher.finish(UNKNOWN_SLASH_HINT)


register_help_section(
    order=200,
    title="输错指令",
    body="不认识的 / 开头指令会提示「未知指令」；发 /帮助 查命令。",
)
