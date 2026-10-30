# Farbe des Hintergrundlichts schon beim Einschalten

Stand 2026-10-29. Emulator (`tools/emu`, Unicorn) mit Hacktribe 2.02, Korgs roter und Korgs blauer 2.02, jeweils mit dem
Satz BLECH, Karte im Speicher, Netzteil. Zeiten sind Emulatorzeit ab dem Einsprung in die Firmware. **Am Gerät nichts
geprüft.** Markierungen: **gemessen**, **offline** (Code gelesen), **hergeleitet**, **offen**.

Wunsch: das Display soll beim Einschalten schon in der eigenen Farbe leuchten, bevor das Startbild kommt, nicht erst, wenn
BLECH seine Einstellungen von der Karte liest. Auf der blauen geht das nicht vor dem Startbild, dort kommt die Farbe etwas später,
solange das Startbild noch steht (Abschnitt Blau).

## Zeitlinie rot (gemessen, Hacktribe und Korgs Original gleich)

| Emulator-ms | Was |
|---:|---|
| 52,52 | die Firmware schaltet Rot, Grün und Blau ein (`0xC002ABEC` bis `0xC002AC04`, über `0xC0016C98`, `0xC0016CE0`, `0xC0016D28`), weiß |
| 52,85 | Aufruf des Startbilds (`0xC002AC38`), mit dem Startbild-Editor gezeichnet erst später |
| 56,05 | das Flash-Objekt entsteht (`0xC0029A40` aus `0xC002AD44`: Speicher holen, Treiber anlegen) |
| 59,08 | erstes Lesen des Flash durch die Firmware (Kennung bei `0x220000`, `0xC0029D78` aus `0xC00289D4`) |
| 59,16 | `0xC00289D8`: hier sind die gehaltenen Tasten schon bekannt (mit EXIT steht `0x2000` an `*0xC033E6F8 + 0x18`) |
| 59,34 | erstes Bild: das Startbild (`0xC003F650`, mit EXIT bei 59,25) |
| 72,57 | die Globals werden aus dem Flash geladen (`0xC004BE8C`, `0x230000`, 256 Byte) |
| 99 | erste Frage nach der Karte |
| 143 und 304 | die Firmware schaltet das Licht noch zweimal ein (über `0xC0028AB4(0)`) |
| 346 | der frühe Haken des Menüs liest die Einstellungen von der Karte, erst ab hier galt die Farbe bisher |

- **Gemessen:** Die Karte ist vor dem Startbild nicht lesbar: die erste Kartenfrage kommt bei 99 ms, das Startbild bei
  59,34 ms. Früher als der Ladebefehl lässt sich die Einstellungsdatei ohnehin nicht öffnen
  ([früher Look](2026-10-16-blech-look-frueh.md)).
- **Gemessen:** Die Globals im RAM kommen erst bei 72,57 ms, also auch nach dem Startbild. Der Flash selbst antwortet ab
  dem ersten Lesen der Firmware (59,08 ms), vor dem Startbild.
- **Offline:** Das Flash-Objekt früher anzulegen (vor 56 ms) hieße, die Reihenfolge der Speicheranforderungen beim Start zu
  ändern; danach lägen alle späteren Objekte an anderen Adressen. Das ist ausgeschlossen.

## Wo die Farbe im Flash liegt

- **Offline:** Der Globals-Block bei `0x230000` (256 Byte, Marke `GLED` bei `+0xFC`) wird von der Firmware selbst gespeichert,
  beim Ausschalten und bei WRITE auf Global ([Globals](2026-10-13-globals-zurueckgesetzt.md)). Kein Update schreibt dort.
- **Gemessen:** Die Bytes 44 bis 251 ändert kein Menü der Firmware, in der Vorgabe der Firmware sind sie 0
  ([Global-Felder](2026-10-14-global-felder.md)). Das Objekt hinter `*0xC0691324` trägt den Block ab `+4`; BLECH zählt seine
  Global-Bytes in diesem Objekt (Init-Pattern 247, letztes Pattern 248 und 249, im Flash die Bytes 243 bis 245).
