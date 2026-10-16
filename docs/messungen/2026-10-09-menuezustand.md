# Menüzustand im RAM: welcher Bildschirm, welche Seite

Stand 2026-10-09. Gemessen im Emulator (`tools/emu/machine.py`) mit der
eigenen SYSTEM.VSB (Sampler 2.02 mit Hacktribe) und dem eigenen Flash
(`2026-10-09-flash-dump.md`); Bedienung über Panel-Nachrichten
(`data/panel.mjs`). Am Gerät noch nicht gegengeprüft; dafür liest
`tools/device/screen_check.py` dieselben Stellen nur lesend aus.

## Weg

- **Gemessen:** `0xC03404C0` enthält einen Zeiger auf den
  Bildschirm-Verwalter, hier immer `0xC06C2210` (mit Flash-Dump und ohne).
- **Gemessen:** Im Verwalter stehen
  - `+0x20` der Zeiger auf den aktuellen Bildschirm,
  - `+0x24` der Zeiger auf ein eingeblendetes Fenster, sonst 0,
  - `+0x2C` die Nummer des Bildschirms (Tabelle unten),
  - `+0x30` die Art des Fensters: 23 beim IFX-TYPE-Fenster, in den übrigen
    gemessenen Zuständen 46.
- **Gemessen:** Im Bildschirm-Objekt steht an `+0x00` seine Klasse
  (vtable-Zeiger) und an `+0x2C` die Seite innerhalb der Gruppe. Die Seite
  zählt nur in den Menügruppen Pattern und Part; anderswo steht 0 oder ein
  Zeiger.
- **Gemessen:** Die Bildschirm-Objekte liegen je nach Ablauf an anderen
  Stellen im Heap (nach dem IFX-TYPE-Fenster an `0xC06CB2E0` statt
  `0xC06CA6A0`). Gültig ist nur der Weg über `0xC03404C0`.

## Bildschirm-Nummern

Gemessen durch Blättern mit Edit ► vom ersten bis zum 29. Menüeintrag.

| Nummer | Bildschirm | Klasse | Seiten |
|---:|---|---|---|
| 1 | Hauptbildschirm | `0xC00E3498` | |
| 3 | Menü Pattern | `0xC00E36E8` | 0 bis 14 |
| 7 | Menü Part | `0xC00E35C8` | 0 bis 7 |
| 8 | Menü Global | `0xC00E3440` | |
| 10 | Menü Event | `0xC00E33B0` | |
| 14 | Menü Data Util | `0xC00E3240` | |
| 18 | Name eingeben (SHIFT + WRITE) | `0xC00E3780` | |
| 19 | Menü Step | `0xC00E3B80` | |
| 21 | Menü Part Util | `0xC00E3658` | |
| 37 | Menü Sample | `0xC00E39C8` | |

Seiten im Menü Pattern: 0 BPM, 1 SWING, 2 BEAT, 3 LENGTH, 4 PATTERN LEVEL,
5 MFX TYPE, 6 CLEAR MFX MOTION, 7 KEY, 8 SCALE, 9 CHORD SET, 10 GATE ARP,
11 ALTERNATE 13-14, 12 ALTERNATE 15-16, 13 CHAIN TO, 14 CHAIN REPEAT.

Seiten im Menü Part: 0 LAST STEP, 1 GROOVE TYPE, 2 GROOVE DEPTH,
3 VOICE ASSIGN, 4 PART PRIORITY, 5 MOTION SEQ, 6 TRG. PAD VELOCITY,
7 SCALE MODE.

- **Gemessen:** Wird IFX TYPE gedreht, bleibt Nummer 1 (Hauptbildschirm),
  und das Fenster mit Klasse `0xC00E3538` erscheint unter `+0x24`. Nach
  rund 3 s ist es wieder weg.
- **Gemessen:** Das Menüobjekt der Pattern-Gruppe (`*0xC0348870`) hält die
  zuletzt gewählte Pattern-Seite an `+0x480` auch nach EXIT; für den
  aktuellen Zustand taugt es nicht.

## Aktuelles Pattern und aktueller Part

- **Gemessen:** `0xC033E6A4` zeigt auf das bearbeitete Pattern,
  `0xC06B2798`; hinter vier Byte Kopf beginnt bei `0xC06B279C` der
  Pattern-Block mit `PTST`. Ein Patternwechsel mit dem VALUE-Regler lädt
  ein anderes Pattern in denselben Puffer, der Zeiger bleibt. Am Gerät lag
  das Pattern am 8.10. an derselben Adresse
  (`2026-10-08-geraeteprotokoll.md`).
