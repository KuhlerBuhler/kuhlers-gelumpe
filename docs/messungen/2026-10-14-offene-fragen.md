# Offene Fragen: was sich mit Emulator und DSP-Tabellen beantworten lässt

Stand 2026-10-14. Offline, Firmware 2.02 mit Hacktribe, eigene `SYSTEM.VSB` und eigener Flash im
ARM-Emulator (`tools/emu`), dazu der DSP-Strom mit Blackfin-Disassembler und -Simulator aus
[`../hintergrund/dsp-erster-blick.md`](../hintergrund/dsp-erster-blick.md) und die Tabellen aus
`2026-10-14-fx-tabellen.md`. Kein Gerät. Die Fragen stammen aus der Liste vom 15.09.2026, als es nur den
Preset-Editor gab.

Markierungen: **gemessen** (ausgeführt, Befehl genannt), **hergeleitet** (aus Code oder Daten geschlossen,
nicht ausgeführt), **offen**. Alle Skripte lagen im Scratchpad. Im Repository liegen nur dieses Dokument und eine
Korrektur in `data/map/firmware.mjs`. Keine Firmwarebytes, keine Namen aus dem DSP-Strom.

## Kurzfassung

| Frage | Status | Antwort in einer Zeile |
|---|---|---|
| Decimator mit zweiter Stufe | teilweise | Der ARM schickt beide Stufen gleich und prüft keine Bausteinnummer; der Absturz liegt im DSP. Ursache offen, die Regel aus Frage 2 erklärt ihn nicht. |
| Restliche Stufe-2-Liste | teilweise | 13 von 19 gemessen. Der Lader gibt Stufe 2 nie Platzspeicher; wer welchen braucht, steht in der Deskriptortabelle (`0x11`, `0x12`, `0x16`, `0x18`). Offen sind `0x0F`, `0x11` bis `0x15`. |
| Stufe 1 durchprobieren | braucht Gerät | Stufe 1 bekommt Speicher, ob alles dort läuft, hört man nur. Kurzer Versuch unten. |
| Drei Kompressoren, drei Ergebnisse | teilweise | Es sind drei getrennte Implementierungen mit verschiedenen Reglern, kein Wunder. Ob der Klang gleichwertig einstellbar ist, braucht Gehör. |
| `mfx_device 0x30`, `ifx_device 0x0B` bis `0x0E` und `0x17` | beantwortet | Im DSP leere Plätze: `0x30` ist ein zweiter Index der Mute-Einheit, die übrigen sind `NoFx(Thru)`. |
| Sieben ungenutzte MFX-Bausteine | beantwortet | Vorgaben und Spannen aller Parameter stehen in der DSP-Tabelle und stimmen mit `units.json` überein (Tabelle unten). |
| Slicer und Repeater laufen aus dem Takt | braucht Gerät | Mechanismus geklärt: `lfo_reset` ist ein Einmal-Auslöser, der nur bei einem Wertwechsel feuert. Hörversuch unten. |
| `lfo_reset` 2 und 3 | teilweise | Außerhalb der Spanne `[0, 1]`, aber nicht gesperrt: ein Phasensprung einmal, danach läuft alles weiter. Kein Dauer-Resync. Hörbare Wirkung braucht Gerät. |
| Sync-Notenwerte je Baustein | teilweise | Alle LFO-Bausteine teilen eine Tabelle mit 42 Verhältnissen (unten). Die Delays haben eigene, nicht gelesen. |
| Modulationstabelle ab `+0x29` | teilweise | Lesestellen und Aufbau der Slots bestimmt, Wirkung am Wert gemessen. Ein Fehler der Karte korrigiert (Vorgabe-Speed und -Tiefe), ein zweiter vermerkt (die Firmware liest eine zweite Kopie der Tabelle). |
| SQEZ beim Schreiben | beantwortet | Die Kennung kommt nur in lesendem Code vor; die Firmware kann das Format lesen, schreibt es nach allem Lesbaren nicht. |

## Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| Die Deskriptoren der Indizes `0x0B` bis `0x0E`, `0x17`, `0x19` bis `0x26` und `0x41` sind derselbe wie der von Index `0x00` (DSP `0x42D8`, "NoFx(Thru)", keine Parameter) | gemessen | Skript 1 unten, 66 Zeiger bei DSP `0x4C30` |
| `mfx_device 0x30` hat denselben Deskriptor wie `0x27` (DSP `0x49F4`, "NoFx(mute)", ein Parameter "Fader") | gemessen | Skript 1 |
| Der Insert-Baustein `0x04` (Punch) ist im DSP ein Durchreicher: gleiche Prozess- und Init-Funktion wie `0x00`, keine Parameter | hergeleitet | Skript 1: `+0x18` und `+0x20` des Deskriptors gleich |
| Stufe 2 bekommt nie Platzspeicher | hergeleitet | Lader Zustand 3, DSP `0x18736` bis `0x18788`: bei gesetztem Bit 0 der Feldnummer Speicher 0 und Größe 0 |
| Stufe 2 ist die ungerade Feldnummer `2 * Teil + 1` | hergeleitet | ARM `0xC003E074` (`mla r0, ip, r0, r1` mit 2 und 1) und `0xC003E078` (Stufe 1 gleich `2 * ip`) |
| Speicher verlangen genau `0x11` Chorus, `0x12` Flanger, `0x16` Ring Mod, `0x18` Short Delay | gemessen | Skript 1, Bytes `+5` und `+6` des Deskriptors ungleich 0 (Insert-Bausteine) |
| Der ARM prüft die Bausteinnummer beim Senden nicht | hergeleitet | `0xC003DE6C` vergleicht nur Bytes des Records mit dem letzten Stand und schickt Änderungen; Nummern kommen nicht in einer Tabelle vor |
| `lfo_reset` ist im DSP-Parameterwandler nicht begrenzt, er indiziert eine Tabelle bei DSP `0x1F060E4` | hergeleitet | Disassembly `0x1C774EA`, `0x231C` und weitere, Aufruf von `0x66DC` |
| Tabellenwerte bei `0x1F060E4`: Index 0 gleich `0xFFFFFFFF`, 1 gleich 0, 2 und 3 gleich Zeiger auf Konstanten | gemessen | `rd.py out/hack 0x1f060e4`, Worte gelesen |
| Beim Chorus wird das Wort als Maske auf die Phase gelegt und danach auf `-1` zurückgesetzt | hergeleitet | Disassembly `0xFFA0030A` bis `0xFFA0031C`; dass `[B0]` die Phase ist, ist nicht bestätigt |
| Alle 13 LFO-Bausteine und der Master-Decimator rufen `0x8534` (Level Mod `0x8600`), und beide rufen `0x694A` mit der Tabelle bei DSP `0x97A0` | hergeleitet | Disassembly der Sync-Note-Funktionen aller Einheiten |
| Beim Ändern der Modulationsart bekommt der Part Tiefe aus `+0x1A` und Speed aus `+0x1B` des Eintrags (71 von 72 Arten) | gemessen | Skript 2 unten |
| Die Firmware liest die Modulationstabelle aus einer zweiten Kopie ab Dateioffset `0x1A00FC`, die Kopie bei `0xD82EC` nie | gemessen | Lesehaken, Skript 3 |
| Die Werte kommen aus einem Speicher je Part und Art ab `0xC069256D` (Paare Tiefe, Speed); ein Schreiben dort wirkt sofort | gemessen | Skript 3 |
| Ein Schreiben in die Slotbytes der gelesenen Kopie ändert die Modulationstiefe sofort | gemessen | Skript 4 |
| Die Kennung SQEZ steht nur an drei Codestellen, alle lesend | hergeleitet | Wortsuche im ARM-Abbild, Querverweise, Disassembly `0xC0030FFC`, `0xC003879C`, `0xC0034E14` |

## 1. Unbekannte Bausteine: `mfx 0x30`, `ifx 0x0B` bis `0x0E`, `0x17`

**Beantwortet für den DSP, offen für die Oberfläche.** Der DSP indiziert seine 66 Deskriptoren mit der
Bausteinnummer (Bits 0 bis 6 des Typbytes, Lader Zustand 3 ab DSP `0x18748`). Die Plätze, die in
`units.json` fehlen:

| Nummer | Deskriptor im DSP |
|---|---|
| `0x0B` bis `0x0E`, `0x17` (und `0x19` bis `0x26`, `0x41`) | derselbe wie `0x00`: "[I] NoFx(Thru)", keine Parameter, Prozessfunktion `0xFFA01348` (kopiert Eingang auf Ausgang, so auch beim Platzwechsel gesetzt) |
| `mfx_device 0x30` | derselbe wie `0x27`: "[M] NoFx(mute)", ein Parameter "Fader" |

Eine Lücke heißt hier also "da ist ein Durchreicher", nicht "da ist etwas Unbekanntes". Ein Preset mit `0x0B`
in einer Insert-Stufe sollte sich wie `0x00` verhalten. Nicht geprüft ist, ob der ARM die Nummern annimmt: er
reicht sie beim Senden ohne Tabellenprüfung weiter (`0xC003DE6C`), eine Prüfung an anderer Stelle (Menü,
Türsteher) ist nicht gelesen. Nummern ab `0x42` indizierten hinter die Zeigertabelle des DSP und sind keine
Option.

