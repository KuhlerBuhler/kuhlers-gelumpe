# e2sFx.all über USB lesen, 2026-11-14

Stand 2026-11-14. Im Emulator mit Hacktribe 2.02 und Korgs Original 2.02 (rot), jeweils mit dem BLECH-Satz. **Am Gerät und auf der
blauen Electribe 2 ist nichts gemessen.** Markierungen wie in [Doom über USB](2026-11-11-doom-usb.md).

Frage: Kann die App die Effekt-Sammeldatei `KORG/blechtribe/Presets/e2sFx.all` von der Karte lesen, ohne Kartenleser?

## Befund

- **offline:** Bits 30 und 29 im Offset von FILE READ wählen `SD:KORG/blechtribe/Presets/e2sFx.all`, den Pfad, den der Lader beim
  Start liest (`tools/patch/fx_card.s`). Grenze wie bei der Sample-Datei 256 MiB. Bisher nannten die zwei Bits keine Datei (Status 3).
  `BLECH.FILE_FX` in `src/protocol.mjs`, `FILE_FX` in `tools/patch/blech_sysex.py`.
- **offline:** Nur lesen. FILE BEGIN mit denselben Bits sagt Status 3 und schreibt nichts. Mit Bit 31 dazu nennen sie keine Datei,
  READ und BEGIN sagen Status 3. Eine Firmware von vorher sagt bei READ ebenfalls Status 3, daran erkennt die App sie; ein INFO-Bit
  gibt es dafür nicht.
- **offline:** Der zweite Code-Bereich (Sample-Befehle, ab `0xC017B950`) war auf der blauen bis `0xC017C000` voll, dort beginnen
  die Preset-Tabellen. `doom_path`, die Doom-Namen und der neue Pfad liegen darum jetzt im Hauptbereich: der endet bei `0xC0172F0C`
  (`0xe0c` von `0xf00` Byte), der zweite bei `0xC017BF6C`, auf der blauen bei `0xC017BF90`.
- **gemessen:** `fx_read_cases` in `tools/emu/sysex_cases.py` besteht auf Hacktribe und auf Korgs Original:

| Fall | Ergebnis |
|---|---|
| `fx_read` | eine `e2sFx.all` von 66313 Byte: Größe stimmt, in 3 Blöcken gleich zurückgelesen |
| `fx_read_tail` | ein READ über das Ende gibt die letzten 100 Byte |
| `fx_write_refused` | FILE BEGIN mit Bits 30 und 29: Status 3, die Datei unverändert |
| `fx_missing` | ohne `e2sFx.all` auf der Karte: Status 6 |

- **gemessen:** `doom_refusals` liest jetzt mit Bits 31, 30 und 29 statt 30 und 29, weiter Status 3; `file_cases` unverändert grün.

## Offen

- Am Gerät lesen, sobald eine Firmware mit dem Patch auf der Karte ist.
- Die blaue Electribe 2: gleicher Code, nicht ausgeführt.
- Die App liest die Datei noch nicht (kein Knopf).
