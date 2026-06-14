"""金句快剪生成：LLM → punchline 子模式剧本 JSON（含运营配套文案）。

【定位 — 区别于 meme 故事模式】
- meme 故事模式（meme_gen.py）：说书人讲一个有铺垫→反转→补刀的故事，带开场钩子+结尾贴片。
- punchline 金句快剪（本文件）：一句一个金句/梗连续轰炸，无故事结构、无钩子、无 endcard，
  快卡点弹出，对齐参考视频「抽象表情包+金句」风格。复用 meme 渲染管线（mode 仍为 meme，
  加 style:"punchline" 标志，meme_build 内分支）。

python3 -m pipeline.gen "话题" --punchline
"""
import re

from ..core import assets, llm
from .. import config

# 金句快剪音色：以抖音魔性贱萌搞怪音 moxing 为主，可少量穿插 narrator/boy/dongbei 制造起伏
PUNCHLINE_VOICES = ["moxing", "narrator", "boy", "dongbei"]

SYSTEM = """你是一个日产千万播放量的抖音「金句快剪」短视频编剧。

【核心定位 — 一定要搞清楚】
这不是讲故事，是「金句轰炸」：一句一个独立的梗/金句/扎心话，连续抛出，
每句配一个表情包，配音念出，快速硬切。没有铺垫、没有反转结构、没有开场钩子、没有结尾说教。
观众图的就是「一句接一句的爽感和共鸣」，像参考的撩妹油腻情话、毒鸡汤、扎心语录那种。

【主题适配】
主题由用户给定（可为：撩妹/油腻情话、毒鸡汤、扎心语录、搞笑金句、阴阳怪气等）。
所有金句都围绕这个主题，但每句要能单独成立、单独被截图传播。

【金句要求 — 这是命根子】
- 每句短而炸，建议 ≤15 字，朗朗上口、有网感、能让人会心一笑或破防。
- 5~8 句，句与句之间可以递进或并列，但不需要起承转合。
- 最后一句要是全片最强的那句（点睛/升华/反差），让人想转发。
- 口语化，像真人在调侃，不要书面腔、不要正能量说教。

【配音音色】
全程以 moxing（抖音魔性贱萌搞怪音，又尖又快又抽象）为主，制造沙雕鬼畜的喜感；
可在 1~2 句穿插 narrator（魔性解说）或 dongbei（东北段子）制造节奏起伏。
voice 只能用：moxing / narrator / boy / dongbei。

【表情包 — 不用你操心】
画面统一用「抽象/鬼畜扭曲脸」风格（系统自动每句随机分配一张不同的抽象表情），
你只管写好金句即可，meme 字段可省略或随便填，系统会覆盖成抽象风格。

【不要的东西】
- 不要 hook（开场钩子）。
- 不要 endcard（结尾贴片）。
- 不要 bgm（金句快剪靠卡点叮撑节奏，留空）。
- 不要 punch 标记。

输出严格 JSON 数组（不要任何解释），每个元素格式：
{
  "mode": "meme",
  "style": "punchline",
  "title": "内部短标题",
  "cover": {"title": "封面大字≤12字可含emoji", "sub": "副标题≤12字"},
  "shots": [
    {"meme": "love",   "text": "金句一句", "voice": "moxing"},
    {"meme": "smug",   "text": "金句一句", "voice": "moxing"},
    {"meme": "doge",   "text": "金句一句", "voice": "narrator"},
    {"meme": "love",   "text": "金句一句", "voice": "moxing"},
    {"meme": "shock",  "text": "最强收尾金句", "voice": "moxing"}
  ],
  "_post": {
    "title": "发布标题25~35字，含情绪词+钩子",
    "tags": ["#金句", "#表情包", "#撩妹", "#抽象", "#段子", "#每日一笑", "#情话"],
    "caption": "评论区置顶文案40~60字，共鸣+引导评论"
  }
}

可用 meme 情绪: {emotions}
可用 voice（只能用这4个）: moxing / narrator / boy / dongbei
"""

