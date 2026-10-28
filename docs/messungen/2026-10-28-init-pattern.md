# Eigenes Init-Pattern (Set Init Pattern, 28.10.)

Stand 28.10.2026, Emulator mit Hacktribe 2.02 und Korgs Original 2.02 (rot). Wunsch: wie bei Hacktribe ein Pattern wählen,
das DATA UTILITY > 5 INITIALIZE PATTERN als Vorlage nimmt. Patch `data/patches/init-pattern.json`, Seite INIT PATTERN unter
BLECH > FEATURES. Am Gerät nicht geprüft.

## Wie die Firmware initialisiert

| Befund | Marker |
|---|---|
| `0xC0036BEC(obj, ziel)` kopiert die Vorlage `0xC00CFF58` (Datei `0xD0058`, `table.initPattern`) mit `0xC000985C` (0x4000 Byte) ins Ziel, setzt in allen 16 Parts und 64 Steps zwei Bytes (+0x31 = 0x48, +0x32 = 0x60) und füllt +0x0C bis +0x0E aus Einstellungen (`0xC002CAF0`, `0xC002CAF8`, `0xC002CAE8`) | offline (Code) |
| Vier Aufrufer: `0xC0036A34` (INITIALIZE PATTERN, Ziel ein Puffer auf dem Stack), `0xC004AD00` (Laden eines Patterns, Ausweichweg), `0xC004C018` und `0xC004C03C` (Start: Patterns ohne gültige Kopie im Flash, im Emulator mit leerem Flash alle 250) | gemessen (Emulator, Haken vor dem Start gesetzt) |
| INITIALIZE PATTERN liest die Vorlage über den Aufruf bei `0xC0036A34` (Lesezugriffe auf `0xC00CFF58` mit Rücksprung `0xC0036C04`) | gemessen (Emulator) |

## Der Patch

- Nur `0xC0036A34` geht durch `ip_init` (`0xC014FD00`, 180 Byte): erst die Funktion der Firmware, dann, wenn Global-Byte 247
  ein Pattern nennt (Nummer plus 1, 1 bis 250) und dessen Block in der Pattern-Bank (`0xC08B2940` + Nummer mal `0x4000`) mit
  `PTST` beginnt, die Kopie dieses Blocks über das Ergebnis. +0x0C bis +0x0E bleiben die Werte der Firmware.
- Der Start und das Laden behalten die Vorlage der Firmware.
- Mit EXIT beim Einschalten: die Vorlage der Firmware.
- Die Seite INIT PATTERN (Art 40 in `tools/patch/script_menu.s`, Code in `tools/patch/script_init.s` im dritten Code-Bereich):
  FACTORY oder 1 bis 250, das Hauptrad schreibt Global-Byte 247 sofort. Die Firmware speichert die Globals beim Ausschalten mit.
  Die Seite gibt es nur, wo der Satz den Patch hat (erstes Wort bei `0xC014FD00` nicht `FF`), also nicht auf der blauen.
- CLEAR PATTERN ergibt sich daraus: ein ganz leeres Pattern (wie Pascals Pattern 250) als INIT PATTERN wählen.

## Fälle (`tools/emu/init_pattern_cases.py`, BLECH-Satz Hacktribe)

| Fall | Ergebnis |
|---|---|
| Seite zeigt INIT PATTERN / FACTORY, Byte 247 ist 0 | ja |
| Rad +7: "7", Byte 247 = 7; Rad stoppt bei FACTORY und 250 | ja |
| INIT PATTERN 7, INITIALIZE PATTERN: das Pattern im RAM heißt wie Pattern 7 ("TEMPLATE SEVEN") | ja |
| FACTORY: "Init Pattern" | ja |
| INIT PATTERN 7 mit EXIT beim Einschalten: "Init Pattern" | ja |

## Offen

- Am Gerät nicht geprüft.
- Blau: gebaut (`data/patches/init-pattern-synth.json`, Stellen in `data/synth-map/last-pattern.json`), die sechs Fälle grün im Emulator mit Korgs blauem 2.02.
- Welche Felder eines geleerten Patterns 0 nicht vertragen, ist nicht untersucht; wer ein eigenes leeres Pattern nimmt, nimmt es so, wie er es gespeichert hat.
