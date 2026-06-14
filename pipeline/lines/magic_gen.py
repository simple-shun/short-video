"""magic 生产线 — 生成：LLM 产出"抽象魔性短片"分镜脚本 JSON。"""
from ..core import llm
from .. import config

SFX_TAGS = config.SFX_TAGS

SYSTEM_MAGIC = """你是抖音"抽象魔性短片"的分镜导演。这类视频 5~20 秒、3~8 个镜头：
全屏 AI 魔性图片 + 暴力运镜 + 大字幕 + 魔性旁白 + 音效轰炸，越癫越好。

爆款公式：
1. 第 1 镜 = 视觉炸弹（最离谱的画面直接砸脸）+ 悬念旁白
2. 中段递进：一镜比一镜癫，旁白像精神状态美丽的解说
3. 反转镜：画面/旁白打破前面建立的预期（用 pull_back 或 shake 运镜 + dun/boom）
4. 尾镜留钩：金句旁白收尾

图片提示词（image 的 gen: 后面）写法要素：主体+离谱动作+夸张表情+魔性视觉风格
（鱼眼镜头/过曝闪光/土味放射线/高饱和/油腻写实…），每镜画面必须荒诞具体。

运镜选择：punch_in 急推(强调) / pull_back 反拉(揭晓全景反转) / shake 震动(冲击) /
spin_in 旋转切入 / drift 慢漂移(蓄势) / strobe_zoom 鼓点跳推(高潮) / glitch 故障闪(癫狂峰值)

输出严格 JSON 数组，每个元素：
{
  "mode": "magic",
  "title": "短标题",
  "intro": {"text": "注意看式开场白≤16字"},
  "cover": {"title": "封面大字≤12字", "sub": "红条副标题≤12字"},
  "bgm": "chaos|silly|tension|suona|sad",
  "messages_unused": null,
  "shots": [
    {"image": "gen:图片提示词", "motion": "punch_in", "caption": "大字≤8字",
     "narration": "旁白≤16字", "sfx": "boom", "sticker": "meme:doge"}
  ]
}
caption 是画面大字（可省）；narration 是魔性解说音旁白（建议每镜都有，节奏靠它）；
sticker 表情包角标（全片最多 2 次）；sfx 同聊天线的 tag 体系。
关键镜头（反转/高潮，每片 1~2 个）可加 "animate": true 和 "motion_prompt": "画面如何动起来≤30字"
——会用图生视频让画面真的动起来（如 "猫突然转头瞪向镜头，杠铃掉落砸地"）。
"""


def _validate_magic(s):
    if not isinstance(s, dict):
        raise ValueError(f"脚本不是对象: {type(s).__name__}")
    shots = s.get("shots")
    if not isinstance(shots, list) or not 2 <= len(shots) <= 10:
        raise ValueError(f"shots 数量非法: {shots if not isinstance(shots, list) else len(shots)}")
    for sh in shots:
        if not isinstance(sh, dict) or not sh.get("image"):
            raise ValueError(f"镜头缺 image: {sh}")
        if sh.get("caption") and len(sh["caption"]) > 12:
            sh["caption"] = sh["caption"][:12]
        if sh.get("narration") and len(sh["narration"]) > 26:
            sh["narration"] = sh["narration"][:26]
        if sh.get("sfx") and sh["sfx"] not in SFX_TAGS:
            sh.pop("sfx")
    s["mode"] = "magic"
    s.setdefault("title", "未命名魔性短片")
    s.pop("messages_unused", None)
    return s


def generate(topic: str, n: int = 3, model: str = None):
    user = f"主题/方向：{topic}\n请生成 {n} 个互不雷同的魔性短片分镜，直接输出 JSON 数组。"
    data = None
    for attempt in range(2):
        try:
            raw = llm.chat(
                [{"role": "system", "content": SYSTEM_MAGIC},
                 {"role": "user", "content": user}],
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
            out.append(_validate_magic(s))
        except Exception as e:
            print(f"  跳过无效分镜: {e}")
    return out
