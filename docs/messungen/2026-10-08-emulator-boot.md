# Firmware im Emulator booten

Stand: 8. Oktober 2026. Sampler 2.02 mit Hacktribe, eigene `SYSTEM.VSB`,
eigene Flash-Dumps (0 bis 16 MiB) als Flash-Inhalt. Werkzeug:
`tools/emu/machine.py` (Unicorn 2.1.4, ARM926). **Offline** heißt: im
Emulator am Originalcode beobachtet. **Modellannahme** heißt: von uns
gesetztes Verhalten der Hardware. Nichts davon ist am Gerät geprüft.

## Ergebnis

Mit dem eigenen Flash bootet die Firmware bis zum Hauptbildschirm und
bleibt dort: Startbild, dann „160.0“, „001 Init Pattern“, „Part:01 OSC:“.
Ohne Flash-Dump startet sie aus einem leeren Flash, in dem nur die
Nutzerdaten-Kennung steht: Hauptbildschirm mit „120.0“, „001 Init Pattern“,
„OSC: SAW“, also leere Patterns und keine Samples (siehe „Ohne Dump
starten“).

Tempo (gemessen, macOS, ohne Analyse-Hooks): 12 s Gerätezeit in 18 s,
rund 135 Millionen Instruktionen pro Sekunde. Die erste Gerätesekunde
braucht rund 10 s, weil der Boot den DSP Byte für Byte über SPI lädt; danach
läuft er schneller als echt und wird im Dienst auf Gerätezeit gebremst. Die
Gerätezeit selbst ist geschätzt (5 ns je Instruktion).

## Chip und Startweg

- **Offline:** Die Assertion-Meldungen nennen Quelldateien wie
  `AM180xSpi.cpp`, `AM180xUSB.cpp`, `AM180xSystemConfiguration.cpp`,
  `AM180xMMSDCardController.cpp`. Der Prozessor ist ein TI AM180x; die
  Peripherieadressen passen zu dieser Familie.
- **Offline:** Reset-Vektor zeigt auf `0xC0000070`: SP setzen, Speicher-Init
  `0xC00296B0`. Assertion-Handler `0xC00298BC`, Argumente R1 Dateiname, R2
  Zeile; er endet in einer Endlosschleife `0xC00299F4`.
- **Modellannahme:** Die Seite ab `0xC0000000` ist auch bei Adresse 0
  sichtbar (die Firmware liest dort die Vektoren). Vermutlich richtet der
  Bootloader das ein.
- **Offline:** IRQ-Eintritt liest HIPIR2 (`0xFFFEE904`), Handlertabelle
  `0xC06A26A8`. Genutzte Interrupts: 16, 21 (Timer 0, Systemtakt),
  25 (UART0), 49, 53 (UART1), 58 (USB0), 68.

## Peripherie

| Teil | Anbindung | Stand |
|---|---|---|
| Display | SPI0, Befehl/Daten über GPIO 8.1; Befehle Page `0xB0+n`, Spalte `0x1n`/`0x0n`, 128 Datenbytes je Page | offline |
| Panel-Controller | UART0, Teiler 100 bei 13-fach-Abtastung: 115.200 Baud bei 150 MHz | hergeleitet |
| MIDI-Buchsen | UART1, Teiler 300 bei 16-fach-Abtastung: 31.250 Baud | hergeleitet |
| DSP | SPI1, Chip Select 1; beim Start rund 271.000 Byte, Blöcke mit `0xAD` | offline; Blackfin-Bootformat vermutet |
| DSP-Datenaustausch | Host-Port `0x60000000` (Daten), `0x60000002` (Steuerung) | offline |
| DSP-Handshake | GPIO 6.1 je Byte, Status `0x81` am Steuerport | Modellannahme |
| Flash | SPI1, Chip Select über GPIO 2.14 (aktiv low); Befehle `0x05`, `0x03`, `0x06`, `0x20`, `0x02`, `0x04` | offline |
| Ein/Aus-Taste | GPIO 7.15, aktiv low; gedrückt erscheint nach einem weißen Kasten „Power Off“ | offline |
| SD-Karte | MMC/SD0; Karte erkannt über GPIO 4.1 (aktiv low) | offline; Emulator meldet keine Karte |
| USB | CFGCHIP2 `0x4972` erzwingt Gerätemodus; der Chip meldet dann selbst eine Session | offline; kein Kabel modelliert |

Der SPI-Treiber liest überlappend: Er schreibt das nächste Byte, bevor er
das vorige abholt. Das Modell hält deshalb ein Byte im Schieberegister und
eins im Puffer, sonst kommt alles um ein Byte verschoben an.

## DSP-Briefkasten

- **Offline:** Der Host-Port überträgt nach sieben Steuerwörtern
  `[0xA9 lesen | 0xAB schreiben, Adresse low, Adresse high, Anzahl
  16-Bit-Wörter, 2, 0, 0]` die Datenwörter.
