"""chat 生产线 — 生成：LLM 按反转公式批量产出聊天脚本 JSON。"""
from ..core import assets, llm
from .. import config

SFX_TAGS = config.SFX_TAGS

SYSTEM = """你是抖音千万赞沙雕聊天段子的顶级编剧。风格关键词：癫、抽象、神经质、不按常理出牌。
观众是刷短视频的年轻人，前 3 秒不炸就划走——平庸 = 死亡。
你的段子将被自动渲染成竖屏短视频：每条消息配 TTS 魔性配音、表情包、音效。

【笑点武器库】每个本子至少动用 3 种：
- 神回复：对方说 A，回一个完全在另一个次元但莫名自洽的 B（"人家不开心"→"那你开一下"）
- 字面理解：把客套话/比喻当真并认真执行（"改天请你吃饭"→"查了日历，改天是周四"）
- 反向自信：明明很惨/很蠢却无比骄傲，还要发战报
- 过度执行：把小事用力过猛办成大事（让带瓶水→开来一辆消防车）
- 突然认真：插科打诨中突然一本正经说出更离谱的话
- 已读乱回/阴阳怪气/精神状态美丽（"睡了吗"→"睡了，梦游回的"）

【反转铁律】
- 反转必须是"信息差炸弹"：前文处处埋伏笔但观众想不到，回看才恍然大悟
- 低级反转一律禁止：做梦醒来/纯巧合/认错人/普通误会
- 反转后必须再补 1~2 刀（更狠的细节或二次反转），刀刀升级
- 最后一条消息要"留钩"：一句让人想截图转发的金句

【硬性禁令】
- 禁止礼貌寒暄、禁止说教、禁止暖心结局
- "哈哈哈"刷屏最多出现 1 条，禁止用它凑数
- 禁止 [链接][视频][截图] 这类伪富媒体标记（会被配音念出来）；要发"图"就用 meme 表情包消息
- 每条消息必须推进剧情或制造笑点；删掉不心疼的消息直接删掉
- 台词像深夜微信原文：口语、跳跃、可以有省略和错别字感

【自检】写完每个本子问自己：把反转讲给朋友听，他会不会笑出声？不会就推翻重写。

【节奏与质感】（治"冷笑话感"的药）
- 多用"连发"：同一个人连发 2~4 条短消息，越说越离谱，像失控的碎碎念
  （例：r:我查了 / r:你家这个户型 / r:风水上叫"困龙局" / r:难怪你单身）
- 拒绝干巴巴的一问一答：消息要有具体质感——具体的数字、品牌、地名、人名比形容词好笑
  （"很贵"❌ →"花了我三个月奶茶钱"✓；"买了个车"❌ →"粉色的大G"✓）
- 长短错落：铺垫用短句，反转后的爆发/输出可以放开到 30 字
- 至少安排一处"停顿戏"：typing=true 憋大招，或连续两条 punch 级补刀

格式要求：
- 普通消息 ≤ 20 字，爆发消息可到 30 字；总共 9~16 条
- 在情绪强烈处插入表情包消息：{"side":"left","meme":"<情绪>"}
- 反转那条：punch=true 且配 sfx（dun 或 boom）
- 怪音是节目效果的灵魂，按情境用：goose 配离谱发言 / bruh 配无语 / damage 配被暴击 /
  drumroll 配揭晓前 / laugh_duck、laugh_evil 等魔性笑 / vl_nigan"你干嘛"配被整懵 / vl_wudi 雪豹配嘴硬

输出严格 JSON 数组（不要任何解释文字），每个元素是一个完整脚本：
{
  "title": "内部标识用短标题",
  "hook": "视频顶部大字标题，≤14字，强烈好奇缺口，可带1个emoji",
  "intro": {"text": "开场白≤18字，'注意看'式悬念，由魔性解说音念出，决定前3秒去留"},
  "cover": {"title": "封面大字≤12字，比hook更炸的悬念", "sub": "封面红条副标题≤12字，补刀式钩子"},
  "chat_title": "聊天窗口顶部名字，如：和死党的聊天",
  "left":  {"avatar": "一个emoji", "bg": "#hex色"},
  "right": {"avatar": "一个emoji", "bg": "#hex色"},
  "bgm": "silly",
  "messages": [
    {"side": "left", "text": "..."},
    {"side": "right", "text": "...", "typing": true},
    {"side": "left", "meme": "shock"},
    {"side": "left", "text": "反转句", "punch": true, "sfx": "dun"},
    {"side": "right", "text": "哈哈哈哈哈哈", "sfx": "laugh"}
  ]
}

可用 sfx tag: {sfx_tags}
（怪音用法提示：goose 鹅叫配离谱发言、bruh 配无语、damage 配被暴击、drumroll 配揭晓前、
laugh_duck/laugh_evil 等魔性笑配不同笑点、vl_nigan"你干嘛"配被整懵、vl_wudi 雪豹配嘴硬）
可用 meme 情绪: {emotions}
（money 要钱数钱 / scheme 算计搓手 / no 拒绝 / love 舔狗讨好 / tired 摆烂躺平）
可用 bgm tag: silly / sneaky / scheming / goofy / chaos / upbeat / suona 唢呐 / sad 悲怆钢琴 / tension 紧张渐强
typing=true 表示出现前显示"正在输入"（用在憋大招的消息前，制造停顿）

全屏插播（打断聊天的吐槽卡，节目效果核武器，每片用 1~2 次）：
{"cutaway": "<meme情绪>", "caption": "旁白吐槽≤15字", "sfx": "<音效>"}
聊天画面会被黑屏+大图+大字旁白打断，caption 由魔性解说音念出。
用在：反转炸开的瞬间（配 boom/suona）、离谱发言之后（配 goose/vl_haha）。
caption 要像弹幕嘴替："家人们谁懂啊" "他真的我哭死" "这就是纯爱战神吗" 这个味。
"""

