# Emulator-Tempo: Zeit je Gerätesekunde

Stand 2026-10-13. Alles im Emulator (`tools/emu/machine.py`, Unicorn 2.1.4, Python 3.14, MacBook mit 10 Kernen),
Firmware `SYSTEM.VSB`, Flash: eigener Dump vom 9.10. Kein Gerätezugriff. Markierungen: **gemessen**, **hergeleitet**, **offen**.
Die Karte für den Import ist ein FAT32-Abbild im Speicher mit einer eigenen `e2sSample.all` (22,5 MB, Kopie der Datei aus
dem Kartenordner, nur gelesen, nicht im Repository).

## Messung vorher und nachher

Verhältnis = Gerätezeit / CPU-Zeit des Prozesses (über 1,0 läuft schneller als das Gerät). Rechner war mit Lastmittel 4 bis 5
durch andere Läufe belegt, die Zahlen schwanken darum um etwa 15 %; vorher und nachher liefen hintereinander.

| Phase | vorher (40b3431) | nachher | Faktor |
|---|---|---|---|
| Boot, 8 s Gerätezeit | 1,58 | 4,08 | 2,6 |
| Hauptbild im Leerlauf | 2,32 | 4,76 | 2,1 |
| Muster spielt | 0,83 | 1,84 | 2,2 |
| IMPORT SAMPLE einer ganzen `.all` (22,5 MB) | 0,39 | 1,17 | 3,0 |
| derselbe Import im Dienst (`server.py`, ohne Echtzeit-Bremse) | 0,5 bis 0,7 | 1,3 bis 1,5 | rund 2,3 |

Der Import liest rund 1000 Sektoren je Gerätesekunde (gemessen, vorher und nachher gleich: 2037 gegen 2038 Sektoren in den
ersten 2 s). Die ganze Datei sind 44000 Sektoren, das sind rund 44 s Gerätezeit; vorher rund 112 s CPU-Zeit, jetzt rund 38 s.
Das Gerät braucht für dieselbe Gerätezeit; schneller als diese 44 s wird es nur, wenn die Firmware weniger rechnet.

## Ursache

- **Gemessen (Stichprobe mit `sample`, Mikro-Messung):** Die vier Code-Hooks mit Python-Rückruf (Assertion, Flash lesen,
  DSP laden, UART voll) liefen nicht nur an ihren Adressen. Sobald ein solcher Hook existiert und die Scheibenlänge über `count`
  begrenzt wird, ruft Unicorn für jeden Befehl den Hook-Verteiler und schaltet dabei den JIT-Schreibschutz um
  (`pthread_jit_write_protect_np`). Eine Schleife kostete mit den vier Hooks 24 ns je Befehl, mit `count` allein 1,9 ns,
  ohne beides 0,5 ns. Im Leerlauf gingen rund die Hälfte aller Abtastwerte dort hin.
- **Gemessen:** Die Firmware greift beim Karten-Import rund 450000-mal je Gerätesekunde auf Register zu (128 Wörter je Sektor aus
  dem Karten-FIFO, dazu rund 260 Zeitgeber-Lesezugriffe je Sektor in Warteschleifen). Jeder Zugriff lief durch drei Python-Frames
  von Unicorn und eine lange if-Kette.
- **Gemessen:** Der SD-Kartenteil selbst (Sektor lesen, FIFO) kostet fast nichts (0,3 µs je Wort); Spiegeln in den Kartenordner
  und die Bildschirm-Aufbereitung im Dienst liegen unter 2 % (Dienst und reine Maschine laufen gleich schnell).

## Behebung

1. Die vier Einsprungstellen sind jetzt Exit-Adressen (`ctl_set_exits`) statt Code-Hooks: der Lauf hält vor der Adresse,
   `Machine.service` erledigt das Modell und läuft weiter. Kostet zur Laufzeit nichts. Faktor rund 2 bis 2,5 überall.
2. Ein Python-Frame je Registerzugriff (eigener `mmio_map` über ctypes), Zeitgeber-Zähler per Tabelle, DSP-Port zuerst geprüft.
3. Prozessorregister in der Scheibenschleife direkt über die Bibliothek gelesen (`reg_read` kostet 1,7 µs).
4. Zeitgeber-Konfiguration und Perioden zwischengespeichert, Zählerlesen ohne Methodenaufrufe.

**Verhalten unverändert (gemessen):** Anzeige-Hash, Panel-Nachrichten (2839, 3988, 9314), Flash-Befehle, DSP-Ladungen und
Gerätezeit sind vor und nach den Änderungen gleich; nur der Befehlszähler `insns` weicht um 0,3 % ab, weil ein Lauf an einer
Exit-Adresse die Scheibe voll anrechnet (6 Fälle im Boot).

## Geprüft

- Python-Tests in `tools/emu`: 99 von 99 (mit `E2_VSB`, `E2_FLASH`), darunter `test_timer.py`: 1000 Timer-Interrupts je
  Sekunde und 25 Bildschirm-Takte je Sekunde innerhalb 1 %.
- `splash_cases.py run`: 36 von 36. `mfx_cases.py run`: 55 von 55 (308 s CPU). `check.py`: Startbild-Editor 30 von 30,
  MFX 2 28 von 28 (je rund 60 s CPU, vorher 63 bis 70 s).
- `npm run test:emu`: 25 von 25, Kartenablauf in 100 s statt 120 s.
- `splash_cases.py` rief `uc.emu_start` mit `until` auf; mit gesetzten Exit-Adressen gilt `until` nicht, der Aufruf läuft
  jetzt über die Exit-Liste. Ein neuer Code-Hook (`Dev.call`) braucht außerdem `ctl_flush_tb`, sonst feuert er nicht.

## Versuch, der nicht trägt

- **Gemessen, verworfen:** Im Interrupt-Handler nur dann in 256-Befehl-Scheiben laufen, wenn ein anderer Interrupt wartet
  (statt immer). Das hätte rund 50 % der Scheiben gespart, aber die Firmware bleibt dann beim Boot hängen (26 Mio. Befehle,
  108 Panel-Nachrichten). `ISR_STEP = 256` ist also Teil des Modells.

## Grenze

- **Hergeleitet:** Die CPU-Emulation ist ein Thread. Rund 50 % der Zeit im Import sind Python-Rückrufe auf Register
  (rund 450000 je Gerätesekunde), rund 35 % ist Unicorn selbst (davon etwa ein Siebtel der Zähl-Hook, der für die Scheibenlänge
  nötig ist), der Rest ist die Scheibenschleife. Host-Arbeit (Spiegeln, Bildschirm, JSON) liegt unter 2 % und
  brächte auf einem zweiten Kern nichts.
- **Offen:** Rund 260 der 475 Zugriffe je Sektor sind Zeitgeber-Lesezugriffe in Warteschleifen der Firmware (200 ns Gerätezeit
  je Lesen). Größere Schritte bei langen Lese-Reihen würden etwa ein Viertel sparen, ändern aber das Zeitmodell und sind nicht
  gemacht. Mehr als etwa Faktor 1,5 über Echtzeit im Import ist ohne diese Modelländerung nicht zu erwarten.
