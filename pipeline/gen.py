"""批量生成段子：python3 -m pipeline.gen "话题" -n 5 [--model xxx] [--make]"""
import argparse

from . import config, script_gen
from .make import make_video


def main():
    ap = argparse.ArgumentParser(description="LLM 批量生成聊天段子 JSON（自动毒舌评分+批次目录）")
    ap.add_argument("topic", help="主题/方向，如：诈骗电话反杀、相亲奇遇、甲方迷惑需求")
    ap.add_argument("-n", type=int, default=3, help="生成数量（默认 3）")
    ap.add_argument("--model", default=None,
                    help=f"OpenRouter 模型 id（默认 {config.DEFAULT_MODEL}）")
    ap.add_argument("--no-judge", action="store_true", help="跳过评分（省一次调用）")
    ap.add_argument("--make", action="store_true", help="生成后直接出片（仅评分≥30的）")
    args = ap.parse_args()

    print(f"▶ 用 {args.model or config.DEFAULT_MODEL} 生成 {args.n} 个段子：{args.topic}")
    scripts = script_gen.generate(args.topic, n=args.n, model=args.model)
    print(f"  通过校验 {len(scripts)} 个")

    # 评分是判别任务，固定用默认便宜模型即可（创作模型由 --model 决定）
    scores = [] if args.no_judge else script_gen.judge(scripts)
    batch_dir, paths = script_gen.save_batch(args.topic, scripts, scores)

    print(f"\n📁 {batch_dir}")
    for p, total in paths:
        print(f"  📝 {p.name}")
    print(f"  📋 挑选指南：{batch_dir / '索引.md'}")

    if args.make:
        for p, total in paths:
            if scores and (total or 0) < 30:
                continue
            make_video(p)


if __name__ == "__main__":
    main()
