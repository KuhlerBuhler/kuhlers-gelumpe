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
  Kopf, Build, jeder Eintrag (Art, Platz kleiner als die Menülänge, Datensatzlänge), Gesamtlänge, CRC-32; geschrieben wird
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
| Vom Editor gebaute Datei (Master 1, Modulation 6) lädt Byte für Byte | ja | ja |

## Offen

- Ob ein Pattern, das schon beim Start geladen ist, das geänderte Preset sofort hört oder erst nach erneuter Wahl. Der
  Lader läuft nach dem Sample-Lader; wann das Pattern seine Effekte einrichtet, ist nicht gemessen.
- Ob geänderte Vorgaben einer Modulation (Tiefe, Tempo) greifen: laut Gerätekarte füllt die Tabelle beim Einschalten den
  Speicher je Part; der Lader läuft danach. Erwartung: erst wenn die Modulation neu gewählt wird.
- Neue Plätze über die Menülänge hinaus legt die Datei nicht an; sie überschreibt nur vorhandene.
- Blau: nicht gemessen, der Lader ist nur im roten Satz.
