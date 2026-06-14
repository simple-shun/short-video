"""生产线注册表 —— 把"加一条新生产线"收敛到这一个文件。

- GENERATORS：CLI flag -> 生成器（topic → 脚本 JSON 列表）
- BUILDERS：  script["mode"] -> 构建器（脚本 → 时间轴 payload）+ 渲染器 HTML

加新线只需：在 lines/ 写 <x>_gen.py（可选 <x>_build.py），在下面两张表各加一行——
不用改 gen.py / make.py 的任何分发逻辑。
"""
from . import config
from .lines import (chat_gen, chat_build, meme_gen, meme_build,
                    punchline_gen, magic_gen, magic_build)

# meme / magic / punchline 共用"魔性"渲染器；chat 用默认 renderer.html（renderer=None）
MEME_HTML = config.ROOT / "renderer" / "magic.html"

GENERATORS = {
    "chat":      {"fn": chat_gen.generate,      "label": "聊天段子",   "judge": True},
    "meme":      {"fn": meme_gen.generate,      "label": "表情包段子", "judge": False},
    "punchline": {"fn": punchline_gen.generate, "label": "金句快剪",   "judge": False},
    "magic":     {"fn": magic_gen.generate,     "label": "魔性短片",   "judge": True},
}

BUILDERS = {
    "chat":  {"fn": chat_build.build,  "renderer": None},        # None → 默认 renderer.html
    "meme":  {"fn": meme_build.build,  "renderer": MEME_HTML},   # punchline(mode=meme) 在此复用
    "magic": {"fn": magic_build.build, "renderer": MEME_HTML},
}
