# DEV MODE am Gerät: Testplan

Stand 14. November 2026. Am Gerät gelaufen: alle Schritte (Ergebnisse unten). Rot, Basis Hacktribe `163d1d8d` (ORIGINAL.BIN der Karte).
Was im Emulator gemessen ist und welche Bereiche gesperrt bleiben: `2026-11-14-dev-mode-sperrbereiche.md`.

Regeln für jeden Schritt:

- **READ** (INFO, READ, FILE READ, `--dry-run`) läuft ohne Rückfrage.
- Jeder Schritt mit **"braucht Freigabe"** schreibt ins Gerät (WRITE, auch nur WRITE BEGIN). Er läuft erst nach einer
  Freigabe für genau diesen Schritt. Das Tool führt nie EXEC aus und drückt keine Tasten.
- Keine SYSTEM.VSB auf die Karte schreiben, die nicht ganz und mit passendem sha256 angekommen ist.

## Vorbereitung

1. Firmware mit Phase 1 bis 3 dieses Branches im Patcher der installierten App bauen, Basis die `ORIGINAL.BIN` der Karte
   (Hacktribe `163d1d8d`). Den CLI-Build nur zum Vergleich (sha256 muss gleich sein).
2. Die SYSTEM.VSB der Karte vorher auf den Laptop sichern (`~/gelumpe-swap`), dann die neue Firmware per SOFTWARE UPDATE
   einspielen.
3. Testbilder für die Schritte 4 bis 6 auf dem Mac bauen, mit genau dieser Firmware als `--vsb`:

   ```bash
   python3 tools/device/make_hot_fixtures.py --vsb out/devmode/geraet.VSB --out out/devmode
   python3 tools/emu/check.py --base ORIGINAL.BIN --patched out/devmode/ht-text.VSB --report out/devmode/ht-text.report.json
   ```

   `ht-text.VSB` ändert nur den Titel der Seite `DEV MODE` in `HOT MODE`. `ht-code.VSB` (Schritt 6) tauscht in
   `menu_text_dev` `ldreq`/`ldrne`, die Seite zeigt dann `OFF`, solange DEV MODE an ist: Laufzeitcode, kein Text.
   Prüfen wie `ht-text.VSB` (`--report out/devmode/ht-code.report.json`).
4. Die Electribe hängt am Host `linux`; `tools/device/` und `tools/patch/blech_sysex.py` dorthin kopieren, die Befehle laufen
   dort.

## Schritte

| # | Schritt | Art | Erwartung | Ergebnis |
|---|---|---|---|---|
| 1 | INFO lesen; `hot_patch.py --dry-run --new ht-text.VSB --checked ht-text.report.json` | READ | Flag `0x200` (DEV MODE eingebaut) gesetzt, `0x400` (an) nicht; das Tool bricht vor dem Basis-Beweis mit "DEV MODE is off" ab | offen |
| 2 | WRITE BEGIN ins Abbild ohne DEV MODE (nur BEGIN, kein DATA, Skript unten) | **braucht Freigabe** | BEGIN abgelehnt (Status != 0), nichts geschrieben; READ der Adresse unverändert | offen |
| 3 | Am Gerät: BLECH-Menü, Seite `DEV MODE` auf ON; danach INFO | am Gerät, dann READ | Flag `0x400` gesetzt | offen |
| 4 | `hot_patch.py --dry-run --new ht-text.VSB --checked ht-text.report.json` | READ | Basis-Beweis über das ganze Abbild bestanden, Tabelle mit einem `hot`-Bereich (der Titel), keine `full`-Zeile | offen |
| 5a | Dasselbe ohne `--dry-run`, Sequencer gestoppt, Blöcke 1 KiB | **braucht Freigabe** | Seite heißt `HOT MODE`, ohne Neustart; Journal in `out/hot-patch/` | offen |
| 5b | Ein 32-KiB-Block in freien FF-Bereich (Adresse vorher aus dem Abbild wählen), Antwortzeit von WRITE DATA messen | **braucht Freigabe** | Antwort kommt, Gerät läuft weiter; Zeit notieren (IRQ/FIQ während der Kopie maskiert) | offen |
| 6 | Code-Änderung in einer Laufzeitfunktion einer Seite schreiben; Seite öffnen; 1 Minute ein Pattern spielen | **braucht Freigabe** | Seite zeigt die Änderung, kein Absturz, Ton ohne Aussetzer | offen |
| 7 | `hot_patch.py --revert out/hot-patch/hot-patch-<sha8>.json` | **braucht Freigabe** | READ der geschriebenen Bereiche gleich Basis; Seite heißt wieder `DEV MODE` | offen |
| 8 | Aus- und einschalten; INFO; `--dry-run` gegen die Basis | am Gerät, dann READ | Flag `0x400` aus, Seite zeigt OFF, READ gleich Basis | offen |
| 9 | DEV MODE an, WRITE BEGIN auf die Schutztabelle `0xC0173800` (nur BEGIN, Skript unten) | **braucht Freigabe** | BEGIN abgelehnt, nichts geschrieben | offen |

Erwartet: Gruppen über 1 KiB zeigen die Warnung "not atomic". Läuft der Sequencer, schreibt das Tool nicht (Wort
`0xC06BC318`). Stürzt das Gerät ab: aus und ein, danach läuft wieder die Firmware der Karte, nichts im Flash ist geändert.

## Nur WRITE BEGIN (Schritte 2 und 9)

Sendet nur BEGIN mit einem Byte. Auch wenn die Firmware es fälschlich annimmt, wird ohne WRITE DATA nichts kopiert.

