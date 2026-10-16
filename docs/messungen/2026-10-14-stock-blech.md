# BLECH auf Korgs Original 2.02

Stand 2026-10-14. Im Emulator und offline, kein Gerät. Eingaben: Korgs `SYSTEM.VSB` aus dem Systemupdate 2.02
(sha256 `1d0f0689...`), eine eigene, bearbeitete Hacktribe-Datei (`b0890899...`) und das eigene Flash-Abbild vom
2026-10-09 (`e177a321...`, Zustand eines Geräts mit Hacktribe). Markierungen: **gemessen** (ausgeführt, Befehl
genannt), **offline** (Code oder Daten gelesen), **hergeleitet**, **offen**. Die Dateien liegen nicht im
Repository, nur Ergebnisse und Hashes. Vorher: [Korgs Original-Firmware 2.02 im Emulator](2026-10-14-stock-emulator.md).

## Kurzfassung

1. **Der BLECH-Satz passt bis auf den Kartenordner unverändert auf Korgs Build.** Die Bytes, die jeder Patch
   ersetzt, haben dort dieselben Hashes, die Haken liegen an denselben Stellen. Der Kartenordner braucht eine
   eigene Fassung, weil Korgs Build `electribe sampler` (mit Leerzeichen) statt `hacktribe` liest.
2. **Das Startbild bleibt bei Korg länger stehen als bei Hacktribe und trägt einen Ladebalken.** Das ist Korgs
   Ladevorgang und kein Fehler des Patches. Mit leerem Flash steht das Bild rund 0,32 s, mit dem eigenen Flash rund
   6 s. Die Fälle des Startbild-Editors zählten die Bilder und verlangten, dass alle gleich sind; der Ladebalken
   ist jetzt als einzige erlaubte Abweichung beschrieben, sonst bleibt die Prüfung gleich streng.
3. **Der Emulator blieb mit Korgs Build und einem benutzten Flash für immer in einer Warteschleife** (Bit 2 des
   DSP-Statusports). Mit dem Bit läuft der Boot durch. Dazu verschob ein einzelnes Gleichlaufwort `0x2C` den
   Rahmen der Host-Port-Transfers um ein Wort; das Modell überliest es jetzt. Hacktribes Boot ändert sich durch
   beides nicht.
4. **`check.py` besteht auf BLECH aus Korgs Original, mit leerem Flash und mit dem eigenen Flash**
   (Zahlen unten).
5. **Was fehlt:** Hacktribes Zusätze (SysEx `0x52` bis `0x57`, Effekt-Presets an den Stellen der Karte). Sie
   bringt BLECH nicht mit.

## Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| Alle Patches außer `blechtribe` wenden sich auf Korgs Datei an, ihre erwarteten Bytes stimmen | gemessen | `node tools/patch/apply.mjs --vsb STOCK --set data/patches/blech.json --out OUT`, Ergebnis `82f54ad5...`; `test/blech-set.test.mjs` mit `E2_STOCK_VSB` |
| Im Original steht der Ordnername bei `0xC00A5656` (18 Byte mit NUL), der Pfad bei `0xC00A5678` (24 Byte), bei Hacktribe an denselben Stellen (11 und 17 Byte belegt) | offline | Bytevergleich beider Dateien |
| Kein 32-Bit-Wort im Abbild zeigt in die Mitte eines der beiden Fenster, in beiden Builds | gemessen | `inside_references` in `tools/patch/blechtribe.py`, bricht sonst ab |
| Die Ordner-Fassungen sind das, was `tools/patch/blechtribe.py` aus den Dateien baut | gemessen | `test/blech-set.test.mjs` mit `E2_VSB` und `E2_STOCK_VSB` |
| Das Start-Bild-Feld liegt in beiden Builds bei `0xF9954`, derselbe Deskriptor `0xC00F9854` | offline | Deskriptor bei `0xC00C5A54` gelesen; der Inhalt des Bildes ist ein anderer (Korgs Logo) |
| Mit leerem Flash zeigt die gepatchte Kopie das Startbild von 0,07 bis 0,40 s, dann leer bis 0,60 s, dann das Hauptbild | gemessen | Anzeige alle 2 ms, ein Lauf mit eigenem Skript |
| Hacktribe, gleiche Messung: Bild 0,07 bis 0,21 s | gemessen | ebenda |
| Über dem Startbild wird ab 0,10 s ein Ladebalken gezeichnet: Seite 7, Spalten 9 bis 119, er löscht die Pixelzeilen 61 und 62 (Bytes `& 0x9F`) | gemessen | Frames gegen das Bild verglichen, mit Flash wächst er von Spalte 19 bis 119 |
| Mit dem eigenen Flash lädt Korgs Build rund 6 s (Bild bis 5,9 s, Hauptbild bei 6,0 s); Hacktribe braucht mit demselben Flash 0,4 s | gemessen | wie oben, Schritte von 10 bis 50 ms |
| Ohne Statusbit 2 am DSP-Port bleibt Korgs Build mit dem eigenen Flash in der Schleife bei `0xC0014E0C` (Bildschirm 46), auch die unveränderte Datei | gemessen | PC alle 0,5 s bis 3 s derselbe Block, auch bei 8 s kein Hauptbild |
| Mit `0x85` statt `0x81` bootet es; Hacktribe ändert sich nicht | gemessen | Anzeige-Pixelzahl und Bildschirmnummer alle 50 ms über 8 s, mit und ohne Flash, byteweise gleich |
| Die Warteschleife ist die Wartestelle in der DSP-Schreibfunktion `0xC0014D60` (Befehl `0x2C`, dann Statusbit 2) | offline | Disassembly |
| Korgs Build schreibt einmal früh ein einzelnes Wort `0x2C` an den Steuerport, danach lagen die 7-Wort-Rahmen des Modells um eins verschoben (die Pegelabfragen erschienen als Adressen wie `0x30EC00A9`) | gemessen | Steuerworte mitgeschrieben, 134 Wörter in der ersten Sekunde, das erste `0x2C`, danach `AB` im Abstand 7; Rahmenlänge `25124 mod 7 = 1` |
| Mit der Regel "`0x2C` am Rahmenanfang überlesen" sind die Rahmen ausgerichtet und die MFX-Fälle mit eigenem Flash bestehen | gemessen | `mfx:dsp_messages` mit Flash: vorher 270 gegen 163 Transfers, nachher 22 gegen 11 und gleich |
| Ohne feinere Zeitscheiben meldete `bootmap.py` mit eigenem Flash Code des MFX-Tick-Hakens als Start: Korgs Build erreicht das Hauptbild an einer beliebigen Stelle des 40-ms-Ticks, Hacktribes 20-ms-Scheibe traf es zufällig nicht. Für Korgs Build gilt jetzt 2 ms | gemessen | `bootmap.py`-Szenario `normal` mit Flash, Blöcke bei `0xC01A5194` |
| Das Bit ist eine **Modellannahme** (wie das `0x81` zuvor): wie echte Hardware antwortet, ist nicht gemessen | offen | |
| `check.py` auf BLECH aus Korgs Original, ohne Flash: 88 von 88 bestanden | gemessen | siehe unten |
| `check.py` auf BLECH aus Korgs Original, mit eigenem Flash: 89 von 89 bestanden | gemessen | siehe unten |
| Die Update-Datei BLECH-aus-Korg wird von Korgs Firmware als Update gefunden (ENTER liest mehr Sektoren als ohne) | gemessen | `test/emulator-stock.test.mjs`, "the fear button with Korg's original ..." |
| Am Gerät | offen | nicht versucht |

