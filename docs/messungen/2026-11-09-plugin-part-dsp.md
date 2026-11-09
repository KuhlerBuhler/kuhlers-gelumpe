# Part-Werte aus Plugins: was an die Klangerzeugung geht

Stand 9. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
ohne BLECH (Wege der Bedienelemente) und mit dem BLECH-Satz (Zwillingsproben). Fälle: `tools/emu/plugin_api23_cases.py` und
`tools/emu/plugin_api24_cases.py` (laufen als Gruppen von `remote_cases`). **Am Gerät nicht geprüft.**

Die Befunde stammen aus PR #401 ([Firmwarepfad für Part-Parameter](2026-11-06-part-param-refresh.md),
[DSP-Transport bei Part-Bedienungen](2026-11-07-part-control-dsp-refresh.md)). Diese Seite prüft sie gegen den Schreibweg von
`korg.parts[i].x = v` (`script_seq_set_part_value_glue` in `tools/patch/script_seq.s`) und hält fest, was übernommen ist.

## Frage

Seit API 14 ruft ein Plugin-Schreibzugriff dieselbe Funktion der Firmware wie der Regler, der Drehgeber oder die Taste, und
ergänzt deren Nebenwirkungen einzeln (Fenster, LED, MIDI-CC). Die Zwillingsproben bis API 25 haben Pattern-Objekt, Bildschirm,
LEDs und MIDI verglichen, aber nicht, was danach Richtung Klangerzeugung geht. PR #401 fand dort vier Lücken.

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
| Develop rief nach dem Part-Edit für die 13 Reglerwerte keinen Parametersetzer; jetzt ruft der Plugin-Weg ihn mit denselben Werten wie der Regler. Zwillinge (11 Regler, GLIDE, CUTOFF): Verteiler und Parametersetzer gleich, auf Hacktribe, rot und blau | gemessen |
| PAN, PITCH und EG INT: der Parametersetzer bekommt den Wert plus 64 (PAN -28 ergibt 0x24 an den Verteiler und 0x64 an den Parametersetzer), wie beim Regler | gemessen |
| Develop gab dem Part-Edit für `sample`, `modType`, `ifxType` und `filterType` Flag 0, der Verteiler frischte nichts auf. Jetzt Flag 1 (Bit 10 in `PS_CC`, `PART_REFRESH` in `tools/patch/script_hooks.py`). Zwillinge SAMPLE, MOD und IFX: alle Verteiler-Aufrufe gleich, auf allen drei (SAMPLE nur Sampler) | gemessen |
| `filterType`: Part-Edit Parameter 10 mit Flag 1 ruft den Verteiler mit Code 0x1D und Flag 1, auf dem Sampler danach `0xC009A5EC`, wie die Filtertaste. Für den gewählten Part schickt der Aufruf die Meldung `{0, Typ}`; die LEDs LPF, HPF und BPF stehen danach wie nach der Taste. Zwillinge mit HPF, BPF und LPF gleich, auf allen drei; ein anderer Part schaltet keine LED | gemessen |
| Die LED-Funktion `0xC0087710`, die PR #401 nimmt, ruft keine der Tasten LPF, AMP EG und IFX ON (Hook, Hacktribe); die Meldung an das Part-Panel reicht, und sie ist der Weg der Firmware | gemessen |
| `mfxSend`: develop rief den Setter mit Flag 1, der den Wert 1 an `0xC009A704` gab, die Taste gibt 127. Jetzt Setter mit Flag 0, dann Parametersetzer mit 127 oder 0, wie IFX ON und die Taste. Zwilling in beide Richtungen gleich, auf allen drei | gemessen |
| `modType` öffnete das Fenster von IFX TYPE (Code 13); der Drehgeber MOD meldet Code 10. Jetzt Code 10, Bildschirm gleich wie nach dem Drehgeber | gemessen |
| Dieselben Zwillingsproben mit dem Stand von develop (Hacktribe): 20 Fälle schlagen fehl, genau die 13 Reglerwerte, SAMPLE, MOD, IFX, die drei Filtertasten und MFX SEND; alle übrigen bestehen | gemessen |
| Der Parametersetzer schickt den Wert über den DSP-Host-Port weiter (PR #401: 16-Wort-Transfer an `0xFF900A34` bei CUTOFF und RESONANCE). Hörbar wird das erst am Gerät | hergeleitet |
| Klang am Gerät: PR #401 meldet, dass ein Schreiben in den Pattern-RAM allein den Klang nicht ändert und der Weg über Part-Edit und Parametersetzer ihn sofort ändert. Mit diesem Stand nicht nachgeprüft | offen |

## Nicht übernommen aus PR #401

| Teil | Grund |
|---|---|
| eigener Schreiber `script_write_part_value_glue` mit API 13/14 und interner Id 72 | develop hat den Schreiber seit API 14 breiter (28 Werte, blau, Fenster, CC); die Nummern kollidieren |
| Hauptbyte und Spiegel selbst schreiben, dann den Verteiler rufen | die Firmware schreibt beides selbst; doppelt |
| LEDs über `0xC0087710` mit festen Typbereichen | siehe oben, die Meldung an das Part-Panel ist der Weg der Taste |
| Step-Getter, `setGate`, `setStep` ohne Trigger | develop hat sie als API 22 |
| `korg.parts[i].muted` nur lesbar | develop schreibt `muted` |
| Bewegungsaufnahme `0xC0090310` | nicht Teil dieser Änderung; Regler, CUTOFF, IFX ON und AMP EG rufen sie, der Plugin-Weg nicht (gemessen auf Hacktribe; dass sie bei REC aufnimmt, ist hergeleitet) |

## Am Gerät zu prüfen

CUTOFF, SAMPLE, Filtertyp und MFX SEND aus einem Plugin gegen das Bedienelement, auf Hacktribe, rot und blau: hörbar gleich,
LEDs LPF, HPF und BPF.
