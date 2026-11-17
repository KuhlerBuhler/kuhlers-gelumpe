# BATTERY %: Ladestand in Prozent neben dem Batteriesymbol

Stand 16.11.2026, Emulator (Hacktribe 2.02, Korgs Original 2.02 rot und blau, je mit dem BLECH-Satz dieses Branches); die
Entladekurve in zwei Läufen am 16./17.11. auf einem roten Gerät. Marker: **gemessen** (im Emulator, bei der Kurve am Gerät), **gelesen** (im
Disassemblat), **hergeleitet**, **geschätzt**.

## Was gebaut ist

- Eine Seite BATTERY % in CUSTOMIZATION > DISPLAY hinter LOAD METER, Vorgabe ON. Bit 4 von Byte 7 der Einstellungsdatei
  (`MX_FLAGS2`, `FLAGS2_BATT_OFF`) bedeutet OFF, wie bei IDLE SAVE: mit der Vorgabe bleibt die Datei Version 3, Version 4 wird
  nur mit gesetztem Bit geschrieben.
- `tools/patch/script_battery.s`: `battery_frame` läuft im Frame-Haken nach `glide_frame`. Gezeichnet wird nur, wenn
  - das Gerät auf Batterie läuft (Wort +0x308 des Netzteil-Modells `*0xC03405C4` ist 0, blau `*0xC034077C`),
  - Global BATTERY TYPE auf Alkali steht (Byte 0x20 der Global-Werte, Objekt `*0xC033E6A0` +4, ist 1),
  - und der Hauptbildschirm ohne Fenster, App oder eigene Frage zu sehen ist (`load_meter_shown`, dieselbe Bedingung wie LOAD
    METER).
  Am Netzteil und mit Ni-MH wird nichts gezeichnet; was schon da stand, wird beim nächsten Bild gelöscht.
- Zustand `BATT`, 28 Byte hinter `GLIDE` in MORE (`script_hooks.py:BATT`), mit dem Stand des Kartensymbols.
- Emulator: `Machine.battery(raw)` schickt die Panel-Nachricht 6 mit einem Rohwert, `Machine.power_source(adapter)` die
  Nachricht 7 (Netzteil oder Batterie). Unit-Test `tools/emu/test_battery_feed.py`.

## Woher der Rohwert kommt

- Panel-Nachricht `06 nn` geht über `0xC0083AD8` als Ereignis Typ 7 in die Sprungtabelle bei `0xC0083510` (Typ 7 → Vtable
  +0x44) und über `0xC00837D4` und `0xC006EC88` in den Setter des Batterie-Modells `0xC0077A14` (blau `0xC006AA4C`) mit
  Rohwert `nn`. (gelesen, im Emulator auf rot und blau gemessen)
- `06 01` ist die Power-Taste. Rohwert 0 oder 1, oder ein Wert bis zur letzten Schwelle, gibt Stufe 0, auf Batterie ist das der
  Abschaltweg. Darum nimmt `Machine.battery` nur 2 bis 255 an, und das Bild ignoriert Werte unter 2. (gelesen, gemessen)
- Der Setter speichert den Rohwert als Wort bei +0x320 und bestimmt die Stufe mit der Tabelle bei +0x318 (4 Byte, absteigend):
  Rohwert > t0 gibt 4, > t1 gibt 3, > t2 gibt 2, > t3 gibt 1, sonst 0. (gelesen)
- Die Tabelle hängt am Batterietyp. Im Emulator: Alkali 127, 110, 104, 97; Ni-MH 134, 129, 124, 97. Sie wird umgestellt, wenn
  BATTERY TYPE im Global-Menü gedreht wird (Seite 14 von 21, von 0 gezählt); ein direkt geschriebenes Global-Byte stellt sie
  nicht um. Der Emulator startet mit Ni-MH. (gemessen)
- Korrektur zu [2026-11-11-plugin-api34-system.md](2026-11-11-plugin-api34-system.md): Ereignis 11 ist nicht der Rohwert,
  sondern die Kartenerkennung (GPIO 4.1 über das Objekt `*0xC00F9308` +0x19). (gemessen)
- Stufe 1 öffnet auf Batterie ein Fenster der Firmware (Low Battery), das bis EXIT stehen bleibt und erst wieder kommt, wenn
  die Stufe vorher auf 2 oder mehr war. Solange es offen ist, zeichnet BATTERY % nicht. (gemessen)

