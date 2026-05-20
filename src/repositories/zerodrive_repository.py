"""QQ 用户与 ZeroDrive 网盘账号的绑定凭证存储。"""

from __future__ import annotations

import aiosqlite

from bot_core.database import DB_PATH, init_db

ADMIN_KEY = "admin"


async def get_credentials(*, bot_self_id: str, qq_user_id: str) -> dict | None:
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT username, access_token, token_type,
                   default_parent_id, default_path
            FROM zerodrive_credentials
            WHERE bot_self_id = ? AND qq_user_id = ?
            """,
            (bot_self_id, qq_user_id),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return {
        "username": str(row["username"]),
        "access_token": str(row["access_token"]),
        "token_type": str(row["token_type"]),
        "default_parent_id": str(row["default_parent_id"]) if row["default_parent_id"] else None,
        "default_path": str(row["default_path"]) if row["default_path"] else None,
    }


async def upsert_credentials(
    *,
    bot_self_id: str,
    qq_user_id: str,
    username: str,
    access_token: str,
    token_type: str = "bearer",
) -> None:
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO zerodrive_credentials
                (bot_self_id, qq_user_id, username, access_token, token_type)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(bot_self_id, qq_user_id) DO UPDATE SET
                username = excluded.username,
                access_token = excluded.access_token,
                token_type = excluded.token_type
            """,
            (bot_self_id, qq_user_id, username, access_token, token_type),
        )
        await db.commit()


async def update_default_dir(
    *,
    bot_self_id: str,
    qq_user_id: str,
    parent_id: str,
    path: str,
) -> None:
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE zerodrive_credentials
            SET default_parent_id = ?, default_path = ?
            WHERE bot_self_id = ? AND qq_user_id = ?
            """,
            (parent_id, path, bot_self_id, qq_user_id),
        )
        await db.commit()


async def delete_credentials(*, bot_self_id: str, qq_user_id: str) -> bool:
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM zerodrive_credentials WHERE bot_self_id = ? AND qq_user_id = ?",
            (bot_self_id, qq_user_id),
        )
        await db.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# 管理员 token（复用了 zerodrive_credentials 表，bot_self_id / qq_user_id 均为 "admin"）
# ---------------------------------------------------------------------------
async def get_admin_token() -> str | None:
    creds = await get_credentials(bot_self_id=ADMIN_KEY, qq_user_id=ADMIN_KEY)
    return creds["access_token"] if creds else None


async def set_admin_token(*, access_token: str, username: str) -> None:
    await upsert_credentials(
        bot_self_id=ADMIN_KEY,
        qq_user_id=ADMIN_KEY,
        username=username,
        access_token=access_token,
    )
