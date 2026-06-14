"""表情包段子生成：LLM → meme 模式剧本 JSON（含运营配套文案）。

【三流水线定位】
- chat  模式：两人微信聊天对话，有 left/right 角色，气泡界面
- meme  模式：单旁白讲故事，全程一个说书人视角，配表情包，本文件
- magic 模式：AI 生图+图生视频，分镜导演视角

python3 -m pipeline.gen "话题" --meme
"""
import json
import re

from ..core import assets, llm
from .. import config

# meme 模式专用音色：都是"旁白/说书人"性质，无"角色扮演"概念
# narrator = 魔性解说（主力）
# dongbei  = 东北腔旁白（段子感强）
# shaanxi  = 陕西腔旁白（土味喜感）
# boy      = 贱萌旁白（适合自嘲）
MEME_VOICES = ["narrator", "dongbei", "shaanxi", "boy"]

SYSTEM = """你是一个日产千万播放量的抖音表情包段子视频编剧。

【核心定位 — 一定要搞清楚】
这不是"两个人聊天"的视频，是"一个说书人用表情包讲故事"的脱口秀。
全程只有一个叙述者视角，像讲相声、说段子，观众跟着旁白的节奏走。
表情包配合情绪出现，不代表"不同角色在说话"。

【视频结构公式（15~25秒）】
开场钩子（前2秒黑屏大字）→ 铺垫蓄势（2~3句）→ 渲染加深（2~3句）→ 一句反转炸场 → 补刀收尾（1~2句）

【开场钩子 — 前2秒决定生死】
hook.text ≤ 20字，旁白念出，不含emoji，必须是以下之一：
① 好奇缺口："注意看，他研究了三年如何让人喜欢自己"
② 戳痛点预告："有一种朋友，专门在你最难的时候消失"
③ 反常识悬念："我发现了一条定律，越努力越单身"
④ 直接剧透反转结果，让人想看原因："他准备了半年的告白，对方问他是哪位"

【旁白风格】
全程一个声音在讲故事，可以用不同语气：
- narrator：正经魔性解说，铺垫渲染用
- dongbei：东北话段子感，自嘲收尾用（"这不整完了嘛"）
- boy：贱萌调侃，反转后的无奈用
- shaanxi：陕西土味感，补刀用
每句指定一个 voice，整体要有节奏起伏，不能全程一个音色。
【绝对禁止用 left/right】这是聊天流水线的概念，meme 里用会让人觉得是两人对话。

【表情包情绪必须和台词语义一致】
- love：正在讲一段深情/美好的时刻
- smug：一本正经自以为是
- shock：被震到了、信息量炸裂
- confused：懵了、没反应过来
- surprised：瞠目结舌
- doge：被整蒙了、一脸无辜（反转用）
- angry：真的崩溃了
- laugh：苦笑、哈哈但不是真笑
- speechless：无语到说不出话
- tired：彻底摆了、躺平
- cry：真的很惨
- no：干脆拒绝、不行
- scheme：坏笑、在算计什么
- money：跟钱有关的欢喜

【结尾贴片三行（吸引关注关键）】
endcard 必须是对象格式，三行各有职责：
- main：引导互动，"评论区扣1""你们猜他后来怎样"
- sub：情感共鸣句，让人想截图
- cta：悬念/下集预告，"关注我，明天出续集"

输出严格 JSON 数组（不要任何解释），格式：
{
  "mode": "meme",
  "title": "内部短标题",
  "hook": {"text": "开场旁白≤20字不含emoji"},
  "cover": {"title": "封面大字≤12字可含emoji", "sub": "副标题≤12字"},
  "bgm": "scheming",
  "bgm_tempo": 1.28,
  "bgm_volume": 0.40,
  "endcard": {
    "main": "评论区扣1 👇",
    "sub": "你也有过这种经历吗",
    "cta": "关注我，明天出续集 🔥"
  },
  "shots": [
    {"meme": "love",       "text": "铺垫第一句",     "voice": "narrator", "motion": "spin_in"},
    {"meme": "smug",       "text": "铺垫第二句",     "voice": "narrator"},
    {"meme": "shock",      "text": "渲染加深",       "voice": "narrator", "sfx": "wow"},
    {"meme": "love",       "text": "渲染推高",       "voice": "narrator"},
    {"meme": "confused",   "text": "加最后一把火",   "voice": "dongbei"},
    {"meme": "doge",       "text": "反转一句话",     "voice": "narrator", "punch": true, "sfx": "boom"},
    {"meme": "speechless", "text": "无语自嘲",       "voice": "boy"},
    {"meme": "tired",      "text": "彻底躺平收尾",   "voice": "dongbei",  "sfx": "fail"}
  ],
  "_post": {
    "title": "发布标题25~35字，含情绪词+反转钩子",
    "tags": ["#搞笑", "#表情包", "#反转", "#抽象", "#段子", "#每日一笑", "#魔性", "#鬼畜", "#脱口秀"],
    "caption": "评论区置顶文案40~60字，共鸣+引导评论"
  }
}

可用 meme 情绪: {emotions}
可用 voice（只能用这4个）: narrator / dongbei / shaanxi / boy
可用 bgm: scheming / silly / sneaky / goofy / upbeat / suona / merry / sad
可用 sfx: wow, boom, dun, bruh, fail, laugh, damage, goose, drumroll, pop_cat, scratch, vl_nigan, vl_wudi
"""