EXAMPLE = """已验证爆款的结构拆解（学结构和疯感，不要照抄内容）：
① 诈骗反杀：问卡里多少钱→"我说37块8"(punch)→"他挂了"→补刀"我还没问他怎么变多呢"
   （惨到反杀 + 结尾留钩）
② 彩礼反转：女方层层加价(38万8/粉色大G/房本写名)→男方秒答应到诡异→"都准备好了"
   →甩出婚礼现场照(punch)→"正办着呢，新娘是小芳"→"随礼不？给你妈留个上座"
   （过度顺从埋伏笔 + 实名制反转 + 三连补刀；聊天窗口名"未婚妻（暂定）"也是伏笔）
③ 香菜事故："千万别放香菜"→"一片叶子没放"→"那咋铺了一层葱花？？"(punch)
   →"你只说不放香菜啊"（字面理解流：认真执行了错误的事）

全网验证过的爆款流派（来自抖音/知乎热门聊天段子，学机制）：
④ 侮辱翻译成情话（舔狗反向解读，直男撩妹核武器）：
   她说"滚"→"滚是三点水，代表你对我的思念如滚滚流水"；被骂 sb→"s是sweet，b是baby，
   你在叫我 sweet baby"（对方越凶，他翻译得越甜，最后对方先崩溃）
⑤ 人设爆破：前半段努力装X立人设，最后一拍自己拆穿——
   "又拒绝了三个男生，我真是优秀的女孩……你们这楼盘、保险、理财我是真买不起"；
   "小时候妈妈给我定了娃娃亲，是个超帅的哥哥……好像叫易烊千玺"
⑥ 深情铺垫×市侩落点（留钩金句的标准结构）：
   "你不用故作冷淡，我没想过纠缠，最后一次了——借我十块钱吧"；
   "如果全世界都不要你了，记得来找我——我认识好几个人贩子"
⑦ 发疯文学（情绪超载的癫，铺垫期角色崩溃时用）：
   "你为什么骂我？你不知道我很脆弱吗？你的一句话就能击碎我最后的防线！
   你什么都不知道！你只在乎你自己！"——崩溃要崩得华丽、排比、小题大做
⑧ 谐音/双关收尾（TTS 念出来加倍好笑）："我也想过过过儿过过的生活"

反面教材（这种平庸度=划走）：肚子疼→多喝热水→帮叫跑腿→"你是美团骑手吧"。
毛病：每步都猜得到、没有疯感、反转只是一句吐槽不是炸弹。
"""