Nebenbefund: der Insert-Baustein `0x04` (Punch) hat im DSP keinen Parameter und dieselben Funktionen wie der
Durchreicher. Das passt zu Korgs Hinweis, IFX 01 Punch kostet keine Last (`data/findings.mjs`, `heavyIfx`).

**Kürzester Test am Gerät:** einen Insert-Record im RAM auf `0x0B` stellen, Hörprobe auf einem Part mit Ton.
Erwartung: gleich wie `0x00`, kein Absturz. Ein Ausfall widerlegt die Herleitung.

## 2. Stufe 2: Deskriptoren und Lader

**Gemessen** sind im Stand der Befunde 13 von 19 Insert-Bausteinen (`0x01` bis `0x0A`, `0x10`, `0x16`, `0x18`).
Offen: `0x0F` Distortion, `0x11` Chorus, `0x12` Flanger, `0x13` Phaser, `0x14` Tremolo, `0x15` Level Mod.

**Herleitung aus dem Lader (DSP `0x18736` bis `0x18788`):**

- Der ARM sendet beide Stufen eines Parts über dieselbe Routine (`0xC003E018`), Stufe 1 an Feld `2 * Teil`,
  Stufe 2 an Feld `2 * Teil + 1`.
- Der DSP gibt Platzspeicher (192 000 Byte) nur der geraden Feldnummer, also Stufe 1, und nur wenn Byte `+5`
  oder `+6` des Deskriptors ungleich 0 ist. Bei Stufe 2 steht Speicherzeiger und -größe auf 0.
- Bausteine mit Speicherbedarf: `0x11`, `0x12`, `0x16`, `0x18`.

**Vergleich mit den Messungen:** `0x16` (läuft, kein Ton) und `0x18` (Gerät hängt) passen, beide brauchen Speicher.
`0x01` und `0x08` (stumm) und `0x02` und `0x09` (Absturz) brauchen keinen und fallen trotzdem aus. Die Regel
erklärt also zwei von sechs Ausfällen, die vier anderen bleiben ungeklärt.

**Vorhersage, ungeprüft:** `0x11` und `0x12` in Stufe 2 fallen aus (Speicher fehlt). `0x0F`, `0x13`, `0x14`, `0x15`
haben keinen Speicherbedarf; ob sie laufen, entscheidet der Versuch. Ein Muster zum Namen: alle fünf nicht
"Dbl" genannten Bausteine (`0x03`, `0x04`, `0x06`, `0x0A`, `0x10`) liefen in Stufe 2, von den "Dbl"-Bausteinen
liefen nur `0x05` und `0x07` (Namensteil "[I/Dbl]" im Deskriptor). Was "Dbl" bedeutet, ist nicht gelesen; die
Beobachtung ist ein Hinweis, kein Beleg.

**Kürzester Test am Gerät:** Stufe 1 fest Filter `0x0A`, Stufe 2 nacheinander `0x0F`, `0x13`, `0x14`, `0x15`,
zuletzt `0x11`, `0x12` (diese sind die wahrscheinlich hängenden). Je Kette drei Sekunden Rauschen, Pegel
aufnehmen, nach jedem Absturz Neustart.

## 3. Decimator mit zweiter Stufe

**Der ARM-Teil.** Der ARM sendet beide Stufen mit derselben Routine ohne Bausteinprüfung
(`0xC003E018`, `0xC003DE6C`). Es gibt keine Assertion und keine Sperrliste dafür. Der Absturz entsteht im DSP
oder im Lader. Im Emulator lässt er sich nicht nachstellen, denn er hat keinen DSP.

**Was bleibt.** Warum `0x09` mit einer zweiten Stufe abstürzt, ist offen. Die Speicherregel (Abschnitt 2) scheidet
aus, der Decimator braucht keinen Speicher. Die Messung: Absturz in beiden Richtungen, `0x09 -> 0x0A` und
`0x0A -> 0x09`.

**Test am Gerät:** `0x09 -> 0x10` und `0x09 -> 0x06` (die beiden Stufe-2-Bausteine, die Korg selbst nutzt),
dazu `0x09 -> 0x04` (Punch, im DSP ein Durchreicher). Läuft Punch, ist es die Anwesenheit einer zweiten Stufe,
nicht deren Rechnung.

## 4. Stufe 1 durchprobieren

Braucht Gerät. Aus dem Lader: Stufe 1 bekommt Speicher, also sind `0x11`, `0x12`, `0x16`, `0x18` dort
möglich. Gemessen ist bisher `0x15 -> 0x0A` (läuft), `0x02 -> 0x10` (läuft), `0x15 -> 0x18` (hängt), `0x09 ->
0x0A` (Absturz), `0x16 -> alles` (stumm).

