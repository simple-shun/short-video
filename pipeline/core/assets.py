"""素材解析：按 tag/情绪 从 assets/ 选音效、BGM、表情包。"""
import json
import random
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


def resolve_meme(emotion: str, rng: random.Random):
    """从 assets/memes/<emotion>/ 随机选一张；目录为空返回 None。"""
    d = config.MEME_DIR / emotion
    if not d.is_dir():
        return None
    candidates = [p for p in sorted(d.iterdir()) if p.suffix.lower() in IMAGE_EXT]
    return rng.choice(candidates) if candidates else None


def available_emotions():
    """实际有图的情绪目录列表（给 LLM 提示词用）。"""
    out = []
    for e in config.EMOTIONS:
        d = config.MEME_DIR / e
        if d.is_dir() and any(p.suffix.lower() in IMAGE_EXT for p in d.iterdir()):
            out.append(e)
    return out
