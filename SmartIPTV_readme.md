# Smart IPTV auf dem LG OLED55C37LA

Diese Anleitung beschreibt die Einrichtung von Smart IPTV (SIPTV) auf dem LG
OLED55C37LA und den Betrieb der Senderliste mit einem Raspberry Pi 3. Der Pi
erzeugt regelmäßig HLS-Master-Playlists, in denen jeweils nur die gewollte
Audiospur ausgewählt ist. Er stellt diese Dateien im Heimnetz bereit.

## Überblick

- **Fernseher:** LG OLED55C37LA mit webOS
- **Player:** Smart IPTV aus dem LG App Store
- **Playlist-Verwaltung:** M3U-Upload über <https://siptv.app/mylist/>
- **Playlist-Generator und Webserver:** Raspberry Pi 3 mit Raspberry Pi OS Lite
	(64-bit), Python 3 und nginx
- **Lokaler Webserver-Port:** TCP 8080
- **Zeitgesteuerte Aktualisierung:** systemd-Timer, stündlich und nach
	verpassten Läufen persistent
- **GitHub:** Für den laufenden lokalen Betrieb nicht erforderlich

Der Pi liefert nur die kleinen Playlist-Dateien aus. Video und Ton werden
weiterhin direkt von den jeweiligen Sender-CDNs über das Internet geladen. Der
Fernseher muss deshalb im selben Heimnetz wie der Pi sein; am Router ist keine
Portweiterleitung ins Internet einzurichten.

## Warum gefilterte Playlists nötig sind

Einige Sender-Master bieten mehrere Tonspuren an, beispielsweise „Deutsch“,
„Klare Sprache“, „Originalton“ und „Audiodeskription“. Manche Player wählen
unerwartet eine alternative Spur, obwohl im Master eine Standardspur markiert
ist. Außerdem deklarieren viele Master Untertitelspuren.

Der Generator lädt den aktuellen offiziellen Sender-Master, wählt die höchste
angebotene Video-Rendition und ermittelt die gewünschte Audiospur aus genau der
Audio-Gruppe, auf die diese Video-Rendition verweist. Er erzeugt einen neuen
Master mit dieser einen Audiospur und ohne Untertitel- oder Closed-Caption-
Verweise. URLs für Video und Ton werden absolut ausgegeben, sodass wechselnde
relative Unterpfade der Sender-Master übernommen werden.

Ausgewählte Spuren:

| Sender | Ausgewählte Tonspur | Generierte Datei |
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

Der aktuell geprüfte ARTE-Master deklariert keine separaten Audio- oder
Untertitelgruppen. ARTE bleibt deshalb direkt in der Senderliste und wird nicht
durch den Generator umgeschrieben.

Für NDR Hamburg ist die Ausgabe auf eine einzelne Video-Rendition von
1280x720 bei 50 fps festgelegt. Das ist ein Stabilitätstest gegen mögliches
Buffering beim adaptiven Rendition-Wechsel. Die Video-Playlist enthält MPEG-TS;
der normale deutsche Ton bleibt als separate AAC-HLS-Rendition synchron
zugeordnet. Ein direkter Link auf die Video-Media-Playlist wäre ungeeignet, weil
dadurch die separate Audiospur verloren gehen könnte. Die veröffentlichte
Playlist ist unter
<https://lhm0.github.io/smart_iptv/ndr-hamburg.m3u8> erreichbar; lokal auf dem
Pi lautet die URL
`http://192.168.0.131:8080/ndr-hamburg.m3u8`.

## Raspberry Pi einrichten

### Betriebssystem und Netzwerk

Raspberry Pi OS Lite (64-bit) ist für den Pi 3 ausreichend; eine grafische
Oberfläche wird nicht benötigt. Bei der Einrichtung SSH und einen eigenen
Benutzer aktivieren. Ethernet ist für einen stationären Pi vorzuziehen.

Im Router eine DHCP-Reservierung für den Pi einrichten. Die unten verwendete
Adresse `192.168.0.131` ist die aktuell konfigurierte Pi-Adresse und muss durch
die reservierte Adresse ersetzt werden, falls sie bei dir abweicht. Die
Reservierung sorgt dafür, dass die Playlist-URLs in der Smart-IPTV-Liste stabil
bleiben.

