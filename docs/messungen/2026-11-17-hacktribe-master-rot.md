# Hacktribes Master-Effekte auf der roten 2.02 (17.11.)

Stand 17.11.2026, Emulator, Korgs Original 2.02 rot (sha256 `1d0f0689...`) und Hacktribe 2.02 (`7cb4825c...`).
Frage: kommen die vier Nachbauten von Hacktribes Master-Effekten (Big Hall, Plate Reverb, Tap Delay Sync, Tube Drive)
sauber auf die Plätze 33 bis 36 der roten 2.02, und schicken sie dem DSP dieselben Bausteine wie Hacktribes eigene?
Vorarbeit: [Hacktribes Extras auf rot](2026-11-10-hacktribe-extras-rot.md). Am Gerät nicht gehört.

Marker: **gemessen** (im Emulator ausgeführt), **hergeleitet**, **offen**.

## Ergebnis

| Behauptung | Marker | Beleg |
|---|---|---|
| Rot mit dem BLECH-Set: Master 33 bis 36 sind Big Hall (`M_hall_reverb`, 54), Plate Reverb (`M_wet_plate_reverb`, 56), Tap Delay Sync (`M_tape_echo`, 60), Tube Drive (`M_tubepre`, 47); Menü 45 | gemessen | `preset_cases.py cases`, `presets:ht_mfx_names` |
| Der Katalog beginnt auf rot bei 37 (Short Delay), bisher 33 | gemessen | `presets:ht_mfx_catalog_from_37` |
| Jeder der vier lässt sich wählen, setzt den Typ und schickt 11 Transfers, keine Asserts | gemessen | `presets:ht_mfx_select` |
| VALUE auf der Seite MFX TYPE läuft durch alle 45 Typen, 33 bis 36 eingeschlossen, und springt von 44 auf 0 | gemessen | `presets:ht_mfx_page_walk` |
| Alle 16 Prüfungen von `preset_cases` grün auf rot; auf dem Stand von `release/1.4.7` davor 14 von 16 (33 bis 36 hielten Short Delay bis Master Pumper) | gemessen | gleiche Prüfungen, beide Sets aus derselben Original-Datei |
| Hacktribe mit dem BLECH-Set: seine vier bleiben auf 10, 11, 21, 32, der Katalog beginnt weiter bei 33; die gepatchte Datei ist Byte für Byte die von `release/1.4.7`; 13 von 13 grün | gemessen | `presets:ht_mfx_hacktribe_keeps`, sha256 der gebauten Dateien |
| Gegen Hacktribes eigene (10, 11, 21, 32): gleich viele Transfers (11), gleiche Befehle und Längen in derselben Reihenfolge (`same_blocks`), also dieselben Bausteine; die Werte weichen ab (`same_dsp` falsch), 302 bis 308 von 320 Wörtern gleich | gemessen | `preset_cases.py ht-mfx` |
| Wie die vier am Gerät klingen | offen | nur am Gerät |

## Die Werte

Nicht Hacktribes Bytes. Jeder Nachbau geht von Korgs Werkspreset desselben Typs aus und ist in Richtung von Hacktribes
Preset gesetzt, mit eigenen Werten (hergeleitet):

- Big Hall: Korgs Wet Reverb als Ausgang, Zeit 120, Höhendämpfung 88, im Baustein `M_hall_reverb`.
- Plate Reverb: Korgs Hall Reverb leicht verschoben, im Baustein `M_wet_plate_reverb`.
- Tap Delay Sync: Korgs Tape Delay, Notenwerte 6 und 8, Ausgangspegel 44, Rückkopplung 68 (unter Korgs 70), leichtes LFO.
- Tube Drive: Korgs Tube EQ mit offenen Filtern, Y fährt Sättigung und Gain, nimmt den Ausgangspegel zurück.

Die Felder stehen in `data/fx/catalog.mjs` (`hacktribe: true`).

## Wie gemessen

    node tools/patch/ensure-runtime.mjs
    # Set gebaut mit applyPatches (src/patch.mjs) und data/patches/blech.json, je Original
    tools/emu/.venv/bin/python tools/emu/preset_cases.py cases --base ORIGINAL.VSB --patched BLECH.VSB
    tools/emu/.venv/bin/python tools/emu/preset_cases.py ht-mfx --patched BLECH-ROT.VSB --hacktribe HACKTRIBE.VSB

`ht-mfx` startet beide Dateien, wählt jeden Nachbau und Hacktribes Preset auf seinem Platz und vergleicht die
Transfers über den DSP-Host-Port (`DspLog`).

## Offen am Gerät

- Hörtest der vier auf rot, neben Hacktribes eigenen.
- Lautstärke von Big Hall und Tube Drive gegen Korgs Werkspresets.
