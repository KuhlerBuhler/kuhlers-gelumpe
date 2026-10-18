# CPU-Last und Laden der Samples (18.10.)

Grundlage für [Idee 56](../ideen/56-laden-und-strom.md). Werkzeug: `tools/emu/cpu_profile.py --vsb SYSTEM.VSB`
(Emulator, ohne Flash-Abbild, Karte mit einer `e2sSample.all` aus 20 Samples, zusammen 20 s Audio, 1.948.736 Byte).
Gezählt werden ausgeführte ARM-Befehle je 256-Byte-Seite Code; "beschäftigt" ist Befehle mal 5 ns (die Annahme des
Emulators) über die Gerätezeit, den Rest schläft die Firmware im Wait-for-Interrupt (`0xC0001808`).

## Ergebnisse

| Lauf | eigene Hacktribe-Datei | dieselbe mit BLECH |
|---|---|---|
| Laden: Befehle je Byte der Datei | 71,3 | 71,2 |
| Laden: beschäftigt | 18,3 % | 18,2 % |
| Hauptbildschirm, steht | 4,0 % | 4,1 % |
| Hauptbildschirm, spielt | 6,6 % | 6,7 % |

Die meisten Befehle beim Laden (Anteil an allen Befehlen der Ladezeit):

| Seiten | Anteil | Was dort liegt |
|---|---|---|
| `0xC0016300` bis `0xC0016800` | 26,1 % | Senden ans Display (`0xC00160C4`) und GPIO-Schreiben (`0xC0016BB4` in der Nähe), hergeleitet aus bekannten Adressen |
| `0xC0014800`, `0xC0015300` bis `0xC0015800` | 30,7 % | Zeichenroutinen (ein Pixel `0xC0015824`), hergeleitet |
| `0xC0018100` | 6,6 % | Kartendaten aus dem FIFO (`0xC00180F0`, 64 Byte je Aufruf), gemessen in [virtuelle SD](../hintergrund/virtuelle-sd.md) |

## Was das heißt und was nicht

- **Gemessen:** der ARM schläft schon fast immer; BLECH ändert daran nichts Messbares. Weniger CPU-Takt spart hier
  wenig, solange Licht, LEDs und DSP nicht gemessen sind.
- **Gemessen:** beim Laden geht über die Hälfte der ARM-Arbeit ins Display, nicht in die Karte.
- **Nicht aussagekräftig:** die Ladezeit selbst. Der Emulator meldet die Karte in einem festen Raster (ein Interrupt
  je 100 µs, `MMC_IRQ_NS` in `tools/emu/machine.py`), seine 3,8 s für 1,9 MB sind seine eigenen.
- **Hergeleitet:** der Kartentakt. Die Firmware setzt für den schnellen Modus Teiler 5 (`0xC00176D0`, `mov r3, #5`);
  bei 150 MHz Modultakt (wie Timer 3) sind das 12,5 MHz bei 4 Bit (ACMD6 mit 2). Für SD-Karten erlaubt sind 25 MHz.

Am Gerät offen: Ladezeit einer vollen Datei, Stromaufnahme je Verbraucher.