```python
import struct, sys, zlib
sys.path.insert(0, "tools/device")
from remote_press import Blech, WRITE_BEGIN
from led_show import mido_ask
b = Blech(mido_ask())
addr = int(sys.argv[1], 16)          # Schritt 2: 0xC0100000, Schritt 9: 0xC0173800
before = b.read(addr, 4)
func, body = b.talk(WRITE_BEGIN, struct.pack("<3I", addr, 1, zlib.crc32(before[:1])))
print(f"flags {b.flags:#x}, BEGIN func {func:#x}, status {body[:4].hex()}, unchanged {b.read(addr, 4) == before}")
```

## Ergebnisse

14. November 2026, rot, Firmware `c5aa9ee0` (Hacktribe `163d1d8d` + blech.json), Host `linux`.

| # | Ergebnis |
|---|---|
| 1 | INFO `0x7ff`: `0x200` und `0x400` gesetzt, DEV MODE war schon an (am Gerät eingeschaltet). "DEV MODE is off" nicht geprüft |
| 4 | `--proof full` bricht ab: das Gerät hat 33 Bereiche (41693 Byte) anders als die Basis, alle Laufzeitdaten, die der Emulator in 5 s nicht schreibt: Vektor-Zeiger `0xC0000034` (`0xC0001560`), `.data` bei `0xC00F9068`, `0xC00F9314`, `0xC00F9C80`, Settings-Liste ab `0xC0188A18`, `0xC0190140..0xC01907A0`, Einzelbytes `0xC01B21A6..0xC01B2A7D`, `0xC01DB984..0xC01E45E0`, `0xC01F7000..0xC01FC400`. Mit `--proof near`: 4096 Byte bewiesen, eine Zeile `0xc015b358..0xc015b35c 4 hot`, keine `full`-Zeile. Wie erwartet |
| 5a | Freigabe erteilt. `--yes --proof near`: 4 Byte in 1 Gruppe geschrieben, Journal `hot-patch-88176b69.json`. READ `0xC015B358`: `HOT MODE`, INFO weiter `0x7ff`, Gerät läuft. Display per `remote_press.py --screen` (BLECH, Liste, Zeile vor VERSION): Titel `HOT MODE`, Wert `ON`, ohne Neustart |
| 5b | Freigabe erteilt. Muster in freien FF-Bereich `0xC0165000` (Basis und Gerät FF, nicht gesperrt, keine Daten), Sequencer gestoppt: 1 KiB WRITE 11 ms, 2 KiB 17 ms, Rücklesen gleich, danach FF zurück, Gerät läuft. 32 KiB: ALSA auf `linux` sendet die SysEx nicht (`MidiOutAlsa::sendMessage` Fehler). 4 KiB: keine Antwort auf WRITE DATA; Bereich danach FF, nichts geschrieben, Gerät antwortet weiter, Korg zeigt ein Fenster "Error" (EXIT schließt es). Grenze liegt auf dem Weg Host/USB, nicht gemessen ob am Gerät; das Tool schreibt 1 KiB je Block |
| 7 | Freigabe erteilt. `--revert`: "reverted 1 ranges", READ `0xC015B358` wieder `DEV MODE`, Display nach Verlassen und Betreten der Seite `DEV MODE ON` (der Titel wird beim Betreten kopiert) |
| 9 | Freigabe erteilt. DEV MODE an, BEGIN auf `0xC0173800`: Status 2, abgelehnt, Bytes unverändert |
| 2 | Freigabe erteilt. DEV MODE per Rad -1 aus (`remote_press`), Display `OFF`, `DEV_FLAG` `ffffffff`, INFO `0x3ff`. BEGIN auf `0xC0100000`: Status 2, abgelehnt, Bytes unverändert |
| 8 | Aus und ein am Gerät. INFO `0x3ff`, `DEV_FLAG` `ffffffff`, `0xC015B358` `DEV MODE`, READ `0xC015B000..0xC015C000` gleich Basis, `0xC0165000` 32 KiB FF. `--dry-run` bricht mit "DEV MODE is off" ab (damit auch Schritt 1) |
| 6 | Freigabe erteilt. `ht-code.VSB` (sha `16ab3f52`, `check.py --quick` 19/19), im Emulator zeigt die Seite `ON` bei aus und `OFF` bei an. `--yes --allow-quick`: 8 Byte in 1 Gruppe (`0xC0157A74`, `0xC0157A78`), Rücklesen gleich, INFO `0x7ff`. Display auf der Seite: `DEV MODE` / `OFF` bei `DEV_FLAG` `DEVM`, ohne Neustart. 1 Minute Pattern gespielt: klang normal, kein Absturz. `--revert`: 1 Bereich, READ `0xC0157A70` = `000050e398109f0598109f15` (Basis), nach Verlassen und Betreten der Seite wieder `ON` |

Gefunden und behoben: `--proof full` passt so nicht zum echten Gerät (Bereiche oben gehören zu den Daten), `near` ist
jetzt der Standard. Auf `linux` scheiterte der Emulator-Teil von `hot_patch.py` in den Worker-Prozessen: spawn führt das
Skript dort erneut aus, und dessen `sys.path.insert(0, tools/device)` stellte `tools/device/backlight.py` vor
`tools/emu/backlight.py`. Das Skript hängt seine Pfade jetzt hinten an; auf `linux` laufen beide Bilder durch, die
Context-Dateien sind byte-gleich mit denen vom Mac.
