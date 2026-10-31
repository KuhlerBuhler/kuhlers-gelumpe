# Alten Kartenordner beim ersten Start übernehmen, blaue Electribe (29.10.)

Stand 2026-10-29. Alles im Emulator mit Korgs blauer 2.02 (`41fc5f1c`), Korgs roter (`1d0f0689`) und Hacktribe
(`7cb4825c`), die Dateien außerhalb des Repositorys. **Am Gerät nichts.** Vorgeschichte: [rote Fassung](2026-10-19-ordner-uebernehmen.md),
[Kartenordner der blauen](2026-10-26-blech-hacktribe-blau.md).

Marker: **gemessen** (ausgeführt), **hergeleitet** (aus Code geschlossen).

## Belegtabelle

| Behauptung | Marker | Beleg |
|---|---|---|
| `f_getfree` `0xC008B3B4`, `new` `0xC0026240`, `delete` `0xC0026248`, Bereich-markieren `0xC0010BD8` sind die Funktionen des Samplers (`0xC009E85C`, `0xC0028DCC`, `0xC0028DD4`, `0xC001531C`) | gemessen | `fwmap.py --ref ROT --vsb BLAU`: je "same code: True" (16 maskierte Wörter) |
| `f_mkdir` `0xC008B510`, Bildspeicher `0xC031B310` | gemessen | schon in `data/synth-map/` (`script-runtime.json`, `auto.json`) |
| Der Synth-Starthaken `0xC0028170` läuft in `main` vor dem Start des Schedulers (`0xC0028208` `bl 0xC00005A0`): dort zählt der OS-Tick nicht, `OS_WAIT` kehrt nie zurück | gemessen | Disassembly `0xC0028150` bis `0xC0028210`; Tick-Zähler `0xC0573CE8` steht bei 1, bis der Haken zurückkehrt (erster Tick 308 ms, Haken 286 ms); mit wartender Frage nie |
| Vor dem Scheduler kommen Tasten nicht beim Eingangshaken an, wenn der Haken nicht wartet | gemessen | Haken `0xC00257E8`, 0 Treffer in 800 ms Busy-Wait mit gedrückter Taste |
| `0xC001168C(0xC031BB2C, 2, 0)` und `(…, 3, 0)` schicken den Bildspeicher ans Display; so macht es Korgs PCM-Lader für seinen Balken (`0xC0056EA8`, `0xC0046EFC`) und der Rahmen (`0xC0073D10`) | gemessen | Aufrufe von `0xC001168C` mit LR im Emulator protokolliert |
| Korgs blaue legt in `KORG/electribe/` die Ordner `PatternSet`, `Audio`, ` Project` und `System` an | hergeleitet | Strings `0xC0090503`, `0xC008F692`, `0xC008F66E`, `0xC00904FC`; welcher Pfad wann geschrieben wird, nicht gemessen |

## Der Patch

Gleiches `script_migrate.s` wie auf der roten, mit `MG_BLUE 1`:

- Bedingung: `SD:KORG/blechtribe` lässt sich als Ordner nicht öffnen, `SD:KORG/electribe` schon. Die blaue hat keine
  `e2sSample.all`, nach der man fragen könnte; Patterns liegen im Flash, auf der Karte stehen nur Exporte und die
  Update-Datei. Sobald BLECH `KORG/blechtribe` selbst anlegt (WRITE im Menü, Plugin, Export), kommt die Frage nicht mehr.
- Der Starthaken fragt nicht selbst (vor dem Scheduler geht kein Warten): er stellt die Frage nur auf (`MG_ACTIVE 1`,
  Wahl 2 `ELECTRIBE`) und der Start läuft weiter bis zum Hauptbildschirm. Der Rahmenhaken (UiTask) legt die Frage darüber
  und nimmt EXIT und MENU (`mg_blue_key`), der Eingangsfilter schluckt wie auf der roten alle anderen Tasten.
- MENU kopiert im UiTask: derselbe Platz-Check und dieselbe Kopie, das Display bekommt Fortschritt und Ergebnis direkt
  über `0xC001168C`, weil der UiTask währenddessen nicht zeichnet. Danach setzt BLECH `UI_REDRAW`, die Firmware zeichnet
  ihren Bildschirm neu.
- Text: `COPY YOUR FILES?` statt `COPY YOUR SAMPLES?`, Ordner `ELECTRIBE`. Kopiert wird alles, auch `System/SYSTEM.VSB`
  (dort sucht BLECHs eigenes Update danach).
- Arbeitsbereich wie auf der roten `0xC0190100`, 0xF00 Byte; im Synth-Satz frei (nächster Patch `blech-sysex-synth` ab `0xC0191000`).

## Emulator (`tools/emu/migrate_cases.py`)

| Firmware | Ergebnis |
|---|---|
| Korg blau + `blech-synth.json` | 9 von 9: MENU kopiert alles außer `._junk` (Frage auf dem Display über Bildschirm 1, danach Bildschirm der Firmware), EXIT schreibt nichts, Rad und WRITE tun nichts, `KORG/blechtribe` schon da: keine Frage, EXIT beim Einschalten: keine Frage, leere Karte: keine Frage, 64 KiB frei: CARD FULL, 1 MiB frei: kopiert, nur `System/SYSTEM.VSB`: fragt und kopiert |
| Korg rot + `blech.json` | 10 von 10 |
| Hacktribe + `blech.json` | 10 von 10 |
| Hacktribe + `blech.json`, leerer Flash der blauen | 10 von 10 |

`check.py --quick` mit dem blauen Satz: 22 von 22.

## Offen, für den Gerätetest

- Ob die Frage am Gerät nach dem Start sichtbar ist und MENU/EXIT annimmt.
- Wie lange das Kopieren einer echten Karte dauert, und ob ein minutenlang blockierter UiTask am Gerät etwas auslöst
  (Watchdog, MIDI, Audio). Im Emulator nicht messbar.
- Ob nach DONE oder EXIT der Hauptbildschirm vollständig neu gezeichnet wird.
