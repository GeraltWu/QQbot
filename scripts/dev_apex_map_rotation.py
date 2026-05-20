"""本地调试 Apex 接口（地图 / 玩家），不启动 QQ / NoneBot。

在仓库根目录执行::

    pip install -e ".[dev]"   # 或: pip install python-dotenv
    python scripts/dev_apex_map_rotation.py              # 默认：地图轮换
    python scripts/dev_apex_map_rotation.py map
    python scripts/dev_apex_map_rotation.py player 昵称 [PC|PS4|X1]

依赖 .env 中的 APEX_API_KEY（及可选 APEX_API_BASE_URL）。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_src = _root / "src"


def _bootstrap() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        print(
            "需要 python-dotenv：pip install python-dotenv\n"
            "或：pip install -e \".[dev]\"",
            file=sys.stderr,
        )
        sys.exit(1)
    load_dotenv(_root / ".env")
    _src_s = str(_src)
    if _src_s not in sys.path:
        sys.path.insert(0, _src_s)


def main() -> None:
    parser = argparse.ArgumentParser(description="本地调试 Apex API（Mozambique）。")
    parser.add_argument(
        "cmd",
        nargs="?",
        default="map",
        choices=["map", "player"],
        help="map=地图轮换，player=玩家概况（默认 map）",
    )
    parser.add_argument(
        "rest",
        nargs=argparse.REMAINDER,
        help="player 子命令时：昵称与可选平台，例如 SomeName PS4",
    )
    args = parser.parse_args()

    _bootstrap()

    if args.cmd == "map":
        from services.apex_map_service import fetch_map_rotation_text

        async def _run() -> None:
            print(await fetch_map_rotation_text())

        asyncio.run(_run())
        return

    # player
    raw = " ".join(args.rest).strip()
    if not raw:
        parser.error("player 子命令需要参数，例如：player MyName 或 player My Name PS4")

    from services.apex_player_service import fetch_player_bridge_summary

    async def _run_p() -> None:
        print(
            await fetch_player_bridge_summary(
                raw,
                bot_self_id="dev",
                qq_user_id="dev",
            ),
        )

    asyncio.run(_run_p())


if __name__ == "__main__":
    main()
