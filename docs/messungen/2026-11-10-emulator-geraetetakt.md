# Gerätetakt im Emulator: Cache und Multiply in der laufenden Zeit

Stand 10. November 2026. **Gemessen** im Emulator auf dem Mac, Hacktribe 2.02 (eigene Datei) mit und ohne BLECH-Satz.
Code: `tools/emu/devicetime.py` (`Pace`), `tools/emu/machine.py` (`device_rate`, `run_slice`), Test
`tools/emu/test_devicetime.py`. Markierungen: **gemessen**, **hergeleitet**, **Modellannahme**, **offen**. **Am Gerät nicht
neu gemessen**, die Zuschläge sind die vom 16.10. ([Emulator-Zeit gegen Gerätezeit](2026-10-16-emulator-timing.md)).

## Frage

Der Emulator rechnete jeden Befehl mit 5 ns. Am Gerät kosten ein Multiply und Lesen aus dem Speicher mehr, ein Durchlauf über
großen Speicher rund das Vierfache. Kann der Emulator diese Zuschläge beim Laufen anwenden, so dass Timer-Interrupts,
Bildschirm-Takte und die Echtzeit-Bremse die Gerätezeit sehen, ohne dass er merklich langsamer wird?

## Was ein Blick auf jeden Zugriff kostet

Boot von Hacktribe ohne BLECH bis 1,5 s Gerätezeit, je ein Lauf hintereinander, CPU-Sekunden:

| Variante | CPU | Aufrufe |
|---|---|---|
| flach, 5 ns je Befehl | 1,62 bis 1,95 s | |
| Block-Hook mit leerem Python-Callback | 6,61 s | 9,1 Mio. |
| Hook auf jedes Lesen mit leerem Python-Callback | 10,82 s | 14,1 Mio. |
| Stichprobe am Ende jeder Scheibe (`Pace`) | 1,64 s | |

- **Gemessen:** Ein Block-Hook macht den Emulator rund 3,4- bis 4-mal langsamer, ein Lese-Hook 5,5- bis 6,7-mal, noch ohne jede
  Rechnung im Callback. Ein Cache-Modell, das jeden Zugriff sieht, kommt deshalb nicht in Frage.
- **Gemessen:** Mit der Stichprobe: Boot bis 4 s mit BLECH 2,67 s flach gegen 2,75 und 2,77 s, also 1 bis 4 % mehr CPU, bei
  einer 1-Minuten-Last von 7 bis 8. Zwei Läufe mit Stichprobe sind bit-gleich.

## Wie das Modell rechnet

- Wo eine Scheibe nach ihren Befehlen aufhört, ist eine Stichprobe des Codes, der gerade läuft. Der Code dort wird einmal
  dekodiert: die ganze Schleife, wenn ein Rücksprung höchstens 1 KiB zurück sie umschließt, sonst bis zum Ende des Blocks
  (höchstens 64 Befehle). Sein Preis je Befehl gilt für die nächste Scheibe, die damit auch ihre Länge bis zum nächsten
  Ereignis rechnet.
- Preis je Befehl: 5 ns, dazu 6,7 ns je Multiply und je gelesenem Byte 0,5 ns (Cache trifft), 6,8 ns (Durchlauf, Cache
  verfehlt) oder 12,4 ns (ungecachter Alias `0xC4000000` bis `0xC7FFFFFF`), geteilt durch die Befehle des Stücks. Die Zahlen
  sind die gemessenen vom 16.10.
- Ein Ladezugriff zählt als Durchlauf, wenn sein Basisregister in der Schleife weiterläuft (zurückgeschrieben oder mit `add`
  oder `sub` auf sich selbst) und zwei Stichproben derselben Schleife höchstens 1 ms auseinander, in derselben Richtung, mehr
  als 16 KiB Abstand haben. Lesen über `pc` oder `sp` trifft immer. Lesen außerhalb des SDRAM kostet nichts extra.
