# Hacktribes Extra-Effekte, Grooves und Touch-Skalen auf der roten 2.02 (10.11.)

Stand 10.11.2026, Emulator und Bytevergleich mit Korgs Original 2.02 (rot), Hacktribe 2.02 und Korgs blauer 2.02.
Frage: lassen sich Hacktribes zusätzliche Insert-Effekte, Master-Effekte, Grooves und Touch-Skalen auf die rote
Firmware bringen wie `ht-osc` die Oszillatoren, also als Tabelleneinträge auf Korgs eigenem Code, ohne neuen DSP-Code?
Reine Untersuchung, kein Patch gebaut. Am Gerät nicht geprüft.

Marker: **gemessen** (im Emulator ausgeführt oder in den Dateien verglichen), **hergeleitet** (aus Code oder Messung
geschlossen), **offen**. Adressen sind RAM-Adressen (Datei minus 0x100 plus `0xC0000000`).

Firmware: `hacktribe-2.02.VSB` (sha256 `7cb4825c...`), `korg-red-2.02.VSB` (`1d0f0689...`), `korg-blue-2.02.VSB`
(`41fc5f1c...`), aus `BLECH-CI-Firmware`.

## Ergebnis

| Teil | Hacktribe fügt hinzu | Urteil rot |
|---|---|---|
| Insert-Effekte | 11 Presets (39 bis 49) | **als Datenpatch machbar**, über `preset-tables` und `fx-append`, DSP-Strom im Emulator gleich wie Hacktribe |
| Master-Effekte | keine neuen Plätze, 4 Werksplätze ersetzt | **als Datenpatch machbar**, die 4 als zusätzliche Plätze 33 bis 36 |
| Grooves | 37 neue (25 auf 62) | **braucht etwas ARM-Code** (Kopierhaken beim Start) oder Korg-Daten im Repo; kein DSP-Code |
| Touch-Skalen | 35 neue (35 auf 70) | **als Datenpatch machbar**, mit zwei offenen Entscheidungen (Snap-Tabelle, RAM-Objekt je Skala) |
| Akkord-Sets (Nebenfund) | 2 neue (4 auf 6) | offen, nicht untersucht |

Lizenz: Hacktribes Tabellen dürfen nicht kopiert werden (siehe unten). Jeder Port braucht eigene Daten aus einer
Feldtabelle wie bei `ht-osc`, nicht Hacktribes Bytes.

## Belegtabelle

