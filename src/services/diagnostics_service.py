"""联通测试类逻辑（与 OneBot 无关的纯文本）。"""

from __future__ import annotations

from bot_core.help_registry import register_help_section

__all__ = ["ping_reply", "echo_reply"]


def ping_reply() -> str:
    return "pong"


def echo_reply(text: str) -> str:
    t = text.strip()
    if not t:
        return "/echo <文字>"
    return t

