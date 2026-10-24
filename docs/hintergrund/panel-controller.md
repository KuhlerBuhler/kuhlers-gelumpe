# Panel-Controller: eigener Mikrocontroller hinter Tasten, Reglern und LEDs

Stand 2026-10-24. Nur offline: VSB gelesen, Panel-Firmware disassembliert, Panel-Update im Emulator
gegen ein nachgebautes Boot-ROM gefahren. Am Gerät nichts. Marker: **gemessen** (im Emulator oder
an den Bytes der VSB), **hergeleitet** (aus gelesenem Code, nicht laufen gesehen), **offen**.
Keine Bytes, keine Listings von Korg im Repo; `tools/emu/panel_mcu.py` liest alles aus der eigenen VSB.

Das Bedienfeld ist ein eigener Rechner an UART0 (5-Byte-Nachrichten, siehe
[Panel-Bedienung](../messungen/2026-10-08-panel-bedienung.md)). Seine Firmware steckt in jeder
`SYSTEM.VSB`, und die ARM-Firmware schreibt sie neu, wenn das Panel nicht `0x96` meldet.

## Belegtabelle

| Aussage | Status | Beleg |
|---|---|---|
| Panel-Abbild in der VSB: Hacktribe und Stock ab VSB `0xC6138` (RAM `0xC00C6038`), `0x9700` Byte; Synth ab VSB `0xB0B10` | gemessen | `panel_mcu.py --vsb X.VSB` |
| RAM-Lader dazu, `0x400` Byte, direkt hinter seinem Längenwort (Hacktribe VSB `0xCF864`) | gemessen | `panel_mcu.py` |
| Abbild und Lader sind in Stock, Hacktribe und Synth gleich (SHA-256 `f3ba3b25…`, Lader `9fe8a5cb…`) | gemessen | `panel_mcu.py` je VSB |
| CPU ist ein ARM Cortex-M3: Vektortabelle mit Stack `0x20004000`, Reset `0x60DD` (Thumb), Thumb-2-Code | gemessen | `panel_mcu.py`, `objdump -M force-thumb` |
| Familie Fujitsu/Spansion FM3 (heute Infineon): Watchdog-Schlüssel `0x1ACCE551` an `0x40011C00`, Takt `0x40010000`, GPIO `0x40033000`, Base Timer `0x40025000`, zwei ADC `0x40027000`/`0x40027100`, UART (MFS) `0x40038000`, SRAM `0x1FFFC000` bis `0x20003FFF` | hergeleitet | Panel-Code im Unicorn bis zur Hauptschleife, Registerzugriffe mitgeschrieben |
| Genaues Bauteil, Flashgröße | offen | |
| Version `0x96` steht fest im Panel-Code (Antwort auf `0x80`) | hergeleitet | Panel-Code `0x2E1C` |
| Panel-Takt 40 MHz: UART-Teiler 346 ergibt 115200 Baud nur bei 40 MHz | hergeleitet | Schreibzugriff `0x4003800C = 0x15A` |
| Update läuft in 12 Zuständen, Ablauf siehe unten, gegen das Boot-ROM-Modell vollständig bis „Please Reboot“ | gemessen | `panel_mcu.py --simulate` |
| Fehler beim Zurücklesen: „Error / Unknown Error.“, kein Reset des Panels | gemessen (Anzeige), hergeleitet (Reset) | `panel_mcu.py --simulate --corrupt 3`, `0xC0036DD8` |
| Das Zurücklesen prüft nur 150 der 151 Seiten | gemessen | `--simulate`: nach Seite 150 kein `0xC8` mehr |
| Ohne gültige Antwort auf `0x80` (Wert 0) zeigt das Gerät „Working…“ und startet das Update nach rund 8,7 s | gemessen | Emulator, `panel_version = 0` |
| Ohne Antwort des Panels wartet der Update-Schritt unbegrenzt und zeigt „00“ | gemessen | Emulator 60 s, Version `0x95`, keine Boot-ROM-Antwort |
| ADC-Werte nimmt das Panel als 10 Bit (Bits 11..2 des 12-Bit-Ergebnisses) | hergeleitet | Panel-Code `0x3D98` |
| Regler gehen als 0..255 ans ARM, nicht 0..1023 | hergeleitet | Panel-Code `0x309C`, `0x3180` |
| Touchpad geht als 0..1023 ans ARM, im Normalbetrieb auf Achterschritte gerundet | hergeleitet | Panel-Code `0x3780`, `0x4044` |
| ARM teilt Touchpad durch 8 (`asr #3`) | hergeleitet | `0xC00458D8`, `0xC00458E4` |
| Kalibrierung aus Flash `0x7FF000` geht als `85`/`86` ans Panel und wird dort angewandt | gemessen (Nachrichten), hergeleitet (Rechnung) | Emulator-Mitschnitt: `85 00 69 03 72`, `86 00 9c 03 2f`; Panel-Code `0x3EEC` |
| Jede LED, auch die Pads, bekommt im Panel einen PWM-Wert aus dem Byte 0..255 | hergeleitet | Panel-Code `0x4EBC`, Matrix `0x8460` |
| Pad-LEDs dimmen am Gerät | offen | nicht am Gerät geprüft |
| Abtastrate je Regler, Pad, Touchpad | offen | nur der Grundtakt ist bekannt |

