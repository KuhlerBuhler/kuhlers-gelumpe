# Eigene Insert- und Master-Effekte auf der blauen Electribe 2: Port im Emulator

Stand 2026-11-08. Im Emulator und offline, kein Gerät. Eingaben: Korgs `SYSTEM.VSB` 2.02 der blauen (sha256 `41fc5f1c...`),
Korgs rotes Original 2.02 (`1d0f0689...`), Hacktribe 2.02 (`7cb4825c...`) und dieselbe Datei mit dem Kopf der blauen
(`2b2e1c2f...`, wie im Workflow `verify-patches`). Markierungen: **gemessen** (ausgeführt, Befehl genannt), **hergeleitet**,
**offen**. Davor: [was es kostet](2026-11-08-blau-eigene-effekte.md), [Preset-Tabellen](2026-10-15-preset-tabellen.md),
[Sammeldatei](2026-10-22-sammeldatei-karte.md), [Effekte beim Start](2026-11-05-effekte-start-splash-liste.md).

## Kurzfassung

Der Satz `blech-synth.json` bringt `preset-tables` und `fx-catalog` auf die blaue: Menüs 48 Insert und 40 Master, die
Sammeldatei `e2sFx.all` lädt beim Start, EXPORT ALL EFFECTS schreibt sie, und der Effekt-Editor der App liest und schreibt
die blaue Datei wie Korgs rote. Jeder neue Platz schickt dem DSP dieselben Übertragungen wie auf der roten Datei. Der Klang
am Gerät ist offen.

## Neue Adressen

Alle stehen in `data/synth-map/preset-tables.json`, je mit Beleg im Feld `why`. Gefunden mit `fwmap.py` (rot gegen blau,
siehe [was es kostet](2026-11-08-blau-eigene-effekte.md)); an jeder Stelle steht in der blauen dasselbe Befehlswort wie in der
roten (gemessen, Wort für Wort gelesen).

| Sampler (rot) | blau | was |
|---|---|---|
| `0xC00981B4` | `0xC00857AC` | fünftes Literal des Reglergedächtnisses |
| `0xC0098084` | `0xC008567C` | Zeilenlänge des Insert-Menüs |
| `0xC009809C`, `0xC00980E8`, `0xC00980EC`, `0xC009811C`, `0xC0098138`, `0xC009814C`, `0xC0098150`, `0xC0098188`, `0xC0098194` | `0xC0085694`, `0xC00856E0`, `0xC00856E4`, `0xC0085714`, `0xC0085730`, `0xC0085744`, `0xC0085748`, `0xC0085780`, `0xC008578C` | Stellen der Insert-Menülänge (38 und 37) |
| `0xC0048F80`, `0xC0049EF0`, `0xC004A1F8` | `0xC0043140`, `0xC004400C`, `0xC00442F8` | Stellen der Insert-Menülänge außerhalb des Menüs |
| `0xC00D81EC` | `0xC00C1E64` | Modulationstabelle, 72 Records zu `0x58` (`FX_MODS`) |

Dazu ohne Eintrag in der Karte, weil sie Adressen der blauen selbst sind: Insert-Feld `0xC009898C`, Master-Feld
`0xC0099D88` (`data/map/firmware.mjs`, Build `synth`), Reglergedächtnis `0xC056C3A0` (`tools/patch/preset_tables.py`).
Die Flächen des Patches (`0xC0174000` bis `0xC017CC00`) sind in der blauen frei wie in der roten.

## Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| `preset-tables-synth.json` aus Korgs blauer gebaut; rote und Hacktribe-Varianten neu gebaut sind byte-gleich mit den alten | gemessen | `tools/patch/preset_tables.py` je Build, `git diff` leer für die zwei alten Dateien |
| `src/presets.mjs` findet auf Korgs blauer 38 und 32, Kapazität 100; auf der blauen mit Satz 48 und 40, Kapazität 128; rot und Hacktribe unverändert | gemessen | `node --test test/presets.test.mjs` (12 von 12) und `locatePresets`/`presetRoom` auf den Dateien |
| `preset_cases.py` auf der blauen mit Satz: Werks-Presets unverändert, Getter bis 127, Reglergedächtnis im Patch, INSERT-Regler läuft 50 Schritte durch 48 und springt zurück, Master-Setter nimmt 0 und 39, EXIT beim Start, 10 Insert- und 8 Master-Plätze mit eigenem Record und Namen | gemessen | `tools/emu/preset_cases.py cases --base BLAU --patched BLAU-BLECH`, 12 von 12 |
| Jeder neue Platz schickt dem DSP dasselbe wie auf der roten Datei mit `blech.json`: Insert 39 bis 48 je 14 Übertragungen, Master 33 bis 40 je 11, `same_dsp` wahr, keine Assertion, Menüs 48/48 und 40/40 | gemessen | `tools/emu/blue_red_dsp.py --red ROT-BLECH --blue BLAU-BLECH` |
| `e2sFx.all` lädt beim Start (Kopf Build 3): Insert, Master, Modulation im RAM, die übrigen Records wie die Firmware, Flash wie ohne Datei | gemessen | `tools/emu/fx_card_cases.py cases --patched BLAU-BLECH`, 22 von 22 |
| Fehlende Datei, falsche Prüfsumme, falscher Build, Index hinter dem Menü, abgeschnittene Datei: nichts geladen, Records wie die Firmware | gemessen | dieselben Fälle `refused_*` |
| EXPORT ALL EFFECTS: schreibt RAM in die geladene Datei (Texte bleiben), ohne Datei eine neue mit 160 Einträgen (48 Insert, 40 Master, 72 Modulation); der nächste Start lädt sie; eine nicht geladene oder geänderte Datei bleibt stehen | gemessen | dieselben Fälle `export_*` |
| Die Effekte der Datei gehen beim Start an den DSP (Insert und Master), VERSION zeigt `KORG BLUE FX`, `FX fw?`, `FX bad` | gemessen | dieselben Fälle `boot_*`, `version_*` |
| Mit EXIT beim Start lädt die blaue nichts: ihr Startwrapper überspringt BLECH ganz, der Status bleibt leer | gemessen | `exit_held` |
| Die Datei, die der Editor baut (`src/fx-collection.mjs`, Build `synth`), lädt im Emulator und kommt nach EXPORT gleich zurück | gemessen | `E2_EMU_REQUIRED=1 E2_VSB=BLAU node --test test/emulator-fxcard.test.mjs` |
| Editor offline: die App erkennt die blaue (Build `synth`), findet die Felder, `addPreset` und `appendPresets` arbeiten wie auf der roten (38 auf 39, 18 Katalogeinträge) | gemessen | `identify`, `locatePresets`, `addPreset`, `appendPresets` auf beiden Dateien |
| check.py auf rot, blau, Hacktribe und Hacktribe mit blauem Kopf | gemessen | siehe unten |
| Live-Bearbeitung über SysEx auf der blauen | offen | `stockReady` verlangt Build `stock`; die blaue bleibt dort außen vor |
| Klang am Gerät | offen | keine blaue verfügbar |

## Zwei Fehler, im Emulator gefunden

- Der Startwrapper der blauen (`tools/patch/script_start_synth.s`) rief den Lader `fx_card_load` nicht auf; mit ihm läuft er
  an derselben Stelle wie auf der roten, hinter `script_card_load`.
- `fx_card_cases.py` lief auf der blauen mit den Menüzahlen der roten (`menu_cases.for_build` fehlte) und stürzte bei
  EXPORT ALL EFFECTS ab.

## check.py

`npm run verify:patches -- --cases menu_cases,fx_card_cases,preset_cases,mfx_cases ROT BLAU HACKTRIBE HACKTRIBE-BLAU`
mit `GELUMPE_NODE_RESULTS=strict`: die Startszenarien und die Fälle der vier Module, jede Datei mit ihrem Satz wie in der App
(gemessen, keine Fehler).

| Eingabe | Satz | Prüfungen |
|---|---|---|
| Korg rot 2.02 | `blech.json` | 262 bestanden |
| Korg blau 2.02 | `blech-synth.json` | 252 bestanden |
| Hacktribe 2.02 | `blech.json` | 262 bestanden |
| Hacktribe mit blauem Kopf | `blech.json`, `--hardware blue` | 263 bestanden |

Der volle Lauf aller Fälle steht aus und läuft im Workflow `verify-patches` des Pull Requests.
