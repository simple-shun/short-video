"""媒体小工具：ffprobe 时长、内置音效合成（纯标准库，无 numpy 依赖）。"""
import math
import struct
import subprocess
import wave
from pathlib import Path

from . import config

BUILTIN_DIR = config.SFX_DIR / "builtin"


def trim_silence(src, dst, head_keep=0.04, tail_keep=0.10):
    """裁掉音频首尾静音（edge-tts 每条自带 ~0.6s 静音，拖节奏）。"""
    af = (
        f"silenceremove=start_periods=1:start_threshold=-45dB:start_silence={head_keep},"
        f"areverse,"
        f"silenceremove=start_periods=1:start_threshold=-45dB:start_silence={tail_keep},"
        f"areverse"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", af, str(dst)],
        check=True, capture_output=True,
    )


def probe_duration(path) -> float:
    """音/视频时长（秒）。"""
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def _write_wav(path: Path, samples, sr=44100):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples
        )
        w.writeframes(frames)


def _tone_burst(notes, duration, sr=44100):
    """notes: [(freq, offset_s, vol, decay)] 指数衰减正弦叠加（钟声质感）。"""
    n = int(sr * duration)
    data = [0.0] * n
    for freq, offset, vol, decay in notes:
        start = int(offset * sr)
        for i in range(start, n):
            t = (i - start) / sr
            data[i] += math.sin(2 * math.pi * freq * t) * vol * math.exp(-decay * t)
    return data


def ensure_builtin_sfx():
    """生成兜底音效（与下载素材互补，保证管线在零下载时也能出片）。"""
    specs = {
        # 微信收信"叮咚"：C6 + E6 双脉冲（移植自原 HTML 的 WebAudio 合成）
        "wechat_ding.wav": lambda: _tone_burst(
            [(1047, 0.0, 0.5, 18), (1319, 0.085, 0.42, 20)], 0.45),
        # 发送"噗"：短促低频
        "send_pop.wav": lambda: _tone_burst([(520, 0.0, 0.45, 30)], 0.18),
        # 重音"咚"：低频大衰减
        "dun.wav": lambda: _tone_burst(
            [(82, 0.0, 0.9, 6), (164, 0.0, 0.3, 10), (55, 0.02, 0.5, 5)], 1.0),
        # 叮（强调）
        "ding.wav": lambda: _tone_burst([(1568, 0.0, 0.6, 8)], 0.8),
    }
    out = {}
    for name, gen in specs.items():
        p = BUILTIN_DIR / name
        if not p.exists():
            _write_wav(p, gen())
        out[name.split(".")[0]] = p
    return out
