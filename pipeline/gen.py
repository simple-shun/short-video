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
    ap.add_argument("--magic", action="store_true", help="生成魔性短片分镜（5~20s 全屏运镜模式）")
    ap.add_argument("--meme", action="store_true", help="生成表情包串联短视频（10~20s，零成本出片）")
    ap.add_argument("--punchline", action="store_true", help="生成金句快剪短视频（一句一炸，~7-12s，零成本出片）")
    ap.add_argument("--make", action="store_true", help="生成后直接出片（仅评分≥30的）")
    args = ap.parse_args()

    if args.meme or args.punchline:
        if args.punchline:
            from . import punchline_gen as gen_mod
            kind = "金句快剪"
        else:
            from . import meme_gen as gen_mod
            kind = "表情包段子"
        print(f"▶ 用 {args.model or config.DEFAULT_MODEL} 生成 {args.n} 个{kind}：{args.topic}")
        scripts = gen_mod.generate(args.topic, n=args.n, model=args.model)
        print(f"  通过校验 {len(scripts)} 个")
        _, paths = script_gen.save_batch(args.topic, scripts, [])
        print(f"\n📁 {paths[0][0].parent if paths else '无输出'}")
        for p, _ in paths:
            print(f"  📝 {p.name}")
        if args.make:
            for p, _ in paths:
                make_video(p)
        return

    kind = "魔性短片分镜" if args.magic else "段子"
    print(f"▶ 用 {args.model or config.DEFAULT_MODEL} 生成 {args.n} 个{kind}：{args.topic}")
    if args.magic:
        scripts = script_gen.generate_magic(args.topic, n=args.n, model=args.model)
    else:
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
