# Gate-Schweif: gehaltene Noten auf den Step-Pads (19.10.)

Wunsch vom 17.10.: wo eine Note wirklich anfängt, leuchtet der Step voll; dahinter zeigt ein Schweif in anderer Farbe, der
dunkler wird, wie weit die Note spielt. Gebaut und im Emulator geprüft (Hacktribe), am Gerät nicht. Nur auf den Sampler-Builds,
zusammen mit den Akkorden in Pink ([Poly-Pads](2026-10-19-poly-pads-pink.md)).

## Wie lang eine Note spielt (Emulator, MIDI-Ausgang, 120 BPM, ein Step 125 ms)

- Das Gate eines Steps geht von 0 bis 96, 96 ist ein ganzer Step: Gate 48 endet nach 70 ms, 72 nach 100 ms, 96 nach 130 ms.
- 127 ist TIE. Folgt ein eingeschalteter Step mit derselben Note, spielt sie durch: Note aus und wieder an fallen auf dieselbe
  Zeit, bis zum letzten Step der Kette, der mit seinem eigenen Gate endet. Mit einer anderen Note auf dem nächsten Step beginnt
  dort eine neue Note, auf einen leeren Step folgt nichts (die Note endet nach einem Step).
- Länger als ein Step wird eine Note also nur über TIE-Ketten. Genau die zeigt der Schweif.

## Was die Pads zeigen (`tools/patch/pad_colors.py`)

- SEQUENCER-Modus, der gewählte Part: ein Step, dessen Vorgänger eingeschaltet ist, TIE hat und dieselbe erste Note, ist Schweif.
  Er leuchtet in Pink (der Farbe, die neben PAD COLOR und SELECT COLOR übrig ist, wie die Akkorde) mit der halben Helligkeit, der
  zweite mit einem Viertel, ab dem dritten mit einem Achtel. Der Trigger bleibt, wie die Firmware ihn zeigt.
- Läuft der Cursor über einen Schweif-Step, zeigt das Pad die Überlagerung wie sonst auch.
- Die Firmware schickt beim Ändern eines Steps nur dessen Pad. Deshalb gehen bei jedem Pad, das sie schickt, die Pads dahinter
  noch einmal raus, wenn sich ihr Schweif geändert hat.
- Mit EXIT beim Einschalten zeigt die Firmware alles wie immer.

## Geprüft (`tools/emu/menu_cases.py`, `tie_cases`)

Steps 1 bis 5 eine gebundene Note: Trigger wie die Firmware, dann 127, 63, 31, 31 in Pink. Step 7 mit TIE auf eine andere Note:
zwei Trigger. Step 10 mit TIE auf einen leeren Step: kein Schweif. TIE nachträglich auf Step 12 gesetzt und das Pad zweimal
gedrückt: Step 13 zeigt den Schweif. EXIT beim Einschalten: alles rot wie in der Firmware.