## Wo das Abbild liegt

Hacktribe (Stock gleich):

| Teil | VSB-Offset | RAM | Größe |
|---|---|---|---|
| Panel-Firmware | `0xC6138` | `0xC00C6038` | `0x9700` (38 656 Byte, 151 Seiten zu 256) |
| Längenwort | `0xCF838` | `0xC00CF738` | 4 |
| Länge des Laders | `0xCF860` | `0xC00CF760` | 4 |
| RAM-Lader | `0xCF864` | `0xC00CF764` | `0x400` |

Das Abbild beginnt mit seiner Vektortabelle, ist für Adresse 0 gelinkt und belegt 19 eigene
Interrupts (Watchdog, Dual Timer, 16 Handler für die UART-Kanäle, Base Timer). Der Lader ist reiner
Thumb-Code für `0x20000000` und spricht den Flash-Controller (`0x40000000`) und UART `0x40038000` an.

## Das Panel-Update

Auslöser: Antwort auf `80 00 00 00 00` ist nicht `0x96` (`0xC0028940`, Sollwert `0xC002CA38`), oder es
kommt keine (Wert 0, dann nach 1000 Versuchen zu 1 ms). Dann setzt die Firmware `+0x22` am
Panel-Objekt, lädt keine Nutzerdaten (`0xC004D0E8`) und der Schritt `0xC0036CA0` fährt das Update.
Er zeigt die Zustandsnummer zweistellig an, daher „00“ bis „12“.

Funktionen: Objekt `0xC0046034`, Start `0xC00469FC`/`0xC00468F0`, Zustandsautomat `0xC00462F0`,
Seite senden `0xC0046190`, Vergleich beim Zurücklesen `0xC0046228`, Abschluss `0xC0046A64`,
Empfang `0xC00282D8`, ein Byte senden `0xC002868C`, Block senden `0xC00286B4`, Leitung leeren
`0xC00286C0`, normalen Panelverkehr sperren `0xC0028524`.

Ablauf, gemessen mit `panel_mcu.py --simulate` (Zeiten in Gerätezeit):

| Zustand | Panel antwortet | ARM sendet |
|---|---|---|
| Start | | Leitung leeren, 500 ms warten, UART-Teiler 1202 (rund 9600 Baud, hergeleitet), GPIO 7.12 auf 1, 200 ms, GPIO 6.8 auf 1, 2 s, dann `18` (bei 3,49 s) |
| 0 | `11` | 10 Byte: Schreiben ins RAM ab `0x20000000`, `0x400` Byte, Summe |
| 1 | `01` | Lader, `0x400` Byte und Summe (Byte-Summe) |
| 2 | `01` | `18` |
| 3 | `11` | `C0` und acht Nullen und Summe: Lader starten |
| 4 | `7E` | Leitung leeren, Teiler 115, 200 ms, `49` |
| 5 | `00` | `27` |
| 6 | `80` | `66`, Länge `00 00 97 00` big-endian, `8C` |
| 7, 8 | je `1A` | Seiten zu 256 Byte plus Summe, 151 Stück (bis 7,45 s) |
| 9 | `1A` | `C7` |
| 10 | `1A` | `C8`: Zurücklesen beginnt |
| 11 | 256 Byte je Seite | nach jeder passenden Seite `C8`; nach 150 Seiten fertig |
| 12 | | Teiler 100 (115200), GPIO 7.12 und 6.8 auf 0, 500 ms, 6.8 auf 1: Panel startet normal; „Please Reboot“ |

Rollen der Pins: 7.12 wählt den Boot-Modus, 6.8 ist der Reset des Panels (hergeleitet aus der
Reihenfolge; Boot-ROM `18`/`11` passt zum seriellen Programmiermodus der FM3, nicht am Datenblatt
geprüft). Die Summen sind die Byte-Summe modulo 256. Die Summe der zurückgelesenen Seiten prüft die
ARM-Firmware nicht, nur den Inhalt.

