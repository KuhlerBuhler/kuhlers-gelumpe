# 82. Vorschau: einen Part ins laufende Pattern holen

Wunsch (30.10.): in der Vorschau (`VIEW:` oder `NEXT:`) ein Pad im Modus PART MUTE drücken, und der Part fängt an zu spielen,
ohne dass das Pattern gewechselt wird. Stand 2026-11-02: **gebaut, im Emulator geprüft (Hacktribe, rot, blau), am Gerät nichts.**
Marker: **gemessen**, **hergeleitet**, **ungeprüft**.

## Entschieden (30.10.)

- Entstummen von Part N im angesehenen Pattern B kopiert Part N von B ins laufende Pattern A und ersetzt dort Part N, Klang und
  Steps. Er spielt sofort und ist nicht stumm.
- Kopiert wird mit der Firmware-eigenen Funktion Copy Part (Part Util 1/4), nicht mit eigenem Code. Sie nimmt auch die Motion des
  Parts mit.
- EXIT ohne Wechsel: der kopierte Part bleibt im laufenden Pattern bis zum nächsten Patternwechsel. Nichts geht in die Bank, auf die
  Karte oder ins Flash.
- Geändert nach dem ersten Test am Gerät (30.10.): der erste Druck auf ein Pad in der Vorschau holt den Part immer, egal ob er in B
  stumm ist oder nicht. Ein Part, der in B schon leuchtet, wird also nicht stumm geschaltet, sondern kopiert, und sein Pad bleibt an.
  Vorher schaltete dieser Druck den Part in der Ansicht stumm und das Pad ging aus, das war am Gerät falsch. Ist der Part in B stumm,
  holt ihn der erste Druck ebenso, er spielt nicht stumm (wie bisher). Stummschalten nur in der Ansicht gibt es damit nicht mehr.
- Ein zweiter Druck auf einen schon geholten Part schaltet ihn im laufenden Pattern stumm, ein dritter wieder an, wie ein Pad ohne
  Vorschau. Die Ansicht zeigt dabei dasselbe Mute.
- Beim Wechsel lädt B ganz normal, mit den Mutes, die auf den Pads standen.
- Dazu (30.10.): SHIFT + PART MUTE schaltet in der Vorschau um, wem die Pads gehören. Die Vorschau beginnt bei B wie oben. Nach
  SHIFT + PART MUTE zeigen und schalten die Pads die Mutes des laufenden Patterns A, wie ohne Vorschau, in den normalen Farben,
  nichts wird kopiert. Noch einmal SHIFT + PART MUTE: zurück zu B. Jede neue Vorschau beginnt bei B.
- Selbst festgelegt: das Rad innerhalb der Vorschau behält die Seite. Wer auf A die Mutes spielt und dabei weiterblättert, behält
  seine Pads. Endet die Vorschau (EXIT, Wechsel, Rad zurück auf das laufende Pattern), ist beim nächsten Mal wieder B dran.
- Die Mutes, die auf B gesetzt waren, bleiben für den Wechsel. Wie geholte Parts beim Umschalten bleiben, steht unter 02.11.
- SHIFT + PART MUTE hebt in der Firmware alle Mutes auf einmal auf (gemessen, [Tastenkombinationen](../tastenkombinationen.md)). In der
  Vorschau tut es das mit dem Patch nicht mehr, ohne Vorschau weiter wie immer.

## Entschieden (02.11.): die Pads blinken

- In der Vorschau blinken im Modus PART MUTE die Pads der Parts, die in B an sind. Man sieht so, welche Parts B mitbringt und
  welche schon geholt sind.
- Ein Druck holt den Part wie oben, sein Pad hört auf zu blinken und leuchtet. Der nächste Druck schaltet ihn aus.
- Parts, die in B stumm sind, bleiben dunkel, ein Druck holt sie, dann leuchtet das Pad.
- Takt wie MENU: 280 ms an, 280 ms aus. Blinkt MENU (`VIEW:`), blinken die Pads mit, bei `NEXT:` im selben Takt für sich.
- Im SEQUENCER und mit EXIT beim Einschalten blinkt nichts. Auf der Seite von A blinken nur die geholten Parts (unten).
- Gebaut, im Emulator geprüft (Hacktribe, rot, blau), am Gerät nichts. ([Messung](../messungen/2026-11-02-vorschau-pads-blinken.md))

## Entschieden (02.11.): geholte Parts beim Umschalten

Gemeldet: nach dem Holen ließ sich auf A der eigene Part nicht zurückholen, A spielte weiter den aus B. Und zurück auf B blinkte ein
schon geholter Part wieder, nach zweimal Umschalten sah man nicht mehr, was geholt war. Selbst festgelegt:

- Geholte Parts bleiben über SHIFT + PART MUTE gemerkt. Vergessen werden sie erst, wenn die Vorschau endet oder das Rad ein anderes
  Pattern zeigt.
- Auf der Seite von A blinken die Pads der geholten Parts, die an sind. Der erste Druck holt A seinen eigenen Part zurück, aus dem
  Bank-Block von A, ungemutet. Das Pad leuchtet dann fest, danach schalten die Drücke wie ohne Vorschau.
