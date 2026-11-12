# DSP-Modell im Emulator, für Prüfungen

Stand 12. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02, Korgs Original 2.02 rot und blau (eigene Dateien), jeweils
mit dem BLECH-Satz von develop und mit dem Stand von #506. **Am Gerät nicht geprüft.** Kein Ton, nur was die CPU dem DSP sagt.

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
| Wort 0 ist `0x106`, Wort 1 das Kommando. Im Leerlauf kommen nur die Kommandos `1` und `0x31` (Pegel abfragen) | gemessen |
| Kommando `0` setzt DSP-Parameter: Wort 2 = Anzahl Paare minus 1, dann Paare (Parameter, Wert). Ein Paar `0xC0011F54`, zwei Paare `0xC001203C` | gelesen (Hacktribe), gemessen |
| Parameter `0x2C2 + 0x6D * Part` (blau `0x2A8 + 0x6D * Part`) ist der Schalter des Parts am DSP, 1 an, 0 aus | gelesen (`0xC0093A20`, `0xC0093988`, blau `0xC0081680`), gemessen |
| Jede Note schaltet ihren Part wieder an (Sampler `0xC0093988`, ohne Prüfung des Bits in `0xC06914E8`); das Abschalten `0xC0093A20` schickt nur etwas, wenn das Bit gesetzt ist, also nach einer Note | gelesen, gemessen |
| Nach dem Start ohne Note hat ein Part nie einen Schalterwert bekommen; das Modell meldet dann `None` | gemessen |
| LEVEL, PAN und PART MUTE schicken beim Bedienen nichts an das Postfach; LEVEL ändert nur den Pattern-RAM, ein stummer Part schickt keine Note | gemessen (LEVEL, MUTE auf Part 1, Hacktribe) |
| Während einer Note geht laufend Parameter `0x2C2 + 0x23` (Part 1) mit wechselnden Werten an den DSP; was er bedeutet, ist offen | gemessen |

Das Modell (`DspModel.attach(machine)`) hängt sich wie `DspLog` vor `machine.write`, ändert keinen Rückgabewert und keine
Lesedaten. Es hält den letzten Wert jedes Parameters und jede Schaltung eines Parts mit Gerätezeit. Abfragen: `part_on(p)`,
`switched_off(p, since)`, `parts_switched_off(since)`, `mark()`.

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

## Grenzen

- **Offen:** Warum der Part am Gerät stumm blieb, obwohl die nächste Note ihn wieder anschaltet (im Emulator gemessen: nach dem
  Reset schickt die nächste Note den Schalter wieder auf 1). Hergeleitet: das Abschalten setzt im DSP etwas zurück, das erst
  ein neues Sample (SAMPLE-Rad) und Stop/Start wieder einrichten. Der DSP-Code ist nicht emuliert, das Modell sagt deshalb
  nicht "hörbar", sondern nur "abgeschaltet worden" und "zuletzt an".
- **Offen:** Bedeutung der übrigen 108 Parameter je Part und der anderen Kommandos (Noten: `0x2B` bis `0x36`, `9`, `0x16`).
- **Nicht im Modell:** Sample-Übertragungen (`0xAB` an andere Adressen, Effekt-Puffer `0xFF900018`, `0xFF900098`), Lesen.