Auf dem Pi installieren:

```sh
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y python3 nginx
sudo timedatectl set-timezone Europe/Berlin
sudo mkdir -p /srv/smart-iptv/public
sudo chown -R "$USER":"$USER" /srv/smart-iptv
```

### Generator kopieren und testen

Die folgenden Befehle werden auf dem Mac im Repository-Verzeichnis ausgeführt.
`ludwin` ist der eingerichtete Pi-Benutzer; bei einem anderen Benutzernamen
entsprechend ersetzen:

```sh
scp generate_zdf.py ludwin@192.168.0.131:/srv/smart-iptv/generate_zdf.py
ssh ludwin@192.168.0.131 'python3 /srv/smart-iptv/generate_zdf.py'
```

Der Generator schreibt elf Dateien nach `/srv/smart-iptv/public/`. Er gibt pro
Sender die gewählte Tonspur und Auflösung aus. Wenn eine Quelle oder die
gewünschte Audiospur fehlt, wird der Fehler gemeldet und der Lauf endet mit
nicht-null Status. Für den betroffenen Sender bleibt die zuletzt erfolgreich
erzeugte Datei erhalten; andere erfolgreich gelesene Sender können trotzdem
aktualisiert worden sein.

### nginx einrichten

Auf dem Pi die Konfiguration anlegen:

```sh
sudo tee /etc/nginx/sites-available/smart-iptv >/dev/null <<'EOF'
server {
		listen 8080;
		listen [::]:8080;
		server_name _;
		root /srv/smart-iptv/public;

		location = /zdf-tvton.m3u8 {
				default_type application/vnd.apple.mpegurl;
				add_header Cache-Control "no-cache";
				try_files $uri =404;
		}

		location / {
				default_type application/vnd.apple.mpegurl;
				add_header Cache-Control "no-cache";
				try_files $uri =404;
		}
}
EOF

sudo ln -sf /etc/nginx/sites-available/smart-iptv /etc/nginx/sites-enabled/smart-iptv
sudo nginx -t
sudo systemctl reload nginx
```

Die Konfiguration stellt ausschließlich Dateien aus dem Playlist-Verzeichnis
auf Port 8080 bereit. Sie öffnet den Dienst nicht automatisch im Internet.

### Stündliche Aktualisierung mit systemd

Auf dem Pi den One-shot-Dienst und den Timer einrichten. Im Beispiel heißt der
Pi-Benutzer `ludwin`; bei einem abweichenden Benutzer sowohl `User=` als auch
den Projektpfad prüfen und anpassen:

```sh
sudo tee /etc/systemd/system/smart-iptv.service >/dev/null <<'EOF'
[Unit]
Description=Generate filtered Smart IPTV playlists
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=ludwin
WorkingDirectory=/srv/smart-iptv
ExecStart=/usr/bin/python3 /srv/smart-iptv/generate_zdf.py
EOF

sudo tee /etc/systemd/system/smart-iptv.timer >/dev/null <<'EOF'
[Unit]
Description=Update Smart IPTV playlists hourly

[Timer]
OnCalendar=hourly
Persistent=true
RandomizedDelaySec=5m
Unit=smart-iptv.service

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now smart-iptv.timer
sudo systemctl start smart-iptv.service
```

Der Timer startet beim Booten automatisch. `Persistent=true` lässt einen
verpassten Lauf nachholen, wenn der Pi während eines geplanten Laufs aus war.
Der Dienst ist ein One-shot-Dienst: Nach erfolgreicher Generierung ist
`inactive (dead)` bei `systemctl status` normal; entscheidend ist
`status=0/SUCCESS` im letzten Lauf. Kann der Pi eine Senderquelle vorübergehend
nicht erreichen, bleibt dessen letzte gültige Playlist auf der Platte und der
nächste stündliche Lauf versucht es erneut.

### Funktion prüfen

Auf dem Pi:

