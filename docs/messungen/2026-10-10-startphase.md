# Startphase, Startmodi und Notschalter-Taste

Stand 2026-10-10. Gemessen im Emulator (`tools/emu/machine.py`,
`tools/emu/bootmap.py`) mit der eigenen SYSTEM.VSB (Sampler 2.02 mit
Hacktribe), mit dem eigenen Flash-Dump vom 9.10. und mit leerem Flash;
Code offline gelesen. Am Gerät nicht gegengeprüft. Zeiten sind Emulator-Zeit
(angenommene 5 ns pro Befehl): die Reihenfolge gilt, die Millisekunden
nicht genau.

## Zeitachse beim Einschalten

| Emulator-ms | Was |
|---:|---|
| 52,5 | erste Daten ans Display |
| 52,9 | Startbild gelesen (`0xC00F9854`, VSB `0xF9954`), gezeichnet über den Aufruf `0xC002AC38` → `0xC003F650` mit Bild Nr. 13 an 0,0 |
| 69,5 | Panel nach Version gefragt (`0x80`), Prüfung bei `0xC0028940` |
| 70,3 | Panel nach gehaltenen Tasten gefragt (`0x91`) |
| 74,8 | Kennung bei Flash `0x220000` geprüft (`0xC0029D78`) |
| 360,8 | Bildschirm-Verwalter meldet Bildschirm 1, die Anwendung läuft |

- **Gemessen:** Das Startbild liegt als 1024 Byte in 8 Seiten zu 128
  Spalten, Bit 7 ist die oberste Zeile einer Seite (das Display hat Bit 0
  oben). So gelesen gleicht es Pixel für Pixel dem Display bei 200 ms.
- **Gemessen:** Das Startbild kommt vor allen drei Rettungswegen
  (Panel-Update, Startmodi, Update-Abfrage). Code, der das Startbild
  zeichnet oder lädt, läuft also auch dann, wenn das Gerät gerettet werden
  soll.

## Display-Licht beim Start

- **Gemessen:** Bei 52,5 ms setzt die Firmware die Pins 6.3, 6.4 und 6.5
  (GPIO-Treiber `0xC0016B00`, gerufen über `0xC0016BF8`) und schickt ein
  ganzes Bild ans Display, bevor sie das Startbild zeichnet (Aufrufe ab
  52,85 ms, Startbild-Bild bei 65,2 ms). Einen Einschaltbefehl ans LCD
  schickt sie in den ersten 400 ms nicht, nur bei 138 ms den Kontrast
  (`0x81 0x22`); das LCD schaltet also schon der Bootloader ein.
- **Hergeleitet aus Freetribe** (`cpu/src/kernel/device/dev_lcd.c`,
  `dev_lcd_set_backlight`): GP6P3, GP6P4 und GP6P5 sind das rote, grüne und
  blaue Licht des Displays. Die Firmware schaltet alle drei an, also weiß.
- Daraus: Das Licht hängt nicht am Startbild. Fällt der Aufruf
  `0xC002AC38` weg, ist das Display ab 52,5 ms hell und leer.
- **Gemessen:** Die Firmware setzt die drei Pins mit
  `0xC0016BB4(0x01E26000, an, 3, Maske)`, Maske `0x08` rot, `0x10` grün,
  `0x20` blau. `tools/device/backlight.py` ruft genau das per Execute; im
  Emulator ändern sich damit nur diese drei Bits, alle anderen Pins des
  Paars (auch das Halten der Stromversorgung) bleiben, keine Assertion.
- **Gemessen am Gerät, 10.10. abends** (`backlight.py`, nur RAM, am Gerät
  beobachtet und fotografiert): Rot, Grün, Blau, Gelb, Cyan, Magenta und Weiß
  erscheinen wie gesetzt, das Licht wechselt sofort. Danach antwortet das
  Gerät weiter, ein Neustart bringt Weiß zurück. Jedes RAM-Schreiben zeigt
  kurz „Working...“; lädt das Skript alle Farben in einem Schreiben hoch und
  schaltet nur noch per Execute, kommt es nur beim Hochladen und beim
  Zurückschreiben. Ein und aus je Kanal, also acht Zustände; Zwischenstufen
  (Dimmen) gibt es auf diesem Weg nicht.

## Display-Licht im Betrieb

- **Gemessen im Emulator, ohne Netzteil** (Panel-Nachricht 7 = 0): Ein
  Timer-Interrupt (`0xC0025B20`) ruft alle 0,5 ms `0xC00289F4`. Ist das Byte
  `0xC00F9310` gesetzt, schaltet die Routine Rot, Grün und Blau jedes Mal
  neu (Grün und Rot kurz an, Blau aus, in 200 ms je 16 von 400 Mal an): ein
  per Software gedimmtes Licht. Gesetzt wird das Byte über `0xC0028AB4(1)`,
  beim Start bei 101 ms und 328 ms; `0xC0028AB4(0)` löscht es und schaltet
  alle drei an.
- **Gemessen im Emulator, mit Netzteil:** Das Byte bleibt 0, die Routine
  schreibt nichts, das Licht steht auf Weiß.
- Daraus, hergeleitet: Auf Batterie dimmt die Firmware das Licht durch
  schnelles An und Aus. Das passt zum Flackern in Videos (Kamera gegen
  Dimm-Takt); am Gerät nicht gemessen. Beim Farbtest hing das Gerät am USB
  und die Farben blieben stehen, die Routine lief dort also nicht.
- **Gemessen im Emulator:** Auch ein Execute zeigt „Working...“, rund 2 ms
  nach der Bestätigung für etwa 48 ms; mit Abtastung ab 50 ms war es vorher
  übersehen worden. Über das Kabel lässt sich das Licht also nicht ohne
  dieses kurze Einblenden umschalten.

