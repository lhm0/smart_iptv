# smart_iptv

Automatisch erzeugter ZDF-HLS-Master für Smart IPTV: nur **TV Ton**, keine
Audiodeskription als Alternative, keine Untertitel und höchste verfügbare
Video-Rendition.

## Einrichtung

1. Dieses Repository nach GitHub pushen. Der Workflow liegt unter
   `.github/workflows/pages.yml` und startet nach jedem Push auf `main`.
2. GitHub: **Settings → Pages**.
3. **Build and deployment → Source → GitHub Actions** auswählen.
4. Unter **Actions** den Workflow **Build and publish ZDF TV Ton stream**
   prüfen bzw. mit **Run workflow** starten.
5. Nach erfolgreichem Lauf:
   `https://lhm0.github.io/smart_iptv/zdf-tvton.m3u8`

Der Workflow läuft zusätzlich ungefähr stündlich und bei jedem Push.

## Smart-IPTV-Senderliste

Den bisherigen ZDF-Eintrag ersetzen durch:

```m3u
#EXTINF:-1 tvg-name="ZDF" group-title="Öffentlich-rechtlich",ZDF
https://lhm0.github.io/smart_iptv/zdf-tvton.m3u8
```

Danach die Sender-M3U auf der Smart-IPTV-Uploadseite erneut hochladen und die
App am Fernseher neu starten.

## Funktionsweise

`generate_zdf.py` lädt den aktuellen ZDF-Master, sucht `TV Ton`, wählt die
höchste Video-Rendition, macht alle URLs absolut und erzeugt einen neuen
HLS-Master mit genau dieser einen Audiospur. Untertitel werden nicht übernommen.

Die erzeugte Datei wird als GitHub-Pages-Artefakt veröffentlicht; wechselnde
ZDF-Unterpfade/Hashes werden daher bei jedem Lauf neu ermittelt. Fehlt der
Audiostream `TV Ton` im aktuellen Master, schlägt die Generierung fehl, statt
eine andere Audiospur zu veröffentlichen.
