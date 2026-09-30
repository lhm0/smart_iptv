# smart_iptv

Der Raspberry Pi erzeugt stündlich aktuelle HLS-Master-Playlists mit jeweils
nur dem normalen deutschen Ton und ohne Untertitel. GitHub Actions veröffentlicht
zusätzlich die NDR-Testplaylist unter einer stabilen öffentlichen URL.

Die ausführliche Anleitung zur Einrichtung von Smart IPTV auf dem LG, zum
Raspberry Pi, Generator, nginx, Timer und zur Fehlerbehebung steht in
[SmartIPTV_readme.md](SmartIPTV_readme.md).

## Gefilterte Sender

Der Generator liest die aktuellen offiziellen Sender-Master dynamisch ein und
schreibt die Dateien nach `/srv/smart-iptv/public/` auf dem Pi:

| Sender | Ausgewählte Tonspur | Datei |
| --- | --- | --- |
| Das Erste | Deutsch | `das-erste-deutsch.m3u8` |
| ZDF | TV Ton | `zdf-tvton.m3u8` |
| NDR Hamburg | Deutsch, fest 1280x720p50 | `ndr-hamburg.m3u8` |
| SWR Baden-Württemberg | Deutsch | `swr-bw-deutsch.m3u8` |
| hr-fernsehen | Deutsch | `hr-deutsch.m3u8` |
| BR Fernsehen Süd | Deutsch | `br-sued-deutsch.m3u8` |
| WDR Fernsehen | Deutsch | `wdr-deutsch.m3u8` |
| 3sat | TV Ton | `3sat-tvton.m3u8` |
| ZDFinfo | TV Ton | `zdfinfo-tvton.m3u8` |
| ZDFneo | TV Ton | `zdfneo-tvton.m3u8` |
| ONE | Deutsch | `one-deutsch.m3u8` |

ARTE bleibt direkt in der Senderliste, da der aktuelle Master keine separaten
Audio- oder Untertitelgruppen deklariert.

Die NDR-Datei enthält genau eine Video-Rendition: 1280x720 bei 50 fps. Audio
bleibt als separate, synchronisierte HLS-Rendition „Deutsch“ zugeordnet;
Audiodeskription und Untertitel werden nicht angeboten. Die veröffentlichte
Adresse lautet <https://lhm0.github.io/smart_iptv/ndr-hamburg.m3u8>. Der Pi
erzeugt dieselbe Datei lokal unter
`http://192.168.0.131:8080/ndr-hamburg.m3u8`.

Der Generator prüft bei NDR auch, dass Video- und Audio-Media-Playlist
erreichbare HLS-Manifeste sind. Bei Fehlern wird die vorherige gültige Datei
nicht überschrieben; GitHub Pages behält dann den zuletzt eingecheckten Stand.
Der GitHub-Runner erhält eine abweichende NDR-CDN-URL, die im Heimnetz 404
lieferte. Deshalb überspringt der Pages-Workflow NDR. Die stündliche Pi-Datei
wird automatisch dynamisch aktualisiert; zum Aktualisieren der öffentlichen
Pages-Kopie nach einem Pfadwechsel die geprüfte Datei vom Pi kopieren und
committen:

```sh
scp ludwin@192.168.0.131:/srv/smart-iptv/public/ndr-hamburg.m3u8 public/ndr-hamburg.m3u8
git add public/ndr-hamburg.m3u8
git commit -m "Refresh NDR Hamburg playlist"
git push
```

## Generator auf dem Pi aktualisieren

Von diesem Verzeichnis auf dem Mac ausführen:

```sh
scp generate_zdf.py ludwin@192.168.0.131:/srv/smart-iptv/generate_zdf.py
ssh ludwin@192.168.0.131 'python3 /srv/smart-iptv/generate_zdf.py'
```

Der zweite Befehl erzeugt die Playlists sofort. Der bereits eingerichtete
`smart-iptv.timer` ruft denselben Generator danach stündlich und nach einem
Neustart des Pi wieder auf. Status und nächste Laufzeit:

```sh
systemctl list-timers smart-iptv.timer
journalctl -u smart-iptv.service
```

## Smart IPTV

Die Senderliste `smartiptv.m3u` verwendet die lokale Pi-Adresse
`192.168.0.131:8080`. Der Router sollte dem Pi diese Adresse dauerhaft per
DHCP-Reservierung zuweisen. Nach Änderungen an der Senderliste die aktualisierte
M3U-Datei in Smart IPTV erneut laden.