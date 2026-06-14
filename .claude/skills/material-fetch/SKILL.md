---
name: material-fetch
description: 按需为短视频素材库下载符合方向的高质量表情包/图片素材，并带质量审核（抓取→接触表→人工剔除→入库）。当用户说"素材不够/再找点表情/抓一批XX风格的表情/补充某标签素材/给素材库加图"时触发。
---

# 素材抓取 Skill（带质量审核）

为 `assets/memes/<tag>/` 按需补充符合视频方向的素材。**核心是质量**：图源搜索结果鱼龙混杂，
必须经过"抓取→看接触表→剔除跑题/文字过多/低质→入库"，不能抓完直接用。

## 何时用
- 现有标签素材不够，要补量
- 要新建一类风格的表情标签（如 abstract 抽象脸、cute 高级感、cry 哭等）
- 用户给了参考图/风格，要找类似素材

## 风格基线（本项目方向）
做的是"抽象/魔性/搞怪/猥琐、不正经"的抖音自媒体短视频。素材审核标准：
- ✅ 要：扭曲熊猫头、简笔画抽象脸、deep-fried 扭曲脸、扭曲动物脸、猥琐鬼脸——**脸为主、最好少字或无字**
- ❌ 剔除：真人脱口秀/综艺截图、正常动画截图、正常猫狗、纯文字海报、整段文字的反应表情包
  （这些表情自带大段文字，会和我们的字幕打架）

## 执行步骤

### 1. 确定 tag 与关键词
- 复用已有 tag 直接补量；新风格起个英文 tag。
- `abstract` 已有内置预设。其他风格自己定中文关键词（要具体、贴风格），例如：
  - 抽象脸：`扭曲熊猫头,简笔画抽象表情包,抽象熊猫头,deep fried 表情`
  - 高级感猫：`高级感猫猫表情包,优雅猫`
- 中文素材用 `--source 360`（image.so.com，反爬松，缩略图低清正好贴"模糊抽象"风）；
  欧美 emoji/GIF 用 `--source tenor --queries "cursed emoji,blue emoji meme"`。

### 2. 抓取（故意多抓，留出剔除余量）
```bash
# 用预设
python3 scripts/fetch_material.py --tag abstract --rebuild
# 自定义关键词
python3 scripts/fetch_material.py --tag <tag> --source 360 \
    --keywords "关键词1,关键词2" --count 80 --per 12 --pages 2
```
- `--rebuild` 清空该 tag 目录重抓；不加则追加（自动按内容去重）。
- 抓完会自动生成接触表 `/tmp/contact_<tag>.png` 并打印路径。

### 3. 审核（必做！用 Read 看接触表）
```bash
# 量大时分批生成更清晰的接触表（每张 cols=7）
python3 -c "import importlib.util as u; s=u.spec_from_file_location('cs','scripts/contact_sheet.py'); m=u.module_from_spec(s); s.loader.exec_module(m); m.build('assets/memes/<tag>',0,45,cols=7,out='/tmp/c1.png'); m.build('assets/memes/<tag>',45,200,cols=7,out='/tmp/c2.png')"
```
用 Read 打开 `/tmp/c1.png`、`/tmp/c2.png`。图块左下角编号 = 文件排序号。
按"风格基线"逐张判断，记下要删的编号（真人截图/正常动画动物/纯文字/字太多的）。

### 4. 剔除入库
```bash
python3 scripts/curate_material.py --tag <tag> --remove "2,3,5,70-84"
# 或反向：只保留好的
python3 scripts/curate_material.py --tag <tag> --keep-only "1,4,7-20"
```
会删图并重建该 tag 的 manifest 条目。剔除后可再跑一次第 3 步复查。

### 5. 注册标签（仅新 tag 需要）
若是**新** tag 且要用于 meme/punchline 渲染，把它加进 `pipeline/config.py` 的 `EMOTIONS` 列表
（`meme_build` 用它校验合法情绪；punchline 已固定用 `abstract`）。已有 tag 跳过。

### 6. 报告
告诉用户：tag、最终保留数量、剔除了多少、接触表路径。建议出一条片复检观感。

## 注意
- 360 缩略图是低清的——对"模糊抽象"风是加分，但若要高清素材该换源。
- 版权：素材标注 `license: unknown - personal use`，仅个人/测试用途。
- 不要一次抓几百张（之前踩过坑）：`--count` 控制在 ~80，`--per` 每词 ~12，够选即可。
