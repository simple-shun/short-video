"""魔性短片管线（mode: magic）：分镜 → 生图/图生视频 → 运镜渲染 → 混音成片。"""
import hashlib
import random
from pathlib import Path

from ..core import assets, imagegen, media, tts, videogen
from .. import config

MAGIC_HTML = config.ROOT / "renderer" / "magic.html"
MOTIONS = ["punch_in", "pull_back", "shake", "spin_in", "drift", "strobe_zoom", "glitch"]

PRE_ROLL = 400
SHOT_PAD = 450        # 旁白念完后的呼吸
DEFAULT_SHOT = 2000   # 无旁白镜头默认时长


def _resolve_image(val: str, rng: random.Random):
    """gen:提示词 / meme:情绪 / 相对路径 → 本地图片 Path（解析失败返回 None）。"""
    if not val:
        return None
    if val.startswith("gen:"):
        prompt = val[4:].strip()
        full = (f"竖版9:16构图，抖音魔性沙雕风格插画，色彩高饱和，表情夸张离谱：{prompt}。"
                f"画面里不要任何文字。")
        try:
            return imagegen.generate_image(full)
        except Exception as e:
            print(f"  生图失败({e})，该镜头改用梗图兜底")
            return assets.resolve_meme("shock", rng)
    if val.startswith("meme:"):
        return assets.resolve_meme(val[5:], rng)
    p = config.ROOT / val
    return p if p.exists() else None


def _resolve_media(s: dict, rng: random.Random):
    """镜头底片 → ("video"|"image", Path)；解析失败返回 None。
    优先级：显式 video > 动图 GIF 转码 > animate 图生视频 > 静图。"""
    if s.get("video"):
        p = config.ROOT / s["video"]
        return ("video", p) if p.exists() else None
    img = _resolve_image(s.get("image", ""), rng)
    if not img:
        return None
    if img.suffix.lower() == ".gif":
        mp4 = videogen.CLIPS_DIR / f"gif_{hashlib.sha1(img.read_bytes()).hexdigest()[:12]}.mp4"
        if not mp4.exists():
            media.gif_to_mp4(img, mp4)
        return ("video", mp4)
    if s.get("animate"):
        prompt = (s.get("motion_prompt") or s.get("narration") or s.get("caption")
                  or "镜头缓慢推进，主体做夸张魔性的动作")
        try:
            clip = videogen.generate_clip(img, prompt, max(2, round(s.get("dur", 5000) / 1000)),
                                          model=s.get("video_model"))
            return ("video", clip)
        except Exception as e:
            print(f"  图生视频不可用（{e}），该镜头退回静图运镜")
    return ("image", img)


def build(script: dict):
    """返回 {payload, audio_events, total_ms, bgm, bgm_tempo}（与聊天线 timeline.build 同构）。"""
    rng = random.Random(script.get("title", ""))
    shots_in = script.get("shots") or []

    # ── 旁白 TTS（intro 也走 narrator）──
    workdir = config.OUTPUT_DIR / script["_slug"]
    items = [{"text": s.get("narration", ""), "voice": s.get("voice"),
              "rate": s.get("rate"), "pitch": s.get("pitch")} for s in shots_in]
    intro = script.get("intro") or {}
    intro_text = intro.get("text", "") if isinstance(intro, dict) else str(intro)
    if intro_text:
        items.append({"text": intro_text})
    narrs = tts.synth_texts(items, workdir / "audio")
    intro_audio = narrs.pop() if intro_text else (None, 0.0)

    audio_events = []
    cutaways = []
    cursor = PRE_ROLL

    # ── intro 开场白（黑屏大字插播）──
    if intro_text:
        dur = 2400
        if intro_audio[0]:
            dur = max(dur, int(intro_audio[1] * 1000) + 450)
            audio_events.append({"t": cursor + 120, "file": str(intro_audio[0]),
                                 "volume": 1.0, "kind": "voice"})
        audio_events.append({"t": cursor, "file": str(assets.resolve_sfx(intro.get("sfx", "whoosh"))),
                             "volume": 0.8, "max_dur": 4.0, "kind": "fx"})
        cutaways.append({"t": cursor, "dur": dur, "image": None,
                         "caption": intro_text, "big": True})
        cursor += dur + 120

    # ── 镜头序列 ──
    shots_out = []
    for i, s in enumerate(shots_in):
        m = _resolve_media(s, rng)
        if not m:
            print(f"  镜头{i} 无可用底片，跳过")
            continue
        kind, mpath = m
        t = cursor
        narr_path, narr_dur = narrs[i]
        dur = int(s.get("dur", DEFAULT_SHOT))
        if narr_path:
            dur = max(dur, int(narr_dur * 1000) + SHOT_PAD)
            audio_events.append({"t": t + 120, "file": str(narr_path),
                                 "volume": 1.0, "kind": "voice"})
        if s.get("sfx"):
            audio_events.append({"t": t + 50, "file": str(assets.resolve_sfx(s["sfx"])),
                                 "volume": 0.85, "max_dur": 4.0, "kind": "fx"})
        sticker = None
        if s.get("sticker"):
            sp = _resolve_image(s["sticker"], rng)
            sticker = sp.resolve().as_uri() if sp else None
        shot = {
            "t": t, "dur": dur,
            "motion": s.get("motion") if s.get("motion") in MOTIONS else "punch_in",
            "caption": s.get("caption", ""),
            "sticker": sticker,
        }
        shot["video" if kind == "video" else "image"] = mpath.resolve().as_uri()
        shots_out.append(shot)
        cursor = t + dur

    total_ms = cursor + 600

    # ── 封面 ──
    cov = script.get("cover") or {}
    cov_img = None
    val = cov.get("image", "")
    if val:
        cov_img_p = _resolve_image(val if ":" in val or "/" in val else f"meme:{val}", rng)
        cov_img = cov_img_p.resolve().as_uri() if cov_img_p else None
    if not cov_img:
        # 封面只能用静图：取第一个图片镜头
        cov_img = next((sh["image"] for sh in shots_out if sh.get("image")), None)
    cover = {
        "title": cov.get("title") or script.get("hook") or script.get("title", ""),
        "sub": cov.get("sub", "看到最后绷不住了"),
        "image": cov_img,
    }

    payload = {
        "endcard": script.get("endcard", "关注我，下集更癫 🤪"),
        "shots": shots_out,
        "cutaways": cutaways,
        "cover": cover,
    }
    bgm = assets.resolve_bgm(script.get("bgm"))
    return {
        "payload": payload,
        "audio_events": audio_events,
        "total_ms": total_ms,
        "bgm": str(bgm) if bgm else None,
        "bgm_tempo": float(script.get("bgm_tempo", 1.25)),
        # 短片旁白稀疏，BGM 底量比聊天线更高才有能量感
        "bgm_volume": float(script.get("bgm_volume", 0.26)),
    }
