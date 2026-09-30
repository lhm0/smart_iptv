#!/usr/bin/env python3
import os
import re
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlparse

CHANNELS = [
    ("ZDF", "zdf-tvton.m3u8", "https://zdf-hls-15.akamaized.net/hls/live/2016498/de/veryhigh/master.m3u8", "TV Ton"),
    ("Das Erste", "das-erste-deutsch.m3u8", "https://daserste-live.ard-mcdn.de/daserste/live/hls/de/master.m3u8", "Deutsch"),
    ("NDR Fernsehen Hamburg", "ndr-hamburg.m3u8", "https://mcdn.ndr.de/ndr/hls/ndr_fs/ndr_hh/master.m3u8", "Deutsch"),
    ("SWR Baden-Württemberg", "swr-bw-deutsch.m3u8", "https://swrbwd-hls.akamaized.net/hls/live/2018672/swrbwd/master.m3u8", "Deutsch"),
    ("hr-fernsehen", "hr-deutsch.m3u8", "https://hr-live.ard-mcdn.de/hr/live/hls/de/master.m3u8", "Deutsch"),
    ("BR Fernsehen Süd", "br-sued-deutsch.m3u8", "https://mcdn.br.de/br/fs/bfs_sued/hls/de/master.m3u8", "Deutsch"),
    ("WDR Fernsehen", "wdr-deutsch.m3u8", "https://wdrfs247.akamaized.net/hls/live/681509/wdr_msl4_fs247/master.m3u8", "Deutsch"),
    ("3sat", "3sat-tvton.m3u8", "https://zdf-hls-18.akamaized.net/hls/live/2016501/dach/veryhigh/master.m3u8", "TV Ton"),
    ("ZDFinfo", "zdfinfo-tvton.m3u8", "https://zdf-hls-17.akamaized.net/hls/live/2016500/de/veryhigh/master.m3u8", "TV Ton"),
    ("ZDFneo", "zdfneo-tvton.m3u8", "https://zdf-hls-16.akamaized.net/hls/live/2016499/de/veryhigh/master.m3u8", "TV Ton"),
    ("ONE", "one-deutsch.m3u8", "https://mcdn-one.ard.de/ardone/hls/master.m3u8", "Deutsch"),
]
PINNED_VARIANTS = {
    "ndr-hamburg.m3u8": ("1280x720", 50.0),
}

OUTPUT_DIR = Path(os.environ.get("SMART_IPTV_OUTPUT_DIR", Path(__file__).resolve().parent / "public"))
QUOTED_ATTRIBUTES = {"URI", "GROUP-ID", "NAME", "LANGUAGE", "CHARACTERISTICS", "CODECS", "CHANNELS", "AUDIO"}


def fetch(url):
    host = urlparse(url).hostname or ""
    referer = "https://www.zdf.de/" if host.startswith("zdf-hls-") else "https://www.ardmediathek.de/"
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": referer,
        "Accept": "application/vnd.apple.mpegurl,application/x-mpegURL,*/*",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8-sig")


def parse_attributes(line):
    result = {}
    for part in re.findall(r'(?:[^,"]|"[^"]*")+', line.split(":", 1)[1]):
        if "=" in part:
            key, value = part.split("=", 1)
            result[key.strip()] = value.strip().strip('"')
    return result


def serialize_attributes(attributes):
    parts = []
    for key, value in attributes.items():
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        if key in QUOTED_ATTRIBUTES or "," in value:
            parts.append(f'{key}="{escaped}"')
        else:
            parts.append(f"{key}={escaped}")
    return ",".join(parts)


def rendition_score(attributes):
    try:
        width, height = map(int, attributes.get("RESOLUTION", "0x0").lower().split("x"))
    except ValueError:
        width = height = 0
    try:
        frame_rate = float(attributes.get("FRAME-RATE", "0"))
    except ValueError:
        frame_rate = 0
    try:
        bandwidth = int(attributes.get("AVERAGE-BANDWIDTH", attributes.get("BANDWIDTH", "0")))
    except ValueError:
        bandwidth = 0
    return width * height, frame_rate, bandwidth


