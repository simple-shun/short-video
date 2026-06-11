"""时间轴编排：由配音时长驱动消息节奏，产出渲染 payload 和音频事件表。"""
import random

from . import assets, config, media


def preprocess(script: dict) -> dict:
    """把 intro 开场白转成首条全屏插播（注意看式悬念开场，必须在 TTS 之前调用）。"""
    intro = script.get("intro")
    if intro and not script.get("_intro_done"):
        text = intro.get("text", "") if isinstance(intro, dict) else str(intro)
        if text:
            cut = {
                # 无图时也要保持 cutaway 为真值，否则会漏进聊天流变成空气泡
                "cutaway": (intro.get("image") if isinstance(intro, dict) else None) or "none",
                "caption": text,
                "sfx": (intro.get("sfx") if isinstance(intro, dict) else None) or "whoosh",
                "dur": (intro.get("dur") if isinstance(intro, dict) else None) or 2600,
                "big": True,
            }
            script["messages"] = [cut] + script["messages"]
        script["_intro_done"] = True
    return script


def build(script: dict, tts_results, seed: str = ""):
    """
    script: 段子 JSON；tts_results: [(audio_path|None, duration_s)] 与消息对应。
    返回 {payload, audio_events, total_ms, bgm}
    """
    rng = random.Random(seed or script.get("title", ""))
    builtin = media.ensure_builtin_sfx()

    # 脚本级节奏覆盖（控制总时长用）
    pad_after_audio = int(script.get("pad_after_audio", config.PAD_AFTER_AUDIO))
    image_dwell = int(script.get("image_dwell", config.IMAGE_DWELL))
    end_hold = int(script.get("end_hold", config.END_HOLD))

    payload_msgs = []
    cutaways = []      # 全屏插播 {t, dur, image, caption}
    audio_events = []  # {t, file, volume}
    cursor = config.PRE_ROLL

    for i, msg in enumerate(script["messages"]):
        # ── 全屏插播：占独立时间槽，不进聊天流 ──
        if msg.get("cutaway"):
            val = msg["cutaway"]
            p = None
            if val in config.EMOTIONS:
                p = assets.resolve_meme(val, rng)
            else:
                cand = config.ROOT / val
                p = cand if cand.exists() else None
            audio_path, audio_dur = tts_results[i]
            if not p and not audio_path:
                continue  # 图和旁白都没有就整条跳过
            t = cursor
            dur = int(msg.get("dur", 1700))
            if audio_path:
                dur = max(dur, int(audio_dur * 1000) + 450)
                audio_events.append({"t": t + 150, "file": str(audio_path),
                                     "volume": 1.0, "kind": "voice"})
            if msg.get("sfx"):
                audio_events.append({"t": t + 80, "file": str(assets.resolve_sfx(msg["sfx"])),
                                     "volume": 0.85, "max_dur": 4.0, "kind": "fx"})
            cutaways.append({
                "t": t, "dur": dur,
                "image": p.resolve().as_uri() if p else None,
                "caption": msg.get("caption", ""),
                "big": bool(msg.get("big")),
            })
            cursor = t + dur + 120
            continue

        side = msg.get("side", "left")
        typing_ms = 900 if msg.get("typing") else 0
        cursor += typing_ms
        t = cursor

        # 表情包消息：meme:<情绪> 或显式 image 路径
        image_uri = None
        if msg.get("meme"):
            p = assets.resolve_meme(msg["meme"], rng)
            if p:
                image_uri = p.resolve().as_uri()
        elif msg.get("image"):
            p = config.ROOT / msg["image"]
            if p.exists():
                image_uri = p.resolve().as_uri()
        # 纯图消息但素材库没图：整条跳过，不渲染空气泡
        if (msg.get("meme") or msg.get("image")) and not image_uri and not msg.get("text"):
            cursor = t - typing_ms  # 回退 typing 占位
            continue

        audio_path, audio_dur = tts_results[i]

        pm = {
            "side": side,
            "t": t,
            "typing_ms": typing_ms,
            "punch": bool(msg.get("punch")),
        }
        if image_uri:
            pm["image"] = image_uri
        else:
            pm["text"] = msg.get("text", "")
        payload_msgs.append(pm)

        # 消息提示音：收到=叮咚，发出=噗（fx 轨：不触发 BGM 闪避）
        ding = builtin["wechat_ding"] if side == "left" else builtin["send_pop"]
        audio_events.append({"t": t, "file": str(ding), "volume": 0.4, "kind": "fx"})

        # 配音（voice 轨：作为 BGM 闪避的旁链信号）
        if audio_path:
            audio_events.append({"t": t, "file": str(audio_path),
                                 "volume": 1.0, "kind": "voice"})

        # 额外音效（限长 4s 防止长素材如唢呐盖住后续配音）
        if msg.get("sfx"):
            sfx_path = assets.resolve_sfx(msg["sfx"])
            audio_events.append({"t": t + 120, "file": str(sfx_path),
                                 "volume": 0.85, "max_dur": 4.0, "kind": "fx"})

        # 本条停留时长
        if audio_path:
            dwell = int(audio_dur * 1000) + pad_after_audio
        elif image_uri:
            dwell = image_dwell
        else:
            dwell = config.SILENT_DWELL
        if msg.get("punch"):
            dwell += config.PUNCH_EXTRA
        dwell += int(msg.get("pause", 0))
        cursor = t + dwell

    total_ms = cursor + end_hold

    def _role(side, default):
        role = dict(script.get(side) or default)
        # 头像支持图片：相对路径转 file:// 绝对 URI
        av = role.get("avatar", "")
        if av and not av.startswith(("file:", "http")) and "." in av:
            p = config.ROOT / av
            if p.exists():
                role["avatar"] = p.resolve().as_uri()
        return role

    # 封面数据：title/sub/image（image 可填情绪 tag 或路径，缺省用 right 头像图）
    cov = script.get("cover") or {}
    cov_img = None
    val = cov.get("image", "")
    if val in config.EMOTIONS:
        cov_img = assets.resolve_meme(val, rng)
    elif val and (config.ROOT / val).exists():
        cov_img = config.ROOT / val
    else:
        rav = (script.get("right") or {}).get("avatar", "")
        if rav and (config.ROOT / rav).exists():
            cov_img = config.ROOT / rav
    cover = {
        "title": cov.get("title") or script.get("hook") or script.get("title", ""),
        "sub": cov.get("sub", "看到最后一句我跪了"),
        "image": cov_img.resolve().as_uri() if cov_img else None,
    }

    payload = {
        "hook": script.get("hook") or script.get("title", ""),
        "chatTitle": script.get("chat_title", "聊天"),
        "endcard": script.get("endcard", "关注我，下集更炸 🔥"),
        "timeLabel": script.get("time_label", "晚上 9:41"),
        "left": _role("left", {"avatar": "🐱", "bg": "#ffb347"}),
        "right": _role("right", {"avatar": "🐼", "bg": "#74b9ff"}),
        "messages": payload_msgs,
        "cutaways": cutaways,
        "cover": cover,
    }

    bgm = assets.resolve_bgm(script.get("bgm"))
    return {
        "payload": payload,
        "audio_events": audio_events,
        "total_ms": total_ms,
        "bgm": str(bgm) if bgm else None,
        "bgm_tempo": float(script.get("bgm_tempo", 1.0)),  # >1 加速更魔性
    }
