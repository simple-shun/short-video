#!/usr/bin/env python3
"""通用素材抓取器：按标签/关键词从图源下载表情包到 assets/memes/<tag>/，
去重、限量、校验，生成接触表(contact sheet)供人工/Agent 审核，并更新 manifest。

被 material-fetch skill 调用。也可直接命令行用。

来源：
  360   —— image.so.com 搜图（中文素材主力，反爬松，缩略图低清但贴“抽象模糊”风格）
  tenor —— g.tenor.com v1（欧美 emoji/GIF，匿名 key）

用法示例：
  # 用内置预设抓“抽象扭曲脸”
  python3 scripts/fetch_material.py --tag abstract --rebuild

  # 自定义关键词抓某风格（中文）
  python3 scripts/fetch_material.py --tag chic --source 360 \
      --keywords "高级感表情包,优雅猫猫" --count 40 --per 10

  # 欧美 emoji
  python3 scripts/fetch_material.py --tag cursed --source tenor \
      --queries "cursed emoji,blue emoji meme" --count 30

抓完务必看接触表 assets/memes/<tag>/_contact.png 审核质量，剔除不合适的图。
"""
import argparse
import hashlib
import json
import subprocess
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEME_DIR = ROOT / "assets" / "memes"
MANIFEST = MEME_DIR / "manifest.json"

# 内置预设：tag -> (source, 关键词/查询)
PRESETS = {
    # 参考视频风格：模糊/扭曲/猥琐/简笔画 抽象脸（中文）
    "abstract": ("360", ["抽象表情包", "扭曲熊猫头", "鬼畜表情包", "猥琐表情包",
                          "沙雕表情包", "发癫表情包", "简笔画抽象表情包", "抽象熊猫头"]),
}


def _curl(url, referer, binary=False):
    cmd = ["curl", "-s", "--max-time", "20", "-A", "Mozilla/5.0", "-e", referer, url]
    r = subprocess.run(cmd, capture_output=True, timeout=35)
    return r.stdout if binary else r.stdout.decode("utf-8", "ignore")


def _valid(data: bytes, min_kb=4):
    if not data or len(data) < min_kb * 1024:
        return None
    if data[:4] == b"GIF8":
        return ".gif"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    return None


def search_360(word, pages):
    urls = []
    for pi in range(pages):
        u = (f"https://image.so.com/j?q={urllib.parse.quote(word)}"
             f"&src=srp&pn={pi*60}&rn=60")
        try:
            lst = json.loads(_curl(u, "https://image.so.com/")).get("list", [])
        except Exception:
            lst = []
        for x in lst:
            mu = x.get("thumb") or x.get("img")
            if mu:
                urls.append(mu)
        time.sleep(0.4)
    return urls


def search_tenor(query, want):
    key = "LIVDSRZULELA"
    u = (f"https://g.tenor.com/v1/search?"
         + urllib.parse.urlencode({"q": query, "key": key, "limit": want + 8,
                                   "media_filter": "minimal", "contentfilter": "medium"}))
    try:
        data = json.loads(_curl(u, "https://tenor.com/"))
    except Exception:
        return []
    out = []
    for r in data.get("results", []):
        media = r.get("media", [{}])[0]
        for k in ("gif", "mediumgif", "tinygif"):
            if media.get(k, {}).get("url"):
                out.append(media[k]["url"])
                break
    return out


def contact_sheet(dest: Path):
    """用 PIL 把目录里的图拼成带编号的接触表，供审核（编号对应排序，便于按号删）。"""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "cs", str(Path(__file__).parent / "contact_sheet.py"))
        cs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cs)
        return cs.build(str(dest), out=f"/tmp/contact_{dest.name}.png")
    except Exception as e:
        print(f"  接触表生成失败: {e}")
        return None


def main():
    ap = argparse.ArgumentParser(description="通用素材抓取器")
    ap.add_argument("--tag", required=True, help="目标标签（assets/memes/<tag>/）")
    ap.add_argument("--source", default=None, choices=["360", "tenor"], help="图源")
    ap.add_argument("--keywords", default="", help="360 中文关键词，逗号分隔")
    ap.add_argument("--queries", default="", help="tenor 英文查询，逗号分隔")
    ap.add_argument("--count", type=int, default=80, help="总量上限")
    ap.add_argument("--per", type=int, default=12, help="每个关键词保留上限")
    ap.add_argument("--pages", type=int, default=2, help="360 每词翻页数")
    ap.add_argument("--min-kb", type=int, default=4, help="最小文件大小KB（滤垃圾）")
    ap.add_argument("--rebuild", action="store_true", help="先清空该标签目录再抓")
    args = ap.parse_args()

    # 解析关键词/源
    source = args.source
    terms = []
    if args.keywords:
        terms = [k.strip() for k in args.keywords.split(",") if k.strip()]
        source = source or "360"
    elif args.queries:
        terms = [k.strip() for k in args.queries.split(",") if k.strip()]
        source = source or "tenor"
    elif args.tag in PRESETS:
        source, terms = PRESETS[args.tag]
    else:
        ap.error(f"标签 {args.tag} 无预设，请用 --keywords 或 --queries 指定")

    dest = MEME_DIR / args.tag
    dest.mkdir(parents=True, exist_ok=True)
    if args.rebuild:
        for p in dest.glob("*"):
            if p.is_file():
                p.unlink()

    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else []
    if args.rebuild:
        manifest = [x for x in manifest if x.get("tag") != args.tag]
    seen = {hashlib.sha1(p.read_bytes()).hexdigest()
            for p in dest.glob("*") if p.is_file()}

    print(f"▶ 抓取 tag={args.tag} source={source} 关键词={terms}")
    added, idx = 0, {}
    ref = "https://image.so.com/" if source == "360" else "https://tenor.com/"
    for t in terms:
        if added >= args.count:
            break
        urls = search_360(t, args.pages) if source == "360" else search_tenor(t, args.per + 6)
        subj = "".join(ch for ch in t if ch.isalnum())[:10] or f"k{len(idx)}"
        kept = 0
        for u in urls:
            if added >= args.count or kept >= args.per:
                break
            try:
                data = _curl(u, ref, binary=True)
            except Exception:
                continue
            ext = _valid(data, args.min_kb)
            if not ext:
                continue
            h = hashlib.sha1(data).hexdigest()
            if h in seen:
                continue
            seen.add(h)
            idx[subj] = idx.get(subj, 0) + 1
            fname = f"{args.tag}_{subj}_{idx[subj]}{ext}"
            (dest / fname).write_bytes(data)
            manifest.append({"file": f"{args.tag}/{fname}", "tag": args.tag,
                             "source": u, "license": "unknown - personal use"})
            added += 1
            kept += 1
            time.sleep(0.12)
        print(f"  '{t}': +{kept}（累计 {added}）")

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    sheet = contact_sheet(dest)
    total = len([p for p in dest.glob('*') if p.is_file() and not p.name.startswith('_')])
    print(f"\n✅ tag={args.tag} 新增 {added}，目录共 {total} 张，manifest 已更新")
    if sheet:
        print(f"📋 接触表（审核用）：{sheet}")
    print("⚠️  请审核接触表，剔除跑题/文字过多/低质图后再用。")


if __name__ == "__main__":
    main()
