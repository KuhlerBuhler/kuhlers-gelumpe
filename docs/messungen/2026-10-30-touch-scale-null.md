# TOUCH SCALE RANGE 0: X spielt nur den Grundton (30.10.)

Stand 30.10.2026, Emulator mit Hacktribe 2.02, Korgs rotem 2.02 und Korgs blauem 2.02, jeweils ohne und mit BLECH. Wunsch: ein
Wert 0 auf der Seite TOUCH SCALE RANGE; dann spielt X auf dem Touchpad überall den Grundton des Patterns (Vorgabe C4), die Oktave
der Tastatur (KEYBOARD + 1 oder 4) gilt weiter, Y bleibt wie es ist, mit Touch Scale allein und mit Gate Arp + Touch Scale. Patch
`data/patches/touch-scale-zero.json` (rot) und `data/patches/touch-scale-zero-synth.json` (blau), Bauer
`tools/patch/touch_scale_zero.py`, Fälle `tools/emu/touch_scale_zero_cases.py`. Am Gerät nichts getan.

Marker: **gemessen** heißt im Emulator ausgeführt und gesehen (die Stellen im Code dazu gelesen), **hergeleitet** heißt aus dem
Code geschlossen, **ungeprüft** heißt offen, vor allem am Gerät.

## Wo der Wert liegt

| Befund | Marker |
|---|---|
| Der Umfang ist ein Global, kein Pattern-Wert: Byte 38 des Global-Blocks (`global.touchScaleRange`), 1 bis 4 = Oktaven ([Global-Felder](2026-10-14-global-felder.md)). Patterns und `pattern.touchScale` tragen ihn nicht | gemessen |
| Getter `0xC0047544` (`ldrb r0, [r0, #0x2a]` am Global-Objekt, `+4` ist der Block), Setter `0xC004754C` | gemessen |
| Die Firmware kopiert den Wert beim Start und bei jeder Änderung (`0xC009A8B8`) in das Touch-Scale-Objekt `0xC06911E4`, Wort `+0x14`. Beim Spielen liest nur die Abbildung unten dieses Wort, das Global-Byte nicht | gemessen |
| `+0x18` im selben Objekt ist die Oktave der Tastatur: 4 nach dem Start, KEYBOARD + 4 gibt 5, KEYBOARD + 1 dreimal gibt 3 | gemessen |
| Seite 12/20 TOUCH SCALE RANGE: Wertänderung `0xC007A924` (Getter, plus Drehung, `cmp r1, #0; movle r1, #1`, `cmp r1, #4; movge r1, #4`, Setter) | gemessen |
| Die Anzeige formatiert die Zahl selbst: mit 0 im Byte zeigt die Seite `0 Oct`, ohne Änderung am Text | gemessen |
| Vorgabetabelle der Firmware (`0xC00CFE58` rot, `0xC00BA7B0` blau): Byte 38 ist 1. Die Firmware prüft beim Laden nur `GLED`, nicht den Bereich | gemessen |
| Blau: Abbildung `0xC005710C`, Klemme `0xC006D2C4`, Objekt `0xC056B4C4`, jeweils dieselben Befehle | gemessen |

## Wie X zur Note wird

Abbildung bei `0xC0060654` (blau `0xC005710C`), `r4` ist das Touch-Scale-Objekt, `r0` die Zahl der Stufen der Tonleiter:

    slots  = Stufen x Umfang + 1
    stufe  = X(0 bis 127) x slots / 128
    oktave = stufe / Stufen + Oktave der Tastatur
    ton    = stufe % Stufen

Noten am MIDI-Ausgang, Touch Scale allein, Startpattern, Tonart C, Oktave 4, X = 0, 128, ..., 1023 (gemessen, rot und blau gleich):

| Umfang | Noten |
|---|---|
| 1 | 48 50 51 53 55 57 58 60 60 |
| 2 | 48 50 53 57 60 63 67 70 72 |
| 3 | 48 51 57 62 67 70 75 81 84 |
| 4 | 48 53 60 65 72 79 84 91 96 |
| 0 (Wort im Objekt gesetzt) | 48 an jeder Stelle |

