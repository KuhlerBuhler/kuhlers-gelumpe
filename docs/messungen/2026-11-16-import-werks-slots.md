# IMPORT SAMPLE auf Werks-Slots

16.11.2026, Firmware 2.02 rot (Korg) und Hacktribe, **gemessen im Emulator** und **offline** aus
dem Code gelesen. Am Gerät nicht gemessen. Patch: `tools/patch/import_slots.py`, Fälle:
`tools/emu/import_slots_cases.py`.

## Der Zielwähler

DATA UTILITY > IMPORT SAMPLE fragt nach der Datei das Ziel ab (SELECT DESTINATION). Der Wähler
liegt bei `0xC006A224`, der Wert steht in `0xC00F9CCC` und ist die angezeigte Nummer, der Slot ist
die Nummer minus 1. **offline**

Die Bereichsprüfung sind sieben Befehle ab `0xC006A23C`: `cmp r1, #500`, darunter plus 499 (in zwei
Teilen `0x1F0` und 3), dann `cmp r1, #1000`, darüber minus 499. Der Wähler läuft also nur von 501
bis 999 und springt an beiden Enden um. Korgs rote Firmware und Hacktribe haben an dieser Adresse
dieselben Bytes. Die blaue (Synth) hat kein IMPORT SAMPLE. **offline**

## Was der Import selbst annimmt

Der Import (Funktion `0xC004EDF0`, aufgerufen von `0xC003629C`) liest pro Slot das Halbwort bei
`0xC047B08C + Slot * 32 + 0x12`, die Wave-Nummer des Slots. Ist sie 49 (`0x31`) oder kleiner,
lehnt er den Slot mit Code 36 (`0x24`) ab, das Gerät zeigt dann "Error / Unknown Error.". **offline**

Im Emulator, Wert in `0xC00F9CCC` direkt gesetzt und den Import ausgelöst: **gemessen**

| Firmware | abgelehnte Slots | erste Nummer, die geht |
|---|---|---|
| Korg rot | 0 bis 17 (DSP-Wellen und Audio-Eingänge) | 19 |
| Hacktribe | 0 bis 273 (dazu die Synth-Wellen von Hacktribe) | 275 |

Ab dieser Nummer nimmt der Import jeden Slot. Ziel 100 auf Korg rot: Slot 99 heißt danach
"Kick" (der Name der WAV). Ziel 19 auf Korg rot: aus "Hippy" wird "Kick". Ziel 275 auf Hacktribe:
aus "Sample275" wird "Kick". **gemessen**

## Speichern

Der Import schreibt nichts auf die Karte. Die Firmware schreibt `e2sSample.all` nur mit DATA
UTILITY > EXPORT ALL SAMPLE (siehe [Virtuelle SD](../hintergrund/virtuelle-sd.md)), das gilt für
Werks-Slots genauso wie für die Slots ab 501. **gemessen**: nach dem Import und einem Neustart ohne
Export ist das importierte Sample nicht mehr im Slot.

Eine `e2sSample.all` mit Samples in Werks-Slots lädt die Firmware beim Start ohne Fehlerfenster:
Korg rot Slots 18 und 19, Hacktribe Slots 274, 275, 300, 400 und 499 tragen danach die Namen aus der
Datei. **gemessen**

## Der Patch

`import-slots` ersetzt die sieben Befehle durch eine Prüfung gegen die erste Nummer, die der Import
annimmt (19 oder 275), 999 bleibt oben. Unter der ersten Nummer springt der Wähler auf 999, über 999
auf die erste Nummer. Die Oszillator-Slots davor bleiben unerreichbar, so kommt kein "Unknown
Error". Kein eigener Code, kein RAM, eine Variante je Build.

Im Emulator auf beiden Builds: Wähler öffnet auf 501, dreht bis zur ersten Nummer herunter, einen
Schritt tiefer 999, von 999 einen Schritt hoch die erste Nummer, Import auf die erste Nummer ersetzt
den Namen, keine Assertion. **gemessen**

## Offen

- Am Gerät nicht geprüft: Import auf einen Werks-Slot, Abspielen, EXPORT ALL SAMPLE und Neustart.
- Ob eine geleerte oder gelöschte `e2sSample.all` den Werks-Slot wieder mit dem Werks-Sample füllt,
  ist hergeleitet (die Werksbank liegt im Flash ab `0x800000`, siehe
  [Werks-Samplebank](2026-10-07-werks-sample-flash.md)), nicht gemessen.
