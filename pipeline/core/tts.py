"""逐条消息 TTS（edge-tts），返回每条的音频文件与时长。"""
import asyncio
import re
from pathlib import Path

import edge_tts

from .. import config
from . import media

# 去掉 emoji 等 TTS 念不出的字符
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF⭐❗️]+"
)


# 含汉字/字母/数字才可发音；纯标点（"？？？"）会让 edge-tts 抛 NoAudioReceived
_PRONOUNCEABLE_RE = re.compile(r"[一-鿿a-zA-Z0-9]")


def tts_text(text: str) -> str:
    t = _EMOJI_RE.sub("", text or "")
    t = t.replace("...", "").replace("……", "").replace("…", "")
    t = t.strip()
    if not _PRONOUNCEABLE_RE.search(t):
        return ""
    return t


def _voice_for(script: dict, msg: dict) -> dict:
    """消息音色：消息级 voice 覆盖 > 角色配置 > 全局默认；插播旁白默认魔性解说音。"""
    if msg.get("cutaway"):
        base = dict(config.VOICES["narrator"])
        role = {}
    else:
        side = msg.get("side", "left")
        base = dict(config.VOICES.get(side, config.VOICES["left"]))
        role = script.get(side) or {}
    side = msg.get("side", "left")
    for k in ("voice", "rate", "pitch"):
        if role.get(k):
            base[k] = role[k]
        if msg.get(k):
            base[k] = msg[k]
    # 预置音色别名：voice 可以写 "dongbei"/"narrator" 等（rate/pitch 也跟随别名，除非显式覆盖）
    if base["voice"] in config.VOICES:
        alias = config.VOICES[base["voice"]]
        explicit = {k: v for k, v in base.items() if msg.get(k) or (script.get(side) or {}).get(k)}
        base = {**alias, **{k: v for k, v in explicit.items() if k != "voice"}}
    return base


async def _synth_one(text, voice_cfg, out_path):
    comm = edge_tts.Communicate(
        text, voice_cfg["voice"], rate=voice_cfg["rate"], pitch=voice_cfg["pitch"]
    )
    await comm.save(str(out_path))


async def _synth_all_async(script, audio_dir):
    audio_dir.mkdir(parents=True, exist_ok=True)
    results = []
    sem = asyncio.Semaphore(4)

    async def work(i, msg):
        if msg.get("no_tts"):
            return i, None
        if msg.get("cutaway"):
            text = tts_text(msg.get("caption", ""))   # 插播旁白
        elif msg.get("image") or msg.get("meme"):
            return i, None
        else:
            text = tts_text(msg.get("text", ""))
        if not text:
            return i, None
        raw = audio_dir / f"msg_{i:03d}.raw.mp3"
        out = audio_dir / f"msg_{i:03d}.wav"
        async with sem:
            for attempt in range(3):
                try:
                    await _synth_one(text, _voice_for(script, msg), raw)
                    break
                except edge_tts.exceptions.NoAudioReceived:
                    return i, None  # 永久性失败（如不可发音文本）：降级为无配音
                except Exception:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(1.5 * (attempt + 1))
        media.trim_silence(raw, out)  # 去掉 edge-tts 自带的首尾静音，节奏更紧
        raw.unlink(missing_ok=True)
        return i, out

    tasks = [work(i, m) for i, m in enumerate(script["messages"])]
    for coro in asyncio.as_completed(tasks):
        i, path = await coro
        results.append((i, path))
    results.sort()
    return [p for _, p in results]


def synth_texts(items, audio_dir, prefix="nar"):
    """通用逐条合成（魔性短片旁白等用）。
    items: [{"text", "voice"?, "rate"?, "pitch"?}]，voice 可为别名/edge 音色 id，默认 narrator。
    返回 [(path|None, duration_s)] 与 items 一一对应。
    """
    audio_dir = Path(audio_dir)

    async def go():
        audio_dir.mkdir(parents=True, exist_ok=True)
        sem = asyncio.Semaphore(4)

        async def work(i, it):
            text = tts_text(it.get("text", ""))
            if not text:
                return i, None
            v = it.get("voice") or "narrator"
            cfg = dict(config.VOICES.get(v) or {**config.VOICES["narrator"], "voice": v})
            for k in ("rate", "pitch"):
                if it.get(k):
                    cfg[k] = it[k]
            raw = audio_dir / f"{prefix}_{i:03d}.raw.mp3"
            out = audio_dir / f"{prefix}_{i:03d}.wav"
            async with sem:
                for attempt in range(3):
                    try:
                        await _synth_one(text, cfg, raw)
                        break
                    except edge_tts.exceptions.NoAudioReceived:
                        return i, None
                    except Exception:
                        if attempt == 2:
                            raise
                        await asyncio.sleep(1.5 * (attempt + 1))
            media.trim_silence(raw, out)
            raw.unlink(missing_ok=True)
            return i, out

        res = await asyncio.gather(*[work(i, it) for i, it in enumerate(items)])
        return sorted(res)

    paths = asyncio.run(go())
    return [(p, media.probe_duration(p)) if p else (None, 0.0) for _, p in paths]


def synth_script(script: dict, audio_dir):
    """对脚本里每条消息合成配音。返回 [(path|None, duration_s)]，与消息一一对应。"""
    paths = asyncio.run(_synth_all_async(script, audio_dir))
    out = []
    for p in paths:
        if p is None:
            out.append((None, 0.0))
        else:
            out.append((p, media.probe_duration(p)))
    return out
