# Echter DSP-Code im Simulator: Stand und Grenze

Stand 12. November 2026. Hacktribe 2.02. Versuch aus [Ton im Emulator](../ideen/52-ton-im-emulator.md): das DSP-Programm der
Firmware im Blackfin-Simulator aus gdb laufen lassen und mit dem Verkehr füttern, den der Emulator am Host-Port aufzeichnet, um echte
Ausgangspegel zu bekommen. **Ergebnis: Der Weg ist vorerst geparkt.** Init, Postfach und Audioschleife laufen, aber Noten bleiben
still, und wo der DSP Samples abspielt, ist nicht gefunden. Das [DSP-Modell](2026-11-12-dsp-modell.md) bleibt der Weg für Prüfungen.

Die Werkzeuge dazu (Aufzeichnung, Replay, Simulator-Erweiterungen) liegen nicht im Repo.

## Aufbau

| Befund | Marker |
|---|---|
| Simulator: gdb 15.2 (`gdb-15.2.tar.xz`, sha256 `83350ccd35b5b5a0cba6b334c41294ea968158c573940904f00b92f76345314d`), `sim/bfin` mit der `SIGNEXTEND`-Korrektur aus [Ton im Emulator](../ideen/52-ton-im-emulator.md), gebaut mit `make all-sim` | gebaut |
| Dazu im Simulator: Schreib- und Lesespur auf Adressbereiche (ohne Befehlsholen), PC-Spur mit P4/P5, ein Modell der Speicher-DMA (MDMA S0/D0, großes Deskriptorformat) | gebaut |
| Speicherbild: das DSP-Programm wie beim Boot über SPI1 geladen, Peripherie-Register als einfacher Speicher | gebaut |
| Init, Postfach-Handler `0xFFA04EC8` und die Frame-Funktion `0xFFA0141A` laufen; 1,5 s Audio aus dem aufgezeichneten Emulator-Verkehr in etwa 15 s Rechenzeit | gemessen |
| Der Replay ist offen: die CPU im Emulator sieht nicht, was der Simulator rechnet. Die CPU fragt `0xFF9031C8..0xFF9031E6` etwa 3000-mal in 1,5 s ab, der Emulator liefert dort 0; der DSP legt dort beim Init Zeiger ab | gemessen |

## Warum die Noten still bleiben

Ausgangs-Spitzenpegel `0xFF9030F4`/`F8` bleibt bei 1, mit einem eigenen Sample auf Part 1 (Slot 501) auf jedem vierten Schritt.

| Befund | Marker |
|---|---|
| Kommando `0x2D` (CPU `0xC009559C`, einmal je Oszillator und ms): Wellenform, ein Flag und der vorzeichenbehaftete Wert aus dem Part-Feld `+0x3E` (OSC EDIT oder Modulation). Kein Pegel, 0 ist normal | gelesen, gemessen |
| Noten-Kommandos auf der DSP-Seite: `0x1F` → `0xFFA050B0`, `0x2B` → `0xFFA051C0`, `0x2C` → `0xFFA05210`, `0x2D` → `0xFFA05268`, `0x2E` → `0xFFA05290`, `0x32` → `0xFFA053B6`, `0x36` → `0xFFA055F2` (Sprungtabelle `0x01F02B84`). `0x1F` und `0x32` gehen Paare (p, q) durch und rufen je Stimmentyp einen Setter (`0xFFA06670`, `0xFFA057B8`); `q = 0x1D4` zeigt auf den Generatorzustand `0xFF800750` | gelesen |
| Hacktribe-Samples haben Wellenform = Slot + 50. Über `0x31` wählt die CPU in `0xC0099F24` den Weg `0xC0095418`; die Vorlage mit Typ `0x22` (Daten `0xC00E6D94`, 18 Wörter) statt `0x21`, weil `0xC009989C` immer 0 liefert. Der Stummel ist in Korgs Original 2.02 rot gleich, kommt also nicht vom Patch | gelesen |
| Generator-Tabelle `0xFFB00010` (aus ROM `0x01F02478`): Typ `0x21` = `0xFFA02EDE`, Sample-Abspieler mit Schleife, wartet auf die MDMA; Typ `0x22` = `0xFFA0331E`, liest `[P4]`/`[P4 + 4]` | gelesen |
| `P4 = 0xFF802870`, jeden Frame aus dem SPORT-Empfangsring gefüllt (DMA3/DMA4, Deskriptoren ab `0xFF900E4C`). Typ `0x22` liest also den Codec-Eingang | gemessen (Simulator), gelesen |
| Die MDMA startet jeden Frame (`0xFFA0187E..0xFFA01890`) und kopiert nur zwischen `0x01C65xxx` und `0xFF8035xx`/`0xFF8036xx`, alles Nullen; hergeleitet: Verzögerungspuffer eines Effekts | gemessen (Simulator) |
| Die CPU schickt der Stimme die Startadresse im DSP-SDRAM (`0x00365EC0`, Wort 10) und `0xBB7A` (Wort 4). Die Sample-Daten liegen dort. Aber weder der DSP-Kern noch die MDMA liest Wort 9 bis 18 der Stimme oder den Bereich `0x360000..0x380000` | gemessen (Lesespur) |
| Die CPU speist kein Audio in den DSP: sie richtet weder McASP (`0x01D00000`) noch EDMA (`0x01C00000`) ein, auch nicht beim Start. Beim Spielen schreibt sie nur UART, Display-SPI, Timer, GPIO und Interrupt-Steuerung | gemessen (Emulator, alle Peripherie-Schreibzugriffe gezählt) |

## Offen

- Wo der DSP die Samples abspielt. Kandidaten: die Part-Schleife `0xFFA019DE`, oder die Typ-Setter von `0x1F`/`0x32` richten für Typ
  `0x22` etwas ein, das im Simulator fehlt.
- Ob der Stimmentyp `0x22` für Samples auch am Gerät gilt oder im Emulator anders gewählt wird. Am Gerät nicht geprüft.
- Kopplung Simulator und Emulator (die CPU sieht die Antworten des DSP): nicht gebaut.
