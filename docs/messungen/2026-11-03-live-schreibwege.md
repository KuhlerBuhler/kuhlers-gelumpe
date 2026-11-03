# Live-Schreibwege: Pattern, Parts und Global

Stand 3. November 2026. Gemessen im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau,
jeweils mit dem BLECH-Satz. Fälle: `tools/emu/live_write_cases.py` (läuft als Gruppe von `remote_cases`). **Am Gerät
nicht geprüft.** Die Ergebnisse stehen je Feld als `live` in der [Gerätekarte](../geraetekarte.md).

## Frage

Jeder Wert, den man an der Electribe einstellt, landet im Pattern oder in den Global-Einstellungen im RAM. Welche
Funktion der Firmware schreibt ihn, wenn man ihn im Menü oder mit einer Taste ändert, und reicht es, das Byte selbst zu
schreiben? Oder muss der Setter laufen, weil er noch etwas anderes nachzieht (Kopie für die Klangerzeugung, einen Cache,
die Anzeige)?

## Vorgehen

1. Jede Seite des Pattern-Menüs (Bildschirm 3), des Part-Menüs (Bildschirm 7) und des Global-Menüs (Bildschirm 9)
   einmal hoch und runter gedreht, dazu die Tasten MASTER FX, MFX HOLD, TOUCH SCALE, GATE ARP, IFX ON, MFX SEND, AMP EG,
   der LEVEL-Regler und die Encoder für Sample und Insert-Effekt. Dabei jede Schreibung ins Pattern und in die
   Global-Einstellungen mit Adresse und Rücksprung festgehalten. So ergibt sich der Setter.
2. Zwillingsprobe: zwei Läufe aus demselben Start, einmal nur das Byte geschrieben, einmal der Setter mit demselben Wert.
   Verglichen sind 4 MB RAM ab `0xC0300000`, das Bild des Displays und die LEDs. Was beide Läufe gleich haben, ist der
   Wert; was nur der Setter ändert, ist sein Nachzug.
3. Jeder Setter meldet zum Schluss an die Beobachter (`0xC00431F0` und `0xC0048C6C`, blau `0xC003D6EC` und
   `0xC0042E48`). Die Meldung schreibt in jedem Lauf dieselben Stellen (Warteschlangen und Zähler bei `0xC030B37C`,
   `0xC030D728`, `0xC0316710`, `0xC03487D0`, `0xC06A240C`, `0xC06CA684` bis `0xC06CB000`; blau `0xC03484F0`,
   `0xC05737C4`, `0xC05975B0` bis `0xC0597804`). Sie zählt hier nicht als Nachzug: wer das Byte schreibt, verzichtet nur
   darauf, dass andere Teile der Oberfläche es sofort erfahren.

Das Pattern-Objekt steht in `[0xC033E6A4]`, sein Block ab +4. Offsets unten sind Block-Offsets. Hinter dem Block
(Block-Offset 0x4000 und höher) liegt die Kopie, die die Klangerzeugung liest; der Schreiber dafür ist `0xC004B208`
(blau `0xC0045120`) mit `(Objekt + 0x401C, x, Parameter, Wert)`. Das Global-Objekt steht in `[0xC033E6A0]`, sein Block
ab +4. Rot hat dieselben Adressen wie Hacktribe; die blauen stehen in `data/synth-map/live-write.json`.

## Pattern (gemessen)

Setter mit `(Pattern-Objekt, Wert, 1)`, Alternate mit `(Pattern-Objekt, welches, Wert, 1)`.