| Behauptung | Marker | Beleg |
|---|---|---|
| Unterhalb `0xC00A0000` unterscheiden sich Hacktribe und rot an 69 Stellen; alle Zählstellen der vier Teile liegen darunter | gemessen | Wortvergleich der beiden VSB (`diff.py`) |
| Übrige Hacktribe-Änderungen springen in Hacktribes eigenen ARM-Code ab `0xC0170000` (Filter, SysEx u.a.), Aufrufer `0xC0026450`, `0xC00265B0`, `0xC0026B00`, `0xC002B098`, `0xC002B294`, `0xC005F144`, `0xC006EAD4`, `0xC00702C0`, `0xC008374C`; für Grooves und Skalen nicht nötig | gemessen (Sprünge), hergeleitet (nicht nötig) | Disassembly der Diff-Stellen |
| DSP-Strom `0xC00F9E10` bis `0xC013C0B0` ist in rot und Hacktribe gleich | gemessen | [FX-Tabellen](2026-10-14-fx-tabellen.md), hier wiederholt |
| Insert: Menü 38 rot, 49 Hacktribe; Stellen `0xC003EFDC`, `0xC0048F80`, `0xC0049EF0`, `0xC004A1F8`, Knopfspeicher-Zeile `0xC0098084` und Geschwister | gemessen | Bytevergleich |
| Master: Menü `0xC003EFE4` ist in beiden `mov r0,#0x20` (32) | gemessen | Bytevergleich |
| 11 neue Inserts: Lag, KP2 Comp, LP Drive, LP Drive Res, HP Drive, HP Res Drive, BP Drive, BP Drive Res, 9/32 Delay, 3/32 Delay, 1/12 Delay | gemessen | Getter `0xC003E738` auf Hacktribe, Namen bei Record +1 |
| Hacktribe ersetzt Master 10 Slicer durch Big Hall, 11 Jag Filter durch Plate Reverb, 21 Touch Wah durch Tap Delay Sync, 32 Auto Pan durch Tube Drive | gemessen | Getter `0xC003E750`, rot gegen Hacktribe |
| Bausteine `I_mkp2_comp`, `M_hall_reverb`, `M_wet_plate_reverb` nutzt kein rotes Werkspreset, sie liegen aber in Korgs DSP-Strom | gemessen | Stufenbytes 298/372/446 aller Records gegen die Bausteinliste |
| Die 11 Inserts auf roten Plätzen 39 bis 49 und die 4 Master auf 33 bis 36: Menüs 49 und 36, Namen richtig, Drehen läuft rund, keine Asserts; Transfers je Insert 14, je Master 11; `same_dsp` für alle 15 wahr gegen Hacktribe | gemessen | `tools/emu/blue_fx_probe.measure` auf rot mit den 15 Records |
| Groove-Setter `0xC0049DA4`: `cmp r2,#0x18` rot, `#0x3d` Hacktribe; über der Grenze setzt er 0 | gemessen | Disassembly |
| Groove-Menü läuft bei `0xC007BB88`/`90`/`94` um bei 25 rot, 62 Hacktribe | gemessen | Bytevergleich |
| Rot baut 25 GVST-Vorlagen zu 0x140 Byte im RAM ab `0xC068A03C` mit Inline-`strb`-Code (um `0xC0052200` bis `0xC0052440`, Literal `0xC0052338`); im Image stehen diese Bytes nicht als Tabelle | gemessen | Disassembly, RAM nach dem Start |
| Hacktribe hat eine Image-Tabelle mit 62 Einträgen bei `0xC0143B00` (Datei `0x143C00`) und lenkt 4 Literale dorthin: `0xC0047A28`, `0xC0047A88`, `0xC0047AE8` (Leser Offset/Velocity/Gate +0x30/31/32, Länge +0x22) und `0xC0080AF8` (Namen) | gemessen | Bytevergleich, `data/map/firmware.mjs` `table.groove` |
| Hacktribe-Einträge 0 bis 24 sind Byte für Byte Korgs RAM-Tabelle; Hacktribes eigene RAM-Tabelle ist ebenfalls gleich | gemessen | Vergleich im Emulator |
| 37 neue Grooves: Forward, Backward, Swing Plus, Swing Minus, Crescendo 64, Decrescendo 64, Drift Plus 64, Drift Minus 64 und 29 Song-Grooves (Alright 64 bis Tutu 64, Door 32) | gemessen | Namen aus Hacktribes Tabelle |
| Ein Pattern mit Groove-Byte 40 behält 40 beim Anwenden; die sechs Leser `0xC00479F4` bis `0xC0047ADC` klemmen nicht und lesen auf rot Eintrag 40 = `0xC068D23C`, fremdes RAM hinter der Tabelle, ohne Assert | gemessen | Probe mit Groove 40, Tiefe 127, beim Abspielen |
| Skalen: rot 35 (0 bis 34), Hacktribe 70; Menügrenze `0xC007CF24`/`28` 0x22 gegen 0x45, Setter `0xC004860C`/`10` `cmp/movge #0x23` gegen `#0x46` | gemessen | Bytevergleich, Disassembly |
| Vier Skalentabellen werden per Literal umgelenkt (Tabelle unten) | gemessen | Bytevergleich |
| Die ersten 35 Einträge der Stufentabelle sind gleich; in der Snap-Tabelle ändert Hacktribe 126 der ersten 420 Byte (01 zu ff) | gemessen | Bytevergleich der Tabellen |
| Hacktribes 35 neue Skalen zeigen alle auf Chromatics RAM-Objekt `0xC068C520` | gemessen | Zeigerliste `0xC0140000` |
| Ein Pattern-Skalenbyte über 34 stürzt auf rot beim Anwenden bei `0xC0055BD0` ab (36 und 69 gemessen); 35, 50, 70 nicht, weil hinter der Zeigerliste zufällige Bytes stehen | gemessen | Emulator, je Wert neu gestartet |
| Akkord-Sets: Grenze `0xC007CE34`/`38` 4 rot, 6 Hacktribe; Wert im Pattern Byte 41 (+0x2d) | gemessen (Grenze), hergeleitet (Byte) | Bytevergleich, Getter |
| Rot hat im Set `blech.json` freien Platz `FF` von `0xC013C0B0` bis `0xC014F000` (0x12F50 Byte); kein Patch-`ram` liegt dort, `ht-osc` beginnt bei `0xC014F000` | gemessen | gebautes Set, `data/patch-ram.mjs` |
| Im Hacktribe-Set liegen dort Hacktribes Tabellen, ein Port wäre nur rot (`notNeededOn` hacktribe) | hergeleitet | gleiche Adressen |
| Blau: freier Platz `0xC01217F4` bis +0x2E40C; 35 Skalen, Namensliste `0xC00C3B08` (genutzt bei `0xC004B3B0`); GVST-Code bei `0xC0049134`; Groove-Grenze 24 | gemessen | Blau-Image, Disassembly |
| Wie die neuen Inserts, Master, Grooves und Skalen am Gerät klingen | offen | nur am Gerät |

