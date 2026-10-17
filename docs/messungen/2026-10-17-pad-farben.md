# Pad-Farben: Part und Auswahl in Rot, Blau oder Pink

Stand 2026-10-17. Im Emulator (`tools/emu/menu_cases.py`, `pad_colour_cases`) mit BLECH auf Hacktribe (eigene `SYSTEM.VSB`) und offline
mit Capstone. Am Gerät ist nichts geprüft. Markierungen: **gemessen**, **offline**, **hergeleitet**, **offen**.

## Was der Patch tut

Jedes Pad hat eine rote (`0x2C + 2n`) und eine blaue LED (`0x2D + 2n`). Die Firmware zeigt in Rot, was das Pad gerade zeigt (Part spielt,
Pad gedrückt, Schritt), in Blau den gewählten Part, beides zusammen ist Pink. Im Menü BLECH, CUSTOMIZATION, wählt man:

| Seite | Werte | Vorgabe |
|---|---|---|
| PAD COLOR | RED, BLUE, PINK | RED |
| SELECT COLOR | RED, BLUE, PINK, nie die Farbe von PAD COLOR | BLUE |

Leuchten beide zugleich, bekommt das Pad die Farbe, die übrig bleibt: pinke Pads und blauer Cursor überlappen in Rot, pinke Pads und roter
Cursor in Blau. Mit Rot und Blau (der Vorgabe), mit EXIT beim Einschalten oder ohne Einstellung ändert der Patch nichts.

## Wie

- **Offline:** Alle LED-Nachrichten der Firmware laufen durch `0xC00875F4` (Manager, LED, force): sie vergleicht Sollwert und Kopie, baut
  die Nachricht `{LED, Flag, Helligkeit}` bei Manager `+0xB4C` und springt bei `0xC00876A8` zum Sender `0xC0087578`. Der Haken sitzt auf
  diesem Sprung. Er rechnet aus dem Sollwert beider LEDs des Pads die Farbe aus und schickt die Helligkeit dafür; ändert sich dadurch die
  andere LED des Pads, schickt er sie mit (er merkt sich, was er je LED zuletzt geschickt hat). Sollwert und Kopie der Firmware bleiben,
  wie sie sind.
- Das Menü ruft vier Einsprünge des Patches (`0xC018B000`): Farben aus der Einstellungsdatei, Bits dafür, nächste Farbe, Texte. Jede
  Änderung schickt alle 32 Pad-LEDs neu. In der Einstellungsdatei: Bits 2 bis 3 PAD COLOR (0 Rot), Bits 29 bis 30 SELECT COLOR (0 Blau,
  1 Rot, 2 Pink), damit eine Datei ohne die Bits die Firmware ist.

## Gemessen

- `padcolor_pages`: die Seiten zeigen RED und BLUE, das Pad des gewählten Parts leuchtet blau (0, 255).
- `padcolor_select_at_once`: SELECT auf PINK, das Pad wird sofort rot und blau (255, 255).
- `padcolor_never_the_same`, `padcolor_pad_skips_select`: die Wahl springt über die Farbe der anderen Seite.
- `padcolor_overlap_is_the_colour_left`: PAD PINK, SELECT RED, Pad gedrückt und gewählt: blau (0, 255).
- `padcolor_file_holds_them`, `padcolor_start_reads_them`: WRITE schreibt `0x20000008` ins look-Wort, der nächste Start liest es und das
  Pad des Parts leuchtet rot.
- `padcolor_exit_held_is_stock`: mit EXIT beim Einschalten blau wie bei der Firmware.
- **Hergeleitet:** die Helligkeit einer Überlappung ist die hellere der beiden. Am Gerät leuchtet ohnehin jeder Wert ab 1 voll
  ([Pad-LED-Stufen](2026-10-16-pad-led-stufen.md)).
- **Offen:** nur auf dem roten Sampler (Hacktribe und Korgs Original); die blaue Electribe bekommt die Seiten nicht.
