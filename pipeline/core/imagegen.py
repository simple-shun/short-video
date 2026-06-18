"""AI 生图：按提示词 sha1 缓存，同图不重复花钱。"""
import base64
import hashlib
import mimetypes
import os
from pathlib import Path

import requests

from .. import config

CACHE_DIR = config.ASSETS / "gen_cache"
MODEL = os.environ.get("IMAGE_MODEL", "google/gemini-3.1-flash-image-preview")


def generate_image(prompt: str, out_path=None, timeout=120, ref_images=None) -> Path:
    """生成图片并返回路径；同提示词命中缓存直接返回。

    ref_images: 可选参考图路径列表，喂给多模态生图保持人物/画风一致（图生图）。
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    refs = [Path(p) for p in (ref_images or []) if Path(p).exists()]
    sig = prompt + "".join(hashlib.sha1(p.read_bytes()).hexdigest()[:12] for p in refs)
    key = hashlib.sha1(sig.encode()).hexdigest()[:16]
    cached = CACHE_DIR / f"{key}.png"
    if cached.exists():
        return cached

    content = [{"type": "text", "text": prompt}]
    for p in refs:
        mime = mimetypes.guess_type(str(p))[0] or "image/png"
        b64 = base64.b64encode(p.read_bytes()).decode()
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"}})

    resp = requests.post(
        f"{config.OPENROUTER_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {config.openrouter_key()}"},
        json={"model": MODEL,
              "messages": [{"role": "user", "content": content}],
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
