# Hänger nach EXEC-Tastendrücken (rot, 15.11.)

Gerät: rote Electribe mit 1.4.6-Testfirmware, USB an einem Linux-Rechner, Werkzeug
`tools/device/remote_press.py`. Ursache offen.

| Befund | Status |
|---|---|
| Ein Prozess schickt 43 Tastendrücke per EXEC, ohne Fehler | gemessen |
| Ein Prozess schickt 30 Tastendrücke per EXEC mit je einem READ von 140 KB davor, ohne Fehler | gemessen |
| 25 Werkzeugstarts nur mit READ, ohne Fehler | gemessen |
| Der nächste Werkzeugstart nach einem Prozess, der EXEC benutzt und den Stub-Puffer `0xC1000000` zurückgeschrieben hat, bekommt keine Antwort, das Gerät hängt | gemessen |
| Linux `dmesg` danach: 19 Mal `rawmidi drain error (avail = 4090, buffer_size = 4096)` | gemessen |
| Einmal nach einem Neustart liefert ein READ von 4 Byte 16388 Byte, die SysEx-Grenzen gehen also verloren | gemessen |
| Der Stub ohne Warten im EXEC hängt genauso, Warten im EXEC ist nicht die Ursache | gemessen |
| Ohne die Blechy-Seite (nur BPM/SWING) hängt es genauso | gemessen |
| USB-Kabel neu stecken bringt eine tote SysEx-Leitung zurück, solange das Gerät selbst läuft; ein Hänger braucht Aus/Ein | gemessen |

Nächste Schritte, jeder kann einen Neustart kosten: mehrere Prozesse, die den Stub nur
nach `0xC1000000` schreiben und zurückschreiben, ohne EXEC; dann mehrere Prozesse mit
EXEC ohne Rückschreiben. Das trennt "Schreiben nach `0xC1000000`" von "EXEC". Vor einem
Update per USB nach solchen Tests das Kabel neu stecken und ein READ prüfen.