## Gehaltene Tasten

- **Offline:** Die Antworten `0x91` und `0x92` tragen je ein 32-Bit-Wort,
  Byte 1 bis 4 big-endian (`0xC0028040`). `0x91` setzt das untere Wort und
  löscht das obere (`0xC0028814`), `0x92` setzt das obere (`0xC00287F4`).
- **Offline:** Das Panel-Objekt (0x28 Byte) hängt an `*0xC033E6F8`:
  - `+0x18` die gehaltenen Tasten, 64 Bit,
  - `+0x20` der Startmodus,
  - `+0x21` ein Merker, wenn nur `0x400` gehalten wurde,
  - `+0x22` gesetzt, wenn die Panel-Version nicht `0x96` ist (Panel-Update).
- **Gemessen:** Die Maske bleibt nach dem Start stehen: mit `0x2000`
  gehalten steht nach 8 s noch `0x2000` an `+0x18`. Die Firmware fragt `0x91`
  nur einmal. Außer der Startmodus-Tabelle liest kein Code `+0x18` (alle
  Stellen, die `0xC033E6F8` laden, durchgesehen).
- **Hergeleitet, nicht gemessen:** Bit n ist die Panel-Taste n aus
  `data/panel.mjs`. Dafür spricht: die Modi 1 bis 4 gehen über die vier
  benachbarten Bits 28 bis 31, das sind die Tasten 1 bis 4 mit gleichem
  zweiten Bit 27 (PATTERN SET). Am Gerät prüfbar, nur lesend: Taste beim
  Einschalten halten, dann `screen_check.py --held`.

## Startmodi

Tabelle bei `0xC002882C`: es zählt nur die genaue Maske, das obere Wort
muss 0 sein. Jede Maske im Emulator gebootet (`machine.py --held`).

| Maske | Modus | Display | Tasten (hergeleitet) |
|---|---:|---|---|
| `0x18000000` | 1 | Versionsseite `[ALL]` | PATTERN SET + 1 |
| `0x28000000` | 2 | Versionsseite `[SHIP]` | PATTERN SET + 2 |
| `0x48000000` | 3 | Versionsseite `[MAIN]` | PATTERN SET + 3 |
| `0x88000000` | 4 | Versionsseite `[PNL]` | PATTERN SET + 4 |
| `0x14000000` | 5 | Versionsseite `[EXT]` | MFX SEND + 1 |
| `0x24000000` | 6 | Versionsseite `[SERV]` | MFX SEND + 2 |
| `0x0C000000` | 7 | Tabelle `00: ---` bis `15: ---`, LEDs 76 bis 87 an | PATTERN SET + MFX SEND |
| `0x00140000` | 8 | Data Util 1/3, IMPORT PATTERN | LPF + HPF |
| `0x00000080` | 9 | Versionsseite `[XY]`, XYPad Check | MFX HOLD |
| `0x0A000000` | 11 | XY TEST, Step 1 | PATTERN SET + STEP JUMP |
| `0x00000400` | 0 | normaler Start, Merker `+0x21` | SHIFT |
| sonst | 0 | normaler Start | |

- **Offline:** Modus 10 kommt nicht aus der Tabelle, sondern aus der
  fehlenden Kennung bei `0x220000` (Update-Abfrage, `0xC00289E0`).
- **Offline:** Bei `0xC002AD74` gehen die Modi 1 bis 10 in einen eigenen
  Weg ohne die Anwendung, Modus 11 ebenso nach zwei weiteren Aufrufen,
  Modus 0 startet normal; ist `+0x22` gesetzt, läuft das Panel-Update
  (`0xC004D0E8`).
- **Offline:** Den Merker `+0x21` liest nur `0xC006B9F4`, im Ereignis-Code
  der Bildschirmklasse `0xC00E3B38`: mit Merker wechselt ein Ereignis auf
  Bildschirm 28 statt 4. Welcher Bildschirm das ist, ist offen.

## Startphase als Adressbereiche

`bootmap.py` bootet 17 Wege (normal mit eigenem und mit leerem Flash,
Update-Abfrage, Panel-Update, jeder Startmodus, die Notschalter-Taste) und
sammelt jeden Code-Block, der läuft, und jedes Byte des Abbilds, das
gelesen wird, bis Bildschirm 1 erscheint. Wege, die Bildschirm 1 nie
erreichen, zählen 1,5 s Emulator-Zeit ganz; ihr Display steht nach 1 s
und ändert sich bis 4 s nicht mehr.

- **Gemessen:** 157 072 Byte Code in 1931 Bereichen und 47 962 gelesene
  Byte in 2424 Bereichen (Tabellen, Konstanten, das Startbild). Ein
  normaler Start allein: 148 136 Byte Code. Ein Lauf über alle Wege dauert
  rund 80 s. Darin stecken auch Treiber und Hilfsfunktionen, die
  später weiterlaufen (Display, Flash, Interrupts).
- **Gemessen:** Die Blöcke kommen aus dem Übersetzungs-Hook von Unicorn
  (`UC_HOOK_EDGE_GENERATED`, einmal pro Block); ein Hook auf jede Ausführung
  findet einen Block mehr (7016 statt 7015) und braucht elfmal so lange.

## Notschalter-Taste

- **Gemessen:** EXIT (`0x2000`, Bit 13) hat keinen Startmodus. Mit EXIT
  gehalten startet die Firmware normal, das Display gleicht dem Start ohne
  Taste, und die Maske steht danach an `*0xC033E6F8 + 0x18`.
- Ein Patch kann sie also beim ersten Gebrauch lesen, ohne die Startphase
  zu ändern. Ob EXIT am Gerät wirklich Bit 13 ist: siehe oben, lesend
  prüfbar.
