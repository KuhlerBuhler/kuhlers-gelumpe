# Notenassistent: nach einer Note leuchten die passenden Pads

Stand 2026-10-16. Kein Gerätezugriff in dieser Sitzung, alles im Emulator (Firmware 2.02 mit Hacktribe, eigene `SYSTEM.VSB`, eigener Flash-Dump); am Gerät ist bestätigt,
dass die Hinweise erscheinen (Rückmeldung vom 16.10., siehe "Am Gerät gemessen"), alles andere ist es nicht.
Die Prüfungen sind `tools/emu/note_assist_cases.py` (läuft in `tools/emu/check.py` mit, Namen in Klammern), der Patch ist `data/patches/note-assistant.json`,
gebaut von `tools/patch/note_assist.py`. Marker: **gemessen**, **hergeleitet**, **offen** (am Gerät zu prüfen).
Die Pads sind wie in der Firmware von 0 gezählt (Pad 0 ist das Pad 1 am Gerät).

## Was der Patch tut

Im KEYBOARD-Modus leuchten gleich nach einer Note (im nächsten Takt des LED-Managers) die Pads der Noten, die dazu passen, in einem schwachen Rosa (die rote und die blaue LED des Pads zusammen, beide sehr niedrig)
und gehen nach 1,5 s ohne neue Note wieder aus. Pads, deren Note nicht passt, bleiben dunkel. Eine neue Note ersetzt die Hinweise sofort durch die zu ihr.
**Das Pad des gewählten Parts** (Pad n für Part n+1, sonst Blau 255 der Firmware) ist während der Hinweise ein Pad wie jedes andere: passt seine Note, zeigt es den Hinweis, sonst ist es
dunkel. Am Gerät war das Blau sonst nicht von einem Hinweis zu unterscheiden (Rückmeldung 16.10.). Enden die Hinweise (Zeit, anderer Pad-Modus, anderer Bildschirm, Oktave, Tonart, Tonleiter,
Einstellung aus, eine Note des Sequencers), gibt der Patch dem Pad das Blau 255 zurück: **gemessen** (`firmware_does_not_redraw_the_part_blue`), die Firmware leuchtet es nicht von selbst wieder,
ein dunkel gesetztes Blau blieb vier Sekunden dunkel. Das gedrückte Pad (Rot 192) bleibt wie bisher das Licht der Firmware, auch wenn es das Pad des Parts ist. Welches Pad das Blau des Parts trägt,
liest der Patch bei jedem Takt aus dem LED-Manager (`+0xB60`, der gewählte Part); das Pad, dessen Blau er genommen hat, merkt er sich in `STATE + 0x10`. Wechselt der Part, während die Hinweise stehen,
gilt für das alte Pad nur noch die Regel der übrigen Pads (die Firmware setzt das Blau selbst um, `part_change_leaves_no_stale_blue`).

## Am Gerät gemessen (Rückmeldung 16.10., Besitzer)

| Beobachtung | Folge |
|---|---|
| Die Hinweise erscheinen: nach einem Pad-Druck im KEYBOARD-Modus leuchten die passenden Pads rosa | der Weg über den LED-Manager (Tabellen und `0xC00875F4`) funktioniert am Gerät |
| Eine Pad-LED kennt nur an oder aus: 0 ist aus, jeder Wert ab 1 leuchtet voll ([Messung](2026-10-16-pad-led-stufen.md)); der LED-Manager schickt dieselbe Panel-Nachricht | die Werte 21 und 13 leuchten voll, das Rosa kommt aus Rot und Blau zusammen; "schwach" ist am Gerät nicht möglich, die Werte bleiben, weil der Patch seine LEDs an ihnen erkennt |
| Das Blau des gewählten Parts (255) blieb während der Hinweise stehen | der Grund für die Änderung oben: ob die Note dieses Pads passt, war nicht zu sehen |

