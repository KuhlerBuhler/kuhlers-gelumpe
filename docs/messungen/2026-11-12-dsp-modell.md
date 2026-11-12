# DSP-Modell im Emulator, für Prüfungen

Stand 12. November 2026. DSP-Programm aus der Firmware gelesen (Blackfin-Code ab `0xC00F9E10`, entpackt mit
`tools/dsp/dsp_extract.py`, disassembliert mit einem selbst gebauten `bfin-objdump`). **Gemessen** im Emulator mit Hacktribe 2.02, Korgs Original 2.02 rot und blau (eigene Dateien), jeweils
mit dem BLECH-Satz von develop und mit dem Stand von #506. **Am Gerät nicht geprüft.** Kein Ton: das Modell hält, was die CPU dem DSP sagt, und
beantwortet die Lesezugriffe, deren Bedeutung gelesen ist.

Code: `tools/emu/dsp_model.py`, Tests `tools/emu/test_dsp_model.py`, Prüffall `shortcut:exit_pad_keeps_the_part_on_at_the_dsp_*`
(`case_reset_dsp` in `tools/emu/shortcut_cases.py`).

## Ausgangslage

Der Emulator führt das DSP-Programm nicht aus. Der Host-Port (`0x60000000` Daten, `0x60000002` Steuerung, Format in
[DSP-Audiopfade](2026-10-08-dsp-audiopfade.md)) nimmt jede Übertragung an, Lesen liefert 0, nur der Eingangspegel ist belegt.
Geschriebene Daten zählt `machine.py` nur ab, `DspLog` in `mfx_cases.py` schneidet sie für einzelne Prüfungen mit. Was am DSP
ankommt, ist damit sichtbar, aber nicht gedeutet. Darum sah der Emulator ohne Modell nicht, dass der Part-Reset von #470 den Part am DSP
abschaltet (#506, Gerätetest 11.11.: Part stumm).

## Was das Modell liest

| Befund | Marker |
|---|---|
| Jede Schreibübertragung (`0xAB`) ans Postfach `0xFF900A34` ist eine Nachricht. Die CPU schickt immer 16 Wörter, hinter der Nachricht steht Stack-Rest | gemessen |
| Wort 0 ist `0x106`, Wort 1 das Kommando. Im Leerlauf kommen nur die Kommandos `1` und `0x31`, alle 40 ms, für die Pegelanzeige ([Pegel-LEDs](2026-11-12-pegel-leds.md)) | gemessen |
| DSP-Seite: Handler `0xFFA04EC8`, Kommandos unter `0x3C` über die Sprungtabelle `0x01F02B84`. Parameter N liegt bei `0xFF800000 + 4N`, ab `0x4000` bei `0xFF8F0000 + 4N` (`0xFFA071CC`) | gelesen |
| Kommando `0`: Slot = Wert << 16. `1`: Tripel (Parameter, hoch, tief), Slot = hoch << 16 \| tief. `2`: Block (Anzahl - 1, Start, Werte), je Slot = Wert << 16. `0x16`: Anzahl - 1, dann Tripel (Parameter p, a, b), Slot p = a << 16, Slot p + 1 = b << 16 (`0xFFA05084`). `0x31`: Block mit 32-Bit-Werten (hoch, tief) | gelesen |
| `9` (Quelle, Ziel): kopiert 0x1A Slots (`0xFFA0505A`). `0x26`: Anzahl - 1, dann Paare (p, q): Slot p = 0, Slot q = 0, Slot q - 1 = Slot p + 0x19 (`0xFFA05172`). Blau schickt `0x26` ohne Anzahl, also ein Paar (p, q) | gelesen; blau gemessen (CPU-Seite), DSP-Code von blau nicht gelesen |
| Übrige Noten-Kommandos `0x1F`, `0x2B` bis `0x39`: rechnen Hüllkurven, Filterkoeffizienten und Filterzustand im DSP (`0x39`/`0x35` über `0xFFA05AEC`, Koeffizienten-Tabelle `0x01F02DDC`; `0x34` setzt den Filterzustand eines Parts zurück); das Modell zählt sie nur | gelesen, teilweise |
| `0x2B` (p, v): Slot p = v << 16, dann rechnet der DSP aus v + Slot p + 1 und dem Generatortyp in Slot p + 2 den Slot p + 3 (`0xFFA051C0`, Setter `0xFFA06970`). `0x2C` (p, q, v): Slot q = v << 16, dann dasselbe mit Slot p + v nach Slot q + 2 (`0xFFA05210`). `0x30` (Flag, p, Daten): Filter-Setter `0xFFA05CB2` und `0xFFA05BF0` auf Slot p, mit Flag auch auf Slot p + 0x6E (`0xFFA05308`) | gelesen |
| Die Part-Regler schicken beim Drehen und mit der nächsten Note keinen DSP-Parameter, außer PAN: Part-Parameter `+0x60` über Kommando 2 (Regler 0, 64, 127 ergibt `0`, `0x3EFB`, `0x7DF7`). LEVEL, PITCH, RESONANCE, EG INT, MOD DEPTH, ATTACK, IFX EDIT, DECAY, OSC EDIT und MOD SPEED wirken nur über die Werte in den Noten-Kommandos `0x2B` bis `0x30`, die die CPU laufend je Stimme schickt | gemessen (Hacktribe, Part 1) |
| Wort 1 einer Stimme (Ziel von `0x2B`) ist nicht die Note: Sequencer-Noten 48, 60 und 72 ergeben denselben Wert `0x3B00`; Wort 2 (Ziel von `0x2C`) ändert sich mit PITCH, aber nicht linear (Regler 0, 64, 96, 127 ergibt -24, -8, -1,6, 0 in 1/256-Schritten gerechnet). Bedeutung offen | gemessen (Hacktribe, rot, blau gleich) |
| Stimmen: 24 Blöcke zu 0x1A Parametern ab `0x43AB` (`0xFF900EAC`), gelesen von der Stimmenschleife `0xFFA0141A`. Eine Note kopiert mit `9` die Vorlage ihres Parts (Parameter `0x18 + 0x1A * Part`) in eine freie Stimme, setzt `+0x15` (Velocity-Gain) und dann Wort 0 (Gate) auf 1; das Ende der Note setzt das Gate mit `0x26` auf 0. Stimmen werden reihum vergeben. Die Zahl 24 ist hergeleitet (die Blöcke enden bei `0x461B`, dem ersten Part-Zustand) | gelesen, gemessen (Hacktribe, rot, blau) |
| Velocity-Gain `+0x15`: Velocity 127 → `0x0BD0`, 100 → `0x0690`, 30 → `0x014B` (Hacktribe); blau bei 100 → `0x0497`. | gemessen |
| Parameter `0x2C2 + 0x6D * Part + 0x23` geht jede Millisekunde an den DSP, gleich bei Velocity 127 und 30; Bedeutung offen | gemessen |
| Part-Schalter im DSP: die Audioschleife `0xFFA019DE` überspringt einen Part mit Schalter 0 und löscht seinen Ausgangszustand (`0xFF90186C + 0x118 * Part`, +0x100); mit 1 läuft er beim nächsten Sample wieder, nichts bleibt hängen | gelesen |
| FIFO `0xFF900018`/`0xFF900098` (Handler `0x17FF8`): zwei Puffer zu 32 Wörtern, Eintrag = Flags << 28 \| Kanal << 22 \| Code << 16 \| Wert, Kanal 62 beendet den Puffer. Code `0x20` auf Kanal 0 bis 32 ist das Tempo in hundertstel BPM (`0xFF900004`), danach rechnet der Effekt des Kanals seine Tempo-Zeiten neu (`0x17C78`) | gelesen; Tempo 155.5 schickt `0x3CBE` an alle 33 Kanäle: gemessen |
| Der alte Part-Reset (develop) schickt zusätzlich den Schalter aus/an, `0x31E = 0`, ein Kommando `0x39` und über das FIFO das aktuelle Tempo an alle Kanäle; alle anderen Zugriffe sind mit #506 gleich. Nichts davon hält den Part im DSP stumm | gemessen (Emulator), gelesen |
| Kommando `0` setzt DSP-Parameter: Wort 2 = Anzahl Paare minus 1, dann Paare (Parameter, Wert). Ein Paar `0xC0011F54`, zwei Paare `0xC001203C` | gelesen (Hacktribe), gemessen |
| Parameter `0x2C2 + 0x6D * Part` (blau `0x2A8 + 0x6D * Part`) ist der Schalter des Parts am DSP, 1 an, 0 aus | gelesen (`0xC0093A20`, `0xC0093988`, blau `0xC0081680`), gemessen |
| Jede Note schaltet ihren Part wieder an (Sampler `0xC0093988`, ohne Prüfung des Bits in `0xC06914E8`); das Abschalten `0xC0093A20` schickt nur etwas, wenn das Bit gesetzt ist, also nach einer Note | gelesen, gemessen |
| Nach dem Start ohne Note hat ein Part nie einen Schalterwert bekommen; das Modell meldet dann `None` | gemessen |
| LEVEL, PAN und PART MUTE schicken beim Bedienen nichts an das Postfach; LEVEL ändert nur den Pattern-RAM, ein stummer Part schickt keine Note | gemessen (LEVEL, MUTE auf Part 1, Hacktribe) |

Das Modell (`DspModel.attach(machine)`) hängt sich vor `machine.write` und `machine.dsp_read`. Es hält ein Bild des DSP-Speichers
(`mem`, `word(adresse)`): Postfach-Kommandos schreiben ihre Slots, andere Schreibübertragungen landen unverändert an ihrer
Adresse. Dazu den letzten Wert jedes Parameters, jede Schaltung eines Parts mit Gerätezeit, die Zahl je Kommando
(`commands`), die FIFO-Einträge (`fifo`), das Tempo je Kanal (`tempo`) und jedes Öffnen und Schließen einer Stimme mit ihrem
Part (`gates`). Abfragen: `part_on(p)`, `switched_off(p, since)`, `parts_switched_off(since)`, `mark()`, `voices()` (offene
Stimmen mit Part und Velocity-Gain), `notes(part, since)`.

Lesen beantwortet das Modell nur für den Ausgangs-Spitzenpegel `0xFF9030F4..0xFF9030FB`: der größere Wert aus dem zuletzt
Geschriebenen und dem Pegel, den ein Fall mit `output(links, rechts)` setzt (0 bis 1). Alle anderen Lesezugriffe liefern wie
bisher 0.

## Regressionsprüfung #506

Ablauf je gestoppt und laufend: alle 64 Schritte von Part 1 an, Pad 1 (Note, Part 1 am DSP an), OSC drei Rastungen, dann EXIT +
Pad 1. Geprüft: Part 1 war vorher an, während des Resets schaltet nichts einen Part ab, danach ist Part 1 an.

| Stand | Hacktribe | rot | blau |
|---|---|---|---|
| develop (Reset mit der Klangeinrichtung von Copy Part, #470) | Part 1 abgeschaltet, beide Fälle rot | gleich | gleich |
| #506 (Sample-Handler wie das SAMPLE-Rad) | nichts abgeschaltet, beide Fälle grün | gleich | gleich |

Gemessen 12.11. Die Prüfung fragt die DSP-Seite, nicht eine Firmware-Adresse wie der Hook-Fall in #506
(`exit_pad_keeps_the_part_on_*`); sie greift also auch, wenn ein anderer Weg den Part abschaltet.

Bis #506 auf develop ist (Back-merge von 1.4.6), schlagen die zwei neuen Fälle auf develop fehl. Das ist gewollt: genau der
Fehler, den sie finden sollen.

## Stimmen gegen den Sequencer

Part 1 auf allen 64 Schritten, Part 3 auf jedem vierten, 1,5 s gespielt: der Note-on-Hook der Firmware zählt 22 Noten, das Modell
22 geöffnete Stimmen (Part 1: 17, Part 3: 5, andere: 0), 20 wieder geschlossen, 2 klingen noch. Gleich auf Hacktribe, rot und
blau (12.11.). Prüffall `shortcut:dsp_voices_follow_the_sequencer` (`case_voices_dsp`).

## Grenzen

- **Offen:** Warum der Part am Gerät stumm blieb. Der DSP-Verkehr des alten Resets, so wie ihn der Emulator sieht, erklärt es
  nicht (siehe oben). Hergeleitet: die Ursache liegt CPU-seitig oder in einem Zustand, den der Emulator anders hat als das Gerät.
  Das Modell sagt deshalb nicht "hörbar", sondern nur "abgeschaltet worden" und "zuletzt an".
- **Offen:** Bedeutung der übrigen 108 Parameter je Part; die Noten-Kommandos sind nur gezählt.
- **Nicht im Modell:** ein eigenes Ausgangssignal. Der Spitzenpegel kommt nur aus `output()`. Welche Stimme wann klingt, weiß das
  Modell; wie laut, rechnet der DSP in der Stimmenschleife `0xFFA0141A` und der Part-Schleife `0xFFA019DE` aus Sample-Daten,
  Velocity-Gain, Hüllkurve, Filter und Part-Pegel. Das ist Rechnen wie der DSP, nicht mehr Mitlesen. Der Versuch mit dem echten
  DSP-Code im Simulator: [DSP im Simulator](2026-11-12-dsp-im-simulator.md).
