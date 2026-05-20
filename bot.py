"""应用入口：`nb run` 默认加载本文件。

插件在 `src/plugins`，业务包在 `src/bot_core`、`src/services` 等，需先将 `src` 加入
`sys.path`，否则会出现 `No module named 'bot_core'` / `services`。
"""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
_src = _root / "src"
_src_s = str(_src)
if _src_s not in sys.path:
    sys.path.insert(0, _src_s)

try:
    from dotenv import load_dotenv

    load_dotenv(_root / ".env")
except ImportError:
    pass

import nonebot  # noqa: E402
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter  # noqa: E402

nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)
nonebot.load_from_toml("pyproject.toml")

app = nonebot.get_asgi()

if __name__ == "__main__":
    nonebot.run(app="__mp_main__:app")
