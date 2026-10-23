"""使用真实 Apex API 数据生成地图轮换卡片，便于调整 HTML/CSS 模板。"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from services.apex_map_card import close_map_card_renderer
from services.apex_map_service import fetch_map_rotation_card


class ApexPreviewError(RuntimeError):
    """真实接口或图片渲染失败。"""


async def _render() -> bytes:
    try:
        result = await fetch_map_rotation_card()
        if isinstance(result, str):
            raise ApexPreviewError(result)
        return result
    finally:
        await close_map_card_renderer()


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="使用真实 API 生成 Apex 地图卡片")
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=ROOT / "data" / "apex-map-preview.png",
    )
    args = parser.parse_args()
    image = asyncio.run(_render())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image)
    print(args.output.resolve())  # noqa: T201
