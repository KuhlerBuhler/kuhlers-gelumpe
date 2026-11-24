# Gerätetest: BLECH-Firmwaredatei

Anleitung für Tester. Die Datei ist gebaut und im Emulator geprüft, am Gerät ist nur bestätigt,
was in Abschnitt 6 so steht. Siehe auch die [Übersicht](README.md).

## 1. Worum es geht

BLECH ist ein Satz von Patches für die eigene `SYSTEM.VSB` (Sampler 2.02, Korgs Original oder
[Hacktribe](../glossary.md#hacktribe)). Er gibt der Electribe das Menü BLECH, Plugins von der SD-Karte, den
Startbild-Editor, MFX 2 und mehr ([Plugins](../plugins.md), [Patcher](../patcher.md)). Dieser Test spielt die Datei
über DATA UTILITY, SOFTWARE UPDATE auf, prüft den Notschalter und geht die Geräteschritte durch, die der Emulator
nicht beantworten kann.

Der Satz steht in `data/patches/blech.json` (rot) und `data/patches/blech-synth.json` (blau). Die Seite Patcher baut
daraus dieselbe Datei wie `tools/patch/apply.mjs`.

## 2. Warnung

**Das Gerät wird verändert.** SOFTWARE UPDATE schreibt eine geänderte Firmware in den Flash
(`0x020000` bis `0x220000`). Du machst das auf eigenes Risiko, ohne Gewähr. Was passieren kann:

- Das Gerät hängt oder startet neu: aus- und wieder einschalten, oder mit gehaltenem EXIT starten.
- Das Gerät startet mit BLECH nicht normal: die Original-Firmware neu aufspielen (Abschnitt 5).
- Hängt die Firmware vor der Update-Abfrage, ist das Gerät ohne JTAG nicht zu retten. Die Startwege sind im
  Emulator geprüft, am Gerät ist das nicht ausgeschlossen ([Patcher](../patcher.md), "Was kaputtgehen kann").
- Daten gehen verloren, wenn das Update oder ein späteres Speichern gestört wird. Am 13.10. standen die Globals
  nach Arbeit am Gerät auf der Vorgabe, die Ursache ist **offen**
  ([Messung](../messungen/2026-10-13-globals-zurueckgesetzt.md)). FACTORY RESET löscht Patterns und Globals und
  steht in DATA UTILITY direkt vor SOFTWARE UPDATE.

Korg-Daten werden nie hochgeladen. `BLECH.VSB` enthält deine Firmware und bleibt bei dir, die Seite Patcher
verarbeitet sie im Browser. Gemeldet werden nur Textausgaben und Prüfsummen.

## 3. Voraussetzungen

- Electribe 2 mit Firmware 2.02, Netzteil angeschlossen (kein Batteriebetrieb beim Update).
- Die eigene `SYSTEM.VSB` oder `ORIGINAL.BIN` (Korg oder Hacktribe).
- SD-Karte im Gerät, Kartenleser am Rechner.
- Die App (Seite Patcher) oder Node 20. Für die Emulator-Prüfung die Python-Umgebung (`npm run setup:emu`).
- Für die Schritte in Abschnitt 7: Python 3 mit `mido` und das Gerät per USB. Es muss genau ein MIDI-Port mit
  "electribe" und "SOUND" im Namen da sein.

## 4. Vorher sichern

1. **SD-Karte komplett kopieren.**
2. **Global-Block lesen** (nur Lesen, nie ab Adresse `0x1000000`):

   ```bash
   python3 tools/device/flash_dump.py --out <Datei> --start 0x230000 --length 0x4000
   ```

   Die ersten 256 Byte sind der Global-Block ([Speicherbereiche](../speicherbereiche.md)). Nach dem Update dasselbe
   in eine zweite Datei schreiben und die ersten 256 Byte vergleichen.
3. **Patterns sichern:** am Gerät EXPORT ALL PATTERN in DATA UTILITY, das legt eine `.e2sallpat`-Datei im
   Kartenordner ab. Die Samples liegen als `e2sSample.all` auf der Karte, also in der Kartenkopie.
4. **Die laufende Firmwaredatei** sichern und ihre Prüfsumme notieren (`shasum -a 256`). Das ist die
   Rückkehr-Datei aus Abschnitt 5.

## 5. Der Weg zurück

Welche Datei in welchen Ordner gehört, steht in der [Rettung](../rettung.md), "Welche Datei in welchen Ordner".
Kurz:

- **Notschalter:** beim Einschalten EXIT halten. Dann läuft die Firmware ohne BLECH-Menü, Plugins und MFX 2, nur für
  diesen Start, es wird nichts gespeichert. Datenpatches wie das Blech-Startbild wirken weiter. Gegen kaputte
  Startdaten, DSP-Patches und kaputte gespeicherte Daten hilft er nicht ([Patcher](../patcher.md), "Notschalter").
- **Gerät startet noch:** die gesicherte Original-Datei als `SYSTEM.VSB` in den Ordner der laufenden Firmware legen,
  Prüfsumme der Kopie nachlesen, DATA UTILITY, SOFTWARE UPDATE. Am 10.10. so hin und zurück geübt
  ([Messung](../messungen/2026-10-10-rueckweg-geuebt.md)).
- **Gerät startet nicht:** [Rettung](../rettung.md). Hängt die Firmware vor der Update-Abfrage, hilft nur JTAG, nichts
  weiter ausprobieren.
- **Ein Plugin macht Ärger:** `Plugin/e2sPlugin.all` von der Karte nehmen oder mit gehaltenem EXIT starten.
- **Globals weichen ab:** nicht ausschalten und nicht WRITE drücken (das speichert, was im RAM steht). Den
  gesicherten Block als Global-Dump (`0x51`) senden, das speichert sofort. Den globalen MIDI-Kanal danach von Hand
  setzen. Ein fertiges Werkzeug dafür liegt nicht bei (**offen**).

## 6. Installieren und Notschalter

Je Schritt "ok", "anders" oder "nicht gelaufen" melden. Hält ein Schritt nicht, was er erwartet: aufhören, Ausgabe
und Display notieren.

| # | Schritt | Erwartet |
|---|---|---|
| 1 | Datei bauen: Seite Patcher, oder `node tools/patch/apply.mjs --vsb <eigene SYSTEM.VSB> --set data/patches/blech.json --out BLECH.VSB` | `wrote BLECH.VSB`, SHA-256 notieren (sie hängt von deiner Ausgangsdatei ab) |
| 2 | Im Emulator prüfen: die Seite Patcher macht es selbst und gibt den Download erst danach frei, `apply.mjs` druckt den Befehl für `tools/emu/check.py` | alle Prüfungen bestanden, das dauert einige Minuten |
| 3 | `BLECH.VSB` als `SYSTEM.VSB` in den Ordner der laufenden Firmware auf der Karte, Prüfsumme der Kopie nachlesen | gleich der aus Schritt 1 |
| 4 | Karte ins ausgeschaltete Gerät, Netzteil, DATA UTILITY, SOFTWARE UPDATE (davor steht FACTORY RESET, das nicht bestätigen), Version ansehen, bestätigen, "OK. Please Reboot." abwarten, ausschalten | das Update läuft durch |
| 5 | Einschalten, dann Global-Block erneut lesen und mit der Sicherung vergleichen | Blech-Startbild, Hauptbildschirm, Samples da, Globals unverändert |
| 6 | Neustart mit gehaltenem EXIT | normaler Start ohne Menü BLECH (der Ring läuft von Global direkt zu Data Util), das Blech-Startbild erscheint trotzdem |

Der Notschalter ist am Gerät für den MFX-2-Code-Patch bestätigt (13.10.), für den ganzen Satz ist er **offen**.

## 7. Geräteschritte

Das Menü BLECH und die Plugin-Laufzeit sind im Emulator mit Fällen in `tools/emu/` geprüft (`menu_cases.py`,
`script_cases.py`, `blechy_cases.py`). Die folgenden Schritte brauchen das Gerät.

### 7.1 BLECH SysEx: RAM lesen, Durchsatz messen

Der Patch `blech-sysex` gibt dem Gerät eigene [SysEx](../glossary.md#sysex)-Befehle `0x60` bis `0x63`
([Messung](../messungen/2026-10-15-blech-sysex.md)). Gerät per USB, kein Editor im Browser offen:

```bash
python3 tools/device/blech_sysex_probe.py --repeat 5
```

Das Werkzeug fragt INFO, liest `0xC0000100` in Blöcken von 256 bis 32768 Byte, prüft jeden Block gegen die CRC-32 des
Geräts und druckt Millisekunden und KiB/s je Größe. Es schreibt nichts. Bricht es bei einer Größe ab, ist die Größe
darunter der größte sichere Block.

Erwartet: INFO mit Version 1, Flags `0xF`, größter Block 32768, alle Blöcke mit passender CRC. Im Emulator über DIN
schafft ein Block 2,6 KiB/s (die Leitung ist die Grenze), über USB wird deutlich mehr erwartet (geschätzt). Mit EXIT
beim Einschalten bleibt die Abfrage ohne Antwort. Melden: die Ausgabe, bei einem Abbruch die Größe und die Meldung.

### 7.2 BLECH FLASH READ: den Flash lesen (besonders blaue Electribe)

Der Befehl `0x64` liest den Flash nur, es gibt keinen, der ihn schreibt oder löscht. Gedacht für die blaue
Electribe 2 (Synth), von der es bisher keine Sicherung des Flash gibt. Voraussetzung: eine Firmware mit dem
SysEx-Patch (Synth: `data/patches/blech-synth.json`), Netzteil, nichts am Gerät bedienen, solange das Werkzeug läuft.

1. Die Original-`SYSTEM.VSB` der blauen (Version 2.02) und die Karte sichern, das ist der Weg zurück.
2. Die BLECH-Synth-Datei als `SYSTEM.VSB` in den Ordner legen, der in der [Rettung](../rettung.md) für die blaue
   steht, dort **keine andere Datei** (besonders kein `BOOT.VSB`, `USER.VSB`, `PCM.VSB`: was die Firmware damit tut,
   ist nicht gemessen). SOFTWARE UPDATE wie in Abschnitt 6, mit Netzteil (mit Batterie lehnt das Gerät ab).
3. Lesen:

   ```bash
   python3 tools/device/blech_sysex_probe.py --repeat 2
   python3 tools/device/blech_flash_dump.py --out <Datei> --start 0x220000 --length 0x8000   # ein kleiner Anfang
   python3 tools/device/blech_flash_dump.py --out <Datei>                                      # der ganze Flash
   ```

   Das Werkzeug liest in Blöcken zu 4096 Byte, prüft jede CRC-32, liest alles zweimal und schreibt die Datei nur,
   wenn beide Läufe gleich sind. Es lehnt einen Pfad in einem Git-Arbeitsverzeichnis ab, denn die Datei enthält
   Korg-Daten.
4. Zurück: die gesicherte Original-Datei in denselben Ordner, dieselben Schritte. Dann antworten INFO und FLASH READ
   nicht mehr.

Erwartet: der kleine Lauf zeigt am Anfang die Kennung der Nutzerdaten (Synth `KORGelec2USR`, Sampler `KORGele2sUSR`),
der volle Lauf endet mit "written", beide Läufe haben dieselbe SHA-256, die Datei hat 16.777.216 Byte. Die Datei nicht
weitergeben. Melden: SHA-256 und Dauer, sonst die Meldung und die Adresse.

### 7.3 HT OSC: Hacktribes Oszillatoren auf der roten Firmware (nur rot)

Voraussetzung: der BLECH-Satz auf Korgs roter 2.02, Karte mit der eigenen `e2sSample.all`. Im Emulator gemessen ist,
dass die Einträge stehen, der Regler sie erreicht, die Datei lädt und ein Pattern sie behält
([Messung](../messungen/2026-11-08-ht-osc-freie-plaetze.md)). Wie sie klingen, zeigt nur das Gerät.

1. Part 1 wählen, OSC-Regler bis 420 (letztes Werks-Sample), eine Raste weiter. Erwartet: 422 DUAL-SAW. Weiter bis
   497 VPM-SINE 32, die nächste Raste springt auf 501. Jeden Oszillator kurz anspielen.
2. Mit einer Hacktribe vergleichen, wenn eine da ist (DUAL-SAW, CHIP-NOISE, X-SAW 0, X-SAW +12, VPM-SINE 4).
   Erwartet: gleicher Klang.
3. Osc Edit auf DUAL-SAW und X-SAW 0 drehen. Erwartet: der Klang ändert sich wie unter Hacktribe.
4. Part 1 auf 431 (CHIP-TRI 2), WRITE, aus- und einschalten. Erwartet: Part 1 steht auf 431 und klingt gleich.
5. BLECH > FEATURES ansehen. Erwartet: keine Seite HT OSC, die Oszillatoren sind immer an.
6. Mit EXIT beim Einschalten: wie die Firmware, 422 heißt `Sample422`.

Melden: ok je Schritt, sonst welcher Oszillator anders klingt oder stumm ist (mit Platznummer).

### 7.4 CATEGORY in SAMPLE EDIT (rot und Hacktribe, nicht blau)

Voraussetzung: der BLECH-Satz, Karte mit mindestens einem eigenen Sample. Im Emulator gemessen sind Seiten, Zähler,
Rad, Export und ein Sample mit Slices ([Messung](../messungen/2026-11-21-sample-kategorie.md)).

1. DATA UTILITY > SAMPLE EDIT, ein eigenes Sample wählen, EDIT rechts. Erwartet: Seite 3/11 heißt CATEGORY, der Wert ist
   "[User]" (Hacktribe "[Wave]").
2. Rad auf "[Kick]", EXIT. Erwartet: das Part-Bild zeigt beim Sample "[Kick]".
3. SHIFT + OSC-Rad auf einem Part mit diesem Sample. Erwartet: es springt auf das Sample als eigene Kick-Folge, nicht zu
   den Werks-Kicks.
4. RENAME, START POINT, DELETE SAMPLE durchgehen. Erwartet: wie vorher, der Zähler zählt bis 11/11 und läuft auf 1/11 um.
5. EXPORT ALL SAMPLE, aus- und einschalten. Erwartet: das Sample steht weiter auf "[Kick]", und ein Sample-Werkzeug am
   Rechner zeigt die Kategorie Kick.
6. Ohne EXPORT ALL SAMPLE umstellen, aus- und einschalten. Erwartet (hergeleitet): die alte Kategorie ist zurück.
7. Mit EXIT beim Einschalten: SAMPLE EDIT hat Korgs 10 Seiten, keine CATEGORY.

Melden: ok je Schritt, sonst die Seite und was das Display zeigt.

## 8. Am Gerät bestätigt

| Punkt | Stand |
|---|---|
| Update mit einer Datei aus dem eigenen Patcher, danach zurück mit der gesicherten Datei | am Gerät bestätigt, 10.10. ([Messung](../messungen/2026-10-10-rueckweg-geuebt.md)) |
| EXIT beim Einschalten ist Bit 13 (`0x2000`), Startmodus 0 | am Gerät bestätigt, 10.10. |
| MFX 2 als erster Code-Patch: Update lief, Fingerabdrücke im RAM gleich der Datei, kein Knacken nach Gehör | am Gerät bestätigt, 13.10. ([Messung](../messungen/2026-10-13-mfx-umschalter-geraet.md)) |
| Eine laufende BLECH nimmt ihr Update aus `KORG/blechtribe/System/SYSTEM.VSB` | am Gerät bestätigt, 15.10. |
| Notschalter für den ganzen Satz, SysEx-Durchsatz über USB, Klang der HT-OSC-Oszillatoren, CATEGORY am Gerät | offen |
| Ein/Aus auf dem Bildschirm "OK. Please Reboot." | offen |
| Verhalten der Firmware bei einem fehlerhaften oder abgebrochenen Update | offen |
| Ursache für die zurückgesetzten Globals vom 13.10. | offen |
