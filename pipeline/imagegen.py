"""AI 生图（gemini-2.5-flash-image）：按提示词 sha1 缓存，同图不重复花钱。"""
import base64
import hashlib
from pathlib import Path

import requests

from . import config

CACHE_DIR = config.ASSETS / "gen_cache"
MODEL = "google/gemini-2.5-flash-image"


def generate_image(prompt: str, out_path=None, timeout=120) -> Path:
    """生成图片并返回路径；同提示词命中缓存直接返回。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(prompt.encode()).hexdigest()[:16]
    cached = CACHE_DIR / f"{key}.png"
    if cached.exists():
        return cached

    resp = requests.post(
        f"{config.OPENROUTER_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {config.openrouter_key()}"},
        json={"model": MODEL,
              "messages": [{"role": "user", "content": prompt}],
              "modalities": ["image", "text"]},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    imgs = (data.get("choices") or [{}])[0].get("message", {}).get("images") or []
    if not imgs:
        raise RuntimeError(f"生图失败（无图片返回）: {str(data)[:300]}")
    cached.write_bytes(base64.b64decode(imgs[0]["image_url"]["url"].split(",", 1)[1]))
    if out_path:
        Path(out_path).write_bytes(cached.read_bytes())
        return Path(out_path)
    return cached
