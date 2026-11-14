# DEV MODE am Gerät: Testplan

Stand 14. November 2026. **Noch nichts am Gerät gelaufen.** Rot, Basis Hacktribe `163d1d8d` (ORIGINAL.BIN der Karte).
Was im Emulator gemessen ist und welche Bereiche gesperrt bleiben: `2026-11-14-dev-mode-sperrbereiche.md`; Eingaben über
USB (Schritte 10 bis 12): `2026-11-14-dev-mode-eingabe.md`.

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

   `ht-text.VSB` ändert nur den Titel der Seite `DEV MODE` in `HOT MODE`. Für Schritt 6 (Code) gibt es noch kein Testbild,
   es wird vor dem Test gebaut und geprüft (offen).
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
| 6 | Code-Änderung in einer Laufzeitfunktion einer Seite schreiben; Seite öffnen; 1 Minute ein Pattern spielen | **braucht Freigabe** | Seite zeigt die Änderung, kein Absturz, Ton ohne Aussetzer | offen (Testbild fehlt) |
| 7 | `hot_patch.py --revert out/hot-patch/hot-patch-<sha8>.json` | **braucht Freigabe** | READ der geschriebenen Bereiche gleich Basis; Seite heißt wieder `DEV MODE` | offen |
| 8 | Aus- und einschalten; INFO; `--dry-run` gegen die Basis | am Gerät, dann READ | Flag `0x400` aus, Seite zeigt OFF, READ gleich Basis | offen |
| 9 | DEV MODE an, WRITE BEGIN auf die Schutztabelle `0xC0173800` (nur BEGIN, Skript unten) | **braucht Freigabe** | BEGIN abgelehnt, nichts geschrieben | offen |
| 10 | DEV MODE an; `remote_press.py --dry-run menu` und `remote_press.py --screen` | READ | Ausgabe `Weg: DEV MODE (WRITE in die Mailbox, kein EXEC)`, Display wird gelesen | offen |
| 11 | `remote_press.py menu +1 exit`, dann `level=200 pad5 touch=400,300` | **braucht Freigabe** | Seite wechselt wie am Panel, Pad 5 klingt, Pegel und Touch wirken; kein EXEC, Gerät läuft weiter | offen |
| 12 | DEV MODE aus; `remote_press.py --dry-run menu` | READ | Weg `EXEC-Stub`, ins Postfach wird nichts geschrieben | offen |

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

Noch keine. Hier je Schritt Datum, Firmware-sha256 und Ausgabe eintragen.