**Kürzester Test:** Stufe 2 fest Filter `0x0A`, Stufe 1 nacheinander die 19 Bausteine, je drei Sekunden Rauschen. In
dieser Reihenfolge, das Gefährliche zuletzt: `0x01` bis `0x08`, `0x0F`, `0x10` bis `0x15`, dann `0x16`, `0x18`, `0x09`.

## 5. Drei Kompressoren

Aus den DSP-Tabellen (`2026-10-14-fx-tabellen.md`, Deskriptoren):

| Baustein | Regler | Rechnung |
|---|---|---|
| `0x01` mKP2 Comp | Sensitivity, Attack, Output, Trim, vier EQ-Regler (10) | eigene Funktionen (`0xFFA078D8` bis `0xFFA07AF2`) |
| `0x02` SR1 Comp | Threshold, Ratio, Knee, Attack, Release, Hold, Tube, Output (10) | Funktion `0xFFA00AD0`, **dieselbe wie `0x05` Limiter** |
| `0x03` Cheap Comp | HPF, Peak Hold, Env LPF, Bit Shift, Sens, Output (6 im DSP, 4 in `units.json`) | eigene Funktionen (`0xFFA08D98`) |

**Hergeleitet:** drei getrennte Algorithmen mit nicht vergleichbaren Reglern. "Attack" des mKP2 und "Attack" des SR1
sind verschiedene Dinge, und der SR1 hat einen Schwellwert, der mKP2 keinen. Verschiedene Ergebnisse bei
gleichem Namen sind erwartet.

**Offen:** ob die Vorgaben klanglich vergleichbar sind, und die Parameterzahl von Cheap Comp (4 oder 6,
siehe `2026-10-14-fx-tabellen.md`). **Kürzester Test:** ein Kick-und-Hihat-Loop, nacheinander `0x01`, `0x02`,
`0x03` mit Vorgaben, Ausgangspegel auf gleiche Lautheit, dann nach Gehör vergleichen; dazu bei `0x03` die Regler
5 und 6 (Sens, Output) bewegen: reagiert etwas, hat der Baustein 6 Parameter.

## 6. Sieben ungenutzte MFX-Bausteine

Die Vorgaben als gespeichertes Byte, in Parameterreihenfolge der DSP-Tabelle (angezeigter Wert gleich Byte plus
Minimum, siehe `2026-10-14-fx-tabellen.md`). Alle stimmen mit `data/units.json` überein, Parameterzahl und
Vorgaben, null Abweichungen in diesen sieben (Skript 1). Die beiden Quellen sind nicht unabhängig, die
Tabelle in `units.json` stammt aus demselben DSP-Strom.

| Baustein | Vorgaben (Byte) |
|---|---|
| `0x28` mKP2 Comp | 100, 0, 49, 50, 12, 127, 36, 16, 36, 50 |
| `0x2A` Limiter | 100, 0, 36, 0, 8, 8, 50, 72 |
| `0x2B` 4 Band EQ | 100, 127, 2, 0, 0, 1, 16, 5, 36, 33, 5, 36, 48, 5, 36, 52, 5, 36 |
| `0x34` Tremolo | 100, 0, 80, 2, 50, 0, 0, 66, 1, 25, 36, 0, 18 |
| `0x39` Dry Plate Reverb | 100, 31, 61, 51, 39, 64, 30, 30, 26 |
| `0x2C` Wah | 100, 0, 0, 127, 1, 1, 1, 127, 0, 0, 0, 47, 6, 19, 0, 0, 56 |
| `0x35` Level Mod | 127, 24, 2, 126, 0, 1, 1, 33, 6, 27, 0, 36 |

Die Spannen je Parameter stehen in `data/map/fx-ranges.mjs`. Offen: ob diese Vorgaben ein musikalisch brauchbarer
Ausgangspunkt sind (zum Beispiel Level Mod mit Tiefe 126, bipolar, Ruhepunkt 63) und ob der DSP sie beim Laden
einer Einheit selbst setzt. Beides sieht man am Gerät: Baustein in einen Master-Record setzen, alle
Parameter auf die Tabellenvorgabe, hören.

## 7. Synchronisation

**Mechanismus (hergeleitet).** `lfo_reset` ist im DSP ein Einmal-Auslöser. Der Parameterwandler bildet den
Wert über eine Tabelle bei DSP `0x1F060E4` auf ein Wort im Zustand des LFOs ab (Chorus: Wort 2):

| Wert | Wort | Wirkung (Chorus, Prozessfunktion `0xFFA002B8`) |
|---|---|---|
| 0 | `0xFFFFFFFF` | Maske ohne Wirkung, Phase unverändert |
| 1 | 0 | Maske null: Phase wird auf 0 gesetzt |
| 2, 3 | Zeiger (`0x01F0A8D8`, `0x01F0A928`) | Maske mit Zeigerbits: Phase wird auf einen von der aktuellen Phase abhängigen Wert verändert |