| Feld | Byte | Setter Hacktribe, rot | Setter blau | Byte allein reicht | Der Setter zieht nach |
|---|---|---|---|---|---|
| Tempo | 34, u16 | `0xC004A80C` | `0xC00448EC` | nein | Clock-Zähler ab `0xC0314234`, Hauptanzeige; blau zusätzlich LED 20 |
| Swing | 36 | `0xC004A594` | `0xC0044674` | ja | nur die Meldung |
| Länge | 37 | `0xC004A560` | `0xC0044640` | nein | kopiert die Steps des ersten Takts nach hinten |
| Beat | 38 | `0xC004A4F8` | `0xC00445F8` | offen | im RAM nur die Meldung; Hacktribe und rot melden zusätzlich Parameter 0x3B an die Klangerzeugung, ohne Spur im RAM |
| Key | 39 | `0xC004A6FC` | `0xC00447DC` | nein | Cache ab `0xC068C280` (blau `0xC0566588`) |
| Scale | 40 | `0xC004A77C` | `0xC004485C` | nein | derselbe Cache |
| Chord Set | 41 | `0xC004A534` | `0xC0044614` | nein | Cache ab `0xC068CFD0` (blau `0xC05672D8`) |
| Play Level | 42, invertiert | `0xC004A698` | `0xC0044778` | nein | Kopie bei 0x426E (blau 0x424E) |
| Gate Arp | 49, neu | `0xC004A5F8` | `0xC00446D8` | ja | nur die Meldung; Menü 0 bis 49 |
| Alternate 13-14 | 68 | `0xC004A614`, welches 0 | `0xC00446F4` | nein | Kopie bei 0x4024 |
| Alternate 15-16 | 69 | `0xC004A614`, welches 1 | `0xC00446F4` | nein | Kopie bei 0x4025 |
| Chain To | 15104, u16 | `0xC004A5B0` | `0xC0044690` | ja | nur die Meldung |
| Chain Repeat | 15106 | `0xC004A5D4` | `0xC00446B4` | ja | nur die Meldung |

Das Menü schreibt Gate Arp auf Seite 11 (Index 10), Byte 49. Das Feld fehlte bisher in der Karte.

## Master-Effekt und Pad (gemessen)

Setter mit `(Pattern-Objekt + 0x4004, Wert, 1)`. Gemessen mit MASTER FX an und dem Pad berührt, bewegt und losgelassen,
dann MFX HOLD zweimal.

| Feld | Byte | Setter Hacktribe, rot | Setter blau | Byte allein reicht | Der Setter zieht nach |
|---|---|---|---|---|---|
| Pad berührt | 60, neu | `0xC00488A0` | `0xC0042AF8` | nein | Kopie ab 0x401C, Zustand des Effekts; Parameter 2 |
| Typ | 61 | `0xC0048A64` | `0xC0042CBC` | nein | Kopie bei 0x401D und viele Stellen des Effekts |
| Pad X | 62 | `0xC0048924` | `0xC0042B7C` | nein | Kopie, Parameter 4 |
| Pad Y | 63 | `0xC0048984` | `0xC0042BDC` | nein | Kopie, Parameter 5 |
| Hold | 65 | `0xC00489E4` | `0xC0042C3C` | nein | Kopie, Parameter 6; setzt auch Byte 60 |

Byte 60 ist 1, solange das Pad im Master-FX-Modus berührt ist, und geht beim Loslassen auf 0. Auch dieses Feld fehlte
in der Karte.

TOUCH SCALE und GATE ARP als Tasten und eine Berührung in diesen Modi schreiben nichts ins Pattern. Ein Lesezugriff auf
die Bytes 44 bis 59 kam in keinem Lauf vor (Menüs, Tasten, Regler, Pad). Der Umfang von Touch Scale steht in den
Global-Einstellungen (Byte 38), der Zustand des Modus im RAM bei `0xC06911E4`. Die Bytes 44 bis 48 und 50 bis 59
bleiben unbekannt.

## Parts (gemessen)

Direkte Setter mit `(Pattern-Objekt + 0x400C, Part, Wert, 1)`, sie schreiben bei Objekt + 0x330 mal Part + 0x80X.
Sample, Level und Insert-Effekt gehen über den Part-Setter `0xC0048460` (blau `0xC0042700`): `r0` aus `[0xC034886C]`
(blau `[0xC0348570]`), `r1` 0x10, `r2` 0, `r3` die Nummer des Werts, auf dem Stack Wert und 0. Die blaue Version hat
keine Besetzt-Prüfung und ihre Sprungtabelle bei `0xC00BA624`. Offsets relativ zum Part.

