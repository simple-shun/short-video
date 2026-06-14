"""批量生成脚本：python3 -m pipeline.gen "话题" -n 5 [--meme|--punchline|--magic] [--make]

注册表驱动：按 CLI flag 在 registry.GENERATORS 里查生成器；评分/落盘走 core.batch。
"""
import argparse

from . import config, registry
from .core import batch
from .make import make_video


def main():
    ap = argparse.ArgumentParser(description="LLM 批量生成短视频脚本 JSON（注册表驱动）")
    ap.add_argument("topic", help="主题/方向，如：诈骗电话反杀、相亲奇遇")
    ap.add_argument("-n", type=int, default=3, help="生成数量（默认 3）")
    ap.add_argument("--model", default=None,
                    help=f"OpenRouter 模型 id（默认 {config.DEFAULT_MODEL}）")
    ap.add_argument("--no-judge", action="store_true", help="跳过评分（省一次调用）")
    ap.add_argument("--meme", action="store_true", help="表情包段子（说书人讲故事）")
    ap.add_argument("--punchline", action="store_true", help="金句快剪（一句一炸）")
    ap.add_argument("--magic", action="store_true", help="魔性短片分镜（AI 生图运镜）")
    ap.add_argument("--make", action="store_true", help="生成后直接出片（评分线仅 ≥30）")
    args = ap.parse_args()

    flag = ("punchline" if args.punchline else "meme" if args.meme
            else "magic" if args.magic else "chat")
    gen = registry.GENERATORS[flag]

    print(f"▶ 用 {args.model or config.DEFAULT_MODEL} 生成 {args.n} 个{gen['label']}：{args.topic}")
    scripts = gen["fn"](args.topic, n=args.n, model=args.model)
    print(f"  通过校验 {len(scripts)} 个")
    if not scripts:
        return

    # 评分是判别任务，固定用默认便宜模型；仅 judge=True 的线评分
    scores = [] if (args.no_judge or not gen["judge"]) else batch.judge(scripts)
    batch_dir, paths = batch.save_batch(args.topic, scripts, scores)

    print(f"\n📁 {batch_dir}")
    for p, total in paths:
        print(f"  📝 {p.name}")
    print(f"  📋 挑选指南：{batch_dir / '索引.md'}")

    if args.make:
        for p, total in paths:
            if gen["judge"] and scores and (total or 0) < 30:
                continue
            make_video(p)


if __name__ == "__main__":
    main()
