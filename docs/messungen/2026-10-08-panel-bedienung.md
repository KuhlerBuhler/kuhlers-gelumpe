# Bedienfeld: Nummern der Tasten, Regler, Pads und LEDs

Stand 2026-10-08. Gemessen im Emulator (`tools/emu/machine.py`) mit der
eigenen VSB und leerem Flash: nach 3 s Gerätezeit (Hauptbildschirm) je eine
Panel-Nachricht schicken, dann Display und LED-Befehle der Firmware ansehen.
Kein Gerät angeschlossen. Die Tabelle steht in `data/panel.mjs`.

## Nachrichten vom Panel an die CPU (5 Byte)

- **Offline:** Verteiler bei `0xC002814C`. Taste `00 nn zz` (zz 1 gedrückt,
  0 losgelassen), Drehgeber `01 nn 00 dd` (dd vorzeichenbehaftet), Regler
  `02 nn hi lo`, Pad `04 nn hi lo an`, Touchpad `05 xh xl yh yl`, Typ 6
  ein Byte, Typ 7 ja/nein. Freetribe (`svc_panel.c`) liest dieselben Felder.
- **Gemessen:** Regler `02 00 00 80` zeigt LEVEL 64, `00 FF` 127, `03 FF`
  511. Die Firmware begrenzt nicht; das Panel schickt 0 bis 255.
- **Gemessen:** Pad `04 nn 00 64 01` wählt Part nn+1 und lässt die rote LED
  des Pads leuchten, `04 nn 00 00 00` lässt los. nn 16 ergibt „Part:17“,
  gültig sind 0 bis 15.
- **Gemessen:** Typ 6 mit 1 zeigt „Power Off“, mit 0 danach schaltet die
  Firmware ab (siehe unten). Das ist der Ein/Aus-Taster.
- **Gemessen:** Typ 7 mit 1 tauscht das Batteriesymbol oben rechts gegen
  ein Symbol mit Stecker, mit 0 kommt die Batterie zurück. Steht Typ 7 auf 1,
  übergeht die Firmware den Ein/Aus-Taster (Typ 6) ganz. Gesendet direkt
  nach den gehaltenen Tasten (`0x91`) verwirft sie ihn; nach der zweiten
  Versionsabfrage (`0x80`, rund 290 ms nach dem Start) nimmt sie ihn an.
- **Gemessen am Gerät (2026-10-08):** Typ 7 heißt „Netzteil steckt“. Mit
  Netzteil zeigt das Gerät oben rechts das Stecker-Symbol statt der Batterie,
  wie der Emulator bei Typ 7 = 1. Am Gerät bestätigt. Der
  Emulator bietet es als Schalter „Netzteil steckt“ an.
- **Gemessen:** Touchpad `05 ...` allein spielt im Touch-Scale-Modus eine
  Note; losgelassen wird sie erst mit Taste `0x22` (losgelassen). Taste
  `0x22` ist die Berührung des Touchpads.
- **Hergeleitet:** Touchpad-Werte reichen von 0 bis 1023: die Kalibrierung
  bei Flash `0x7FF000` im eigenen Dump hat vier 16-Bit-Werte zwischen 100
  und 900.

## Tasten

Namen aus dem Werkstatt-Test der Firmware („Switch & LED Check“, Strings ab
`0xC00A6B00`); Freetribe nennt PLAY `0x02`, MENU `0x09`, SHIFT `0x0a`, EXIT
`0x0d`, LPF `0x12`, HPF `0x14`, BPF `0x16`, AMP EG `0x20`.

| Nr. | Taste | Beleg im Emulator |
|---|---|---|
| `0x00` | REC | LEDs REC und PLAY an |
| `0x01` | STOP | nach PLAY gehen die PLAY-LEDs aus |
| `0x02` | PLAY | LEDs `0x09` und `0x15` an |
| `0x03` | TAP | viermal im Abstand 0,65 s: Tempo 92.3 |
| `0x04` | GATE ARP | LED `0x1a` an |
| `0x05` | TOUCH SCALE | nach MASTER FX: LED `0x1b` wieder an |
| `0x06` | MASTER FX | LED `0x1b` aus, `0x1c` an |
| `0x07` | MFX HOLD | LED `0x1d` an |
| `0x08` | Edit ◄ | untere Zeile springt auf „ScaleMode“ (letzter Eintrag) |
| `0x09` | MENU | Menü „Pattern 1/29“, BPM |
| `0x0a` | SHIFT | nach Freetribe; allein keine Änderung |
| `0x0b` | Part ◄ | Part 01 wird 16 |
| `0x0c` | Edit ► | untere Zeile springt auf „Pitch“ (nächster Eintrag) |
| `0x0d` | EXIT | nach Freetribe; am Hauptbildschirm keine Änderung |
| `0x0e` | WRITE | „select DESTINATION“, LED `0x0b` |
| `0x0f` | Part ► | Part 01 wird 02 |
| `0x10` | PART MUTE | LED `0x20`, Pads rot |
| `0x11` | PART ERASE | LED `0x21` |
| `0x12` | LPF | „FILTER TYPE MS20 LPF“ |
| `0x13` | TRIGGER | nach SEQUENCER: LED `0x22` wieder an |
| `0x14` | HPF | „FILTER TYPE electribe HPF“, LED `0x0d` |
| `0x15` | SEQUENCER | LED `0x23` |
| `0x16` | BPF | „FILTER TYPE electribe BPF“, LED `0x0e` |
| `0x17` | KEYBOARD | LED `0x24` |
| `0x18` | CHORD | LED `0x25` |
| `0x19` | STEP JUMP | LED `0x26` |
| `0x1a` | MFX SEND | LED `0x0f` aus (war an) |
| `0x1b` | PATTERN SET | LED `0x27` |
| `0x1c` bis `0x1f` | Takt 1 bis 4 | im SEQUENCER: rote LED `0x28` bis `0x2b` |
| `0x20` | AMP EG | LED `0x10` |
| `0x21` | IFX ON | LED `0x11` |
| `0x22` | Touchpad berührt | lässt die Touchpad-Note los |

