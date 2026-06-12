"""图生视频适配器：参考图 + 动作提示词 → mp4 底片。

走 OpenRouter 视频生成 API（异步任务），用项目现有 key，无需额外账号。
默认模型 google/veo-3.1-lite（无声 720p $0.03/秒，5 秒镜头约 ¥1.1）。
可用 VIDEO_MODEL 环境变量或脚本字段覆盖，候选：
  alibaba/wan-2.6 ($0.10/s) / kwaivgi/kling-v3.0-std ($0.084/s) /
  minimax/hailuo-2.3 ($0.082/s) / x-ai/grok-imagine-video (480p $0.05/s)
"""
import base64
import hashlib
import mimetypes
import os
import time
from pathlib import Path

import requests

from . import config

CLIPS_DIR = config.ASSETS / "clips"
DEFAULT_MODEL = os.environ.get("VIDEO_MODEL", "google/veo-3.1-lite")

PROVIDERS = {}


def register(name):
    def deco(fn):
        PROVIDERS[name] = fn
        return fn
    return deco


def available() -> bool:
    try:
        config.openrouter_key()
        return True
    except RuntimeError:
        return False


@register("openrouter")
def _openrouter_i2v(image_path: Path, motion_prompt: str, dur_s: int,
                    out_path: Path, model: str = None):
    key = config.openrouter_key()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    mime = mimetypes.guess_type(str(image_path))[0] or "image/png"
    b64 = base64.b64encode(Path(image_path).read_bytes()).decode()

    r = requests.post(
        f"{config.OPENROUTER_BASE}/videos",
        headers=headers,
        json={
            "model": model or DEFAULT_MODEL,
            "prompt": motion_prompt,
            "duration": max(2, min(int(dur_s), 10)),
            "resolution": "720p",
            "aspect_ratio": "9:16",
            "frame_images": [{
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
                "frame_type": "first_frame",
            }],
        },
        timeout=90,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"视频任务创建失败 {r.status_code}: {r.text[:400]}")
    job = r.json()
    poll_url = job.get("polling_url") or f"{config.OPENROUTER_BASE}/videos/{job['id']}"
    print(f"    视频任务 {job.get('id')} 生成中（{model or DEFAULT_MODEL}，通常 1~3 分钟）...")

    deadline = time.time() + 720
    while time.time() < deadline:
        time.sleep(12)
        q = requests.get(poll_url, headers=headers, timeout=30)
        q.raise_for_status()
        st = q.json()
        status = st.get("status")
        if status == "completed":
            urls = st.get("unsigned_urls") or []
            if not urls:
                raise RuntimeError(f"任务完成但无视频地址: {str(st)[:300]}")
            data = requests.get(urls[0], headers=headers, timeout=300).content
            out_path.write_bytes(data)
            cost = (st.get("usage") or {}).get("cost")
            if cost:
                print(f"    完成，本镜头成本 ${cost}")
            return out_path
        if status in ("failed", "canceled", "error"):
            raise RuntimeError(f"视频任务失败: {str(st)[:400]}")
    raise TimeoutError("视频任务超时（12 分钟）")


def generate_clip(image_path, motion_prompt: str, dur_s: int = 5,
                  provider: str = "openrouter", model: str = None) -> Path:
    """参考图 → 动态视频片段；按（图+提示词+时长+模型）哈希缓存，命中不花钱。"""
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1(
        Path(image_path).read_bytes() + motion_prompt.encode()
        + str(dur_s).encode() + (model or DEFAULT_MODEL).encode()
    ).hexdigest()[:16]
    cached = CLIPS_DIR / f"{h}.mp4"
    if cached.exists():
        return cached
    return PROVIDERS[provider](Path(image_path), motion_prompt, dur_s, cached, model=model)
