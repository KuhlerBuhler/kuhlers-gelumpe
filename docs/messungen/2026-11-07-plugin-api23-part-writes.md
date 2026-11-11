# Plugin API 23: IFX ON, IFX TYPE, Sample und AMP EG schreibbar

Stand 7. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz. Fälle: `tools/emu/plugin_api23_cases.py` (läuft als Gruppe von `remote_cases`). **Am Gerät nicht geprüft.**

## Frage

Nach API 21 ([Messung](2026-11-06-plugin-api21-pattern-parts.md)) blieben `sample`, `ifxOn` und `ifxType` nur lesbar, AMP EG
fehlte ganz. Lassen sie sich so setzen, dass Pattern, Kopie der Klangerzeugung, LED und Bildschirm wie nach der Taste oder dem
Drehgeber stehen?

## Weg

Wie bei API 21 je Wert eine Zwillingsprobe: die Taste (IFX ON 0x21, AMP EG 0x20, MFX SEND 0x1A) oder der Drehgeber (IFX, SAMPLE)
einmal bedient, Pattern-Objekt (Block und Kopie, 0x4274 Byte), LEDs 15 bis 17 und Bildschirm gemerkt, zurückgestellt, dann
derselbe Wert durch `script_seq_set_part_value_glue` gesetzt. Die Tastenwege sind vorher offline gelesen und mit einem
Tracer im Emulator nachverfolgt.

## Tastenwege (Sampler, blau in Klammern)

| Taste | Was die Firmware tut |
|---|---|
| IFX ON (`0xC007C908`, blau `0xC006F28C`) | Setter `0xC0049DEC` (`0xC0043F08`) mit `(Objekt + 0x400C, Part, Wert, 0)`, schreibt Byte 0x820 und die Kopie mit 1; zwei Funktionen der Motion-Aufzeichnung (`0xC0090310`, `0xC0090368`); MIDI-CC über `0xC00405EC` (`0xC003B224`), am Ausgang `b0 68 7f`; Parametersatz `0xC0059720` (`0xC005013C`) mit `(Part + 1, 0x11, 127 oder 0, 1)`, der die Kopie auf 127 setzt; Meldung `{3, Wert}` an das Part-Panel hinter `0xC03487E4` (`0xC03484F8`), das LED 17 schaltet |
| AMP EG (`0xC007C7DC`) | Setter `0xC0049664` (`0xC0043780`) mit `(Objekt + 0x400C, Part, Wert, 1)`, Byte 0x81A (Part-Byte 26) und Kopie, klemmt auf 1; Meldung `{2, Wert}`, LED 16. Kein MIDI |
| MFX SEND | Setter `0xC00496D4` (`0xC00437F0`), dann Meldung `{1, Wert}`, LED 15 |

Korrektur zu API 21: dort steht `0xC00405EC` als Klangerzeugung und `0xC0059720` als MIDI. Es ist umgekehrt, `0xC00405EC` schickt
den CC, `0xC0059720` setzt den Wert in der Klangerzeugung (die 127 in der Kopie).

## Ergebnisse

| Befund | Marker |
|---|---|
| `ifxOn`: Setter mit Flag 0, Parametersatz mit 127 oder 0, Meldung `{3, Wert}`. Objekt und LEDs gleich wie nach der Taste, auf Hacktribe, rot und blau | gemessen |
| `ifxOn`: kein MIDI-CC und keine Motion-Aufzeichnung; wie die anderen Schreibwege der Plugins geht nichts an MIDI | gemessen (MIDI), offline gelesen (Motion) |
| `ampEg` (neues Feld, Part-Byte 26, in der Gerätekarte `egOn`): Setter und Meldung `{2, Wert}`, gleich wie die Taste, auf allen drei | gemessen |
| `mfxSend` (API 21) schaltete die LED nicht. Jetzt mit Meldung `{1, Wert}`, LED gleich wie nach der Taste | gemessen |
| Die Meldung geht nur für den gewählten Part raus, wie die Taste nur den gewählten Part schaltet. Für einen anderen Part ändern sich Byte und Kopie, die LEDs nicht | gemessen |
| `ifxType`: der Drehgeber IFX ruft den Part-Edit (`0xC0048460`) mit Parameter 0x1A, der den Setter `0xC0049EE4` ruft (setzt auch IFX EDIT auf den Standardwert des Typs). Der Aufruf geht denselben Weg, mit Fenstercode 13. Objekt und Bildschirm gleich wie nach dem Drehgeber, auf Hacktribe und rot | gemessen |
| Fenstercode 13: von 0 bis 47 durchprobiert, nur 13 gibt dasselbe Bild wie der Drehgeber | gemessen |
| `ifxType` Grenze: der Setter prüft mit `cmp r2, #top` bei `0xC0049EF0` (blau `0xC004400C`) und setzt Werte darüber auf 0. Der Aufruf liest dieses Byte zur Laufzeit und klemmt darauf: 58 auf Hacktribe (59 Typen), 47 auf rot, 37 auf blau. 200 ergibt die letzte Nummer, -5 ergibt 0. Steht dort kein solcher Befehl, schreibt der Aufruf nichts | gemessen |
| Der fx-Katalog von BLECH hebt dieses Byte (Hacktribe ohne BLECH 0x30), darum steht die Grenze nicht als Zahl in der Laufzeit | gemessen |
| `ifxType` auf blau: über den direkten Setter, weil der Part-Edit dort nicht vermessen ist. Objekt gleich wie nach dem Drehgeber, das Fenster des Drehgebers fehlt | gemessen |
| `sample`: der Part-Edit mit Parameter 8 und der ganzen Slotnummer als Wort (der Weg von API 14 hatte auf ein Byte gekürzt). Objekt und Bildschirm gleich wie nach dem Regler SAMPLE, auf Hacktribe und rot | gemessen |
| Leerer Slot: der Regler überspringt ihn über `0xC0040D50(Slot, Richtung)`, das den nächsten belegten Slot liefert. Der Aufruf schreibt einen Slot nur, wenn diese Funktion ihn selbst zurückgibt; sonst bleibt alles, wie es war. Im Emulator ohne Flash sind 0 bis 273 belegt, 999 und 5000 (auf 999 geklemmt) schreiben nichts | gemessen |
| `sample` auf blau: keine Samples, der Aufruf schreibt nichts | gemessen |
| Ein Plugin setzt und liest `korg.parts[1].ampEg`, `.ifxOn`, `.ifxType` und `.sample` über den Namen | gemessen |
| `korg.seq.setPartValue` nahm Feldnummern bis 19, jetzt bis 31 wie `korg.read.patternValue`; die Laufzeit prüft die Zahl der Felder selbst | gemessen |

## Namen

`ampEg` ist neu und braucht zum Lesen und Schreiben API 23. `sample`, `ifxOn` und `ifxType` lesen weiter ab API 8 und schreiben
ab API 23.

## Offen

- **Am Gerät**: keine Zeile.
- **Slices**: ist ein Sample in Slices geteilt, setzt die Firmware beim Wählen noch den Slice (Parameter 0x1E, `0xC0041068`). Nicht gemessen; der Aufruf setzt nur den Slot.
- **MIDI**: ob `ifxOn` den CC wie die Taste schicken soll, ist eine Entscheidung, keine Messung. Die anderen Schreibwege schicken nichts.
- **IFX TYPE auf blau** ohne Fenster, solange der Part-Edit dort nicht vermessen ist.