Danach schreibt der DSP `-1` zurück: ein Reset gilt einmal. Der Tremolo-Baustein ist einfacher: jeder Wert ungleich
0 schreibt 0 in ein Wort des Zustands (vermutlich die Phase).

**Der ARM sendet nur geänderte Parameter** (`0xC003DE6C` vergleicht jedes Byte mit dem letzten Stand). Daraus
folgt, was die Messung vom 2026-09-21 zeigte: Steht `lfo_reset` fest auf 1, feuert das einmal beim Laden. Eine
Zeile Play auf `lfo_reset` setzt den Wert bei jedem Druck und löst deshalb jedes Mal aus. Das passt zur
Messung, die Play-Zeile synchronisiere.

**`lfo_reset` 2 und 3.** Die Spanne der Tabelle ist `[0, 1]`. Der Wandler prüft sie nicht, wer 2 oder 3 schickt,
liest die danebenliegenden Zeiger (die Tabelle hat nur zwei Wörter). Hergeleitet: ein einmaliger Phasensprung auf
einen Wert, der von der Phase abhängt, danach normaler Lauf. Das ist **kein** Dauer-Resync und löst das
Resync-Problem nicht. Ob der Sprung hörbar ist und wie er klingt, ist offen.

**Slicer und Repeater laufen aus dem Takt.** Folgt aus dem Mechanismus: nach einer Parameteränderung gibt es keinen
neuen Auslöser, der LFO läuft mit dem alten Phasenversatz weiter, und erst Stop und Play (Play-Zeile) setzt neu.
Das ist eine Herleitung, kein Befund am Klang. Welche Parameteränderungen die Phase selbst verschieben,
ist nicht gelesen.

**Test am Gerät (kürzester):** Level Mod `0x15`, Sync an, Note 1/4, ein Part mit gleichmäßigem Ton.
`lfo_reset` im RAM nacheinander 0, 1, 0, 2, 0, 3 schreiben (jeweils auf 0 zurück, sonst ist es keine Änderung
und der ARM sendet nichts). Hören: bei 1 springt das Pumpen auf den Beginn, bei 2 und 3 ein einmaliger Sprung
auf anderen Stand, danach läuft es durch. Dazu `lfo_speed` verändern und hören, ob das Pumpen aus dem
Takt gerät.

## 8. Sync-Notenwerte

**Hergeleitet (Code gelesen):** Alle 13 LFO-Bausteine (`0x11` bis `0x16`, `0x2C`, `0x2D`, `0x31` bis `0x35`)
und dazu der Decimator `0x3E` im Master rufen dieselbe Funktion `0x8534` (Level Mod `0x8600`) und beide dieselbe
Nachschlagefunktion `0x694A` mit der Tabelle bei DSP `0x97A0`: Records zu 6 Byte, zwei 16-Bit-Zahlen
(Zähler, Nenner) und eine Null. Es gibt also **keine** Tabelle je Baustein; der Parameter `SyncNote` hat überall die
Spanne `[0, 41]` (42 Werte). Die Delays (Short Delay, Mod.Delay mit Spanne `[0, 63]`) benutzen eigene Funktionen
(`0x1C7EB26`, `0x1C78CCC`, `0x1C78DCC`), nicht gelesen.

Verhältnisse nach Index (Zähler / Nenner):

| Index | Wert |
|---|---|
| 0 bis 12 | 16, 8, 4, 2, 1, 1/2, 1/4, 1/8, 1/16, 1/24, 1/32, 1/64, 1/128 |
| 13 bis 25 | 1/2, 3/8, 1/3, 1/4, 3/16, 1/6, 1/8, 1/12, 1/16, 1/24, 1/32, 1/64, 1/128 |
| 26 bis 33 | 8, 4, 2, 1, 1/2, 1/4, 1/8, 1/64 |
| 34 bis 41 | 1/4, 3/16, 1/8, 1/12, 1/16, 1/24, 1/32, 1/64 |

**Hergeleitet:** die Werte sind Perioden in Takten oder ganzen Noten, denn 1/24, 1/12, 1/6, 1/3 sind Triolen und
3/8, 3/16 punktierte Noten. Die Vorgaben passen dazu: Level Mod, Tremolo, Wah und Multimode-Filter stehen auf
Index 6 gleich 1/4, die langsamen Chorus, Flanger, Phaser und Ring Mod auf Index 1 bis 5 (8 Takte bis ein halber). **Offen:** ob
die Einheit "Takt" (ganze Note) oder "Viertel" ist (Faktor 4), und wie Korgs Namen (1/4, 1/8T, 1/4D) auf die Indizes
fallen; das entscheidet eine Hörprobe oder Korgs Liste. Die Gruppen 13 bis 25 und 34 bis 41 sehen nach Varianten
(punktiert, Triolen) der ersten aus, die Gruppierung im Menü ist nicht geprüft. Die Karte bekommt keine Namen, bis
das geklärt ist.

