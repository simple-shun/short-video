#!/usr/bin/env python3
"""审核剔除：按接触表上的编号删除某标签下的跑题/低质素材，并重建 manifest。
编号与 contact_sheet.py / fetch_material.py 的排序一致（按文件名 sorted，1-based）。

用法：
  python3 scripts/curate_material.py --tag abstract --remove "2,3,5,70-84"
  python3 scripts/curate_material.py --tag abstract --keep-only "1,4,7-20"
"""
import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEME_DIR = ROOT / "assets" / "memes"
MANIFEST = MEME_DIR / "manifest.json"
IMG_EXT = (".jpg", ".jpeg", ".png", ".gif")


def parse_ranges(s):
    out = set()
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def main():
    ap = argparse.ArgumentParser(description="按编号剔除素材并重建 manifest")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--remove", default="", help="要删的编号，如 2,3,5,70-84")
    ap.add_argument("--keep-only", default="", help="只保留这些编号，其余删")
    args = ap.parse_args()

    d = MEME_DIR / args.tag
    files = sorted(f for f in os.listdir(d)
                   if f.lower().endswith(IMG_EXT) and not f.startswith("_"))

    if args.keep_only:
        keep = parse_ranges(args.keep_only)
        drop = {i for i in range(1, len(files) + 1) if i not in keep}
    else:
        drop = parse_ranges(args.remove)

    removed = 0
    for i, f in enumerate(files, 1):
        if i in drop:
            os.remove(d / f)
            removed += 1

    m = [x for x in json.loads(MANIFEST.read_text()) if x.get("tag") != args.tag]
    left = sorted(f for f in os.listdir(d)
                  if f.lower().endswith(IMG_EXT) and not f.startswith("_"))
    for f in left:
        m.append({"file": f"{args.tag}/{f}", "tag": args.tag,
                  "source": "curated", "license": "unknown - personal use"})
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2))
    print(f"✅ tag={args.tag} 删除 {removed}，保留 {len(left)} 张，manifest 已重建")


if __name__ == "__main__":
    main()
