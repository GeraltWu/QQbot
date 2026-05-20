"""统一的 SQLite 数据库入口。所有仓库模块共用同一个数据库文件。"""

from __future__ import annotations

from pathlib import Path

import aiosqlite

DB_PATH = Path("data") / "bot.sqlite3"


async def init_db() -> None:
    """建所有表（幂等），各仓库模块启动时调用。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        # 提醒
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_self_id TEXT NOT NULL,
                target_kind TEXT NOT NULL,
                target_id TEXT NOT NULL,
                creator_id TEXT NOT NULL,
                hour INTEGER NOT NULL,
                minute INTEGER NOT NULL,
                body TEXT NOT NULL,
                schedule_kind TEXT NOT NULL DEFAULT 'daily',
                once_date TEXT
            );
            """,
        )

        # Apex 绑定
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS apex_player_links (
                bot_self_id TEXT NOT NULL,
                qq_user_id TEXT NOT NULL,
                player_name TEXT NOT NULL,
                platform TEXT NOT NULL,
                PRIMARY KEY (bot_self_id, qq_user_id)
            );
            """,
        )

        # ZeroDrive 绑定（含管理员：bot_self_id="admin", qq_user_id="admin"）
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS zerodrive_credentials (
                bot_self_id TEXT NOT NULL,
                qq_user_id TEXT NOT NULL,
                username TEXT NOT NULL,
                access_token TEXT NOT NULL,
                token_type TEXT NOT NULL DEFAULT 'bearer',
                default_parent_id TEXT,
                default_path TEXT,
                PRIMARY KEY (bot_self_id, qq_user_id)
            );
            """,
        )

        await db.commit()