- Die Farbe liegt in **Global-Byte 250**, im Flash Byte 246 des Blocks (`0x2300F6`): `0x80` plus die Pins der Farbe
  (`0x08` rot, `0x10` grün, `0x20` blau), jeder andere Wert heißt Weiß der Firmware. Kein eigener Schreibweg in den Flash:
  BLECH setzt nur das Byte im RAM, die Firmware speichert es mit den Globals.

## Der Patch

- **Gesetzt:** wenn das Menü die Einstellungen liest und wenn WRITE im Menü BLECH sie auf die Karte schreibt, also genau die
  Farbe, die auch in der Datei steht. Eine Änderung ohne WRITE ändert das Byte nicht.
- **Start:** ein Haken bei `0xC00289D8` (`cmp r0, #0x124`, hinter dem ersten Lesen des Flash, nur auf dem Weg des normalen
  Starts, die Startmodi zweigen vorher ab; auf der blauen `0xC0025E48`, Abschnitt Blau) prüft Panel, EXIT und Panel-Update, liest 12 Byte ab `0x2300F4` über die
  Lesefunktion der Firmware (`0xC0029A74`), prüft `GLED` und das Byte und setzt nur die drei Pins.
- **Bis zum Scharfschalten:** die Haken der drei Lichtfunktionen lassen einen Kanal, den die Farbe dunkel hält, auch bei den
  Einschaltaufrufen der Firmware (143 und 304 ms) aus.
- **Ohne Einstellungsdatei:** scharf geschaltet geht das Licht zurück auf Weiß, wie es das Menü dann zeigt.
- **Grenze:** vor dem Scharfschalten gibt es nur an und aus je Kanal, danach übernimmt die Software-PWM des Menüs (bis etwa 350 ms).
- **Regel für die Pins** (`boot_light_save`, Stand 2026-10-30): ein Kanal ist an, wenn sein Pegel mindestens halb so groß ist wie der
  des stärksten (`2 * Pegel >= Maximum`), der stärkste ist immer an, eine Farbe 0 0 0 ist das Weiß der Firmware. Vorher waren alle
  Kanäle mit Pegel über 0 an, eine Farbe mit drei von null verschiedenen Pegeln startete also weiß (siehe Abschnitt Gerätebericht).

## Fälle (`tools/emu/menu_cases.py`, `boot_light_cases`, Teil von `early_look_cases`)

Gemessen mit Hacktribe 2.02, Korgs roter und Korgs blauer 2.02 mit BLECH, Einstellungsdatei mit Rot (15, 0, 0). Auf der blauen
steht statt des zweiten Falls `colour_while_the_start_image` (Abschnitt Blau), Karte ohne Einstellungsdatei heißt dort Rot ab
64,78 ms statt beim Startbild:

| Fall | Ergebnis |
|---|---|
| Einstellungen gelesen: Global-Byte 250 ist `0x88`; nach dem Ausschalten steht `0x88` im Flash bei `0x2300F6` | ja |
| nächster Start: Weiß bei 52,52 ms, Rot bei 59,25 ms, Startbild bei 59,44 ms mit roten Pins | ja |
| Rot bleibt durch die Einschaltaufrufe der Firmware bis zum scharfen Menü | ja |
| EXIT beim Einschalten: Weiß beim Startbild und danach, das Menü bleibt unscharf | ja |
| Karte ohne Einstellungsdatei: Rot beim Startbild, Weiß, sobald das Menü scharf ist | ja |
| Grün gewählt, WRITE: das Byte wird `0x90` | ja |

**Gemessen:** `tools/emu/check.py --quick` (Start, Rettungswege, Startphase) ist für Hacktribe, Korgs rote und Korgs blaue 2.02 mit BLECH grün.

## Blau

