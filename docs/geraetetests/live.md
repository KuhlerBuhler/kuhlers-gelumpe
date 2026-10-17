# Gerätetest: Patternwechsel, Ladebalken, eigenes Startbild, TAP Motion, Notenassistent

Stand 2026-10-15. Für die Firmware mit dem BLECH-Satz, nachdem [blech-datei.md](blech-datei.md) durchgespielt ist.
Alles hier ist im Emulator gemessen ([Patternwechsel](../messungen/2026-10-15-patternwechsel.md),
[Ladebalken](../messungen/2026-10-15-ladebalken.md), [Startbild auf der Karte](../messungen/2026-10-15-startbild-karte.md)),
**am Gerät ist nichts davon bestätigt**. Du veränderst nichts an der Firmware, nur die Karte bekommt zwei Dateien
(der Startbild-Editor in den Flash-Sektor `0x7F0000`), und das nur, wenn du im Editor WRITE drückst.

**Notausgang:** EXIT beim Einschalten halten. Dann läuft die Firmware ohne alles davon (Patternwechsel, Ladebalken, Startbild
von der Karte), das Startbild ist das der VSB. Bleibt trotzdem etwas hängen, ist der Weg zurück derselbe wie in
[blech-datei.md](blech-datei.md): das Original-Update von der Karte.

## 1. Ladebalken

Karte mit einer `e2sSample.all` in `KORG/blechtribe/Sample/` (am besten mit vielen Samples, damit das Laden einige Sekunden dauert).

1. Einschalten, ohne etwas zu halten. **Erwartet:** das BLECH-Startbild bleibt stehen, solange geladen wird; der Strich unter BLECH
   füllt sich von links nach rechts, die Augen wandern, am linken und rechten Rand blenden kleine Gesichter kurz ein und aus; "Loading nnn%" erscheint nicht. Der Balken ist am Ende voll.
2. Die Startzeit mit der Stoppuhr gegen den Start mit EXIT gehalten vergleichen (dort fehlen auch die Plugins, wenn welche auf der Karte
   liegen: nimm eine Karte ohne `Plugin/`). **Erwartet:** gleich lang, höchstens ein paar Zehntel Sekunden Unterschied.
3. Ohne Karte einschalten. **Erwartet:** das Startbild wie bisher, kein Balken, normaler Start.
4. Mit EXIT gehalten einschalten. **Erwartet:** das Startbild der VSB, danach das Fenster "Loading nnn%" wie in der Firmware.

## 2. Eigenes Startbild ab dem ersten Bild

1. Global, Seite 20 SPLASH SCREEN, MENU, ein paar Pixel ändern, WRITE. **Erwartet:** das Fenster "Working" erscheint kurz, danach ist
   das geänderte Bild wieder da.
2. Neu starten. **Erwartet:** das geänderte Bild steht vom ersten Moment an, ohne weiße Phase davor.
3. Mit EXIT gehalten einschalten. **Erwartet:** das Startbild der VSB.

## 3. Patternwechsel mit Bestätigung

Ein Pattern spielen lassen (PLAY), am besten eins mit vier Takten.

1. Das Rad drehen. **Erwartet:** unten steht `VIEW:` mit der gewählten Nummer, das laufende Pattern spielt weiter, auch über mehrere
   Durchläufe. Ein angeschlossenes MIDI-Gerät bekommt dabei **kein** Program Change.
2. MENU drücken. **Erwartet:** unten steht `NEXT:`, jetzt geht Bank Select und Program Change raus, und das Pattern wechselt am nächsten
   Sequenzende (wie die Firmware es sonst tut).
3. Wieder drehen und EXIT drücken. **Erwartet:** die Anzeige springt auf das laufende Pattern zurück, es wechselt nichts.
4. Drehen, MENU, dann EXIT vor dem Sequenzende. **Erwartet:** die Bestätigung ist weg (ein Program Change für das laufende Pattern geht raus),
   es wechselt nichts.