- **Offline:** Nachrichten an den DSP gehen nach `0xFF900A34`, Kopf `0x106`,
  dann Befehlsnummer (zum Beispiel `0x4c3b` nach der Pegelabfrage).
- **Offline:** Die CPU liest die Ausgänge des DSP bei `0xFF900018` und
  `0xFF900098` (Tabelle `0xC00A7F58`, je 16 Wörter, `0xC003DBC4`) und wartet,
  solange dort Bit 31 des ersten Langworts gesetzt ist.
- **Modellannahme:** Nicht modellierte DSP-Wörter lesen sich als 0. Damit
  wartet die CPU nicht.

## Eingangspegel und Stromversorgung

- **Offline:** Der Pegel des Audio-Eingangs kommt vom DSP: zwei Wörter ab
  `0xFF9030EC` (`0xC0013F74`, alle 40 ms). Das obere Wort ergibt 0 bis 5
  Balken unter den Schwellen 260, 2067, 4125, 8230, 16422 (`0xC00872F8`,
  Tabelle `0xC00A3648`); ein Wert über `0x5A7EF811` zeigt „CLIP“
  (`0xC001403C`, Anzeige `0xC00871E0`). Am Bild bestätigt: `0x0200`
  ein kurzer Balken, `0x4100` ein langer, `0x6000` CLIP.
- **Modellannahme:** Am Eingang steckt nichts, der Emulator meldet 0.
- **Offline:** „Power Off“ kommt von der Ein/Aus-Taste (GPIO 7.15), nicht
  von der Batterie. Woher die Firmware Batteriestand und Netzteil kennt, ist
  offen; das Batteriesymbol bleibt im Emulator gleich.

## Startentscheidungen

- **Offline:** Die Firmware fragt den Panel-Controller mit `80 00 00 00 00`
  nach seiner Version und erwartet `0x96` (`0xC0028940`, Sollwert in
  `0xC002CA38`). Andere Version oder keine Antwort: Panel-Update mit
  12 Schritten, Anzeige „00“. Das passt zum Debrick-Wiki von Hacktribe.
- **Offline:** Danach fragt sie gehaltene Tasten ab (`0x91`, Antworten
  `0x91` und `0x92`). Bestimmte Tastenmasken wählen besondere Startmodi
  (`0xC002882C`).
- **Offline:** Ab Flash `0x220000` steht ein Kopf `KORGele2sUSR`. Byte 4
  bis 11 müssen `elec2USR` oder `ele2sUSR` sein (`0xC0029D78`, Ergebnis
  `0x124`), sonst Startmodus 10: „SOFTWARE UPDATE / press ENTER“ und
  „Power Off“ zur Auswahl.

## Ohne Dump starten

- **Offline:** Die Firmware liest beim Start aus dem Flash die Kennung
  `0x220000` (16 Byte), `0x7FF000` (8 Byte, vier 16-Bit-Werte, vermutlich
  Touchpad-Kalibrierung), die Globals `0x230000` (0x100 Byte), die Patterns
  ab `0x240000` (0x3E8000 Byte) und später `0x7EF000` (8 Byte).
- **Offline:** Mit gelöschtem Flash und nur `KORGele2sUSR` plus vier
  Nullbytes bei `0x220000` bootet sie bis zum Hauptbildschirm. Globals,
  Patterns und Kalibrierung dürfen leer sein.
- **Offline:** `0x7EF000` ist eine 64-Bit-Kennung des Panel-Controllers
  (`0xC003B1E8`). Gilt sie als leer (0 oder alle Bits gesetzt), fragt die
  Firmware das Panel mit `0x90`, bekommt sie als `0xA0` (unteres Wort) und
  `0xA1` (oberes Wort) und schreibt sie in den Flash (`0xC0029FD0`).
  Antwortet das Panel nicht, bleibt das Display nach dem Startbild leer.
- **Modellannahme:** Der Emulator antwortet mit einer erfundenen Kennung.

## Panel-Nachrichten (5 Byte)

Vom Panel an die CPU, Typ in Byte 0 (`0xC002814C`, `0xC0028064`):
0 Taste, 1 Drehgeber, 2 Regler (16 Bit), 4 Pad, 5 XY-Pad, 6 ein Bytewert,
7 Ja/Nein, `0x80` Version, `0x91`/`0x92` gehaltene Tasten,
`0xA0`/`0xA1` die Panel-Kennung. Von der CPU ans Panel: `0x80`
Versionsabfrage, `0x91` Tastenabfrage, `0x90` Kennung abfragen, `0x84`, `0x85`/`0x86`
Kalibrierung; `00 nn hh` setzt LED `nn` auf Helligkeit `hh` (wie in
Freetribe).
Welche Nummer zu welchem Bedienelement gehört und was Typ 6 und 7 tun:
[Bedienfeld](2026-10-08-panel-bedienung.md).

## Offen

- Die DSP-Seite des Briefkastens: was die CPU erwartet, damit Abläufe mit
  DSP-Antwort weiterlaufen.
- Woher Batteriestand und Netzteil kommen.
- SD-Karte als Abbild aus dem eigenen Backup.