## Rechnung

- Glättung: der erste Wert gilt sofort; danach rückt der geglättete Wert (mal 256) alle 250 ms um ein Achtel des Abstands zum
  Rohwert vor, ab einem Abstand unter 8/256 springt er ganz hin.
- Ort zwischen leer und voll in Promille: (geglättet - leer) * 1000 / (voll - leer), auf 0 bis 1000 begrenzt; leer ist
  die letzte Schwelle der Tabelle, die die Firmware gerade nutzt (97, dort schaltet sie aus), voll ist fest 160 (`BP_FULL`).
  Korgs volle Schwelle 127 taugt nicht als 100 %: frische Alkali-Zellen lesen 162 bis 163, und bis 127 vergeht über eine
  Stunde, die Anzeige stünde so lange auf 100 %. 160 liegt knapp unter frischen Zellen, damit auch etwas schwächere neue
  Zellen bei 100 % anfangen.
- Daraus die Ladung über die Kurve `batt_curve` (11 Stützpunkte, dazwischen linear), auf 10 % gerundet.
- Hysterese: der angezeigte Wert ändert sich erst, wenn die neue Ladung mehr als 8 % (80 Promille) von ihm weg ist. Ein
  kurzer Einbruch oder Rauschen um eine Stufengrenze lässt ihn stehen.
