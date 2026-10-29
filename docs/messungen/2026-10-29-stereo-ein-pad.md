# Stereo auf einem Pad (29.10.)

Stand 29.10.2026, Emulator mit Korgs Original 2.02 (rot) und Hacktribe 2.02, beide mit denselben Adressen. Wunsch: ein
Stereo-Sample auf Pad 1 belegt nur Pad 1, Pad 2 bleibt frei. Patch `data/patches/stereo-pad.json`. Am Gerät nicht geprüft.

## Wie die Firmware Stereo-Samples spielt

| Befund | Marker |
|---|---|
| `0xC004E41C(osc)` sagt, ob das Sample eines Oszillators stereo ist: Eintrag `0xC047B08C + osc * 0x20`, +0x12 minus 0x32 ist die Nummer, `0xC004E2F0` macht daraus den Index der Metadaten, dort +9 das Stereo-Flag (`esli[65]`) | offline (Code), gemessen (Emulator: 1 für die Stereo-Datei, 0 für Mono) |
| Der Lader nimmt das Stereo-Flag aus dem `esli`-Satz, nicht aus dem `fmt `-Abschnitt: eine Stereo-WAV mit `esli[65] = 0` lädt als Mono | gemessen (Emulator) |
| `0xC007DDCC(_, part, nummer)` ist der Stereo-Modus eines Parts: 2 für ein geschnittenes Sample, sonst bei Stereo (oder Oszillator 0x11) 1 auf einem ungeraden Part (1, 3, ...) und 0 auf einem geraden (2, 4, ...), 0 bei Mono. `0xC007ED5C(_, part)` holt den Oszillator aus dem Part und fragt ihn | offline (Code), gemessen (Emulator: Modus `[1, 0, 0, 0]` mit Stereo auf Part 1, `[0, 0, 0, 0]` mit Stereo auf Part 2) |
| Über `0xC007ED5C`, `0xC007ED8C` (Part führt ein Paar) und `0xC007EDBC` (Part ist die zweite Hälfte) laufen Partwahl (`0xC0081BB4`, PART > springt über die zweite Hälfte), Pads (`0xC0043684`, `0xC0043B70` leiten auf den ersten Part um), LEDs (`0xC0088A90` bis `0xC0088DD0`), Pattern-Anzeige (`0xC0066848`) und Sequencer (`0xC0059228` bis `0xC005AFBC`) | offline (Code) |
| `0xC00413DC` (Oszillatorwechsel): nur auf einem ungeraden Part nimmt ein neues Stereo-Sample den nächsten Part in Beschlag (`0xC0043F10`, `0xC005AAF4` mit Part + 1), ein Wechsel zurück auf Mono gibt ihn frei | offline (Code) |
| Die Stimme bekommt ihren Modus in `0xC0099D88`: Stereo-Sample auf ungeradem Part Modus 3, auf geradem Modus 4 (`0xC0099E20`). Die Tabelle `0xC00E922C` macht daraus den Typ der Nachricht 0x2E an den DSP: Modus 0 ergibt 0 (Mono), 3 ergibt 2, 4 ergibt 4 | offline (Code) |
| Was der ARM beim Anschlag von Pad 1 an das Postfach `0xFF900A34` schickt: Mono-Sample eine Stimme (Nachricht 0x34 mit Zähler 0), Typ 0. Stereo auf Part 1 zwei Stimmen (Zähler 1, Handles `0x461B` und `0x4661`), Typ 2. Stereo auf Part 2 eine Stimme, Typ 4 | gemessen (Emulator) |
| Typ 4 ist also eine eigene Stimmart des DSP für "Stereo-Sample auf einer Stimme". Ob sie links und rechts mischt oder nur einen Kanal spielt, sagt nur das Gerät | hergeleitet, Klang **offen** |
| Die Bytes des Patterns ändern sich beim Paaren nicht: der zweite Part behält Sample und Steps, er wird nur nicht gespielt und nicht gezeigt | gemessen (Emulator: nach dem Wechsel auf Stereo nur die zwei Bytes des Samples von Part 1 anders) |
| Der Live-Eingang (Oszillator 0x11 im Part, 0x2D in der Stimme) paart auf demselben Weg, unabhängig vom Stereo-Flag | offline (Code) |

## Der Patch

