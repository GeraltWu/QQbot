"""定时提醒：解析指令、调度任务、投递消息。"""

from __future__ import annotations

import re
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from nonebot import get_bot, require
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageEvent,
    MessageSegment,
    PrivateMessageEvent,
)

from bot_core.help_registry import register_help_section
from repositories import reminder_repository

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler  # noqa: E402

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
_TZ_NAME = "Asia/Shanghai"
_TZ = ZoneInfo(_TZ_NAME)
_DATED_ADD_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s+([01]?\d|2[0-3]):([0-5]\d)\s+(.+)$",
    re.DOTALL,
)
_DAILY_ADD_RE = re.compile(
    r"^([01]?\d|2[0-3]):([0-5]\d)\s+(.+)$",
    re.DOTALL,
)

__all__ = [
    "bootstrap_reminders",
    "handle_reminder_command",
    "send_reminder",
    "session_target",
]


def _job_id(rid: int) -> str:
    return f"reminder_{rid}"


def session_target(event: MessageEvent) -> tuple[str, str]:
    if isinstance(event, GroupMessageEvent):
        return "group", str(event.group_id)
    if isinstance(event, PrivateMessageEvent):
        return "private", str(event.user_id)
    return "private", str(event.get_user_id())


async def _creator_display(bot: Bot, event: MessageEvent, creator_id: str) -> str:
    try:
        uid = int(creator_id)
    except ValueError:
        return creator_id
    try:
        if isinstance(event, GroupMessageEvent):
            info = await bot.get_group_member_info(
                group_id=event.group_id,
                user_id=uid,
                no_cache=False,
            )
            card = (getattr(info, "card", None) or "").strip()
            nick = (getattr(info, "nickname", None) or "").strip()
            return card or nick or creator_id
        info = await bot.get_stranger_info(user_id=uid, no_cache=False)
        nick = (getattr(info, "nickname", None) or "").strip()
        return nick or creator_id
    except Exception:
        return creator_id


def _once_run_at(once_date: str, hour: int, minute: int) -> datetime | None:
    try:
        d = date.fromisoformat(once_date)
    except ValueError:
        return None
    return datetime.combine(d, time(hour, minute, 0), tzinfo=_TZ)


async def send_reminder(rid: int, bot_self_id: str) -> None:
    try:
        bot = get_bot(bot_self_id)
    except KeyError:
        return
    row = await reminder_repository.get_payload_for_send(rid=rid)
    if row is None:
        try:
            scheduler.remove_job(_job_id(rid))
        except KeyError:
            pass
        return
    msg = MessageSegment.text(f"【提醒】{row['body']}")
    if row["target_kind"] == "group":
        await bot.send_group_msg(group_id=int(row["target_id"]), message=msg)
    else:
        await bot.send_private_msg(user_id=int(row["target_id"]), message=msg)

    kind = row.get("schedule_kind") or "daily"
    if kind == "once":
        await reminder_repository.delete_reminder(rid=rid)
        try:
            scheduler.remove_job(_job_id(rid))
        except KeyError:
            pass


async def _add_scheduler_job_daily(
    rid: int,
    bot_self_id: str,
    hour: int,
    minute: int,
) -> None:
    scheduler.add_job(
        send_reminder,
        "cron",
        id=_job_id(rid),
        replace_existing=True,
        hour=hour,
        minute=minute,
        timezone=_TZ_NAME,
        kwargs={"rid": rid, "bot_self_id": bot_self_id},
        misfire_grace_time=120,
    )


async def _add_scheduler_job_once(
    rid: int,
    bot_self_id: str,
    run_at: datetime,
) -> None:
    scheduler.add_job(
        send_reminder,
        "date",
        id=_job_id(rid),
        replace_existing=True,
        run_date=run_at,
        kwargs={"rid": rid, "bot_self_id": bot_self_id},
        misfire_grace_time=300,
    )


async def bootstrap_reminders() -> None:
    await reminder_repository.init_db()
    now = datetime.now(_TZ)
    for r in await reminder_repository.iter_schedule_rows():
        rid = int(r["id"])
        bot_self_id = str(r["bot_self_id"])
        hour, minute = int(r["hour"]), int(r["minute"])
        kind = (r.get("schedule_kind") or "daily").strip()
        if kind == "once":
            od = r.get("once_date")
            if not isinstance(od, str) or not od.strip():
                await reminder_repository.delete_reminder(rid=rid)
                continue
            run_at = _once_run_at(od.strip(), hour, minute)
            if run_at is None:
                await reminder_repository.delete_reminder(rid=rid)
                continue
            if run_at <= now:
                await reminder_repository.delete_reminder(rid=rid)
                continue
            await _add_scheduler_job_once(rid, bot_self_id, run_at)
        else:
            await _add_scheduler_job_daily(rid, bot_self_id, hour, minute)


def _schedule_label(r: dict[str, object]) -> str:
    h, m = int(r["hour"]), int(r["minute"])
    t = f"{h:02d}:{m:02d}"
    kind = (r.get("schedule_kind") or "daily").strip()
    if kind == "once" and isinstance(r.get("once_date"), str) and r["once_date"].strip():
        return f"{r['once_date'].strip()} {t}（一次）"
    return f"每天{t}"