EXAMPLES = """
【风格参考 — 学一句一炸的节奏，不抄内容】

① 撩妹油腻情话型（参考视频同款）
shots:
  doge/moxing        - "朋友"
  smug/moxing        - "衣服是穿给外人看的"
  love/moxing        - "和我在一起的时候"
  doge/narrator    - "下次就不要穿了"
  smug/moxing        - "我又不是外人"
  love/moxing        - "我是你的心上人"

② 毒鸡汤型
shots:
  smug/moxing        - "努力不一定成功"
  doge/narrator    - "但不努力一定很轻松"
  tired/moxing       - "你的同龄人正在抛弃你"
  laugh/boy        - "好在我没有同龄人 我朋友都是大爷"
  speechless/moxing  - "起跑线？我直接躺平在终点"

③ 扎心语录型
shots:
  love/moxing        - "我把最好的脾气给了陌生人"
  cry/narrator     - "把最差的情绪留给了最亲的人"
  tired/moxing       - "成年人的崩溃 都是静音模式"
  doge/boy         - "白天笑嘻嘻 晚上emo到天明"
  smug/moxing        - "没事 反正明天还得继续装"
"""


def _validate(script: dict) -> dict:
    shots = script.get("shots") or []
    shots = shots[:8] if len(shots) > 8 else shots
    if len(shots) < 4:
        raise ValueError(f"shots 不足（{len(shots)}），至少 4 个")

    # 金句快剪统一用「抽象/鬼畜脸」风格池（对齐参考视频），每句随机抽一张不同抽象脸
    has_abstract = "abstract" in set(assets.available_emotions())
    for s in shots:
        s["meme"] = "abstract" if has_abstract else (s.get("meme") or "doge")
        voice = s.get("voice", "moxing")
        if voice not in PUNCHLINE_VOICES:
            voice = "moxing"
        s["voice"] = voice
        # 金句快剪不用 punch / hook，清掉以防误带
        s.pop("punch", None)
        text = (s.get("text") or "").strip()
        if not text:
            raise ValueError(f"shot 缺少 text: {s}")
        if len(text) > 18:
            s["text"] = text[:18]

    script["shots"] = shots
    script["mode"]  = "meme"
    script["style"] = "punchline"
    # 显式抹掉故事模式的元素，确保渲染走快剪分支
    script.pop("hook", None)
    script.pop("endcard", None)
    script.pop("bgm", None)

    script.setdefault("cover", {
        "title": script.get("title", ""),
        "sub":   "看到最后会爱上 😏",
    })
    return script


def generate(topic: str, n: int = 3, model: str = None) -> list[dict]:
    emotions = ", ".join(assets.available_emotions())
    # 用 replace 而非 format，避免 SYSTEM 里的 JSON 示例 {} 被误当占位符
    system   = SYSTEM.replace("{emotions}", emotions) + EXAMPLES
    prompt   = (
        f"请为主题「{topic}」生成 {n} 个金句快剪短视频剧本。"
        f"记住：一句一个独立金句连续轰炸，不是讲故事，无钩子无结尾贴片，voice 只能用 moxing/narrator/boy/dongbei。"
        f"每个剧本 shots 5~8 句，每句 ≤15 字短而炸，最后一句最强，必须附带 _post 运营文案。"
        f"输出 JSON 数组。"
    )

    for attempt in range(2):
        try:
            raw = llm.chat(
                [{"role": "system", "content": system},
                 {"role": "user",   "content": prompt}],
                model=model, temperature=0.95,
            )
            break
        except (ValueError, RuntimeError):
            if attempt == 1:
                raise
    scripts = llm.extract_json(raw)
    if not isinstance(scripts, list):
        raise RuntimeError(f"LLM 未返回 JSON 数组:\n{raw[:500]}")

    results = []
    for s in scripts:
        try:
            results.append(_validate(s))
        except (ValueError, KeyError) as e:
            print(f"  跳过非法剧本：{e}")
    return results
