"""提醒任务 SQLite 存储。"""

from __future__ import annotations

from typing import Any

import aiosqlite

from bot_core.database import DB_PATH, init_db as _core_init_db


async def _init_reminder_db() -> None:
    await _core_init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_columns(db)


init_db = _init_reminder_db  # 兼容旧调用方，带列迁移检查


async def _ensure_columns(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(reminders)")
    rows = await cur.fetchall()
    names = {str(r[1]) for r in rows}
    if "schedule_kind" not in names:
        await db.execute(
            "ALTER TABLE reminders ADD COLUMN schedule_kind TEXT NOT NULL DEFAULT 'daily'",
        )
    if "once_date" not in names:
        await db.execute("ALTER TABLE reminders ADD COLUMN once_date TEXT")
    await db.commit()


async def insert_reminder(
    *,
    bot_self_id: str,
    target_kind: str,
    target_id: str,
    creator_id: str,
    hour: int,
    minute: int,
    body: str,
    schedule_kind: str = "daily",
    once_date: str | None = None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO reminders
            (bot_self_id, target_kind, target_id, creator_id, hour, minute, body,
             schedule_kind, once_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bot_self_id,
                target_kind,
                target_id,
                creator_id,
                hour,
                minute,
                body,
                schedule_kind,
                once_date,
            ),
        )
        await db.commit()
        rid = cur.lastrowid
    assert rid is not None
    return int(rid)


async def list_reminders(
    *,
    bot_self_id: str,
    target_kind: str,
    target_id: str,
    creator_id: str,
) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT id, hour, minute, body, creator_id, schedule_kind, once_date
            FROM reminders
            WHERE bot_self_id = ? AND target_kind = ? AND target_id = ?
              AND creator_id = ?
            ORDER BY id
            """,
            (bot_self_id, target_kind, target_id, creator_id),
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_creator_for_reminder(
    *,
    rid: int,
    bot_self_id: str,
    target_kind: str,
    target_id: str,
) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT creator_id FROM reminders
            WHERE id = ? AND bot_self_id = ? AND target_kind = ? AND target_id = ?
            """,
            (rid, bot_self_id, target_kind, target_id),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return str(row["creator_id"])


async def delete_reminder(*, rid: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM reminders WHERE id = ?", (rid,))
        await db.commit()


async def get_payload_for_send(*, rid: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT target_kind, target_id, body, schedule_kind
            FROM reminders WHERE id = ?
            """,
            (rid,),
        )
        row = await cur.fetchone()
    return dict(row) if row else None


async def iter_schedule_rows() -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT id, bot_self_id, hour, minute, schedule_kind, once_date
            FROM reminders
            """,
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]
