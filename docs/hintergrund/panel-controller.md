# Panel-Controller: eigener Mikrocontroller hinter Tasten, Reglern und LEDs

Nur offline: VSB gelesen, Panel-Firmware disassembliert, Panel-Update im Emulator
gegen ein nachgebautes Boot-ROM gefahren. Am Gerät nichts. Marker: **gemessen** (im Emulator oder
an den Bytes der VSB), **hergeleitet** (aus gelesenem Code, nicht laufen gesehen), **offen**.
Keine Bytes, keine Listings von Korg im Repo; `tools/emu/panel_mcu.py` liest alles aus der eigenen VSB.

Das Bedienfeld (Panel) ist ein eigener Rechner an UART0 (5-Byte-Nachrichten, siehe
[Panel-Bedienung](../messungen/2026-10-08-panel-bedienung.md)). Seine Firmware steckt in jeder
[`SYSTEM.VSB`](../glossary.md#vsb), und die ARM-Firmware schreibt sie neu, wenn das Panel nicht `0x96` meldet.

## Der Chip

- **Gemessen:** Abbild und Lader sind in Korgs Original, Hacktribe und Synth gleich (`panel_mcu.py --vsb X.VSB` nennt
  Lage, Größen und Hashes). Das Panel-Abbild liegt in Hacktribe und Original ab VSB `0xC6138`, im Synth ab VSB `0xB0B10`.
- **Gemessen:** Die CPU ist ein ARM Cortex-M3 (Vektortabelle mit Stack `0x20004000`, Reset `0x60DD`, Thumb-2-Code).
- **Hergeleitet** (Panel-Code im Unicorn bis zur Hauptschleife, Registerzugriffe mitgeschrieben): Familie Fujitsu/Spansion
  FM3 (heute Infineon): Watchdog-Schlüssel `0x1ACCE551` an `0x40011C00`, Takt `0x40010000`, GPIO `0x40033000`, Base Timer
  `0x40025000`, zwei ADC `0x40027000` und `0x40027100`, UART (MFS) `0x40038000`, SRAM `0x1FFFC000` bis `0x20003FFF`.
  Der Panel-Takt ist 40 MHz (UART-Teiler 346 ergibt 115200 Baud nur dort). Die Version `0x96` steht fest im Panel-Code
  (Antwort auf `0x80`, Code `0x2E1C`).
- **Offen:** genaues Bauteil, Flashgröße.

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

- 88 LED-Nummern `0x00` bis `0x57` in einer Matrix aus 8 Zeilen zu 11 Spalten (Tabelle `0x8460`). Der
  Scan `0x4F28` schaltet je Aufruf eine Zeile weiter, der Zähler läuft nach 7 wieder auf 0 (`0x5584`).
- Spalten 0 bis 6 laufen über die Kanäle 1 bis 7 der Base Timer, Spalten 7 bis 10 sind reine GPIO-Pins
  (Bit-Band `0x4266xxxx`, `0x5310` bis `0x53A2`). Jede Spalte hat dazu ihren GPIO-Pin, der sagt, ob die
  LED der aktuellen Zeile an ist (Byte 1 und Wert ungleich 0).
- PWM: Periode 5000 Zählschritte (Register 4999), Takt geteilt durch 4, bei 40 MHz rund 2 kHz (hergeleitet).
- `00 nn wert` legt `[nn, 1, wert]` ab (`0x2E3A`). Für die PWM-Spalten rechnet das Panel daraus ein
  Tastgrad-Wort `P - min(floor(wert * P / 255), P - 1)` mit `P = 4999` und legt es im LED-Eintrag ab
  (`0x4EBC`, Tabelle `0x1FFFDFAC`, 6 Byte je LED, Wort bei `+4`). Linear, ohne Gamma, auch für die Pads.
  Alle 256 Werte im Emulator abgelesen (`panel_mcu.py --duty`): 0 ergibt 4999, 1 ergibt 4980, 64 ergibt
  3745, 128 ergibt 2490, 192 ergibt 1236, 255 ergibt 1.
- Der Scan schreibt das Wort über `0x7464` ins Vergleichsregister des Kanals (Zeiger `0x86D4`) und
  begrenzt es dort auf `P - 1`. Ist Byte 1 oder der Wert 0, schreibt er `P`, die LED bleibt aus.
  Kleineres Wort heißt also heller; dass der Ausgang so herum gepolt ist, ist hergeleitet, nicht gemessen.
- Mit PWM: alle Pad-LEDs, die Regler-LEDs `0x00` bis `0x04`, REC (`0x12`), PLAY (`0x09`, `0x15`), die
  blauen LEDs von 1 bis 4 (`0x16` bis `0x19`) und `0x4C` bis `0x57` (keinem Bedienelement zugeordnet,
  vermutlich die unteren RGB-LEDs, offen).
- Nur an oder aus: alle übrigen Tasten-LEDs, auch STOP, TAP und die roten LEDs von 1 bis 4 (Liste
  `LED_ON_OFF` in `data/panel.mjs`). Power Save dimmt sie darum nicht, solange ihr Wert nicht 0 wird.
- **Offen:** ob die Pads am Gerät sichtbar dimmen.

## Auflösung: wo Bits verloren gehen

| Quelle | Wandler | Panel sendet | ARM nutzt |
|---|---|---|---|
| Regler | 12 Bit | 8 Bit (0..255) nach `>> 2` beim Lesen und `>> 2` beim Senden | 7 Bit (`wert >> 1`, siehe [Skript-Laufzeit](skript-laufzeit.md)) |
| Touchpad | 12 Bit | 0..1023, aber normal in Achterschritten (128 Stufen) | 7 Bit (`>> 3`) |
| Pads | offen | 16-Bit-Feld | offen |

Im Emulator kommen Reglerwerte 0..1023 an, das echte Panel schickt höchstens 255. Mit `02 nn 03 FF` lässt sich die
ARM-Seite trotzdem füttern (gemessen in der [Panel-Bedienung](../messungen/2026-10-08-panel-bedienung.md)), vom echten
Panel kommt das nicht.

**Was ein Patch an Auflösung gewinnen könnte** (hergeleitet, nichts davon gebaut):

- ARM-Patch, Panel unverändert (geringes Risiko): Regler 1 Bit mehr (256 statt 128 Stufen), wenn die Firmware das
  `>> 1` nicht macht. Mehr gibt das Panel nicht her, und die meisten Parameter sind 0..127. Touchpad: `83 01` beim Start
  senden und das `>> 3` weglassen, dann kommen 0..1023 aus einem Rohbereich von rund 713 x 595 Schritten (mit der eigenen
  Kalibrierung 105..882 und 156..815). Wie viel davon Rauschen ist, ist offen.
- Panel-Patch (mittleres Risiko, nächster Abschnitt): Regler mit 10 Bit senden, das Format hat `hi lo`, nur das `>> 2` in
  `0x309C`/`0x3180` fällt weg; 12 Bit gingen, wenn das Totband von 3 mitwächst. Schneller abtasten über den Grundtakt
  (100 µs) oder die Ereignisteilung, was Last und LED-Matrix dazu sagen, ist offen. Touchpad ohne Achterschritte schon im
  Panel, oder kürzer warten als 12 Messungen.

Quelle: `git show origin/develop:docs/hintergrund/panel-controller.md`, Abschnitt "Was ein Patch gewinnen könnte"

## Risiko beim Ändern des Panel-Abbilds

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
