# Neue Katalog-Effekte für Bass, Kick, Verzerrung und Mix (11.11.)

Stand 2026-11-11. 14 Insert-Effekte, 3 Master-Effekte und 4 Modulationen in `data/fx/catalog.mjs`, Beschreibung in
[Effekt-Katalog](../effekt-katalog.md). Eingaben: Korgs rotes Original 2.02 (`1d0f0689...`) und Hacktribe 2.02 (`7cb4825c...`),
eigene Dateien. Markierungen: **gemessen** (ausgeführt), **hergeleitet**, **offen**. **Kein Effekt ist am Gerät gehört.**
Der Emulator rechnet kein Audio und der DSP ist dort nur ein Stub ([MFX-DSP](2026-10-09-mfx-dsp.md)): die DSP-Last und der Klang sind
mit ihm nicht messbar.

## Was gebaut wird

Es gibt keinen neuen Baustein und keinen neuen DSP-Code. Jeder Effekt ist eine Einstellung der 66 Bausteine, die in der Firmware
stecken (`data/units.json`), die Modulationen sind Einträge der 72-Arten-Tabelle. Die Werte stammen aus den Werkspresets desselben Bausteins
(Hacktribe und Korg rot), die Stufe-2-Bausteine aus der [Messreihe](2026-09-21-stage2-sweep.md).

## Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| Alle 21 Einträge lesen als .e2fx v2 zurück (Namen und Spannen der Parameter stimmen) | gemessen | `readFx(fxText(p))` je Eintrag, `test/fx-v2.test.mjs` |
| Die 17 Insert- und Master-Records bauen gegen Hacktribe und Korg rot ohne Fehler; Menüs Hacktribe Insert 49 auf 73, Master 32 auf 43; Korg rot Insert 38 auf 62, Master 32 auf 43 | gemessen | `appendPresets` auf beiden Originalen; Kapazität 128 |
| Der Linter meldet für die neuen Effekte nur Warnungen: `rest-not-silent` (auch bei 61 von 81 Werkspresets), bei Bit Grinder, Alias Crush und Master Warmth dazu `output-above-usable` | gemessen | `lint` je Record. Der Linter kennt keine Einheit, die Werkspresets des Decimators (127) und der Röhrenvorstufe (66) stehen ebenso über seinem Bereich 38 bis 60 |
| Kein neuer Effekt steht über den Pegelgrenzen der Werkspresets seiner Einheit (Distortion 20, Acid Drive 65, Level Mod 36) | gemessen | `test/fx-v2.test.mjs`, `LEVEL_CAPS` |
| Jeder Eintrag geht durch den Türsteher der Sammeldatei | gemessen | `test/fx-v2.test.mjs`, "every catalog effect passes" |
| Emulator, Hacktribe: Start 15 von 15, `preset_cases` 12 Prüfungen, `fx_card_cases` 22 Prüfungen, alle grün (INSERT-Regler läuft alle Plätze durch und springt zurück, jeder neue Platz hat Record und Namen, jede Wahl schickt dem DSP Übertragungen, keine Assertion; Sammeldatei lädt) | gemessen | `node tools/verify-patches.mjs --cases preset_cases,fx_card_cases <Original>`, 55 Prüfungen |
| Dasselbe auf Korg rot | gemessen | derselbe Befehl, 55 Prüfungen |
| Blaue Electribe | offen | der Katalog gilt nur für rot ([Katalog fest](2026-10-23-fx-katalog-fest.md)), nicht gelaufen |
| Klang, Lautstärke, DSP-Last, Knacken beim Umschalten | offen | nur am Gerät |
| Zwei Stufen aus Kompressor, EQ, Limiter und Verzerrer laufen am Gerät | offen | gemessen sind nur die Stufe-2-Bausteine mit Filter in Stufe 1 und die Werkketten Acid Drive und EQ, Filter und Filter, Filter und Acid Drive. Alle anderen Paare (Verzerrer und Limiter, EQ und Limiter, SR1 und Limiter) sind nicht gelaufen |

## Herleitungen, auf denen die Werte stehen