```sh
systemctl is-enabled smart-iptv.timer
systemctl list-timers smart-iptv.timer --no-pager
systemctl status smart-iptv.service --no-pager
curl -i http://127.0.0.1:8080/das-erste-deutsch.m3u8
```

Auf dem Mac oder einem anderen Gerät im selben Heimnetz die Adresse des Pi
verwenden:

```sh
curl -i http://192.168.0.131:8080/das-erste-deutsch.m3u8
```

Erwartet werden HTTP `200 OK`, der MIME-Type
`application/vnd.apple.mpegurl`, `#EXTM3U` und genau eine
`#EXT-X-MEDIA:TYPE=AUDIO`-Deklaration. In der gefilterten Datei sollen keine
`SUBTITLES`- oder `CLOSED-CAPTIONS`-Attribute stehen.

## Smart IPTV auf dem LG einrichten

### App und Gerätekennung

1. Smart IPTV aus dem LG App Store installieren und starten.
2. Die in der App angezeigte Gerätekennung notieren. Sie wird für den Upload
	 und gegebenenfalls die App-Aktivierung benötigt.
3. Die Kennung wie ein persönliches Geräte-Identifikationsmerkmal behandeln
	 und nicht in öffentlich zugängliche Dokumentation oder Chats kopieren.

### Senderliste hochladen

Die Datei `smartiptv.m3u` enthält die aktuelle Reihenfolge und die lokalen
Playlist-URLs. Öffne <https://siptv.app/mylist/> im Browser:

1. Gerätekennung des Fernsehers eingeben.
2. Die aktuelle Datei `smartiptv.m3u` auswählen und hochladen.
3. EPG-Sprache auf Deutsch stellen, sofern die Auswahl angeboten wird.
4. Übertragung bestätigen.
5. Smart IPTV am Fernseher vollständig beenden und neu starten.

Nach jeder Änderung an der Senderliste die aktualisierte M3U-Datei erneut
hochladen. Die Playlist-Dateien auf dem Pi selbst müssen nicht hochgeladen
werden; sie werden von Smart IPTV über die lokalen URLs abgerufen.

Die aktuelle Senderliste zeigt auf:

```m3u
#EXTM3U
#EXTINF:-1 tvg-name="Das Erste" group-title="Öffentlich-rechtlich",Das Erste
http://192.168.0.131:8080/das-erste-deutsch.m3u8
#EXTINF:-1 tvg-name="ZDF" group-title="Öffentlich-rechtlich",ZDF
http://192.168.0.131:8080/zdf-tvton.m3u8
#EXTINF:-1 tvg-name="NDR Hamburg" group-title="Öffentlich-rechtlich",NDR Hamburg
https://lhm0.github.io/smart_iptv/ndr-hamburg.m3u8
#EXTINF:-1 tvg-name="SWR Baden-Württemberg" group-title="Öffentlich-rechtlich",SWR Baden-Württemberg
http://192.168.0.131:8080/swr-bw-deutsch.m3u8
#EXTINF:-1 tvg-name="hr-fernsehen" group-title="Öffentlich-rechtlich",hr-fernsehen
http://192.168.0.131:8080/hr-deutsch.m3u8
#EXTINF:-1 tvg-name="BR Fernsehen Süd" group-title="Öffentlich-rechtlich",BR Fernsehen Süd
http://192.168.0.131:8080/br-sued-deutsch.m3u8
#EXTINF:-1 tvg-name="WDR Fernsehen" group-title="Öffentlich-rechtlich",WDR Fernsehen
http://192.168.0.131:8080/wdr-deutsch.m3u8
#EXTINF:-1 tvg-name="3sat" group-title="Öffentlich-rechtlich",3sat
http://192.168.0.131:8080/3sat-tvton.m3u8
#EXTINF:-1 tvg-name="arte" group-title="Öffentlich-rechtlich",arte
https://artesimulcast.akamaized.net/hls/live/2030993/artelive_de/index.m3u8
#EXTINF:-1 tvg-name="ZDFinfo" group-title="Öffentlich-rechtlich",ZDFinfo
http://192.168.0.131:8080/zdfinfo-tvton.m3u8
#EXTINF:-1 tvg-name="ZDFneo" group-title="Öffentlich-rechtlich",ZDFneo
http://192.168.0.131:8080/zdfneo-tvton.m3u8
#EXTINF:-1 tvg-name="ONE" group-title="Öffentlich-rechtlich",ONE
http://192.168.0.131:8080/one-deutsch.m3u8
```

