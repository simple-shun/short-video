"""Playwright 逐帧渲染：虚拟时钟 seek + 截图，永不掉帧。"""
import json
import math

from playwright.sync_api import sync_playwright

from . import config


def render_frames(payload: dict, total_ms: int, frames_dir, cover_path=None):
    frames_dir.mkdir(parents=True, exist_ok=True)
    n_frames = math.ceil(total_ms / 1000 * config.FPS)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": config.VIEW_W, "height": config.VIEW_H},
            device_scale_factor=config.SCALE,
        )
        page.goto(config.RENDERER_HTML.resolve().as_uri())
        info = page.evaluate(f"window.SV.load({json.dumps(payload, ensure_ascii=False)})")
        if not info.get("ok"):
            raise RuntimeError(f"渲染器 load 失败: {info}")

        for f in range(n_frames):
            t = f * 1000 / config.FPS
            page.evaluate(f"window.SV.seek({t})")
            page.screenshot(path=str(frames_dir / f"{f:05d}.png"))
            if f % 150 == 0:
                print(f"  渲染帧 {f}/{n_frames}")

        # 封面：复用同一页面单独排版截一张
        if cover_path and payload.get("cover"):
            page.evaluate(f"window.SV.showCover({json.dumps(payload['cover'], ensure_ascii=False)})")
            page.screenshot(path=str(cover_path), type="jpeg", quality=92)
            print(f"  封面已渲染：{cover_path}")
        browser.close()
    print(f"  渲染完成：{n_frames} 帧 @{config.FPS}fps")
    return n_frames