| Feld | Byte | Setter Hacktribe, rot | Setter blau | Byte allein reicht | Der Setter zieht nach |
|---|---|---|---|---|---|
| Last Step | 0 | `0xC0048CE8` | `0xC0042EC4` | ja | nichts, nur der Store |
| Mute | 1 | `0xC0049330` | `0xC00434F0` | nein | Kopie, Stimmenzustand bei `0xC068D058`; klemmt bei 1, Parameter 0x12 |
| Voice Assign | 2 | `0xC00493A0` | `0xC0043560` | nein | Kopie; klemmt bei 3, Parameter 0x13 |
| Motion Sequence | 3 | `0xC0049410` | `0xC00435D0` | nein | Kopie, Parameter 0x14 |
| Pad Velocity | 4 | `0xC0049478` | `0xC0043638` | nein | Kopie, Parameter 0x15 |
| Scale Mode | 5 | `0xC00492A0` | `0xC0043460` | nein | Cache ab `0xC068C280` |
| Priority | 6 | `0xC00494E8` | `0xC00436A8` | nein | Kopie, Parameter 0x17 |
| Sample | 8, u16 | Part-Setter, Wert 8 | Part-Setter | nein | Kopie, Stimmen, Anzeige; schreibt auch Byte 11 |
| Level | 24 | Part-Setter, Wert 19 | Part-Setter | nein | Kopie, Parameterfenster (schon in `PART_WRITES`) |
| AMP EG | 26 | `0xC0049664` | `0xC0043780` | nein | Kopie, Parameter 0x28 |
| MFX Send | 27 | `0xC00496D4` | `0xC00437F0` | nein | Kopie, Parameter 0x29 |
| Groove | 28 | `0xC0049DA4` | `0xC0043EC0` | ja | nur die Meldung |
| Groove Depth | 29 | `0xC0049D7C` | `0xC0043E98` | ja | nur die Meldung |
| IFX On | 32 | `0xC0049DEC` | `0xC0043F08` | nein | Kopie, Parameter 0x2C |
| Insert-Effekt | 33 | Part-Setter, Wert 26 | Part-Setter | nein | Kopie |

Die Seiten des Part-Menüs schreiben in dieser Reihenfolge: Last Step, Groove, Groove Depth, Voice Assign, Priority,
Motion Sequence, Pad Velocity, Scale Mode; die neunte Seite schreibt nichts. Auf allen drei Firmwares gleich.

Last Step: Das Menü geht von 0 bis 15, das Display zeigt 0 als 16 und 1 bis 15 wie sie sind (Bild des Displays
gelesen). Bisher stand das Feld als unbekannt in der Karte.

## Global (gemessen)

Setter mit `(Global-Objekt, Wert, 1)`. Die meisten melden danach einen Parameter über `0xC004B208` mit
`r0 = [0xC034890C]`. Offsets wie in der [Messung vom 14. Oktober](2026-10-14-global-felder.md), auf allen drei
Firmwares gleich.