5. Drehen, dann STOP. **Erwartet:** das Pattern bleibt das alte (die Firmware würde das gewählte anwenden).
6. Im Stillstand drehen. **Erwartet:** wie immer, das Pattern wird sofort geladen.
7. PATTERN SET und ein Pad während des Spielens. **Erwartet:** wie immer, das gewählte Pattern startet am Sequenzende.
8. Mit EXIT beim Einschalten: Drehen beim Spielen sendet wieder bei jedem Klick ein Program Change und merkt das Pattern vor (die Firmware ohne den Patch).

9. Menü BLECH, Gruppe FEATURES, Seite PATTERN CONFIRM ("Feature 2/4"): Hauptrad auf OFF, WRITE, aus- und einschalten, Pattern beim Spielen drehen. **Erwartet:** wie Punkt 8, die Firmware ohne den Patch (jeder Klick sendet ein Program Change). Wieder ON, WRITE, neu starten: Punkt 1 bis 7 gelten. Ohne Karte ist der Patternwechsel aus, was die Seite auch zeigt ([Patcher](../patcher.md), "Schalter, die das Menü ergänzen muss").

## 4. TAP Motion

Im Emulator gemessen ([Messung](../messungen/2026-10-15-tap-motion-patch.md)), am Gerät nichts davon bestätigt. Ein Pattern mit einem Part, Part 1 gewählt.
Der Patch ersetzt das Tap-Tempo der TAP-Taste; SHIFT + TAP (Seite BPM) bleibt.

1. REC, PLAY, einen Regler (zum Beispiel FILTER oder LEVEL) im Takt hin und her drehen, STOP. Danach PLAY. **Erwartet:** die Bewegung spielt wie immer
   (Motion Sequence Smooth ist die Vorgabe), die TAP-Lampe leuchtet dauernd und blinkt nicht mehr im Takt.
2. Beim Spielen TAP drücken. **Erwartet:** die Lampe geht aus, die Bewegung ist ab dem nächsten Schritt weg, nicht erst beim
   nächsten Takt. Noch einmal TAP: Lampe an, die Bewegung spielt sofort wieder. **Melde, was du hörst:** springt der Klang beim Aus- und Einschalten,
   geht der Regler beim Ausschalten auf den Wert der Hand zurück oder bleibt er, und ob Trigger Hold (Menü Part, Seite MOTION SEQ) anders klingt als Smooth (TAP merkt sich den Modus).
3. Part wechseln (Part-Tasten). **Erwartet:** die Lampe zeigt den Zustand des gewählten Parts, jeder Part hat sein eigenes Ein und Aus. Das Menü Part, MOTION SEQ zeigt dieselbe Einstellung (Off bei aus).
4. TAP aus, dann REC und noch einmal einen Regler aufnehmen. **Erwartet:** die Aufnahme klappt, TAP an spielt sie. WRITE sichert den Zustand, den das Byte beim WRITE hat; ohne WRITE kommt beim Patternwechsel der alte Zustand zurück.
5. Touchpad im Modus MASTER FX aufnehmen (REC, PLAY, Finger auf das Pad, STOP). Danach MASTER FX halten und TAP drücken. **Erwartet:** solange MASTER FX gehalten ist, zeigt die TAP-Lampe die Master-FX-Bewegung, TAP
   schaltet nur sie (der Effekt geht aus, wenn die Geste gerade lief), der Part bleibt unberührt. **Beachte:** MASTER FX stellt das Pad auf Master FX um, das bleibt nach dem Loslassen so.
6. SHIFT + TAP. **Erwartet:** Pattern-Menü auf der Seite BPM, wie immer, die Bewegung bleibt, wie sie ist.
7. Menü BLECH, Gruppe FEATURES, Seite TAP MOTION ("Feature 3/4"): Hauptrad auf OFF, WRITE, neu starten. **Erwartet:** TAP ist wieder das Tap-Tempo, die Lampe blinkt im Takt, nichts schaltet. Wieder ON, WRITE: Punkt 1 bis 6.
8. Ohne Karte oder mit EXIT beim Einschalten: wie Punkt 7, die Firmware ohne den Patch.
9. Eine App aus dem BLECH-Menü öffnen und TAP drücken. **Erwartet:** die App bekommt TAP, die Bewegung schaltet nicht.

## 5. Notenassistent

