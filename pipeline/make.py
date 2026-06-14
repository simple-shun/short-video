"""一键出片：python3 -m pipeline.make scripts/xxx.json（聊天/魔性短片双模式）"""
import argparse
import json
import shutil
import time
from pathlib import Path

from . import compose, config, magic, render, script_gen, timeline, tts


def make_video(script_path, keep_frames=False):
    t0 = time.time()
    script = json.loads(Path(script_path).read_text())
    slug = script_gen.slugify(script.get("title", Path(script_path).stem))
    script["_slug"] = slug
    workdir = config.OUTPUT_DIR / slug
    frames_dir = workdir / "frames"
    audio_dir = workdir / "audio"
    workdir.mkdir(parents=True, exist_ok=True)

    mode = script.get("mode")
    is_magic = mode == "magic"
    is_meme = mode == "meme"
    renderer_html = magic.MAGIC_HTML if (is_magic or is_meme) else None

    if is_meme:
        from . import meme_build
        print(f"▶ [{slug}] 1-2/5 TTS 配音+时间轴 (meme)")
        tl = meme_build.build(script)
        print(f"  {len(tl['payload']['shots'])} 个表情包镜头，总时长 {tl['total_ms'] / 1000:.1f}s，"
              f"BGM: {Path(tl['bgm']).name if tl['bgm'] else '无'}")
    elif is_magic:
        print(f"▶ [{slug}] 1-2/5 分镜解析+生图+旁白 (magic)")
        tl = magic.build(script)
        print(f"  {len(tl['payload']['shots'])} 个镜头，总时长 {tl['total_ms'] / 1000:.1f}s，"
              f"BGM: {Path(tl['bgm']).name if tl['bgm'] else '无'}")
    else:
        print(f"▶ [{slug}] 1/5 逐条配音 (edge-tts)")
        timeline.preprocess(script)  # intro 开场白 → 首条插播
        tts_results = tts.synth_script(script, audio_dir)
        voiced = sum(1 for p, _ in tts_results if p)
        print(f"  {voiced}/{len(tts_results)} 条消息有配音")

        print(f"▶ [{slug}] 2/5 编排时间轴")
        tl = timeline.build(script, tts_results)
        print(f"  总时长 {tl['total_ms'] / 1000:.1f}s，BGM: {Path(tl['bgm']).name if tl['bgm'] else '无'}")

    print(f"▶ [{slug}] 3/5 逐帧渲染 (playwright)")
    cover_path = workdir / "cover.jpg"
    render.render_frames(tl["payload"], tl["total_ms"], frames_dir,
                         cover_path=cover_path, renderer_html=renderer_html)

    print(f"▶ [{slug}] 4/5 混音 (配音+音效+BGM闪避)")
    voice_wav = workdir / "voice.wav"
    fx_wav = workdir / "fx.wav"
    master_wav = workdir / "master.wav"
    events = tl["audio_events"]
    compose.build_voice_track([e for e in events if e.get("kind") == "voice"],
                              tl["total_ms"], voice_wav)
    compose.build_voice_track([e for e in events if e.get("kind") != "voice"],
                              tl["total_ms"], fx_wav)
    compose.build_master_track(voice_wav, fx_wav, tl["bgm"], tl["total_ms"], master_wav,
                               bgm_volume=tl.get("bgm_volume", 0.16),
                               bgm_tempo=tl.get("bgm_tempo", 1.0))

    print(f"▶ [{slug}] 5/5 封装 MP4")
    out_mp4 = workdir / f"{slug}.mp4"
    compose.mux_video(frames_dir, master_wav, out_mp4)
    # 封面渲染失败时兜底：取反转(punch)时刻的帧
    if not cover_path.exists():
        punch_t = next((m["t"] for m in tl["payload"].get("messages", []) if m.get("punch")),
                       tl["total_ms"] * 0.4)
        punch_frame = min(int(punch_t / 1000 * config.FPS) + 8,
                          int(tl["total_ms"] / 1000 * config.FPS) - 1)
        compose.make_cover(frames_dir, punch_frame, cover_path)

    if not keep_frames:
        shutil.rmtree(frames_dir, ignore_errors=True)
        voice_wav.unlink(missing_ok=True)
        fx_wav.unlink(missing_ok=True)

    print(f"✅ 完成 {out_mp4}  (耗时 {time.time() - t0:.0f}s)")
    return out_mp4


def main():
    ap = argparse.ArgumentParser(description="聊天段子 JSON → 短视频 MP4")
    ap.add_argument("script", nargs="+", help="段子 JSON 路径（可多个）")
    ap.add_argument("--keep-frames", action="store_true", help="保留帧序列便于调试")
    args = ap.parse_args()
    for s in args.script:
        make_video(s, keep_frames=args.keep_frames)


if __name__ == "__main__":
    main()
