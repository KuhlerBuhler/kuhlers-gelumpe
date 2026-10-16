# Eigener Start-Haken für BLECH auf dem Synth

Stand 2026-10-16. Gemessen mit dem blauen Original 2.02 ausschließlich im
Emulator. Kein Gerät wurde angesprochen. Messprogramme und vollständige
Protokolle liegen außerhalb des Repositorys.

## Ergebnis

**Gemessen:** Die vollständige Menü- und Plugin-Laufzeit braucht den Einstieg
bei `0xC0028170`, nach der nativen Modell- und Bildschirm-Initialisierung.
Die zunächst untersuchte Stelle `0xC0028084` erlaubt bereits Dateizugriffe,
liegt für die vollständige Laufzeit aber zu früh: Mit einer eingelegten Karte
weichen dort die LEDs LPF und MFX SEND vom Original ab. Auch das Vorziehen
des verdrängten nativen Aufrufs behebt das nicht. Am späteren Einstieg bleiben
beide LEDs und der übrige geprüfte Zustand wie im Original.

Der Synth lädt keine Samples. Menü, Einstellungen, Blechy und Karten-Plugins
werden deshalb über einen eigenen Synth-Wrapper initialisiert. Die beiden
Sampler-Haken am Sample-Lader bleiben auf die Sampler-Builds beschränkt.

## Adressen und Ablauf

| Stelle | Sampler | Synth | Prüfung |
|---|---|---|---|
| gemeinsamer Einstieg nach den besonderen Tastenmodi | `0xC002ADAC` | `0xC0027FE8` | 16 Befehle gleich |
| Prüfung des Panel-Update-Merkers | `0xC002AE40` | `0xC0028074` | anderer Code, keine direkte Übernahme |
| früherer Startbild-Kandidat | `0xC002AE64` | `0xC0028074` | anderer Code, bleibt abgelehnt |
| Probe nach dem Laden der Benutzerdaten | `0xC002AEC0` | `0xC0028084` | 16 Befehle gleich; nur Dateizugriff geeignet |
| Fortsetzung der Dateiprobe | `0xC002AEC4` | `0xC0028088` | 16 Befehle gleich |
| ursprüngliches Aufrufziel der Dateiprobe | `0xC0057884` | `0xC004E678` | 16 Befehle gleich |
| Einstieg der vollständigen Laufzeit | `0xC002AFAC` | `0xC0028170` | 16 Befehle gleich, eindeutiger Treffer |
| Datei öffnen | `0xC009DB60` | `0xC008A6B8` | 16 Befehle gleich |
| Datei lesen | `0xC009DD74` | `0xC008A8CC` | 16 Befehle gleich |
| Datei schließen | `0xC009E3DC` | `0xC008AF34` | 16 Befehle gleich |

Die Gleichheitsprüfungen verwenden `FirmwareMap.same_code` aus
`tools/patch/fwmap.py` mit dem angegebenen Synth-Ziel und 16 Befehlen.
Die Maskierung berücksichtigt verschobene Sprünge, PC-relative Literale und
Firmware-Zeiger. Zusätzlich wurden Kontrollfluss, Aufrufziele und Auswirkungen
im Emulator beobachtet. Eine gleiche Sprungmaske allein bestimmt kein Ziel.

Im normalen Start mit dem aufgebauten PCM-Flash wird `0xC0028074` bei
93,367 ms erreicht. Dort folgt bei freiem Panel-Update-Merker der native
Lader `0xC0046E54`. Er kehrt vor `0xC0028084` bei 4899,240 ms zurück.
Mit leerem Benutzer-Flash liegt dieser Punkt schon bei 284,726 ms.
Die Initialisierung hängt am tatsächlichen nativen Ablauf, nicht an einer
festen Wartezeit. Danach folgt die weitere native Initialisierung bis zum
jetzt verwendeten Einstieg bei `0xC0028170`.

## Failsafe und besondere Startwege

Der Wrapper prüft vor jedem eigenen Dateizugriff und vor jeder Initialisierung:

1. Panel-Zeiger aus `0xC033E8F8`, einschließlich Null und `0xFFFFFFFF`.
2. EXIT in den Einschalt-Tasten bei Panel `+0x18`, Maske `0x2000`.
3. Panel-Update-Merker bei Panel `+0x22`.
4. Besonderen Startmodus bei Panel `+0x20`; nur Wert null wird zugelassen.

Bei einem dieser Schutzfälle führt er keinen eigenen Lader aus. Sonst ruft er
Menü und Einstellungen, Blechy, Karten-Plugins und das Zählen der Menüseiten
jeweils einmal in dieser Reihenfolge auf. Vor der Rückkehr stellt er alle
Register und Flags wieder her, führt das verdrängte `ldrb r3, [r4, #4]` aus
und setzt bei `0xC0028174` fort. Das gilt auch bei ausgelöstem Notschalter.

Die eigene Unicorn-Prüfung deckt Normalstart, EXIT, Panel-Update, besonderen
Startmodus sowie beide ungültigen Panel-Zeiger ab. Sie prüft zusätzlich
Register, Flags, Stapel, Rücksprung und den Effekt des verdrängten Befehls.
Die vollständigen Firmware-Prüfungen stehen in der
[Synth-Messung](2026-10-16-blech-synth.md).

## Voruntersuchung des Dateizugriffs

Der Dateiaufruf bei `0xC0028074` kehrt nach sieben Sekunden Emulatorzeit
nicht zurück. Bei `0xC0028084` öffnet und schließt dieselbe Probe eine eigene
20-Byte-Datei erfolgreich; das Öffnen dauert rund 17,45 ms. Lesen liefert
Inhalt und Länge unverändert. Ohne Datei kommt Status 4, ohne Karte Status 12
zurück; der Hauptbildschirm bleibt erreichbar.

Die zehn besonderen Tastenmodi und die Update-Abfrage bei fehlender
Benutzerkennung umgehen die frühere Dateiprobe. Shift mit Maske `0x400`
bleibt ein normaler Start. EXIT und Panel-Update können den normalen
Kontrollfluss erreichen und brauchen deshalb die ausdrückliche Schutzprüfung.

| Vorversuch | Ergebnis |
|---|---|
| Original: 16 Startfälle und Normalstart sowie EXIT mit Karte | 18 von 18 wie erwartet |
| geschützte Dateiprobe: 16 Startfälle mit Karte und Normalstart sowie EXIT auf dem damaligen Synth-Satz | 18 von 18 wie erwartet |
| früher und später Dateiaufruf, fehlende Karte, EXIT und Panel-Update | 5 von 5 wie erwartet; früher Aufruf als Gegenprobe ohne Rückkehr |
| eigene Testdatei auf Original und damaligem Synth-Satz sowie fehlende Datei | 3 von 3 wie erwartet |

Diese Vorversuche belegen den Dateizugriff. Erst die spätere Prüfung mit der
vollständigen Laufzeit deckte die beiden LED-Abweichungen auf und führte zum
Einstieg `0xC0028170`. Der Startbild-Editor benötigt weiterhin eine eigene
Untersuchung seiner frühen Zeichenfolge und des späteren Dateizugriffs.