**Kürzester Test:** Tremolo `0x14` oder Level Mod `0x15`, Sync an, Tempo 120, `SyncNote` auf 6 (erwartet
Viertel, 2 Schläge je Sekunde) und auf 8 (erwartet Sechzehntel), Tempo mit der Stoppuhr oder per Aufnahme
auszählen.

## 9. Modulationstabelle ab `+0x29`

### 9.1 Zwei Kopien, und die Karte zeigt auf die falsche

**Gemessen.** Die Tabelle der 72 Modulationsarten steht zweimal im Firmwareabbild: bei Dateioffset `0xD82EC` (RAM
`0xC00D81EC`, dort steht sie in `data/map/firmware.mjs`) und bei Dateioffset `0x1A00FC` (RAM `0xC019FFFC`). Beide sind
bis auf die ersten vier Bytes des ersten Eintrags gleich (Zeiger gegen `0xFF`). Mit einem Lesehaken im Emulator, ab
Einschalten und über Boot, Hauptbild, Drehen von MOD. TYPE, MOD. DEPTH, MOD. SPEED und Play:

- Lesezugriffe auf die Kopie bei `0xD82EC`: 0.
- Lesezugriffe auf die Kopie bei `0x1A00FC`: tausende, aus `0xC0098xxx` und `0xC009946C`. Der Code nimmt
  `0xC01A0000` als Anfang der Namen (`0xC0098D3C`).

Wer die Tabelle in einer gepatchten `SYSTEM.VSB` ändert, muss die Kopie bei `0x1A00FC` ändern (und
sinnvollerweise beide). Die Karte bleibt bei `0xD82EC`; die Notiz an `table.modType` nennt jetzt die zweite Kopie.
Ob bei einem anderen Pfad (zum Beispiel Laden eines Pattern) die erste Kopie benutzt wird, ist nicht gezeigt.

### 9.2 Vorgabe-Speed und Vorgabe-Tiefe

**Gemessen.** Die Karte nannte `+27` "Vorgabetiefe". Im Emulator (Skript 2): bei jedem Drehen von MOD. TYPE setzt
die Firmware Speed und Tiefe des Parts. Die Werte:

- **Tiefe gleich Byte `+0x1A` des Eintrags**, **Speed gleich Byte `+0x1B`**, bei 71 von 72 Arten. Die eine
  Ausnahme ist die Art, mit der das Init-Pattern startet (Art 3): sie zeigt 127 und 127. Das passt zur Herkunft,
  der Wert kommt aus dem Speicher je Part und Art (nächster Abschnitt).
- Der Karteneintrag `modType.depth` lag auf `+27`. Korrigiert: Tiefe auf `+26`, Speed neu auf `+27`.

### 9.3 Woher die Vorgaben kommen

**Gemessen.** Beim Einschalten füllt die Firmware aus der Tabelle (Kopie `0x1A00FC`) einen Speicher je Part und
Art (Part 14 stimmt danach für alle 72 Arten mit der Tabelle überein; bei Part 1 weicht Art 3 ab, die Art des
Init-Patterns): `0xC069256D + 2 * (Part * 72 + Art)`, je Paar (Tiefe, Speed), 16 mal 72 mal 2 Byte. Beim Drehen von MOD.
TYPE liest sie das Paar von dort (`0xC0099554`, `0xC0099580`), setzt Art, Tiefe und Speed über die allgemeinen
Setter (`0xC0049B90`, `0xC0049B18`, `0xC0049A9C`) und schreibt beim Drehen von MOD. DEPTH und MOD. SPEED das Paar
zurück (`0xC00995F0`, `0xC00995B0`). Es ist also ein Gedächtnis der letzten Einstellung je Part und Art, keine
Tabelle der Vorgaben.

- Ein Schreiben von Tiefe `0x22` und Speed `0x11` auf den Platz von Part 1 und Art 12 und dann Art 12 wählen:
  Part zeigt `0x11` und `0x22`. **Wirkt sofort.**
- Ein Schreiben von Tiefe und Speed in die gelesene Tabellenkopie (Art 12) und in die andere Kopie (Art 13) und
  dann die Art wählen: **keine Wirkung**, weil das Gedächtnis schon gefüllt ist. Das klärt die alte Frage, ob ein RAM-Schreiben in die Tabelle live wirkt: für
  die Vorgaben nein, für die Slotbytes (9.4) ja.

