"""QQ 用户与 Apex（Mozambique）玩家名、平台的绑定。"""

from __future__ import annotations

import aiosqlite

from bot_core.database import DB_PATH, init_db


async def get_link(*, bot_self_id: str, qq_user_id: str) -> tuple[str, str] | None:
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT player_name, platform FROM apex_player_links
            WHERE bot_self_id = ? AND qq_user_id = ?
            """,
            (bot_self_id, qq_user_id),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return str(row["player_name"]), str(row["platform"])


async def upsert_link(
    *,
    bot_self_id: str,
    qq_user_id: str,
    player_name: str,
    platform: str,
) -> None:
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO apex_player_links (bot_self_id, qq_user_id, player_name, platform)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(bot_self_id, qq_user_id) DO UPDATE SET
                player_name = excluded.player_name,
                platform = excluded.platform
            """,
            (bot_self_id, qq_user_id, player_name, platform),
        )
        await db.commit()


async def delete_link(*, bot_self_id: str, qq_user_id: str) -> bool:
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM apex_player_links WHERE bot_self_id = ? AND qq_user_id = ?",
            (bot_self_id, qq_user_id),
        )
        await db.commit()
        return cur.rowcount > 0
