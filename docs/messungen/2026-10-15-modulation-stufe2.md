# Modulationsarten, Stufe 2: was die übrigen Bytes eines Eintrags tun

Stand 2026-10-15. Kein Gerätezugriff. Alles ist im Emulator gemessen (Firmware 2.02 mit Hacktribe, eigene
`SYSTEM.VSB`, eigener Flash-Dump), nichts am Gerät. [`tools/emu/modtable_probe.py`](../../tools/emu/modtable_probe.py)
wiederholt jede Messung (`E2_VSB=... E2_FLASH=... tools/emu/.venv/bin/python tools/emu/modtable_probe.py`, rund zehn
Minuten auf vier Prozessen), die Namen der Prüfungen stehen in Klammern. Marker: **gemessen (Emulator)**, **offline** (Code
gelesen, nicht ausgeführt), **hergeleitet**, **offen**.

Stufe 1 machte Name, Ziel, Vorgabetiefe, Vorgabe-Speed und Kurve der 72 Arten bearbeitbar
([Stufe 1](2026-10-14-offene-fragen.md), Abschnitt 9). Hier geht es um alles ab Byte `+0x14` eines Eintrags: was die
Firmware davon liest, was es tut, was nichts liest. Eine Messung verändert die Tabelle, die die Firmware liest (RAM
`0xC019FFFC`, live) oder eine gebootete Kopie der Firmware-Datei, wählt eine Art mit MOD. TYPE, stellt MOD. DEPTH und
MOD. SPEED, spielt eine Note auf Part 1 und sieht an drei Stellen nach:

- am **Zustand je Part im RAM**: neun Byte je Part (`0xC06924DD`, drei Ausgänge für die Geschwindigkeit und sechs
  Slot-Stärken) und, bei jedem Aufruf der Modulations-Engine, was sie je Ziel aufsummiert (elf Wörter bei `0xC069FEC8`);
- am **Display** (Prüfsumme des Bildspeichers nach der Wahl der Art und nach dem Stellen der Regler);
- an dem, was der **ARM dem DSP über das Postfach** schickt (die Pakete an `0xFF900A34`, je Befehl und Wort
  verglichen, siehe [dsp-erster-blick.md](../hintergrund/dsp-erster-blick.md), Abschnitt 2).

**Offsets** sind die der [Gerätekarte](../geraetekarte.md) (`table.modType`, Fenster ab Dateioffset `0x1A00FC`). Das Fenster
eines Eintrags beginnt vier Byte vor dem Datensatz, den die Firmware liest: der Datensatz beginnt beim Namen (RAM
`0xC01A0000` für Art 0, Abstand `0x58`), sein Offset ist der Kartenoffset minus 4. Die Bytes `+0x00` bis `+0x03` des
Fensters gehören darum nicht zur Art: es sind die letzten vier Byte des Datensatzes davor (bei Art 0 die Struktur davor,
`ff ff ff ff`). Das Ende des Datensatzes von Art 71 liegt bei `0xC01A18C0`, dahinter beginnt die Namenstabelle der
Oszillatoren (`layout.record_start`, `layout.record_end`).

## Ergebnis in einem Satz je Frage

| Frage | Antwort | Marker |
|---|---|---|
| Was liest die Firmware von einem Eintrag? | den Namen, die Vorgaben, die Kurve, zwei Merker für den LFO, zwei Paare für die Geschwindigkeit, einen Merker für die Hüllkurve und je Slot Quelle, Ziel, zwei Stärken und einen Merker; 30 Byte nie | gemessen (Emulator) |
| Was ist das Byte "Ziel" (`+0x19`)? | Korgs Index der Zielliste (Muster 3, 1, 2, 4, 0, 5): ein Etikett, die Firmware liest es nie; die Ziele stehen im Slot | gemessen (Emulator) |
| Wo steht, was eine Art moduliert? | in sechs Slots zu je 8 Byte ab `+0x2C`; jede Art füllt Slot 0, vier Pitch-Arten auch Slot 1 | gemessen (Emulator) |
| Welche Ziele gibt es? | Codes 1 Pitch, 2 OSC, 3 Filter, 8 Level, 9 Pan, 10 IFX; 4 bis 7 wirken auch, 0 und ab 11 nichts | gemessen (Emulator) |
| Wie stark? | von und bis (je -63 bis 63) zwischen MOD. DEPTH 0 und 127 in 256 Stufen; ein Merker hängt die Stärke an die Vorgabetiefe der Art statt an MOD. DEPTH | gemessen (Emulator) |
| Was ist die Kurve? | die Wellenform der LFO-Einheit: 0 Sägezahn fallend, 1 Rechteck, 2 Dreieck, 3 Sample and Hold, 4 Zufall, 5 einpoliges Rechteck, 6 Sinus; ab 8 ein Index hinter eine Tabelle | gemessen (Emulator) |
| Wie läuft MOD. SPEED? | zwischen den Paaren `+0x20`, `+0x21` (LFO) und `+0x28`, `+0x29` (Hüllkurve); `+0x1E` und `+0x24` machen daraus einen Notenschritt des Tempos | gemessen (Emulator) |
| Was ist `+0x1D`? | Phase-Reset: mit gesetztem Merker springt die LFO-Phase bei manchen Anschlägen auf 0 | gemessen (Emulator), Bedingung offen |
| Was bleibt? | 30 Byte je Eintrag, die nichts liest, und die Zwischenwerte `+0x1F`, `+0x25` und je Slot `+2` (nachgerechnet, nie gelesen) | gemessen (Emulator) |
| Was kommt am DSP an? | nicht die Tabelle: die Engine rechnet im ARM, am DSP kommen ihre Ergebnisse als Wörter in den Paketen für Pitch, OSC, Filter, Level und Pan an | gemessen (Emulator) |
| Was ließe sich als Nächstes bearbeiten? | Wellenform, die Slots (Ziel, Stärke, Tiefe folgt), die Geschwindigkeitsbereiche, Phase-Reset; Tempo-Sync nur zusammen mit dem passenden Bereich | Abschnitt 11 |

