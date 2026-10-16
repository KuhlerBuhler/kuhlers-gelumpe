# Global-Dump

Gemessen 2026-09-16: `GLOBAL DATA DUMP REQUEST` (`0x0E`) liefert 256 Byte ab
`GLST`.

- Byte 41 trägt denselben Kanal wie Byte 4 der Antwort auf die Gerätesuche.
- Byte 42 (Receive Filter) stand auf Short, solange kein Controller ankam,
  und auf Off, als alle 14 Controller wirkten.
- Byte 40 (Clock Mode) meldete Internal, obwohl am Gerät External USB
  eingestellt war und die Clock den Sequencer zog. Der Dump gibt vermutlich
  den gespeicherten, nicht den laufenden Stand zurück.
