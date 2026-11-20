# Echter DSP-Code im Simulator: Stand und Grenze

Stand 12. November 2026. Hacktribe 2.02. Versuch aus [Ton im Emulator](../ideen/52-ton-im-emulator.md): das DSP-Programm der
Firmware im Blackfin-Simulator aus gdb laufen lassen und mit dem Verkehr füttern, den der Emulator am Host-Port aufzeichnet, um echte
Ausgangspegel zu bekommen. **Ergebnis: Der Weg ist vorerst geparkt.** Init, Postfach und Audioschleife laufen, aber Noten bleiben
still, und wo der DSP Samples abspielt, ist nicht gefunden. Das [DSP-Modell](2026-11-12-dsp-modell.md) bleibt der Weg für Prüfungen.

Aufzeichnung und Replay liegen in [tools/dsp/sim](../../tools/dsp/sim/README.md), die Simulator-Erweiterungen (Spuren, MDMA-Modell) liegen nicht im Repo.

## Aufbau

| Befund | Marker |
|---|---|
| Simulator: gdb 15.2 (`gdb-15.2.tar.xz`, sha256 `83350ccd35b5b5a0cba6b334c41294ea968158c573940904f00b92f76345314d`), `sim/bfin` mit der `SIGNEXTEND`-Korrektur aus [Ton im Emulator](../ideen/52-ton-im-emulator.md), gebaut mit `make all-sim` | gebaut |
| Dazu im Simulator: Schreib- und Lesespur auf Adressbereiche (ohne Befehlsholen), PC-Spur mit P4/P5, ein Modell der Speicher-DMA (MDMA S0/D0, großes Deskriptorformat) | gebaut |
| Speicherbild: das DSP-Programm wie beim Boot über SPI1 geladen, Peripherie-Register als einfacher Speicher | gebaut |
| Init, Postfach-Handler `0xFFA04EC8` und die Frame-Funktion `0xFFA0141A` laufen; 1,5 s Audio aus dem aufgezeichneten Emulator-Verkehr in etwa 15 s Rechenzeit | gemessen |
| In der Umgebung `operating` des Simulators stürzt er ab (auch mit einem leeren Programm), in `virtual` endet der DSP-Start mit einem Busfehler, weil der Bereich der Peripherie-Register fehlt. Es geht so: Peripherie-Register als Speicher, die Init-Funktionen aus einem eigenen Rahmenprogramm ohne Betriebssystem und Interrupts aufrufen, dann Postfach-Wörter einspeisen | gemessen |
| Der Replay ist offen: die CPU im Emulator sieht nicht, was der Simulator rechnet. Die CPU fragt `0xFF9031C8..0xFF9031E6` etwa 3000-mal in 1,5 s ab, der Emulator liefert dort 0; der DSP legt dort beim Init Zeiger ab | gemessen |

## Warum die Noten still bleiben

Ausgangs-Spitzenpegel `0xFF9030F4`/`F8` bleibt bei 1, mit einem eigenen Sample auf Part 1 (Slot 501) auf jedem vierten Schritt.

