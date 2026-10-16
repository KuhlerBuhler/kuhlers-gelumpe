# TAP Motion: der Patch, im Emulator geprüft

Stand 2026-10-15. Kein Gerätezugriff, alles im Emulator (Firmware 2.02 mit Hacktribe, eigene `SYSTEM.VSB`, eigener Flash-Dump), am Gerät ist nichts bestätigt.
Baut auf der [Recherche](2026-10-15-tap-motion.md) auf und setzt Idee 39 als Firmware-Patch um, nicht als Plugin
([Idee 39](../ideen/39-automationen-tap.md), [Idee 34](../ideen/34-tap-shortcut.md)). Die Prüfungen sind `tools/emu/tap_motion_cases.py`
(läuft in `tools/emu/check.py` mit, Namen in Klammern), der Patch ist `data/patches/tap-motion.json`, gebaut von `tools/patch/tap_motion.py`.
Marker: **gemessen**, **hergeleitet**, **offen** (am Gerät zu prüfen).

## Was der Patch tut

| Eingabe | Wirkung |
|---|---|
| REC mit Reglern oder Touchpad | wie immer: die Bewegung liegt im Pattern, eine Aufnahme je Part |
| TAP | schaltet die aufgenommene Bewegung des gewählten Parts, sofort, ab dem nächsten Schritt |
| MASTER FX gehalten, TAP | schaltet die Bewegung der Master-FX-Spuren (die Geste des Touchpads) |
| TAP-Lampe | an, wenn die Bewegung läuft, aus, wenn nicht; beim Part-Wechsel gleich nach; solange MASTER FX gehalten ist, der Zustand von Master FX |
| SHIFT + TAP | bleibt die Seite BPM der Firmware |
| Tap-Tempo | weg, solange der Patch an ist |
| Menü BLECH, CUSTOMIZATION, Seite TAP MOTION | ON (Vorgabe) oder OFF; OFF ist die Firmware ohne den Patch |

Aus, wie die Firmware es lässt, ist der Patch bei EXIT beim Einschalten, ohne Karte und mit TAP MOTION auf OFF (`stock_without_the_patch`,
`setting_off_gives_the_led_back`: vier TAP im Abstand von 0,65 s ergeben 92,3 BPM, die Lampe blinkt im Takt, das Byte bleibt).

## Messungen

**Sofort, nicht zum Takt (gemessen, `on_in_the_middle_of_the_bar`, `off_in_the_middle_of_the_bar`).** Aufgenommen ist ein Regler in den Schritten 16 bis 31.
TAP bei Schritt 24 schaltet ein: die Spur spielt ab Schritt 25 mit den aufgenommenen Werten. TAP bei Schritt 20 schaltet aus: die Spur spielt bis Schritt 20 und ist ab 21
still. Der Eingriff wirkt also ab dem nächsten Schritt (bei 160 BPM 93,75 ms), das Warten auf den Takt der Recherche entfällt. TAP vor dem
Fenster (Schritt 5) hält die Spur im Fenster still. Mit EXIT beim Einschalten ändert TAP nichts, die Spur spielt in beiden Läufen (`reference_firmware`).

**Der Schalter (gemessen, `byte_and_copy_follow`).** TAP ruft den Setter, den auch das Menü Part ruft (`0xC0049410`: Objekt `[0xC0348900]`, Part, Modus, 0 für ohne Meldung).
Er schreibt das Byte `Pattern + 0x807 + 0x330 * Part` und seine Kopie 0x382E weiter, ohne dass sich der Bildschirm ändert. Aus ist 0, an gibt den Modus zurück, den der Part hatte (`trigger_hold_comes_back`).
Der Patch merkt sich den Modus je Part im RAM (nicht im Pattern); ein Patternwechsel vergisst ihn (`pattern_change_forgets_the_remembered_mode`).

