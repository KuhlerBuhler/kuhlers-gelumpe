# Eigene Insert- und Master-Effekte auf der blauen Electribe 2: was es kostet

Im [Emulator](../glossary.md#emulator) und offline, kein Gerät. Eingaben: Korgs `SYSTEM.VSB`
2.02 der blauen (sha256 `41fc5f1c...`), Korgs rotes Original 2.02 (`1d0f0689...`), die blaue Datei mit dem Satz
`blech-synth.json` (Stand develop `e5509017`). Markierungen: **gemessen** (ausgeführt, Befehl genannt), **hergeleitet**,
**offen**. Siehe auch: [Preset-Tabellen](2026-10-15-preset-tabellen.md), [FX-Tabellen](2026-10-14-fx-tabellen.md),
[Sammeldatei](2026-10-22-sammeldatei-karte.md), [Blaue Electribe](2026-10-15-blaue-electribe.md).

## Kurzfassung

1. **Die Effekte der blauen sind die des roten Korg-Originals.** Getter, Zeigerfelder, Recordgröße `0x20C`, alle 200
   Records (100 Insert, 100 Master) sind Platz für Platz byte-gleich, nur an anderen Adressen. Die DSP-Bausteine sind
   dieselben 66, mit gleichen Namen, Parametern, Vorgaben und Spannen. Anders ist das [DSP](../glossary.md#dsp)-Programm als Ganzes, nicht die Schnittstelle der Effekte.
2. **Ein Katalog-Record, in einen Platz der blauen gelegt, bootet und wird gespielt**: Menüs 48 und 40, der INSERT-Regler
   läuft durch und springt zurück, jeder der 18 Plätze schickt dem DSP dieselben Übertragungen wie auf dem roten Original,
   keine Assertion. Auch mit dem Satz `blech-synth.json`.
3. **Fast alles ist Adressarbeit.** Neu zu messen ist nur, was die Gerätekarte als Dateiabstand des Samplers führt
   (Menülängen, Getter), und der Klang am Gerät.

## Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| Insert-Getter `0xC00391AC`, Master-Getter `0xC00391C4`, Code gleich dem roten (`0xC003E738`, `0xC003E750`), Klemme 99 | gemessen | 20 Byte je Getter verglichen, Klemmwort `0x23A00063` in beiden |
| Zeigerfeld Insert `0xC009898C`, Master `0xC0099D88`, je 100 verschiedene Einträge | gemessen | Literale `0xC00391C0`, `0xC00391D8` gelesen |
| Records in drei Läufen wie bei Korg rot: 47 ab `0xC0092958`, 9 ab `0xC0098B1C`, 144 ab `0xC0099F18`, Felder dazwischen | gemessen | Zeiger beider Felder sortiert |
| Recordgröße und Aufbau gleich; alle 100 Insert- und 100 Master-Records Platz für Platz byte-gleich mit Korg rot | gemessen | SHA-Vergleich je Platz, 100 von 100 je Feld; 38 Insert- und 32 Master-Presets mit gleichen Namen |
| Bausteine in den Werks-Presets: Stufe 1 dieselben 16 Unit-IDs, Stufe 2 dieselben 3, Master dieselben 18 wie rot | gemessen | Gerätebyte jeder Stufe |
| DSP-Strom der blauen bei `0xC00DFB80`, `0x41C74` Byte; Deskriptoren bei DSP `0x4C74` (rot `0x4C30`) | gemessen | Bootblöcke verkettet (Kopf `0xAD`, XOR 0), SDRAM wie `tools/fx-tables.py` aufgebaut |
| Alle 66 Deskriptoren gleich: Name, Parameterzahl, je Parameter Name, Vorgabe, Minimum, Maximum, Flags | gemessen | 66 von 66; 44 mit Parametern |
| Was die Bausteine im DSP rechnen, ist gleich | offen | das DSP-Programm ist nicht disassembliert; Klang nur am Gerät |
| Die 18 Katalog-Records, für die blaue gebaut, sind byte-gleich mit denen für rot | gemessen | `tools/emu/blue_fx_records.mjs` red und blue, 18 von 18 |
| Modulationstabelle (72 Records zu `0x58`) liegt bei `0xC00C1E64`, gleich der roten `0xC00D81EC` | gemessen | 72 von 72 gleich (das erste Wort vor dem ersten Namen gehört nicht zur Tabelle, wie bei rot), Lader im Code bei `0xC0086180` und `0xC00868DC` zeigen auf `+4` |
| Die Flächen von `preset-tables` (`0xC0174000` bis `0xC017CC00`) sind in der blauen mit `blech-synth.json` gelöscht | gemessen | FF geprüft |
| Reglergedächtnis des Insert-Effekts bei `0xC056C3A0` (rot `0xC0692278`), fünf Literale ab `0xC00856A0`, gleiche Abstände wie rot | gemessen | Wortsuche, 5 Treffer in beiden |
| Von den 15 Stellen der Menülängen hat `data/synth-map/` nur die zwei bei `0xC0039BFC` und `0xC0039C04`; die übrigen 12 und die Zeilenlänge findet `fwmap.py` (11 mit gleichem Code, 2 nur am Ort; ebenso das fünfte Reglerliteral) | gemessen | `fwmap.py --ref ROT --vsb BLAU ...`, jede Stelle trägt das erwartete Byte (38, 37, 32) |
| Port von `preset-tables` und Katalog auf Korgs blaue: Menüs 48 und 40, INSERT-Regler läuft durch und springt zurück, Namen der neuen Plätze aus den Gettern, je Insert-Platz 14 und je Master-Platz 11 Übertragungen, gleich der roten Datei mit denselben Schritten (`same_dsp`), keine Assertion | gemessen | `tools/emu/blue_fx_probe.py --vsb BLAU --records blau.json --compare ROT rot.json` |
| Dasselbe auf der blauen mit `blech-synth.json` | gemessen | `blue_fx_probe.py --vsb BLAU-BLECH --records ...`, gleiche Zahlen, keine Assertion |

`same_dsp` vergleicht Befehl, Wortzahl und Daten und lässt eine durchgehende Verschiebung der Zieladressen zu
([MFX-Fälle](2026-10-10-mfx-umschalter.md)). Gleiche Übertragungen heißen also: dieselben Werte an dieselben Stellen
des Effekts, nicht derselbe Klang.

## Was die Probe tut

`tools/emu/blue_fx_probe.py` baut nur im Speicher, was ein Port schreiben würde: neue Zeigerfelder zu 128 und das
Reglergedächtnis an den Adressen von `preset-tables` (in der blauen frei), Literale und Klemmen der Getter, die fünf
Reglerliterale und die Menülängen an den Orten der blauen, die Records aus `tools/emu/blue_fx_records.mjs` in die
unbenannten Plätze 39 bis 48 und 33 bis 40. An jedem Ort prüft sie den erwarteten Befehl oder Wert. Dann startet sie die
Maschine, liest Zähler und Namen über die Getter, dreht den INSERT-Regler einmal ganz durch und wählt jeden neuen Platz,
dazu Insert 2 und Master 2 zum Vergleich. Mit `--compare` macht sie dasselbe auf der roten Datei. Es geht keine
Firmware ins Repository, die Records bleiben im Arbeitsordner.

## Offen

- Klang am Gerät (keine blaue verfügbar), wie bei allen Katalogeinträgen.
- Ob das DSP-Programm der blauen die Bausteine gleich rechnet: gleiche Deskriptoren und Übertragungen sprechen dafür, ein
  Beweis ist es nicht.
- Der Lader `fx_card.s` und EXPORT ALL EFFECTS sind auf der blauen nicht gelaufen; nur ihre Adressen sind gefunden.
- Live-Bearbeitung der Effekte über SysEx: die blaue hat die Befehle `0x52` bis `0x57` von Hacktribe nicht.
