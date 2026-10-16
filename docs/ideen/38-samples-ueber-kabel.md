# Idee 38: Samples übers Kabel rein und raus, ohne Karte umzustecken

Stand: beschlossen, Dateizugriff der Firmware im Emulator gemessen, am Gerät offen. Der Sample-Weg selbst ist nicht gebaut. Zurück zu den [Ideen](../ideen.md).

- **Rein:** eine WAV-Datei per SysEx in den RAM, ein kleines Programm schreibt sie über die Datei-Funktionen der Firmware auf die Karte, DATA UTILITY importiert sie.
- **Raus:** DATA UTILITY exportiert ein geladenes Sample als WAV auf die Karte, das Programm liest die Datei in den RAM, der Editor holt sie ab.

Erst im Emulator mit virtueller Karte, am Gerät nur mit frischer Kartensicherung. Baut auf den Ideen 4, 5 und 14 auf.

## Belege

- Recherche zur Karte, zur virtuellen SD-Karte und zu den Datei-Funktionen der Firmware: [Virtuelle SD-Karte](../hintergrund/virtuelle-sd.md).
- Im Emulator lesen und schreiben `f_open`, `f_read`, `f_write` und `f_close` über SysEx-Execute eine Datei auf der virtuellen Karte; der Test am Gerät ist vorbereitet, aber nicht gelaufen ([Karte am Gerät](../geraetetests/karte.md)).