**Vorgabe, wenn nie eingeschaltet (gemessen, `never_on_is_smooth`, `reference_firmware`).** Ein neues Pattern hat das Byte 1 (Smooth), und eine Aufnahme ändert es nicht
(nach REC, PLAY, STOP ist es 1, auch die Kopie). Ist das Byte 0 und nichts gemerkt (der Nutzer hat im Menü Off gestellt), schaltet TAP auf 1. Trigger Hold (2) kommt nur
zurück, wenn der Part vorher mit diesem Modus lief.

**Jeder Part für sich (gemessen, `only_the_selected_part`, `led_follows_the_selected_part`).** Part 2 gewählt, TAP: Byte von Part 2 gleich 0, Part 1 bleibt 1. Die Lampe folgt dem Part
(an, an, nach TAP aus, zurück auf Part 1 an, Part 2 wieder aus).

**TAP-Lampe (gemessen, `led_is_the_state`, `reference_led_flashes`).** Die Firmware blinkt die Lampe im Takt (Paket `0014ff0000` und `0014000000` je Schlag). Der Patch nimmt den Blitz weg
(Haken auf der ersten Anweisung der Blitz-Funktion `0xC00881E0`) und setzt die Lampe im 40-ms-Takt des LED-Managers (Haken `0xC0087740`) über seinen eigenen Weg
(`0xC0087710`: Modus 1 steht an, 0 aus). Beim ersten Mal sendet er, was auch immer der Eintrag des Managers sagt: der steht beim Start schon auf 1, das Bedienfeld hat aber
von der Initialisierung "dunkel" bekommen (ohne diese Regel blieb die Lampe nach dem Start dunkel, obwohl das Byte 1 ist; so gefunden und behoben). Wird TAP MOTION im Menü auf OFF gestellt, gibt der Patch die Lampe zurück
und der Blitz der Firmware läuft wieder.

**Kein Tap-Tempo (gemessen, `tap_tempo_is_gone`).** Vier TAP im Abstand von 0,65 s: die Firmware stellt 92,3 BPM ein, mit dem Patch bleibt das Tempo bei 160,0, der Part-Zustand
ist nach vier Schlägen wieder wie vorher. Der Haken sitzt auf der Anweisung unmittelbar vor dem Aufruf der Tap-Tempo-Rechnung (`0xC0042CC0`), nachdem die Firmware
alle Bedingungen geprüft hat (Taste gedrückt, kein SHIFT, ein Bildschirm, auf dem TAP gilt). SHIFT + TAP kommt nicht bis dort und bleibt die Seite BPM
(`shift_tap_is_the_bpm_page`: Bildschirm 3, Bewegung und Lampe unverändert).

**REC bei ausgeschalteter Bewegung (gemessen, `rec_with_the_motion_off`).** TAP aus, REC, PLAY, Regler, STOP: die Spur hat 21 Bytes, das Byte bleibt 0, die Spur ist still, bis TAP
einschaltet, dann spielt sie mit den aufgenommenen Werten (16 von 16 Schritten). Das Byte stand schon in der Recherche (`gate-rec-with-mode-0`): die Firmware nimmt auch bei Off auf.

**WRITE und Patternwechsel (gemessen, `write_saves_the_state_at_write_time`, `unwritten_state_goes_with_the_pattern_change`, `mfx_byte_is_saved_with_the_pattern`).** WRITE sichert das Pattern mit dem Zustand, den die
Bytes im Moment des WRITE haben: TAP aus, WRITE, anderes Pattern, zurück: das Byte ist 0 und die Lampe aus; das andere Pattern zeigt sein eigenes Byte (1) und die Lampe an. Ein
Zustand ohne WRITE geht beim Patternwechsel verloren wie jede andere Änderung (TAP aus, weg, zurück: das Pattern kommt mit 1 wieder). Dasselbe gilt für das Master-FX-Byte.
Wer eine Bewegung "aus" im Pattern haben will, schreibt es also mit WRITE.