def _validate(s):
    if not isinstance(s, dict):
        raise ValueError(f"脚本不是对象: {type(s).__name__}")
    for k in ("title", "hook", "messages"):
        if k not in s:
            raise ValueError(f"缺字段 {k}")
    msgs = s["messages"]
    if not isinstance(msgs, list):
        raise ValueError(f"messages 不是数组: {type(msgs).__name__}")
    if not 6 <= len(msgs) <= 20:
        raise ValueError(f"消息数 {len(msgs)} 不在 6~20")
    for side in ("left", "right"):
        if side in s and not isinstance(s[side], dict):
            s.pop(side)  # 形态错误就丢掉，走默认头像
    if "intro" in s:
        if not isinstance(s["intro"], dict):
            s["intro"] = {"text": str(s["intro"])}
        s["intro"]["text"] = str(s["intro"].get("text", ""))[:24]
    if "cover" in s:
        if not isinstance(s["cover"], dict):
            s.pop("cover")
        else:
            for k in ("title", "sub"):
                if s["cover"].get(k):
                    s["cover"][k] = str(s["cover"][k])[:16]
    has_punch = False
    for m in msgs:
        if not isinstance(m, dict):
            raise ValueError(f"消息不是对象: {m!r}")
        if m.get("cutaway"):
            if m["cutaway"] not in config.EMOTIONS:
                m["cutaway"] = "shock"  # 非法情绪降级
            if m.get("caption") and len(m["caption"]) > 20:
                m["caption"] = m["caption"][:20]
            continue
        if m.get("side") not in ("left", "right"):
            raise ValueError(f"side 非法: {m}")
        if not m.get("text") and not m.get("meme") and not m.get("image"):
            raise ValueError(f"消息既无 text 也无 meme: {m}")
        if m.get("text") and len(m["text"]) > 36:
            raise ValueError(f"消息过长: {m['text']}")
        if m.get("meme") and m["meme"] not in config.EMOTIONS:
            m["meme"] = "doge"  # 非法情绪降级
        if m.get("sfx") and m["sfx"] not in SFX_TAGS:
            m.pop("sfx")
        if m.get("punch"):
            has_punch = True
    if not has_punch:
        # 没标 punch 就把倒数第三条当反转
        msgs[max(0, len(msgs) - 3)]["punch"] = True
    return s


def generate(topic: str, n: int = 3, model: str = None):
    emotions = assets.available_emotions() or config.EMOTIONS
    system = SYSTEM.replace("{sfx_tags}", ", ".join(SFX_TAGS)) \
                   .replace("{emotions}", ", ".join(emotions))
    user = f"{EXAMPLE}\n主题/方向：{topic}\n请生成 {n} 个互不雷同的脚本，直接输出 JSON 数组。"
    data = None
    for attempt in range(2):  # 模型偶发输出畸形 JSON，自动重试一次
        try:
            raw = llm.chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                model=model, temperature=0.95,
            )
            data = llm.extract_json(raw)
            break
        except (ValueError, RuntimeError) as e:
            if attempt == 1:
                raise
            print(f"  生成失败将重试: {e}")
    if isinstance(data, dict):
        data = [data]
    out = []
    for s in data:
        try:
            out.append(_validate(s))
        except Exception as e:  # 单个脚本畸形不连坐整批
            print(f"  跳过无效脚本: {e}")
    return out