## 1. Der Eintrag Byte für Byte

Offsets der Karte. "Gelesen" heißt: ein Lesehaken auf den 72 Datensätzen sah einen Zugriff (Abschnitt 7).

| Offset | Feld | Was es tut | Marker |
|---|---|---|---|
| `+0x00` bis `+0x03` | gehört nicht zur Art | Ende des Datensatzes davor (Slot 5, Abschnitt 3); bei Art 0 `ff ff ff ff` | gemessen (Emulator) |
| `+0x04` bis `+0x13` | Name | als Zeichenkette bis zum ersten Nullbyte gelesen und kopiert; 16 Zeichen gehen, der Abschluss ist dann `+0x14` | gemessen (Emulator) |
| `+0x14` bis `+0x18` | frei | in allen 72 Arten 0, nie gelesen | gemessen (Emulator) |
| `+0x19` | Ziel (Stufe 1) | Etikett, nie gelesen | gemessen (Emulator) |
| `+0x1A` | Vorgabetiefe | beim Einschalten in den Speicher je Part und Art (Stufe 1); außerdem live die feste Tiefe für Slots mit Merker 0 | gemessen (Emulator) |
| `+0x1B` | Vorgabe-Speed | beim Einschalten in den Speicher je Part und Art (Stufe 1) | gemessen (Emulator) |
| `+0x1C` | Kurve | Wellenform der LFO-Einheit | gemessen (Emulator) |
| `+0x1D` | Phase-Reset | LFO-Phase auf 0 bei Anschlägen | gemessen (Emulator) |
| `+0x1E` | LFO-Speed als Notenwert | MOD. SPEED wird ein Notenschritt (Ausgang 1) statt einer Rate (Ausgang 0) | gemessen (Emulator) |
| `+0x1F` | Zwischenwert | die LFO-Speed bei der Vorgabe-Speed, in allen 72 Arten nachgerechnet, nie gelesen | gemessen (Emulator) |
| `+0x20`, `+0x21` | LFO-Speed von und bis | Wert bei MOD. SPEED 0 und 127 | gemessen (Emulator) |
| `+0x22`, `+0x23` | frei | in allen 72 Arten 0, nie gelesen | gemessen (Emulator) |
| `+0x24` | EG-Zeit als Notenwert | Ausgang 2 ist ein Notenschritt des Tempos statt eines Rate-Index | gemessen (Emulator) |
| `+0x25` | Zwischenwert | die EG-Zeit bei der Vorgabe-Speed, in allen 72 Arten nachgerechnet, nie gelesen | gemessen (Emulator) |
| `+0x26`, `+0x27` | frei | in allen 72 Arten 0, nie gelesen | gemessen (Emulator) |
| `+0x28`, `+0x29` | EG-Zeit von und bis | Wert bei MOD. SPEED 0 und 127 | gemessen (Emulator) |
| `+0x2A`, `+0x2B` | frei | in allen 72 Arten 0, nie gelesen | gemessen (Emulator) |
| `+0x2C + 8k` | Slot k, Quelle | 0 Hüllkurve, 1 LFO-Einheit, sonst aus | gemessen (Emulator) |
| `+0x2D + 8k` | Slot k, Ziel | Zielcode | gemessen (Emulator) |
| `+0x2E + 8k` | Slot k, Zwischenwert | Stärke bei der Vorgabetiefe, nie gelesen | gemessen (Emulator) |
| `+0x2F + 8k` | Slot k, Stärke von | signed, bei MOD. DEPTH 0 | gemessen (Emulator) |
| `+0x30 + 8k` | Slot k, Stärke bis | signed, bei MOD. DEPTH 127 | gemessen (Emulator) |
| `+0x31 + 8k` | Slot k, Tiefe folgt MOD. DEPTH | ungleich 0: ja; 0: die Vorgabetiefe `+0x1A` | gemessen (Emulator) |
| `+0x32 + 8k`, `+0x33 + 8k` | Slot k, frei | in allen 72 Arten 0, nie gelesen | gemessen (Emulator) |

