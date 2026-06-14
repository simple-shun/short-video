# short-video · 抖音抽象短视频自动化流水线

一条命令把一个主题变成 1080×1920 竖屏成片：**LLM 写脚本 → 配音(TTS) → 表情包/音效/BGM → 逐帧渲染 → ffmpeg 合成**。

目前有 **4 条生产线**，共用同一套渲染/混音底座：

| 生产线 | CLI | 形态 | 渲染器 | 出片成本 |
|---|---|---|---|---|
| **chat** | （默认，无 flag） | 模拟微信聊天对话段子（左右气泡 + 反转） | `renderer.html` | 仅生成阶段 LLM |
| **meme** | `--meme` | 说书人讲故事 + 表情包段子（钩子→反转→补刀） | `magic.html` | 仅生成阶段 LLM |
| **punchline** | `--punchline` | 金句快剪（一句一炸 + 抽象脸 + 魔性配音 + 随机喜感 BGM） | `magic.html` | 仅生成阶段 LLM |
| **magic** | `--magic` | AI 生图/图生视频 魔性短片（全屏运镜） | `magic.html` | 生成 + **出片生图付费** |

> 渲染、混音、TTS 全部本地/免费；只有 LLM 写脚本、magic 的 AI 生图/视频走 OpenRouter 计费。

---

## 环境要求

| 依赖 | 安装 |
|---|---|
| Python 3.10+（已验证 3.12） | — |
| ffmpeg / ffprobe | `brew install ffmpeg` |
| Python 包 | `pip install -r requirements.txt`（edge-tts / playwright / requests） |
| Chromium 内核 | `playwright install chromium`（仅首次） |
| OpenRouter key | `.env` 里 `OPENROUTER_API_KEY=sk-or-...`（参考 `.env.example`） |

edge-tts 与 OpenRouter 需联网；渲染与合成完全本地。

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # 填入 OPENROUTER_API_KEY
```

---

## 快速开始

```bash
# 1) 生成脚本（LLM）。-n 数量；--make 生成后直接出片
python3 -m pipeline.gen "相亲奇遇"        -n 3            # chat（默认）
python3 -m pipeline.gen "扎心语录" --punchline -n 3 --make # 金句快剪 + 直接出片
python3 -m pipeline.gen "猫主子的早晨" --meme  -n 3        # 表情包段子
python3 -m pipeline.gen "办公室の怪事" --magic -n 2        # 魔性短片（出片会生图付费）

# 2) 把脚本 JSON 出成片
python3 -m pipeline.make scripts/punchline/毒舌_烦你一辈子.json
python3 -m pipeline.make scripts/*.json --keep-frames     # 批量 + 保留帧调试
```

产物在 `output/<片名>/`：成片 `<片名>.mp4` + 封面 `cover.jpg`。
脚本批次落在 `scripts/<月日_时分>_<主题>/`，附 `索引.md`（含评分/毒评/出片命令）。

---

## 架构（分层 + 注册表）

```
pipeline/
├── config.py        # 全局配置：VOICES 声音库 / EMOTIONS / SFX_TAGS / 默认模型 / 路径
├── registry.py      # ⭐ 生产线注册表：GENERATORS(按 CLI flag) + BUILDERS(按 script mode)
├── gen.py           # CLI：批量生成脚本（注册表驱动）
├── make.py          # CLI：脚本 JSON → MP4（注册表驱动）
├── core/            # 基础设施层（与具体生产线无关）
│   ├── llm.py       #   OpenRouter LLM 客户端
│   ├── tts.py       #   edge-tts 配音
│   ├── assets.py    #   表情包/音效/BGM 解析（含 random_bgm）
│   ├── media.py     #   底层音频/ffmpeg 工具
│   ├── render.py    #   Playwright 虚拟时钟逐帧截图（永不掉帧）
│   ├── compose.py   #   配音/音效/BGM 混音 + 侧链闪避 + 封装 mux
│   ├── imagegen.py  #   AI 生图（magic 用）
│   ├── videogen.py  #   AI 图生视频（magic 用）
│   └── batch.py     #   生成共享工具：slugify / judge(毒舌评分) / save_batch
└── lines/           # 生产线层：每条线 = 生成 + 构建
    ├── chat_gen.py / chat_build.py
    ├── meme_gen.py / meme_build.py        # punchline 复用 meme_build 的 style 分支
    ├── punchline_gen.py                   # build 复用 meme_build
    └── magic_gen.py / magic_build.py
```

**数据流**：`gen.py` → `lines/<x>_gen.generate(topic)` → 脚本 JSON →
`make.py` → `lines/<x>_build.build(script)` → 时间轴 payload →
`core/render` 逐帧截图 → `core/compose` 混音封装 → MP4。

### 加一条新生产线

1. 在 `lines/` 写 `<x>_gen.py`（`generate(topic, n, model) -> [script]`）
   和可选的 `<x>_build.py`（`build(script) -> {payload, audio_events, total_ms, bgm, ...}`）。
2. 在 `registry.py` 的 `GENERATORS` / `BUILDERS` 各加一行。

**无需改动 `gen.py` / `make.py`。**

---

## 配置与调参（`pipeline/config.py`）

- `VOICES`：edge-tts 音色库（全局可复用），任何脚本写 `"voice":"名字"` 即可引用。
  含 `moxing`(抖音魔性贱萌搞怪)、`narrator`(魔性解说)、`liao`、`dongbei`/`shaanxi` 等。
- `EMOTIONS`：表情包情绪目录（对应 `assets/memes/<情绪>/`），含 `abstract` 抽象脸池。
- `SFX_TAGS`：音效 tag 词表。
- 模型：`OPENROUTER_MODEL`(文案) / `IMAGE_MODEL` / `VIDEO_MODEL`（见 `.env`）。

各生产线的「风格/提示词」在对应 `lines/<x>_gen.py` 里改；「节奏/动画/音效/BGM」在 `lines/<x>_build.py`。

---

## 素材库与抓取

```
assets/
├── memes/<情绪>/   # 表情包，按情绪分类（含 abstract 抽象/扭曲脸）+ manifest.json
├── sfx/            # 音效（基础 + 魔性笑 + 怪音 + 中文梗语音 voicelines/）+ builtin/ 兜底
├── bgm/            # 背景音乐（沙雕/唢呐/悲怆/紧张…）+ manifest.json
└── voice_ref/      # 参考音色样本
```

按需补素材有 **`material-fetch` skill**（带质量审核）：抓取 → 接触表 → 剔除跑题 → 入库。
底层脚本：`scripts/fetch_material.py`（360/tenor 多源）、`contact_sheet.py`、`curate_material.py`。

---

## 成本说明

- **免费/本地**：edge-tts 配音、Playwright 渲染、ffmpeg 混音封装。
- **付费（OpenRouter）**：`gen` 阶段写脚本的 LLM 调用；`judge` 评分；**magic 出片的 AI 生图/视频**。
- chat / meme / punchline 的**出片**不花钱（只生成阶段 LLM 收费）；magic 出片每条会生图，注意成本。

详细操作另见 `docs/操作手册.md`（注：该手册早于架构重构，模块路径以本 README 为准）。
