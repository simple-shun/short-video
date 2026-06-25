#!/usr/bin/env python3
"""
fafeng（猥琐发疯音）可复用声音源
配方：edge-tts zh-CN-YunxiaNeural (+30% rate / +30Hz pitch) → rubberband 降3半音(共振峰跟随下移=油腻拉音) → 去首尾静音
来源：复刻参考视频 73f0db6f... 的音色，实测目标 F0 中位~308Hz；本配方实测~314Hz，Gemini 比对≈八成像。
参考样本：assets/voice_ref/weisuo_fafeng_ref.wav
用法：python3 scripts/fafeng_tts.py "文案文字" out.wav
依赖：edge-tts、rubberband、ffmpeg
"""
import sys, subprocess, tempfile, os

VOICE="zh-CN-YunxiaNeural"; RATE="+30%"; PITCH="+30Hz"; SEMITONES="-3"

def synth(text, out_wav):
    td=tempfile.mkdtemp()
    raw=os.path.join(td,"raw.mp3"); pre=os.path.join(td,"pre.wav"); rb=os.path.join(td,"rb.wav")
    # edge-tts 偶发首调空响应，重试
    for _ in range(4):
        subprocess.run(["edge-tts","--voice",VOICE,"--rate",RATE,"--pitch",PITCH,
                        "--text",text,"--write-media",raw],
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if os.path.exists(raw) and os.path.getsize(raw)>2000: break
    subprocess.run(["ffmpeg","-y","-i",raw,"-ar","44100","-ac","1",pre],
                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(["rubberband","--pitch",SEMITONES,"-q",pre,rb],
                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    # 去首尾静音（放满连读）
    sr="silenceremove=start_periods=1:start_silence=0.03:start_threshold=-45dB:detection=peak"
    subprocess.run(["ffmpeg","-y","-i",rb,"-af",f"{sr},areverse,{sr},areverse",out_wav],
                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return out_wav

if __name__=="__main__":
    if len(sys.argv)<3:
        print("用法: python3 scripts/fafeng_tts.py \"文案\" out.wav"); sys.exit(1)
    synth(sys.argv[1], sys.argv[2])
    print("OK ->", sys.argv[2])