- **Gemessen** (Korgs blaue 2.02 mit BLECH): Licht an (Weiß) bei 44,72 ms, das Startbild zeichnet die Firmware bei 45,15 ms selbst,
  das Flash-Objekt entsteht erst bei 61,59 ms, das erste Lesen bei 64,61 ms (`0xC00270BC` aus `0xC0025E40`, dieselbe Stelle wie
  `0xC00289D4` auf der roten). Vor dem Startbild ist der Flash auf der blauen also nicht lesbar.
- **Gemessen:** Das Startbild steht lange genug: am Display (was über SPI ankommt, in 1-ms-Schritten) ist es ab 59 ms zu sehen und
  bleibt bis 396 ms, dann wird das Display leer, bei 516 ms kommt der Hauptbildschirm. Zwischen 92 und 94 ms ändern sich nur
  wenige Pixel.
- **Gemessen:** Die Firmware der blauen lässt Global-Byte 250 auch in Ruhe: Vorgabe 0 im RAM, nach dem Ausschalten 0 im Flash bei
  `0x2300F6`, `GLED` bei `0x2300FC` wie auf der roten.
- **Der Haken:** `0xC0025E48` (`cmp r0, r3`, hinter dem ersten Lesen des Flash, `r3` ist die Kennung `0x123`) ruft dieselbe
  Funktion wie der Haken der roten (`boot_light_set` in `tools/patch/script_boot_light.s`, mit den Flash-Funktionen der blauen
  `0xC0026DAC` und `0xC0026DE0`). Die Haken der Lichtfunktionen und das Speichern sind auf beiden gleich.
- **Gemessen** (`boot_light_cases`): Rot ab 64,78 ms, Startbild am Display von 60 bis 396 ms, Rot bleibt bis zum scharfen Menü,
  EXIT bleibt Weiß, ohne Einstellungsdatei Weiß ab 306,71 ms, WRITE von Grün macht das Byte `0x90`.
- **Hergeleitet:** Auf der blauen leuchtet das Startbild rund 5 ms Emulatorzeit weiß (59 bis 64,8 ms), dann in der Farbe.

## Gerätebericht 2026-10-30: Start blieb weiß

Rote Electribe, Hacktribe, Entwicklungsstand 1.3.8: HUE 15, SAT 13, BRIGHT 14, INTENSITY 15, DISPLAY INVERT an; das Licht blieb beim
Startbild weiß, auch nach WRITE auf Global und im BLECH-Menü und nach dem Ausschalten.

- **Gemessen** (Emulator, Hacktribe 2.02 mit BLECH): die Seiten HUE 15, SAT 13, BRIGHT 14 speichern Rot, Grün, Blau = 14, 13, 2
  (über die Seiten gedreht). Alle drei sind über 0, `M_BL_ON` ist `0x38`.
- **Gemessen:** mit genau diesen Werten (und INVERT an) in der Einstellungsdatei: Global-Byte 250 ist `0xB8` (alle drei Pins), nach
  dem Ausschalten steht `0xB8` im Flash, der Haken läuft (59,44 ms Startbild mit Pins `0x38`). Also kein Fehler im Schreibweg (b),
  und INVERT oder Version 2 der Datei ändern nichts; der Haken läuft auf dem Stand (c). Ursache ist (a): drei Kanäle an sind Weiß.
- **Behoben:** die Regel für die Pins oben. 14, 13, 2 startet als Rot und Grün (Gelb, Pins `0x18`, Byte `0x98`).
  Fälle `hsv_15_13_14_byte`, `pins_follow_the_strongest`, `his_colour_starts_yellow` in `boot_light_cases`.
- **Offen:** am Gerät nicht geprüft.

## Offen

- Am Gerät nicht geprüft: ob die rund 7 ms Weiß vor der Farbe (52,5 bis 59,2 ms Emulatorzeit) zu sehen sind.
- Wird das Gerät ohne Ausschalten vom Strom getrennt, speichert die Firmware die Globals nicht; der nächste Start zeigt dann
  die Farbe vom letzten Ausschalten.
- Am Gerät nicht geprüft: ob die rund 5 ms Weiß des Startbilds auf der blauen zu sehen sind.
