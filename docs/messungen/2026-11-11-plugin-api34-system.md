# Plugin API 34: Netzteil oder Batterie, Ladestand, LEDs lesen

Stand 11. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz (`data/patches/blech.json`, für blau `blech-synth.json`). Fälle: `tools/emu/plugin_api34_cases.py` (läuft
als Gruppe von `remote_cases`). **Am Gerät nicht geprüft.** Teil 9 des Plans.

## Frage

Kann ein Plugin lesen, ob das Gerät am Netzteil oder auf Batterie läuft, wie voll die Batterie ist und was eine LED gerade zeigt,
jeweils mit dem, was die Firmware selbst hält?

## Netzteil oder Batterie

- Das Panel schickt Nachricht 7 (`07 x`). Der Panel-Verteiler `0xC002814C` stellt daraus Ereignis 6 ein (`0xC0083AAC`). Der
  Handler `0xC0083790` ruft `0xC006F36C`, das ruft `0xC007822C`, und das schreibt den Wert nach `[*0xC03405C4] + 0x308`:
  1 Netzteil, 0 Batterie. (gelesen, Disassembly rot und Hacktribe)
- Blau: das Modell steht in `*0xC034077C`, Versatz 0x308 gleich. (gelesen, Disassembly blau)
- Im Emulator kippt das Wort mit Nachricht 7, und die Firmware zeichnet dazu das Stecker-Symbol (Zeichenfunktion `0xC0084A8C`).
  (gemessen)
- `korg.system.power` liest dieses Wort über `objects_state_word` (Zeiger 0, -1 → -1). (eigener Code)

## Ladestand

- Das Batterie-Modell steht in `*0xC03405C8` (blau `*0xC0340780`), gesetzt von `0xC0077A14`: Rohwert bei +0x320, Stufe bei
  +0x328 aus einer Schwellen-Tabelle bei +0x318 (je nach Batterietyp), +0x31C ist das Freigabe-Flag. (gelesen)
- Stufen: 4, 3, 2, 1 (niedrig: die Firmware zeigt ohne Netzteil die Warnung 0x1b/0x1a), 0 (leer, Abschaltweg `0xC0028C18`).
  (gelesen)
- Quelle des Rohwerts: Ereignis 11 (Poster `0xC0083E7C`, aus der Task bei `0xC002A4B0`) nimmt Byte +0x19 des Objekts aus
  `0xC001CF0C`. Der Emulator schickt diesen Wert nie; der Setter der Anzeige `0xC0084100` wurde im Emulator nie gerufen. Welcher
  Wert auf dem Gerät tatsächlich bei +0x328 steht, ist darum nur hergeleitet. (hergeleitet)
- Batterie-Widget: Vtable-Slots `0xC0084100` (Stufe 1..4 → Bild 5..2) und `0xC008414C` (Netzteil → +0x4C blendet aus). Bild 1 ist
  der Stecker, 2/3/4 sind 3/2/1 Balken, 5 leer (Zeichnen `0xC003F650`, Tabelle `0xC00C1C2C`). (gelesen)
- `korg.system.battery` liest +0x328. (eigener Code)

## LEDs lesen

- Der LED-Manager `*0xC0345A1C` (blau `0xC0345BD0`) hält eine Kopie je LED bei +0x88C + 8 * LED, Byte 2 ist die Helligkeit
  (Messung `2026-10-14-led-zustand-ram.md`). (gelesen)
- `korg.read.led(index)` liest dieses Byte, ohne Manager 0. 0x88C ist kein ARM-Immediate, darum +0x880 und Ladeversatz 0xE.
  (eigener Code)
- Ein Plugin, das selbst mit `korg.led` schreibt, liest damit den Wert der Firmware, nicht den eigenen. (Urteil, so gewollt)
- Ausnahme VALUE-LED (`0x00`): der Patch pad-colors schickt sie nach dem Start einmal mit 255 an der Kopie vorbei (er schickt den
  Sollwert, der für VALUE auf 255 steht). Die Kopie und damit `korg.read.led(0)` bleiben 0. Ohne pad-colors geht für LED 0 nur 0
  hinaus. (gemessen, rot mit BLECH und mit BLECH ohne pad-colors; ob die VALUE-LED am Gerät deshalb leuchtet, nicht geprüft)

## Ergebnisse

| Befund | Marker |
|---|---|
| Start auf Batterie: `korg.system.power` 0; Nachricht `07 1`: 1; `07 0`: wieder 0 | gemessen (Hacktribe, rot, blau) |
| `korg.system.battery` nach dem Start gleich dem Modell +0x328 (im Emulator 0, weil kein Rohwert kommt); 2 ins Modell geschrieben: liest 2 | gemessen (Hacktribe, rot, blau) |
| `korg.read.led` für LEDs `0x00`, `0x01`, `0x02`, `0x09`, `0x0C`, `0x15`, `0x16`, `0x1B` gleich der Kopie, in Ruhe und nach PLAY; gleich der letzten Panel-Nachricht außer LED 0 (siehe oben) | gemessen (Hacktribe, rot, blau) |

## Offen

- Gerät: Ladestand mit echter Batterie (welche Stufe bei welcher Spannung, ob +0x328 ohne Batterie 0 oder 4 ist).
- Gerät: Stecker ziehen und stecken während ein Plugin läuft.