## Insert- und Master-Effekte

**Was Hacktribe hinzufügt.** 11 Insert-Presets auf 39 bis 49 (Namen oben), Menü 49. Beim Master keine neuen Plätze,
Menü bleibt 32, vier Werkspresets sind ersetzt (Big Hall, Plate Reverb, Tap Delay Sync, Tube Drive). Gemessen.

**Code.** Nur Records. Die Bausteine darin (`I_mkp2_comp`, `M_hall_reverb`, `M_wet_plate_reverb` und die übrigen) sind
in Korgs DSP-Strom vorhanden, der Strom ist in rot und Hacktribe gleich. Im Emulator schickt rot mit den 15 Records an
den DSP dasselbe wie Hacktribe (`same_dsp` wahr für alle 15). Gemessen.

**Was an der Anzahl hängt.** Insert: Menülänge an 4 Stellen und die Knopfspeicher-Zeilen, die `fx-catalog` schon
anpasst. Master: Menülänge `0xC003EFE4`. Getter klemmen bei 99, `preset-tables` hebt das auf 127. Ein Pattern, das
einen Preset über dem Menü nennt, behandelt die [Preset-Tabellen-Messung](2026-10-15-preset-tabellen.md). Gemessen.

**Was schon da ist.** `preset-tables` gibt 128 Plätze je Tabelle, `fx-catalog` (`src/fx-append.mjs`) hängt schon 10
Inserts und 8 Master an. Die Hacktribe-Effekte wären weitere Einträge in derselben Liste, hinter den Katalogeinträgen.
`preset-tables-stock` deckt nur die Tabellen ab, nicht die Records. Hergeleitet.

**Blau.** Derselbe Weg wie im [Blau-Effekte-Bericht](2026-11-08-blau-eigene-effekte.md): Plätze über
`synth-map`/`fwmap`, Aufwand dort geschätzt. Offen.

**Urteil: als Datenpatch machbar.** Die Records müssen aus einer eigenen Feldtabelle kommen (Name, Bausteine,
Parameter), nicht als Block aus Hacktribe, siehe Lizenz.

## Grooves

**Was Hacktribe hinzufügt.** 37 Grooves, 62 statt 25. Gemessen.

**Code.** Die Leser sind Korgs, nur die Tabelle liegt woanders: Hacktribe lenkt 4 Literale auf eine 62er Tabelle im
Image und hebt Setter-Grenze und Menüumlauf. Rot hat aber keine Groove-Tabelle im Image: Korgs 25 Vorlagen entstehen
beim Start aus Inline-Code im RAM. Ein Datenpatch müsste die 25 Werksvorlagen als Bytes ins Image schreiben, also
Korg-Daten ins Repo legen. Das geht nicht. Zwei Wege ohne DSP-Code (hergeleitet):

