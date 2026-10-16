# Effekt-Editor auf Korgs Original: Records live lesen und schreiben

Stand 2026-10-15. Kein Gerätezugriff, alles im Emulator gemessen (Korgs Original 2.02 mit dem Satz BLECH, zum Vergleich
Hacktribe 2.02 mit BLECH), über BLECHs eigene SysEx-Befehle ([BLECH SysEx](2026-10-15-blech-sysex.md)). Markierungen:
**gemessen** (ausgeführt), **hergeleitet**, **offen**.

## Was vorher im Weg stand

Der Editor las und schrieb Effekt-Records nur an Hacktribes Tabellen (`table.ifx`, `table.mfx`) und nur mit Hacktribes
Befehlen. Korgs Build hat beides nicht: die Records liegen verstreut und werden über zwei Zeigerfelder gefunden
([Preset-Tabellen](2026-10-15-preset-tabellen.md)), und mit BLECH gibt es Befehle, die dort lesen und schreiben, aber die
Schutztabelle der Firmware kannte nur Hacktribes Adressen und hätte jeden Schreibzugriff auf Korgs Records abgelehnt.

## Was jetzt geht

| Behauptung | Status | Beleg |
|---|---|---|
| Korgs Build hält seine 200 Records (100 Insert, 100 Master, 38 und 32 davon im Menü) in drei Läufen zu 0x20C Byte: 47 ab `0xC00A7F60`, 9 ab `0xC00AE124`, 144 ab `0xC00AF520`; die zwei Zeigerfelder stehen zwischen den Läufen | gemessen | `data/map/firmware.mjs` (`records`), `test/presets.test.mjs` (mit `E2_STOCK_VSB`: die Läufe sind genau die Records) |
| Der Editor findet den Record eines Platzes über das Zeigerfeld der geladenen Datei und prüft vorher, dass die Zeigerfelder im laufenden Gerät dieselben sind | gemessen | `pointersMatch` in `src/presets.mjs`, `test/emulator-blech-session.test.mjs` |
| Lesen, Schreiben mit Zurücklesen und Zurücknehmen eines Records laufen über BLECH auf Korgs Original im Emulator, in der Sitzung und über die Seite (Name geändert, aus dem RAM zurückgelesen, zurückgenommen) | gemessen | `test/emulator-blech-session.test.mjs`, `test/e2e/fx-stock.e2e.mjs` |
| Der Türsteher nimmt die Adresse eines Platzes nur an, wenn sie die ist, die das Zeigerfeld der Datei für ihn nennt, und nur in Korgs Records; ohne Adresse meint ein Record Hacktribes Tabelle und wird auf Korgs Gerät abgelehnt | gemessen | `test/blech-session.test.mjs` |
| Die Schutztabelle der Firmware ist je Build eigen. Eine für beide hätte Hacktribes Tabelle auf Korgs Build und Korgs Läufe auf Hacktribe freigegeben, ein Record hätte quer über zwei andere geschrieben werden können, und die Zeigerfelder wären überschreibbar gewesen | hergeleitet, mit Prüffall | `sysex:window_edges` (ein ganzer Record des anderen Rasters wird abgelehnt), `sysex:allows_declared`, beide Builds |
| Slots 101 bis 128 des Patches preset-tables sind live nicht beschreibbar (kein erklärter Bereich); sie gehen weiter nur in die Kopie der Datei | hergeleitet (Slots dort haben keinen erklärten Bereich, getestet ist die Sperre für andere Adressen) | `test/blech-session.test.mjs` |

## Entscheidungen

- **Tabelle je Build.** `blech-sysex.json` gilt für Hacktribe, `blech-sysex-stock.json` für Korgs Original; sie unterscheiden sich
  nur in `builds` und in der Tabelle (`src/sysex-table.mjs`, `protectTable({ build })`). Die Sitzung vergleicht die CRC der
  Tabelle im Gerät mit der ihres Builds.
- **Zustand und Puffer von BLECH SysEx liegen bei `0xC0191000` bis `0xC01A0000`**, weil die Preset-Tabellen `0xC0174000` bis
  `0xC017CC00` brauchen (die Prüfung der Speicherbereiche fand die Überdeckung beim Zusammenführen).
- **Warten statt Zurückfallen.** Ein Lesen der Seitenleiste hält die Sitzung oft gerade fest; wer ein Preset öffnet, sendet oder
  zurücknimmt, wartet darauf und versucht es erneut, statt die Kopie der Datei zu zeigen oder die Sendung scheitern zu lassen.
- **Pegel-Seite:** sie las Records an Hacktribes Adressen, auch auf Korgs Build; jetzt über denselben Weg wie der Editor.

## Offen

- Am Gerät ist nichts geprüft; Korgs Records sind dort an derselben Stelle zu erwarten, weil es dieselbe Firmware ist.
- Ob Korgs Firmware einen live geschriebenen Record beim nächsten Wählen des Presets neu aus ihren Daten lädt, ist am Emulator
  nicht beobachtet; die Seite liest ihn nach dem Senden zurück, der Klang ist damit nicht belegt.