- Die elf Werte von `batt_curve` kommen aus zwei Entladungen am Gerät (Abschnitt Entladekurve). Davor war die Kurve eine
  Gerade zwischen Korgs Alkali-Schwellen 97 und 127, danach (#659) gemessen, aber noch mit 127 als voll.

## Entladekurve

Zwei Läufe auf einem roten Gerät (HT-Basis, BLECHTRIBE-Testbuild), je vier Alkaline AA, Global AUTO POWER OFF aus, POWER
SAVE an, USB zum Auslesen gesteckt (das Gerät lief trotzdem auf Batterie, +0x308 war 0). Einmal pro Minute nur gelesen (BLECH
READ): Rohwert +0x320 und Stufe +0x328 des Batterie-Modells.

**Lauf 1** (16./17.11.), Rubin Alkaline, nicht frisch (das Batteriesymbol zeigte schon einen Strich weniger), Hauptbildschirm,
kein Abspielen, bis zum Ausschalten:

| Minute | Rohwert | Stufe |
|---|---|---|
| 0 | 123 | 3 |
| 4 | 118 | 3 |
| 11 | 115 | 3 |
| 23 | 112 | 3 |
| 34 | 110 | 2 (ab hier) |
| 51 | 106 | 2 |
| 61 | 104 | 1 (ab hier, Low Battery) |
| 74 | 100 | 1 |
| 80 | 98 | 1 |
| 81 bis 82 | | aus |

(gemessen) Der letzte gelesene Rohwert vor dem Ausschalten war 98; ob 97 noch kurz anlag, zeigt das Minutenraster nicht. Die
Warnung Low Battery kam etwa 21 Minuten vor dem Ausschalten.

**Lauf 2** (17.11. abends), frische Zellen, beim Einlegen 162 bis 163, dabei wurde gespielt und aufgenommen. Nach 94 Minuten
endete der Lauf durch ein Firmware-Update, die Zellen wurden nicht leer gefahren:

| Minute | Rohwert | Stufe |
|---|---|---|
| 0 | 162 | 4 |
| 2 | 160 | 4 |
| 6 | 155 | 4 |
| 14 | 150 | 4 |
| 25 | 145 | 4 |
| 47 | 140 | 4 |
| 63 | 137 | 4 |
| 75 | 135 | 4 |
| 92 | 132 | 4 |

(gemessen) Stufe 4 heißt über Korgs Schwelle 127, den Wechsel auf 3 hat der Lauf nicht mehr erreicht.

Daraus `batt_curve`: für jeden Stützpunkt (Rohwert 97 + 6,3 pro Schritt bis 160, das sind 0, 10, ... 100 % des Wegs von leer
nach voll) der Anteil der Laufzeit, der ab dem ersten Erreichen dieses Rohwerts noch bleibt, in Promille. Die Zeitachse ist
zusammengesetzt: 160 bis 132 aus Lauf 2 (90 Minuten), 132 bis 123 **geschätzt** (22 Minuten, mit den zuletzt gemessenen
0,4 pro Minute), 123 bis aus aus Lauf 1 (83 Minuten); zusammen etwa 195 Minuten (geschätzt).

| Rohwert | 97 | 103 | 110 | 116 | 122 | 129 | 135 | 141 | 147 | 154 | 160 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Promille | 0 | 97 | 221 | 369 | 421 | 488 | 626 | 795 | 908 | 974 | 1000 |

- 97 bis 116 und 135 bis 160 gemessen, 122 und 129 liegen im geschätzten Stück oder an seinem Rand.
- Die Läufe hatten verschiedene Last: oben mit Spielen, unten ohne. Ohne Spielen hält der untere Teil länger, er bekommt
  dadurch etwas mehr Anteil, als er mit Spielen hätte. Die Anzeige ist unten eher zu großzügig (hergeleitet).
- Unter Last sackt die Spannung, der Rohwert liest beim Spielen niedriger und erholt sich danach. Ausgeglichen wird das nur
  durch Glättung und Hysterese, nicht herausgerechnet (das Gerät misst keinen Strom).

## Platz in der Statusleiste

Gemessen auf allen drei Builds, Seite 0 des Bildschirmspeichers (Zeilen 1 bis 7, Zeile 0 bleibt der Firmware). Vorher:

| Spalten | Inhalt |
|---|---|
| 50 bis 74 | BPM |
| 75 bis 108 | auf dem Hauptbildschirm frei (Ruhe, Regler, Tasten, PLAY, REC, Motion-Aufnahme, STOP, Netzteil) |
| 84 bis 97 | in den Menüs das EDIT-Symbol (Bild 0x0B ab x 84, `0xC0085438`); auf dem Hauptbildschirm zeichnet die Firmware es beim Betreten und bei jedem Neuzeichnen in der Löschfarbe, das löscht 84 bis 97 |
| 109 bis 114 | Kartensymbol |
| 117 bis 127 | Batteriesymbol (leeres Bild 117 bis 127) |

Korrektur zur ersten Fassung: 75 bis 99 sind nicht "nie benutzt", das EDIT-Symbol belegt 84 bis 97 in den Menüs und löscht
sie auf dem Hauptbildschirm. (gemessen)

Belegung jetzt, auf dem Hauptbildschirm, gleich ob BATTERY % gerade gezeigt wird oder nicht:

| Spalten | Inhalt |
|---|---|
| 86 bis 93 | LOAD METER (zwei Ziffern) |
| 94 bis 99 | Kartensymbol |
| 100 | frei |
| 101 bis 115 | BATTERY %: vier Felder zu je 3 Spalten und einer leeren, rechtsbündig (Hunderter ab 101, Zehner ab 105, Einer ab 109, `%` ab 113), "100%" passt ganz hinein |
| 116 | frei (die leere Spalte des `%`) |
| 117 bis 127 | Batteriesymbol |

In allen anderen Bildschirmen (Menüs, GLOBAL PARAMETERS, die WRITE-Frage, Blechy) bleibt das Kartensymbol bei 109, sonst
läge es über dem EDIT-Symbol. Seiten ab 1 sind der Rahmen der Box und darum nicht nutzbar. Geschrieben werden nur Bytes, die
sich geändert haben, und nur dann wird der Bereich als geändert markiert.

## Kartensymbol

- Das Objekt baut `0xC008C8B4` (blau `0xC007B308`): x bei +4 (109), y +8 (1), Breite +0xC (6), Höhe +0x10 (8), "neu zeichnen"
  +0x14, Karte drin +0x48. Sein Zeichnen (Vtable +8, `0xC008C7D4`) löscht das Rechteck, wenn +0x14 gesetzt ist, und malt Bild 6
  bei x, y, wenn eine Karte drin ist. Es ist das dritte Objekt der Statusleiste: `[[SCREEN_MANAGER] + 0x4C]`. (gelesen)
- `card_widget` holt es zur Laufzeit über diesen Zeiger, ohne feste Adresse pro Build, und nimmt es nur mit Breite 6, Höhe 8
  und x 109 oder 94.
- `card_place` im Haken von SWITCH_SCREEN (`autosave_switch_hook`): für den Hauptbildschirm (1) x = 94, sonst 109. Ändert sich
  x, wird +0x14 gesetzt und die alte Stelle gelöscht (GLOBAL PARAMETERS löscht sie selbst nicht).
- Der Wechsel wird nur eingereiht, der Bildschirm-Manager zeigt ihn später. `card_frame` wartet darum bis zu 300 ms, bis der
  angekündigte Bildschirm da ist, und stellt sonst nichts um.
- `card_frame` im Frame-Haken: auf dem Hauptbildschirm zeichnet es die Karte bei 94 neu, wenn +0x14 gesetzt ist, die Spalten
  94 bis 99 nicht mehr so aussehen wie nach dem letzten Zeichnen (das Löschen durch EDIT) oder die Karte inzwischen gesteckt
  oder gezogen wurde. Letzteres braucht es auf blau: dort zeichnet das Stecken den Hauptbildschirm neu, das EDIT-Löschen nimmt
  die gerade gemalte Karte wieder weg, und die Spalten sehen danach aus wie vorher. Außerhalb des Hauptbildschirms stellt es
  ein übrig gebliebenes x 94 auf 109 zurück (für einen Wechsel ohne SWITCH_SCREEN).
- Beim Betreten des Hauptbildschirms ist die Karte für ein Bild weg (Firmware malt, EDIT löscht, `card_frame` malt neu). Im
  Emulator nicht sichtbar, am Gerät zu prüfen.

## Lastanzeige nach Blechy

Vorher (develop) zeichnete LOAD METER nach dem Schließen von Blechys App nicht mehr: `SCRIPT_CONTROL_DISPLAY_ACTIVE` bleibt
nach dem Schließen 1. `load_meter_shown` verlangt jetzt zusätzlich eine offene App (`APP_STATE` nicht 0), wie
`script_display_blit`. Davon hängt auch das Kartensymbol bei 94 ab. (gemessen)

## Belegtabelle

| Behauptung | Beleg | Marker |
|---|---|---|
| Mit Ni-MH wird nichts gezeichnet | `battery_percent_cases.py:hidden_with_nimh` | gemessen |
| Auf Batterie mit Alkali steht der Wert der Kurve, als Glyphen | `shown_on_alkali_battery` | gemessen |
| Werte von knapp über leer bis über voll geben 0 bis 100 in Zehnerschritten | `steps_of_10` | gemessen |
| Ein Einbruch für einen Schritt lässt den Wert stehen, ein dauerhafter Anstieg läuft in Stufen bis 100 | `smoothed` | gemessen |
| Am Netzteil sofort weg, zurück auf Batterie wieder da | `hidden_on_mains` | gemessen |
| Mit LOAD METER ON und Karte behalten Zahl, Lastanzeige, Karte und Batteriesymbol ihre Spalten, 100 bleibt frei | `layout_with_load_meter_and_card` | gemessen |
| Ohne Karte nichts bei 94 und 109, auch nicht nach BLECH-Menü und GLOBAL PARAMETERS | `card_none` | gemessen |
| Mit Karte nach dem Start bei 94, nicht bei 109 | `card_boot_at_94` | gemessen |
| In BLECH-Menü und GLOBAL PARAMETERS die Karte bei 109 und 84 bis 99 wie ohne Karte, zurück wieder bei 94; mit LOAD METER OFF und ON | `card_menus_load_meter_off`, `card_menus_load_meter_on` | gemessen |
| Auf dem Hauptbildschirm gezogen weg, gesteckt wieder bei 94 | `card_pull_and_insert_on_main` | gemessen |
| In der WRITE-Frage bei 109, danach bei 94 | `card_write_question` | gemessen |
| Mit Blechys App offen keine Karte bei 94, geschlossen wieder da | `card_app` | gemessen |
| OFF nimmt die Zahl beim nächsten Bild weg | `off_hides_at_once` | gemessen |
| Seite 7 von 7 in DISPLAY, Vorgabe ON, WRITE mit ON schreibt Version 3 | `page_default_on` | gemessen |
| OFF auf der Seite: zurück auf dem Hauptbildschirm keine Zahl; WRITE schreibt Version 4 mit Bit 4 | `page_off_hides_on_the_main_screen`, `write_off_is_version_4` | gemessen |
| Der nächste Start liest OFF, Bit gelöscht zeigt wieder | `next_start_reads_off` | gemessen |
| Gleiche Ergebnisse auf Hacktribe, rot und blau | je 18 von 18 Fällen | gemessen |
| Prozentwerte entsprechen der echten Restladung | Kurve ist eine Gerade | hergeleitet, offen |
| Am Gerät | nicht geprüft | offen |

```
python3 tools/emu/battery_percent_cases.py --vsb PATCHED.VSB
```
