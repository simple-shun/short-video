"""一键出片：python3 -m pipeline.make scripts/xxx.json [--keep-frames]

注册表驱动：按 script["mode"] 在 registry.BUILDERS 里查构建器与渲染器，
渲染 → 混音 → 封装的流程对所有生产线统一。
"""
import argparse
import json
import shutil
import time
from pathlib import Path

from . import config, registry
from .core import batch, compose, render


def make_video(script_path, keep_frames=False):
    t0 = time.time()
    script = json.loads(Path(script_path).read_text())
    slug = batch.slugify(script.get("title", Path(script_path).stem))
    script["_slug"] = slug
    workdir = config.OUTPUT_DIR / slug
    frames_dir = workdir / "frames"
    workdir.mkdir(parents=True, exist_ok=True)

    mode = script.get("mode") or "chat"
    builder = registry.BUILDERS.get(mode)
    if not builder:
        raise ValueError(f"未知 mode={mode!r}，已注册：{list(registry.BUILDERS)}")

    print(f"▶ [{slug}] 1-2/5 构建时间轴 (mode={mode})")
    tl = builder["fn"](script)
    print(f"  {len(tl['payload'].get('shots', tl['payload'].get('messages', [])))} 个镜头，"
          f"总时长 {tl['total_ms'] / 1000:.1f}s，"
          f"BGM: {Path(tl['bgm']).name if tl['bgm'] else '无'}")

    print(f"▶ [{slug}] 3/5 逐帧渲染 (playwright)")
    cover_path = workdir / "cover.jpg"
    render.render_frames(tl["payload"], tl["total_ms"], frames_dir,
                         cover_path=cover_path, renderer_html=builder["renderer"])

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
                               bgm_tempo=tl.get("bgm_tempo", 1.0),
                               duck_ratio=tl.get("bgm_duck_ratio", 5.0),
                               duck_threshold=tl.get("bgm_duck_threshold", 0.03),
                               duck_release=tl.get("bgm_duck_release", 850))

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
    ap = argparse.ArgumentParser(description="脚本 JSON → 短视频 MP4")
    ap.add_argument("script", nargs="+", help="脚本 JSON 路径（可多个）")
    ap.add_argument("--keep-frames", action="store_true", help="保留帧序列便于调试")
    args = ap.parse_args()
    for s in args.script:
        make_video(s, keep_frames=args.keep_frames)


if __name__ == "__main__":
    main()
