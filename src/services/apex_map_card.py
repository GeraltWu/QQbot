"""将 Apex 地图轮换数据渲染为 HTML/CSS 卡片并截图为 PNG。"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).with_name("templates")
_CN_TZ = ZoneInfo("Asia/Shanghai")
_READABLE_FMT = "%Y-%m-%d %H:%M:%S"
_MODE_ORDER_LABELS: tuple[tuple[str, str, str], ...] = (
    ("battle_royale", "匹配", "PUBLIC MATCH"),
    ("ranked", "排位", "RANKED LEAGUES"),
    ("ltm", "娱乐模式", "LIMITED TIME MODE"),
)


def _total_remaining_minutes(phase: dict[str, Any], now: int) -> int | None:
    remaining = phase.get("remainingMins")
    if remaining is not None:
        try:
            return max(0, int(remaining))
        except (TypeError, ValueError):
            pass
    end = phase.get("end")
    if isinstance(end, (int, float)) and float(end) > now:
        return max(0, int((float(end) - now) // 60))
    return None


def _remaining_text(phase: dict[str, Any], now: int) -> str:
    remaining = _total_remaining_minutes(phase, now)
    if remaining is not None:
        if remaining <= 0:
            return "即将切换"
        hours, minutes = divmod(remaining, 60)
        if hours == 0:
            return f"{minutes} 分钟"
        if minutes == 0:
            return f"{hours} 小时"
        return f"{hours} 小时 {minutes} 分钟"
    timer = phase.get("remainingTimer")
    if isinstance(timer, str) and timer.strip():
        return timer.strip()
    return ""


def _display_end_time_str(phase: dict[str, Any]) -> str | None:
    for key in (
        "readableDate_end",
        "readableDateEnd",
        "readable_date_end",
        "readableDate_start",
        "readableDateStart",
        "readable_date_start",
    ):
        raw = phase.get(key)
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = datetime.strptime(raw.strip(), _READABLE_FMT).replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                return raw.strip()
            return (parsed + timedelta(hours=8)).strftime(_READABLE_FMT)

    end = phase.get("end")
    if isinstance(end, (int, float)):
        try:
            utc_time = datetime.fromtimestamp(float(end), tz=timezone.utc)
            return utc_time.astimezone(_CN_TZ).strftime(_READABLE_FMT)
        except (OSError, OverflowError, ValueError):
            return None
    return None


def _switch_time_text(phase: Any, now: int) -> str:
    if not isinstance(phase, dict):
        return "时间未知"
    raw = _display_end_time_str(phase)
    if not raw:
        return "时间未知"
    try:
        switch_time = datetime.strptime(raw, _READABLE_FMT).replace(tzinfo=_CN_TZ)
    except ValueError:
        return raw

    now_time = datetime.fromtimestamp(now, tz=timezone.utc).astimezone(_CN_TZ)
    day_delta = (switch_time.date() - now_time.date()).days
    clock = switch_time.strftime("%H:%M")
    if day_delta == 0:
        return clock
    if day_delta == 1:
        return f"明天 {clock}"
    return f"{switch_time.month}月{switch_time.day}日 {clock}"


def _text(value: Any, default: str = "—") -> str:
    if value is None:
        return default
    result = str(value).strip()
    return result or default


def _phase_view(phase: Any, now: int, *, current: bool) -> dict[str, Any]:
    if not isinstance(phase, dict):
        return {
            "available": False,
            "map": "暂无数据",
            "event": "",
            "end_time": "—",
            "remaining": "时间未知",
            "progress_percent": 0,
        }

    map_name = _text(phase.get("map"), "未知地图")
    event = _text(phase.get("eventName") or phase.get("eventname"), "")
    if event.casefold() == map_name.casefold():
        event = ""

    progress = 0
    if current:
        start = phase.get("start")
        end = phase.get("end")
        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            duration = float(end) - float(start)
            if duration > 0:
                elapsed_ratio = (now - float(start)) / duration
                progress = round(min(1.0, max(0.0, elapsed_ratio)) * 100)
        elif (remaining := _total_remaining_minutes(phase, now)) is not None:
            # 接口没有开始时间时无法推算真实比例，仅保留一个中性的进度提示。
            progress = 50 if remaining > 0 else 100

    return {
        "available": True,
        "map": map_name,
        "event": event,
        "end_time": _display_end_time_str(phase) or "—",
        "remaining": _remaining_text(phase, now) or "时间未知",
        "progress_percent": progress,
    }


def build_map_rotation_view(
    data: dict[str, Any], *, now: int | None = None
) -> dict[str, Any]:
    """把第三方接口结构转换为模板使用的稳定视图模型。"""
    timestamp = int(time.time()) if now is None else now
    modes: list[dict[str, Any]] = []
    for key, label, subtitle in _MODE_ORDER_LABELS:
        block = data.get(key)
        if not isinstance(block, dict):
            continue
        current_view = _phase_view(block.get("current"), timestamp, current=True)
        next_view = _phase_view(block.get("next"), timestamp, current=False)
        switch_at = _switch_time_text(block.get("current"), timestamp)
        next_end_at = _switch_time_text(block.get("next"), timestamp)
        modes.append(
            {
                "key": key,
                "label": label,
                "subtitle": subtitle,
                "current": current_view,
                "next": next_view,
                "switch_at": switch_at,
                "next_end_at": next_end_at,
            }
        )

    if not modes:
        current = data.get("current")
        following = data.get("next")
        if isinstance(current, dict) or isinstance(following, dict):
            current_view = _phase_view(current, timestamp, current=True)
            next_view = _phase_view(following, timestamp, current=False)
            switch_at = _switch_time_text(current, timestamp)
            next_end_at = _switch_time_text(following, timestamp)
            modes.append(
                {
                    "key": "battle_royale",
                    "label": "匹配",
                    "subtitle": "BATTLE ROYALE",
                    "current": current_view,
                    "next": next_view,
                    "switch_at": switch_at,
                    "next_end_at": next_end_at,
                }
            )

    updated = datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(_CN_TZ)
    return {
        "modes": modes,
        "mode_count": max(1, len(modes)),
        "updated_at": updated.strftime("%Y-%m-%d %H:%M"),
    }


class _MapCardRenderer:
    def __init__(self) -> None:
        self._playwright: Any = None
        self._browser: Any = None
        self._start_lock = asyncio.Lock()
        self._render_slots = asyncio.Semaphore(3)
        self._templates = Environment(
            loader=FileSystemLoader(_TEMPLATE_DIR),
            autoescape=select_autoescape(("html", "xml")),
            enable_async=False,
        )

    async def _ensure_browser(self) -> Any:
        if self._browser is not None and self._browser.is_connected():
            return self._browser
        async with self._start_lock:
            if self._browser is not None and self._browser.is_connected():
                return self._browser
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            return self._browser

    async def render(self, view: dict[str, Any]) -> bytes:
        template = self._templates.get_template("apex_map_rotation.html")
        html = template.render(**view)
        async with self._render_slots:
            browser = await self._ensure_browser()
            page = await browser.new_page(
                viewport={"width": 960, "height": 1500},
                device_scale_factor=1,
            )
            try:
                await page.set_content(html, wait_until="load")
                card = page.locator("#apex-map-card")
                return await card.screenshot(type="png")
            finally:
                await page.close()

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None


_renderer = _MapCardRenderer()


async def render_map_rotation_card(data: dict[str, Any]) -> bytes:
    view = build_map_rotation_view(data)
    if not view["modes"]:
        raise ValueError("地图轮换响应中没有可渲染的模式")
    return await _renderer.render(view)


async def close_map_card_renderer() -> None:
    await _renderer.close()
