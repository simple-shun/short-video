"""时间轴编排：由配音时长驱动消息节奏，产出渲染 payload 和音频事件表。"""
import random

from ..core import assets, media, tts
from .. import config


def build(script: dict):
    """自包含构建（统一 BUILDERS 的 build(script) 接口）：
    开场预处理 → 逐条 TTS → 编排时间轴。等价于原 make.py 里 chat 的三步。"""
    preprocess(script)
    audio_dir = config.OUTPUT_DIR / script["_slug"] / "audio"
    tts_results = tts.synth_script(script, audio_dir)
    return assemble(script, tts_results)


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
                "dur": (intro.get("dur") if isinstance(intro, dict) else None) or 2100,
                "big": True,
            }
            script["messages"] = [cut] + script["messages"]
        script["_intro_done"] = True
    return script


def assemble(script: dict, tts_results, seed: str = ""):
    """
    script: 段子 JSON；tts_results: [(audio_path|None, duration_s)] 与消息对应。
    返回 {payload, audio_events, total_ms, bgm}
    """
    rng = random.Random(seed or script.get("title", ""))
    builtin = media.ensure_builtin_sfx()

    # 脚本级节奏覆盖（控制总时长用）；默认值已调紧以压到 30s 内
    pad_after_audio = int(script.get("pad_after_audio", 230))
    image_dwell = int(script.get("image_dwell", 1250))
    end_hold = int(script.get("end_hold", 1500))

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
        typing_ms = 650 if msg.get("typing") else 0
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

    # 封面：聊天截图模式——手机停在反转气泡做主视觉，大字压顶+红条压底。
    # 比纯文字大字报点击率高（观众一眼看到"那句话"）。
    cov = script.get("cover") or {}
    punch_t = next((m["t"] for m in payload_msgs if m.get("punch")), None)
    if punch_t is None and payload_msgs:
        punch_t = payload_msgs[-1]["t"]            # 没标 punch 用最后一条
    cover = {
        "mode": "chat",
        "seekMs": (punch_t + 700) if punch_t is not None else 0,  # 反转气泡滑入后定格
        "title": cov.get("title") or script.get("hook") or script.get("title", ""),
        "sub": cov.get("sub", "看到最后一句我直接笑喷"),
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
