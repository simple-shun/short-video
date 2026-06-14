"""表情包串联短视频管线（mode: meme）：
开场钩子插播 → 表情包序列（TTS+节拍音效+运镜）→ 反转高光 → 结尾悬念贴片。
无需 AI 生图/生视频，秒级出片，走 magic.html 渲染器。
"""
import random
from pathlib import Path

from ..core import assets, tts
from .. import config

MEME_HTML = config.ROOT / "renderer" / "magic.html"

# ── 时序参数（毫秒）：故事段子模式 ──
HOOK_DUR     = 2400   # 开场钩子插播时长
HOOK_PAD     = 80     # 钩子→第一帧间隙
SHOT_PAD     = 300    # TTS 念完后的呼吸
DEFAULT_SHOT = 1900   # 无 TTS 镜头默认时长
PUNCH_EXTRA  = 700    # punch 高光帧额外停留
MIN_SHOT     = 1400   # 任何镜头最短时长
END_HOLD     = 1400   # 结尾定格

# ── 时序参数（毫秒）：金句快剪模式（style: punchline，对齐参考视频快卡点）──
PL_SHOT_PAD     = 150   # 念完后极短呼吸
PL_DEFAULT_SHOT = 1100  # 无 TTS 镜头默认时长
PL_MIN_SHOT     = 850   # 最短时长（快切）
PL_END_HOLD     = 500   # 结尾定格

# ── 运镜策略 ──
PUNCH_MOTION  = "punch_in"
OPEN_MOTION   = "spin_in"
CYCLE_MOTIONS = ["drift", "pull_back", "shake", "bounce", "drift", "pull_back", "spin_in"]

# ── 每帧切换节拍音效池（轻量，强化节奏感）──
# 奇数帧用 boing，偶数帧用 whoosh，punch 帧单独用 dun+vine_boom
BEAT_SFXS = ["boing", "whoosh"]

# ── 金句快剪「喜感 BGM 池」：每条随机挑一首（沙雕/魔性/坏笑/唢呐），适合抖音快剪 ──
PUNCHLINE_BGM_TAGS = ["silly", "goofy", "chaos", "upbeat", "scheming", "sneaky", "suona"]


def _to_static(img_path: Path) -> Path:
    """GIF → 提取第一帧静图（magic.html video seek 会卡死）。"""
    if img_path.suffix.lower() != ".gif":
        return img_path
    import hashlib, subprocess
    h = hashlib.sha1(img_path.read_bytes()).hexdigest()[:12]
    out = config.ASSETS / "gen_cache" / f"gif1st_{h}.png"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(img_path), "-frames:v", "1", str(out)],
            capture_output=True, check=True,
        )
    return out


