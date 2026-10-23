# QQBot

## How to start

1. generate project using `nb create` .
2. create your plugin using `nb plugin create` .
3. writing your plugins under `src/plugins` folder.
4. run your bot using `nb run --reload` .

## Apex 地图卡片

地图轮换使用 Playwright 将 HTML/CSS 模板渲染为 PNG。首次安装依赖后，还需要安装 Chromium：

```powershell
python -m playwright install chromium
```

不启动机器人也可以读取 `.env` 中的 API 配置，使用真实地图数据生成卡片：

```powershell
python scripts/preview_apex_map_card.py
```

预览图默认写入 `data/apex-map-preview.png`。渲染失败时机器人会自动回退到原来的文本结果。

## Documentation

See [Docs](https://nonebot.dev/)

待新增：
1. 接入大模型
2. 发送视频
