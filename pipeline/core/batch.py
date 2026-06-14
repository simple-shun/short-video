"""生成阶段的共享工具：标题转 slug、毒舌评分、批次落盘+索引。
与具体生产线无关，被各 *_gen 生成器与 CLI 复用。"""
import json
import re
from datetime import datetime

from . import llm
from .. import config


def slugify(title: str) -> str:
    s = re.sub(r"[^\w一-鿿]+", "_", title).strip("_")
    return s[:40] or "untitled"


JUDGE_SYSTEM = """你是最毒舌的抖音爆款评委，见过上万条百万赞段子，对平庸零容忍。
对每个本子按 4 维打分（各 10 分，总分 40）：
- 反转力度：是信息差炸弹还是温吞吐槽？低级反转(巧合/误会)直接 ≤3 分
- 笑点密度：逐条数，超过 2 条"白开水消息"就扣到 6 分以下
- 癫狂度：台词像正常人客服对话的 ≤4 分；像精神状态美丽的网友才给高分
- 节奏：铺垫拖沓、结尾没留钩都扣分
另外指出每个本子"最该删/改的一条消息"。30 分以下的本子在 verdict 里写"毙"。
返回严格 JSON 数组：[{"index":0,"total":32,"comment":"一句话毒评","fix":"最该改哪条","verdict":"过|毙"}]"""


def judge(scripts, model=None):
    """毒舌评分。失败时返回空列表（不阻塞保存）。"""
    brief = []
    for i, s in enumerate(scripts):
        lines = []
        if s.get("shots"):  # 魔性短片分镜
            for sh in s["shots"]:
                lines.append(f"镜[{sh.get('motion', '')}] 画面:{str(sh.get('image', ''))[:40]} "
                             f"字:{sh.get('caption', '')} 旁白:{sh.get('narration', '')}")
        else:
            for m in s["messages"]:
                t = m.get("text") or f"[{m.get('meme', '图')}]"
                mark = "(punch)" if m.get("punch") else ""
                lines.append(f"{m.get('side', '?')[0]}:{t}{mark}")
        brief.append(f"【{i}】{s['title']} | hook:{s.get('hook', s.get('cover', {}).get('title', ''))}\n"
                     + "\n".join(lines))
    try:
        raw = llm.chat(
            [{"role": "system", "content": JUDGE_SYSTEM},
             {"role": "user", "content": "\n\n".join(brief)}],
            model=model, temperature=0.3,
        )
        data = llm.extract_json(raw)
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"  评分失败(不影响保存): {e}")
        return []


def save_batch(topic, scripts, scores=None):
    """每批一个子目录：scripts/<月日_时分>_<主题>/，按评分降序命名 + 生成索引。"""
    batch_dir = config.SCRIPTS_DIR / f"{datetime.now():%m%d_%H%M}_{slugify(topic)[:16]}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    by_idx = {s.get("index"): s for s in (scores or []) if isinstance(s, dict)}
    order = sorted(range(len(scripts)),
                   key=lambda i: -(by_idx.get(i, {}).get("total") or 0))

    paths, index_lines = [], [f"# {topic}", ""]
    for rank, i in enumerate(order, 1):
        s = scripts[i]
        sc = by_idx.get(i, {})
        total = sc.get("total")
        tag = f"{total}分" if total is not None else "未评分"
        p = batch_dir / f"{rank:02d}_{tag}_{slugify(s['title'])[:20]}.json"
        p.write_text(json.dumps(s, ensure_ascii=False, indent=2))
        paths.append((p, total))
        hook = s.get("hook") or (s.get("intro") or {}).get("text") or (s.get("cover") or {}).get("title", "-")
        index_lines += [
            f"## {rank:02d}. [{tag}] {s['title']}  {'❌毙' if sc.get('verdict') == '毙' else ''}",
            f"- 钩子：{hook}",
            f"- 毒评：{sc.get('comment', '-')}",
            f"- 建议改：{sc.get('fix', '-')}",
            f"- 出片：`python3 -m pipeline.make \"{p}\"`",
            "",
        ]
    (batch_dir / "索引.md").write_text("\n".join(index_lines))
    return batch_dir, paths