- Keine Stichprobe nehmen: Scheiben im Interrupt-Handler, Scheiben, die in einem Warten, in einer Abfrage des Timers oder an
  einer der vom Modell übernommenen Routinen enden. **Gemessen:** Mit der Stichprobe am Anfang der Scheibe lag sie in der
  Hälfte der Fälle auf dem Interrupt-Vektor `0x18`; mit Handler-Scheiben endeten sie rund 1000-mal je Sekunde an denselben zwei
  Stellen des Handlers (`0xC009AF44`, `0xC0026BDC`) und gaben 8,6 und 10 ns je Befehl.

## Ergebnisse

| Befund | Marker |
|---|---|
| Die vier Schleifen der Messung vom 16.10. im Modell: alu 20,0, mul 26,7, memh 48,0 ns je Runde, mem über 2 MiB 141,6, memu über 2 MiB 233,4 (Gerät 20,15, 26,82, 47,88, 143,43, 234,1) | gemessen |
| mem über 256 KiB: 126,2 statt 143 ns je Runde, weil die erste Stichprobe eines Durchlaufs als Treffer zählt | gemessen |
| Boot mit BLECH bis 4 s: Befehle außerhalb des Wartens im Schnitt 5,43 ns je Befehl (flach 5,00); Hauptbild nach 400 ms wie flach | gemessen |
| Plugin-VM (`vm_bench.py --emu`): 5,7 bis 6,1 ns je Emulator-Befehl, lean 48,6 bis 58,8 ns je Operation, checked 82,8 bis 94,2 | gemessen |
| Plugin-VM am Gerät (13.10.): 7 bis 8 ns je Emulator-Befehl, lean 50 bis 70, checked 100 bis 115 ns je Operation | gemessen |
| Das Modell schließt bei der VM rund ein Drittel bis die Hälfte des Abstands zum Gerät, der Rest liegt in etwas, das es nicht kennt (indirekte Sprünge der Sprungtabelle, Schreiben, Befehls-Cache) | hergeleitet |
| `menu:wheel_*`, Stand vor dem Fix `7938605b`: SPLASH IMPORT Nachlauf flach 983 und 992 ms, mit Modell 1114 und 1114 ms | gemessen |
| `menu:wheel_*`, Stand mit dem Fix: SPLASH IMPORT flach 60 und 30 ms, mit Modell 60 und 40 ms; PLUGINS flach 30 und 30, mit Modell 40 und 70 ms; alle sechs Fälle grün (Grenze 150 ms) | gemessen |
| `pswitch:fast_steps_*`, Stand vor dem Fix `c2ba48fd`: flach 130 und 265 ms, mit Modell 136 und 266 ms; mit dem Fix beide 0 ms, grün | gemessen |
| Beide Nachläufe aus dem Gerätetest von 1.4.5 zeigte der Emulator schon flach: SPLASH IMPORT wartet auf die Karte, die Musterwahl auf die Leitung zum Panel. Ein Nachlauf, den es nur am Gerät gibt, ist damit nicht gezeigt | hergeleitet |
| Ein Schritt in SPLASH IMPORT kostet nach dem Fix 1,86 Mio. Befehle, flach 9,3 ms. Bei 15 ms zwischen zwei Schritten hält das Gerät mit, solange es weniger als das 1,6-Fache braucht; die VM lag am Gerät beim 1,33- bis 1,57-Fachen | hergeleitet |

## Modellannahmen

- Daten-Cache 16 KiB (Datenblatt des AM1808). Gemessen ist nur 4 KiB trifft, 256 KiB nicht.
- Zuschlag linear in den Bytes, auch für `ldrb` und `ldrh`; jedes Multiply kostet ihn, auch ohne abhängigen Befehl danach.
- Schreiben, Befehls-Cache, falsch vorhergesagte und indirekte Sprünge, Lesen von Peripherie und Thumb-Code: kein Zuschlag.
- Ein Handler läuft im Preis des Codes, den er unterbricht.
- Eine Stichprobe gilt für die ganze nächste Scheibe (bis 20 000 Befehle).

## Offen

- **Am Gerät**: ein echter Firmware-Pfad mit Zeitmessung gegen das Modell, zum Beispiel ein Schritt in SPLASH IMPORT oder
  IMPORT SAMPLE mit Timer 3 gemessen.
- Indirekte Sprünge und Schreiben am Gerät messen; beides fehlt der VM zum Gerätewert.
- Wo die Cache-Grenze zwischen 4 KiB und 256 KiB liegt.