| Frage | Entscheidung |
|---|---|
| Was passt | Abstand zur gespielten Note (modulo 12) von 0, 3, 4, 5, 7, 8 oder 9 Halbtönen: Prim und Oktave, kleine und große Terz, Quarte, Quinte, kleine und große Sexte. Nicht: Sekunden, Septimen, Tritonus |
| Innerhalb der Tonart und Tonleiter des Patterns | immer, ohne eigene Prüfung: das Layout der Pads ist die Tonleiter des Patterns (siehe unten), also sind alle 16 Pads Töne der Tonart und Tonleiter; die Abstandsregel allein filtert |
| Wann | ab dem nächsten Takt des LED-Managers (höchstens 40 ms) nach dem Drücken eines Pads; aus nach 38 Takten (je 40 ms, zusammen 1,52 s) ab dem Drücken, wenn keine neue Pad-Note kam |
| Welche Note zählt | eine Note, die ein Pad im KEYBOARD-Modus spielt, und seit 19.10. auch eine Note des Sequencers vom gewählten Part, wenn ein Pad des Layouts sie hält: sie ist dann die Bezugsnote und startet die 1,5 s neu (gemessen: `sequencer_note_shows_hints`) |
| Wie lange | 1,5 s ab der Pad-Note, oder bis der Modus wechselt, das Hauptbild verlassen wird oder sich Oktave, Tonart oder Tonleiter ändern; danach ist Ruhe bis zur nächsten Pad-Note |
| Gehaltenes Pad | die Hinweise erscheinen auch bei gedrücktem Pad; das gedrückte Pad behält das Rot der Firmware, nach dem Loslassen bekommt es den Hinweis (Prim), solange die 1,5 s laufen; sie laufen ab dem Drücken, nicht ab dem Loslassen |
| Aus | EXIT beim Einschalten, keine Karte, oder das Wort `NA_SETTING` auf 0. Ohne Datei oder Bit ist der Patch an |

## Wie die Firmware die Pads belegt

