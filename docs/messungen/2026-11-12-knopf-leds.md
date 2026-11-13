# KNOB LEDS: Regler-LEDs ausschalten

Stand 12.11.2026, nur Emulator (Hacktribe 2.02, Korgs Original 2.02 rot und blau), kein Gerät. Marker: **gemessen** (im
Emulator), **offline gelesen** (Disassembly, Quelltext), **hergeleitet**, **offen**.

## Was es tut

BLECH > CUSTOMIZATION > LED > KNOB LEDS (letzte Seite der LED-Gruppe) schaltet die fünf LEDs hinter den Reglern VALUE,
SAMPLE/OSC, CUTOFF, MOD TYPE und IFX TYPE (LED `0x00` bis `0x04`, [LED-Inventur](2026-10-13-led-inventur.md)). ON ist die
Vorgabe und sieht aus wie die Firmware. OFF hält sie dunkel, auch wenn ein Regler gedreht wird. Alles andere bleibt, wie es
war. Gilt sofort, WRITE (oder AUTO SAVE) behält es in Bit 6 von Byte 5 der Einstellungsdatei. Mit EXIT beim Einschalten
leuchten sie wie in der Firmware.

## Wie es gebaut ist

| Teil | Wo | Marker |
|---|---|---|
| Dunkel schalten: im Haken am Ende der LED-Sendefunktion (`0xC00876A8`, Patch pad-colors) setzt `pc_knob_dark` die Helligkeit einer Regler-LED auf 0, bevor die Nachricht zum Panel geht; der Sollwert der Firmware (Manager + `0x4E` + 8 * LED) bleibt | `tools/patch/pad_colors.py` (`pt_dim_only`, `pr_dim`) | gemessen |
| Schalter: `S_KNOB` (pad-colors-Zustand + 4, `0xC018BF04`), 0 OFF, sonst ON, FF nie geschrieben (ON); Einträge +40 setzen und +44 lesen für das Menü | `tools/patch/pad_colors.py` | gemessen |
| Sofort: die Seite ruft +40 mit r1 = 1, das schickt die LEDs 0 bis 4 über die Sendefunktion der Firmware (`0xC00875F4`) neu; beim Lesen der Datei (r1 = 0) wird nichts geschickt, nur vorgemerkt wie bei den Pad-Farben | `pc_knob_set` | gemessen |
| Menü: Seite 53 KNOB LEDS als neunte Seite der LED-Gruppe, die Zeilen von `sub_kinds` sind dafür 16 statt 8 Byte breit; ohne pad-colors im Satz fehlt die Seite | `tools/patch/script_menu.s` | gemessen (Seite), hergeleitet (ohne pad-colors, kein Satz ohne den Patch geprüft) |
| Datei: Bit 6 von Byte 5. Das Bit hieß auf develop kurz HT OSC OFF (09.11., zwischen ddd28d73 und 310bf006), kein Release hat es geschrieben. 1.4.5 liest Byte 5 mit der Maske `0xFF`, eine Datei mit dem Bit bleibt dort lesbar, das Bit tut dort nichts. Keine neue Dateiversion | `script_menu.s` (`menu_settings_load`, `menu_settings_write`) | offline gelesen |

Der blaue Build nimmt dieselben Stellen über `data/synth-map/` (Sendefunktion, LED-Manager), der Code bleibt bei
`0xC018B000`.

## Prüfung

`tools/emu/menu_cases.py` (`knob_leds_cases`), je Hacktribe, rot und blau, alle 9 Fälle grün:

| Fall | Ergebnis | Marker |
|---|---|---|
| `default_on` | ohne Bit 6 leuchten die LEDs wie der Sollwert der Firmware (`[255, 255, 255, 255, 255]` im Stand) | gemessen |
| `page` | Seite `KNOB LEDS` / `ON`, Zähler 8 von 9 | gemessen |
| `off_at_once` | OFF schickt sofort `[0, 0, 0, 0, 0]`, der Sollwert der Firmware bleibt (`[155, 255, 255, 255, 255]`) | gemessen |
| `knob_turned_stays_dark` | PAN auf dem Hauptbildschirm gedreht: alle fünf bleiben 0 | gemessen |
| `on_again` | ON schickt den Sollwert der Firmware wieder | gemessen |
| `file_holds_off` | WRITE: Byte 5 = `0x41` (Bit 6 neben Bit 0 von METER LOUD RAINBOW) | gemessen |
| `start_reads_off` | Neustart mit dieser Datei: LEDs dunkel, Seite zeigt OFF | gemessen |
| `exit_held_is_stock` | EXIT beim Einschalten mit derselben Datei: LEDs wie in der Firmware | gemessen |
| `file_holds_on` | ON und WRITE: Byte 5 = `0x01` | gemessen |

`page_cases`, `orig_cases` und `pad_colour_cases` laufen mit der neuen Seite weiter grün (Hacktribe, rot, blau).

## Offen

- Am Gerät nicht geprüft: ob die LEDs mit OFF wirklich dunkel bleiben und mit ON wieder angehen, auch nach Power Save.
- VALUE leuchtet in der Firmware nur beim Drehen; mit OFF bleibt es auch dann aus (hergeleitet aus `knob_turned_stays_dark`,
  am Gerät offen).