- **Gate.** Bounce Gate nimmt den Level Mod (`0x15`) mit der Quelle EXP (4), wie Korgs Pumper (mpy, Sync an, Play auf `lfo_reset`). Die Tiefe
  steht auf 8 statt 126: [Level Mod](2026-09-21-level-mod.md) nennt 0 "pumpt auf die Eins" und 126 "gegen die Eins", die Richtung ist die
  umgekehrte des Pumpers. Notenwert 8 ist 1/16, 7 ist 1/8 ([Sync-Notenwerte](2026-10-14-offene-fragen.md), Abschnitt 8, Einheit "Takt oder Viertel" dort offen).
  **Hergeleitet, nicht gehört:** ob der Anschlag vorn laut ist und hinten abklingt, oder umgekehrt. Dann hilft eine Tiefe um 118.
- **Modulationen.** Quelle 0 ist die Hüllkurve, Ziel 3 Filter, 8 Level, 1 Pitch ([Stufe 2](2026-10-15-modulation-stufe2.md)). Pitch-Spitze bei
  Stärke 63 ist 6144, bei 50 3481, bei 12 153; 6144 ist 24 mal 256, die Einheit ist also vermutlich 1/256 Halbton (hergeleitet).
  Daraus: Stärke 16 ist rund 1,6 Halbtöne (Bounce Pitch), 56 rund 18 (Kick Drop), 63 24 (Kick Click). Die Hüllkurve fällt auf die Hälfte
  bei MOD. SPEED 20 in 27 ms, bei 50 in 137 ms: Speed 12, 26, 36 sind hergeleitet etwa 10, 45, 80 ms. Die Zeit hängt vom Paar `+0x28`, `+0x29` des
  überschriebenen Platzes ab, die Modulation schreibt es nicht: darum die Empfehlung, einen EG+-Platz (1 bis 6) zu nehmen.
- **EQ-Frequenzen.** Index 0 bis 58 vermutlich eine 1/6-Oktav-Reihe ab 20 Hz (hergeleitet, offen laut [FX-Tabellen](2026-10-14-fx-tabellen.md)):
  Index 12 wäre rund 80 Hz, 22 rund 250 Hz. Der Typ 3 eines EQ-Bandes steht im Werkspreset für "aus"; die neuen Effekte benutzen nur 0 (Peak),
  1 (Höhen-Regal) und 2 (Tiefen-Regal) mit den Werkspresets als Vorbild.
- **Pegel.** Verzerrer bleiben bei `output_level` 14 bis 17 (Grenze 20, [Pegel](2026-10-29-fx-katalog-pegel.md)). Die Werte für Bit Grinder,
  Alias Crush (90) und Master Warmth (84) sind geschätzt, Werkspresets stehen bei 127 und 66.

## Was nicht geht

- **Falten, Transienten-Former mit Notenauslöser, eine Hüllkurve für Attack und Decay des Verstärkers:** kein Baustein dafür, keine
  Stelle im Effekt, die den Part berührt. Näher kommen das Gate (am Takt) und Bounce Pluck (an der Note).
- **Kompressor oder Limiter als Modulation:** Ziele der Modulation sind Pitch, OSC, Filter, Level, Pan und IFX, sie misst keinen Pegel.
- **Decimator mit zweiter Stufe, SR1 in Stufe 2:** gemessen Absturz ([Stufe 2](2026-09-21-stage2-sweep.md)).

## Offen: was am Gerät zu prüfen ist

1. Bounce Gate 16 und 8: Richtung (laut am Anfang?), Verhältnis zum Takt, Play setzt neu an.
2. Bounce Pluck, Bounce Pitch, Kick Drop, Kick Click auf einem EG+-Platz: Länge, Stärke, ob die Pitch-Einheit stimmt.
3. Zwei-Stufen-Effekte (Bass Enhancer, Hardtekk Kick, Tekk Kick Soft, Warm Drive, Glue Comp): läuft Stufe 2, Pegel, kein Absturz.
4. Alle Pegel, besonders Bit Grinder, Alias Crush, Master Warmth, Master Glue.
5. Die DSP-Last mit vielen Parts auf diesen Effekten (Korg nennt zu viele schwere Effekte als Grund für ausbleibende Noten).