`0x23` bis `0x3f` zeigen keine Wirkung.

## Drehgeber und Regler

| Art | Nr. | Anzeige im Emulator |
|---|---|---|
| Drehgeber | 0 | Pattern 001 wird 002; LED-Ring `0x00` |
| Drehgeber | 1 | SAMPLE/OSC |
| Drehgeber | 2 | CUTOFF |
| Drehgeber | 3 | MOD. TYPE |
| Drehgeber | 4 | IFX TYPE |
| Regler | 0 | LEVEL |
| Regler | 1 | PAN |
| Regler | 2 | OSC PITCH |
| Regler | 3 | RESONANCE |
| Regler | 4 | EG INT. |
| Regler | 5 | MOD. DEPTH |
| Regler | 6 | ATTACK |
| Regler | 7 | IFX EDIT |
| Regler | 8 | DECAY / RELEASE |
| Regler | 9 | SAMPLE/OSC EDIT |
| Regler | 10 | MOD. SPEED |

Regler 11 bis 19 zeigen nichts. Ein Regler, der auf seinen aktuellen Wert
gestellt wird, zeigt ebenfalls nichts (PAN in der Mitte).

## LEDs

Von der CPU ans Panel `00 nn hh`. Gemessen: die LEDs in der Tastentabelle,
Pads rot `0x2c + 2n` und blau `0x2d + 2n` (blau = gewählter Part), Ring des
Hauptreglers `0x00`. Die übrigen Nummern (Ringe `0x01` bis `0x04`, Edit
`0x05`/`0x06`, MENU `0x07`, EXIT `0x08`, SHIFT `0x0a`, STOP `0x13`, TAP
`0x14`, Takt blau `0x16` bis `0x19`) stammen aus Freetribe (`svc_panel.h`).
MENU ändert seine LED beim Öffnen des Menüs nicht.

Farben, RGB und wie man LEDs selbst setzt: siehe
[LEDs selbst setzen](2026-10-08-led-execute.md). Kurz: Pads haben rot und
blau (kein Grün), echtes RGB nur die vier unteren Lichter.

## Ausschalten

- **Gemessen:** Nach Typ 6 mit 1 und dann 0 (Typ 7 auf 0) setzt die Firmware alle LEDs auf
  0 und zieht GPIO 7.11 sowie 6.3 bis 6.5 auf 0.
- **Hergeleitet:** GPIO 7.11 hält die Stromversorgung. Der Emulator gilt ab
  da als aus: CPU steht, Display dunkel.
- **Gemessen:** GPIO 7.15 dauerhaft auf 0 zeigt ebenfalls „Power Off“ und
  schaltet danach ab. Was am Gerät daran hängt, ist nicht geklärt; die Seite
  nutzt Typ 6.

## Am Gerät beobachtet (2026-10-08)

- Ausschalten braucht 2 s gehaltenen Ein/Aus-Taster. Im Emulator reicht
  Typ 6 mit 1 und dann 0 sofort. Hergeleitet: das Panel meldet den Taster
  erst nach dem Halten; der Emulator-Dienst schickt Typ 6 deshalb erst nach
  2 s gehaltener Taste.
- Start: rund 1 s weißes Display, 4 s Startbild, kurzes Aufblitzen, dann
  Laden; dabei leuchtet kurz die Energiesparanzeige (Energiesparen auf
  Auto), danach Samples von der Karte oder ohne Karte gleich das Pattern.
  Der Emulator braucht rund 1 s bis zum Pattern, weil er das Flash-Lesen
  abkürzt und das DSP-Programm nicht hochlädt.

## UART-Sendezeit

- **Gemessen:** Der Hauptregler wechselt das Pattern und schickt dabei
  `B0 00 00 B0 20 00 C0 01` über DIN-MIDI. Meldete das Modell das
  Senderegister sofort wieder leer, lief die Interrupt-Schleife der UART
  (`0xC0025670`) achtmal und die Firmware brach mit `MidiHandler.cpp`
  Zeile 85 ab. Mit der Zeit eines Bytes auf der Leitung (320 µs bei 31250
  Baud, 87 µs bei 115200) läuft sie durch.
- **Gemessen:** Dasselbe beim Empfang: eine ganze SysEx-Nachricht auf einmal
  im Empfänger bricht ebenso ab. Eingehende Bytes kommen deshalb im Abstand
  einer Bytezeit an; danach beantwortet die Firmware RAM-Schreiben über
  DIN-MIDI mit `0x21`.