Ersetze `192.168.0.131` in allen lokalen URLs, falls der Pi eine andere
reservierte IPv4-Adresse hat.

### Lizenz und EPG

Die Smart-IPTV-Testphase und eine mögliche dauerhafte App-Lizenz sind
unabhängig vom Senderzugriff. Offizielle Informationen stehen unter
<https://siptv.app/activation/>. Für Upload und Aktivierung wird die in der App
angezeigte Gerätekennung verwendet.

Die EPG-Sprache ist keine Audioeinstellung der M3U. Beim Playlist-Upload Deutsch
auswählen, falls die Option angezeigt wird. Das EPG (Programminformationen) und
die Auswahl der HLS-Audiospur sind voneinander unabhängig.

## Bildqualität

Der Generator behält die höchste in der aktuellen Master-Playlist verfügbare
Video-Rendition nach Auflösung, Bildrate und Bandbreite. Die Sender können ihre
Varianten oder URLs jederzeit ändern; deshalb wertet der Pi die Master bei
jeder Aktualisierung neu aus. Beim geprüften ZDF-Master betrug die höchste
Auflösung 1280 × 720 bei 50 Bildern pro Sekunde. Der Generator kann keine
höhere Auflösung erzeugen, als der Sender anbietet.

## Aktualisieren und Fehlerbehebung

### Generator oder Senderliste aktualisieren

Nach Änderungen am Generator auf dem Mac aus dem Repository-Verzeichnis:

```sh
scp generate_zdf.py ludwin@192.168.0.131:/srv/smart-iptv/generate_zdf.py
ssh ludwin@192.168.0.131 'python3 /srv/smart-iptv/generate_zdf.py'
```

Nach Änderungen an `smartiptv.m3u` die M3U-Datei erneut über die Smart-IPTV-
Uploadseite übertragen. Eine Änderung an der M3U-Datei ändert nicht die bereits
auf dem Fernseher gespeicherte Liste, bis sie erneut hochgeladen wird.

### Status und Protokolle

Auf dem Pi:

```sh
systemctl is-enabled smart-iptv.timer
systemctl list-timers smart-iptv.timer --no-pager
systemctl status smart-iptv.service --no-pager
journalctl -u smart-iptv.service -n 100 --no-pager
sudo nginx -t
sudo systemctl status nginx --no-pager
```

- **`Connection refused` bei SSH:** Prüfen, ob die IP im Router noch dem Pi
	zugeordnet ist und ob SSH auf dem Pi aktiviert ist.
- **HTTP `404`:** Dateiname, Generator-Ausgabe und nginx-`root` prüfen.
- **HTTP `200` auf dem Pi, aber nicht vom Mac:** Pi-IP, WLAN/LAN, Gastnetz-
	Isolation und nginx-Port 8080 prüfen. Fernseher und Pi müssen sich im
	erreichbaren selben Heimnetz befinden.
- **Generator meldet fehlende Tonspur oder HTTP-Fehler:** Sender-Master kann
	geändert oder vorübergehend nicht erreichbar sein. Alte Datei bleibt bei
	einem Fehler für diesen Sender erhalten; Protokoll prüfen und später erneut
	ausführen.
- **Alte Senderliste am Fernseher:** M3U erneut hochladen und Smart IPTV
	vollständig neu starten.
- **Timer zeigt `active (waiting)`, Dienst zeigt `inactive (dead)`:** Das ist
	im Normalfall korrekt. Der Timer wartet auf den nächsten Lauf; der
	Einmaldienst läuft nur während der Generierung.

Den nginx-Webserver nicht per Portweiterleitung aus dem Internet freigeben.
Die in der M3U verwendeten privaten Pi-Adressen funktionieren nur für Geräte,
die den Pi im Heimnetz erreichen können.

---

Dokumentationsstand: 26. September 2026