async def handle_reminder_command(
    *,
    raw: str,
    bot_self_id: str,
    creator_id: str,
    target_kind: str,
    target_id: str,
    bot: Bot | None = None,
    event: MessageEvent | None = None,
) -> str:
    if not raw:
        return (
            "/提醒 添加 HH:mm 内容 | /提醒 添加 YYYY-MM-DD HH:mm 内容（仅一次）\n"
            "/提醒 列表 | /提醒 删除 编号"
        )
    parts = raw.split(maxsplit=1)
    sub = parts[0]

    if sub in ("添加", "add"):
        if len(parts) < 2:
            return "/提醒 添加 HH:mm 内容 或 /提醒 添加 YYYY-MM-DD HH:mm 内容"
        rest = parts[1].strip()
        m_d = _DATED_ADD_RE.match(rest)
        if m_d:
            date_s, hs, ms, body = m_d.group(1), m_d.group(2), m_d.group(3), m_d.group(4).strip()
            if not body:
                return "内容不能为空"
            hour, minute = int(hs), int(ms)
            ts = f"{hour:02d}:{minute:02d}"
            if not _TIME_RE.match(ts):
                return "时间用 HH:mm（24h）"
            run_at = _once_run_at(date_s, hour, minute)
            if run_at is None:
                return "日期无效，请用 YYYY-MM-DD"
            if run_at <= datetime.now(_TZ):
                return "该日期时间已过，请重新设置"
            rid = await reminder_repository.insert_reminder(
                bot_self_id=bot_self_id,
                target_kind=target_kind,
                target_id=target_id,
                creator_id=creator_id,
                hour=hour,
                minute=minute,
                body=body,
                schedule_kind="once",
                once_date=date_s,
            )
            await _add_scheduler_job_once(rid, bot_self_id, run_at)
            return f"已加 #{rid} {date_s} {hour:02d}:{minute:02d}（仅一次）：{body}"

        m_t = _DAILY_ADD_RE.match(rest)
        if not m_t:
            return "/提醒 添加 HH:mm 内容 或 /提醒 添加 YYYY-MM-DD HH:mm 内容"
        hs, ms, body = m_t.group(1), m_t.group(2), m_t.group(3).strip()
        if not body:
            return "内容不能为空"
        hour, minute = int(hs), int(ms)
        ts = f"{hour:02d}:{minute:02d}"
        if not _TIME_RE.match(ts):
            return "时间用 HH:mm（24h）"
        rid = await reminder_repository.insert_reminder(
            bot_self_id=bot_self_id,
            target_kind=target_kind,
            target_id=target_id,
            creator_id=creator_id,
            hour=hour,
            minute=minute,
            body=body,
            schedule_kind="daily",
            once_date=None,
        )
        await _add_scheduler_job_daily(rid, bot_self_id, hour, minute)
        return f"已加 #{rid} 每天{hour:02d}:{minute:02d}：{body}"

    if sub in ("列表", "list"):
        rows = await reminder_repository.list_reminders(
            bot_self_id=bot_self_id,
            target_kind=target_kind,
            target_id=target_id,
            creator_id=creator_id,
        )
        if not rows:
            return "暂无提醒"
        nick_cache: dict[str, str] = {}
        lines: list[str] = []
        for r in rows:
            uid = str(r["creator_id"])
            if uid not in nick_cache:
                if bot is not None and event is not None:
                    nick_cache[uid] = await _creator_display(bot, event, uid)
                else:
                    nick_cache[uid] = uid
            preview = r["body"] if len(r["body"]) <= 40 else r["body"][:40] + "…"
            sched = _schedule_label(r)
            lines.append(
                f"{r['id']}. {sched} · {nick_cache[uid]} · {preview}",
            )
        return "\n".join(lines)

    if sub in ("删除", "del", "remove"):
        tail = parts[1] if len(parts) > 1 else ""
        rid_s = tail.split(maxsplit=1)[0] if tail else ""
        if not rid_s.isdigit():
            return "/提醒 删除 编号"
        rid = int(rid_s)
        creator = await reminder_repository.get_creator_for_reminder(
            rid=rid,
            bot_self_id=bot_self_id,
            target_kind=target_kind,
            target_id=target_id,
        )
        if creator is None:
            return "无此编号"
        if creator != creator_id:
            return "仅能删自己的"
        await reminder_repository.delete_reminder(rid=rid)
        try:
            scheduler.remove_job(_job_id(rid))
        except KeyError:
            pass
        return f"已删 #{rid}"

    return "子命令：添加/列表/删除"


register_help_section(
    order=40,
    title="定时提醒",
    body=(
        "发到当前群/私聊；列表仅看自己创建的\n"
        "/提醒 添加 22:30 喝水（每天）\n"
        "/提醒 添加 2026-05-10 09:00 开会（该日仅一次）\n"
        "/提醒 列表 · /提醒 删除 编号\n"
        "英文：add list del"
    ),
)