| Befund | Marker |
|---|---|
| Kommando `0x2D` (CPU `0xC009559C`, einmal je Oszillator und ms): Wellenform, ein Flag und der vorzeichenbehaftete Wert aus dem Part-Feld `+0x3E` (OSC EDIT oder Modulation). Kein Pegel, 0 ist normal | gelesen, gemessen |
| Noten-Kommandos auf der DSP-Seite: `0x1F` → `0xFFA050B0`, `0x2B` → `0xFFA051C0`, `0x2C` → `0xFFA05210`, `0x2D` → `0xFFA05268`, `0x2E` → `0xFFA05290`, `0x32` → `0xFFA053B6`, `0x36` → `0xFFA055F2` (Sprungtabelle `0x01F02B84`). `0x1F` und `0x32` gehen Paare (p, q) durch und rufen je Stimmentyp einen Setter (`0xFFA06670`, `0xFFA057B8`); `q = 0x1D4` zeigt auf den Generatorzustand `0xFF800750` | gelesen |
| Hacktribe-Samples haben Wellenform = Slot + 50. Über `0x31` wählt die CPU in `0xC0099F24` den Weg `0xC0095418`; die Vorlage mit Typ `0x22` (Daten `0xC00E6D94`, 18 Wörter) statt `0x21`, weil `0xC009989C` immer 0 liefert. Der Stummel ist in Korgs Original 2.02 rot gleich, kommt also nicht vom Patch | gelesen |
| Generator-Tabelle `0xFFB00010` (aus ROM `0x01F02478`), wie der Simulator sie zeigte: Typ `0x21` = `0xFFA02EDE`, Sample-Abspieler mit Schleife, wartet auf die MDMA; Typ `0x22` = `0xFFA0331E`, liest `[P4]`/`[P4 + 4]`. **Falsch, siehe [Korrektur](#korrektur-1611)** | gelesen |
| `P4 = 0xFF802870`, jeden Frame aus dem SPORT-Empfangsring gefüllt (DMA3/DMA4, Deskriptoren ab `0xFF900E4C`). Typ `0x22` liest also den Codec-Eingang. **Falsch, siehe [Korrektur](#korrektur-1611)** | gemessen (Simulator), gelesen |
| Die MDMA startet jeden Frame (`0xFFA0187E..0xFFA01890`) und kopiert nur zwischen `0x01C65xxx` und `0xFF8035xx`/`0xFF8036xx`, alles Nullen; hergeleitet: Verzögerungspuffer eines Effekts | gemessen (Simulator) |
| Die CPU schickt der Stimme die Startadresse im DSP-SDRAM (`0x00365EC0`, Wort 10) und `0xBB7A` (Wort 4). Die Sample-Daten liegen dort. Aber weder der DSP-Kern noch die MDMA liest Wort 9 bis 18 der Stimme oder den Bereich `0x360000..0x380000`. Das ist eine Folge des Simulatorfehlers, siehe [Korrektur](#korrektur-1611) | gemessen (Lesespur) |
| Die CPU speist kein Audio in den DSP: sie richtet weder McASP (`0x01D00000`) noch EDMA (`0x01C00000`) ein, auch nicht beim Start. Beim Spielen schreibt sie nur UART, Display-SPI, Timer, GPIO und Interrupt-Steuerung | gemessen (Emulator, alle Peripherie-Schreibzugriffe gezählt) |

## Offen

- Wo der DSP die Samples abspielt, und ob Typ `0x22` am Gerät gilt: beantwortet, siehe [Korrektur](#korrektur-1611).
- Kopplung Simulator und Emulator (die CPU sieht die Antworten des DSP): nicht gebaut.

## Korrektur 16.11.

Die Tabelle oben ist um einen Platz verschoben. Der DSP kopiert die Generator-Tabelle beim Start mit der Schleife
`R0 = [P0++] || [I1++] = R0`. Die Hardware speichert dabei das alte `R0`, der GNU-Simulator schrieb das Register des
Zeiger-Ladens sofort und speicherte den neuen Wert. So landete jeder Eintrag einen Platz daneben (gelesen, behoben im
Simulator auf dem Sample-Swap-Zweig; `tools/dsp/qemu-bfin.patch` macht es richtig).

| Befund | Marker |
|---|---|
| Typ `0x22` = `0xFFA02EDE`, der Sample-Abspieler. Eigene und Werks-Samples nutzen beide die Vorlage mit Typ `0x22` | gelesen |
| `0xFFA0331E` gehört zu einem anderen Typ, nicht zu den Samples. Die übrigen Adressen gehören je zum nächsthöheren Typ | hergeleitet |
| Damit erledigt: der Stimmentyp `0x22` gilt auch am Gerät (rot, 15.11.: Stimmenplatz 0 trägt nach einem Pad mit eigenem Sample Typ `0x22` in Wort 3); das Sample kommt nicht über den Codec-Eingang, dort bleibt der Pegel beim Spielen bei etwa -79 dBFS | gemessen (Gerät, Host-Port-Lesen) |
| Der DSP-Code bei `0xFFA0331E` und vier geprüfte Firmware-Bereiche sind am Gerät byteweise gleich mit dem Simulator | gemessen (Gerät) |
