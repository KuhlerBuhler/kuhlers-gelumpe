# Plugin API 24: Schreibwege wie Regler, Tasten und Menüseiten, MIDI-CC, Fensterschalter

Stand 8. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz. Fälle: `tools/emu/plugin_api24_cases.py` (läuft als Gruppe von `remote_cases`). **Am Gerät nicht geprüft.**

## Frage

Für 1.4.5 soll jeder Wert, den ein Regler, Drehgeber oder eine Taste am Gerät setzt, über die Plugin-API setzbar sein und sich
dabei verhalten wie die Bedienung am Gerät. Nach API 23 ([Messung](2026-11-07-plugin-api23-part-writes.md)) fehlten: der MIDI-CC
der Regler und Tasten, der Part-Edit auf blau, sieben Part-Werte, fünf Pattern-Werte und die Slices beim Sample. Dazu soll ein
Plugin das Parameterfenster abschalten können.

## Weg

Je Wert eine Zwillingsprobe: der Regler, der Drehgeber, die Taste oder die Menüseite einmal bedient, Pattern-Objekt (Block und
Kopie der Klangerzeugung, 0x4274 Byte), MIDI-Ausgang (ohne Clock und Active Sensing), LEDs und Bildschirm gemerkt, zurückgestellt,
dann derselbe Wert durch `script_seq_set_part_value_glue` oder `script_seq_set_pattern_value_glue` gesetzt. Wo zwei Geräte
nötig sind (MFX HOLD, Slices), startet ein zweites aus demselben Zustand. Die Wege der Firmware sind vorher offline gelesen und
mit Hooks im Emulator nachverfolgt.

## MIDI-CC (Sampler, blau in Klammern)

Die Regler und Tasten schicken den CC über `0xC00405EC` (`0xC003B224`) mit `(MIDI-Objekt, Part + 1, Id, Wert * 2)`, das
MIDI-Objekt liefert `0xC0045320` (`0xC003F640`). Part + 1 = 17 ist der globale Kanal. Die Ids stehen in `PART_CC` in
`tools/patch/script_hooks.py`: LEVEL 0xA, PAN 0x10B (mit Vorzeichen, Wert + 64), PITCH 0x102 (mit Vorzeichen), GLIDE 3,
OSC EDIT 4, CUTOFF 5, RESONANCE 6, EG INT 0x107 (mit Vorzeichen), MOD DEPTH 8, MOD SPEED 9, ATTACK 0xC, DECAY 0xD, IFX EDIT 0xE,
IFX ON 0x211 (an/aus, 127 oder 0), MFX SEND 0x212 (an/aus).

## Ergebnisse

