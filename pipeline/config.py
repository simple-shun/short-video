"""全局配置：路径、密钥、默认参数。"""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SFX_DIR = ASSETS / "sfx"
BGM_DIR = ASSETS / "bgm"
MEME_DIR = ASSETS / "memes"
SCRIPTS_DIR = ROOT / "scripts"
OUTPUT_DIR = ROOT / "output"
RENDERER_HTML = ROOT / "renderer" / "renderer.html"

# ── 视频参数 ──
FPS = 30
# 设计尺寸 540x960，deviceScaleFactor=2 → 实际输出 1080x1920
VIEW_W, VIEW_H = 540, 960
SCALE = 2

# ── OpenRouter ──
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
# 段子生成默认模型；可用 --model 覆盖。中文梗类创作 deepseek 性价比高，
# 想要更强可换 anthropic/claude-sonnet-latest 等
DEFAULT_MODEL = "deepseek/deepseek-v4-pro"


def openrouter_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    md = ROOT / "openrouter.md"
    if md.exists():
        m = re.search(r'(sk-or-[A-Za-z0-9-]+)', md.read_text())
        if m:
            return m.group(1)
    raise RuntimeError("找不到 OpenRouter key：请设置 OPENROUTER_API_KEY 或在 openrouter.md 中提供")


# ── 默认音色（edge-tts）──
# 左右默认用"尖快女声 vs 浑厚男声"的强反差组合，加速升调制造魔性感
VOICES = {
    "left":     {"voice": "zh-CN-XiaoyiNeural",           "rate": "+28%", "pitch": "+22Hz"},  # 尖快做作女声
    "right":    {"voice": "zh-CN-YunjianNeural",          "rate": "+22%", "pitch": "+0Hz"},   # 浑厚解说男声
    "boy":      {"voice": "zh-CN-YunxiaNeural",           "rate": "+20%", "pitch": "+0Hz"},   # 贱萌男声
    "narrator": {"voice": "zh-CN-YunjianNeural",          "rate": "+30%", "pitch": "+12Hz"},  # 魔性解说
    "dongbei":  {"voice": "zh-CN-liaoning-XiaobeiNeural", "rate": "+18%", "pitch": "+0Hz"},   # 东北话
    "shaanxi":  {"voice": "zh-CN-shaanxi-XiaoniNeural",   "rate": "+18%", "pitch": "+0Hz"},   # 陕西话
}

# ── 时间轴参数（毫秒）──
PRE_ROLL = 800        # 开场标题缓冲
PAD_AFTER_AUDIO = 380 # 配音念完后的呼吸
IMAGE_DWELL = 1600    # 纯表情包消息停留
SILENT_DWELL = 1000   # 无配音文字消息停留
PUNCH_EXTRA = 350     # punch 消息额外停顿
END_HOLD = 2400       # 结尾定格

# 表情包情绪目录（与 assets/memes/ 子目录对应）
EMOTIONS = ["shock", "speechless", "laugh", "cry", "doge", "angry", "smug", "confused",
            "money", "scheme", "no", "love", "tired"]
