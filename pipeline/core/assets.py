"""素材解析：按 tag/情绪 从 assets/ 选音效、BGM、表情包。"""
import hashlib
import json
import random
import subprocess
from pathlib import Path

from .. import config
from . import media

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _load_manifest(d: Path):
    f = d / "manifest.json"
    if f.exists():
        try:
            data = json.loads(f.read_text())
            # 手工编辑可能写坏形态：只接受 [{"file": ...}, ...]
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict) and "file" in x]
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _manifest_path(base_dir: Path, file: str):
    """manifest 里的 file 可能相对 manifest 目录、项目根或为绝对路径。"""
    p = Path(file)
    if p.is_absolute():
        return p if p.exists() else None
    for cand in (base_dir / file, config.ROOT / file):
        if cand.exists():
            return cand
    return None


def resolve_sfx(tag: str):
    """按 tag 找音效：依次查 sfx 和 voicelines 的 manifest，其次文件名匹配，最后内置兜底。"""
    for d in (config.SFX_DIR, config.SFX_DIR / "voicelines"):
        for item in _load_manifest(d):
            if item.get("tag") == tag:
                p = _manifest_path(d, item["file"])
                if p:
                    return p
    if config.SFX_DIR.exists():
        for p in sorted(config.SFX_DIR.rglob("*")):
            if p.suffix.lower() in AUDIO_EXT and tag in p.stem:
                return p
    builtin = media.ensure_builtin_sfx()
    if tag in builtin:
        return builtin[tag]
    # 找不到该 tag：用"叮"兜底，绝不让管线断掉
    return builtin["ding"]


def resolve_bgm(tag: str = None):
    """按 tag 选 BGM；没有 tag 或没匹配就随便选一首；一首都没有返回 None。"""
    manifest = _load_manifest(config.BGM_DIR)
    if tag:
        for item in manifest:
            if item.get("tag") != tag:
                continue
            p = _manifest_path(config.BGM_DIR, item["file"])
            if p:
                return p
    candidates = [p for p in sorted(config.BGM_DIR.glob("*"))
                  if p.suffix.lower() in AUDIO_EXT] if config.BGM_DIR.exists() else []
    return candidates[0] if candidates else None


def random_bgm(tags, rng: random.Random):
    """从给定 tag 集合里随机挑一首 BGM（用于喜感快剪每条随机配乐）；无匹配返回 None。"""
    manifest = _load_manifest(config.BGM_DIR)
    pool = []
    tagset = set(tags)
    for item in manifest:
        if item.get("tag") in tagset:
            p = _manifest_path(config.BGM_DIR, item["file"])
            if p:
                pool.append(p)
    return rng.choice(sorted(pool)) if pool else None


WATERMARK_CROP = 0.12  # 去水印缓解：四边各裁掉的比例（QQ/微博水印可能内嵌较深）


def _clean_meme(p: Path):
    """去水印缓解：中心裁掉四边各 WATERMARK_CROP，按内容哈希+裁幅缓存。

    GIF 跳过（保动画，meme_build 会取首帧）；裁剪失败回退原图，绝不让管线断掉。
    """
    if p.suffix.lower() == ".gif" or WATERMARK_CROP <= 0:
        return p
    h = hashlib.sha1(p.read_bytes()).hexdigest()[:12]
    out = config.ASSETS / "gen_cache" / f"crop{int(WATERMARK_CROP * 100)}_{h}{p.suffix}"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        keep = 1 - 2 * WATERMARK_CROP
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", str(p),
             "-vf", f"crop=floor(iw*{keep}/2)*2:floor(ih*{keep}/2)*2",
             str(out)], capture_output=True)
        if r.returncode != 0 or not out.exists():
            return p
    return out


def resolve_meme(emotion: str, rng: random.Random):
    """从 assets/memes/<emotion>/ 随机选一张（已做去水印裁剪）；目录为空返回 None。"""
    d = config.MEME_DIR / emotion
    if not d.is_dir():
        return None
    candidates = [p for p in sorted(d.iterdir()) if p.suffix.lower() in IMAGE_EXT]
    return _clean_meme(rng.choice(candidates)) if candidates else None


def available_emotions():
    """实际有图的情绪目录列表（给 LLM 提示词用）。"""
    out = []
    for e in config.EMOTIONS:
        d = config.MEME_DIR / e
        if d.is_dir() and any(p.suffix.lower() in IMAGE_EXT for p in d.iterdir()):
            out.append(e)
    return out
