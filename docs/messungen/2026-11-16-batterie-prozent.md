# BATTERY %: Ladestand in Prozent neben der Lastanzeige

Stand 16.11.2026, nur Emulator (Hacktribe 2.02, Korgs Original 2.02 rot und blau, je mit dem BLECH-Satz dieses Branches),
kein Gerät. Marker: **gemessen** (im Emulator), **gelesen** (im Disassemblat), **hergeleitet**.

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
- Zustand `BATT`, 16 Byte hinter `GLIDE` in MORE (`script_hooks.py:BATT`).
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
- Ort zwischen leer und voll in Promille: (geglättet - leer) * 1000 / (voll - leer), auf 0 bis 1000 begrenzt; voll ist
  die erste, leer die letzte Schwelle der Tabelle, die die Firmware gerade nutzt.
- Daraus die Ladung über die Kurve `batt_curve` (11 Stützpunkte, dazwischen linear), auf 10 % gerundet.
- Hysterese: der angezeigte Wert ändert sich erst, wenn die neue Ladung mehr als 8 % (80 Promille) von ihm weg ist. Ein
  kurzer Einbruch oder Rauschen um eine Stufengrenze lässt ihn stehen.
- **Die Kurve ist ein Platzhalter (hergeleitet, nicht gemessen):** eine Gerade zwischen Korgs Alkali-Schwellen für leer und
  voll. Eine echte Entladekurve muss am Gerät gemessen werden (Rohwert gegen Zeit bei bekannter Last); dann werden die elf
  Werte in `batt_curve` ersetzt, sonst nichts.

## Platz in der Statusleiste

Gemessen auf allen drei Builds, Seite 0 des Bildschirmspeichers (Zeilen 1 bis 7, Zeile 0 bleibt der Firmware):

| Spalten | Inhalt |
|---|---|
| 50 bis 74 | BPM |
| 75 bis 99 | auf dem Hauptbildschirm nie benutzt (Ruhe, Regler, Tasten, PLAY, REC, Motion-Aufnahme, STOP, Netzteil) |
| 100 bis 107 | LOAD METER (Ziffern ab 100) |
| 109 bis 114 | Kartensymbol |
| 117 bis 127 | Batteriesymbol (leeres Bild 117 bis 127) |

Direkt neben dem Batteriesymbol sind nur die Spalten 115, 116 und 127 frei, zu wenig für eine Zahl. Gewählt: feste Stelle
links von LOAD METER, Spalten 83 bis 98, rechtsbündig in vier Feldern zu je 3 Spalten und einer leeren (Hunderter ab 83,
Zehner ab 87, Einer ab 91, `%` ab 95), Spalte 99 bleibt als Abstand zur Lastanzeige frei. Das `%` unterscheidet die Zahl von
den nackten Ziffern der Lastanzeige. Seiten ab 1 sind der Rahmen der Box und darum nicht nutzbar. Geschrieben werden nur
Bytes, die sich geändert haben, und nur dann wird der Bereich als geändert markiert.

## Belegtabelle

| Behauptung | Beleg | Marker |
|---|---|---|
| Mit Ni-MH wird nichts gezeichnet | `battery_percent_cases.py:hidden_with_nimh` | gemessen |
| Auf Batterie mit Alkali steht der Wert der Kurve, als Glyphen | `shown_on_alkali_battery` | gemessen |
| Werte von knapp über leer bis über voll geben 0 bis 100 in Zehnerschritten | `steps_of_10` | gemessen |
| Ein Einbruch für einen Schritt lässt den Wert stehen, ein dauerhafter Anstieg läuft in Stufen bis 100 | `smoothed` | gemessen |
| Am Netzteil sofort weg, zurück auf Batterie wieder da | `hidden_on_mains` | gemessen |
| Mit LOAD METER ON und Karte behalten Zahl, Lastanzeige, Karte und Batteriesymbol ihre Spalten, 99 bleibt frei | `layout_with_load_meter_and_card` | gemessen |
| OFF nimmt die Zahl beim nächsten Bild weg | `off_hides_at_once` | gemessen |
| Seite 7 von 7 in DISPLAY, Vorgabe ON, WRITE mit ON schreibt Version 3 | `page_default_on` | gemessen |
| OFF auf der Seite: zurück auf dem Hauptbildschirm keine Zahl; WRITE schreibt Version 4 mit Bit 4 | `page_off_hides_on_the_main_screen`, `write_off_is_version_4` | gemessen |
| Der nächste Start liest OFF, Bit gelöscht zeigt wieder | `next_start_reads_off` | gemessen |
| Gleiche Ergebnisse auf Hacktribe, rot und blau | je 11 von 11 Fällen | gemessen |
| Prozentwerte entsprechen der echten Restladung | Kurve ist eine Gerade | hergeleitet, offen |
| Am Gerät | nicht geprüft | offen |

```
python3 tools/emu/battery_percent_cases.py --vsb PATCHED.VSB
```