def build(script: dict):
    """返回与 magic.build() 同构的 {payload, audio_events, total_ms, bgm, bgm_tempo, bgm_volume}。"""
    rng      = random.Random(script.get("title", ""))
    shots_in = script.get("shots") or []
    workdir  = config.OUTPUT_DIR / script["_slug"]

    # 金句快剪：节奏快、统一叮卡点、pop 弹出、无钩子无 endcard
    is_punchline = script.get("style") == "punchline"
    min_shot     = PL_MIN_SHOT if is_punchline else MIN_SHOT
    shot_pad     = PL_SHOT_PAD if is_punchline else SHOT_PAD
    default_shot = PL_DEFAULT_SHOT if is_punchline else DEFAULT_SHOT
    end_hold     = PL_END_HOLD if is_punchline else END_HOLD

    # meme 模式只用旁白类音色，屏蔽聊天流水线的 left/right
    MEME_VOICES = {"narrator", "dongbei", "shaanxi", "boy", "liao", "moxing"}

    def _meme_voice(v):
        return v if v in MEME_VOICES else "narrator"

    # ── 1. TTS 批量合成 ──
    hook_cfg  = script.get("hook") or {}
    hook_text = hook_cfg.get("text", "") if isinstance(hook_cfg, dict) else str(hook_cfg)
    if is_punchline:
        hook_text = ""  # 金句快剪无开场钩子
    tts_items = [{"text": s.get("text", ""), "voice": _meme_voice(s.get("voice", "narrator"))}
                 for s in shots_in]
    if hook_text:
        tts_items.append({"text": hook_text, "voice": "narrator"})
    narrs      = tts.synth_texts(tts_items, workdir / "audio", prefix="meme")
    hook_audio = narrs.pop() if hook_text else (None, 0.0)

    audio_events = []
    cutaways     = []
    shots_out    = []

    # ── 2. 开场钩子 cutaway ──
    cursor = 0
    if hook_text:
        hook_dur = HOOK_DUR
        if hook_audio[0]:
            hook_dur = max(hook_dur, int(hook_audio[1] * 1000) + 350)
            audio_events.append({"t": 60, "file": str(hook_audio[0]),
                                 "volume": 1.0, "kind": "voice"})
        audio_events.append({"t": 0, "file": str(assets.resolve_sfx("whoosh")),
                             "volume": 0.85, "max_dur": 2.0, "kind": "fx"})
        cutaways.append({"t": 0, "dur": hook_dur,
                         "image": None, "caption": hook_text, "big": True})
        cursor = hook_dur + HOOK_PAD

    # ── 3. 镜头序列 ──
    for i, s in enumerate(shots_in):
        emotion = s.get("meme") or "doge"
        if emotion not in set(config.EMOTIONS):
            emotion = "doge"

        img_path = assets.resolve_meme(emotion, rng)
        if not img_path:
            print(f"  镜头{i} meme:{emotion} 无图，跳过")
            continue

        t              = cursor
        narr_path, narr_dur = narrs[i]

        # 时长计算
        dur = max(int(s.get("dur", default_shot)), min_shot)
        if s.get("punch"):
            dur += PUNCH_EXTRA
        if narr_path:
            dur = max(dur, int(narr_dur * 1000) + shot_pad)
            audio_events.append({"t": t + 70, "file": str(narr_path),
                                 "volume": 1.0, "kind": "voice",
                                 "voice": _meme_voice(s.get("voice", "narrator"))})

        # ── 音效：每帧切换节拍 + punch 专属双爆 ──
        if s.get("sfx"):
            # 显式指定音效
            audio_events.append({"t": t + 20, "file": str(assets.resolve_sfx(s["sfx"])),
                                 "volume": 0.9, "max_dur": 3.0, "kind": "fx"})
        elif s.get("punch"):
            # punch 帧：vine_boom（重低频冲击）
            audio_events.append({"t": t + 20, "file": str(assets.resolve_sfx("boom")),
                                 "volume": 0.9, "max_dur": 2.0, "kind": "fx"})
            audio_events.append({"t": t + 80, "file": str(assets.resolve_sfx("dun")),
                                 "volume": 0.7, "max_dur": 1.5, "kind": "fx"})
        elif is_punchline:
            # 金句快剪：每帧统一「叮」卡点（对齐参考视频）
            audio_events.append({"t": t + 20, "file": str(assets.resolve_sfx("ding")),
                                 "volume": 0.6, "max_dur": 0.8, "kind": "fx"})
        else:
            # 普通帧：轮换节拍音（boing/whoosh 交替，音量较轻）
            beat = BEAT_SFXS[i % len(BEAT_SFXS)]
            audio_events.append({"t": t + 20, "file": str(assets.resolve_sfx(beat)),
                                 "volume": 0.45, "max_dur": 0.8, "kind": "fx"})

        # ── 运镜 ──
        valid_motions = {"punch_in","pull_back","shake","spin_in","drift",
                         "strobe_zoom","glitch","bounce","pop"}
        if s.get("motion") in valid_motions:
            motion = s["motion"]
        elif s.get("punch"):
            motion = PUNCH_MOTION
        elif is_punchline:
            motion = "pop"   # 弹出+轻微放大后稳定
        elif i == 0:
            motion = OPEN_MOTION
        else:
            motion = CYCLE_MOTIONS[(i - 1) % len(CYCLE_MOTIONS)]

        static_path = _to_static(img_path)
        shots_out.append({
            "t":       t,
            "dur":     dur,
            "image":   static_path.resolve().as_uri(),
            "caption": s.get("text", ""),
            "motion":  motion,
            "punch":   bool(s.get("punch")),
            "sticker": None,
        })
        cursor = t + dur

    if not shots_out:
        raise RuntimeError("没有合法的 meme 镜头")

    total_ms = cursor + end_hold

    # ── 4. 封面 ──
    punch_shot = next((sh for sh in shots_out if sh.get("punch")), shots_out[0])
    punch_img  = punch_shot.get("image") or punch_shot.get("video")
    cov   = script.get("cover") or {}
    cover = {
        "title": cov.get("title") or script.get("title", ""),
        "sub":   cov.get("sub", "看到最后直接石化 😱"),
        "image": punch_img,
    }

    # ── 5. 结尾贴片：支持对象格式 {main, sub, cta}；金句快剪不带 endcard ──
    endcard = None if is_punchline else script.get("endcard", {})

    payload = {
        "endcard":      endcard,
        "total_ms":     total_ms,   # 传给进度条
        "shots":        shots_out,
        "cutaways":     cutaways,
        "cover":        cover,
        "hide_progress": is_punchline,  # 金句快剪隐藏底部进度条
    }

    # BGM：金句快剪默认从「喜感池」随机挑一首（每条不同，title 种子可复现）；脚本显式 bgm 优先
    if is_punchline:
        bgm = assets.resolve_bgm(script["bgm"]) if script.get("bgm") \
            else assets.random_bgm(PUNCHLINE_BGM_TAGS, rng)
    else:
        bgm = assets.resolve_bgm(script.get("bgm"))
    return {
        "payload":      payload,
        "audio_events": audio_events,
        "total_ms":     total_ms,
        "bgm":          str(bgm) if bgm else None,
        "bgm_tempo":    float(script.get("bgm_tempo", 1.15 if is_punchline else 1.28)),
        "bgm_volume":   float(script.get("bgm_volume", 0.40 if is_punchline else 0.40)),
        # 金句快剪配音密集：用轻闪避(ratio≈2)+高音量，保证 BGM 全程清晰可闻又不抢人声
        "bgm_duck_ratio":     2.0 if is_punchline else 5.0,
        "bgm_duck_threshold": 0.06 if is_punchline else 0.03,
        "bgm_duck_release":   300 if is_punchline else 850,
    }