1. Ein kleiner ARM-Haken nach dem Groove-Aufbau kopiert die 25 RAM-Vorlagen an den Anfang der neuen Tabelle, die 37
   neuen stehen als eigene Daten dahinter. Aufwand gering, aber neuer ARM-Code.
2. Feldtabelle wie bei `ht-osc`, aus der der Patchbauer die 62 Einträge zur Bauzeit aus der Nutzer-VSB zieht. Die 25
   Werksvorlagen sind aber nicht im Image, also geht das nur für die 37 neuen; die 25 brauchen trotzdem Weg 1.

**Was an der Anzahl hängt.** Setter-Grenze `0xC0049DA4`, Menüumlauf `0xC007BB88`/`90`/`94`, 4 Literale. Die Leser
klemmen nicht: ein Pattern mit Groove über 24 liest auf rot heute schon fremdes RAM (gemessen). Ein Pattern aus
Hacktribe mit neuem Groove spielt auf rot also Müll, ohne Absturz im Emulator.

**Was schon da ist.** Nichts. `data/map/firmware.mjs` kennt nur Hacktribes Tabelle (`table.groove`).

**Blau.** Gleiche Bauweise (GVST-Code `0xC0049134`, Grenze 24), eigene Adressen nötig. Offen.

**Urteil: braucht etwas ARM-Code.** Kein DSP-Code, aber ohne Kopierhaken kein Weg, der keine Korg-Bytes ins Repo legt.
Die 37 Vorlagen selbst sind kreative Daten Hacktribes ohne Lizenz (siehe unten).

## Touch-Skalen

**Was Hacktribe hinzufügt.** 35 Skalen, 70 statt 35: Lydian Minor, Phrygian Dominant, Major Bebop, Minor Bebop,
Dominant Bebop, Gregorian Nr.4, Lydian Diminished, Aeolyptian, Superlocrian, Aeolian Pentatonic, Kokin-joshi, Scottish
Pentatonic, Iwato, Acoustic, Raga Kamalamanohari, Neapolitan Major, Neapolitan Minor, Enigmatic, Raga Shri Kalyan,
Hungarian Romanian, Salimic, Epogimic, Espla's Scale, Spanish Octamode, Ionidyllic, Epicryllic, MEXian, Katycryllic,
Raga Sindhura Kafi, Chromatic Hypolydian, Ionogian, Gycryllic, Chromatic Phrygian, Hamel, Moptygic. Im Display auf 15
Zeichen gekürzt. Gemessen. Viele Namen stammen aus Ian Rings Skalenverzeichnis: hergeleitet.

**Code.** Nur Tabellen, Korgs Code liest sie:

| Tabelle | Rot | Hacktribe | Literal | Inhalt |
|---|---|---|---|---|
| Stufen | `0xC00DCF70` | `0xC013EC00` | `0xC005423C` | 13 Byte je Skala: Anzahl und 12 Stufen; erste 35 gleich |
| Snap | `0xC00DD148` | `0xC013F280` | `0xC0054508` | 12 vorzeichenbehaftete Byte je Skala; Hacktribe ändert 126 der ersten 420 |
| Namen | `0xC00DD330` | `0xC013E000` | `0xC00545BC` | Zeigerliste, Namen bei Hacktribe ab `0xC013E400` |
| RAM-Objekt je Skala | `0xC00DDB18` | `0xC0140000` | `0xC0055360`, `0xC005537C`, `0xC00553BC` | Zeiger nach `0xC068C4xx`; +8 klemmt die Länge, +0x314 |

Gemessen. Der Skalenindex steht im Objekt `0xC068FB7C` +0x304, im Pattern Byte 40 (`data/map/pattern.mjs`
`pattern.scale`, Bereich [0,34]).

**Was an der Anzahl hängt.** Menügrenze `0xC007CF24`/`28`, Setter `0xC004860C`/`10`, die vier Literale, und
`pattern.scale` im Repo (Editor, Prüfungen). Ein Pattern mit Skala über 34 kann rot heute schon zum Absturz bringen
(gemessen bei 36 und 69). Ein Hacktribe-Pattern mit neuer Skala ist auf rot also gefährlich, mit Port nicht mehr.