k läuft von 0 bis 5. Der sechste Slot (k = 5) liegt in den letzten vier Bytes des Fensters (`+0x54` bis `+0x57`: Quelle,
Ziel, Zwischenwert, Stärke von) und den ersten vier Bytes des nächsten Fensters (Stärke bis, Merker, zwei freie); bei Art
71 sind das die vier Byte hinter dem letzten Fenster, noch im Datensatz.

## 2. Wie die Firmware rechnet

**Der Zugriff (offline).** Alles, was die Firmware vom Eintrag liest, geht durch eine Funktion, `0xC0098D10`: Art hinein,
Adresse des Datensatzes heraus (`0xC01A0000 + 0x58 * Art`). Ihre 20 Aufrufstellen liegen alle in `0xC0098E48` bis
`0xC0099430` (Schreiben der Vorgaben, Lesen der Felder, Rechnen), eine davon holt den Namen für die Anzeige. Daraus
folgt die Liste der gelesenen Bytes in Abschnitt 7.

**Der Speicher je Part (gemessen (Emulator)).** Neun Byte je Part ab `0xC06924DD + 9 * Part`: Ausgang 0 (freie LFO-Rate),
Ausgang 1 (Notenschritt des LFO), Ausgang 2 (EG-Zeit), Stärke der Slots 0 bis 5. Die Firmware rechnet sie beim Wählen der
Art und beim Drehen von MOD. DEPTH und MOD. SPEED neu (`0xC0099088`). Die Rechnung steht im Skript nachgebaut
(`model_slots`) und gibt den Speicher für alle 72 Arten und 648 Kombinationen aus Part (1, 6, 16), Tiefe und Speed bis auf
das Byte wieder (`model.slots_all_types`):

- Von `lo` nach `hi` läuft ein Regler `x` (0 bis 127) in 256 Stufen: `lo + (((hi - lo + 1) * (2x + 1)) >> 8)`, begrenzt auf
  `lo` und `hi`; ist `lo` größer als `hi`, läuft es abwärts.
- Geschwindigkeit: Ausgang 2 ist der Wert zwischen `+0x28` und `+0x29` beim eingestellten MOD. SPEED. Für den LFO gilt
  das Paar `+0x20`, `+0x21`; ist `+0x1E` 0, ist das Ergebnis Ausgang 0 (Ausgang 1 gleich `ff`), sonst Ausgang 1.
- Die Stärke eines Slots aus `lo` (`+0x2F`) und `hi` (`+0x30`): ist `hi` über 0 und `lo` ab 0, zwischen `lo` und `hi`; ist
  `lo` unter 0 und `hi` über 0, immer zwischen 0 und 63; ist `hi` höchstens 0, gespiegelt (von `-hi` bis `-lo`) und negativ.
  Stellgröße ist MOD. DEPTH, außer der Merker `+0x31` ist 0: dann die Vorgabetiefe `+0x1A`. Die Engine kürzt auf -63 bis 63.

**Die Engine (offline, gemessen (Emulator) bestätigt).** Die Firmware ruft sie nur auf, solange der Part klingt (im Leerlauf
0 Aufrufe in 0,5 s, bei gespielter Note rund 1800, `slots.engine_needs_a_voice`). Je Aufruf gilt für jeden der sechs
Slots: ist die Stärke 0, geschieht nichts. Sonst die Quelle: 0 ist die Hüllkurve (Einheit 2, Pegel durch 2), 1 der Ausgang
der LFO-Einheit (mit Vorzeichen, durch 2, also höchstens 16384), jeder andere Wert lässt den Slot aus. Quelle mal
Stärke, je Ziel anders skaliert, wird auf das Wort des Ziels addiert (elf Wörter, Index gleich Zielcode). Danach ruft die
Engine für jedes Wort eine Setzfunktion, die es ins Objekt des Parts schreibt (Pitch `+0x94`, Filter `+0xA0`, ...).

**Skalierung je Ziel (gemessen (Emulator), Stärke 50, LFO-Spitze 16384).**

| Ziel | Code | Spitze | Rechnung |
|---|---|---|---|
| Pitch | 1 | 3481 | eine Tabelle je Stärke, nicht linear: Stärke 5 gibt 12, 12 gibt 153, 16 gibt 409, 17 gibt 512, 18 gibt 665, 50 gibt 3481, 63 gibt 6144 |
| Filter | 3 | 20000 | quadratisch, `2 * (Quelle * Stärke * Stärke >> 12)`; bei Stärke 63 31752 |
| alle anderen | 2, 4 bis 10 | 12800 | linear, `Quelle * Stärke >> 6` |

