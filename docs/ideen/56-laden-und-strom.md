# 56. Schneller laden, weniger Strom

Status: recherchiert und im Emulator gemessen, am Gerät offen. Zurück zu den [Ideen](../ideen.md).

Wunsch: Samples beim Start schneller laden, Export und Import (`e2sSample.all`, `e2sPattern.all`) beschleunigen, im
Normalbetrieb weniger Strom brauchen. Messungen: [CPU-Last und Laden im Emulator](../messungen/2026-10-18-cpu-last-und-laden.md).

## Was wir wissen

| Aussage | Status |
|---|---|
| Die Firmware schläft im Leerlauf mit Wait-for-Interrupt (`0xC0001808`) | gelesen, im Emulator gemessen |
| ARM im Leerlauf rund 4 % beschäftigt, beim Abspielen 6,6 % | gemessen im Emulator (5 ns je Befehl angenommen) |
| Beim Laden von `e2sSample.all`: 71 ARM-Befehle je Byte, über die Hälfte im Zeichnen und Senden des Displays (`0xC0014800` bis `0xC0016900`), das Lesen der Karte selbst (`0xC00180F0`) 6,6 % | gemessen im Emulator |
| Die Karte läuft mit 4 Bit und Teiler 5: 150 MHz / 12 = 12,5 MHz; erlaubt sind 25 MHz (Teiler 2) | Register gelesen (`0xC00176D0`, `mov r3, #5`); Modultakt 150 MHz hergeleitet aus Timer 3 |
| Daten kommen per Interrupt alle 64 Byte, jeder Interrupt weckt eine Task, kein DMA | gemessen ([virtuelle SD](../hintergrund/virtuelle-sd.md)) |
| Beim Laden schickt die Firmware 176-mal ans Display (3,8 s Emulatorzeit, 1,9 MB) | gemessen im Emulator |
| Eine `e2sSample.all` mit 23 974 068 Byte lädt am Gerät in 14,87 s (Stoppuhr, ein Lauf), rund 1,6 MB/s; die Karte schafft bei 12,5 MHz mit 4 Bit theoretisch rund 6 MB/s | gemessen, ein Lauf |
| ARM-Arbeit aus dem Emulator ergibt rund 8,5 s der 14,87 s; der Rest ist Warten auf die Karte, den Weg in den DSP über den [Host-Port](../glossary.md#host-port) oder Pausen der Firmware | hergeleitet |
| Wie viel Strom Licht, LEDs, DSP und CPU am Gerät ziehen | **offen**: braucht ein Messgerät in der Stromzuleitung |
| Die Pad-LEDs kennen Helligkeitsstufen | am Gerät gesehen (Pulsieren) |
| Power Save der Firmware dimmt das Licht (2 von 18 Takten) und schaltet die untere LED-Leiste ab | gemessen ([Anpassung](../messungen/2026-10-14-blech-anpassung.md)) |

Der Emulator gibt der Karte ein festes Raster (ein Interrupt je 100 µs), seine Ladezeit sagt über das Gerät nichts.

## Optionen

| Option | Nutzen | Aufwand | Risiko |
|---|---|---|---|
| **Kartentakt 25 MHz** statt 12,5 (ein Befehl, `0xC00176D0`) | bis doppelte Datenrate, wenn die Karte der Engpass ist (offen) | klein: ein Patch-Wort | mittel: Leitungen und billige Karten bei 25 MHz ungeprüft, Lese- und Schreibfehler möglich; erst als Testdatei am Gerät |
| **Display beim Laden seltener zeichnen** | halbiert die ARM-Arbeit je Byte (gemessen), hilft nur, wenn die CPU der Engpass ist (offen) | mittel | klein |
| **DMA statt Interrupt je 64 Byte** | weniger Task-Wechsel, CPU frei | groß: Treiber der Firmware umbauen | hoch |
| **Pattern-Import: nur geänderte Flash-Sektoren schreiben** | schneller, schont den Flash | mittel | mittel: Flash-Schreibweg der Firmware |
| **Licht nach einer Zeit ohne Bedienung ganz aus** | offen, bis gemessen | mittel: Zeit seit der letzten Taste führen | klein |
| **CPU-Takt senken** | klein: der ARM schläft schon fast immer | groß | hoch: DSP und Audio hängen am selben PLL |

## Vorschlag

Messen, bevor gebaut wird:

1. Strom: ein Messgerät am Netzteil, mit Licht aus, LEDs aus, beides und LEDs voll.
2. Laden: während des Ladens Zeitstempel mitschreiben (freier Timer, ein kleiner Stub an der Kartenlesefunktion
   `0xC00180F0` und am Host-Port-Schreibweg), einmal mit Korgs Takt und einmal mit einer Testdatei mit 25 MHz. Das zeigt,
   ob Rechnen oder Warten die Zeit kostet.

Danach das bauen, was die Messung als groß zeigt.
