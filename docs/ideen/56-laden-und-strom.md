# 56. Schneller laden, weniger Strom

Wunsch vom 18.10.: Samples beim Start schneller laden, Export und Import (`e2sSample.all`, `e2sPattern.all`)
beschleunigen, im Normalbetrieb weniger Strom brauchen und den Energiesparmodus ausbauen.

Messungen: [CPU-Last und Laden im Emulator](../messungen/2026-10-18-cpu-last-und-laden.md).

## Was wir wissen

| Aussage | Status |
|---|---|
| Die Firmware schläft im Leerlauf mit Wait-for-Interrupt (`0xC0001808`) | gelesen, im Emulator gemessen |
| ARM im Leerlauf rund 4 % beschäftigt, beim Abspielen 6,6 % | gemessen im Emulator (5 ns je Befehl angenommen) |
| Beim Laden von `e2sSample.all`: 71 ARM-Befehle je Byte, über die Hälfte im Zeichnen und Senden des Displays (`0xC0014800` bis `0xC0016900`), das Lesen der Karte selbst (`0xC00180F0`) 6,6 % | gemessen im Emulator |
| Die Karte läuft mit 4 Bit und Teiler 5: 150 MHz / 12 = 12,5 MHz; erlaubt sind 25 MHz (Teiler 2) | Register gelesen (`0xC00176D0`, `mov r3, #5`); Modultakt 150 MHz hergeleitet aus Timer 3 |
| Daten kommen per Interrupt alle 64 Byte, jeder Interrupt weckt eine Task, kein DMA | gemessen ([virtuelle SD](../hintergrund/virtuelle-sd.md)) |
| Wie lange das Gerät für eine volle `e2sSample.all` braucht und wo die Zeit am Gerät hängt | **offen**: der Emulator gibt der Karte ein festes Raster (ein Interrupt je 100 µs), seine Ladezeit sagt über das Gerät nichts |
| Wie viel Strom Licht, LEDs, DSP und CPU am Gerät ziehen | **offen**: braucht ein Messgerät in der Stromzuleitung |
| Power Save der Firmware: dimmt das Licht (2 von 18 Takten) und schaltet die untere LED-Leiste ab | gemessen ([Anpassung](../messungen/2026-10-14-blech-anpassung.md)) |

## Optionen

| Option | Nutzen | Aufwand | Risiko |
|---|---|---|---|
| **Kartentakt 25 MHz** statt 12,5 (ein Befehl, `0xC00176D0`) | bis doppelte Datenrate der Karte, wenn die Karte der Engpass ist (offen) | klein: ein Patch-Wort, Haken, Doku | mittel: Leitungen auf der Platine und billige Karten bei 25 MHz ungeprüft, Lese- und Schreibfehler möglich; erst als Testdatei am Gerät |
| **Display beim Laden seltener zeichnen** | halbiert die ARM-Arbeit je Byte (gemessen), hilft nur, wenn die CPU der Engpass ist (offen) | mittel | klein |
| **DMA statt Interrupt je 64 Byte** | weniger Task-Wechsel, CPU frei | groß: Treiber der Firmware umbauen | hoch |
| **Pattern-Import: nur geänderte Flash-Sektoren schreiben** | schneller, wenn ein Satz größtenteils gleich ist; schont den Flash | mittel | mittel: Flash-Schreibweg der Firmware |
| **Energiesparen: Pad- und Tasten-LEDs dimmen** (Helligkeit je LED gibt es im LED-Manager, `+0x4E + 8 * LED`) | offen, bis gemessen | klein bis mittel | klein |
| **Licht nach einer Zeit ohne Bedienung ganz aus** (wie ein Bildschirmschoner) | offen, bis gemessen | mittel: eine Zeit seit der letzten Taste führen | klein |
| **CPU-Takt senken** | klein: der ARM schläft schon fast immer | groß | hoch: DSP und Audio hängen am selben PLL |

## Vorschlag

1. **Messen, bevor gebaut wird.** Strom: das Plugin Stromtest (Licht aus, LEDs aus, beides, LEDs voll) mit einem
   Messgerät am Netzteil. Laden: Stoppuhr vom Einschalten bis zum Hauptbildschirm mit einer `e2sSample.all` bekannter
   Größe, einmal mit Korgs Takt und einmal mit einer Testdatei mit 25 MHz.
2. Danach das bauen, was die Messung als groß zeigt.