- **Gemessen:** `*0xC0348880 + 0x14` ist der gewählte Part, 0 bis 15. Er
  folgt Part ◄/► (nach 15 kommt 0) und dem Pad im Trigger-Modus und bleibt
  im Menü und nach einem Patternwechsel erhalten.
- **Gemessen:** Im Pattern-Block zeigt Byte 61 den Master-Effekt und
  Byte `0x800 + 33 + Part × 0x330` den Insert-Effekt des Parts, jeweils als
  Platz im Menü ab 0. Das Display zeigt den Platz plus 1: Byte 1 ist
  „02 Tape Delay“, Byte 17 im ersten Part „18 Delay 1/4“, Byte 15 im
  zweiten „16 Band Plus Filter“. Dieselben Nummern hat der Effekte-Bereich
  für die Slots der geladenen VSB.

## Änderung im RAM und Display

- **Gemessen:** Auf der Seite MFX TYPE wurde der Name von MFX 2 über die
  emulierte DIN-MIDI geschrieben (Adresse, dann Daten, beide mit `0x21`
  bestätigt). Das Display zeigt danach weiter den alten Namen. Erst wenn
  die Seite neu aufgebaut wird, steht der neue da.
- **Gemessen:** EXIT und dann MENU bauen dieselbe Seite neu auf, weil das
  Menü die zuletzt offene Seite behält. Die 16 KiB des Pattern-Puffers
  bleiben dabei unverändert. VALUE +1 und -1 bauen sie auch neu auf,
  stellen aber kurz den Master-Effekt des Patterns um.

## Display im RAM

- **Gemessen im Emulator:** Die 1024 Byte ab `0xC031B310` und ab
  `0xC031B710` sind auf Hauptbildschirm, Menüseite 1 und 2 jeweils
  byte-gleich mit dem Bild, das über SPI0 ans Display geht: 8 Seiten zu
  128 Spalten, Bit 0 die oberste Zeile einer Seite. Eine Suche nach dem
  Bildinhalt im RAM findet zuerst `0xC031B310`.
- **Gemessen im Emulator, 10.10.:** 1024 Byte ab `0xC031B310` geschrieben
  stehen beim nächsten Zeitschritt auf dem Display und bleiben dort (nach
  3 s unverändert), bis die Firmware selbst neu zeichnet (nach MENU war es
  weg). Dieselben Bytes ab `0xC031B710` ändern das Display nicht.
- **Nicht gemessen:** dass das Bild am Gerät an derselben Adresse liegt.
  Die Seite sagt das neben dem Spiegel; liest sie dort Muster statt eines
  Bildschirms, ist es nicht dieselbe Adresse.

## Gegenprobe am Gerät

- **Gemessen am Gerät, 9.10. abends**, nur Gerätesuche und RAM-Lesen
  (`tools/device/screen_check.py`): `*0xC03404C0 = 0xC06C2210`,
  `*0xC0348880 = 0xC06C41C0`, `*0xC033E6A4 = 0xC06B2798`, alle drei wie im
  Emulator. Auf dem Hauptbildschirm Nummer 1, kein Fenster, Part 1,
  Master 2, Insert 17.
- **Gemessen am Gerät:** Die 1024 Byte ab `0xC031B310` ergeben als
  LCD-Bild den Hauptbildschirm des Geräts (Pattern-Nummer und -Name im
  invertierten Feld). Die Display-Adresse gilt also auch am Gerät.
- **Gemessen am Gerät** mit `screen_check.py --watch` (alle 0,2 s gelesen),
  während am Gerät bedient wurde: MENU gibt Nummer 3, Seite 0 BPM; Edit ►
  zählt die Seiten 1 bis 14 in der Reihenfolge der Tabelle oben, Seite 5
  ist MFX TYPE; danach Nummer 7 (Menü Part) mit den Seiten 0, 1, 2. EXIT
  gibt Nummer 1. Part ► setzt den Part auf 2. IFX TYPE gedreht: Fenster
  Art 23 erscheint, der Insert des Parts geht von 17 auf 18, nach rund 2 s
  ist das Fenster weg. VALUE gedreht: anderes Pattern im selben Puffer,
  Master 1 und Insert 9. Alles wie im Emulator.