## 3. Die Slots

Gemessen an Art 25 (LFOTri Pitch, Slot 0 auf Pitch) bei MOD. DEPTH 100.

| Messung | Ergebnis | Prüfung |
|---|---|---|
| Quelle 1 (LFO) | Pitch-Spitze 3481 in rund 1800 Aufrufen | `slots.kind1_is_lfo` |
| Quelle 0 (Hüllkurve) | auf einer LFO-Art ein einziger Wert in 1828 Aufrufen, sonst nichts | `slots.kind0_is_envelope` |
| Quelle 2, 3, 255 | nichts | `slots.kind_other_is_off` |
| von und bis (-63, 0), (10, 20), (0, 20), (5, 5), (20, 10), (-20, -5), (0, 127) | Stärke im RAM -50, 18, 16, 5, 12, -17 und 100, jedes wie die Rechnung; Pitch-Spitzen 3481, 665, 409, 12, 153, 512 und 6144 (die Engine kürzt 100 auf 63) | `slots.range_model` |
| von -10 oder -128 mit bis 20 oder 127 | wie 0 bis 63: der untere Wert zählt nicht, solange `hi` über 0 ist | `slots.range_negative_lo_ignored` |
| Merker `+0x31` 0 | Stärke 15 (Vorgabetiefe 31) statt 50; 2 verhält sich wie 1 | `slots.follow_fixed` |
| `+0x2E`, `+0x32`, `+0x33` des Slots geändert | Engine, Zustand, Display und DSP-Wörter unverändert | `slots.spare_no_effect` |
| zweiter Slot auf Filter (Quelle 1, bis 63, Merker 1) | Filter-Wort 20000, Pitch unverändert | `slots.second_slot` |
| zweiter Slot auf Pitch | Pitch-Spitze verdoppelt (6962 = 2 mal 3481): zwei Slots auf dasselbe Ziel addieren sich | `slots.second_slot_adds` |
| sechster Slot auf Level | ohne Stärke bis und Merker im nächsten Fenster nichts, mit beiden dort Level-Spitze 12800 | `slots.sixth_needs_next_entry` |
| Art 1 (EG+ Pitch) mit Quelle 1 | folgt der LFO-Einheit statt der Hüllkurve: Spitze 12286 auf 6143 | `slots.eg_source` |

Die Ziele (Slot 0 auf Art 25, Codes 0 bis 12 sowie 100 und 255, `targets.*`):

| Code | Wort der Engine | Was am DSP als Wort ankommt, das sich mit der Modulation ständig ändert |
|---|---|---|
| 0 | keins | nichts |
| 1 Pitch | 1 | Paket `0x2B`, Wort 3 |
| 2 OSC | 2 | Paket `0x2D`, Wort 3, und Paket `0x2C`, Wort 8 |
| 3 Filter | 3 | Paket `0x30`, Worte 4 und 5 |
| 4 | 4 | Paket `0x30`, Worte 6 bis 8 |
| 5 | 5 | Paket `0x30`, Worte 4, 5 und 13 |
| 6, 7 | 6, 7 | keins, nur einzelne Schreibwerte |
| 8 Level | 8 | Paket `0x00`, Wort 4 |
| 9 Pan | 9 | Paket `0x02`, Worte 4 und 5 (dazu viele Pakete mehr) |
| 10 IFX | 10 | keins, nur einzelne Schreibwerte |
| 11, 12, 100, 255 | keins | nichts: Engine, Zustand, Display und DSP-Wörter wie bei Code 0 (`targets.high_codes`) |

Wort 0 eines Pakets ist der Kopf (`0x106`), Wort 1 die Befehlsnummer. Was die Codes 4 bis 7 am Klang ändern, ist **offen**:
keine Art nutzt sie, ihre Setzfunktionen schreiben in andere Felder des Part-Objekts (`+0xA4`, `+0xA8`, `+0xAA`, `+0xAC`,
offline gelesen). Ein Code ab 11 ändert in den Läufen nichts; der Code liest dabei aber ein Wort hinter den elf Summen und
schreibt es zurück (offline gelesen), darum gehört in einen Editor nur 0 bis 10.

## 4. Die Wellenform (Kurve, `+0x1C`)

Art 25 bei gleichem MOD. SPEED. Der Mittelwert der LFO-Einheit je sechzehntel Phase, in Tausend (`curve.*`):

