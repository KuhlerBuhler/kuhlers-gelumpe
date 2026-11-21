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

## DSP lesen per EXEC (14. und 15.11.)

Die Werkzeuge in `tools/device` (`dsp_peek.py`, `l1_dump.py`, `region_peek.py`) lesen den DSP über die Host-Port-Lesefunktion
der Firmware `0xC00141F8`, gestartet per EXEC. Die Funktion nimmt Sperre 1 und wartet ohne Zeitgrenze auf den Host-Port
(hergeleitet aus dem Code). Bleibt die Antwort aus, hängt jedes DSP-Kommando und damit das Gerät.

| Lesen | Ergebnis | Status |
|---|---|---|
| Bank A ab `0xFF800000` (`l1_dump.py`), Leerlauf | hängt bei den ersten Lesezugriffen, Aus/Ein nötig, Karte unberührt | gemessen |
| Bank B `0xFF904000` bis `0xFF908000`, Leerlauf | zweimal ohne Fehler | gemessen |
| L1-Scratchpad `0xFFB00010` | hängt, zweimal von zwei, auch auf einem stillen Gerät | gemessen |
| Code der Stimmenschleife `0xFFA0141A..0xFFA0157C` | hängt | gemessen |
| beliebige Adresse, während ein Sample klingt | hängt | gemessen |
| Code bei `0xFFA0331E` und `0xFFA04612`, Stimmen- und Part-Blöcke, stilles Gerät nach STOP und Ausklingen | ohne Fehler | gemessen |

Daraus: per EXEC nur auf einem stillen Gerät lesen, nur feste bekannte Blöcke (kein Abzug ganzer Bänke) und L1-Code außerhalb
der Stimmenschleife, nie das Scratchpad `0xFFB00000` oder Peripherie-Register (die DMA erreicht sie nicht, hergeleitet). Für
bekannte RAM-Adressen der CPU reicht BLECH READ (`0x61`) ohne EXEC.
