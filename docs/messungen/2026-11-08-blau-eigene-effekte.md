# Eigene Insert- und Master-Effekte auf der blauen Electribe 2: was es kostet

Stand 2026-11-08. Im Emulator und offline, kein Gerät, nichts gebaut außer einer Messprobe. Eingaben: Korgs `SYSTEM.VSB`
2.02 der blauen (sha256 `41fc5f1c...`), Korgs rotes Original 2.02 (`1d0f0689...`), die blaue Datei mit dem Satz
`blech-synth.json` (Stand develop `e5509017`). Markierungen: **gemessen** (ausgeführt, Befehl genannt), **hergeleitet**,
**geschätzt**, **offen**. Davor: [Preset-Tabellen](2026-10-15-preset-tabellen.md), [FX-Tabellen](2026-10-14-fx-tabellen.md),
[Katalog fest](2026-10-23-fx-katalog-fest.md), [Sammeldatei](2026-10-22-sammeldatei-karte.md), [Blaue Electribe](2026-10-15-blaue-electribe.md).

## Kurzfassung

1. **Die Effekte der blauen sind die des roten Korg-Originals.** Getter, Zeigerfelder, Recordgröße `0x20C`, alle 200
   Records (100 Insert, 100 Master) sind Platz für Platz byte-gleich, nur an anderen Adressen. Die DSP-Bausteine sind
   dieselben 66, mit gleichen Namen, Parametern, Vorgaben und Spannen. Der Satz "die blaue hat andere Bausteine" in
   [Katalog fest](2026-10-23-fx-katalog-fest.md) stimmt nicht; anders ist das DSP-Programm als Ganzes, nicht die
   Schnittstelle der Effekte.
2. **Ein Katalog-Record, in einen Platz der blauen gelegt, bootet und wird gespielt**: Menüs 48 und 40, der INSERT-Regler
   läuft durch und springt zurück, jeder der 18 Plätze schickt dem DSP dieselben Übertragungen wie auf dem roten Original,
   keine Assertion. Auch mit dem Satz `blech-synth.json`.
3. **Fast alles ist Adressarbeit.** Neu zu messen ist nur, was die Gerätekarte heute als Dateiabstand des Samplers führt
   (Menülängen, Getter), und der Klang am Gerät. Schätzung gesamt: 4 bis 5 Arbeitstage ohne Gerätetest.

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
| Die App lehnt die blaue für den Katalog ab ("Preset-Tabellen nicht erkannt") | gemessen | `appendPresets` auf der blauen Datei |

`same_dsp` vergleicht Befehl, Wortzahl und Daten und lässt eine durchgehende Verschiebung der Zieladressen zu
([MFX-Fälle](2026-10-10-mfx-umschalter.md)). Gleiche Übertragungen heißen also: dieselben Werte an dieselben Stellen
des Effekts, nicht derselbe Klang.

## Was es braucht, je Stück

| Stück | Art | Status | Aufwand (geschätzt) |
|---|---|---|---|
| `preset-tables` für die blaue: Builder bekommt `--build synth`, 11 Orte (2 Getterliterale, 4 Klemmbefehle, 5 Reglerliterale) über `synthaddr`, dazu neue Einträge in `data/synth-map/` für die Orte, die `fwmap` findet; `preset_cases.py` auf die blaue | nur Adressen | in der Probe gemessen | 0,5 Tag |
| Gerätekarte und `src/presets.mjs` je Build: Getter, Klemme, 13 Stellen der Insert-Menülänge, Zeilenlänge, Master-Stelle für die blaue; danach findet `locatePresets` die Felder und `fx-append.mjs` arbeitet ohne Änderung | nur Adressen, aber die Karte kennt heute nur Dateiabstände des Samplers | hergeleitet | 1 Tag mit Tests |
| `fx-catalog` und `preset-tables-synth` in `blech-synth.json` | Satz | hergeleitet | in den beiden oben |
| Sammeldatei `e2sFx.all` laden (`fx_card.s`): Getter und Zähler sind in der Karte, `FS_*` und die Orte von `fx_reapply` (Pattern, Part-Bearbeitung, [Effekte beim Start](2026-11-05-effekte-start-splash-liste.md)) hat die Laufzeit der blauen schon; neu sind `FX_BUILD` für die blaue, `FX_MODS` `0xC00C1E64` als Eintrag, `fx_card.s` statt `script_fx_none.s`; `src/fx-collection.mjs` bekommt den Build und die Lage der Modulationstabelle | nur Adressen | Adressen gemessen, Lader nicht gelaufen | 1 Tag mit `fx_card_cases.py` auf der blauen |
| EXPORT ALL EFFECTS: steht in `fx_card.s` (`menu_export_fx`), kommt mit dem Lader; dazu das Bit der Seite in `DU_BUILT` der blauen (heute 3, die Effekte fehlen) | nur Adressen | hergeleitet | in dem Tag oben |
| Effekt-Editor der App: der Weg für Korgs rotes Original (über die Zeigerfelder) trägt die blaue, sobald `locatePresets` sie findet; Freigabe in `FEATURES.synth` und der Seite, Browser-Tests | wenig neu | hergeleitet | 1 bis 2 Tage |
| Klang am Gerät, Live-Bearbeitung über SysEx (die blaue hat keine Befehle `0x52` bis `0x57` von Hacktribe) | Gerätetest, Live-Weg neue Arbeit | offen | Gerätetest offen; Live-Weg nicht geschätzt |

Kein Stück braucht neue DSP-Arbeit oder neue Bausteine: die Bausteine sind dieselben, und die Records des Katalogs
entstehen aus Werks-Records, die in beiden Firmwares gleich sind.

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