## Prüfung

Befehl (die Spannen stehen in der Ausgabe von `apply.mjs`, `GELUMPE_JOBS=4`):

```bash
node tools/patch/apply.mjs --vsb STOCK --set data/patches/blech.json --out BLECH-STOCK.VSB
tools/emu/.venv/bin/python tools/emu/check.py --base STOCK --patched BLECH-STOCK.VSB --allow ... --allow-code ... [--flash flash_full_2026-10-09.bin]
```

Beide Läufe: alle Startwege, DSP-Strom, Startphase mit den Ausnahmen der Patches, die neun Startbild-Fälle, die
acht MFX-2-Fälle, die Menü-, Einstellungs- und Look-Fälle (BLECH-Menü und Plugin-Laufzeit). Mit Flash kommt der
Start mit leerem Flash (`boot:normal_blank`) als 89. Prüfung dazu nicht anders als bei Hacktribe: nur der Ladebalken
über dem Startbild ist als Abweichung beschrieben.

Auf dem Weg dahin fiel es mehrmals durch, jedes Mal aus einem Grund im Emulator oder in der Prüfung, nie im Patch:
der Ladebalken (ein Startbild-Fall), die Wartezeit des Ladens (`boot:normal`, `kill_switch`, alle MFX-Fälle),
das noch nicht gesetzte LED-Bild eine Sekunde nach dem Hauptbild (`mfx:boot_mode`), die zu grobe Zeitscheibe
(`start_phase`) und das verschobene Rahmenwort (`mfx:dsp_messages`, `mfx:led_copy`).
## Was dafür geändert wurde

- `machine.py`: Statusbit 2 am DSP-Port, Gleichlaufwort `0x2C` überlesen (auch in `DspLog` von `mfx_cases.py`),
  `loading()` und `finish_boot()` (Korgs Build läuft, solange er lädt, und eine Sekunde danach).
- `bootmap.py`, `bootcache.py`, `splash_cases.py` (`Dev.run`): warten auf das Ende des Ladens, nur für Korgs Build;
  `bootmap.py` mit 2-ms-Scheiben für Korgs Build.
- `splash_cases.py`: `same_image` lässt für Korgs Build den Ladebalken über dem Bild zu, `boot_case` wartet bis zu
  12 s. Die Prüfung bleibt für Hacktribe unverändert (`test_splash_cases.py`).

## Offen

- Am Gerät läuft BLECH aus Korgs Original nicht: weder Menü noch Plugins noch der Weg über SOFTWARE UPDATE.
- Wie echte Hardware am DSP-Port antwortet (Bit 2), und ob Korgs Ladebalken am Gerät genauso aussieht wie im
  Emulator.
- `script_cases.py` ist auf Korgs Build nicht gelaufen.
