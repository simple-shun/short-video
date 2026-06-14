#!/usr/bin/env python3
"""给素材目录生成带编号的接触表(contact sheet)，供人工/Agent 审核质量。
编号与目录内文件排序一一对应，便于按号删除。

用法：
  python3 scripts/contact_sheet.py assets/memes/abstract            # 全部
  python3 scripts/contact_sheet.py assets/memes/abstract 0 45       # 只看 1~45
  # 输出 /tmp/contact_<tag>.png，再用 Read 查看
"""
import os
import sys
from PIL import Image, ImageDraw

IMG_EXT = (".jpg", ".jpeg", ".png", ".gif")


def listing(d):
    return sorted(f for f in os.listdir(d)
                  if f.lower().endswith(IMG_EXT) and not f.startswith("_"))


def build(d, lo=0, hi=None, cols=7, cell=210, out=None):
    files = listing(d)
    hi = hi if hi is not None else len(files)
    sub = files[lo:hi]
    rows = (len(sub) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell), (35, 35, 35))
    dr = ImageDraw.Draw(sheet)
    for i, f in enumerate(sub):
        try:
            im = Image.open(os.path.join(d, f)).convert("RGB")
        except Exception:
            continue
        im.thumbnail((cell - 8, cell - 30))
        x, y = (i % cols) * cell, (i // cols) * cell
        sheet.paste(im, (x + 4, y + 4))
        dr.rectangle([x, y + cell - 26, x + 44, y + cell], fill=(0, 0, 0))
        dr.text((x + 5, y + cell - 22), f"{lo + i + 1}", fill=(255, 220, 0))
    tag = os.path.basename(d.rstrip("/"))
    out = out or f"/tmp/contact_{tag}.png"
    sheet.save(out)
    print(f"{len(sub)} 张 → {out}  (编号 {lo+1}~{lo+len(sub)})")
    return out


if __name__ == "__main__":
    d = sys.argv[1]
    lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    hi = int(sys.argv[3]) if len(sys.argv) > 3 else None
    build(d, lo, hi)
