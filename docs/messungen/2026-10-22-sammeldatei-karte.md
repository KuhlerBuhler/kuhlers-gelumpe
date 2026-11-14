# Presets und Modulationen von der Karte (e2sFx.all)

Stand 22. Oktober 2026. Gemessen im Emulator (`tools/emu/fx_card_cases.py`, `test/emulator-fxcard.test.mjs`) mit der
eigenen Hacktribe-2.02-Datei und Korgs Original 2.02 (rot), jeweils mit dem BLECH-Satz. **Am Gerät nicht geprüft.**

## Was gebaut ist

- `src/fx-v2.mjs`: `.e2fx` Version 2. Art, Name, je Stufe der Baustein (Unit-ID) mit Parametern nach Namen, die
  Steuerung; eine Modulation mit Name, Tiefe, Tempo, Kurve und fünf Slots. Kein Firmware-Byte darin. Version 1 wird
  weiter gelesen und nach v2 umgesetzt.
- `src/fx-collection.mjs`: die Sammeldatei `KORG/blechtribe/Presets/e2sFx.all`. Jeder Eintrag trägt seinen v2-Text und den
  Datensatz für den Build, für den die Datei gebaut ist. Der Datensatz entsteht aus dem Datensatz der Firmware an diesem
  Platz; ein anderer Baustein kommt aus einem Spender-Preset derselben Firmware mit diesem Baustein in derselben Stufe.
- `tools/patch/fx_card.s`: der Lader in der Plugin-Laufzeit, direkt nach dem Plugin-Lader beim Start. Erster Durchgang:
  Kopf, Build, jeder Eintrag (Art, Platz bis 100, Datensatzlänge), Gesamtlänge, CRC-32; geschrieben wird
  nichts. Nur eine Datei, die das besteht, wird ein zweites Mal gelesen, und ihre Datensätze gehen dorthin, wohin die
  Getter der Firmware zeigen (`0xC003E738`, `0xC003E750`), die Modulationen in die Tabelle, die der Build liest
  (Hacktribe `0xC019FFFC`, Korg `0xC00D81EC`). Zustand in `0xC01F7FE0` (Status, Zahl der Einträge).

## Ergebnis (gemessen im Emulator)

| Fall | Hacktribe | Korg rot |
|---|---|---|
| Gute Datei: Insert 2, Master 1, Modulation 4 im RAM wie in der Datei | ja | ja |
| Ein Preset, das die Datei nicht nennt, bleibt | ja | ja |
| Flash nach dem Start gleich wie ohne Datei | ja | ja |
| Datei fehlt, Prüfsumme falsch, falscher Build, Platz 251, abgeschnitten: nichts geändert | ja | ja |
| EXIT beim Einschalten: nichts geändert | ja | ja |
| Insert auf Platz 100 und Master hinter dem Menü (14.11.): Menüs wachsen auf 100 und 49, alle 15 Längen-Stellen gleich, Knopf-Speicher 16 Zeilen à 100, Encoder läuft durch alle 100 und die leeren Plätze, Platz 100 schickt dem DSP dasselbe wie Preset 6, Flash unverändert | ja | ja |
| Platz 101: abgelehnt, Menüs bleiben; Datei nur mit Plätzen im Menü: Menüs bleiben | ja | ja |

## Plätze hinter dem Menü (14.11.)

Die App lässt Plätze bis 100 wählen (`collectionEntry` prüft nur `recordOf`). Bis 1.4.5 lehnte der Lader jeden Platz ab der
Menülänge ab, die ganze Datei wurde "FX bad" (gemeldet mit IFX 59 und 60 bei 59 Inserts). Mit dem BLECH-Satz hat jeder der
Plätze 1 bis 100 einen eigenen Datensatz (gemessen auf Hacktribe und Korg rot, `preset_tables.py`: 100 Zeiger der Firmware,
erst 101 bis 128 zeigen auf Eintrag 0). Jetzt:

- Erster Durchgang: Platz bis 100 geht durch, wenn beide Getter-Klammern 127 sind (Preset-Tabellen da) und alle 15
  Stellen der Menülänge (`fx_sites` in `fx_card.s`: 8 Anzahl, 6 letzter Index, 1 Master) den Befehl und die Länge tragen,
  die die Firmware hat. Sonst wie bisher "FX bad".
- Nach dem zweiten Durchgang (`fx_grow`): jede Stelle bekommt die neue Länge im RAM, nie kürzer. D-Cache-Zeile reinigen
  (`c7, c10, 1`), Schreibpuffer leeren, I-Cache leeren, dann Knopf-Speicher neu (`0xC00980AC`) und je Part der Wert
  zurück (`0xC009816C`), danach wie bisher `fx_reapply`. Im Flash ändert sich nichts, nach dem Ausschalten liest der Start
  die Datei wieder.
- Am Gerät noch nicht gemessen (Cache-Befehle laufen am Gerät im Doom-Lader, `2026-10-22-doom-am-geraet.md`).
| Vom Editor gebaute Datei (Master 1, Modulation 6) lädt Byte für Byte | ja | ja |

## Offen

- Ob ein Pattern, das schon beim Start geladen ist, das geänderte Preset sofort hört oder erst nach erneuter Wahl. Der
  Lader läuft nach dem Sample-Lader; wann das Pattern seine Effekte einrichtet, ist nicht gemessen.
- Ob geänderte Vorgaben einer Modulation (Tiefe, Tempo) greifen: laut Gerätekarte füllt die Tabelle beim Einschalten den
  Speicher je Part; der Lader läuft danach. Erwartung: erst wenn die Modulation neu gewählt wird.
- Blau: nicht gemessen, der Lader ist nur im roten Satz.
