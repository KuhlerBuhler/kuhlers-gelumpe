# Startbild-Editor: malen und SHIFT (18.10.)

Wunsch vom Gerät (18.10.): ENTER/MENU gehalten soll dauerhaft zeichnen, SHIFT soll den Cursor hoch und runter
bewegen.

**Neu (`tools/patch/splash_editor.py`).**

- SHIFT gehalten (Taste `0x0A`, Wort `0xC06BCA70 + 8 * 0x0A` nicht 0): ein Schritt des Rads ist eine Zeile (128 Pixel),
  mit Umlauf über die 8192 Pixel wie bisher.
- MENU kippt das Pixel wie bisher und merkt sich die neue Farbe (`S_PAINT`, `STATE + 0x30`). Solange MENU gehalten ist
  (Taste `0x09`), geht der Cursor Schritt für Schritt und jedes Pixel, auf dem er landet, bekommt diese Farbe; ein
  schneller Dreh mit mehreren Schritten auf einmal lässt also keine Lücke.

**Gemessen (Emulator, `tools/emu/splash_cases.py run`, BLECH auf einer eigenen Hacktribe-Datei mit dem Flash-Abbild vom
09.10.).** SHIFT gehalten: zwei Schritte von Pixel 3 nach 259, drei zurück nach 8067 (Umlauf), einer vor nach 3, das
Bild unverändert. MENU gehalten, dann vier Schritte in einer Nachricht: die Bytes 3 bis 7 tragen die Farbe des Kippens
(0), Byte 8 bleibt, der Cursor steht nach einem weiteren Schritt ohne MENU auf 8, auf dem Display stehen die gemalten
Pixel, keine Assertion.

Nicht am Gerät geprüft. Offen: ob die Firmware SHIFT mit dem Rad auf der Global-Seite selbst noch anders nutzt; im
Emulator kam der Schritt unverändert im Slot an.