| Kurve | Gestalt | Gemessen |
|---|---|---|
| 0 | Sägezahn fallend | von +30 auf -31, 1253 verschiedene Werte |
| 1 | Rechteck | +32,8 und -32,8, 2 Werte |
| 2 | Dreieck | von +4 bis +29 und, durch 0, auf -29, 976 Werte |
| 3 | Sample and Hold | 13 verschiedene Werte, die je einen Durchlauf halten |
| 4 | Zufall | 1145 Werte |
| 5 | Rechteck einpolig | +32,8 und 0 |
| 6 | Sinus | wie das Dreieck, runder: +6,5, +18, +27, +32 |
| 7 | wie 4 | |
| 8, 9, 15, 16 | wie 0 | |
| 255 | wie 3 | |

Die Firmware liest erst einen Byte-Index von acht Einträgen (Kurve gleich Index, `0xC00E8570`), dann eine Funktion aus
einer Tabelle von acht (`0xC00E8578`). Kurven ab 8 laufen hinter die Index-Tabelle in andere Daten; die Ergebnisse stehen
oben und gelten für dieses Abbild (`curve.above_seven`). Die 72 Arten nutzen 0 bis 4: Sägezahn (13 Arten, auch EG- Filter),
Rechteck (12), Dreieck (35), Sample and Hold (6), Zufall (6).

**Hüllkurven-Arten:** ihre LFO-Einheit läuft mit Rate 0 und steht still. Die Kurve legt nur den Wert fest, an dem sie steht
(Kurve 1 und 5: 32767, 3, 4 und 7: 0, 2: bis 2746, 6: bis 4300), der Klang der Art kommt aus der Hüllkurve
(`curve.eg_is_dc`). Die Kurve wirkt dort erst, wenn ein Slot die Quelle 1 hat.

## 5. Die Geschwindigkeit

**LFO, freie Rate (`+0x1E` gleich 0).** Ausgang 0 ist ein Rate-Index von 0 bis 127. Dauer eines Durchlaufs beim Paar (n, n)
(`speed.free.*`): n = 0 steht, 16 gibt 5882 ms, 32 gibt 1205 ms, 64 gibt 211 ms, 96 gibt 67 ms, 127 gibt 10 ms. Das Paar
bestimmt die Spanne, die MOD. SPEED überstreicht: mit (0, 64) liefert MOD. SPEED 127 den Index 64, mit (127, 0) dreht sich
der Regler um (127 gibt 0) (`speed.free_range`).

**LFO, Notenwert (`+0x1E` gleich 1).** Ausgang 1 ist ein Notenschritt von 1 bis 16 (`speed.sync.*`). Dauer eines Durchlaufs
in Schlägen bei 160 BPM:

| Schritt | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Schläge | 16 | 8 | 4 | 3 | 2 | 1,5 | 1,33 | 1 | 0,75 | 0,67 | 0,5 | 0,33 | 0,25 | 0,17 | 0,125 | 0,06 |

Schritt 8 bleibt bei 90, 160 und 240 BPM ein Schlag (665, 375 und 250 ms, `speed.sync_follows_tempo`). Ein Schritt über 16
(17, 20, 127) läuft wie 16 (23 ms, `speed.sync_over_16`). Setzt man `+0x1E` auf einer freien Art, mit dem Paar (8, 8), läuft
sie im Schritt 8 (375 ms statt 11111 ms); löscht man es auf einer synchronen Art mit dem Paar (8, 8), ist 8 ein Rate-Index
(11111 ms) (`flags.tempo_sync`). Der Merker ohne passendes Paar gibt also ein viel zu langsames oder schnelles Ergebnis.

**Hüllkurve (`+0x28`, `+0x29`, `+0x24`).** Ausgang 2 kommt aus dem Paar bei MOD. SPEED. Die Zeit, bis die Hüllkurve auf die
Hälfte gefallen ist (`speed.eg.*`): bei MOD. SPEED 20 27 ms, bei 50 137 ms, bei 100 638 ms, bei 127 über zwei Sekunden; mit
dem Paar (0, 64) bei MOD. SPEED 127 224 ms, mit (127, 0) 2 ms, mit (100, 100) wie MOD. SPEED 100. Mit `+0x24` gleich 1 ist
Ausgang 2 ein Notenschritt des Tempos (1 bis 16, größere Werte gelten als 16, `speed.eg_bpm_clamp`): Schritt 10 gibt 37 ms
bei 160 BPM (65 ms bei 90, 25 ms bei 240, `speed.eg_bpm_tempo`) und als Rate-Index ohne den Merker 13 ms. Art 1 mit gesetztem
Merker und Art 7 (EG+ BPM Pitch) verhalten sich bei gleichem Schritt gleich (`speed.eg_bpm_flag`).

## 6. Phase-Reset (`+0x1D`)

Acht Anschläge hintereinander (0,4 s gehalten, 0,3 s Pause, `flags.sync.*`), die Phase beim ersten Aufruf der Engine nach
jedem Anschlag, oberste zwölf Bit:

