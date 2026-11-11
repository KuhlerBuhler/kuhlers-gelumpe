# Plugin API 31: Ausgangspegel wie die Pegelanzeige

Stand 11. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz (`data/patches/blech.json`, für blau `blech-synth.json`). Fälle: `tools/emu/plugin_api31_cases.py` (läuft
als Gruppe von `remote_cases`). **Am Gerät nicht geprüft.** Teil 6.2 des Plans; 6.1, 6.3 und 6.4 (Spettro, Capture, Spektrum)
warten auf die Entscheidung des Besitzers.

## Frage

Kann ein Plugin den Ausgangspegel lesen, so wie ihn die unteren LEDs zeigen, ohne die Anzeige zu stören?

## Weg

Die Funktion der unteren LEDs (`0xC0088284`, blau `0xC0078468`) läuft alle 40 ms. Sie liest zwei Pegel aus dem Objekt
`[0xC033E4F4]` (beide Builds gleich): das Byte `+0x13` und das oberste Byte von `+0x14`, beide mit Vorzeichen und mal 2. Dann
glättet sie beide mit `0xC0088220` (blau `0xC0078404`, gleiche Befehle) (gelesen):

```
zustand = (pegel * 128 * 0x3A5A + zustand * 0x45A5) >> 15
angezeigt = zustand >> 7
```

Der Zustand liegt in zwei Worten bei `0xC06913A8` (blau `0xC056B644`, aus dem Literal der Glättung gelesen). Die Faktoren
ergeben zusammen 0x7FFF, der Wert nähert sich also dem Pegel.

`korg.audio.level(kanal)` liest `zustand >> 7` und begrenzt auf 0 bis 254. Das Plugin ruft die Glättung nicht selbst auf, sonst
liefe der Zustand der Anzeige doppelt so schnell.

Die Firmware glättet nur, solange sie die Anzeige zeigt: Hält ein Plugin die LEDs (`korg.ledHold`, Sperre bei LED-Manager
`+0xB98`) oder ist Global Power Save "Always" (Schalter 0), kehrt sie vorher zurück (gelesen: `bne 0xC00885D4`, `beq
0xC00885B0`). Der bestehende Haken `led_meter_hook` am Anfang der Funktion glättet in diesen beiden Fällen selbst, mit denselben
Pegeln und derselben Funktion. Die LEDs ändert er dabei nicht.

## Ergebnisse

| Befund | Marker |
|---|---|
| Der Emulator ruft die LED-Funktion und die Glättung alle 40 ms auf (25 Mal in 1 s) | gemessen |
| Der Emulator setzt die Pegel im Objekt nach jedem Schritt auf 0; die Fälle schreiben sie vor jedem Aufruf neu | gemessen |
| Rohpegel (100, 50) gibt (199, 99), (127, 0) gibt (253, 0), (-112, 20) gibt (0, 39), (0, 0) gibt (0, 0); jeweils gleich dem Zustand der Firmware >> 7 | gemessen |
| Die Glättung bleibt mit ganzen Zahlen eins unter dem doppelten Pegel stehen (199 statt 200) | gemessen |
| Mit gehaltenen LEDs (Sperre 1): (60, 120) gibt (119, 239) | gemessen |
| Mit Power Save "Always": alle zwölf LEDs 0, (30, 40) gibt (59, 79), (90, 70) gibt (179, 139) | gemessen |
| Gleiche Zahlen auf Hacktribe, rot und blau | gemessen |
| Die LED-Look-Fälle von `menu_cases` laufen mit dem geänderten Haken weiter | siehe Lauf im PR |

## Offen

- Gerät: welcher Kanal links ist (Byte `+0x13` treibt die LEDs 7 bis 12, das andere 1 bis 6), ob der Pegel vor oder nach dem
  Master-Volume liegt, und wie schnell er einem echten Signal folgt.
- Woher die Firmware die Pegel ins Objekt schreibt (DSP-Seite), ist nicht gelesen.