**Das Layout (gemessen, `layout_is_the_key_and_scale`).** Der KEYBOARD-Modus hat ein Objekt (Zeiger bei `0xC0348880`), das 16 Noten bei `+0x40` hält. Pad 0 bis 7 sind die Einträge 8 bis 15,
Pad 8 bis 15 die Einträge 0 bis 7. Die Firmware baut die Tabelle bei jeder Änderung von Tonart, Tonleiter und Oktave neu (Maschinencode `0xC0044C34`) aus ihrer Tonleitertabelle
(16 Byte je Tonleiter bei `0xC013D000`), der Oktave und, wenn Scale Mode des Parts aus ist, der Tonart. Bei Scale Mode an kommt die Tonart erst beim Spielen dazu, die gespielte Note ist am Ende
dieselbe (gemessen, `Scale Mode` 0 und 1: gleiche Pad-Noten). In sechs Kombinationen aus Tonart und Tonleiter (Dorian in C, Major Penta in D#, Chromatic, Ionian in G, minor Penta in F, Aeolian in A)
sind alle 16 Pad-Noten Töne der Tonart und der Tonleiter, bestimmt aus den Intervallen der Musiktheorie und der MIDI-Note, die die Firmware für jedes Pad sendet. Bei Chromatic sind es 16 Halbtöne, bei Dorian in C
steht 60, 62, 63, 65, 67, 69, 70, 72 auf Pad 0 bis 7 und 48 bis 60 auf Pad 8 bis 15. Eine Tonleiter, deren Noten über 127 hinausgehen (Index 34, gemessen: 120, 132, 144), hat Pads ohne Note;
auf die zeigt der Patch nie einen Hinweis.

**Tonart und Tonleiter des Patterns (hergeleitet aus dem Code, gemessen über die Setter).** Das Pattern hält die Tonart in Byte `+0x2B` und die Tonleiter in `+0x2C` seines Objekts
(Dateioffsets 39 und 40, [Gerätekarte](../geraetekarte.md)). Die Setter der Firmware sind `0xC004A6FC` (Tonart) und `0xC004A77C` (Tonleiter), beide bauen den Rest neu. Ein Byte direkt zu schreiben
ändert das Layout nicht, erst der Setter; die Prüfung setzt beides über die Setter, wie das Menü es tut.

**Welche Note gespielt wird (gemessen, Haken `pad_hook`).** Die Funktion der Firmware, die ein Pad im KEYBOARD-Modus behandelt (`0xC0044B3C`: Objekt, Pad, an, Velocity), liest die Note als Tabelleneintrag
und löst sie aus. Der Haken merkt sich Note und Pad, wenn ein Pad runtergeht, sonst nichts. Bei gehaltener KEYBOARD-Taste (Part wählen) ist der Aufruf nur ein Loslassen, der Haken tut dort nichts.

**Der Pad-Modus (gemessen).** Das Feld `+0xB58` des LED-Managers (Zeiger bei `0xC0345A1C`) ist der Modus der Pads: 3 TRIGGER, 4 SEQUENCER, 5 KEYBOARD, 6 CHORD, 7 STEP JUMP, 9 PATTERN SET, 0 PART MUTE.
`+0xB60` ist der gewählte Part. Das Hauptbild ist Bildschirm 1 (Zeiger `0xC03404C0`, `+0x2C`).

## Die Helligkeit der Pad-LEDs

**Was die Firmware schickt (gemessen, `firmware_pad_values`).** Jedes Pad hat zwei LEDs, rot bei `0x2C + 2n` und blau bei `0x2D + 2n`. Über alle sechs Pad-Modi, mit und ohne Spielen, sendet die Firmware an die Pads nur
**0, 192 und 255**: 192 für eine gespielte Note (zweimal die feste Velocity 96), 255 für das Blau des gewählten Parts und die Schritt-LEDs. Mit Pad Velocity an im Part ist die Helligkeit des gedrückten Pads
**zweimal die Velocity der Note**, gemessen (`firmware_pad_values`) 34, 98, 166 und 254 für die Pad-Velocities 5, 40, 90 und 127, in einem Handlauf mit Velocity 5 bis 127 auch 70, 130 und 180: gerade Zahlen von 34 bis 254, nie darunter.

**Hergeleitet:** das Bedienfeld bekommt ein Byte 0 bis 255 je LED, die Firmware nutzt für Pads Zwischenwerte (Velocity) und für die unteren RGB-LEDs einen ganzen Verlauf
([Anpassung](2026-10-14-blech-anpassung.md)). Sie geht also davon aus, dass das Bedienfeld Helligkeit abstuft.

**Am Gerät inzwischen beantwortet (16.10., siehe oben):** die Pad-LEDs zeigen Zwischenstufen, wenn sie über den LED-Manager gesetzt werden. **Offen** bleibt, wie ein Wert wie 21 aussieht (die Rückmeldung nennt rosa). Der Emulator hat kein Bedienfeld, er sieht nur das Byte, das die Firmware
schickt. Der Patch schreibt **rot 21 und blau 13 von 255** (8 und 5 Prozent), beides ungerade Zahlen unter dem kleinsten Wert der Firmware. Warum diese Werte: Blau wirkt bei gleichem Strom meist heller als Rot, also
bekommt Blau weniger; die Zahlen sind eine Schätzung, kein Messwert. Ob das am Gerät rosa und schwach wirkt, ist das Erste, was der Gerätetest klärt ([Gerätetest](../geraetetests/live.md), Punkt 5.1).
Zeigt das Bedienfeld nur an und aus, wären die Hinweise so hell wie das gedrückte Pad; dann ist die Abhilfe nur das Blau (Abstand zum Rot der Firmware) oder ein anderer Weg, und der Patch ist neu zu bauen:
die Werte stehen als `HINT_RED` und `HINT_BLUE` in `tools/patch/note_assist.py`, nirgends sonst.

## Wie die LEDs gesetzt werden

**Der Weg der Firmware (hergeleitet, im Lauf bestätigt).** Der LED-Manager hat je LED einen Eintrag zu 8 Byte, Helligkeit bei `+2`; die Firmware setzt Pads in `0xC008870C` (Manager, Part, Note, Velocity),
indem sie die Helligkeit in zwei Tabellen schreibt (`Manager + 0x4E + 8 * LED` und dasselbe `0x2C0` weiter) und `0xC00875F4` ruft ([LED-Zustand im RAM](2026-10-14-led-zustand-ram.md)). Der Patch geht genauso:
`na_put` schreibt beide Tabellen und ruft `0xC00875F4` mit dem Schalter 1, der den Vergleich mit der Kopie überspringt und immer sendet.

**Die Firmware schreibt ein Pad nur, wenn es dunkel ist (hergeleitet aus `0xC008870C`).** Bei einer Note an schreibt sie die Helligkeit nur, wenn der Eintrag 0 ist; bei einer Note aus schreibt sie immer 0. Ein Hinweis auf einem
Pad würde das Aufleuchten bei einer Sequencer-Note also verschlucken. Darum nimmt der Haken `light_hook` (erste Anweisung von `0xC008870C`) bei jeder Note an des gewählten Parts alle Hinweise weg, bevor die Firmware ihre Pads setzt.
Ohne diesen Haken bleibt das Pad hell und ohne Sequencer-Licht: Kontrollprobe unten.

**Der Patch erkennt seine LEDs am Wert.** Die Firmware schreibt nur 0, 192, 255 und gerade Zahlen; die beiden Werte des Patches sind ungerade und nicht 255. Jedes Pad mit einem Wert des Patches, das keinen Hinweis
zeigen soll, wird dunkel gesetzt; ein Pad mit einem anderen Wert gehört der Firmware und bleibt unberührt. Der Patch führt keine Liste und überlebt so, wenn ihm zwischendurch jemand ein Pad abnimmt oder zwei Tasks gleichzeitig laufen.
Ein Pad bekommt den Hinweis nur, wenn beide LEDs dunkel sind (oder schon seine Werte halten): ein gedrücktes Pad hat Rot 192 und bleibt so. Die Ausnahme ist das Pad des gewählten Parts: es darf Blau 255, Blau 0 oder
den Hinweis halten und folgt, solange das Hinweisfenster offen ist, der Regel "passt: Hinweis, sonst dunkel" (Bit 16 der Pad-Maske, `WINDOW`); danach bekommt es sein Blau 255 zurück.

## Haken und Platz

- **Drei Haken**, alle auf der ersten oder letzten Anweisung einer Funktion der Firmware, keiner verschluckt etwas (`swallow: false`):
  `0xC0044B3C` (Pad-Ereignis des KEYBOARD-Modus, Kette `pad-note`, Stufe `keyboard-pad`), `0xC008870C` (Licht eines Pads, Stufe `pad-light`) und `0xC00877D4` (das letzte `pop` des 40-ms-Takts des LED-Managers,
  Kette `led-tick-end`). Den Takt-Anfang `0xC0087740` belegt TAP Motion; die Haken ergänzen sich, weil meiner am Ende sitzt.
- **Code** bei `0xC0189000` (812 Byte von 2048 reserviert), **Zustand** bei `0xC0189F00` (64 Byte), beides im freien FF-Bereich hinter TAP Motion (`0xC0188000`, der Block von Blechy davor, `0xC0184000` bis `0xC0188000`). Zustand: `NA_SETTING` bei `+0` (nie geschrieben, FFFFFFFF, oder 1 heißt an, 0 aus),
  Takte seit dem letzten Pad-Drücken bei `+4` (FFFFFFFF zu Beginn, sättigt bei `0x1000`), Note bei `+8` und Pad bei `+0xC` (FFFFFFFF ist keine).
- **Startphase.** Der Takt des LED-Managers läuft ab etwa 140 ms. Der Haken und der Code sind in `startPhase` genannt; der Code sieht beim Start nur das Bedienfeld-Objekt, den Notschalter, die Karte, das Einstellungswort und den Pad-Modus an
  und schreibt nichts. Die beiden anderen Haken laufen nur bei einem Pad oder einer Note.
- **Beide Builds.** Dieselben Wörter an denselben Stellen in Hacktribes und in Korgs 2.02: der Patch ist `builds: ["hacktribe", "stock"]`, die gebaute Datei ist für beide Dateien dieselbe (`apply` auf beide geprüft). Gemessen: alle 20 Prüfungen bestehen auch mit Korgs eigener 2.02 und dem ganzen BLECH-Satz (Variante `stock`), mit demselben Flash-Dump.
- **Kein Flash, keine Karte.** Der Patch schreibt nichts in den Flash und nichts auf die Karte.
- **Die Seite NOTE ASSIST im Menü** (letzte Seite der Gruppe CUSTOMIZATION, jetzt 11 Seiten) schreibt das Wort `NA_SETTING`, wie `TM_SETTING` bei TAP MOTION: ON (Vorgabe) oder OFF, das Hauptrad wirkt sofort, WRITE legt OFF als **Bit 4** der Flags
  der Einstellungsdatei ab (Bit 0 Skripte, 1 MFX 2, 2 Patternwechsel aus, 3 TAP Motion aus, 4 Notenassistent aus); eine Datei ohne das Bit oder keine Datei heißt an. Der Zustand des Menüs liegt im Wort `+0xFC` des Menüzustands
  (das Wort hinter den acht Byte des Tab-Textes, dessen längster Text "Plugins" ist), das Wort des Patches ist als `shares` in der Plugin-Laufzeit eingetragen. Menüprüfungen: `menu:note_assist_*` in `tools/emu/menu_cases.py`.

## Prüfungen

`note_assist_cases.py`, acht Gruppen, alle im Emulator mit dem ganzen BLECH-Satz und dem eigenen Flash:

| Prüfung | Was sie belegt |
|---|---|
| `layout_is_the_key_and_scale` | sechs Tonarten und Tonleitern: alle 16 Pad-Noten sind Töne der Tonart und Tonleiter (Musiktheorie gegen die MIDI-Note der Firmware) |
| `fitting_pads_show_the_hint` | neun Läufe mit zwei oder einem Pad je Kombination: 0,2 s nach der Note sind die Pads mit Hinweis genau die, deren Note 0, 3, 4, 5, 7, 8 oder 9 Halbtöne von der gespielten entfernt ist (aus der MIDI-Note der Firmware gerechnet, nicht aus der Tabelle des Patches) |
| `other_pads_stay_dark` | alle übrigen Pads sind dunkel, auch das Pad des Parts (Hinweis oder dunkel, kein Blau mehr) |
| `hints_come_with_the_next_tick`, `hints_end_after_a_second_and_a_half`, `hints_stay_off` | der erste Hinweis steht höchstens 0,1 s nach dem Drücken, der letzte ist nach 1,4 bis 1,7 s weg (Soll 38 Takte zu 40 ms = 1,52 s), vier Sekunden später ist kein Hinweis da |
| `new_note_replaces_the_hints`, `new_note_restarts_the_time` | eine Sekunde nach der ersten Note steht der Hinweis noch; eine neue Note ersetzt ihn binnen 0,15 s durch den der neuen (das neue Pad zeigt das Rot der Firmware); die Zeit läuft ab der neuen Note, nicht ab der alten |
| `held_pad_keeps_the_firmwares_light` | ein gehaltenes Pad: Pad (192, 0) von der Firmware, Pad des Parts mit Hinweis, wenn seine Note passt, die anderen mit Hinweis; losgelassen bekommt das Pad den Hinweis, nach 1,5 s ist alles aus und das Pad des Parts hat sein Blau (0, 255) |
| `blue_of_the_part_is_a_pad_like_any_other`, `blue_of_the_part_comes_back` | Part 4 gewählt (Pad 3): nach einer Note, die zu seiner passt, zeigt sein Pad (21, 13), nach einer, die nicht passt, ist es dunkel; 1,8 s später ist in beiden Fällen das Blau (0, 255) zurück |
| `firmware_does_not_redraw_the_part_blue` | Patch aus (EXIT beim Einschalten): wird das Blau des Part-Pads über Tabellen und Sendefunktion des LED-Managers dunkel gesetzt, bleibt es vier Sekunden dunkel; die Firmware zeichnet es nicht neu, der Patch muss es zurückgeben |
| `part_change_leaves_no_stale_blue` | Part 4 auf 5 während die Hinweise stehen: Pad 3 ist danach dunkel, Pad 4 hat das Blau der Firmware, kein altes Blau bleibt stehen |
| `part_blue_comes_back_when_the_hints_end`, `part_blue_back_when_the_mode_changes` | nach dem Ende der Hinweise (Zeit) und nach einem Moduswechsel (SEQUENCER, TRIGGER, CHORD, STEP JUMP) trägt das Pad des Parts wieder sein Blau |
| `sequencer_light_wins` | Part 5 des Werks-Patterns spielt die Note 63 im Schritt 1; das Pad dieser Note ist vorher als Hinweis zu sehen, zeigt im Moment der Note das Licht der Firmware (192, 0) und danach, solange die 1,5 s laufen, wieder den Hinweis |
| `no_hint_in_other_pad_modes`, `hints_go_when_the_mode_changes`, `pads_in_other_modes_leave_nothing` | in SEQUENCER, TRIGGER, CHORD, STEP JUMP und PATTERN SET kein Hinweis, auch nicht beim Zurückwechseln; sichtbare Hinweise gehen binnen 0,1 s weg; Pads, die in den anderen Modi gedrückt werden, hinterlassen nichts |
| `no_hint_in_the_menu` | MENU: die Hinweise gehen, nach EXIT keine bis zur nächsten Note |
| `octave_shift_ends_the_hints` | BAR 4 (eine Oktave höher) beendet die Hinweise; die nächste Note bringt sie wieder |
| `stock_without_the_patch`, `setting_off_gives_the_leds_back`, `setting_on_again` | mit EXIT beim Einschalten, ohne Karte und mit dem Wort 0: die Pads nur mit 0, 192, 255, kein Hinweis, die Zustandswörter bleiben FFFFFFFF; das Wort zur Laufzeit auf 0 nimmt die Hinweise innerhalb von 0,3 s weg und eine neue Note zeigt keine; auf 1 geht es wieder |
| `firmware_pad_values` | die Werte der Firmware an den Pads (siehe oben); die beiden Werte des Patches sind nie darunter |
| `led_lock_keeps_the_pads` | hält ein Plugin die LED-Sperre (`Manager + 0xB98`), schreibt der Patch nichts; die Zeit läuft weiter, wird die Sperre innerhalb der 1,5 s gelöst, kommen die Hinweise |

**Kontrollprobe ohne den Haken `light_hook` (gemessen, einmal von Hand, nicht Teil von `check.py`):** Part 5 gewählt, ein Pad auf C angetippt, die Hinweise stehen (auch Pad 2 mit der Note 63), dann PLAY. Gemessen mit der ersten Fassung der Zeit (Hinweise erst nach 1,5 s); der Mechanismus ist derselbe, und `sequencer_light_wins` prüft ihn mit dem Haken.
Mit dem Haken zeigt Pad 2 im ersten Schritt (192, 0), das Licht der Firmware, und danach wieder den Hinweis. Ohne den Haken (das Wort `0xC008870C` auf dem Original) bleibt das Pad im Hinweis (21, 13), das Licht der Firmware
kommt nie, und beim Ende der Note setzt die Firmware das Rot auf 0 und die Hinweise flackern (rot 0, blau 13) bis zum nächsten Takt des LED-Managers. Der Haken ist also nötig und tut, was die Herleitung sagt.

## Grenzen und offen

- **Offen, am Gerät:** ob 21 und 13 zu schwach, zu stark oder zu bläulich sind (Zwischenwerte zeigt der Weg über den LED-Manager, 16.10.); ob das Blau des Parts nach dem Ende der Hinweise sichtbar zurückkommt, auch bei Moduswechsel und Part-Wechsel mitten in den 1,5 s; ob die Hinweise unter Last flackern; ob 1,5 s Hinweiszeit sich richtig anfühlt.
- Die Zeit läuft im 40-ms-Takt des LED-Managers; ist der Takt am Gerät langsamer oder unregelmäßig (er läuft in einem Task der Firmware), dauern die Hinweise entsprechend länger oder kürzer. Im Emulator gemessen: aus nach 1,5 s.
- Spielt ein Part im KEYBOARD-Modus Noten, flackern die Pads dieser Noten wie immer (das Licht der Firmware gewinnt); die Hinweise für die letzte Pad-Note laufen daneben ihre 1,5 s und enden dann.
- Der Hinweis hängt an einer Pad-Note, nicht am Touchpad; Noten des Touchpads (Touch Scale) sind keine Bezugsnote; Noten des Sequencers sind es seit 19.10.
- Der Hinweis auf das gespielte Pad selbst (Prim) erscheint nach dem Loslassen, solange die 1,5 s laufen; die Pads gleicher Note einer anderen Oktave gehören dazu.
- Die Intervalle liegen als Maske `CONSONANT` in `tools/patch/note_assist.py`; eine andere Auswahl heißt ein Zahlenwechsel und ein neuer Build.