## Was die Panel-Firmware tut

Aufbau: C++ mit kleinem Ereignis-Scheduler. Grundtakt ist Timer 1 des Dual Timers (Ladewert 4000,
bei 40 MHz 100 µs); jeder Takt löst Ereignis 2 aus, jeder dritte Ereignis 0 (`0x22E4`, hergeleitet).
Wie oft dabei ein einzelner Regler, ein Pad oder das Touchpad gelesen wird, ist offen; das braucht
einen Lauf der Panel-Firmware mit Interrupts.

Nachrichten ans ARM (Ereignistabelle `0x8200`): `00` Taste, `01` Drehgeber, `02` Regler, `04` Pad
(16-Bit-Wert und an/aus), `05` Touchpad, `06` Ein/Aus, `07` Netzteil, `80` Version, `91`/`92`
gehaltene Tasten, `A0`/`A1` Kennung. Vom ARM (`0x2CB8`): `00` LED, `01 nn` (`0x26A0`, offen),
`02 b` (`0x5464`, offen), `80`, `83 b` Touchpad fein/grob, `84 b` (offen), `85`/`86` Kalibrierung X/Y,
`90` Kennung, `91` gehaltene Tasten, `A0` (offen).

### Regler

- Zwei ADC-Einheiten mit je vier Abtastkanälen (AN4, AN5, AN8, AN9 und AN0 bis AN3), davor
  vermutlich Multiplexer, denn es sind 11 Regler, Touchpad und Pads (hergeleitet).
- Ergebnis: 12 Bit im Wandler, die Firmware nimmt Bits 11..2, also 10 Bit (`0x3D98`, hergeleitet;
  die Lage des Ergebnisses im Register hängt am FDAS-Bit, nicht am Datenblatt geprüft).
- Totband: ein neuer Wert zählt erst, wenn er um mehr als 3 (von 1023) abweicht (`0x3CA4`).
- Gesendet wird `02 nn hi lo` mit Wert `>> 2`, also 0..255 (`0x309C`, nur bei Änderung).
- Regler 1, 2 und 4 (PAN, OSC PITCH, EG INT.) haben eine Mittenzone: Rohwerte 449 bis 575 werden 512
  (gesendet 128), der Rest wird auf beide Hälften gestreckt.
- Zwei ADC-Kanäle sind Tasten (`0x20` AMP EG, `0x21` IFX ON): Schwelle 512 (`0x3CC6`).

### Touchpad

- Resistiv: vier Phasen, je drei Ausgänge geschaltet (`0x433C`); über 880 heißt „nicht berührt“.
- Berührung gilt erst nach 12 ruhigen Messungen, Bewegung unter ±3 wird ignoriert (`0x4068`).
- Kalibrierung: Grenzen aus `85`/`86` (Vorgabe ohne ARM 255 und 767), am Rand 32 Rohschritte
  Sicherheitsabstand, Ausgabe 0..1023, Y gespiegelt (`0x3EEC`).
- Standard ist gerundet auf Achterschritte (Merker `+0x22` am Objekt `0x1FFFDEC0`, Vorgabe an).
  `83 01` schaltet fein, jeder andere Wert grob (`0x3E52`). Die ARM-Firmware schickt `83 01` an zwei
  Stellen (`0xC006DCFC`, `0xC00749B0`) und sonst `83 00`; welche Bildschirme das sind, ist offen.

### LEDs

- 88 LED-Nummern `0x00` bis `0x57` in einer Matrix 11 x 8 (Tabelle `0x8460`): 8 PWM-Kanäle der Base
  Timer, 11 Zeilen über GPIO.
- PWM: Periode 5000 Zählschritte, Takt geteilt durch 4, bei 40 MHz rund 2 kHz (hergeleitet).
- `00 nn wert`: das Panel rechnet für jede LED `wert * Periode / 255` in einen Tastgrad um (`0x4EBC`),
  linear, ohne Gamma. Das gilt auch für die Pads: auf Panel-Seite gibt es kein Nur-an/aus. Ob die
  Pads am Gerät sichtbar dimmen, ist offen.

## Auflösung: wo Bits verloren gehen

| Quelle | Wandler | Panel sendet | ARM nutzt |
|---|---|---|---|
| Regler | 12 Bit | 8 Bit (0..255) nach `>> 2` beim Lesen und `>> 2` beim Senden | 7 Bit (`wert >> 1`, siehe [Skript-Laufzeit](skript-laufzeit.md)) |
| Touchpad | 12 Bit | 0..1023, aber normal in Achterschritten (128 Stufen) | 7 Bit (`>> 3`) |
| Pads | offen | 16-Bit-Feld | offen |