**Entscheidungen, die offen sind.**

1. Snap-Tabelle: Hacktribe ändert auch die Snap-Richtung der 35 Werksskalen. Wer Hacktribes Tabelle übernimmt, ändert
   das Spielgefühl der bestehenden Skalen. Vorschlag: Korgs 35 Einträge unverändert lassen, nur 35 neue anhängen. Offen.
2. RAM-Objekt: Hacktribe gibt allen 35 neuen Skalen Chromatics Objekt. Was dieses Objekt steuert und ob eigene Objekte
   nötig sind, ist nicht gemessen. Offen.

**Was schon da ist.** Nichts. Intervalle und Namen der Skalen sind allgemeines Musikwissen und frei als Feldtabelle
schreibbar (hergeleitet), die Snap-Werte müssten selbst bestimmt werden.

**Blau.** 35 Skalen, Namensliste `0xC00C3B08`; Stufen-, Snap- und Objekttabelle auf blau nicht gesucht. Offen.

**Urteil: als Datenpatch machbar**, im freien Gebiet `0xC013C0B0` bis `0xC014F000`, mit 4 Literalen und 2 Grenzen,
sobald die zwei Entscheidungen oben gefallen sind.

## Akkord-Sets (Nebenfund)

Hacktribe hebt die Grenze der Akkord-Sets von 4 auf 6 (`0xC007CE34`/`38`, gemessen). Wo die Tabelle liegt und was die
zwei neuen enthalten, ist nicht untersucht. Offen.

## Lizenz

Hacktribes `LICENSE` ist AGPL-3.0, das README sagt aber, dass der Inhalt des Ordners `patch` nicht Open Source ist und
nicht unter die GPL fällt. Die Tabellen kommen nur über diesen Ordner (`patch/hacktribe-2.patch`). Gemessen (Dateien
gelesen). Daraus (hergeleitet):

- Hacktribes Bytes (Records, Groove-Vorlagen, Skalentabellen) dürfen nicht ins Repo und nicht in einen Patch kopiert
  werden.
- Effekt-Records lassen sich aus eigenen Feldern neu aufbauen, wie bei `fx-catalog`. Ob die Parameterwerte eines
  Hacktribe-Presets geschützt sind, ist eine Rechtsfrage. Offen.
- Skalen-Intervalle und -Namen sind Fakten, frei schreibbar.
- Die 37 Groove-Vorlagen sind kreative Daten ohne Lizenz: nicht übernehmbar, eigene Grooves wären nötig.

Ein Weg ohne Kopie wäre wie bei `ht-osc` ein Bauschritt, der die Werte aus der Hacktribe-VSB des Nutzers liest. Der
Bauschritt in `ht_osc.py` prüft gegen die VSB, er kopiert nicht. Ob das Lesen zur Bauzeit lizenzrechtlich reicht, ist
offen.

## Wie gemessen

- Wortvergleich der drei VSB unterhalb `0xC00A0000`, Disassembly jeder Diff-Stelle mit capstone.
- Effekte: `tools/emu/blue_fx_probe.measure` auf der roten VSB mit den 15 Hacktribe-Records auf den Plätzen 39 bis 49
  und 33 bis 36, Vergleich mit Hacktribe über `same_dsp`. Die Records lagen nur im Speicher.
- Grooves: Emulator (`splash_cases.Dev`), Groove-Byte im Part über das Objekt `u32(0xC0348910)`, Pattern anwenden mit
  `0xC004A8E4(u32(0xC0691334))`, Leser beim Abspielen protokolliert.
- Skalen: Tabellen per Literal verglichen; Pattern-Skalenbyte gesetzt, Pattern angewendet, je Wert neu gestartet.
- Freier Platz: gebaute Sets `blech.json` (rot, Hacktribe) und `blech-synth.json` (blau), Lauf von `FF`.

## Offen am Gerät

- Klang der 11 Inserts und 4 Master auf rot.
- Ein Hacktribe-Pattern mit Groove über 24 und Skala über 34 auf rot ohne Port: was passiert am Gerät.
- Snap-Verhalten der neuen Skalen mit Chromatics RAM-Objekt.
