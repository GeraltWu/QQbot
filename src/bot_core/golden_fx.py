"""SSR 出金 GIF 动画：高密度金色星芒粒子在画面表面闪烁。

不触发则返回原图 bytes，触发则返回 GIF bytes。
通过 SSR_RATE 环境变量控制概率，默认 0.05。
"""

from __future__ import annotations

import io
import math
import os
import random

from PIL import Image, ImageDraw

_RATE = float(os.environ.get("SSR_RATE", "0.05"))  # 触发概率，0~1
_MAX_DIM = 400          # 图片最长边超过此值则等比缩小
_FRAMES = 8             # GIF 总帧数
_FRAME_MS = 100          # 每帧毫秒
_PARTICLE_RATIO = 0.1  # 粒子数 = 图片总像素 × 此比例
_TINT_ALPHA = 0        # 金色罩层透明度，0~255


def maybe_add_ssr_effect(img_bytes: bytes) -> bytes:
    if random.random() > _RATE:
        return img_bytes
    return _make_ssr_gif(img_bytes)


def _make_ssr_gif(img_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    w, h = img.size

    # 透明图垫白底
    bg = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    bg.alpha_composite(img)
    img = bg

    if max(w, h) > _MAX_DIM:
        scale = _MAX_DIM / max(w, h)
        w, h = int(w * scale), int(h * scale)
        img = img.resize((w, h), Image.LANCZOS)

    particles = _gen_particles(img, w, h)

    frames: list[Image.Image] = []
    for fi in range(_FRAMES):
        t = fi / (_FRAMES - 1)

        frame = img.copy()
        _apply_tint(frame, w, h, _TINT_ALPHA)
        _apply_particles(frame, w, h, t, particles)

        frames.append(frame.convert("RGB"))

    return _save_gif(frames, [_FRAME_MS] * _FRAMES)


# ---------------------------------------------------------------------------
# 粒子生成
# ---------------------------------------------------------------------------
def _gen_particles(
    img: Image.Image, w: int, h: int,
) -> list[tuple[int, int, int, float, float, int, int, int]]:
    """返回 [(x, y, size, phase, freq, r, g, b), ...]。
    采样原图对应位置的像素颜色，作为粒子闪烁的基色。
    """
    result = []
    scale = max(w, h) / _MAX_DIM
    base_sizes = [int(s * scale) for s in (2, 3, 4, 5)]
    count = int(w * h * _PARTICLE_RATIO)
    px = img.load()
    for _ in range(count):
        x = random.randint(0, w - 1)
        y = random.randint(0, h - 1)
        size = random.choices(base_sizes, weights=[25, 40, 25, 10])[0]
        phase = random.random() * math.pi * 2
        freq = random.uniform(1.8, 5.0)
        r, g, b = px[x, y][:3]
        result.append((x, y, size, phase, freq, r, g, b))
    return result


# ---------------------------------------------------------------------------
# 单帧：金色底膜
# ---------------------------------------------------------------------------
def _apply_tint(frame: Image.Image, w: int, h: int, alpha: int) -> None:
    overlay = Image.new("RGBA", (w, h), (255, 215, 0, alpha))
    frame.alpha_composite(overlay)


# ---------------------------------------------------------------------------
# 单帧：粒子层
# ---------------------------------------------------------------------------
def _apply_particles(
    frame: Image.Image,
    w: int,
    h: int,
    t: float,
    particles: list[tuple[int, int, int, float, float, int, int, int]],
) -> None:
    pl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pl)

    for x, y, size, phase, freq, br, bg, bb in particles:
        angle = t * math.pi * 2 * freq + phase
        raw = math.sin(angle)
        if raw <= 0.1:
            continue
        alpha = int(255 * raw)
        if raw > 0.98:
            # 峰顶纯白星芒（仅顶部 1%）
            color = (255, 255, 250, alpha)
            _draw_star(pd, x, y, size, color)
        elif raw > 0.15:
            # 中段：基色高饱和 + 提亮，圆形
            avg = (br + bg + bb) / 3
            sat = 4
            boost = 40
            r = min(255, int(avg + (br - avg) * sat + boost))
            g = min(255, int(avg + (bg - avg) * sat + boost))
            b = min(255, int(avg + (bb - avg) * sat + boost))
            color = (r, g, b, alpha)
            _draw_dot(pd, x, y, size, color)
        else:
            # 低位：基色中饱和 + 微提亮，圆形
            avg = (br + bg + bb) / 3
            sat = 2.5
            boost = 20
            r = min(255, int(avg + (br - avg) * sat + boost))
            g = min(255, int(avg + (bg - avg) * sat + boost))
            b = min(255, int(avg + (bb - avg) * sat + boost))
            color = (r, g, b, alpha)
            _draw_dot(pd, x, y, size, color)

    frame.alpha_composite(pl)


# ---------------------------------------------------------------------------
# 圆形光点
# ---------------------------------------------------------------------------
def _draw_dot(
    draw: ImageDraw.Draw,
    cx: int,
    cy: int,
    size: int,
    color: tuple[int, int, int, int],
) -> None:
    r = max(1, size // 3)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)


# ---------------------------------------------------------------------------
# 四角星
# ---------------------------------------------------------------------------
def _draw_star(
    draw: ImageDraw.Draw,
    cx: int,
    cy: int,
    size: int,
    color: tuple[int, int, int, int],
) -> None:
    s = size
    hs = max(1, s // 3)
    points = [
        (cx, cy - s),
        (cx + hs, cy - hs),
        (cx + s, cy),
        (cx + hs, cy + hs),
        (cx, cy + s),
        (cx - hs, cy + hs),
        (cx - s, cy),
        (cx - hs, cy - hs),
    ]
    draw.polygon(points, fill=color)


# ---------------------------------------------------------------------------
# GIF 输出
# ---------------------------------------------------------------------------
def _save_gif(frames: list[Image.Image], durations: list[int]) -> bytes:
    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        disposal=2,
        optimize=True,
    )
    buf.seek(0)
    return buf.read()