Die Angabe „Panel-Wert 0..1023“ für Regler in der Skript-Laufzeit passt nicht zum Panel-Code: das
Panel schickt höchstens 255. Mit `02 nn 03 FF` lässt sich die ARM-Seite trotzdem füttern (gemessen in
der [Panel-Bedienung](../messungen/2026-10-08-panel-bedienung.md)), vom echten Panel kommt das nicht.

## Was ein Patch gewinnen könnte

**ARM-Patch, Panel unverändert (geringes Risiko):**

- Regler: 1 Bit mehr (256 statt 128 Stufen), wenn die Firmware das `>> 1` nicht macht. Mehr gibt das
  Panel nicht her. Die Parameter selbst sind meist 0..127, der Gewinn wirkt nur dort, wo ein Wert
  feiner sein kann.
- Touchpad: `83 01` beim Start senden und das `>> 3` weglassen. Dann kommen 0..1023 aus einem
  Rohbereich von rund 713 x 595 Schritten (mit der eigenen Kalibrierung 105..882 und 156..815,
  hergeleitet). Wie viel davon Rauschen ist, ist offen.

**Panel-Patch (mittleres Risiko, siehe unten):**

- Regler mit 10 Bit senden: das Format hat `hi lo`, nur das `>> 2` in `0x309C`/`0x3180` fällt weg.
  12 Bit wären möglich, das Totband von 3 müsste dann mitwachsen.
- Schnelleres Abtasten über den Grundtakt (100 µs) oder die Ereignisteilung; was dabei die Last und
  die LED-Matrix macht, ist offen.
- Touchpad ohne Achterschritte schon im Panel, oder eine kürzere Wartezeit als 12 Messungen.

## Risiko eines Panel-Patches

- **Wie geschrieben wird:** Das ARM schaltet das Panel per GPIO in den Boot-Modus seines ROMs und
  schreibt das ganze Abbild neu. Das ROM-Bootprogramm liegt im Chip, ein kaputtes Panel-Abbild
  zerstört den Weg zurück also nicht (hergeleitet, Boot-ROM der FM3 nicht am Datenblatt geprüft).
- **Selbstheilung:** Meldet das Panel nicht `0x96` oder gar nichts, flasht die Stock-Firmware beim
  nächsten Start ihr eigenes Abbild darüber (im Emulator für `0x95` und für keine Antwort gemessen).
  Stromausfall mitten im Update führt also beim nächsten Start wieder ins Update (hergeleitet).
- **Die Falle:** Ein eigenes Panel-Abbild, das `0x96` meldet, aber Tasten oder Regler kaputt
  liefert, wird nie überschrieben. Der Weg über „SOFTWARE UPDATE, press ENTER“ braucht dann eine
  Taste, die vielleicht nicht geht. Deshalb: ein eigenes Abbild meldet eine andere Version, und
  der ARM-Patch, der es einspielt, akzeptiert genau diese; fällt der Patch weg, stellt die
  Stock-Firmware das Original wieder her.
- **Prüfung:** Die Firmware vergleicht nur 150 von 151 Seiten. Die letzte Seite (ab `0x9600`)
  muss man selbst prüfen, zum Beispiel über eine Prüfsumme, die das Panel meldet.
- **Fehler beim Update:** „Error / Unknown Error.“, das Panel bleibt im Lader stehen; nach dem
  Neustart antwortet es nicht und das Update läuft erneut (hergeleitet).
- **Offen:** Flash-Schutzbits der FM3, die der Lader setzen könnte; ob `0x27` den ganzen Chip
  löscht; wie lange ein echtes Update am Gerät dauert (im Emulator falsche Byte-Zeit bei 9600 Baud).

## Werkzeug

```bash
tools/emu/.venv/bin/python tools/emu/panel_mcu.py --vsb SYSTEM.VSB                  # Lage, Größen, Hashes, Vektoren
tools/emu/.venv/bin/python tools/emu/panel_mcu.py --vsb SYSTEM.VSB --simulate      # Update gegen das Boot-ROM-Modell
tools/emu/.venv/bin/python tools/emu/panel_mcu.py --vsb SYSTEM.VSB --simulate --corrupt 3 --png fehler.png
```

Das Werkzeug gibt keine Bytes aus. Die Disassembly der Panel-Firmware gehört nicht ins Repo.
