#!/usr/bin/env python3
import re, urllib.request
from pathlib import Path
from urllib.parse import urljoin

SOURCE="https://zdf-hls-15.akamaized.net/hls/live/2016498/de/veryhigh/master.m3u8"
OUT=Path("public/zdf-tvton.m3u8")

def fetch(u):
    req=urllib.request.Request(u,headers={
        "User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer":"https://www.zdf.de/",
        "Accept":"application/vnd.apple.mpegurl,application/x-mpegURL,*/*",
    })
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.read().decode("utf-8-sig")

def attrs(line):
    d={}
    for p in re.findall(r'(?:[^,"]|"[^"]*")+',line.split(":",1)[1]):
        if "=" in p:
            k,v=p.split("=",1); d[k.strip()]=v.strip().strip('"')
    return d

def q(s): return '"'+s.replace("\\","\\\\").replace('"','\\"')+'"'

def main():
    lines=[x.strip() for x in fetch(SOURCE).splitlines() if x.strip()]
    aud=[]
    for line in lines:
        if line.startswith("#EXT-X-MEDIA:"):
            a=attrs(line)
            if a.get("TYPE")=="AUDIO" and a.get("URI"): aud.append(a)

    audio=next((a for a in aud if a.get("NAME","").casefold()=="tv ton"),None)
    if audio is None: raise RuntimeError("Normaler ZDF-'TV Ton' nicht gefunden.")
    audio_url=urljoin(SOURCE,audio["URI"])

    variants=[]; i=0
    while i<len(lines):
        if lines[i].startswith("#EXT-X-STREAM-INF:"):
            a=attrs(lines[i]); j=i+1
            while j<len(lines) and lines[j].startswith("#"): j+=1
            if j>=len(lines): raise RuntimeError("Video-URI fehlt.")
            variants.append((a,urljoin(SOURCE,lines[j]))); i=j
        i+=1
    if not variants: raise RuntimeError("Keine Video-Rendition gefunden.")

    def score(item):
        a=item[0]
        try: w,h=map(int,a.get("RESOLUTION","0x0").lower().split("x"))
        except: w=h=0
        try: fps=float(a.get("FRAME-RATE","0"))
        except: fps=0
        try: bw=int(a.get("AVERAGE-BANDWIDTH",a.get("BANDWIDTH","0")))
        except: bw=0
        return (w*h,fps,bw)

    video,video_url=max(variants,key=score)
    mf=[
      '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="tvton",NAME="TV Ton",LANGUAGE='+q(audio.get("LANGUAGE","deu"))+
      ',DEFAULT=YES,AUTOSELECT=YES,URI='+q(audio_url)
    ]
    f=[]
    for k in ("BANDWIDTH","AVERAGE-BANDWIDTH","CODECS","RESOLUTION","FRAME-RATE","VIDEO-RANGE"):
        if k in video: f.append(k+"="+(q(video[k]) if k=="CODECS" else video[k]))
    f.append('AUDIO="tvton"')
    out="\n".join(["#EXTM3U","#EXT-X-VERSION:6",*mf,"#EXT-X-STREAM-INF:"+",".join(f),video_url,""])
    OUT.write_text(out,encoding="utf-8",newline="\n")
    print("Audio:",audio.get("NAME"),audio_url)
    print("Video:",video.get("RESOLUTION"),video.get("FRAME-RATE"),video_url)
    print("Untertitel: aus")

if __name__=="__main__": main()
