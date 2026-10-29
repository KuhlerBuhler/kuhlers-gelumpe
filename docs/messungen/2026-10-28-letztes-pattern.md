# Letztes Pattern beim Einschalten (Idee 76)

Stand 28.10.2026, Emulator mit Hacktribe 2.02 und Korgs Original 2.02 (rot). Am Gerät gelesen (nur lesend, BLECH READ):
die Globals im RAM. Zu [Idee 76](../ideen/76-letztes-pattern.md), Patch `data/patches/last-pattern.json`.

## Wo die Firmware beim Start Pattern 001 nimmt

| Befund | Marker |
|---|---|
| Die Globals (256 Byte) werden beim Start aus dem Flash geladen (`0xC004BEE0` → `0xC002A0F8`), bevor ein Pattern geladen wird; die laufende Kopie liegt hinter dem Zeiger `0xC0691324` (bei Hacktribe `0xC06A2A90`) | gemessen (Emulator) |
| Die Startfunktion lädt Pattern 0 in den Bearbeitungspuffer: `mov r1, #0` bei `0xC002AF40`, dann `0xC004A350` und `0xC004AB84(obj, pattern, 0)` | gemessen (Emulator) |
| Kurz danach wählt ein Befehl Pattern 0 über `0xC0079DB4` (Aufruf aus `0xC0036FA0`, Nummer aus der Nachricht, nicht aus der Startfunktion); dieselbe Funktion nimmt jede Patternwahl am Rad, klemmt die Nummer auf 0 bis 249 und lädt das Pattern | gemessen (Emulator) |
| Nur `0xC002AF40` umgestellt: der Befehl wählt danach wieder 001. Beide umgestellt: das Display zeigt 006 | gemessen (Emulator) |
| Die Samples hängen nicht am ersten Pattern: die Sample-Datei wird vorher ganz geladen | gemessen (Boot-Messung 2026-10-08) |

## Wo die Nummer bleibt

| Befund | Marker |
|---|---|
| Globals-Bytes 44 bis 251 sind am roten Gerät alle 0 (252 bis 255 sind "GLED"); kein Menüpunkt erreicht sie (`data/map/global.mjs`) | gelesen (Gerät) |
| Byte 248 im RAM gesetzt, ausgeschaltet (Fenster "Power Off", Speichern über `0xC004C1B4`), neu gestartet: das Byte ist wieder da | gemessen (Emulator) |
| Der Patch schreibt weder den Flash noch die Karte: die Firmware speichert die Globals beim Ausschalten und bei WRITE im Global-Menü ohnehin | offline (Code) |

## Der Patch

- `0xC002AF40` ruft `lp_boot`: Nummer aus Byte 248 minus 1 (0 heißt: keine gemerkt, dann 001), Merker in Byte 249.
- `0xC0079DC8` (das `mov r4, r0` hinter dem Klemmen) ruft `lp_select`: die erste Wahl mit Merker nimmt die gemerkte
  Nummer und löscht den Merker; jede Wahl schreibt ihre Nummer plus 1 in Byte 248.
- Mit EXIT beim Einschalten: Start mit 001, keine Wahl merkt sich etwas, beim nächsten Start ohne EXIT kommt das
  gemerkte Pattern.
- Code 160 Byte bei `0xC014FE00`, im `FF`-Lauf `0xC0148880` bis `0xC0150000`, den kein anderer Patch nutzt.

## Fälle (`tools/emu/last_pattern_cases.py`)

| Fall | Hacktribe | Korg rot |
|---|---|---|
| erster Start ohne gemerkte Nummer: 001 | ja | ja |
| Rad +5, aus, an: 006 | ja | ja |
| Rad -2, aus, an mit EXIT: 001 | ja | ja |
| danach aus, an: 004 | ja | ja |

## Offen

- Am Gerät nicht geprüft.
- Blaue Electribe (Synth): gebaut (`data/patches/last-pattern-synth.json`). Die blaue lädt beim Start Pattern 0 bei `0xC0028104` und ruft danach von sich aus keine Patternwahl auf; ihre Nummer steht in `0xC0583668 + 0x318` (r0 der Wahl `0xC006C740`, Emulator). `lp_boot` trägt die gemerkte Nummer dort ein, darauf wählt die Firmware sie selbst, und der Merker gibt der Wahl die Nummer. Die fünf Fälle grün mit Korgs blauem 2.02.
- Ein Menüpunkt zum Abschalten gibt es nicht; wer 001 will, hält EXIT oder nimmt den Patch im Patcher raus.