- Korgs Firmware spielt mit Umfang 0 also schon einen festen Ton: einen Slot, Stufe 0, den Grundton. Aber in der Oktave **unter**
  der Tastatur: 48 (C3), wo KEYBOARD Pad 1 die 60 (C4) spielt. Nach KEYBOARD + 4 sind es 60 und 72. (gemessen)
- Gate Arp + Touch Scale (GATE ARP aus Touch Scale, Modus 3) geht durch dieselbe Abbildung: mit Umfang 0 wiederholt der Arp die
  Note des Pads (60) und die 48. (gemessen)
- Ein gespeicherter Wert 0 im Flash (Global-Block bei `0x230000`): Korgs Firmware lädt ihn, das Objekt hat 0, das Touchpad spielt 48,
  keine Assertion, in allen drei Builds. (gemessen)

## Der Patch

- Klemme: `movle r1, #1` wird `movle r1, #0`. Die Seite geht von 4 bis 0 und bleibt dort stehen, nach oben bis 4. (gemessen)
- Abbildung, 11 Worte am Platz, kein eigener Code:

      ldr  r7, [r4, #0x14]     Umfang
      ldrh r3, [r4, #0x30]     X
      muls r7, r0, r7          Z bei Umfang 0
      and  r5, r0, #0xff       Stufen
      add  r7, r7, #1
      and  r7, r7, #0xff       slots
      mul  r7, r3, r7
      lsr  r7, r7, #7          vorher lsl #9, lsr #16
      moveq r7, r5             Umfang 0: stufe = Stufen, also Oktave + 1, Ton 0
      mov  r1, r5
      mov  r0, r7

  `lsl #9` dann `lsr #16` ist für jedes Produkt unter 2^23 dasselbe wie `lsr #7`; das Produkt ist höchstens 127 x 255. Das schafft
  den Platz für `moveq`. (hergeleitet; die Tabelle oben kommt mit dem Patch unverändert heraus, gemessen)
- Mit Umfang 0 spielt X also den Grundton in der Oktave der Tastatur: C4 (60) nach dem Start, C5 (72) nach KEYBOARD + 4, C3 (48)
  nach KEYBOARD + 1 zweimal. Tonart D gibt D4 (62), A gibt A4 (69). (gemessen)
- Gate Arp + Touch Scale mit Umfang 0 und Tonart D: der Arp spielt Pad-Note 60 und 62, Y ändert weiter die Länge (mittlere Länge der
  62 bei Y 100 etwa 10 ms, bei Y 900 etwa 110 ms). (gemessen)
- Ein gespeicherter Wert 0 kommt nach dem Einschalten wieder: Global-Byte 0, Objekt 0, Touchpad spielt 60. (gemessen)
- Kein Haken, keine Startphase, kein RAM, kein Schalter. EXIT beim Einschalten ändert daran nichts, die Befehle sind fest im Image.
  (hergeleitet)

## Alte Dateien und Korgs Firmware

- Das Menü der Firmware lässt 0 nicht zu, also steht in keinem Global-Block eines Geräts und keiner `.e2sallpat` eine 0, solange sie
  nicht mit BLECH gesetzt wurde. Patterns sind nicht betroffen, der Wert ist global. Werte 1 bis 4 spielen wie bisher. (hergeleitet,
  die Gleichheit von 1 bis 4 gemessen)
- Ein Global-Block mit 0 auf Korgs Firmware ohne BLECH (Rückweg, oder Import All Pattern einer Datei, die mit BLECH gespeichert wurde):
  X spielt den Grundton eine Oktave tiefer (C3). Auf der Seite gibt VALUE nach oben 1, nach unten bleibt die Klemme bei 1.
  (Ton gemessen, Seite hergeleitet aus der Klemme)
- Ein Wert über 4 (nur über SysEx möglich) ändert sich durch den Patch nicht. (hergeleitet)

## Ungeprüft

- Alles am Gerät: Klang, ob `0 Oct` am Display so stehen bleibt, Gate Arp mit Y, Patternwechsel mit anderer Tonart.
- Ob WRITE oder das Ausschalten den Wert 0 im Flash so ablegt wie im Emulator.