### 9.4 Aufbau ab `+0x1A`, was gelesen wird

Die Firmware liest die Einträge ab dem Namen (`+4` im Record der Karte); im Folgenden gelten die Offsets der
Karte. **Gelesen** (Lesehaken, Boot, MOD. TYPE, DEPTH, SPEED, Play; Funktion in Klammern):

| Offset | Gelesen von | Bedeutung |
|---|---|---|
| `+0x19` Ziel | in den Läufen nicht gelesen | Ziel des Eintrags (Muster `03 01 02 04 00 05`, aus der Messung vom 2026-09-14) |
| `+0x1A` | `0xC0098FC0` | **Vorgabe-Tiefe**, zugleich feste Tiefe für Slots mit Merker 0 |
| `+0x1B` | nur beim Füllen des Gedächtnisses | **Vorgabe-Speed** |
| `+0x1C` | `0xC0098E94` | Kurvenform; ein Setter bei `0xC009916C` schreibt dort zur Laufzeit |
| `+0x1D`, `+0x1E` | `0xC0098ECC`, `0xC0098EAC` | Merker (je als 0 oder 1 gelesen); `+0x1E` wählt, ob die Speedkurve nach Ausgang 0 oder 1 geht |
| `+0x20`, `+0x21` | `0xC0099040`, `0xC0099044` | Paar (Untergrenze, Obergrenze) für Speed, Wertebereich 0 bis 127; LFO-Arten 0 und 127 |
| `+0x24` | `0xC0098E58` | Merker "BPM": bei allen BPM-Arten 1 |
| `+0x28`, `+0x29` | `0xC0099018`, `0xC009901C` | Paar (Unter-, Obergrenze) für Speed; EG-Arten 0 und 127, BPM-EG-Arten 16 und 1 (Schritte) |
| `+0x2C` bis `+0x53` | je Slot `k` von 0 bis 4, Stride 8 | siehe unten |
| `+0x54` bis `+0x57` | Slot 5, Stride 8 | der sechste Slot ist abgeschnitten: seine Bytes `B` und Merker liegen im Anfang des Folgeeintrags (Offset 0 und 1, immer 0) |

Je Slot (acht Byte ab `+0x2C + 8 k`): **`+0` gelesen** (`0xC0098F10`, Bedeutung offen, 0 bei den EG-Arten,
1 bei den übrigen), **`+1` gelesen** (`0xC0098F30`, Ziel des Slots: 1 Pitch, 2 OSC, 3 Filter, 8 Level, 9 Pan,
10 IFX, nach dem Namen der Einträge zugeordnet), **`+2` nicht gelesen** (Werte 0, ±32, ±48, ±53, ±63; Bedeutung
offen), **`+3` und `+4` gelesen** (`0xC0098FB4`, `0xC0098FBC`: vorzeichenbehaftete Untergrenze `A` und Obergrenze
`B` der Modulationsstärke; in der Tabelle nur (0, 63), (-63, 0) und (0, 0)), **`+5` gelesen** (`0xC0098FB0`:
Merker, 0 nimmt die feste Tiefe aus `+0x1A`, 1 nimmt die Tiefe des Parts), **`+6` und `+7` nicht gelesen**
(immer 0).

**Nicht gelesen** in den Läufen: `+0x2A`, `+0x2B`, `+0x2E`, `+0x32`, `+0x33` (und jeweils plus 8 je Slot). `+0x2A` und
`+0x2B` sind in allen 72 Einträgen 0, `+0x32` und `+0x33` ebenso.

**Wirkung am Wert (gemessen, Skript 4).** Die Firmware rechnet aus Tiefe und Slotgrenzen eine Stärke je Slot in einen
Speicher je Part (Neun Byte je Part, Ausgang 3 bis 8 sind die Slots, `0xC06924DD`):

- Art 12, `A = -63`, `B = 0` (wie ausgeliefert): Stärke `-10`, `-25`, `-50` bei Tiefe 21, 50, 100.
- Dieselbe Art, `A = -10`, `B = +20` in die gelesene Kopie geschrieben: Stärke `+10`, `+25`, `+50`.

Das Vorzeichen von `B` bestimmt also die Richtung, der Betrag folgt der Tiefe mal 63 durch 127; die genauen
Beträge von `A` und `B` änderten hier nichts. Mit zwei Werten ist das eine Beobachtung, keine Formel.

**Offen:** Bedeutung von `+0x1D`, `+0x2C` (je Slot) und `+0x2E` (je Slot); wo die Ausgänge des Speichers hingehen (DSP
oder Klangerzeugung); ob die Kopie bei `0xD82EC` irgendwo gebraucht wird. Das nächste Stück ist, die Leser der
Ausgänge bei `0xC06924DD` zu verfolgen.