Jeder Part spielt ein Stereo-Sample so, wie die Firmware es auf einem geraden Part tut. Drei Befehle rufen Code bei `0xC014FF00`
(hinter dem Code von last-pattern; `0xC014FF00` bis `0xC0150000` ist `FF` in Korgs roter und blauer 2.02 und in Hacktribe 2.02,
gemessen am 29.10. in den drei Dateien):

| Stelle | Vorher | Mit dem Patch |
|---|---|---|
| `0xC007DE08` im Stereo-Modus | `bne` zu "Part gerade?" | Stereo gibt 0 (kein Paar) |
| `0xC00413EC` im Oszillatorwechsel | `bne` überspringt das Belegen nur auf ungeraden Parts | jeder Part überspringt es |
| `0xC0099E2C` im Modus der Stimme | `moveq r3, #3` | Modus 4 |

Der Schalter ist die Seite STEREO 1 PAD in BLECH > FEATURES, die letzte der Gruppe, nur wo der Satz den Patch hat (erstes Wort
bei `0xC014FF00` nicht `FF`, also nicht auf der blauen). Sie schreibt das Wort `0xC014FFFC` (im Abbild `FF`, das heißt an): 1 an,
0 aus, sofort wirksam. WRITE behält AUS als Bit 2 von Byte 5 der Einstellungsdatei; ohne Datei oder ohne das Bit ist es an. Ein
BLECH bis 1.3.7 liest die Datei mit dem Bit nicht (es liest auch Version 3 nicht). Ist der Schalter aus oder war EXIT beim
Einschalten gehalten, tun alle drei Stellen, was die Firmware tut. Der Stereo-Modus läuft schon beim Laden des ersten Patterns
in der Startphase, deshalb nennt der Patch die Stelle und seinen Code als `startPhase`. Geschnittene Samples (Modus 2) und der
Live-Eingang bleiben, wie sie sind. Das Pattern-Format ändert sich nicht.

Folge für alte Patterns: Ein Pattern mit Stereo-Sample auf Part 1 spielte Part 2 nicht. Mit dem Patch spielt Part 1 das Sample
auf einer Stimme, und Part 2 spielt, was in ihm steht (sein Sample, seine Steps).

## Fälle (`tools/emu/stereo_pad_cases.py`)

Karte mit Mono (501), Stereo (502, `esli[65] = 1`) und Mono (503), Part 1 bekommt 502 über das SAMPLE-Rad, Part 2 503.

| Fall | Original | Mit Patch |
|---|---|---|
| Modus von Part 1 und 2 | `[1, 0]` | `[0, 0]` |
| PART > von Part 1 | Part 3 | Part 2 |
| Pad 1 | 2 Stimmen, Typ 2 | 1 Stimme, Typ 4 |
| Pad 2 | keine eigene Stimme | 1 Stimme, Typ 0, Audio von 503 |
| Bytes des Patterns nach den zwei Wechseln | Samples von Part 1 und 3 (PART > landet auf Part 3) | nur die Samples von Part 1 und 2 |
| mit EXIT beim Einschalten | | wie das Original |
| Seite STEREO 1 PAD ohne Einstellungsdatei | | ON, Wort `FFFFFFFF` |
| Rad nach links | | OFF, Wort 0, Part 1 und 2 paaren wieder (Modus 1, zwei Stimmen) |
| WRITE, dann neuer Start von derselben Karte | | Byte 5 der Datei `0x04`, die Seite zeigt OFF, Wort 0 |
| Start mit METER LOUD RAINBOW und STEREO 1 PAD OFF (Byte 5 `0x05`), WRITE, neuer Start | | Byte 5 bleibt `0x05`, die Seite zeigt OFF (vorher schrieb RAINBOW Byte 5 ganz und löschte Bit 2) |

Beide Builds (BLECH-Satz auf Korgs roter 2.02 und auf Hacktribe 2.02) bestehen alle Fälle, das Original fällt bei fünf der
Fälle ohne Menü durch.

## Offen

- Klang von Typ 4 am Gerät (Summe oder ein Kanal, Pegel gegenüber dem Paar).
- Am Gerät: Pad 2 neben einem Stereo-Pad 1 spielt sein eigenes Sample, die LEDs und die Partwahl wie im Emulator.
