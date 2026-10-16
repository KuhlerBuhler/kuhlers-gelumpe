# Korgs Original-Firmware 2.02 im Emulator

Stand 2026-10-14. Offline und im Emulator, kein Gerät. Eingaben: Korgs `SYSTEM.VSB` aus dem
Systemupdate 2.02 (sha256 `1d0f0689...`), Hacktribes offizielle 2.02 aus dem SD-Paket (`7cb4825c...`)
und eine eigene, bearbeitete Hacktribe-Datei (`b0890899...`). Markierungen: **gemessen** (ausgeführt,
Befehl genannt), **offline** (Code oder Daten gelesen), **hergeleitet**, **offen**. Die Dateien liegen
nicht im Repository, nur Ergebnisse und Hashes.

## Kurzfassung

1. **Korgs Original bootet im Emulator ohne Änderung am Emulator.** Hauptbild nach 600 ms Gerätezeit
   (Hacktribe 400 ms), gleiches Display, keine Assertion, alle Haken des Emulators feuern.
2. **Alle Stellen, die der Emulator braucht, liegen in beiden Builds an denselben Adressen.** Der Code
   unterscheidet sich in 39 kleinen Bereichen (1208 Byte, der größte 307 Byte). Der Rest der Unterschiede
   ist Hacktribes neuer Code (ab `0xC0170000` und `0xC01A0000`) und sind Daten.
3. **Nicht übertragbar sind die Funktionen, die Hacktribe hinzufügt:** SysEx `0x52` bis `0x57`, die
   Effekt-Presets an den Stellen der Gerätekarte, die Groove-Tabelle, BLECH und Plugins.
4. **Ordner der Karte:** Korgs Build liest `KORG/electribe sampler/` (mit Leerzeichen, 17 Zeichen),
   Hacktribes `KORG/hacktribe/`. Der Kartenspeicher des Emulators nahm nur Namen ohne Leerzeichen bis
   16 Zeichen und fiel für das Original auf `hacktribe` zurück. Das war die einzige Stelle, an der der
   Emulator mit dem Original falsch lag.

## Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| Original bootet bis `screen_1`, Display-Hash gleich dem der Hacktribe-Datei nach 6 s | gemessen | `machine.py --vsb STOCK --seconds 6`, `display_sha256 7b67b71c...` bei beiden |
| Die vier Haken (Assert, Flash-Lesen, DSP-Upload, UART-Sendeschleife) feuern im Original | gemessen | Zähler am `service` in 3 s: Upload 1 (bei beiden), Flash-Lesen 24 (Hacktribe 6), UART 234 (232) |
| Acht Stellen haben in beiden Builds dieselbe maskierte Signatur | gemessen | `firmware.py DATEI --sign ADRESSE` gegen alle drei Dateien, Tabelle in `docs/emulator.md` |
| Alle Startwege gleich: Normal, Update-Abfrage (Modus 10), Panel-Update, 11 Startmodi, EXIT | gemessen | `bootmap.py --vsb` mit beiden Dateien: Modi und Tasten identisch, `screen_1` bei 541 ms gegen 341 ms |
| Der Code unterscheidet sich in 39 Bereichen, 1208 Byte, unter `0xC00A0000` | gemessen | Bytevergleich der Nutzlasten, Lücken unter 256 Byte zusammengefasst |
| Die 65 397 Byte Unterschied aus [dsp-erster-blick.md](../hintergrund/dsp-erster-blick.md) sind überwiegend Daten | gemessen | `0xC00A7F60` bis `0xC00B5A25` allein 56 005 Byte (Effekttabellen), dazu Namen, Groove-Tabelle und Hacktribes Code |
| Hacktribes Code liegt in `0xC0170000` und `0xC01A0000`, bei Korg steht dort 0xFF | gemessen | Bytevergleich |
| Korgs Build kennt Hacktribes SysEx nicht: Gerätesuche wird beantwortet (Version 2.2), RAM-Lesen und -Schreiben nicht | gemessen | `machine.py --midi`, eine Antwort auf drei Anfragen (`test/emulator-stock.test.mjs`) |
| In Korgs VSB sind die Preset-Tabellen der Karte fast leer: MFX-Slots 1 bis 32 und fast alle Insert-Slots sind Nullen | gemessen | Vergleich der Datei bei `0xB5030` und `0xA81F0`, Schritt `0x20C`; nur MFX 33 "Mid EQ", IFX 49 "Repeater" und 50 stehen dort |
| Die Preset-Namen stehen in Korgs Datei an anderen Stellen (zum Beispiel "Mod Delay" bei `0xBC4DD`, bei Hacktribe `0xB5031`) | gemessen | Suche nach dem Namen mit NUL |
| Menülängen sind in Korgs Build 32 (Master) und 38 (Insert), an denselben Stellen wie bei Hacktribe | gemessen | `identify` liest `menu.mfxCount` und `menu.ifxCount`, die Stellen sind einig |
| Die Groove-Tabelle bei `0x143C00` gibt es nur bei Hacktribe | gemessen | Kennung `GVST` kommt bei Korg nur dreimal vor, alle unter `0x54200` |
| Korgs Build liest `KORG/electribe sampler/` | offline | Zeichenkette bei `0xC00A5678` vor `e2sSample.all`, bei Hacktribe `KORG/hacktribe/` |
| Karte, WAV-Import und -Export in `KORG/electribe sampler/Sample/`, Ordner als Karte nach Neustart: wie bei Hacktribe | gemessen | `test/emulator-card-stock.test.mjs`, drei Fälle |
| SOFTWARE UPDATE findet `KORG/electribe sampler/System/SYSTEM.VSB`: mit der Datei liest die Firmware nach ENTER 32 Sektoren, ohne 17 | gemessen | Probelauf mit dem Dienst, Datei über `/sd/system` abgelegt, DATA UTILITY 14, ENTER; `test/emulator-stock.test.mjs` |
| Der DSP-Strom ist gleich | offline | [dsp-erster-blick.md](../hintergrund/dsp-erster-blick.md), nicht neu gemessen |

## Offen

- Wie Korgs Build seine Presets ablegt (Format, Ort), ist nicht entschlüsselt.
- Warum Korgs Build bis zum Hauptbild 200 ms länger braucht (mehr Flash-Lesen: 24 gegen 6 Aufrufe).
- Die Fälle der Patch-Prüfung (`splash_cases.py`, `mfx_cases.py`, `menu_cases.py`, `script_cases.py`) sind
  für Hacktribe geschrieben und rechnen mit dessen Adressen für Pattern, Sequenzer und Menü. Stand 2026-10-14,
  später am Tag: gegen eine gepatchte Kopie des Originals laufen die Fälle von `check.py`, siehe
  [BLECH auf Korgs Original 2.02](2026-10-14-stock-blech.md).
- Der Update-Ablauf selbst (Schreiben in den Flash, Neustart) mit Korgs Datei als Ziel: nicht geprüft,
  nur das Finden der Datei.
