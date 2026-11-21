# Plugin API 27: MFX-2-Typ und Touchpad-Modus

Stand 11. November 2026. **Gemessen** im Emulator mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils
mit dem BLECH-Satz (`data/patches/blech.json`, für blau `blech-synth.json`). Fälle: `tools/emu/plugin_api27_cases.py` (läuft
als Gruppe von `remote_cases`). **Am Gerät nicht geprüft.**

## Frage

Kann ein Plugin den MFX-2-Typ des Patches mfx-switch lesen und setzen, den Touchpad-Modus lesen und setzen und einen
Moduswechsel als Ereignis bekommen, ohne einen zweiten Schreiber neben dem Patch und ohne neue Adressen zu raten?

## Weg

**MFX-2-Typ** (`mfx2Type`, Feld 18 von `korg.read.patternValue` / `korg.seq.setPatternValue`, dazu die Eigenschaften
`korg.pattern.current.mfx2Type` und `korg.patterns[i].mfx2Type`):

- Der Patch mfx-switch hat am Anfang seines Codes (`CODE_AT`, 0xC01A5000) jetzt vier feste Worte: die Kennung `MFX2`,
  `b table_load`, den Standardtyp und `b killed`. Die Laufzeit prüft die Kennung, ruft `table_load` (die Tabelle lädt der
  Patch sonst erst beim ersten MFX-2-Druck) und liest das Byte der Tabelle (`RECBUF + 8 + Pattern`). 0 heißt Standardtyp.
- Schreiben geht nur, wenn `killed` 0 meldet (EXIT beim Einschalten nicht gehalten, MFX 2 im BLECH-Menü an). Ist MFX 2 aktiv
  (`S_MODE == 1`), ruft die Laufzeit den Typ-Setter der Firmware mit Ankündigung 1, wie die Seite MFX TYPE. Der Hook des
  Patches schreibt dann Tabelle und Dirty-Flag. Sonst schreibt die Laufzeit das Tabellenbyte und setzt Dirty selbst.
  Gespeichert wird mit WRITE, wie bei einer Änderung am Gerät.
- Ohne den Patch (falsche Kennung) liest ein Plugin -1.

**Touchpad-Modus** (`korg.touchpad.mode`, Blatt 53, neue Basis `touchpad`):

- Gelesen wird das Wort `[[0xC06912E0]] + 0x334` (blau über `data/synth-map/mfx-switch.json`, 0xC056B58C), 0 Gate Arp,
  1 Touch Scale, 2 Master FX, 3 beides. 4 heißt MFX 2: Modus 2 und `S_MODE == 1`.
- Gesetzt wird mit genau einem Tastendruck über die Panel-Queue (`script_press_key_glue`), also so, wie es die Hand
  macht. Mit dem Patch: 1 ist SHIFT + TOUCH SCALE, 2 MASTER FX, 3 GATE ARP, 4 TOUCH SCALE; 0 ist mit dem Patch nicht
  erreichbar und wird ignoriert. Ohne den Patch (oder MFX 2 aus) gilt die Tabelle der Firmware aus
  `2026-10-10-mfx-umschalter.md`; ein Ziel, das von dort mit einem Druck nicht erreichbar ist, bleibt ohne Wirkung.

**Ereignis `touchpadMode`**: der Frame-Hook vergleicht den Modus mit dem letzten und meldet jede Änderung, egal ob von
Hand oder vom Plugin.

## Ergebnisse

| Befund | Marker |
|---|---|
| Alle neun Fälle grün auf Hacktribe 2.02, rot 2.02 und blau 2.02 mit BLECH, keine Assertion der Maschine | gemessen |
| Lesen nach dem Start: Tabelle leer, Plugin liest 6 (Standardtyp 7, 0-basiert) für `current` und `patterns[0]` | gemessen |
| Setzen bei inaktivem MFX 2 (Master FX): Tabelle 13 für den Wert 12, Dirty 1, der Typ im Pattern-Objekt (+0x41) bleibt | gemessen |
| Setzen bei aktivem MFX 2: Tabelle 21 für 20, der Typ im Pattern-Objekt wird 20 | gemessen |
| Setzen über dem Ende: 99 wird 39 auf Hacktribe und rot, 31 auf blau (32 MFX-Typen) | gemessen |
| MFX 2 im BLECH-Menü aus: Setzen ändert nichts | gemessen |
| Modus setzen mit MFX 2 an: 4, 3, 1, 2 je mit einem Druck erreicht; 0 bleibt 2 | gemessen |
| Modus setzen mit MFX 2 aus: Ergebnisse gleich der Firmware-Tabelle (0 von 3, 3 von 2 nicht erreichbar, bleibt 2) | gemessen |
| `touchpadMode` meldet GATE ARP (3) und `korg.touchpad.mode = 4` (4), je einmal | gemessen |
| Typ 25 überlebt WRITE und einen Neustart mit dem geschriebenen Flash | gemessen |
| SHIFT + TOUCH SCALE im selben Frame ergibt Modus 1 | gemessen (Schritt von 3 nach 1) |
| Ohne den Patch mfx-switch liest ein Plugin -1 und Setzen bleibt ohne Wirkung | hergeleitet (Kennungsprüfung in `mfx2_on`, kein Fall ohne Patch) |

## Offen

- Am Gerät ist nichts davon geprüft.
- Der Schreibbereich ist 0 bis 39 wie bei `mfxType`; Hacktribe mit Katalog hat 43 MFX-Typen. Die Typen 40 bis 42 erreicht
  ein Plugin also nicht, wie schon bei `mfxType`.