def build_playlist(source_url, wanted_audio, preferred_resolution=None, preferred_frame_rate=None):
    lines = [line.strip() for line in fetch(source_url).splitlines() if line.strip()]
    audio_tracks = [
        parse_attributes(line)
        for line in lines
        if line.startswith("#EXT-X-MEDIA:")
        and parse_attributes(line).get("TYPE") == "AUDIO"
        and parse_attributes(line).get("URI")
    ]

    variants = []
    for index, line in enumerate(lines):
        if not line.startswith("#EXT-X-STREAM-INF:"):
            continue
        attributes = parse_attributes(line)
        uri_index = index + 1
        while uri_index < len(lines) and lines[uri_index].startswith("#"):
            uri_index += 1
        if uri_index < len(lines):
            variants.append((attributes, urljoin(source_url, lines[uri_index])))
    if not variants:
        raise RuntimeError("Keine Video-Rendition gefunden.")

    if preferred_resolution is not None:
        matching_variants = []
        for variant in variants:
            attributes = variant[0]
            try:
                frame_rate = float(attributes.get("FRAME-RATE", "0"))
            except ValueError:
                continue
            if (
                attributes.get("RESOLUTION") == preferred_resolution
                and preferred_frame_rate is not None
                and abs(frame_rate - preferred_frame_rate) < 0.001
            ):
                matching_variants.append(variant)
        if not matching_variants:
            raise RuntimeError(
                f"Angeforderte Video-Rendition {preferred_resolution} bei "
                f"{preferred_frame_rate:.3f} fps fehlt; es wird keine Ersatzqualität gewählt."
            )
        video, video_url = max(matching_variants, key=lambda item: rendition_score(item[0]))
    else:
        video, video_url = max(variants, key=lambda item: rendition_score(item[0]))
    audio_group = video.get("AUDIO")
    if not audio_group:
        raise RuntimeError("Die ausgewählte Video-Rendition verweist auf keine separate Audiospur.")
    audio = next((
        track for track in audio_tracks
        if track.get("GROUP-ID") == audio_group
        and track.get("NAME", "").casefold() == wanted_audio.casefold()
    ), None)
    if audio is None:
        raise RuntimeError(f"Audiospur {wanted_audio!r} in Gruppe {audio_group!r} nicht gefunden.")

    audio["URI"] = urljoin(source_url, audio["URI"])
    audio["DEFAULT"] = "YES"
    audio["AUTOSELECT"] = "YES"
    video["AUDIO"] = audio_group
    video.pop("SUBTITLES", None)
    video.pop("CLOSED-CAPTIONS", None)

    version = next((line.split(":", 1)[1] for line in lines if line.startswith("#EXT-X-VERSION:")), "6")
    output = ["#EXTM3U", f"#EXT-X-VERSION:{version}"]
    if "#EXT-X-INDEPENDENT-SEGMENTS" in lines:
        output.append("#EXT-X-INDEPENDENT-SEGMENTS")
    output.extend((
        "#EXT-X-MEDIA:" + serialize_attributes(audio),
        "#EXT-X-STREAM-INF:" + serialize_attributes(video),
        video_url,
        "",
    ))
    return "\n".join(output), audio, video


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    failures = []
    for name, filename, source_url, wanted_audio in CHANNELS:
        try:
            preferred_resolution, preferred_frame_rate = PINNED_VARIANTS.get(filename, (None, None))
            playlist, audio, video = build_playlist(
                source_url,
                wanted_audio,
                preferred_resolution,
                preferred_frame_rate,
            )
            (OUTPUT_DIR / filename).write_text(playlist, encoding="utf-8", newline="\n")
            print(f"{name}: Audio {audio['NAME']} | Video {video.get('RESOLUTION', 'unbekannt')}")
        except Exception as error:
            failures.append((name, error))
            print(f"{name}: FEHLER: {error}")
    print("Untertitel: in allen erzeugten Playlists aus")
    if failures:
        raise SystemExit(f"{len(failures)} von {len(CHANNELS)} Sendern konnten nicht aktualisiert werden.")


if __name__ == "__main__":
    main()