| Art, `+0x1D` | Phase nach den Anschlägen 1 bis 8 | Rücksetzungen in 2 bis 8 |
|---|---|---|
| 25 (frei LFO), 1 | 0, 1689, 1689, 0, 0, 0, 0, 0 | 5 von 7 |
| 25, 0 | 0, 1689, 3379, 972, 2662, 255, 1945, 3635 | 0 von 7 |
| 30 (LFO mit Tempo), 1 | 0, 2031, 2030, 0, 0, 0, 0, 0 | 5 von 7 |
| 30, 0 | 0, 2002, 4005, 1911, 3914, 1820, 3823, 1729 | 0 von 7 |

Mit gesetztem Merker setzt die Firmware die Phase bei manchen Anschlägen auf 0, ohne ihn bei keinem. Welche, hängt vom
Zeitpunkt ab: mit 0,1, 0,2 und 0,45 s mehr Vorlauf vor den Anschlägen waren es bei Art 25 5, 5 und 5 von 7, bei Art 30 5, 5
und 7 von 7 (`flags.sync_timing`). Die Funktion dahinter
(`0xC0097624`, folgt der Anschlagbehandlung) setzt Phase und Zeitbezug des Taktes neu (offline gelesen). Warum nicht jeder
Anschlag zurücksetzt, ist **offen**.

## 7. Was nichts liest

Ein Lesehaken auf allen 72 Datensätzen sieht beim Wählen jeder Art, beim Drehen von MOD. DEPTH und MOD. SPEED, bei einem
Pad-Anschlag je Art und beim Abspielen, was die Firmware liest, und einer vom Einschalten an, was sie beim Start liest
(`reads.*`). Gelesen wird nur, was Abschnitt 1 beschreibt (`reads.only_documented`, `reads.always`); beim Start zusätzlich
`+0x1A` und `+0x1B` (`reads.boot_defaults`). Quelle und Ziel eines Slots liest die Firmware nur, wenn seine Stärke nicht 0
ist, darum fehlen sie im Lauf für die Slots 2 bis 5 (und die Messung in Abschnitt 3 füllt sie).

Nie gelesen und in der Messung einzeln und gemeinsam verändert (`unread.single`, `unread.all`): `+0x14` bis `+0x18`,
`+0x19`, `+0x1F`, `+0x22`, `+0x23`, `+0x25`, `+0x26`, `+0x27`, `+0x2A`, `+0x2B`, je Slot k `+0x2E + 8k` (sechs) und
`+0x32 + 8k`, `+0x33 + 8k` (zehn, die Slots 0 bis 4), zusammen 30 Byte. Je Byte einzeln auf `0x5A`, auf einer Hüllkurven-Art (1) und
einer LFO-Art (25), und alle 30 zugleich auf `0xA5` bei Art 1, 25 und 36 ändert nichts an den Werten der Engine, am Zustand
je Part, am Display und an den Paketen zum DSP.

**Zwischenwerte.** `+0x1F` und `+0x25` sind in allen 72 Arten genau das, was die Rechnung bei der Vorgabe-Speed liefert
(`table.cache_equals_default`). Die Zwischenwerte je Slot (`+0x2E + 8k`) gleichen bei positiven Bereichen (50 von 50) der
Stärke bei der Vorgabetiefe, bei negativen (26 von 26) der Stärke bei der gespiegelten Tiefe, 127 minus Vorgabetiefe. Eine
Abweichung vom Muster gibt es: Art 14 (EG- OSC) hat in Slot 4 den Zwischenwert 5 bei einem sonst leeren Slot. Dieselben Bytes
schreiben die Funktionen, die den Datensatz "for Voicing" füllen (Abschnitt 9); dass sie in der Tabelle genau nachgerechnet
gleich sind, passt dazu (hergeleitet).

**Der Name.** Die Firmware misst die Zeichenkette und kopiert sie, beides bis zum ersten Nullbyte. Ein anderes erstes
Zeichen ändert die Anzeige bei der Wahl der Art (`unread.name_shows`), ein Byte hinter dem Nullbyte nicht
(`unread.name_after_nul`). Ein Name aus 16 Zeichen geht: der Abschluss ist dann das Byte `+0x14` (0 in allen Arten), die
Modulation erreicht dieselben Spitzen (`unread.name_sixteen`).

## 8. Muster über die 72 Arten

Zwölf Quellen mal sechs Ziele. Hüllkurven: EG+ (0 bis 5), EG+ mit Tempo (6 bis 11), EG- (12 bis 17), EG- mit Tempo (18 bis
23). LFOs: LFOTri (24 bis 29), LFOTriB (30 bis 35), SawUpB (36 bis 41), SawDwnB (42 bis 47), SquUpB (48 bis 53), SquDwnB (54
bis 59), S&HBPM (60 bis 65), Random (66 bis 71). Das B in den Namen heißt Tempo. "Up" und "Dwn" kommen aus dem Vorzeichen der
Stärke, nicht aus der Wellenform: beide Sägezähne haben die Kurve 0, beide Rechtecke die Kurve 1 (`table.*`).

