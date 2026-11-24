# Hacktribe-Extras auf der roten Firmware und das Osterei

Hintergrund zu zwei Themen: Was Hacktribe gegenüber Korgs roter 2.02 zusätzlich mitbringt (Grooves, Touch-Skalen, Akkordtabellen,
Akkord-Sets) und ob sich das als Tabelleneinträge auf Korgs eigenem Code nachbauen lässt wie die Oszillatoren von `ht-osc`. Dazu das
Osterei auf der Seite VERSION und die Freischaltung im Flash. Die rohen Messnotizen stehen in der Git-Historie:
`git show origin/develop:docs/messungen/2026-11-10-hacktribe-extras-rot.md` und `...2026-11-09-osterei-version.md`.

Alle Adressen sind RAM-Adressen (Datei minus `0x100` plus `0xC0000000`). Grundlage: Emulator und Bytevergleich von Korgs Original
2.02 (rot), [Hacktribe](../glossary.md#hacktribe) 2.02 und Korgs blauer 2.02. Es ist nichts davon gebaut und **am Gerät nichts geprüft**
(Ausnahme: das Osterei ist im Emulator gebaut und geprüft, am Gerät offen). Markierungen: **gemessen** (im Emulator ausgeführt oder in
den Dateien verglichen), **hergeleitet**, **offen**.

Die Insert- und Master-Effekte von Hacktribe sind der Teil, der schon gebaut ist, siehe [Effekt-Katalog](../effekt-katalog.md#gleiche-plätze-auf-korgs-202-und-hacktribe)
und [Messung Master](../messungen/2026-11-17-hacktribe-master-rot.md).

## Ergebnis

| Teil | Hacktribe fügt hinzu | Urteil rot |
|---|---|---|
| Grooves | 37 neue (25 auf 62) | braucht etwas ARM-Code (Kopierhaken beim Start) oder Korg-Daten im Repo, kein DSP-Code |
| Touch-Skalen | 35 neue (35 auf 70) | als Datenpatch machbar: Korgs 35 bleiben unverändert, 35 neue angehängt; eigene Akkordtabellen je neuer Skala (entschieden) brauchen eine gemeinsame Methode mit 3 Befehlen ARM-Code |
| Akkord-Sets (Nebenfund) | 2 neue (4 auf 6) | offen, nicht untersucht |

Keine DSP-Änderung nötig. Lizenz: Hacktribes Tabellen dürfen nicht kopiert werden (siehe unten), jeder Port braucht eigene Daten aus
einer Feldtabelle wie bei `ht-osc`.

## Absturz und Müll auf rot: Hacktribe-Pattern ohne Port

Ein Pattern mit neuer Skala oder neuem Groove ist auf rot ohne Port gefährlich. Das Pattern-Byte bleibt beim Anwenden erhalten, die
Firmware rechnet damit.

- **Skala über 34 stürzt ab (gemessen):** ein Pattern-Skalenbyte (Byte 40) über 34 stürzt auf rot beim Anwenden bei `0xC0055BD0` ab.
  36 und 69 gemessen. 35, 50 und 70 überleben nur, weil hinter der Zeigerliste zufällige Bytes stehen. Je Wert neu gestartet.
- **Groove 40 liest fremdes RAM (gemessen):** ein Groove-Byte 40 bleibt beim Anwenden 40. Die sechs Leser `0xC00479F4` bis `0xC0047ADC`
  klemmen nicht und lesen auf rot den Eintrag 40 bei `0xC068D23C`, fremdes RAM hinter der Tabelle, ohne Assert. Gemessen mit Groove 40,
  Tiefe 127, beim Abspielen. Ein Groove über 24 liest auf rot also schon heute fremdes RAM.
- Ob und was davon am Gerät passiert, ist offen.

Quelle: Messung 2026-11-10/hacktribe-extras-rot

## Grooves

- **Rot hat keine Groove-Tabelle im Image (gemessen):** die 25 GVST-Vorlagen (je `0x140` Byte) baut die Firmware beim Start mit
  Inline-`strb`-Code (um `0xC0052200` bis `0xC0052440`, Literal `0xC0052338`) in den RAM ab `0xC068A03C`. Im Image stehen die Bytes nicht
  als Tabelle. Ein Datenpatch müsste die 25 Werksvorlagen als Bytes ins Repo legen, das geht nicht.
- **Hacktribe hat eine Image-Tabelle mit 62 Einträgen** bei `0xC0143B00` (Datei `0x143C00`, Format siehe
  [Gerätekarte](../geraetekarte.md#groove-templates)) und lenkt 4 Literale dorthin: `0xC0047A28`, `0xC0047A88`, `0xC0047AE8` (Leser für
  Offset, Velocity und Gate bei `+0x30`, `+0x31`, `+0x32`, Länge `+0x22`) und `0xC0080AF8` (Namen). Der Setter `0xC0049DA4` hat die Grenze
  `cmp r2,#0x18` auf rot und `#0x3d` auf Hacktribe, darüber setzt er 0. Der Menüumlauf bei `0xC007BB88`, `0xC007BB90`, `0xC007BB94` läuft
  bei 25 (rot) und 62 (Hacktribe) um.
- Hacktribes Einträge 0 bis 24 sind Byte für Byte Korgs RAM-Tabelle. Die 37 neuen: Forward, Backward, Swing Plus, Swing Minus,
  Crescendo 64, Decrescendo 64, Drift Plus 64, Drift Minus 64 und 29 Song-Grooves (Alright 64 bis Tutu 64, Door 32).
- **Urteil (hergeleitet):** zwei Wege ohne DSP-Code. Weg 1: ein kleiner ARM-Haken nach dem Groove-Aufbau kopiert die 25 RAM-Vorlagen an
  den Anfang der neuen Tabelle, die 37 neuen stehen als eigene Daten dahinter. Weg 2: eine Feldtabelle, aus der der Patchbauer die 62
  Einträge zur Bauzeit aus der Nutzer-VSB zieht. Weg 2 geht nur für die 37 neuen, die 25 brauchen trotzdem Weg 1. Die 37 Vorlagen sind
  kreative Daten Hacktribes und nicht übernehmbar, eigene Grooves wären nötig.
- **Blau:** gleiche Bauweise, GVST-Code bei `0xC0049134`, Groove-Grenze 24, eigene Adressen nötig. Offen.

Quelle: Messung 2026-11-10/hacktribe-extras-rot

## Touch-Skalen

Hacktribe hat 70 Skalen statt 35 (rot: Index 0 bis 34). Die 35 neuen: Lydian Minor, Phrygian Dominant, Major Bebop, Minor Bebop,
Dominant Bebop, Gregorian Nr.4, Lydian Diminished, Aeolyptian, Superlocrian, Aeolian Pentatonic, Kokin-joshi, Scottish Pentatonic, Iwato,
Acoustic, Raga Kamalamanohari, Neapolitan Major, Neapolitan Minor, Enigmatic, Raga Shri Kalyan, Hungarian Romanian, Salimic, Epogimic,
Espla's Scale, Spanish Octamode, Ionidyllic, Epicryllic, MEXian, Katycryllic, Raga Sindhura Kafi, Chromatic Hypolydian, Ionogian,
Gycryllic, Chromatic Phrygian, Hamel, Moptygic (im Display auf 15 Zeichen gekürzt, gemessen). Viele Namen stammen aus Ian Rings
Skalenverzeichnis (hergeleitet). Die 35 neuen haben 5, 6, 7, 8 und 9 Stufen (5, 4, 14, 11 und 1 Skalen, gezählt in Hacktribes Stufentabelle).

Korgs Code liest nur Tabellen, vier davon lenkt Hacktribe per Literal um (gemessen, Bytevergleich):

| Tabelle | Rot | Hacktribe | Literal | Inhalt |
|---|---|---|---|---|
| Stufen | `0xC00DCF70` | `0xC013EC00` | `0xC005423C` | 13 Byte je Skala: Anzahl und 12 Stufen; die ersten 35 sind gleich |
| Snap | `0xC00DD148` | `0xC013F280` | `0xC0054508` | 12 vorzeichenbehaftete Byte je Skala; Hacktribe ändert 126 der ersten 420 Byte (01 zu ff) |
| Namen | `0xC00DD330` | `0xC013E000` | `0xC00545BC` | Zeigerliste, Namen bei Hacktribe ab `0xC013E400` |
| Akkordobjekt je Skala | `0xC00DDB18` | `0xC0140000` | `0xC0055360`, `0xC005537C`, `0xC00553BC` | Zeiger nach `0xC068C4xx` |

- **Grenzen:** Menü `0xC007CF24`/`0xC007CF28` (`0x22` rot gegen `0x45`), Setter `0xC004860C`/`0xC0048610` (`cmp/movge #0x23` gegen `#0x46`).
- **Skalenindex:** im Objekt `0xC068BF7C` bei `+0x304`, im Pattern Byte 40 (`pattern.scale`, Bereich 0 bis 34 im Repo).
- **Entschieden:** Hacktribe ändert auch die Snap-Richtung der 35 Werksskalen. Für blechtribe bleiben Korgs 35 Snap-Einträge unverändert,
  35 neue werden angehängt.
- **Urteil:** als Datenpatch machbar, im freien Gebiet `0xC013C0B0` bis `0xC014F000` (siehe unten), mit 4 Literalen und 2 Grenzen. Auch
  `pattern.scale` im Repo (Editor, Prüfungen) hängt an der Zahl der Skalen.
- **Blau:** 35 Skalen, Namensliste `0xC00C3B08` (genutzt bei `0xC004B3B0`). Stufen-, Snap- und Objekttabelle auf blau nicht gesucht. Offen.

Intervalle und Namen der Skalen sind allgemeines Musikwissen und frei als Feldtabelle schreibbar (hergeleitet). Die Snap-Werte müssten
selbst bestimmt werden.

Quelle: Messung 2026-11-10/hacktribe-extras-rot

## Akkordtabelle je Skala (Akkordspiel auf den Pads)

Das Objekt je Skala (Zeiger aus `0xC00DDB18`) ist die Akkordtabelle der Skala. Alles gemessen (Bytes, Disassembly), die Rolle ist
hergeleitet.

- **Objekt:** 12 Byte: Zeiger auf eine eigene Methodentabelle (`0xC00DD458 + 24 * Skala`), Anzahl Zeilen, Anzahl Varianten (8 oder 6).
  Gebaut beim Start von `0xC00553C4`. Getter `0xC0055364`, Aufrufer beim Spielen `0xC0056160`
  (`ldr r3,[r0]; ldr r3,[r3,#8]; blx r3`).
- **Dritte Methode** (zum Beispiel `0xC0054918` für Chromatic): `ldr r0,=Basis; add r0,r0,r1,lsl #6; bx lr`, also 64 Byte je Zeile und
  8 Byte je Variante. Die Basis steht als Literal in der Methode, nicht im Objekt.
- **Eintrag (8 Byte):** Byte 0 Akkordname (Index in 22 Namen, 0 = kein Zusatz, also Dur), Byte 1 oben Grundton des Akkords plus 1, unten
  Basston plus 1 bei einem Slash-Akkord (sonst 0), Byte 2 Notenzahl (2 bis 5), Byte 3 bis 7 Noten in Halbtönen ab dem Grundton der Skala,
  Rest `ff`. Leser: `0xC005489C` (Byte 1 oben), `0xC00548C8` (Byte 1 unten), `0xC00548B0` (Name), `0xC00548EC` (Notenzahl),
  `0xC00548DC` (Noten). Beispiel Ionian Zeile 6 Variante 6: M7b5, Akkord F, Bass B.
- **Namenliste** `0xC00DD3E0`, 22 Namen: (leer), M7, add9, 7, M79, m, m7, m9, m7b5, 7sus4, dim, M7b5, dim7, 7b9, 9, drone, mM7, m79, sus4,
  aug, quintal, octave.
- **Zeilen und Varianten je Skala:** Chromatic 12 Zeilen mit 8 Varianten (Zeile 1 Variante 1: C# F G#, Akkorde auf jedem Halbton),
  Ionian 7 mit 8 (Zeile 1 Variante 1: D F A, m, leitereigen), Raga 1 16 mit 6 (Drone-Akkorde: tiefes C und G plus eine Skalennote),
  Octave 12 mit 6. Major Penta hat 7 Zeilen mit denselben Akkorden wie Ionian, 4th Interval 3 Zeilen. Korgs Zeilenzahl folgt also nicht
  immer der Stufenzahl.
- **Varianten bei Ionian** (Skalenstufen ab Stufe r, gemessen, Zählung hergeleitet): 0 = r, r+2; 1 = Dreiklang r, r+2, r+4; 2 =
  Septakkord dazu r+6; 3 = Dreiklang mit Grundton oben (r+7); 4 = Dreiklang mit None (r+8); 5 = offen r, r+4, r+6, r+9; 6 =
  Slash-Akkord mit 5 Noten, von Hand gewählt; 7 = offen r, r+6, r+9, r+11. Stufen über der Oktave zählen plus 12. Variante 4 und 6
  weichen in einzelnen Zeilen ab (Zeile 2 Variante 4 `7` über E), Korg hat sie von Hand gesetzt.
- **Variante aus dem Pattern:** das Pattern-Byte 41 setzt sie beim Anwenden (`u32(0xC00DECE4)` plus `0x314`). Gemessen 0 zu 0, 2 zu 2,
  3 zu 4, 5 zu 6, 7 zu 6, auf rot und Hacktribe gleich.
- **Die 35 neuen Hacktribe-Skalen zeigen alle auf Chromatics Objekt** `0xC068C520` (Zeigerliste `0xC0140000`). Auf Hacktribe liefert der
  Getter bei Skala 40 Chromatics Objekt. **Folge (hergeleitet):** das Akkordspiel auf den neuen Skalen ist chromatisch, nicht
  leitereigen. Skala, Snap und Namen sind davon nicht berührt.
- **Offen:** welcher Pad welche Zeile spielt (nicht verfolgt). Ob Zeilenzahlen unter 7 (5- und 6-stufige Skalen) am Pad anders aussehen
  als bei Korg.

### Entscheidung 10.11.: eigene Akkordtabelle je neuer Skala (Weg 3)

Drei Wege waren möglich: (1) alle neuen Skalen auf Chromatics Objekt, wie Hacktribe (reine Daten, Akkordspiel chromatisch, ohne Assert
gemessen); (2) jede neue Skala auf das Objekt einer Werksskala mit gleicher Stufenzahl (reine Daten, die Akkorde passen nur, wo die
Stufen übereinstimmen, nicht gemessen); (3) eigene Akkordtabellen. **Entschieden: Weg 3.** Noch nicht gebaut.

- **Daten (hergeleitet, keine Hacktribe- und keine Korg-Bytes):** eine Feldtabelle je neuer Skala aus den Intervallen. Ein Generator im
  Patchbauer stapelt Terzen in Skalenstufen nach dem Variantenmuster oben (eine Zeile je Stufe), sucht den Namen aus den Intervallen
  gegen die 22 Namen (passt keiner: Name 0 oder `quintal`) und setzt Byte 1 aus den Tonklassen. Variante 6 als Slash-Akkord bleibt eine
  eigene Regel (Vorschlag: Dreiklang auf Stufe r+4 über Stufe r).
- **ARM-Code (gemessen im Emulator, nur im Speicher):** eine gemeinsame Methode mit 3 Befehlen, 12 Byte, statt einer Kopie je Skala.
  Korg ruft sie mit dem Objekt in `r0`, also kann sie die Basis aus dem Objekt lesen:

      ldr r0, [r0, #12]          ; e590000c  Basis der Tabelle aus dem Objekt
      add r0, r0, r1, lsl #6     ; e0800301  plus Zeile * 64
      bx lr                      ; e12fff1e

- Dazu eine Methodentabelle (24 Byte, Einträge 0 und 1 Korgs eigene von Ionian, Eintrag 2 die neue Methode) und je Skala ein Objekt von
  16 Byte (Methodentabelle, Zeilen, Varianten, Basis). Die Objekte liegen fest im Image, Korgs Aufbau beim Start (`0xC00553C4`) braucht
  es dafür nicht.
- **Probe (gemessen, nur im Speicher):** Ionians Zeiger auf ein solches Objekt mit einer Testtabelle bei `0xC013D000` umgelenkt, Pattern
  mit Skala 1 und Akkord-Set 0, 1, 3 angewendet: der Getter liefert das neue Objekt, die Methode die Testeinträge für Zeile 0, 1 und 6 und
  die gesetzte Variante, keine Asserts. Der Weg über Korgs Aufrufer beim Spielen auf den Pads ist nicht ausgeführt (offen).
- **Platz (hergeleitet):** 244 Zeilen mal 64 Byte = 15.616 Byte, 35 Objekte = 560 Byte, Methodentabelle und Methode 36 Byte, zusammen rund
  16,2 KB. Das freie Gebiet hat 77.648 Byte, die übrigen Skalentabellen (Stufen, Snap, Namen, Zeiger) brauchen davon rund 2 KB.

Quelle: Messung 2026-11-10/hacktribe-extras-rot

## Akkord-Sets

Hacktribe hebt die Grenze der Akkord-Sets von 4 auf 6 (`0xC007CE34`/`0xC007CE38`, gemessen, rot 4). Das Akkord-Set wählt die Variante in
der Akkordtabelle der Skala (Pattern-Byte 41, `+0x2d`, gemessen). Die Tabellen haben 6 oder 8 Varianten. Die zwei neuen Sets wären also
nur die Grenze, ohne neue Daten (hergeleitet). **Offen:** wie Set 5 und 6 auf Skalen mit 6 Varianten wirken.

Quelle: Messung 2026-11-10/hacktribe-extras-rot

## Lizenz

Hacktribes `LICENSE` ist AGPL-3.0. Das README sagt aber, dass der Inhalt des Ordners `patch` nicht Open Source ist und nicht unter die
GPL fällt (siehe auch [Patcher](../patcher.md)). Die Tabellen kommen nur über diesen Ordner (`patch/hacktribe-2.patch`). Gemessen (Dateien
gelesen). Daraus (hergeleitet):

- Hacktribes Bytes (Records, Groove-Vorlagen, Skalentabellen) dürfen nicht ins Repo und nicht in einen Patch kopiert werden.
- Effekt-Records lassen sich aus eigenen Feldern neu aufbauen, wie bei `fx-catalog`. Ob die Parameterwerte eines Hacktribe-Presets
  geschützt sind, ist eine Rechtsfrage. **Offen.**
- Skalen-Intervalle und -Namen sind Fakten, frei schreibbar. Die 37 Groove-Vorlagen sind kreative Daten und nicht übernehmbar.
- Ein Weg ohne Kopie wäre wie bei `ht-osc` ein Bauschritt, der die Werte aus der Hacktribe-VSB des Nutzers liest. Der Bauschritt in
  `ht_osc.py` prüft gegen die VSB, er kopiert nicht. Ob das Lesen zur Bauzeit lizenzrechtlich reicht, ist **offen**.

Quelle: Messung 2026-11-10/hacktribe-extras-rot

## Unterschiede zwischen Hacktribe und rot

- **Diff (gemessen, Wortvergleich der beiden VSB):** unterhalb `0xC00A0000` unterscheiden sich Hacktribe und rot an 69 Stellen. Alle
  Zählstellen der Teile oben liegen darunter. Die übrigen Änderungen springen in Hacktribes eigenen ARM-Code ab `0xC0170000` (Filter,
  SysEx und anderes), Aufrufer `0xC0026450`, `0xC00265B0`, `0xC0026B00`, `0xC002B098`, `0xC002B294`, `0xC005F144`, `0xC006EAD4`,
  `0xC00702C0`, `0xC008374C`. Für Grooves und Skalen ist dieser Code nicht nötig (hergeleitet).
- **Freier Platz rot:** im Satz `blech.json` ist `FF` von `0xC013C0B0` bis `0xC014F000` (`0x12F50` Byte). Kein Patch-`ram` liegt dort,
  `ht-osc` beginnt bei `0xC014F000`. Im Hacktribe-Satz liegen dort Hacktribes Tabellen, ein Port wäre also nur für rot.
- **Freier Platz blau:** ab `0xC01217F4` rund `0x2E40C` Byte.

Quelle: Messung 2026-11-10/hacktribe-extras-rot

## Osterei auf der Seite VERSION

Im Emulator gebaut und geprüft (Hacktribe, rot, blau mit dem BLECH-Satz), **am Gerät nichts geprüft**. Code: `tools/patch/script_egg.s`,
Fälle `tools/emu/egg_cases.py` (Teil von `menu_cases`). Ob das Osterei hier dokumentiert bleiben soll, ist eine Entscheidung des Besitzers.

### Was passiert

- BLECH, Liste, Zeile VERSION, fünfmal MENU hintereinander: die Show startet. Viermal tut nichts. Jede andere Taste dazwischen (EDIT, eine
  andere Zeile) zählt von vorn, MENU auf einer anderen Zeile zählt nicht.
- Alle LEDs der Tasten, Encoder und Pads blinken 200 ms an, 200 ms aus. Pads und die Tasten mit zwei LEDs (PLAY, die Takte 1 bis 4)
  wechseln bei jedem An die Farbe: rot, blau, lila (beide), rot und so weiter. Die unteren RGB-LEDs bleiben, wie sie sind.
- Das Display-Licht läuft durch das Farbrad: ein Schritt von 96 alle 40 ms, eine Runde in 3,84 s, volle Sättigung und Helligkeit, über
  den Weg der Seiten DISPLAY (`look_hsv_rgb`, `menu_look_apply`).
- Der Bildschirm zeigt im Sekundenwechsel AUTISM groß und das Startbild (Bild 13, also Blechys Augen oder das eigene Bild des
  Startbild-Editors).
- EXIT: zurück auf VERSION, Licht und LEDs wie vorher. Beim ersten Mal steht zuerst zwei Sekunden `NEW SAMPLE 500` / `Unlocked` im
  Seitentext, spätere Male kommt die Meldung nicht. Wechselt die Firmware selbst den Bildschirm (eine ihrer Tasten), endet die Show wie
  mit EXIT, ohne Meldung.

### Lichtgrenze

- **Hergeleitet:** 2,5 Blitze pro Sekunde (200 ms an, 200 ms aus) liegen unter der Grenze von höchstens 3 pro Sekunde (WCAG 2.3.1,
  Three Flashes). Das Display-Licht blitzt nicht, es wechselt nur langsam den Farbton bei voller Helligkeit.
- **Gemessen (Emulator):** REC blinkt mit 2,5 pro Sekunde (Fall `egg_leds_blink_at_most_3_a_second`, 4 s in 50-ms-Schritten).
- **Gemessen:** mit 200 ms und dem normalen Budget von 16 LEDs pro Frame kam die Welle über alle 76 LEDs nicht rechtzeitig an (REC blieb
  einzelne Schritte durchgehend an, Pad 1 übersprang Farben, Fall `egg_pads_red_blue_purple`). Während der Show schickt
  `script_led_flush` deshalb bis zu 32 LEDs pro Frame, danach wieder 16. 76 LEDs brauchen so 3 Frames pro Wechsel.
- **Offen:** am Gerät ansehen, ob die Welle über das Panel stört.

Siehe auch [Barrierefreiheit](../barrierefreiheit.md).

### Wo die Freischaltung liegt: Globals-Byte 251 (Flash `0x2300F7`)

- **offline:** die Freischaltung steht im Globals-Block bei `0x230000` (256 Byte, Marke `GLED` bei `+0xFC`). Die Firmware speichert ihn
  selbst über `0xC004C1B4`: ein Löschen und 16 Seiten des 4-KiB-Sektors, beim Ausschalten (`0xC0038B4C`), bei WRITE auf Global, bei SysEx
  `0x51` und bei Import All Pattern ([Globals](../messungen/2026-10-13-globals-zurueckgesetzt.md)). Laden prüft nur `GLED`.
- **offline:** BLECH schreibt selbst nichts in den Flash. Es setzt nur das Byte im RAM-Objekt hinter `*0xC0691324`, Byte 251 (im Flash
  Byte 247, `0x2300F7`). Der Wert `0x5A` heißt frei. Gleicher Weg wie Init-Pattern (247), letztes Pattern (248, 249) und Startlicht (250).
  Kein zusätzliches Löschen, kein zusätzlicher Schreibvorgang.
- **gemessen:** die Bytes 44 bis 251 ändert kein Menü der Firmware, die Vorgabe ist 0 ([Global-Felder](../messungen/2026-10-14-global-felder.md)).
- **gemessen:** SOFTWARE UPDATE schreibt nur `0x020000` bis `0x220000`, die Globals bleiben gleich: die Freischaltung überlebt ein Update.
- **gemessen (Emulator, alle drei Builds):** nach der Show und dem Ausschalten steht im Flash `0x2300F7 = 0x5A`, nach dem Neustart ist Byte
  251 wieder `0x5A` (Fälle `egg_unlock_kept_in_the_flash`, `egg_unlock_survives_a_restart`). Blau hat dieselbe Lage (für Byte 250 gemessen,
  [Startlicht](../messungen/2026-10-29-hintergrundlicht-beim-start.md)).
- **hergeleitet, Grenzen:** die Freischaltung landet erst beim Ausschalten oder bei WRITE auf Global im Flash. Strom weg ohne Ausschalten
  verliert sie. Import All Pattern, SysEx `0x51` und FACTORY RESET schreiben den ganzen Block neu, danach ist sie weg.
- **AUTO SAVE (offline):** AUTO SAVE schreibt beim Verlassen von GLOBAL PARAMETERS den ganzen Global-Block, wenn ein Byte vom
  gespeicherten Stand abweicht, Byte 251 gehört dazu. Ist das Ei schon freigeschaltet, landet die `0x5A` dadurch früher im Flash. Zurück
  auf 0 setzt AUTO SAVE das Byte nie. `autosave_leave` beendet eine laufende Show vorher, damit die Farbe der Show nie in die
  Einstellungsdatei kommt (Fall `egg_auto_save_keeps_the_show_out`, gemessen im Emulator).

### Sample 500 (offen, nicht gebaut)

Ziel: nach der Freischaltung liegt auf Platz 500 (Index 499) ein Sample BLECH, auf rot, Hacktribe und blau.

- **gemessen:** die eigenen Samples beginnen bei Index 500 (Anzeige 501, `src/sample-file.mjs` `FIRST_USER = 500`). Index 499 heißt nach
  dem Start `Sample500`, Import-Nummer 549, Metadaten-Index 499, nicht geladen, auf rot (mit ht-osc) und Hacktribe. ht-osc belegt 421
  bis 496, 497 bis 499 bleiben leer (Fall `datei-497-bis-499-leer`).
- **offline:** der Import eines Samples ist `0xC004EDF0(rec)`: `rec+0` Platz, `rec+2` der 32-Byte-Namenseintrag, Start, Loop und Ende bei
  `+0x28`, `+0x2C`, `+0x30`, One-Shot `+0x34`, danach `0x45C` Byte Metadaten ab `+0x38`. Die Funktion holt den DSP-Speicher vom Zeiger
  `0xC00F9C80`, prüft vorher den freien Platz (`0xC004E218`) und lehnt ab, wenn der Platz schon geladen ist (`+0x0B` der Metadaten). Das
  PCM schreibt der Aufrufer danach über `0xC004EF28` in den DSP.
- **offline:** die Stimme fragt den Platz über `0xC0099788` ab, die Plätze 421 bis 499 geben dort nichts. Auf rot hebt ht-osc die Grenze
  auf 496 (`ho_voice`), für 499 muss die Zahl dort auf 499. Hacktribe braucht an seiner Stelle einen eigenen Haken.
- **hergeleitet:** ein Platzhalter von 1 s, 16 kHz, 16 Bit mono sind 32 KB, Platz dafür in MORE3 (gleich auf allen drei Builds).
- **Blocker:** der Export `0xC004EBD4` lässt nur DSP-Oszillatoren aus. Ein geladenes Sample auf 499 käme beim nächsten Speichern der
  Samples in die `e2sSample.all` des Nutzers. Der Export müsste 499 auslassen. Außerdem: der DSP im Emulator ist ein Stummel (Klang nur am
  Gerät prüfbar), und das Sample nimmt DSP-Speicher hinter den eigenen Samples, ist der voll, lehnt der Import ab.
- **Blau:** keine Nutzer-Samples. Möglich wäre es über einen der elf doppelten Einträge der Oszillatorliste (409 Einträge zu 32 Byte bei
  `0xC00BEB48`, PCM ab Wellen-Nummer `0x32`), das PCM mit dem DSP-Schreiber `0xC00105A4` hinter das Ende der Bank, dazu die Tabellen
  MSVS, MSPR, MSRL und SMPR ([Synth-Samples](../messungen/2026-10-15-synth-samples.md)). Nur die ARM-Seite ist im Emulator gezeigt.
  Offen und nur am Gerät prüfbar: ob der DSP von dort spielt, wo sein Speicher endet, welche Tonhöhe.

Quelle: Messung 2026-11-09/osterei-version

## Offen am Gerät

- Klang der 11 Inserts und 4 Master auf rot (siehe Effekt-Katalog).
- Ein Hacktribe-Pattern mit Groove über 24 und Skala über 34 auf rot ohne Port: was passiert am Gerät.
- Akkordspiel der neuen Skalen mit Chromatics Akkordobjekt: welcher Pad welchen Akkord spielt.
- Osterei: Welle der LEDs am Panel, Verhalten der Freischaltung am Gerät.