| Feld | Byte | Setter Hacktribe, rot | Setter blau | Byte allein reicht | Der Setter zieht nach |
|---|---|---|---|---|---|
| Metronom | 16 | `0xC00471B0` | `0xC004147C` | ja | nichts |
| Sync Polarity | 17 | `0xC00471C0` | `0xC004148C` | nein | Parameter 0x2D |
| Sync Unit | 18 | `0xC00471F8` | `0xC00414C4` | nein | Parameter 0x3A |
| Pattern Change Lock | 19 | `0xC00475BC` | `0xC0041888` | ja | nichts |
| Audio In Thru | 20 | `0xC0047230` | `0xC00414FC` | nein | Parameter 0x2E |
| Velocity Curve | 27 | `0xC00472D8` | `0xC00415A4` | ja | nichts |
| Knob Mode | 28 | `0xC00472E8` | `0xC00415B4` | ja | nichts |
| Trigger Mode | 29 | `0xC0047380` | `0xC004164C` | nein | legt das Trigger-Objekt neu an und lädt es |
| LCD Contrast | 30 | `0xC0047584` | `0xC0041850` | nein | Parameter 0x36 |
| Chain Mode | 31 | `0xC00475CC` | `0xC0041898` | nein | bei 0 der Ketten-Zustand |
| Battery Type | 32 | `0xC00472F8` | `0xC00415C4` | ja | nichts |
| Auto Power Off | 33 | `0xC0047308` | `0xC00415D4` | nein | Parameter 0x34 |
| Tempo Lock | 36 | `0xC0047788` | `0xC0041A54` | nein | Parameter 0x37, danach das Tempo neu |
| Power Save | 37 | `0xC0047348` | `0xC0041614` | nein | Parameter 0x33 |
| Touch Scale Range | 38 | `0xC004754C` | `0xC0041818` | nein | Parameter 0x35 |
| Clock Mode | 40 | `0xC00473D4` | `0xC00416A0` | nein | Parameter 0x31; lehnt ab, solange der Transport in Zustand 6 bis 9 ist |
| Global Channel | 41 | `0xC0047454` | `0xC0041720` | nein | Parameter 0x32 |
| Send Filter | 42 | `0xC004748C` | `0xC0041758` | nein | Parameter 0x38 |
| Receive Filter | 43 | `0xC00474E0` | `0xC00417AC` | nein | Parameter 0x39 |

Die Seite XY CALIBRATION (20) schreibt kein Byte der Global-Einstellungen. Was die gemeldeten Parameter in der
Klangerzeugung auslösen, ist nur aus dem Code gelesen (**offline**); dass der Setter das Byte schreibt und die mit
"nichts" nur das Byte, ist gemessen.

## Klemmen (offline)

Die Setter klemmen selbst, unabhängig vom Menü. Groove: Hacktribe setzt alles über 61 auf 0, rot und blau alles über
24. Hacktribe hat also mehr Groove-Vorlagen; die Karte behält Korgs Bereich 0 bis 24 und nennt die Grenze in der
Notiz. Mute klemmt bei 1, Voice Assign bei 3. Ein reines Byte-Schreiben klemmt nicht: ein Wert außerhalb steht dann im
Pattern, bis ihn die Firmware das nächste Mal liest.

## Offen

- **Beat** auf Hacktribe und rot: der Setter meldet Parameter 0x3B an die Klangerzeugung, im RAM ist davon nichts zu
  sehen. Ob ein reines Byte-Schreiben im Spiel denselben Takt ergibt, ist nicht geprüft.
- **Bytes 44 bis 48 und 50 bis 59** des Patterns: nichts schreibt oder liest sie im Emulator.
- **Motion und Samples**: nicht untersucht.
- **Am Gerät**: keine Zeile ist am Gerät geprüft. Eine Zwillingsprobe im Emulator zeigt, was die Firmware im RAM tut,
  nicht ob die Klangerzeugung zwischendurch einen alten Wert hört.

## Vergleich mit einem anderen Pattern-Editor

Ein anderer Editor für Electribe-Patterns, dessen Quelltext wir gelesen haben, kennt im Pattern den Namen, Tempo (34), Swing (36), Länge (37), Beat (38, 0 bis 3), Key (39), Scale (40,
0 bis 34), je Part Last Step (0), Mute (1) und Sample (8), dazu die Steps (ab 0x30, 12 Byte, An, Gate, Velocity,
Trigger, Noten 4 bis 7). Alle diese Offsets stimmen mit der Karte überein.

Unterschiede:

- **Last Step**: der Editor nennt 0 als 64 und 1 bis 63 wie sie sind. Im Emulator geht das Menü nur bis 15, und 0
  zeigt 16. Ob die Firmware Werte über 15 aus einer Datei annimmt, ist nicht geprüft.
- **Beat**: die Karte erlaubt 4 (Achtel, nur mit BLECH), der Editor nur 0 bis 3.
- Der Editor kennt Chord Set, Play Level, Gate Arp, Alternate, Chain, Groove, die Master-Effekt-Bytes und alle Werte
  von Part-Byte 2 an nicht.

Er beschreibt nur Bytes in Dateien, keinen Schreibweg im laufenden Gerät. Für `live` gibt es dort nichts zu
vergleichen.
