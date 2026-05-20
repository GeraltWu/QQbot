"""帮助文案注册表：各模块在 import 时注册，/帮助 时按 order 聚合渲染。"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["register_help_section", "render_help_text"]


@dataclass(frozen=True, slots=True)
class _HelpSection:
    order: int
    title: str
    body: str


_sections: list[_HelpSection] = []


def register_help_section(*, order: int = 100, title: str, body: str) -> None:
    """注册一块帮助；相同 title 会覆盖旧内容，便于热重载不重复。"""
    global _sections
    body = body.strip()
    filtered = [s for s in _sections if s.title != title]
    filtered.append(_HelpSection(order=order, title=title, body=body))
    _sections = sorted(filtered, key=lambda s: (s.order, s.title))


def render_help_text() -> str:
    blocks = [f"【{s.title}】\n{s.body}" for s in _sections]
    return "\n\n".join(blocks)
