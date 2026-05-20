"""Apex 地图轮换：调用 api.mozambiquehe.re（文档见 https://apexlegendsapi.com/）。"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from bot_core.help_registry import register_help_section

_CN_TZ = ZoneInfo("Asia/Shanghai")
_READABLE_FMT = "%Y-%m-%d %H:%M:%S"
_SHIFT_READABLE_HOURS = 8  # 接口可读时间相对东八区偏 8 小时，展示前加 8 小时

__all__ = ["fetch_map_rotation_text"]

_MAPROTATION_PATH = "/maprotation"

_MODE_ORDER_LABELS: tuple[tuple[str, str], ...] = (
    ("battle_royale", "匹配"),
    ("ranked", "排位"),
    ("ltm", "娱乐模式"),
)


def _apex_base_url() -> str:
    return os.environ.get("APEX_API_BASE_URL", "https://api.mozambiquehe.re").rstrip("/")


def _apex_api_key() -> str | None:
    key = os.environ.get("APEX_API_KEY", "").strip()
    return key or None


def _api_error_message(data: dict[str, Any]) -> str | None:
    err = data.get("Error") or data.get("error")
    if err is None:
        return None
    if isinstance(err, str):
        return err
    return str(err)


def _total_remaining_minutes(phase: dict[str, Any], now: int) -> int | None:
    rm = phase.get("remainingMins")
    if rm is not None:
        try:
            return max(0, int(rm))
        except (TypeError, ValueError):
            pass
    end = phase.get("end")
    if isinstance(end, (int, float)) and float(end) > now:
        return max(0, int((float(end) - now) // 60))
    return None


def _format_hours_minutes_after(total_mins: int) -> str:
    """始终带「小时+分钟」，再接「后」，例如 0小时45分钟后、2小时0分钟后。"""
    total_mins = max(0, int(total_mins))
    h, m = divmod(total_mins, 60)
    return f"{h}小时{m}分钟后"


def _remaining_after_phrase(phase: dict[str, Any], now: int) -> str:
    mins = _total_remaining_minutes(phase, now)
    if mins is not None:
        return _format_hours_minutes_after(mins)
    rt = phase.get("remainingTimer")
    if isinstance(rt, str) and rt.strip():
        return f"{rt.strip()}后"
    return ""


def _first_non_empty_str(phase: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for k in keys:
        v = phase.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _shift_readable_to_display(raw: str) -> str:
    """接口返回的可读时间整体加 8 小时后再展示（按东八区习惯）。"""
    s = raw.strip()
    try:
        naive = datetime.strptime(s, _READABLE_FMT)
    except ValueError:
        return s
    shifted = naive + timedelta(hours=_SHIFT_READABLE_HOURS)
    return shifted.strftime(_READABLE_FMT)


def _display_end_time_str(phase: dict[str, Any]) -> str | None:
    """本段地图结束时刻：优先可读结束时间（加 8 小时），否则用 Unix end 转北京时间。"""
    raw = _first_non_empty_str(
        phase,
        (
            "readableDate_end",
            "readableDateEnd",
            "readable_date_end",
            "readableDate_start",
            "readableDateStart",
            "readable_date_start",
        ),
    )
    if raw:
        return _shift_readable_to_display(raw)
    end = phase.get("end")
    if isinstance(end, (int, float)):
        try:
            dt_utc = datetime.fromtimestamp(float(end), tz=UTC)
            return dt_utc.astimezone(_CN_TZ).strftime(_READABLE_FMT)
        except (OSError, OverflowError, ValueError):
            return None
    return None


def _phase_line(prefix: str, phase: dict[str, Any], now: int) -> str:
    mname = phase.get("map") or "?"
    ev = phase.get("eventName") or phase.get("eventname")
    if isinstance(ev, str) and ev.strip() and ev.strip().lower() != str(mname).lower():
        title = f"{mname}（{ev.strip()}）"
    else:
        title = str(mname)
    when_disp = _display_end_time_str(phase)
    rem = _remaining_after_phrase(phase, now)
    parts: list[str] = [f"{prefix}{title}"]
    if when_disp:
        tail = f"结束于 {when_disp}"
        if rem:
            tail = f"{tail}（{rem}）"
        parts.append(tail)
    elif rem:
        parts.append(rem)
    return "\n".join(parts)


def _format_mode_block(label: str, block: dict[str, Any], now: int) -> list[str]:
    cur = block.get("current")
    nxt = block.get("next")
    lines = [f"【{label}】"]
    if isinstance(cur, dict):
        lines.append(_phase_line("当前：", cur, now))
    else:
        lines.append("当前：—")
    if isinstance(nxt, dict):
        lines.append(_phase_line("下一：", nxt, now))
    else:
        lines.append("下一：—")
    return lines


def _format_payload(data: dict[str, Any]) -> str:
    now = int(time.time())
    pieces: list[str] = []
    for key, label in _MODE_ORDER_LABELS:
        block = data.get(key)
        if not isinstance(block, dict):
            continue
        pieces.extend(_format_mode_block(label, block, now))
    if not pieces:
        # version=1 时可能仅有顶层 current/next
        cur, nxt = data.get("current"), data.get("next")
        if isinstance(cur, dict) or isinstance(nxt, dict):
            pseudo_block: dict[str, Any] = {}
            if isinstance(cur, dict):
                pseudo_block["current"] = cur
            if isinstance(nxt, dict):
                pseudo_block["next"] = nxt
            pieces = _format_mode_block("大逃杀 · 匹配", pseudo_block, now)
        else:
            return "接口返回了无法识别的地图轮换结构，请稍后再试。"
    pieces.append("数据：Apex Legends Status https://apexlegendsstatus.com")
    return "\n".join(pieces)


async def fetch_map_rotation_text() -> str:
    key = _apex_api_key()
    if not key:
        return "未配置环境变量 APEX_API_KEY，无法查询地图轮换。"

    url = f"{_apex_base_url()}{_MAPROTATION_PATH}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                params={"version": 2},
                headers={"Authorization": key},
                timeout=20.0,
            )
    except httpx.TimeoutException:
        return "查询地图轮换超时，请稍后再试。"
    except httpx.RequestError:
        return "网络请求失败，请稍后再试。"

    if resp.status_code == 403:
        return "API Key 无效或未授权（HTTP 403）。"
    if resp.status_code == 429:
        return "请求过于频繁，触发了接口限流（HTTP 429），请稍后再试。"

    try:
        data = resp.json()
    except ValueError:
        return "接口返回了非 JSON 内容，请稍后再试。"

    if not isinstance(data, dict):
        return "接口返回格式异常，请稍后再试。"

    api_err = _api_error_message(data)
    if api_err:
        return f"接口错误：{api_err}"

    if resp.status_code != 200:
        return f"查询失败（HTTP {resp.status_code}），请稍后再试。"

    return _format_payload(data)


register_help_section(
    order=35,
    title="Apex 地图",
    body="当前地图轮换（大逃杀/排位/竞技场/限时等）\n/apex地图 · /apex图",
)
