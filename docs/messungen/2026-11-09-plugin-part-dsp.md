# Part-Werte aus Plugins: was an die Klangerzeugung geht

**Gemessen** im [Emulator](../glossary.md#emulator) mit [Hacktribe](../glossary.md#hacktribe) 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
ohne [BLECH](../glossary.md#blech) (Wege der Bedienelemente) und mit dem BLECH-Satz (Zwillingsproben). Fälle: `tools/emu/plugin_api23_cases.py` und
`tools/emu/plugin_api24_cases.py` (laufen als Gruppen von `remote_cases`). **Am Gerät geprüft** (06.11.) ist der Firmwarepfad: die
Zuweisung über Part-Edit und Parametersetzer aktualisiert den Klang sofort, ein Schreiben in den Pattern-RAM allein reicht nicht.
**Nicht am Gerät geprüft** ist der Plugin-Schreibweg `korg.parts[i].x = v` selbst. Für Synth sind die Firmware-Adressen nicht zugeordnet.

Diese Seite prüft den Schreibweg von `korg.parts[i].x = v` (`script_seq_set_part_value_glue` in `tools/patch/script_seq.s`)
gegen die Wege der Bedienelemente.

## Frage

Seit API 14 ruft ein Plugin-Schreibzugriff dieselbe Funktion der Firmware wie der Regler, der Drehgeber oder die Taste, und
ergänzt deren Nebenwirkungen einzeln (Fenster, LED, MIDI-CC). Geht danach auch dasselbe Richtung Klangerzeugung wie beim Bedienelement?

## Weg

Erst ohne BLECH: Hooks auf den Part-Edit `0xC0048460` (blau `0xC0042700`) mit Parameter, Wert und Flag vom Stack, den
Parametersetzer `0xC0059720` (blau `0xC005013C`), den Verteiler `0xC004B208` (blau `0xC0045120`) mit Part, Code, Wert und Flag
vom Stack, auf dem Sampler auch dessen Wege `0xC009A5EC` (Filter), `0xC009A700` (AMP EG), `0xC009A704` (MFX SEND), `0xC009A764`
(IFX ON), und die Meldungen an das Part-Panel `[0xC03487E4] + 4`. Dann je Regler, Drehgeber und Taste ein Dreh oder Druck.

Dann mit BLECH die Zwillingsproben: Bedienelement einmal, Aufrufe gemerkt, zurückgestellt, derselbe Wert über den Plugin-Weg,
Aufrufe verglichen. Verglichen werden Parametersetzer und Verteiler (mit Flag) und auf dem Sampler die vier Wege; dazu wie bisher
Pattern-Objekt, Bildschirm, MIDI und LEDs.

## Wege der Bedienelemente (ohne BLECH, auf allen drei gleich)

| Bedienelement | Aufrufe |
|---|---|
| Regler LEVEL, PAN, PITCH, RESONANCE, EG INT, MOD DEPTH, ATTACK, IFX EDIT, DECAY, OSC EDIT, MOD SPEED, GLIDE, Drehgeber CUTOFF | Part-Edit mit Flag 0, dann Parametersetzer `(Part + 1, Id, Wert, 1)`; Id ist das untere Byte von `PART_CC`, bei PAN, PITCH und EG INT der Wert plus 64. Der Parametersetzer ruft den Verteiler mit Flag 1 |
| Drehgeber SAMPLE, MOD, IFX | Part-Edit mit Flag 1 (Parameter 8, 14, 26), der Verteiler dann mit Flag 1, kein Parametersetzer |
| Tasten LPF, HPF, BPF | kein Part-Edit: Verteiler Code 0x1D mit Flag 1, auf dem Sampler danach `0xC009A5EC`, dann die Meldung `{0, Typ}` an das Part-Panel, die die LEDs LPF, HPF und BPF schaltet |
| Taste MFX SEND | Setter mit Flag 0 (Verteiler ohne Auffrischen), Parametersetzer `(Part + 1, 0x12, 0 oder 127, 1)`, Verteiler mit 127 und Flag 1, auf dem Sampler `0xC009A704(Part, 127)`, Meldung `{1, Wert}` |

## Ergebnisse

| Befund | Marker |
|---|---|
| Nach dem Part-Edit ruft der Plugin-Weg für die 13 Reglerwerte den Parametersetzer mit denselben Werten wie der Regler. Zwillinge (11 Regler, GLIDE, CUTOFF): Verteiler und Parametersetzer gleich, auf Hacktribe, rot und blau | gemessen |
| PAN, PITCH und EG INT: der Parametersetzer bekommt den Wert plus 64 (PAN -28 ergibt 0x24 an den Verteiler und 0x64 an den Parametersetzer), wie beim Regler | gemessen |
| Der Part-Edit für `sample`, `modType`, `ifxType` und `filterType` bekommt Flag 1, der Verteiler frischt damit auf (Bit 10 in `PS_CC`, `PART_REFRESH` in `tools/patch/script_hooks.py`). Zwillinge SAMPLE, MOD und IFX: alle Verteiler-Aufrufe gleich, auf allen drei (SAMPLE nur Sampler) | gemessen |
| `filterType`: Part-Edit Parameter 10 mit Flag 1 ruft den Verteiler mit Code 0x1D und Flag 1, auf dem Sampler danach `0xC009A5EC`, wie die Filtertaste. Für den gewählten Part schickt der Aufruf die Meldung `{0, Typ}`; die LEDs LPF, HPF und BPF stehen danach wie nach der Taste. Zwillinge mit HPF, BPF und LPF gleich, auf allen drei; ein anderer Part schaltet keine LED | gemessen |
| Die LED-Funktion `0xC0087710` ruft keine der Tasten LPF, AMP EG und IFX ON (Hook, Hacktribe); die Meldung an das Part-Panel ist der Weg der Firmware | gemessen |
| `mfxSend`: Setter mit Flag 0 (die Taste gibt 127 an `0xC009A704`, nicht 1), dann Parametersetzer mit 127 oder 0, wie IFX ON und die Taste. Zwilling in beide Richtungen gleich, auf allen drei | gemessen |
| `modType` öffnet das Fenster mit Code 10 wie der Drehgeber MOD (IFX TYPE hat Code 13), Bildschirm gleich wie nach dem Drehgeber | gemessen |
| Der Parametersetzer schickt den Wert über den [DSP](../glossary.md#dsp)-Host-Port weiter (16-Wort-Transfer an `0xFF900A34` bei CUTOFF und RESONANCE). Hörbar wird das erst am Gerät | hergeleitet |
| Klang am Gerät: der Weg über Part-Edit und Parametersetzer ändert den Klang sofort, ein Schreiben in den Pattern-RAM allein nicht (Geräteprobe 06.11., Hacktribe). Quelle: Messung 2026-11-06/part-param-refresh | gemessen am Gerät |
| Klang am Gerät beim Schreiben aus einem Plugin: nicht geprüft | offen |

## Am Gerät zu prüfen

CUTOFF, SAMPLE, Filtertyp und MFX SEND aus einem Plugin gegen das Bedienelement, auf Hacktribe, rot und blau: hörbar gleich,
LEDs LPF, HPF und BPF.

## Codes und Setter-IDs je Feld

Part-Edit `0xC0048460` bekommt Part, feldspezifischen Aktualisierungscode und Wert, danach `0xC0059720` Part plus eins, Setter-ID,
Reglerwert und Flag 1. Die Codes stammen aus der Zuordnung der physischen Regler in der Firmware (offline gelesen, im Emulator mit
Part 3 für alle 13 Felder bestätigt: Hauptbyte und Mirror tragen den Wert, Part 0 und die Auswahl bleiben unverändert, keine Assertion).
Der Part wird explizit übergeben, die Auswahl am Gerät muss sich nicht ändern.

| Feld | Code für `0xC0048460` | Setter-ID für `0xC0059720` | Wert für den Setter |
|---|---:|---:|---|
| `cutoff` | `0x0B` | 5 | Part-Wert |
| `resonance` | `0x0C` | 6 | Part-Wert |
| `egInt` | `0x0D` | 7 | Part-Wert plus 64 |
| `modSpeed` | `0x0F` | 9 | Part-Wert |
| `modDepth` | `0x10` | 8 | Part-Wert |
| `attack` | `0x11` | 12 | Part-Wert |
| `decay` | `0x12` | 13 | Part-Wert |
| `level` | `0x13` | 10 | Part-Wert |
| `pan` | `0x14` | 11 | Part-Wert plus 64 |
| `ifxEdit` | `0x1B` | 14 | Part-Wert |
| `pitch` | `0x1C` | 2 | Part-Wert plus 64 |
| `glide` | `0x1D` | 3 | Part-Wert |
| `oscEdit` | `0x06` | 4 | Part-Wert |

Der Setter bekommt 0 bis 127, PAN, EG INT und OSC PITCH sind dafür verschoben. Die getrennte Typ-12-Benachrichtigung der UiTask-Queue
(Parameter-ID und Wert, ohne Part-Nummer) nutzen die Part-Zuweisungen nicht; sie ist kein bestätigter DSP-Refresh. Isoliert
aufgerufen (Setter-ID 5 mit Wert 64, ID 6 mit Wert 40, Flag 1, ohne Part-Edit) lässt der Setter den Pattern-RAM unverändert und erzeugt
je einen zusätzlichen `0xAB`-Schreibtransfer mit 16 Wörtern; für die übrigen elf IDs ist nur der gemeinsame Pfad mit `0xC0048460` belegt.
Quelle: Messung 2026-11-06/part-param-refresh.

## Verteiler `0xC004B208`: Aufruf und Spiegel

Beobachtete Aufrufkonvention (gemessen im Emulator, Hacktribe): `R0 = 0xC06B67B4` (Basis des Spiegels), `R1` = Part-Index,
`R2` = Code, `R3` = Refresh-Wert, erstes Stack-Argument 1. Der Spiegel liegt relativ zu `R0 + Part * 0x24`. Der Verteiler gibt den
Part an die spezifischen Pfade weiter, ohne den ausgewählten Part zu ändern (Gegenprobe: Part 0 ausgewählt, `R1 = 3` beim Eintritt:
Auswahl und Hauptbyte von Part 0 bleiben, Mirror und `0xC009A5EC` bekommen Part 3).

| Feld | Code in `R2` | Spiegel-Offset | Pfad bei gesetztem Flag | Refresh-Wert |
|---|---:|---:|---|---|
| Filtertyp | `0x1D` | `+0x22` | `0xC009A5EC` | Feldbyte |
| AMP EG | `0x28` | `+0x30` | `0xC009A700` | Feldbyte |
| MFX SEND | `0x29` | `+0x31` | `0xC009A704` | 0 aus, `0x7F` an |
| IFX ON | `0x2C` | `+0x32` | `0xC009A764` | 0 aus, `0x7F` an |

IFX ON und MFX SEND erreichen den Verteiler zuerst ohne Refresh und danach über die Setter 17 und 18 mit Refresh; AMP EG und Filtertyp
rufen ihn direkt mit Refresh auf. Adressen der Part-Felder und ihrer Spiegel (Hacktribe 2.02):

| Taste | Part 0: Feld / Spiegel | Part 3: Feld / Spiegel |
|---|---|---|
| IFX ON | `0xC06B2FBC` / `0xC06B67E6` | `0xC06B394C` / `0xC06B6852` |
| AMP EG | `0xC06B2FB6` / `0xC06B67E4` | `0xC06B3946` / `0xC06B6850` |
| MFX SEND | `0xC06B2FB7` / `0xC06B67E5` | `0xC06B3947` / `0xC06B6851` |
| LPF, HPF, BPF | `0xC06B2FA8` / `0xC06B67D6` | `0xC06B3938` / `0xC06B6842` |

Quelle: Messung 2026-11-07/part-control-dsp-refresh.

## Setter-Tabelle von `0xC0059720`

Die Tabelle nimmt die IDs 1 bis 19 an (gemessen im Emulator, Part 0 und Part 3 mit Argument `Part + 1`):

- Part-Setter benutzen die IDs 2 bis 14 sowie 17 und 18.
- ID 1 benutzt Code 25 und schreibt das untere Byte des Werts nach `0x403C + Part * 0x24`; die Konvertierungsfunktion ist ein
  unmittelbares `bx lr`. Das reicht nicht als Nachweis, dass ID 1 der Setter für das 16-Bit-Feld `sample` ist.
- Die IDs 15, 16 und 19 (Codes 4, 5 und 2) schreiben auch bei Part 3 an feste Part-0-Offsets (`+6`, `+7`, `+4`). Sie sind keine
  Setter für explizite `korg.parts[i]`-Zuweisungen.
- Die Codes 33 und 42 (Offsets `+0x26` und `+0x33`) wählt keine ID aus. Ein Setter für `modType` oder `ifxType` ist in
  `0xC0059720` nicht vorhanden; ein anderer Weg ist nicht belegt.
- ID 20 endet in einem nicht abgebildeten Instruktionsabruf, IDs außerhalb des Tabellenbereichs sind keine Kandidaten.
- Ein früher gemeldeter 64-Wort-Transfer nach `0xFF900018` für die IDs 15, 16 und 19 ließ sich in der kontrollierten Gegenprobe
  (gegen einen wirkungslosen Aufruf im selben Tick) nicht reproduzieren und gilt nicht als Befund.

Der Part-Edit mit Code 8 (Sample/OSC, 32-Wort-Transfer nach `0xFF900A34`) und Code 26 (IFX TYPE, 64-Wort-Transfers nach
`0xFF900018` und `0xFF900098`) sendet nur mit Flag 1; Code 14 (MOD TYPE) sendet mit keinem Flag sofort einen neuen Block.
Quelle: Messung 2026-11-07/part-control-dsp-refresh.
