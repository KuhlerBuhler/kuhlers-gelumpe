# Plugin API 35: Touchpad-Y halten, im Emulator

`korg.touchLockY(y)` hält das Y, das die Firmware von einer Touch-Nachricht sieht,
so wie `korg.touchLockX(x)` das X hält. Das Plugin bekommt weiter das echte Y.

## Aufbau

**Gelesen:** In einer Touch-Nachricht (Klasse 5) liegen das rohe X in Byte
0x0d/0x0e und das rohe Y in Byte 0x0f/0x10, höheres Byte zuerst. Der
Eingangsfilter `touch_lock_input` (`tools/patch/script_hw.s`) schreibt nach den
Plugins das gesperrte X und das gesperrte Y hinein, jedes aus eigenem Eintrag.

**Gelesen:** Der Y-Eintrag (rohes Y, Plugin, Prüfsumme, 12 Byte) liegt bei
`0xC018D1F0` in der MORE-Reserve hinter den Menüseiten (`TOUCH_LOCK_Y`). Der
Bereich ist in allen drei Images FF, FF heißt keine Sperre.
`script_touch_lock_guard` prüft X und Y und lässt los, wenn das Plugin nicht
mehr läuft.

**Gelesen:** Die Firmware rechnet Y so:

| Modus | Y der Firmware | Stelle (HT/rot, blau) |
| --- | --- | --- |
| Master FX | (roh >> 4) * 2, an +0x20 des Objekts | `0xC00454F8`, `0xC003F818` |
| Touch Scale, Gate Arp | roh >> 3, in r2 der Modusfunktion | `0xC0060830`, `0xC00572E8` |

Die Sperre schreibt roh = y << 3. Daraus: Master FX sieht y auf gerade
abgerundet, Touch Scale und Gate Arp sehen y genau.

## Messung im Emulator

`tools/emu/plugin_api35_cases.py`. Finger bei rohem X 400, Y 500 mit gedrückter
TOUCHPAD-Taste, dann Sperre 64, 127, 33 und -1.

| Fall | Hacktribe | rot | blau |
| --- | --- | --- | --- |
| Master FX: Y frei, 64, 127, 33, -1 (X bleibt 50) | 62, 64, 126, 32, 62 | 62, 64, 126, 32, 62 | 62, 64, 126, 32, 62 |
| Gate Arp: Y frei, 64, 127, 33, -1 (X bleibt 50) | 62, 64, 127, 33, 62 | 62, 64, 127, 33, 62 | 62, 64, 127, 33, 62 |
| Touch Scale: Y frei, 64, 127, 33, -1 (X bleibt 50) | 62, 64, 127, 33, 62 | 62, 64, 127, 33, 62 | 62, 64, 127, 33, 62 |
| Plugin bekommt (400, 500) in allen Schritten | ja | ja | ja |
| Plugin stoppt: Eintrag 0x200, danach FF | ja | ja | ja |

**Gemessen.** Die Rundung in Master FX ist dieselbe wie bei X; in Touch Scale
ist Y anders als X nicht auf gerade gerundet.

```bash
PYTHONPATH=tools/patch tools/emu/.venv/bin/python tools/emu/plugin_api35_cases.py --vsb BLECH.VSB
```

## Offen

- **Gerätetest:** noch nicht gemacht.
- **Klang:** was ein festes Y in Touch Scale und Gate Arp hörbar ändert, ist
  nicht geprüft, nur der Wert, den die Modusfunktion bekommt.
