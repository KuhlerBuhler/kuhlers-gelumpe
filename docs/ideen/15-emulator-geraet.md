# Idee 15: Das Gerät im Emulator starten

Stand: gebaut, der DSP bleibt eine Attrappe. Zurück zu den [Ideen](../ideen.md).

Ziel ist die ARM-Seite der Electribe ohne Sound: die Firmware booten, das Display als Bild auslesen, Tasten, Regler und Pads einspeisen, LEDs zurücklesen. Damit lassen sich Abläufe ohne Gerät bauen und prüfen, und nach jedem Befehl ist zu sehen, ob das Display zeigt, was passieren sollte.

## Was steht

- Die Firmware bootet bis zum Hauptbildschirm, das Display kommt als Bild heraus ([Boot](../messungen/2026-10-08-emulator-boot.md)).
- Alle Bedienelemente und LEDs sind vermessen und auf der Seite bedienbar ([Bedienung](../messungen/2026-10-08-panel-bedienung.md)).
- SysEx geht über die emulierte DIN-MIDI an die Firmware ([SysEx über DIN](../messungen/2026-10-09-din-sysex.md)).
- Aufbau, Start und Bedienung des Emulators stehen in [Emulator](../emulator.md).

Der DSP (laut Freetribe ein Blackfin von Analog Devices) antwortet mit festen Werten. Was die Emulation damit nicht beweist: ob der echte DSP genauso antwortet und ob ein Helfer im RAM auf dem Gerät zuverlässig läuft. Ein echter DSP im Emulator ist Idee 52.

## Hardware-Wissen aus Freetribe

[Freetribe](https://github.com/bangcorrupt/freetribe) ist eine freie Firmware für die Electribe 2 (AGPL-3.0, Treiber auf Basis von TIs StarterWare). Die Angaben sind aus dem Quellcode gelesen und nicht an unserer Firmware geprüft:

| Teil | Anbindung laut Freetribe |
|---|---|
| Display | 128 × 64 Pixel, 8 Pages, SPI0 mit 30 MHz, Chip Select 1; Befehl oder Daten über GPIO 8.1, Reset GPIO 6.9 |
| Hintergrundlicht | RGB, je ein GPIO: 6.3 rot, 6.4 grün, 6.5 blau |
| Panel | eigener Mikrocontroller an UART0, 115200 Baud, Nachrichten zu 5 Byte: Tasten, Regler und Pads herein, LEDs hinaus |
| MIDI-Buchsen | serielles MIDI über einen UART (`dev_trs`) |
| DSP | über SPI |

Ob die Korg-Firmware die Hardware genauso anspricht, zeigt das Protokoll der Hardware-Zugriffe im Emulator, siehe [Boot](../messungen/2026-10-08-emulator-boot.md). Freetribe-Code kommt nicht in `tools/emu/`, weil der Emulator unter GPL-2.0-only steht; das Wissen über Register und Protokolle schon.