**App offen (gemessen, `app_owns_tap`).** Die Eingabe-Weiche der Plugin-Laufzeit (`input_mask_app`) hält jede Taste außer den Transporttasten von der Firmware zurück, solange eine App offen
ist: drei TAP gehen nur an die App, kein Schalten, kein Tempo. Dasselbe gilt für ein Plugin, das die Tasten fängt (Fangmaske 1). Ohne beides schalten drei TAP dreimal. Der Patch muss dafür nichts prüfen:
sein Haken liegt hinter der Weiche, im Tastenbehandler der Firmware, den eine zurückgehaltene Taste nie erreicht. Die Lampe zeigt auch bei offener App den Zustand (die App schaltet LED 0x14 über ihren eigenen
Weg; ein Plugin, das dieselbe Lampe nutzt, kann sich mit dem Patch überschneiden, **offen**, ob das am Gerät auffällt).

## Master FX: ein Schalter ist gefunden

Die Recherche ([Abschnitt 3](2026-10-15-tap-motion.md#3-motion-sequence)) fand keinen Schalter für die Master-FX-Spuren: das Part-Byte, der Part-Eintrag (`0x104`) und das Ziel (`0x11C`) wirken nicht.
Gefunden ist er im Pattern-Objekt bei **`+0x44`** (Dateioffset `0x40`, in der [Gerätekarte](../geraetekarte.md) noch ohne Feld).

| Byte `+0x44` | Wiedergabe der drei Spuren einer Geste (gemessen, `mfx_byte_switches_the_lanes`) |
|---|---|
| 1 (Vorgabe in einem neuen Pattern) | spielt, 16 verschiedene X-Werte in den Schritten 16 bis 31 |
| 0 | die Ausgänge der Spuren sind still (X `0xFFFFFFFF`), nichts spielt |
| 2 | spielt wie 1 |
| 1, aber das Part-Byte 0 | spielt wie 1 (das Part-Byte zählt hier nicht) |

Es ist damit ein eigener Modus für Master FX mit denselben Werten wie `part.motionMode` (0, 1, 2); ob 2 anders klingt als 1, ist wie bei den Parts **offen**.
Gesucht hatte ich den Weg über eine Marke in der Spurtabelle oder den Auslagerungspuffer (Spurdaten in einen RAM-Puffer und zurück): beides ist unnötig, ein Byte reicht und liegt im Pattern,
geht also mit WRITE.

- **Sofort (gemessen, `mfx_off_at_once`, `mfx_on_at_once`).** MASTER FX gehalten, TAP bei Schritt 20 einer laufenden Geste: die Spuren spielen bis Schritt 20 wie aufgenommen und stehen danach still. Die Ausgänge
  halten dabei den letzten Wert (bei den Parts werden sie still), die Wiedergabe schreibt nichts mehr. TAP bei Schritt 24 im nächsten Lauf: ab Schritt 25 spielen sie wieder wie aufgenommen.
- **Der Effekt geht aus (gemessen, `mfx_pad_let_go`).** Die dritte Spur ist der Schalter "MFX Pad An/Aus". Schaltet man mitten in der Geste aus, käme das Loslassen nie, der Effekt bliebe an. Der Patch lässt das Pad dann los
  (`0xC0057C28(0)`, sofern kein Finger auf dem Pad liegt): der Zustand steht ab dem Schritt des Eingriffs auf 0 und kommt beim Wiedereinschalten ab dem nächsten Schritt zurück.
- **Das Part-Byte bleibt unberührt, die Lampe zeigt Master FX nur bei gehaltener Taste (gemessen, `mfx_leaves_the_part_alone`, `mfx_led_while_held`).**
- **Aufnahme und Spielen von Hand bleiben (gemessen, `mfx_off_still_records_and_plays_live`).** Mit dem Byte auf 0 nimmt die Firmware eine Geste trotzdem auf (drei Spuren) und ein Griff ins Pad wirkt wie immer.

**Warum gehalten und nicht "Master FX ist der Pad-Modus" (Urteil, mit Messung).** Die Master-FX-Taste ist ein Schalter, und das Pad steht nach dem Start auf Master FX (Lampe `0x1C` an, gemessen). Hinge die
Wahl am Modus, wäre TAP in der Grundstellung für Master FX belegt und der Part nur zu schalten, nachdem man das Pad auf Touch Scale gestellt hat. Mit der gehaltenen Taste bleibt TAP der Part-Schalter, und Master FX
ist ein Griff mit zwei Fingern wie die anderen Tastenkombinationen am Gerät. Der Preis: MASTER FX stellt das Pad beim Drücken auf Master FX um, auch wenn nur TAP gemeint war; das bleibt nach dem Loslassen so (gemessen,
`touch-master-fx-latches`).

## Aufbau und Grenzen

- **Haken und Platz.** Drei Haken: `0xC0042CC0` (Kette `key-dispatch`, Stufe `tap-handler`), `0xC00881E0` (Blitz) und `0xC0087740` (Tick), beide in der neuen Kette `tap-led`. Der Code liegt bei `0xC0188000`
  (688 Byte von 2048 reserviert), der Zustand bei `0xC0188F00` (64 Byte), beides im freien FF-Bereich hinter dem Block von Blechy (`0xC0184000` bis `0xC0188000`). Die Plugin-Laufzeit ist voll und bleibt unberührt.
  Der Zustand des Patches (`TM_SETTING` bei `+0`) ist das Wort, das die Menüseite schreibt: nie geschrieben (FFFFFFFF) oder 1 ist an, 0 aus; es steht als `shares` im Patch der Laufzeit.
- **Startphase.** Der Blitz und der Tick laufen schon vor dem Hauptbildschirm (Blitz ab etwa 100 ms, Tick ab etwa 140 ms, hinter den Rettungswegen bei 57 bis 60 ms; die Zeiten stehen so im Patch, `check.py` prüft, dass sonst nichts in der Startphase liegt); der Patch nennt sie und den Code in `startPhase`,
  und prüft dort nur das Bedienfeld-Objekt, den Notschalter, die Karte und das Einstellungswort, bevor er an die Firmware zurückgibt. EXIT beim Einschalten lässt alles aus (`exit_held_is_stock`).
- **Kein Flash, keine Karte.** Der Patch schreibt nichts in den Flash und nichts auf die Karte; das Menü schreibt die Einstellung wie die anderen Seiten als Bit 3 der Flags in `KORG/blechtribe/`.
- **Menü.** Die Seite TAP MOTION ist die letzte der Gruppe CUSTOMIZATION (10 Seiten). Eine Datei ohne das Bit heißt ON, wie bei PATTERN CONFIRM; WRITE speichert OFF und lässt die anderen Bits und das Look-Wort stehen
  (`menu:tap_motion_*` in `tools/emu/menu_cases.py`).
- **Die Lampe ist die des Bytes.** Ein Part ohne aufgenommene Bewegung hat das Byte 1 und damit eine leuchtende Lampe; TAP schaltet sie aus, es ändert sich nichts Hörbares. So war die Entscheidung gemeint (Lampe an gleich Byte an),
  ein Zustand "Bewegung vorhanden" wird nicht unterschieden.
- **Gleichzeitige Eingriffe.** Wer beim Spielen einen Regler dreht, hält die Spur 5 bis 6 Schritte an (Recherche, Abschnitt 3); TAP ändert das nicht.
- **Offen, am Gerät.** Hörbarer Sprung beim Schalten, Verhalten des Parameters beim Abschalten (zurück auf den Reglerwert oder nicht), Smooth gegen Trigger Hold, 2 gegen 1 bei Master FX, Lampe und Taste unter Last, ob
  das Byte `+0x44` in Pattern von Korg selbst (Werks-Patterns) eine andere Vorgabe als 1 hat (hier nur in neuen Patterns gesehen).