Im Emulator gemessen ([Messung](../messungen/2026-10-15-note-assistant.md)), am Gerät nichts davon bestätigt. Ein Pattern mit Tonart und Tonleiter, die du kennst (zum Beispiel C, Dorian),
Part 1 gewählt. Der Patch rührt nichts an, was du spielst; er schaltet nur LEDs der Pads.

1. KEYBOARD drücken, ein Pad antippen. **Erwartet:** sofort leuchten mehrere Pads rosa, nach etwa 1,5 s gehen sie wieder aus, die anderen bleiben dunkel. Das Pad des gewählten Parts ist solange wie jedes andere (rosa, wenn seine Note passt, sonst dunkel) und leuchtet danach wieder blau.
   Bei C Dorian und dem Pad der Note F (Pad 4) leuchten die Pads auf C, D, F, A, Bb und C, dunkel bleiben die auf Es und G (Sekunde und kleine Septime; das C auf Pad 1 ist das Part-Pad und zeigt in den 1,5 s ebenfalls rosa, danach wieder blau).
   **Melde, was du siehst:** ist es rosa (rot und blau zusammen) und sieht es deutlich schwächer aus als das gedrückte Pad und als das blaue Part-Pad? Ist es zu schwach, zu hell, zu bläulich oder zu rötlich?
   Dieser Punkt klärt, ob die Pad-LEDs Zwischenhelligkeiten haben: sind die Hinweise so hell wie ein gedrücktes Pad, kennt das Bedienfeld nur an und aus ([Messung](../messungen/2026-10-15-note-assistant.md), "Die Helligkeit der Pad-LEDs"). Die Werte (rot 21, blau 13 von 255) stehen in `tools/patch/note_assist.py`, ein Wechsel ist ein neuer Build.
2. Ein anderes Pad antippen. **Erwartet:** die Hinweise wechseln sofort auf die zur neuen Note (andere Pads) und gehen 1,5 s nach dieser Note aus. Bei gehaltenem Pad erscheinen sie auch; das gehaltene Pad bleibt rot, wie die Firmware es zeigt.
3. Key und Scale im Pattern-Menü ändern (zum Beispiel Major Penta in D). **Erwartet:** die Pads sind die Töne der neuen Tonleiter, die alten Hinweise sind weg, neue gibt es mit der nächsten Note.
4. BAR 4 oder BAR 1 (Oktave) drücken. **Erwartet:** die Hinweise gehen weg und kommen mit der nächsten Note wieder.
5. TRIGGER, SEQUENCER, CHORD oder STEP JUMP wählen, solange Hinweise da sind. **Erwartet:** sie gehen weg; in diesen Modi und mit MENU und in jedem anderen Bildschirm als dem Hauptbild erscheint nichts.
6. Ein Part, der selbst Noten spielt (PLAY): **Erwartet:** das Pad jeder Sequencer-Note leuchtet wie immer (das Licht der Firmware gewinnt); die Hinweise der letzten Pad-Note laufen daneben ihre 1,5 s und enden.
7. Menü BLECH, Gruppe FEATURES, Seite NOTE ASSIST (letzte, "Feature 4/4"): Hauptrad auf OFF, WRITE, neu starten. **Erwartet:** keine Hinweise mehr, die Pads wie in der Firmware. Wieder ON, WRITE: Punkt 1 bis 6. Mit EXIT beim Einschalten oder ohne Karte: wie OFF.

## Was du melden sollst

Pro Punkt: wie erwartet, oder was du statt dessen gesehen hast. Besonders: die Startzeit mit und ohne EXIT (Ladebalken), ob das Display beim Laden
irgendwann das Fenster "Loading" zeigt, ob WRITE im Editor am Gerät eine Datei anlegt, ob MENU im letzten Takt vor dem Sequenzende einen Wechsel verpasst. Bei TAP Motion: was du beim Ein- und Ausschalten hörst (Punkt 2), und ob die TAP-Lampe jedes Mal stimmt. Beim Notenassistenten: wie die Hinweise aussehen (Punkt 5.1), ob 1,5 s richtig ist, und ob sie je mit dem Licht der Firmware kollidieren.
