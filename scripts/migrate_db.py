"""一次性数据迁移：将旧的独立 sqlite3 文件合并到统一的 data/bot.sqlite3。

用法：
    python scripts/migrate_db.py

迁移完成后可手动删除旧文件：
    data/reminders.sqlite3
    data/apex_links.sqlite3
    data/zerodrive.sqlite3
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
NEW_DB = DATA / "bot.sqlite3"

OLD_FILES = {
    "reminders": DATA / "reminders.sqlite3",
    "apex_links": DATA / "apex_links.sqlite3",
    "zerodrive": DATA / "zerodrive.sqlite3",
}


def _table_exists(db: sqlite3.Connection, name: str) -> bool:
    cur = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    )
    return cur.fetchone() is not None


def migrate_reminders(src: Path, dst: sqlite3.Connection) -> int:
    src_db = sqlite3.connect(str(src))
    src_db.row_factory = sqlite3.Row
    if not _table_exists(src_db, "reminders"):
        src_db.close()
        return 0

    # 自动检测列
    cols_cur = src_db.execute("PRAGMA table_info(reminders)")
    cols = [r[1] for r in cols_cur.fetchall()]
    col_str = ", ".join(cols)
    placeholders = ", ".join("?" for _ in cols)

    rows = src_db.execute(f"SELECT {col_str} FROM reminders").fetchall()
    for row in rows:
        dst.execute(
            f"INSERT OR IGNORE INTO reminders ({col_str}) VALUES ({placeholders})",
            tuple(row[c] for c in cols),
        )
    dst.commit()
    src_db.close()
    return len(rows)


def migrate_apex_links(src: Path, dst: sqlite3.Connection) -> int:
    src_db = sqlite3.connect(str(src))
    src_db.row_factory = sqlite3.Row
    if not _table_exists(src_db, "apex_player_links"):
        src_db.close()
        return 0

    rows = src_db.execute(
        "SELECT bot_self_id, qq_user_id, player_name, platform FROM apex_player_links"
    ).fetchall()
    for row in rows:
        dst.execute(
            "INSERT OR IGNORE INTO apex_player_links (bot_self_id, qq_user_id, player_name, platform) "
            "VALUES (?, ?, ?, ?)",
            (row["bot_self_id"], row["qq_user_id"], row["player_name"], row["platform"]),
        )
    dst.commit()
    src_db.close()
    return len(rows)


def migrate_zerodrive(src: Path, dst: sqlite3.Connection) -> int:
    src_db = sqlite3.connect(str(src))
    src_db.row_factory = sqlite3.Row
    count = 0

    # zerodrive_credentials
    if _table_exists(src_db, "zerodrive_credentials"):
        rows = src_db.execute(
            "SELECT bot_self_id, qq_user_id, username, access_token, token_type, "
            "default_parent_id, default_path FROM zerodrive_credentials"
        ).fetchall()
        for row in rows:
            dst.execute(
                "INSERT OR IGNORE INTO zerodrive_credentials "
                "(bot_self_id, qq_user_id, username, access_token, token_type, "
                "default_parent_id, default_path) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    row["bot_self_id"], row["qq_user_id"], row["username"],
                    row["access_token"], row["token_type"] or "bearer",
                    row["default_parent_id"], row["default_path"],
                ),
            )
        count += len(rows)

    # zerodrive_admin_token → 合并到 zerodrive_credentials
    if _table_exists(src_db, "zerodrive_admin_token"):
        row = src_db.execute(
            "SELECT access_token, username FROM zerodrive_admin_token WHERE id = 1"
        ).fetchone()
        if row:
            dst.execute(
                "INSERT OR REPLACE INTO zerodrive_credentials "
                "(bot_self_id, qq_user_id, username, access_token, token_type) "
                "VALUES ('admin', 'admin', ?, ?, 'bearer')",
                (row["username"], row["access_token"]),
            )
            count += 1

    dst.commit()
    src_db.close()
    return count


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)

    dst = sqlite3.connect(str(NEW_DB))

    # 先建表
    dst.executescript(
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

        CREATE TABLE IF NOT EXISTS apex_player_links (
            bot_self_id TEXT NOT NULL,
            qq_user_id TEXT NOT NULL,
            player_name TEXT NOT NULL,
            platform TEXT NOT NULL,
            PRIMARY KEY (bot_self_id, qq_user_id)
        );

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
        """
    )

    total = 0
    for label, old_path in OLD_FILES.items():
        if not old_path.is_file():
            print(f"  [{label}] 旧文件不存在，跳过")
            continue
        if label == "reminders":
            n = migrate_reminders(old_path, dst)
        elif label == "apex_links":
            n = migrate_apex_links(old_path, dst)
        else:
            n = migrate_zerodrive(old_path, dst)
        print(f"  [{label}] 迁移 {n} 条记录")
        total += n

    dst.close()
    print(f"\n迁移完成，共 {total} 条记录 → {NEW_DB}")
    print("请验证后手动删除旧 sqlite3 文件。")
    print(f"  del {DATA / 'reminders.sqlite3'}")
    print(f"  del {DATA / 'apex_links.sqlite3'}")
    print(f"  del {DATA / 'zerodrive.sqlite3'}")


if __name__ == "__main__":
    main()
