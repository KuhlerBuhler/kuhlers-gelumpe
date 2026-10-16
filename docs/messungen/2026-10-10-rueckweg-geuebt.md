# Rückweg geübt: eigene Firmware hin, Original zurück

Stand 2026-10-10 abends. Eigenes Gerät, Firmware über die SD-Karte und
DATA UTILITY → SOFTWARE UPDATE, am Netzteil. Am Gerät bedient und
beobachtet; Karte am Rechner kopiert und geprüft, Gerät per Laptop nur
gelesen. Das ist der zweite Schritt des Rückweg-Versuchs: den
Rückweg einmal durchspielen.

## Ausgangslage

- **Gemessen:** Das Gerät lief mit der Datei, die als
  `SYSTEM-ringtest.VSB` (SHA-256 beginnt `163d1d8d`) auf dem Rechner liegt:
  Menülängen und beide Effekt-Tabellen im RAM gleichen ihr, keiner anderen
  der acht vorhandenen VSB-Dateien.
- **Gemessen:** Auf der Karte lag sie unter `KORG/hacktribe/System/SYSTEM.VSB`.
  Unter `KORG/electribe sampler/System/SYSTEM.VSB` (Ort der Rettung bei der
  Startabfrage) liegt eine andere Datei, `755d025f…`; ob das eine passende
  Werksfirmware ist, ist offen.

## Hin

1. Testfirmware aus `SYSTEM-ringtest.VSB` gebaut, mit dem Patcher
   (`src/patch.mjs`, Startbild-Patch, nur die 1024 Byte bei `0xF9954`):
   `SYSTEM-startbild-test.VSB`, `c806690d…`.
2. Prüfung vor dem Export (`tools/emu/check.py`, mit eigenem Flash-Dump):
   18 von 18 bestanden.
3. Kartendatei gesichert (`SYSTEM-sd-vor-test.VSB`, `163d1d8d…`), Testdatei
   an ihre Stelle, Prüfsumme auf der Karte nachgelesen.
4. **Gemessen am Gerät:** Update über das Menü lief durch. Beim Einschalten
   (EXIT gehalten) zeigte das Gerät das Testbild (Rahmen, Diagonalen,
   Schachbrett) und startete normal.
5. **Gemessen am Gerät:** Das Startbild im RAM (`0xC00F9854`, 1024 Byte)
   gleicht dem der Testdatei (`5b0d33da…`), nicht dem der Ausgangsdatei.
6. **Gemessen am Gerät:** Beim Start gehalten `0x2000`, Bit 13, Startmodus 0
   (`screen_check.py --held`). EXIT ist Bit 13; die Notschalter-Taste stimmt.
   Auf diesen Datenpatch wirkt sie nicht, das Bild zeichnet Korgs Code vor
   der Tastenabfrage.

## Zurück

7. Gesicherte Datei zurück auf die Karte, Prüfsumme `163d1d8d…` auf der Karte
   nachgelesen.
8. **Gemessen am Gerät:** Update über das Menü lief durch, das Gerät startet
   wieder mit dem alten Startbild.

## Ergebnis

Hin und zurück über den normalen Updateweg haben funktioniert, mit einer
Firmware aus dem eigenen Patcher. Der zweite Schritt des Rückweg-Versuchs
ist damit erledigt. Offen bleibt der dritte (Rettung, wenn die laufende Firmware nicht
mehr startet) und ob die Datei unter `KORG/electribe sampler/System/` dafür
taugt.
