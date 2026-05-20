"""Apex 玩家概况：GET /bridge（https://apexlegendsapi.com/）与 QQ 绑定。"""

from __future__ import annotations

import os
from typing import Any

import httpx

from bot_core.help_registry import register_help_section
from repositories import apex_link_repository

__all__ = [
    "fetch_player_bridge_summary",
    "handle_apex_bind",
    "handle_apex_unbind",
]

_BRIDGE_PATH = "/bridge"

_PLATFORM_ALIASES: dict[str, str] = {
    "pc": "PC",
    "steam": "PC",
    "origin": "PC",
    "ps4": "PS4",
    "ps5": "PS4",
    "psn": "PS4",
    "playstation": "PS4",
    "x1": "X1",
    "xbox": "X1",
}


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


def _parse_name_and_platform(raw: str) -> tuple[str, str] | str:
    s = raw.strip()
    if not s:
        return (
            "用法：/apex绑定 游戏昵称 [平台] 绑定后，可用 /apex玩家 省略昵称。\n"
            "带昵称查询：/apex玩家 <昵称> [平台]\n"
            "平台可选：PC（默认）、PS4、X1；昵称含空格时把平台写在最后。"
        )
    parts = s.split()
    last = parts[-1].lower()
    if last in _PLATFORM_ALIASES:
        plat = _PLATFORM_ALIASES[last]
        name = " ".join(parts[:-1]).strip()
        if not name:
            return "请提供玩家昵称（不能只写平台）。"
        return name, plat
    return s, "PC"


def _format_br_rank(rank: dict[str, Any]) -> str | None:
    name = rank.get("rankName") or rank.get("rankDivName")
    div = rank.get("rankDiv")
    score = rank.get("rankScore")
    chunks: list[str] = []
    if name:
        if div is not None and str(div).strip() != "":
            chunks.append(f"{name} {div}")
        else:
            chunks.append(str(name))
    if score is not None:
        try:
            chunks.append(f"RP {int(score)}")
        except (TypeError, ValueError):
            chunks.append(f"RP {score}")
    return " · ".join(chunks) if chunks else None


def _realtime_status_line(rt: dict[str, Any]) -> str:
    raw = rt.get("isOnline")
    if raw == 1:
        status = "在线"
    elif raw == 0:
        status = "离线"
    else:
        status = "未知"
    return f"状态：{status}"


def _selected_legend(data: dict[str, Any]) -> str | None:
    rt = data.get("realtime")
    if isinstance(rt, dict):
        s = rt.get("selectedLegend")
        if isinstance(s, str) and s.strip():
            return s.strip()
    leg = data.get("legends")
    if isinstance(leg, dict):
        sel = leg.get("selected")
        if isinstance(sel, dict):
            ln = sel.get("LegendName")
            if isinstance(ln, str) and ln.strip():
                return ln.strip()
    return None


def _format_bridge_summary(data: dict[str, Any]) -> str:
    g = data.get("global")
    if not isinstance(g, dict):
        return "接口未返回 global 字段，无法展示。"

    name = g.get("name") or "?"
    plat = g.get("platform") or "?"
    level = g.get("level")
    line1 = f"{name} · {plat}"
    if level is not None:
        line1 += f" · Lv.{level}"

    lines: list[str] = [line1]

    rank = g.get("rank")
    br = _format_br_rank(rank) if isinstance(rank, dict) else None
    if br:
        lines.append(f"排位：{br}")

    rt = data.get("realtime")
    if isinstance(rt, dict):
        lines.append(_realtime_status_line(rt))
    legend = _selected_legend(data)
    if legend:
        lines.append(f"当前选中传奇：{legend}")

    lines.append("数据：Apex Legends Status https://apexlegendsstatus.com")
    return "\n".join(lines)


async def _request_bridge(player: str, platform: str) -> str:
    key = _apex_api_key()
    if not key:
        return "未配置环境变量 APEX_API_KEY，无法查询玩家数据。"

    url = f"{_apex_base_url()}{_BRIDGE_PATH}"
    params: dict[str, str | int] = {
        "player": player,
        "platform": platform,
        "version": 5,
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                params=params,
                headers={"Authorization": key},
                timeout=25.0,
            )
    except httpx.TimeoutException:
        return "查询玩家数据超时，请稍后再试。"
    except httpx.RequestError:
        return "网络请求失败，请稍后再试。"

    try:
        data = resp.json()
    except ValueError:
        return "接口返回了非 JSON 内容，请稍后再试。"

    if not isinstance(data, dict):
        return "接口返回格式异常，请稍后再试。"

    api_err = _api_error_message(data)
    if api_err:
        return f"接口错误：{api_err}"

    if resp.status_code == 404:
        return "未找到该玩家，请核对昵称与平台（PC 需为 EA/Origin 绑定名）。"
    if resp.status_code == 403:
        return "API Key 无效或未授权（HTTP 403）。"
    if resp.status_code == 429:
        return "请求过于频繁，触发了接口限流（HTTP 429），请稍后再试。"
    if resp.status_code != 200:
        return f"查询失败（HTTP {resp.status_code}），请稍后再试。"

    return _format_bridge_summary(data)


async def fetch_player_bridge_summary(
    raw_args: str,
    *,
    bot_self_id: str,
    qq_user_id: str,
) -> str:
    raw = raw_args.strip()
    if not raw:
        linked = await apex_link_repository.get_link(
            bot_self_id=bot_self_id,
            qq_user_id=qq_user_id,
        )
        if linked is None:
            return (
                "尚未绑定 Apex 游戏名。请先发：/apex绑定 游戏昵称 [PC|PS4|X1]\n"
                "绑定后可直接发 /apex玩家 查询自己。"
            )
        player, platform = linked
        return await _request_bridge(player, platform)

    parsed = _parse_name_and_platform(raw)
    if isinstance(parsed, str):
        return parsed
    player, platform = parsed
    return await _request_bridge(player, platform)


async def handle_apex_bind(
    raw: str,
    *,
    bot_self_id: str,
    qq_user_id: str,
) -> str:
    parsed = _parse_name_and_platform(raw.strip())
    if isinstance(parsed, str):
        return parsed
    player, platform = parsed
    await apex_link_repository.upsert_link(
        bot_self_id=bot_self_id,
        qq_user_id=qq_user_id,
        player_name=player,
        platform=platform,
    )
    return f"已绑定：{player} · {platform}。发 /apex玩家 可省略昵称查询。"


async def handle_apex_unbind(*, bot_self_id: str, qq_user_id: str) -> str:
    ok = await apex_link_repository.delete_link(
        bot_self_id=bot_self_id,
        qq_user_id=qq_user_id,
    )
    if ok:
        return "已解除 Apex 绑定。"
    return "当前没有绑定记录。"


register_help_section(
    order=36,
    title="Apex 玩家",
    body=(
        "排位、在线状态与选中传奇\n"
        "/apex玩家 昵称 [PC|PS4|X1] · 绑定后可只发 /apex玩家\n"
        "/apex绑定 游戏昵称 [平台] · /apex解绑\n"
        "例：/apex绑定 MyName PS4"
    ),
)
