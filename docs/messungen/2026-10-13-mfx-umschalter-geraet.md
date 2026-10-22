# MFX 2 am Gerät: erster Code-Patch auf der echten Electribe

Stand 2026-10-13. Eigenes Gerät, Firmware: MFX-2-Variante der Testfirmware
(sha256 `5de4b584…`, MFX 2 auf TOUCH SCALE plus Blech-Startbild als Datenpatch), über
die SD-Karte und DATA UTILITY → SOFTWARE UPDATE eingespielt. Bedient und beobachtet wurde
am Gerät; vom Rechner aus wurde das Gerät nur gelesen.
Markierungen: **gemessen**, **hergeleitet**, **offen**.

## Ergebnis

- **Gemessen:** Das Update lief durch. Die Fingerabdrücke im RAM
  (`tools/device/led_inventory.py --identify`) gleichen der Datei: MFX-2-Haken an
  `0xC00700D8` `90bc9d50…`, Startbild `70323aae…`.
- **Gemessen:** Start mit gehaltenem EXIT: das Blech-Startbild erscheint (Datenpatch, wirkt
  vor der Tastenabfrage), das Gerät startet normal, TOUCH SCALE verhält sich wie im
  Original. Der Notschalter schaltet den Code-Patch ab.
- **Gemessen:** Normaler Start: MASTER FX gibt die eigene MFX des Patterns (Tape Delay),
  TOUCH SCALE schaltet auf MFX 2 (Looper). Damit läuft erstmals eigener Code aus dem
  Patcher am Gerät, eingehängt per Sprung und aus dem FF-Bereich ausgeführt.
- **Gemessen:** Beim Start steht der Touchpad-Modus auf Touch Scale (TOUCH SCALE leuchtet),
  wie im Original. Gewünscht ist MASTER FX als Startmodus.

- **Gemessen:** MFX 2 pro Pattern: TOUCH SCALE, Seite MFX TYPE, mit VALUE einen anderen
  Effekt gewählt, WRITE, WRITE. Nach einem Neustart gibt TOUCH SCALE auf diesem Pattern den
  gewählten Effekt, auf anderen Patterns weiter den Looper.
- **Gemessen:** Patternwechsel mit aktivem MFX 2: der Modus bleibt, das neue Pattern bekommt
  sein eigenes MFX 2.
- **Gemessen:** WRITE bei aktivem MFX 2: die eigene MFX des Patterns bleibt unverändert.
- **Gemessen** (nach Gehör): beim Hin- und Herschalten während des Spielens kein Knacken
  wahrgenommen.