EXAMPLES = """
【爆款结构参考 — 学节奏不抄内容】

① 深情错付型（旁白以第三人称讲故事）
hook: "注意看他准备好好讲述这段感情了"
shots:
  love/narrator    - "他记得两个人认识的第一天"
  smug/narrator    - "记得她当时穿着什么颜色的衣服"
  shock/narrator   - "记得她说的每一句话 每一个标点"
  love/narrator    - sfx:wow — "他觉得这就是命中注定"
  confused/dongbei - "然后他鼓起勇气发出了那条消息"
  doge/narrator    - PUNCH sfx:boom — "对方问 你是哪位"
  speechless/boy   - "好好好"
  tired/dongbei    - sfx:fail — "那三年就当交了学费"
endcard: main="有同款经历的扣1" sub="不是你的问题，是缘分不够" cta="关注我，明天讲更惨的"

② 越努力越惨型（第一人称自嘲旁白）
hook: "我研究过让别人喜欢自己的方法"
shots:
  smug/narrator    - "首先要建立信任感"
  smug/narrator    - sfx:wow — "其次要制造情绪价值"
  shock/narrator   - "然后要适时展现脆弱"
  love/narrator    - "最后要制造悬念让对方惦记"
  confused/dongbei - "我认真研究了整整半年"
  doge/narrator    - PUNCH sfx:boom — "我单身十二年"
  laugh/boy        - "理论满分"
  tired/dongbei    - sfx:fail — "实践零分 成功从入门到放弃"
endcard: main="感情小白请扣1" sub="知道和做到之间差了一个银河系" cta="关注我 下期教你真正有用的"

③ 朋友说的型（转述他人神逻辑）
hook: "我朋友跟我说了一句话 我想了三天"
shots:
  confused/narrator - "他说 你不能太在意一个人"
  smug/narrator     - "因为在意就会患得患失"
  shock/narrator    - sfx:wow — "患得患失就会出问题"
  love/narrator     - "所以要学会云淡风轻"
  smug/dongbei      - "我觉得他说得对"
  doge/narrator     - PUNCH sfx:boom — "他谈了七年的女朋友跟别人跑了"
  speechless/boy    - "怪不得他想得这么开"
  tired/dongbei     - sfx:fail — "这叫被迫觉悟"
endcard: main="被迫觉悟过的扣1" sub="有些道理是用代价换来的" cta="关注我 我也被迫觉悟过"
"""


def _validate(script: dict) -> dict:
    shots = script.get("shots") or []
    shots = shots[:10] if len(shots) > 10 else shots
    if len(shots) < 5:
        raise ValueError(f"shots 不足（{len(shots)}），至少 5 个")

    valid_emotions = set(assets.available_emotions())
    valid_sfx = {"wow","boom","dun","bruh","fail","laugh","damage","goose",
                 "drumroll","pop_cat","scratch","vl_nigan","vl_wudi","suona","whoosh","huh","boing"}
    valid_motions = {"punch_in","pull_back","shake","spin_in","drift","strobe_zoom","glitch","bounce"}

    for s in shots:
        if s.get("meme") not in valid_emotions:
            s["meme"] = "doge"
        # 强制 meme 模式只用旁白类音色，禁止 left/right
        voice = s.get("voice", "narrator")
        if voice not in MEME_VOICES:
            voice = "narrator"
        s["voice"] = voice
        if s.get("sfx") and s["sfx"] not in valid_sfx:
            s.pop("sfx", None)
        if s.get("motion") and s["motion"] not in valid_motions:
            s.pop("motion", None)
        text = (s.get("text") or "").strip()
        if not text:
            raise ValueError(f"shot 缺少 text: {s}")
        if len(text) > 40:
            s["text"] = text[:40]

    # 保证有 1~2 个 punch
    punches = [i for i, s in enumerate(shots) if s.get("punch")]
    if not punches:
        idx = max(0, len(shots) - 3)
        shots[idx]["punch"] = True
        shots[idx].setdefault("sfx", "boom")
    elif len(punches) > 2:
        for i in punches[2:]:
            shots[i].pop("punch", None)

    script["shots"] = shots
    script["mode"]  = "meme"
    script.setdefault("bgm_tempo",  1.28)
    script.setdefault("bgm_volume", 0.40)

    # endcard 强制对象格式
    ec = script.get("endcard", {})
    if isinstance(ec, str):
        script["endcard"] = {"main": ec, "sub": "", "cta": "关注我，下集更精彩 🔥"}
    else:
        script.setdefault("endcard", {
            "main": "评论区扣1 👇",
            "sub":  "你也有过这种经历吗",
            "cta":  "关注我，明天出续集 🔥",
        })

    # hook 去 emoji，确保 TTS 能念
    hook = script.get("hook")
    if isinstance(hook, str):
        script["hook"] = {"text": hook}
    elif not isinstance(hook, dict) or not hook.get("text"):
        raise ValueError("缺少 hook.text")
    script["hook"]["text"] = re.sub(
        r"[\U0001F000-\U0001FAFF\U00002600-\U000027BF]+", "",
        script["hook"]["text"]
    ).strip()

    return script


def generate(topic: str, n: int = 3, model: str = None) -> list[dict]:
    emotions = ", ".join(assets.available_emotions())
    # 用 replace 而非 format，避免 SYSTEM 里的 JSON 示例 {} 被误当占位符
    system   = SYSTEM.replace("{emotions}", emotions) + EXAMPLES
    prompt   = (
        f"请为主题「{topic}」生成 {n} 个表情包段子短视频剧本。"
        f"记住：全程单一旁白视角，不是两人对话，voice 只能用 narrator/dongbei/shaanxi/boy。"
        f"每个剧本 shots 7~10 句，结构完整，情绪搭配符合逻辑，必须附带 _post 运营文案。"
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
        except (ValueError, RuntimeError) as e:
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
