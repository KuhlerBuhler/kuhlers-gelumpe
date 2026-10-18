# Patternwechsel im Stand mit ungespeicherten Änderungen (18.10.)

Wunsch vom 18.10. ([Idee 57](../ideen/57-ungespeichert-warnen.md)): ist das Pattern bearbeitet und nicht gespeichert und
spielt nichts, soll das Rad nicht sofort wechseln, sondern wie beim Abspielen blättern: `VIEW:nnn` blinkt, MENU/ENTER
wechselt, EXIT bleibt.

**Neu (`tools/patch/pattern_switch.py`, alle drei Builds, nur wenn PATTERN CONFIRM an ist).**

- "Ungespeichert" heißt: das Pattern im RAM (`0xC033E6A4`, ab `+4`, 0x4000 Byte) unterscheidet sich von seinem Platz in
  der Bank (`0xC08B2940 + Nummer * 0x4000`, Synth `0xC0783D00`).
- Gestoppt und ungespeichert setzt das Rad die gewählte Nummer und das Vormerk-Flag (`+0x318`, `+0x341`) und meldet es
  der Anzeige wie `SET_NUMBER` beim Spielen (`0xC0070688`), lädt aber nichts. Zurück auf der Nummer im RAM endet das
  Blättern.
- **Der Abgleich im Stand:** `0xC0081E18` (Synth `0xC0072810`, Befehl für Befehl gleich gebaut) lädt im Stand laufend die
  gewählte Nummer, wenn sie nicht die laufende ist. Gemessen: ohne Haken war das Pattern 50 ms nach dem Drehen geladen
  (Schreiber der laufenden Nummer `0xC0079ACC`, gerufen von `0xC0081E54`). Ein neuer Haken (Kette `stopped-sync`) lässt
  die Funktion während des Blätterns nichts tun.
- MENU lädt die gewählte Nummer mit `SET_NUMBER` (mit MIDI). EXIT stellt die Nummer im RAM wieder als gewählt ein.
  STOP und PLAY beenden das Blättern ohne zu laden (der Neulade-Zweig von `SET_NUMBER` würde die Änderung verwerfen).
  Pad-Auswahl und MIDI Program Change wechseln weiter direkt.

**Gemessen (Emulator, `pswitch:unsaved_*`, Pascals Hacktribe mit BLECH, Flash-Abbild vom 09.10.).**

| Schritt | Ergebnis |
|---|---|
| Regler gedreht, zwei Klicks | laufend/gewählt/vorgemerkt `(0, 3, 1)`, die Änderung bleibt, kein MIDI, `VIEW:` gelesen |
| EXIT | `(0, 0, 0)`, die Änderung bleibt |
| zwei Klicks, MENU | `(2, 2, 0)`, geladen, Program Change 2 |
| ohne Änderung ein Klick | `(1, 1, 0)`, sofort geladen wie bei Korg |
| blättern, PLAY | spielt das bearbeitete Pattern 0, die Änderung bleibt |
| blättern, WRITE | die Firmware ignoriert WRITE, solange etwas vorgemerkt ist (Bildschirm bleibt 1); nach EXIT speichert WRITE die Änderung an ihren eigenen Platz, Platz 3 bleibt unberührt |
| PATTERN CONFIRM aus | ein Klick lädt sofort |

Keine falschen Treffer beim Erkennen: nach Start, Abspielen, Stoppen, Raddrehen ohne Änderung, Pad spielen und
TOUCH SCALE gleichen sich RAM und Bank. Nicht am Gerät geprüft.