| Befund | Marker |
|---|---|
| Alle elf Regler und GLIDE (SHIFT und PITCH): Objekt, MIDI-CC und Bildschirm nach dem Aufruf gleich wie nach dem Regler, auf Hacktribe, rot und blau | gemessen |
| GLIDE: das Fenster zeichnet sich anders, solange SHIFT gedrückt ist. Gleich ist es, wenn SHIFT auch beim Aufruf gedrückt ist; die Meldung an das Fenster (Code 16, Wert) ist in beiden Fällen dieselbe | gemessen |
| Drehgeber CUTOFF: Objekt, CC und Bildschirm gleich | gemessen |
| `ifxOn` und `mfxSend` schicken jetzt denselben CC wie die Tasten IFX ON und MFX SEND (am Ausgang z. B. `b0 68 7f`); Objekt und LED wie in API 23 gleich | gemessen |
| Ein anderer Part schickt auf seinem Kanal: Part 5 LEVEL 90 gibt `b4 07 5a` | gemessen |
| Blau: der Part-Edit liegt bei `0xC0042700`, sein Objekt bei `0xC0348570`, das Parameterfenster bei `0xC0348500`. Damit schreiben die Reglerwerte auf blau, mit Fenster; `ifxType` auf blau geht jetzt auch über den Part-Edit mit dem Fenster des Drehgebers | gemessen |
| Neue Part-Werte `lastStep`, `motionMode`, `padVelocity`, `scaleMode`, `priority`, `grooveType`, `grooveDepth`: über den Setter der Seiten 16 bis 23 im Part-Menü; Objekt und Seite gleich wie nach dem Drehen im Menü, auf allen drei. Die Seiten sind auf allen drei Firmwares dieselben | gemessen |
| `grooveType` hält beim Grenzwert des Setters (der Aufruf liest das `cmp` des Setters zur Laufzeit), 200 ergibt die letzte Nummer | gemessen |
| `alternate1314`, `alternate1516`: über den Setter der Seiten ALTERNATE (Seiten 11 und 12 im Pattern-Menü) mit `(Pattern-Objekt, Index, Byte, 1)`; Objekt und Seite gleich wie im Menü | gemessen |
| `mfxPadX`, `mfxPadY`: Setter des Touchpads, dann CC 0xF und 0x10 auf dem globalen Kanal, am Ausgang `b0 66 32` und `b0 67 32` für 50, wie das Touchpad bei einer Berührung | gemessen |
| MFX HOLD: der Setter allein schaltet weder LED 0x1D noch den Zustand des Touchpads; das tut der Handler der Taste (`0xC0045390` bis `0xC0045480`: Setter, X/Y ins Objekt, Effekt, Parametersatz, LED). `mfxHold` drückt darum die Taste 0x07 wie `korg.pressKey`, wenn der Wert sich ändert. Objekt und LED gleich wie nach der Taste, an und aus; derselbe Wert drückt nichts | gemessen (Ergebnis), offline gelesen (Handler) |
| `mfxHold` steht erst nach dem nächsten Bild im Block, weil der Tastendruck über die Nachrichtenschlange läuft | offline gelesen |
| Slices: `0xC004E478(Sample)` ungleich 0 heißt geteilt. Der Regler SAMPLE ruft dann `0xC0041068`, das den Part-Edit mit Parameter 0x1E und Fenstercode 0x11 ruft; hochgedreht mit Slice -1 (zurück mit dem höchsten Slice, ungeteilt -2). Der Aufruf geht diesen Weg mit -1 | offline gelesen, mit Hooks nachverfolgt |
| Die Karte im Emulator hat kein Sample mit Slices. Mit einem Hook, der `0xC004E478` für ein Sample 1 liefern lässt, sind Objekt und Bildschirm nach dem Aufruf gleich wie nach dem Regler, auf Hacktribe und rot | gemessen (mit gestelltem Slice-Sample) |
| `korg.display.popups = 0`: Aufrufe dieses Plugins schreiben den Wert, das Fenster bleibt zu (Bildschirm unverändert, LEVEL 33, LAST STEP 7, MFX HOLD 1 im Block). Ohne den Schalter öffnet derselbe Aufruf das Fenster, gelesen wird 1 | gemessen |
| Der Schalter ist Bit 1 im Wort des Plugin-Eintrags, das auch das Halten der Pads trägt (Bit 0, `tools/patch/script_hw.s`); er gilt je Plugin, beim Laden ist das Fenster an | Aufbau der Laufzeit |

## Namen

Neu ab API 24, lesen und schreiben: `lastStep`, `motionMode`, `padVelocity`, `scaleMode`, `priority`, `grooveType`,
`grooveDepth` (Part), `alternate1314`, `alternate1516`, `mfxHold`, `mfxPadX`, `mfxPadY` (Pattern), `korg.display.popups` und
`korg.read.popups()`.

## Offen

- **Am Gerät**: keine Zeile.
- **Name des Patterns**: nicht setzbar. Er ist kein einzelner Wert wie die anderen, und der Weg der Seite NAME ist nicht vermessen.
- **Slices am Gerät**: der Weg ist nur mit einem gestellten Slice-Sample geprüft.
- **`korg.knob`** öffnet das Fenster weiter, auch mit `popups = 0`, weil es die Reglerfunktion der Firmware selbst ruft.
