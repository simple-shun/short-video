# CLAUDE.md — 本项目协作约定

短视频自动化流水线。完整说明见 `README.md`；本文件是给 Claude Code 的工作约定。

## 语言
- 一律简体中文回复（含解释、注释）。

## 架构地图（改代码前先定位）
分层 + 注册表，详见 `README.md`：
- `pipeline/config.py` — 配置：`VOICES` 声音库 / `EMOTIONS` / `SFX_TAGS` / 模型 / 路径
- `pipeline/registry.py` — **生产线注册表**：`GENERATORS`(按 CLI flag) + `BUILDERS`(按 script mode)
- `pipeline/core/` — 基础设施（llm/tts/assets/media/render/compose/imagegen/videogen/batch），**与生产线无关**
- `pipeline/lines/` — 生产线：`<x>_gen.py`(LLM→脚本) + `<x>_build.py`(脚本→时间轴)
- `pipeline/gen.py` / `make.py` — CLI 入口，注册表驱动

## 接口约定（新增/修改生产线时遵守）
- 生成器：`generate(topic, n, model) -> [script_dict]`
- 构建器：`build(script) -> {payload, audio_events, total_ms, bgm, bgm_volume, bgm_tempo, bgm_duck_*}`，**自包含**（含自己的 TTS）
- `BUILDERS` 项的 `renderer`：`None`=默认 `renderer.html`，否则传 `magic.html` 路径
- **加新生产线只改 `lines/` + `registry.py`，不要动 `gen.py`/`make.py` 的分发**
- punchline 脚本 `mode:"meme"+style:"punchline"`，出片走 `meme_build` 的 style 分支（不要新增 mode）

## 常用命令
```bash
python3 -m pipeline.gen "主题" [--meme|--punchline|--magic] -n 3 [--make] [--no-judge] [--model X]
python3 -m pipeline.make scripts/xxx.json [--keep-frames]
```

## 验证（重构/改 build 后必做）
- **build 金标对拍**：改结构/搬移时，对 meme+punchline+chat 调 `build()`，归一化路径后与改前逐字节比对（零成本，edge-tts 免费）。
- 出片冒烟：跑一条 punchline/meme 确认渲染+混音+封装通。
- **不要为验证随便跑 `--magic` 出片**——magic 出片会 AI 生图，**付费**。magic 用源码/导入级验证即可。

## 成本敏感（重要）
- 免费：edge-tts、Playwright 渲染、ffmpeg。付费(OpenRouter)：LLM 生成/评分、magic 生图/视频。
- 跑批量生成或 magic 出片前，先估算并报价给用户确认；默认走节约模式。

## 易错点（gotchas）
- 渲染是 Playwright **虚拟时钟** `window.SV.seek(ms)` 逐帧截图（`renderer/*.html`），不是播放录屏——改动画要保证任意 t 可重建。
- GIF 表情包出片前会被取首帧静图（`meme_build._to_static`），别指望 GIF 动。
- 出片色彩按 BT.709 标记（`compose.mux_video`），勿随意改 colorspace 参数。
- 表情包/BGM 随机选由 **title 作种子**（可复现）；改标题会换图/换曲。
- `config.VOICES` 是全局声音库；caption 文本 = TTS 文本（同一字段），写字母/拼音会被念坏。

## 素材
- 补素材用 `material-fetch` skill（抓取→接触表审核→剔除跑题→入库），勿抓几百张污染库。
- 360 搜图是中文抽象/扭曲脸主力源；欧美 emoji 用 tenor。

## 安全
- 永不提交 `.env` / `openrouter.md` / 任何 `sk-or-` key（已在 .gitignore）。
- 改动遵循「外科手术式」：只动与需求相关的行，匹配现有风格，不顺手重构无关代码。