## 10. SQEZ

**Beantwortet, hergeleitet.** Die Firmware kann das Format lesen, schreibt es nach allem Lesbaren nicht.

- Die Kennung steht als 32-Bit-Wort in einem Literalpool bei `0xC0035320` und als Zeichenkette
  bei `0xC00A485D` (neben den Namen `SYSTEM.VSB`, `USER.VSB`, `PCM.VSB`, `SLICE.VSB`). Mehr Vorkommen hat das ARM-Abbild nicht (Wortsuche
  beider Byte-Reihenfolgen und Zeichenfolge).
- Die Querverweise: `0xC0034E18` (in der Entpackfunktion `0xC0034E14`), `0xC003104C` (Funktion `0xC0030FFC`) und
  `0xC00387CC` (Funktion `0xC003879C`). Alle drei vergleichen die Kennung eines Blocks und rufen dann die
  Entpackfunktion; keine erzeugt eine Kennung.
- Die Entpackfunktion ist ein LH5-Decoder (Fenster 8192 Byte, CRC16 mit Tabelle). Nach einem Packer wurde nicht
  gesucht, belegt ist nur, dass keine Stelle die Kennung erzeugt.
- Dazu passt: die Werks-Patternbank bei Flash `0x640000` wird beim Laden der Werkspatterns entpackt
  (`2026-10-07-werks-sample-flash.md`), nie neu gepackt.

**Folge für eine eigene Werksbank:** das Zurückschreiben geht nicht über die Firmware, nur über ein eigenes
Packprogramm plus Flash-Schreiben, und dort gilt die Sperre aus `../speicherbereiche.md`. Ein Lauf im
Emulator mit WRITE im Hauptbild schrieb gar nichts in den Flash (auch das Pattern nicht), er sagt dazu nichts.

## Skripte

Alle liefen im Scratchpad. Die Kerne zum Nachbauen:

**Skript 1, Deskriptoren.** Mit der Ladefunktion aus `tools/fx-tables.py` (`load_sdram`, `DESCRIPTORS`,
`UNITS`): je Index `i` Deskriptor `d` gleich Wort bei `DESCRIPTORS + 4 i`, Name gleich Zeichenkette bei Wort `d`,
Parameterzahl Byte `d + 4`, Bytes `d + 5` bis `d + 8` (Speicherflags), Funktionen Worte `d + 0x18`, `d + 0x1C`,
`d + 0x20`; Parameter aus Liste bei `d + 0x14` (Name, Vorgabe `+5`, Minimum `+6`, Maximum `+8`). Aufruf:
`python3 -I skript1.py SYSTEM.VSB`.

**Skript 2, Vorgaben beim Drehen.** Boot mit `bootcache.booted(VSB[0x100:], Flash, 0, 5.0)`, `Dev` aus
`tools/emu/splash_cases.py`. Das bearbeitete Pattern liegt bei `*0xC033E6A4 + 4`; Part `p` bei `+0x800 + 0x330 p`,
Art, Speed und Tiefe auf `+16`, `+17`, `+18`. Dann 80 mal `m.send([1, 3, 0, 1, 0])` (MOD. TYPE, +1) mit
`dev.run(0.25)` dazwischen, nach jedem Schritt die drei Bytes lesen und gegen `+0x1B` und `+0x1A` des Eintrags
vergleichen. Ergebnis: 71 von 72.

**Skript 3, Lesehaken und Gedächtnis.** Lesehaken (`UC_HOOK_MEM_READ`) auf beide Kopien von Einschalten an; zweiter
Lauf mit Schreiben von `(0x22, 0x11)` auf `0xC069256D + 2 * 12` und Drehen auf Art 12.

**Skript 4, Slotbytes.** Art 12, Gedächtnis auf Tiefe 21, 50, 100 setzen, Art 13 und zurück auf 12, Stärke lesen
bei `0xC06924DD + 3`; dann `0xC019FFFC + 12 * 0x58 + 0x2F` auf `F6 14` und wiederholen.

Die Messungen im Emulator waren je wenige Sekunden Gerätezeit, mit dem eigenen Flash.

## Was im Repository neu ist

- Dieses Dokument.
- `data/map/firmware.mjs`: Tiefe der Modulationsart auf `+26` verlegt, Speed als neues Feld auf `+27`,
  Evidenz `measure:2026-10-14/offene-fragen`; die Notiz an `table.modType` nennt die zweite Kopie.

Nicht geändert, weil nicht gemessen: Notennamen der Sync-Werte, Einheiten der Effektparameter, `findings.mjs`.
