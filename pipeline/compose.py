"""ffmpeg 合成：配音/音效混音 → BGM 自动闪避 → 帧序列封装 MP4 + 封面。"""
import json
import re
import subprocess

from . import config


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 失败:\n{' '.join(cmd)}\n{r.stderr[-2000:]}")
    return r


def build_voice_track(audio_events, total_ms, out_wav):
    """把所有配音/音效按时间点摆到一条轨上。"""
    total_s = total_ms / 1000
    if not audio_events:
        _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
              "-t", f"{total_s:.3f}", str(out_wav)])
        return
    cmd = ["ffmpeg", "-y"]
    filters = []
    for k, ev in enumerate(audio_events):
        cmd += ["-i", ev["file"]]
        d = int(ev["t"])
        trim = ""
        if ev.get("max_dur"):
            md = ev["max_dur"]
            trim = f"atrim=0:{md},afade=t=out:st={md - 0.6}:d=0.6,"
        filters.append(
            f"[{k}]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"{trim}volume={ev.get('volume', 1.0)},adelay={d}|{d}[a{k}]"
        )
    mix_in = "".join(f"[a{k}]" for k in range(len(audio_events)))
    filters.append(
        f"{mix_in}amix=inputs={len(audio_events)}:normalize=0:dropout_transition=0,"
        f"alimiter=limit=0.95,apad[aout]"
    )
    cmd += ["-filter_complex", ";".join(filters),
            "-map", "[aout]", "-t", f"{total_s:.3f}", str(out_wav)]
    _run(cmd)


def _loudnorm_two_pass(in_wav, out_wav, total_s):
    """两遍式响度归一：先测量再线性增益，避免动态模式抬升安静段/与闪避对抗。"""
    target = "I=-14:TP=-1.2:LRA=11"
    r = _run(["ffmpeg", "-y", "-i", str(in_wav),
              "-af", f"loudnorm={target}:print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if m:
        stats = json.loads(m.group(0))
        af = (f"loudnorm={target}:measured_I={stats['input_i']}"
              f":measured_TP={stats['input_tp']}:measured_LRA={stats['input_lra']}"
              f":measured_thresh={stats['input_thresh']}"
              f":offset={stats['target_offset']}:linear=true")
    else:  # 测量解析失败兜底：退回单遍
        af = f"loudnorm={target}"
    _run(["ffmpeg", "-y", "-i", str(in_wav), "-af", af,
          "-ar", "48000", "-t", f"{total_s:.3f}", str(out_wav)])


def build_master_track(voice_wav, fx_wav, bgm_path, total_ms, out_wav,
                       bgm_volume=0.16, bgm_tempo=1.0):
    """BGM 循环铺底 + 旁链闪避（仅配音触发，提示音/音效不触发）+ 两遍响度归一。"""
    total_s = total_ms / 1000
    pre = out_wav.with_suffix(".pre.wav")
    if not bgm_path:
        fc = "[0][1]amix=inputs=2:normalize=0:dropout_transition=0[out]"
        _run(["ffmpeg", "-y", "-i", str(voice_wav), "-i", str(fx_wav),
              "-filter_complex", fc, "-map", "[out]",
              "-t", f"{total_s:.3f}", str(pre)])
    else:
        tempo = f"atempo={bgm_tempo}," if bgm_tempo and bgm_tempo != 1.0 else ""
        # ratio 5 / release 850ms：消息间隙 BGM 缓慢回升，避免一抽一抽的泵感
        fc = (
            f"[2]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"{tempo}volume={bgm_volume}[bgm];"
            f"[bgm][0]sidechaincompress=threshold=0.03:ratio=5:attack=20:release=850[duck];"
            f"[0][duck][1]amix=inputs=3:normalize=0:dropout_transition=0[out]"
        )
        _run(["ffmpeg", "-y",
              "-i", str(voice_wav), "-i", str(fx_wav),
              "-stream_loop", "-1", "-i", str(bgm_path),
              "-filter_complex", fc, "-map", "[out]",
              "-t", f"{total_s:.3f}", str(pre)])
    _loudnorm_two_pass(pre, out_wav, total_s)
    pre.unlink(missing_ok=True)


def mux_video(frames_dir, master_wav, out_mp4):
    _run(["ffmpeg", "-y",
          "-framerate", str(config.FPS), "-i", str(frames_dir / "%05d.png"),
          "-i", str(master_wav),
          # PNG 是 RGB：显式走 BT.709 矩阵并打 tag，否则播放器按 709 解读 601 数据导致偏色
          "-vf", "scale=out_color_matrix=bt709:out_range=tv",
          "-colorspace", "bt709", "-color_primaries", "bt709",
          "-color_trc", "bt709", "-color_range", "tv",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
          "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
          "-pix_fmt", "yuv420p", "-movflags", "+faststart",
          "-c:a", "aac", "-b:a", "192k", "-shortest", str(out_mp4)])


def make_cover(frames_dir, frame_index, out_jpg):
    src = frames_dir / f"{frame_index:05d}.png"
    if src.exists():
        _run(["ffmpeg", "-y", "-i", str(src), "-q:v", "2", str(out_jpg)])
