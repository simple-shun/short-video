#!/usr/bin/env python3
"""Download funny meme GIFs from the public Tenor v1 API into assets/memes/<emotion>/.

Tenor's legacy v1 endpoint accepts the well-known anonymous key LIVDSRZULELA and
returns direct media.tenor.com GIF URLs. No personal key required.
"""
import json
import os
import subprocess
import time
import urllib.parse

BASE = "/Users/simple/works/ai/short-video/assets/memes"
KEY = "LIVDSRZULELA"
ENDPOINT = "https://g.tenor.com/v1/search"

# emotion -> list of (subject_slug, query, count)
PLAN = {
    "shock": [
        ("guapi", "shocked old man meme", 3),
        ("heiren_wenhao", "black guy question marks meme", 2),
        ("mao", "surprised cat shocked", 3),
    ],
    "laugh": [
        ("wuzui_mao", "cat covering mouth laughing", 3),
        ("doge_haha", "doge laughing meme", 2),
        ("xiaodiao", "laughing crying weasel meme", 2),
    ],
    "speechless": [
        ("fanbaiyan_mao", "cat eye roll meme", 3),
        ("wuyu_gou", "speechless dog meme", 3),
    ],
    "confused": [
        ("naotou_xiongmao", "confused panda scratching head", 3),
        ("wenhao", "confused question mark meme", 3),
    ],
    "doge": [
        ("doge", "doge meme", 3),
        ("doge_cheems", "cheems doge meme", 3),
    ],
    "surprised": [
        ("surprised", "surprised pikachu meme", 3),
        ("jingya_mao", "surprised cat meme", 3),
    ],
    "dizzy": [
        ("touyun", "dizzy spinning eyes meme", 3),
        ("xuanyun", "dizzy cartoon stars meme", 3),
    ],
}


def fetch_urls(query, want):
    url = f"{ENDPOINT}?{urllib.parse.urlencode({'q': query, 'key': KEY, 'limit': want + 6, 'media_filter': 'minimal', 'contentfilter': 'medium'})}"
    try:
        out = subprocess.run(["curl", "-s", "--max-time", "20", url],
                             capture_output=True, text=True, timeout=30).stdout
        data = json.loads(out)
    except Exception as e:
        print(f"  ! query failed ({query}): {e}")
        return []
    urls = []
    for r in data.get("results", []):
        media = r.get("media", [{}])[0]
        for k in ("gif", "mediumgif", "tinygif"):
            if media.get(k, {}).get("url"):
                urls.append(media[k]["url"])
                break
    return urls


def download(url, dest):
    try:
        subprocess.run(["curl", "-sL", "--max-time", "30", "-o", dest, url],
                       capture_output=True, timeout=40)
    except Exception:
        return False
    # validate: real GIF starts with GIF8 and has reasonable size
    if not os.path.exists(dest) or os.path.getsize(dest) < 2000:
        if os.path.exists(dest):
            os.remove(dest)
        return False
    with open(dest, "rb") as f:
        if f.read(4) != b"GIF8":
            os.remove(dest)
            return False
    return True


def main():
    total = 0
    for emotion, items in PLAN.items():
        d = os.path.join(BASE, emotion)
        os.makedirs(d, exist_ok=True)
        for subject, query, count in items:
            urls = fetch_urls(query, count)
            got = 0
            idx = 1
            for url in urls:
                if got >= count:
                    break
                dest = os.path.join(d, f"{subject}_{emotion}_{idx}.gif")
                while os.path.exists(dest):
                    idx += 1
                    dest = os.path.join(d, f"{subject}_{emotion}_{idx}.gif")
                if download(url, dest):
                    print(f"  + {os.path.relpath(dest, BASE)} ({os.path.getsize(dest)//1024}KB)")
                    got += 1
                    idx += 1
                    total += 1
                time.sleep(0.3)
            print(f"[{emotion}] {subject} <- '{query}': got {got}/{count}")
    print(f"\nTOTAL new files: {total}")


if __name__ == "__main__":
    main()
