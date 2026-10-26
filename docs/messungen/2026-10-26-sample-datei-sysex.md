# Die Sample-Datei über SysEx, 2026-10-26

Stand 2026-10-26. Alles im Emulator, mit Hacktribe 2.02, Korgs Original 2.02 und der blauen Electribe 2 (Synth), jeweils mit dem BLECH-Satz.
Die Dateien der Karte sind aus einer Formel gebaut, nichts ist von Korg. **Am Gerät ist nichts gemessen.** Markierungen: **gemessen**
(im Emulator ausgeführt), **offline** (Code gelesen), **offen**.

Frage: Kann der Editor `KORG/<Ordner>/Sample/e2sSample.all` über BLECHs SysEx-Befehle lesen, ändern, kürzen und Samples hinzufügen, ohne
mehr als den Kopf und die neuen Samples zu übertragen, und ohne die Karte zu gefährden?

## Befund

- **offline:** Die FILE-Befehle erreichten nur `SYSTEM.VSB` und `ORIGINAL.BIN`, mit Grenze `0x200100`. Die Sample-Datei war nicht
  erreichbar, in keinem der drei Ordner.
- **offline:** Das FatFs der Firmware (Hacktribe und Korgs Original, 2.02) hat `f_open` `0xC009DB60`, `f_read` `0xC009DD74`, `f_write`
  `0xC009DFB8`, `f_close` `0xC009E3DC`, `f_lseek` `0xC009E404`, `f_opendir` `0xC009E660`, `f_stat` `0xC009E7DC`, `f_getfree`
  `0xC009E85C`, `f_unlink` `0xC009E9B8`, `f_mkdir` `0xC009EB00`. Kein `f_truncate`, kein `f_rename`. Die blaue Electribe 2 hat auch
  `f_unlink` nicht (zwischen `f_getfree` `0xC008B3B4` und `f_mkdir` `0xC008B510` liegt keine Funktion dieser Größe).
- **gemessen:** Nach der Erweiterung ([sample-datei.md](../hintergrund/sample-datei.md)) bestehen die Fälle `sample_*` in
  `tools/emu/sysex_cases.py` auf allen drei Builds:

| Fall | Ergebnis |
|---|---|
| `sample_read` | die Datei in `KORG/blechtribe/Sample/` (Synth: `KORG/electribe/Sample/`) wird über Bit 30 gelesen: Größe und Bytes stimmen |
| `sample_read_limits` | über 256 MiB: Status 3; innerhalb, aber hinter dem Dateiende: 0 Byte |
| `sample_header_in_place` | ein Block bei Offset 0 schreibt den Kopf, der Rest der 40000 Byte bleibt |
| `sample_append` | ein Block am Ende hängt an (45000 Byte auf der Karte) |
| `sample_temp_anew` | die Tauschdatei entsteht bei Offset 0 und wird vom nächsten Block bei 0 neu gemacht |
| `sample_copy` | zwei Stücke auf der Karte kopiert, je mit dem CRC-32 ihrer Bytes, die Tauschdatei ist gleich den Stücken |
| `sample_crc` | FILE CRC liefert den CRC-32 von 25441 Byte, ohne sie zu senden |
| `sample_swap` | alte Datei gelöscht, Tauschdatei zurückkopiert und gelöscht: die Datei ist die verdichtete, `SYSTEM.VSB` unberührt, keine Assertion (nicht auf dem Synth) |
| `sample_refusals` | DELETE von SYSTEM.VSB und ORIGINAL.BIN abgelehnt (2), COPY in einer Datei, von oder in eine andere Datei abgelehnt (2), Länge 0, über 256 KiB, hinter dem Limit, Quelle zu kurz (3), DELETE einer fehlenden Datei (6), schlechte CRC-Bereiche (2, 3); nichts verändert |
| `sample_no_card` | ohne Karte sagen READ, COPY und DELETE 6 |
| `sample_kill_switch_silent` | mit EXIT beim Einschalten antworten alle vier nicht, die Datei bleibt |
| `sample_synth_no_delete` | blaue Electribe 2: DELETE sagt 6, die Dateien bleiben, INFO meldet Bit 7 nicht |

- **gemessen:** Der Weg des Editors (`src/usb-sample-file.mjs`) gegen die Simulation des Geräts (`src/device.mjs`): Liste, Hinzufügen,
  Entfernen mit Verdichten, ein auf der Karte beschädigtes Stück der Tauschdatei (die CRC-Prüfung findet es, die alte Datei bleibt, die
  Tauschdatei geht), ein beschädigtes Zurückkopieren (die fertige Tauschdatei bleibt, `finishTemp` schließt es ab) und eine kaputte
  Tauschdatei (wird erkannt und gelöscht): `test/usb-sample-file.test.mjs`, `test/e2e/sampleset-device.e2e.mjs`.

## Offen

- Am Gerät (Karte, echter Kartenleser, Zeiten bei 20 MB) ist nichts gemessen. Die Zeit der Kopierschritte ist nur im Emulator gesehen.
- Ob ein Abbruch mitten im Kopieren (Strom aus) eine FAT hinterlässt, die der Emulator nicht nachbildet, ist **offen**. Die Befehle benutzen
  nur `f_open`, `f_read`, `f_write`, `f_lseek`, `f_close` und `f_unlink` der Firmware, wie es ihre eigenen Datei-Funktionen tun.
- Eine Wiederherstellung einer unterbrochenen Tauschung beim Einschalten ohne die App gibt es nicht.
