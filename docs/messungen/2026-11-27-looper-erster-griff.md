# Looper: erster Griff nach dem MFX-Wechsel macht stumm (im Emulator nicht nachgestellt)

Gemeldet, alter Fehler der Werksfirmware (Korg 2.02 und Hacktribe): nach einem Wechsel des
Master-Effekts (zum Beispiel High Pass auf Looper) macht manchmal der erste Griff aufs Pad das
ganze Gerät stumm. Erst nach Loslassen und neuem Griff loopt der Looper. Nicht jedes Mal.

Diese Seite hält fest, was im Emulator mit echtem DSP-Code (QEMU-Worker, Hacktribe-VSB) und im
DSP-Code selbst gelesen wurde. **Ergebnis: im Emulator in keinem der geprüften Abläufe Stille.**
Die Ursache ist offen, einige Kandidaten sind ausgeschlossen. Ein Patch folgt daraus nicht.

## Belege

| Aussage | Marker | Beleg |
|---|---|---|
| Ohne MASTER FX-Modus (LED `0x1C` aus) erreicht ein Griff aufs Pad den Looper nicht: `+0x130` (Loop an) bleibt 0, über den Host-Port geht kein Parameter | gemessen (Emulator) | Zustand des Looper-Platzes und Host-Port-Mitschnitt beim Griff |
| Im MASTER FX-Modus schaltet der Griff den Looper an (`+0x130` = 1); Dry `0xFF903114` := 0, Wet `0xFF903118` := `0x7FFF0000`; Loslassen dreht beides zurück | gemessen (Emulator) | Mischerwörter alle 50 ms gelesen |
| Ablauf eines Typwechsels: 0x30 bei 21 ms (Dry voll, Wet 0), 0x31 bei 31 ms (Wet-Freigabe `0xFF903128` := 0), Lader fertig bei 50 ms (Freigabe wieder `0x7FFF0000`, neue Prozessfunktion in `0xFF90312C`) | gemessen (Emulator) | Wörter jede Millisekunde gelesen, High Pass Delay nach Looper und zurück |
| Ein Griff gleich beim Wechsel wirkt erst bei 50 ms, also nach dem Lader; während des Wechsels liest der ARM `0xFF803CF8` immer wieder | gemessen (Emulator) | Mischerwörter je Millisekunde, Host-Port-Mitschnitt (Lesebefehle `0xA9`) |
| Keine Stille (kein 10-ms-Block unter -60 dB) bei: Griff 0, 0,02, 0,05, 0,3 und 1,0 s nach dem Wechsel; Pad-Ecken; Finger über den Wechsel gehalten; MFX HOLD über den Wechsel eingerastet; Sequencer läuft, mit gehaltenem Finger und mit Griff 0,05 s nach dem Wechsel | gemessen (Emulator) | Eingang Audio In Mn, Sinus 1 kHz bei -12 dBFS; Ausgang beim Griff -23 bis -28 dB, tiefster Block -38 dB (Überblendung beim Griff 0 s nach dem Wechsel) |
| Looper-Zustand nach dem ersten Griff: Looplänge `+0x170` = `0x5DC0` (24000 Samples, 0,5 s), Ring `+0xF8` = `0xBB80` (48000 Samples, 1 s), erste Aufnahme `+0xD8` = `0xBB80` | gemessen (Emulator) | Platzzustand über `[0xFF903124]+4` gelesen |
| Schalter-Wandler `0x01C7BB68` (Parameter 0, loopswitch): aus setzt `+0x12C` = 0, `+0x128` = 1, `+0x138` = 1; an ruft `0x01F0E420` und `0x01C7BA76` (Looplänge), setzt `+0x12C`, `+0x128`, `+0x13C`, `+0x138` auf 1 und `+0x9C` = `0x180` | offline | DSP-Strom, eigener Disassembler auf libopcodes |
| Die Prozessfunktion `0xFFA07AF4` übernimmt den Schalter bei `0xFFA0805A`: mit `+0x164` = 0 nimmt der Looper ab der aktuellen Ringposition neu auf, sonst loopt er die letzten `+0x170` Samples des Rings | offline | wie oben |
| Ein Griff während des Ladens würde Dry auf 0 setzen, solange die Wet-Freigabe noch 0 ist: Stille bis der Lader fertig ist | hergeleitet | aus den Mischerwörtern; im Emulator nicht möglich, weil der Griff erst nach dem Lader ankommt (Zeile 4) |
| Ursache am Gerät | offen | nicht nachgestellt |

## Was ausgeschlossen ist (im Emulator)

- **Früher Griff in einen frisch geleerten Ring.** Der Lader nullt den Master-Speicher vor dem
  Init. Mit `+0x164` = 0 nimmt der Looper beim ersten Griff neu auf statt alten Ring abzuspielen,
  der Ausgang war in allen Läufen nicht still.
- **Griff während des Ladens.** Der ARM schickt den Griff erst nach dem Lader. Das Fenster, in
  dem Dry schon 0 und Wet noch gesperrt wäre, gab es nicht.
- **Finger oder MFX HOLD über den Wechsel.** Der Looper startet dann mit Schalter an direkt aus
  dem Laden (Startposition `+0xE0` = 1), klingt aber.
- **Pad-Position.** Die Looplänge blieb bei allen X/Y-Werten bei 0,5 s, der Pegel gleich.

## Grenzen dieser Messung

- Nur die Hacktribe-VSB lief. Der DSP-Code ist in Stock und Hacktribe byte-gleich, der ARM-Teil
  nicht.
- Eingang war ein Dauersinus. Ein Loop aus altem Material ist damit vom Live-Signal nicht zu
  unterscheiden, Stille aber schon.
- Wechsel nur über den Typ-Setter `0xC0048A64`, nicht über einen Patternwechsel und nicht über
  schnelles Drehen durch mehrere Typen im Menü.
- Der Sequencer lief mit leerem Pattern: wenig DSP-Last. Wie lange der Lader am Gerät unter
  voller Stimmenlast braucht, ist offen; nach Zeile 4 wartet der ARM aber ohnehin auf ihn.

## Nächster Schritt

Am Gerät nachstellen (braucht ein OK): Looper wählen, sofort greifen, und während der Stille
nur lesen: `0xFF903114`, `0xFF903118`, `0xFF903128` und `+0x130`, `+0x148`, `+0xDC`, `+0xE0`
des Platzes unter `[0xFF903124]+4`. Zeigt Dry 0 und Freigabe 0, ist es das Lade-Fenster; zeigt
die Freigabe `0x7FFF0000` und `+0x130` = 1, liegt es im Looper selbst.