| Byte | Werte in den 72 Arten (Anzahl) |
|---|---|
| `+0x19` Ziel | 0 bis 5, je 12 |
| `+0x1C` Kurve | 0 (13), 1 (12), 2 (35), 3 (6), 4 (6) |
| `+0x1D` Phase-Reset | 0 (35), 1 (37: die 36 LFOs mit Tempo und Art 14) |
| `+0x1E` LFO-Speed als Notenwert | 0 (36), 1 (36: die LFOs mit Tempo) |
| `+0x20`, `+0x21` | (0, 0) bei den 24 Hüllkurven, (0, 127) bei den 12 freien LFOs (LFOTri, Random), (1, 16) bei den 36 mit Tempo |
| `+0x24` | 1 bei den 12 Hüllkurven mit Tempo, sonst 0 |
| `+0x28`, `+0x29` | (0, 127) bei den 12 Hüllkurven ohne Tempo, (16, 1) bei den 12 mit Tempo, (0, 0) bei den 48 LFOs |
| Slot 0, Quelle | 0 bei den 24 Hüllkurven, 1 bei den 48 LFOs |
| Slot 0, Ziel | 1, 2, 3, 8, 9, 10, je 12 mal |
| Slot 0, von und bis | (0, 63) bei 48 Arten, (-63, 0) bei 24 (EG-, SawUpB, SquUpB) |
| Slot 0, Merker `+0x31` | 1 in allen 72 |
| Slot 1 | in vier Arten gefüllt, den Pitch-Arten 1, 7, 13 und 19, als zweiter Pitch-Slot mit derselben Spanne |
| Slots 2 bis 5 | in allen 72 Arten leer (Stärke 0, Merker 0) |

Zwei Besonderheiten: Art 14 (EG- OSC) hat als einzige Hüllkurve den Phase-Reset 1 und den Zwischenwert in Slot 4; und die
vier Pitch-Arten mit zwei Slots haben die doppelte Pitch-Tiefe der übrigen.

## 9. Der Eintrag "for Voicing"

Außerhalb der Tabelle liegt ein Datensatz mit dem Namen "for Voicing" (`0xC00F9D90`), den die Firmware statt der Tabelle
benutzt, sobald ein Merkerbyte (`0xC06924DC`) nicht 0 ist. Mit dem Merker liefert der Zugriff für jede Art diesen Datensatz
(`scratch.accessor`), auf Art 25 ändert das den Speicher je Part (`scratch.changes_slots`). Den Merker setzen nur die
Funktionen, die den Datensatz füllen: sie schreiben seine Felder einzeln (Kurve, beide Merker, die Zwischenwerte, das Paar der
EG-Zeit, die Slots) und hängen an einem Befehl eines Host-Dispatchers (`0xC002CDF0`, aus `0xC002650C`; offline gelesen, nicht
ausgeführt); in allen Läufen blieb der Merker 0. Dass diese Funktionen die Zwischenwerte schreiben, stützt, was Abschnitt 7
über sie sagt (hergeleitet). Ob die Hacktribe-Firmware oder der Editor diesen Weg je geht, ist **offen**.

## 10. Kopien

(`copy.*`) Drei Änderungen (Kurve 6 an Art 25, EG-Zeit (0, 64) an Art 1, Slot-Ziel Filter an Art 25) wurden einmal live im RAM
der Tabelle gemacht, die die Firmware liest, und einmal in einer Kopie der `SYSTEM.VSB`, die gebootet wurde. Die Werte der
Engine, der Speicher je Part und die Pakete zum DSP sind gleich und unterscheiden sich vom unveränderten Abbild. Dieselben
Änderungen in Korgs Kopie (Dateioffset `0xD82EC`) ändern nichts. Die Seite Modulationen schreibt also in die richtige Kopie.
Was die Firmware erst beim Einschalten liest (die Vorgaben), wirkt nach einem Neustart mit der neuen Datei; alles andere liest
sie bei jedem Aufruf.

## 11. Vorschlag: was sich als Nächstes bearbeiten ließe

Nur Felder mit klarer, harmloser Wirkung. Die Oberfläche ist hier nicht gebaut. Jedes Feld schreibt wie in Stufe 1 in die Kopie
der Tabelle, die die Firmware liest, und geht durch die Prüfung im Emulator.

