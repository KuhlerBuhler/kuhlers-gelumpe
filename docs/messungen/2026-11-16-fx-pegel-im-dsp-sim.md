# FX-Pegel im DSP-Sim (16.11.2026)

Ersetzt die Hörtests aus 1.4.7 durch Messungen mit Korgs echtem [DSP](../glossary.md#dsp)-Code im
GNU-bfin-Sim (`tools/dsp/blackfin_worker.c`, Backend `tools/emu/blackfin_backend.py`).
Fall: `tools/emu/fx_level_cases.py`, Rechenteil getestet in
`tools/emu/test_fx_level_cases.py`.

## Methode

- **Testsignal.** SPORT0 RX spielt eine Datei im Kreis (`BLECH_SPORT_RX_SOURCE`,
  neuer Eingang `file`). Darin stehen 0,2 s Sinus 1 kHz mit -12 dBFS Spitze und
  dann 0,05 s Rauschstoß mit -6 dBFS RMS.
- **Weg zum DSP.** Part 1 bekommt den Oszillator "Audio In Mn" über den
  SAMPLE-Encoder. HT und rot nutzen dieselbe Tabelle. Pad 1 bleibt gehalten.
- **Inserts.** Gewählt über den IFX-Encoder plus IFX ON, wie am Panel. Der
  Name wird über die Firmware-Funktion gelesen und geprüft.
- **Master.** Gewählt über SET_MFX (0xC0048A64) mit MFX SEND an. Der Touchpad
  steht in der Mitte (500/500) und ist gedrückt. Nach 0,3 s Einschwingen kommt
  ein Fenster von 0,5 s.
- **Messwerte.** Ausgang ist Slot 0 und 2 aus dem TX-Mitschnitt. Alle Werte
  sind dB gegen das trockene Signal im selben Lauf:
  - Inserts gegen IFX aus.
  - Master gegen MFX SEND an ohne Effekt.
- **Kennzahlen.**
  - `rms`, `peak`: über das ganze Fenster.
  - `sinus`: nur im Sinusteil.
  - `stoß`: nur im Rauschstoß.
  - `hell`: Höhen minus Tiefen (über 4 kHz gegen unter 500 Hz).
  - `einbr.`: 2-ms-Blöcke im Sinusteil unter der halben Medianleistung.

### Grenzen

- Nur relative Pegel. Codec, Ausgangsstufe und Main-Volume sind nicht
  modelliert. Ein Effekt, der im Sim -3 dB macht, macht am Gerät auch -3 dB
  gegen trocken. Wie laut das absolut klingt, sagt der Sim nicht.
- Touchpad nur in der Mitte. Andere Positionen sind nicht gemessen.
- Der Master-Eingang hat höchstens -12 dBFS Spitze. Schwellen, die erst über
  echten Drums greifen, werden mit dem gemischten Signal nur teilweise erreicht.
- Bei Delays und Hall zählt das Fenster auch Echos. `rms` ist dann eher
  "Lautheit im Fenster" als Verstärkung.

## Ergebnisse HT 1.4.7 (gemessen)

Firmware: Patcher dieses Branches auf HT 163d1d8d. 89 IFX, 58 MFX. Trocken:
-21,7 dBFS RMS, -12,0 dBFS Spitze.

### Inserts

| Effekt | rms | peak | sinus | stoß | hell | einbr. | rot 1.4.7 rms | HT 1.4.6 rms |
|---|---|---|---|---|---|---|---|---|
| Loud Distortion | -2,3 | -3,3 | +0,5 | -5,9 | -6,5 | 0 | -2,3 | +3,3 |
| Bounce Gate 16 | +7,5 | +8,7 | +6,7 | +8,5 | +1,3 | 24 | +5,5 | +3,0 |
| Bounce Gate 8 | +6,8 | +7,4 | +8,4 | +7,2 | +0,6 | 42 | +5,5 | +2,3 |
| Warm Drive | +4,5 | +6,2 | +7,3 | +0,9 | -15,9 | 0 | +4,5 | +3,3 |
| Bit Grinder | -2,9 | -1,4 | -0,9 | -4,7 | -7,6 | 0 | -2,9 | -5,9 |
| Glue Comp (#637) | -6,3 | +2,5 | -21,9 | -3,0 | +3,8 | 0 | -6,3 | -18,3 |
| Bass Enhancer (#544) | -1,6 | -0,2 | -2,9 | -1,0 | +2,1 | 0 | -1,6 | -1,6 |
| Hardtekk Kick (#544) | +7,1 | +5,0 | +9,5 | +4,6 | +2,7 | 0 | +7,1 | +7,1 |

Kein DSP-Absturz, auch nicht bei Bass Enhancer und Hardtekk Kick. Die Bounce
Gates schneiden wie gewollt (Einbrüche).

### Master

| Effekt | rms | peak | sinus | stoß | hell | einbr. | HT 1.4.6 rms |
|---|---|---|---|---|---|---|---|
| Master Pumper | -3,3 | +0,1 | -5,2 | -6,9 | +0,5 | 0 | -6,2 |
| Multi Tap | -6,0 | -4,1 | -4,6 | -13,6 | -24,3 | 0 | -6,2 |
| Wow Tape | -5,1 | -3,8 | -4,3 | -16,6 | -18,7 | 4 | -4,8 |
| Dub Delay | -3,6 | -1,9 | +0,5 | -6,4 | -13,2 | 7 | -3,3 |
| Ping Pong | -4,9 | -2,7 | -3,6 | -14,1 | -5,7 | 32 | -4,7 |
| Ladder Drive | -11,1 | -6,8 | -11,6 | -10,7 | -34,1 | 0 | -11,1 |
| Ring Crush | -24,3 | -19,6 | -60,4 | -24,0 | -21,8 | 0 | -21,2 |
| Master Limiter | -9,5 | -5,0 | -10,6 | -7,1 | +0,5 | 24 | +1,5 |
| Master Glue | +0,1 | +0,1 | +0,1 | +0,1 | +0,5 | 0 | +0,1 |
| Master Tilt | fehlt | | | | | | -0,2 |
| Master Warmth | fehlt | | | | | | -0,2 |

Master Tilt und Master Warmth gibt es in 1.4.7 nicht mehr (1.4.6: 60 MFX,
1.4.7: 58). Bei Delays, Wow Tape und Ping Pong kommen die Einbrüche vom
Echomuster und sind kein Aussetzer.

### rot 1.4.7

Patcher dieses Branches auf rot 2.02. 74 IFX, 41 MFX.

- Inserts: gleich wie HT bis auf 0,2 dB. Ausnahme sind die Bounce Gates
  (+5,5 statt +7,5 / +6,8). Der DSP-Code ist bei rot und HT Byte für Byte
  gleich.
- Master: Pumper -3,5, Limiter -9,5 mit 26 Einbrüchen, Glue +0,1.
- Multi Tap, Wow Tape, Dub Delay, Ping Pong, Ladder Drive und Ring Crush sind
  HT-Presets und fehlen auf rot.

## Nur Sinus, kein Rauschstoß (HT 1.4.7, gemessen)

Mit `--no-burst` wird geprüft, welche Effekte vom Pegel abhängen.

| Effekt | Sinus -12 dBFS | Sinus -3 dBFS |
|---|---|---|
| Glue Comp | -21,9 | +11,6 (Ausgang -1,6 dBFS Spitze) |
| Master Pumper | -3,2 | -3,3 |
| Ladder Drive | -11,6 | -11,6 |
| Ring Crush | -60,4 | -61,0 |
| Master Limiter | -2,1, 0 Einbrüche | -2,1, 0 Einbrüche |
| Master Glue | +0,1 | +0,1 |

## Befunde

- **Master Limiter (1.4.7).**
  - Auf einem gleichmäßigen Sinus: -2,1 dB, keine Einbrüche (gemessen).
  - Mit Rauschstoß: -9,5 dB und 24 Einbrüche im Sinus danach (gemessen).
  - Der Limiter bleibt also nach lauten Stellen lange unten und holt dann in
    Stufen auf (hergeleitet). Das passt zur Gerätebeschreibung "setzt kurz aus
    wie ein leichter Slicer".
  - In 1.4.6 machte derselbe Fall +1,5 dB ohne Einbrüche (gemessen). Das Verhalten
    ist also mit 1.4.7 gekommen.
- **Ring Crush.**
  - Der 1-kHz-Sinus wird um 60 dB gedämpft.
  - Der Stoß bleibt mit -24 dB und wird deutlich dunkler (hell -21,8).
  - Bei Touch in der Mitte wirkt er damit wie ein Tiefpass ohne hörbaren Ring.
    Das passt zur Meldung "nur Lowpass" (gemessen in der Mitte, Urteil für den
    Rest des Pads).
- **Glue Comp (Insert, #637).**
  - 9 dB mehr Eingang ergeben 42,5 dB mehr Ausgang (gegen trocken von -21,9
    auf +11,6).
  - Er arbeitet also wie ein steiler Expander, nicht wie ein Kompressor
    (gemessen).
  - Laute Signale kommen bis knapp unter Vollaussteuerung raus.
- **Master Glue.** +0,1 dB in jedem Fall, keine Klangänderung. Er wirkt im Sim
  nicht messbar (gemessen).
- **Ladder Drive.**
  - Gemessen: -11,1 dB und sehr dunkel (hell -34). Bei Sinus bis -3 dBFS
    bleibt er sauber (stärkster Oberton -75 dB).
  - Die Gerätemeldung "zu laut" lässt sich mit Touch in der Mitte und diesen
    Eingangspegeln nicht nachstellen. Es braucht eine Referenz vom Gerät.
- **Delays (Multi Tap, Wow Tape, Dub Delay, Ping Pong).** 3,6 bis 6 dB leiser
  als trocken, das passt zur Gerätemeldung. Unterschied zu 1.4.6 unter 0,4 dB.
- **1.4.6 gegen 1.4.7.** Mit 1.4.7 geändert (gemessen):
  - Loud Distortion -5,6 dB
  - Bounce Gates +4,5 dB
  - Glue Comp +12 dB
  - Bit Grinder +3 dB
  - Pumper +2,9 dB
  - Limiter -11 dB
  - Kandidaten sind die Stufe-2-Änderungen zwischen den Releases, z. B.
    815af593 (Bank B beim Boot nullen) sowie e4f0309b und 073ab45c
    (Stufe-2-Sperren). Nicht einzeln gemessen, das ist hergeleitet.
  - Unverändert sind Bass Enhancer, Hardtekk Kick, Ladder Drive, Glue und die
    Delays.

## Part-Reset (#611 / #506)

Fall `reset` mit dem SAW-Init-Sound von Part 1, Pad 1 gehalten. Er liest den
ganzen DSP-Part-Block (0x6D Wörter), die Stimmen und 0,3 s Ausgang.

### Ablauf

1. **Referenz.** IFX ON. Danach IFX-Encoder +3 und -3 (Rundweg), IFX ON aus.
2. **Verstellen.**
   - Knöpfe: Pitch 230, Level 30, Pan 240.
   - CUTOFF-Encoder -30.
   - IFX-Encoder +3, dann IFX ON.
3. **Reset.** EXIT + Pad 1. Danach wieder halten und IFX ON.

### Ergebnis (gemessen, HT und rot gleich)

- **Verstellen kommt beim DSP an.** Ausgang -36,9 dB, Helligkeit +4,3 dB.
  Diese Wörter ändern sich:
  - PITCH (0x02, 0 auf 241565696)
  - LEVEL (0x23) und PAN links (0x5F)
  - IFX ON (0x5C), Insert-Wörter 0x5D/0x5E
  - weitere, im DSP-Modell noch unbenannte Wörter 0x16, 0x18, 0x19, 0x24, 0x2B, 0x61 (CUTOFF schreibt keins der benannten)
- **Nach dem Reset ist jedes dieser Wörter zurück.**
  - PITCH 0, Ausgang -0,03 dB, Helligkeit -0,02 dB.
- **IFX-Typ.**
  - Der andere Typ ist hörbar (Helligkeit +2,8 / +2,9 dB).
  - Nach Reset und IFX ON sind alle Insert-Wörter wie nach dem Rundweg und der
    Ausgang ist 0,0 dB gleich.
- **0x26, 0x34..0x54.**
  - Diese 25 Wörter auf rot (auf HT 24, dort zählt 0x50 als DSP-Zustand) schreibt der IFX-Typwechsel allein.
  - Der Rundweg +3/-3 ohne Reset lässt sie genauso stehen, bei gleichem Klang
    (0,0 dB, Helligkeit 0,0).
  - Sie sind Parameter des zuletzt geladenen Typs und kein Reset-Fehler
    (gemessen, Deutung hergeleitet).
  - Auf HT ändern 0x4F/0x50 sich auch ohne Bedienung, das ist DSP-Zustand.
- **Kein DSP-Absturz.**

#611/#506 ist im Sim damit erfüllt: Der DSP-Part-Block bekommt CUTOFF, IFX-Typ,
PITCH, LEVEL und PAN zurück, und die Stimme klingt wie vorher.

## Noch nötige Referenzaufnahmen am Gerät

Der Sim misst nur relativ. Damit die Zahlen fürs Gerät gelten, braucht es:

1. **Ein Effektpegel am Gerät gegen den Sim.** Gleiches Testsignal über Audio
   In, Master Pumper oder Loud Distortion an und aus, Pegel am Ausgang
   aufnehmen. Liegt die Differenz innerhalb von 1 dB vom Sim, gelten die
   Tabellen oben.
2. **Ladder Drive.** Mit heißem Eingang (Drums nahe 0 dBFS) und Touch an
   mehreren Stellen (Ecken, oben, unten), um "zu laut" zu finden.
3. **Master Limiter mit Drums.** Einen Loop mit und ohne Limiter, 1.4.6 gegen
   1.4.7, um das Aufholen nach lauten Stellen am Gerät zu bestätigen.
4. **Ring Crush.** Touch an mehreren Stellen, um zu sehen, ob der Ring
   irgendwo hörbar wird.

## Wiederholen

```bash
cd tools/emu
.venv/bin/python fx_level_cases.py levels --vsb <SYSTEM.VSB> --worker <blackfin-worker>
.venv/bin/python fx_level_cases.py levels --vsb <SYSTEM.VSB> --worker <blackfin-worker> --no-burst --sine-dbfs -3 --only Glue_Comp,Master_Limiter
.venv/bin/python fx_level_cases.py reset --vsb <SYSTEM.VSB> --worker <blackfin-worker>
```

Ein voller `levels`-Lauf dauert 21 bis 32 Minuten, `reset` 5 bis 7 Minuten
(gemessen auf dem Mac). Vorher `node tools/load-gate.mjs` ausführen. Fortschritt
steht in `~/.claude/progress/<label>.json`.