- Zurück auf B blinkt ein so zurückgegebener Part wieder, wie jeder Part, der in B an und nicht geholt ist. Ein Druck holt ihn neu.
- Ohne Druck hin und her: der Part bleibt geholt, sein Pad leuchtet fest, der Druck schaltet ihn aus.
- Gebaut, im Emulator geprüft (Hacktribe, blau), am Gerät nichts.

## Wie es geht

- Der erste Pad-Druck auf einen Part in der Ansicht geht weiter an die Firmware, gemerkt als "Kopie wartet".
- Dort, wo der Hauptbildschirm beim Pad das Mute setzt (UI-Task, `0xC0060D34`, blau `0xC00577A4`), ruft der Patch Copy Part
  (`0xC00667D4`, blau `0xC005C49C`) mit B und Part N, dann das Mute "an". (gemessen, [Messung](../messungen/2026-10-30-vorschau-part-reinholen.md))
- Copy Part nimmt die Quelle aus dem Pattern im RAM, wenn sie die gewählte Nummer ist. In der Ansicht ist das B, darum steht für den
  Aufruf die laufende Nummer dort. (gemessen)
- EXIT beim Einschalten: wie die Firmware, das Pad schaltet das Mute im laufenden Pattern. (gemessen)
- SHIFT + PART MUTE: der Patch hängt an der Stelle, an der die Funktion der Modustasten bei PART MUTE fragt, ob SHIFT gehalten ist
  (`0xC007042C`, blau `0xC0063480`). Mit Vorschau kippt er die Seite und lässt die Pad-LEDs je nach Seite das Pattern im RAM oder die
  Ansicht lesen, ohne Vorschau läuft die Firmware weiter. (gemessen, [Messung](../messungen/2026-10-30-vorschau-part-reinholen.md))

## Grenzen

- Die Kopie ersetzt Part N in A ganz, auch dessen Steps und Motion. Was dort live geändert war, ist weg, bis A neu geladen wird.
- Das laufende Pattern weicht danach von seiner Bank ab, die WRITE-Taste atmet. Wer jetzt WRITE drückt, speichert A mit dem
  geholten Part.
- Stereo-Paare: Copy Part behandelt sie selbst, nicht geprüft. (ungeprüft)
- Ist der Motion-Speicher voll, zeigt die Firmware ihr Fehlerfenster wie bei Copy Part. (hergeleitet, ungeprüft)
- Für die Dauer des Aufrufs steht in der gewählten Nummer die laufende. Der Haken am Sequenzende liest sie in der Ansicht nicht.
  (hergeleitet)
- Zurückholen auf A gibt den Part aus dem Bank-Block von A, nicht das, was vorher live an ihm geändert war. (hergeleitet: Copy Part
  liest den Bank-Block, wenn die Quelle nicht die gewählte Nummer ist)
- Blättert man mit dem Rad weiter, sind die geholten Parts vergessen, auf A blinkt dann nichts mehr und A behält die geholten Parts.

## Am Gerät noch zu prüfen

1. Pattern spielt, ein anderes am Rad ansehen, PART MUTE, ein Pad drücken (stumm oder leuchtend in B): spielt der Part sofort, mit
   dem Klang aus B, und bleibt das Pad an?
2. Hört man beim Kopieren einen Knacks oder eine Lücke, in diesem Part oder in anderen?
3. Zweiter Druck: stumm, dritter: wieder an.
4. EXIT: der Part bleibt. Danach MENU auf B: B lädt, mit den Mutes der Pads.
5. Mit Sync Group, mit einem Stereo-Sample, mit Motion im Quell-Part.
6. Blaue Electribe: dasselbe.
7. In der Vorschau SHIFT + PART MUTE: normale Farben, die Pads schalten A, nichts wird kopiert. Noch einmal: Vorschaufarbe, der erste
   Druck holt den Part. Rad weiter: die Seite bleibt. EXIT, neu ansehen: wieder B.
7a. Part auf B holen, SHIFT + PART MUTE: sein Pad blinkt. Druck: A spielt seinen eigenen Part wieder, das Pad leuchtet. Zurück auf B:
   das Pad blinkt wieder. Ohne Druck zweimal umschalten: das Pad leuchtet fest.
8. Ohne Vorschau hebt SHIFT + PART MUTE weiter alle Mutes auf.
9. Blinken: in der Vorschau blinken die Pads der Parts, die in B an sind, im Takt von MENU, auch nach MENU (`NEXT:`). Ein Druck: das
   Pad leuchtet fest, der Part spielt. Noch ein Druck: dunkel. Die Pads der in B stummen Parts bleiben dunkel bis zum Druck.
10. Blinken: flackert ein Pad kurz auf, wenn man ein anderes drückt? Wie sieht es mit eigenen Pad-Farben aus (nur die rote LED blinkt)?
11. Blinken: nach EXIT, nach dem Wechsel und mit SHIFT + PART MUTE leuchten alle Pads wieder normal, keins bleibt dunkel.