| Reihenfolge | Feld | Form in der Oberfläche | Grenzen |
|---|---|---|---|
| 1 | Kurve `+0x1C` (Stufe 1 hat sie schon) | Auswahl der sieben Wellenformen statt 0 bis 255 | 0 bis 6; 7 ist doppelt, ab 8 liest die Firmware hinter eine Tabelle. Wirkt nur bei Slots mit Quelle LFO |
| 2 | Slots 0 bis 4: Ziel, Stärke von und bis, Tiefe folgt | je Slot eine Zeile: Ziel (Aus, Pitch, OSC, Filter, Level, Pan, IFX), Stärke als zwei Zahlen, ein Schalter | Ziele 0, 1, 2, 3, 8, 9, 10; Stärke -63 bis 63, positiv als "von kleiner als bis", negativ gespiegelt; die Quelle nicht einzeln, sie gehört zur Art (Hüllkurve oder LFO). So bekommt eine Art mehrere Ziele, etwa Pitch und Filter zugleich |
| 3 | Geschwindigkeit `+0x20`, `+0x21`, `+0x28`, `+0x29` | zwei Zahlen "MOD. SPEED läuft von ... bis ..." je Art | 0 bis 127 bei freier Rate, 1 bis 16 bei Notenschritten; "von größer als bis" dreht den Regler um |
| 4 | Phase-Reset `+0x1D` | ein Schalter | 0 oder 1 |
| 5 | Tempo-Sync `+0x1E`, `+0x24` | nur als Umschalter "frei oder Tempo", der das Paar mitsetzt (0 bis 127 oder 1 bis 16) | ein Merker allein ohne das Paar macht den LFO oder die Hüllkurve viel zu langsam oder schnell |

Nicht vorschlagen: die 30 unbenutzten Bytes und die Zwischenwerte (nichts liest sie), die Zielcodes 4 bis 7 (Wirkung am Klang
offen), den sechsten Slot (er liegt halb im nächsten Fenster), das Byte "Ziel" `+0x19` (nur ein Etikett; die Seite sagt es
schon). Das Feld "Ziel" der Seite ließe sich durch die Slot-Ziele ersetzen. Die Hinweise der Seite zu Ziel und Kurve nennen
noch den Stand von Stufe 1. Namen mit 16 Zeichen gehen, "bis zu 16 Zeichen" auf der Seite stimmt.

## 12. Berichtigungen zu Stufe 1 und was offen bleibt

Berichtigt gegenüber [Stufe 1](2026-10-14-offene-fragen.md), Abschnitt 9.4:

- `+0x24` ("BPM") ist nicht bei allen Arten mit Tempo 1, sondern nur bei den zwölf Hüllkurven mit Tempo. Die 36 LFOs mit
  Tempo laufen über `+0x1E` (ihr `+0x24` ist 0).
- Der sechste Slot ist nicht abgeschnitten: seine Bytes hinter dem Fenster sind die letzten vier Byte desselben
  Datensatzes (das Fenster der Karte liegt vier Byte vor dem Datensatz) und wirken, wenn sie gesetzt sind.
- Was in Stufe 1 offen blieb: `+0x1D` ist der Phase-Reset, `+0x2C` die Quelle des Slots (0 Hüllkurve, 1 LFO), `+0x2E` ein nie
  gelesener Zwischenwert (wie `+0x1F` und `+0x25`).
- Die Kurve ist eine Wellenform mit den sinnvollen Werten 0 bis 6; der Bereich 0 bis 255 der Karte ist zu weit.

Offen:

- Warum der Phase-Reset nicht bei jedem Anschlag eintritt (Abschnitt 6).
- Was die Zielcodes 4 bis 7 am Klang tun und was die Pakete zu IFX (10) und zu den Codes 6 und 7 am DSP ändern.
- Wie sich die Werte am Gerät anhören: alles hier ist im Emulator an Engine-Werten und Wörtern zum DSP gemessen, nicht gehört.
- Ob der Host-Befehl, der "for Voicing" füllt, am Gerät je ankommt (Abschnitt 9).
- Ob eine andere Firmware-Version dieselben Werte hat: gemessen ist nur 2.02 mit Hacktribe.

## Skript

`tools/emu/modtable_probe.py` hat eine Prüfung je Aussage dieser Datei (Namen in Klammern). Die Abschnitte `layout`, `reads`,
`table`, `model`, `slots`, `targets`, `curve`, `speed`, `flags`, `unread`, `scratch` und `copy` laufen einzeln (`--only`),
`--json` schreibt die Zahlen dahinter. Die Läufe nutzen vier Prozesse (`GELUMPE_JOBS`), jeder startet die Firmware aus einem
Schnappschuss des Boots. Die Prüfungen verändern die Tabelle im RAM des Emulators oder eine Kopie der Datei, nie die Datei selbst.

## Was im Repository neu ist

- Dieses Dokument.
- `tools/emu/modtable_probe.py`.
- `data/map/firmware.mjs`: die Felder ab `+0x14` einzeln statt des Blocks `modType.unknown`, Evidenz
  `measure:2026-10-15/modulation-stufe2`; sie haben keinen Transportweg, die bearbeitbaren sind im Expertenmodus. Notizen an
  `modType.target` und `modType.curve`.
- `data/findings.mjs`: die Befunde dieser Datei.
- `test/modtable.test.mjs`: jedes Byte ab `+0x14` hat ein Feld.
