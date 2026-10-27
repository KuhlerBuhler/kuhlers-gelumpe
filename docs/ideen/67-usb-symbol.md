# 67. USB-Symbol auf dem Display

Idee (26.10.): solange die Electribe per USB an einem Rechner hängt, zeigt der Hauptbildschirm ein kleines Symbol.

Stand 2026-10-27: **nur untersucht und aufgeschrieben, nichts gebaut, am Gerät nichts.** Marker: **gemessen**,
**hergeleitet**, **ungeprüft**.

## Befund

- Der USB-Baustein ist ein MUSB-Kern ab `0x01E00000`, Register ab +0x400 (FADDR `0x01E00400`, POWER `0x01E00401`,
  DEVCTL `0x01E00460`). Im Emulator nur als Stub (`tools/emu/machine.py`). (gemessen, Code gelesen)
- Die Firmware merkt sich die gesetzte Konfiguration im Byte `0xC033E4B2` (Objekt `0xC033E4A8`, +0xA): 0 nicht
  eingerichtet, 1 eingerichtet. Gleiche Adresse auf rot, blau und Hacktribe. (gemessen im Emulator)
  - Rot und Hacktribe: SET_CONFIGURATION `0xC0024244`, Getter `0xC00243D8`, Init löscht das Byte (`0xC002433C`).
  - Blau: SET_CONFIGURATION `0xC001FB6C`, Getter `0xC001FD00`, Init `0xC001FC04`, Reset `0xC001FC64`.
- Gelöscht wird das Byte nur beim Init, der Bus-Reset-Handler `0xC0020248` fasst es nicht an. Nach dem Abziehen bleibt es
  also vermutlich auf 1. (hergeleitet, ohne Rechner nicht prüfbar)
- Ausweich-Quellen: FADDR (nach Bus-Reset 0), DEVCTL (VBUS-Bits), oder CFGCHIP2 `0x01C14184` Bit 16, das der Werkstest
  "Unplug USB Cable" (`0xC00764EC`) liest. (ungeprüft)
- Im Hauptbildschirm gibt es heute kein USB-Symbol, die Bitmap-Tabelle `0xC00C1C2C` hat keins. (gemessen)

## Zeichnen

- Einsetzen wie der Ladebalken: am Sende-Hook `0xC008370C` in den Bildpuffer `0xC031B310` (`tools/patch/load_bar.py`).
  Etwa 60 ARM-Befehle plus ein 8x8-Bild. Freier Platz im Look-Bereich `0xC0183900` bis `0xC0184000`. (gemessen auf rot)
- Platz: links neben der Batterie, etwa x=104 bis 112, y=0 bis 7. Muss auf jedem Bildschirm geprüft werden, lange
  Seitentitel könnten heranreichen. (gemessen an einem roten Bild)
- Blau und Hacktribe: Sende-Hook und freier Platz noch nicht gemessen.

## Test

- Emulator: `0xC0024244` mit einem Setup-Paket aufrufen oder `0xC033E4B2` setzen, Bild mit und ohne Symbol vergleichen.
  Ein Kabel ist nicht nachgebildet.
- Am Gerät: Kabel rein (Symbol da), Kabel raus (Symbol weg), Rechner neu starten, Ruhezustand, wieder einstecken. Der
  Test mit dem Abziehen entscheidet, ob das Byte reicht oder FADDR/DEVCTL nötig sind.

## Aufwand

Klein bis mittel. Risiken: das Byte bleibt nach dem Abziehen stehen, Überschneidung mit langen Seitentiteln, Platz im
Look-Bereich.
