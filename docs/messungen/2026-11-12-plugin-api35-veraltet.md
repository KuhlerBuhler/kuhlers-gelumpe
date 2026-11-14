# Plugin API 35: veraltete Aufrufe

Stand 12. November 2026. Teil 10 des Plans. Keine neue Firmware-Forschung, nur Abgleich vorhandener Aufrufe. Lauf im Emulator
mit Hacktribe 2.02 (eigene Datei), Korgs Original 2.02 rot und blau, jeweils mit dem BLECH-Satz. **Am Gerät nicht geprüft.**

## Frage

Welche Aufrufe der Plugin-API ersetzt ein neuerer Aufruf eins zu eins, und laufen Plugins mit der alten Form weiter?

## Befund

| Alt | Ersatz | Ersatz ab API | Marker |
|---|---|---|---|
| `korg.read.chainMode()`, Eigenschaft `korg.chainMode` | `korg.global.chainMode` | 20 | gelesen, hergeleitet (siehe unten) |
| `korg.current.*` | `korg.pattern.current.*` | 21 | gelesen |

- `korg.read.chainMode` liest Byte 31 des Global-Blocks `0xC06A2A94` (`script_read_chain_mode_glue` in `tools/patch/script_hw.s`)
  und gibt 0 oder 1. Das Blatt `korg.global.chainMode` ist das Feld CHAIN MODE (Offset `0x1f`,
  [2026-10-14-global-felder.md](2026-10-14-global-felder.md)) desselben Global-Objekts. Dass beide dieselbe Speicherstelle
  lesen, ist aus den Offsets hergeleitet, nicht getrennt gemessen. (gelesen, hergeleitet)
- `korg.current.*` und `korg.pattern.current.*` übersetzt der Compiler in denselben Aufruf, der Block ist Byte für Byte gleich
  (`test/script-properties.test.mjs`). (gelesen, Test)
- Nicht als veraltet markiert, weil sie etwas anderes tun oder nur Abkürzungen sind: `korg.pressKey` (Druck und Loslassen in
  einem) neben `keyDown`/`keyUp`, `korg.passKeys` neben `keyHold`/`keyMask`, `korg.backlight` neben den Farbblättern des Menüs,
  `korg.motion.enabled` neben dem Motion-Modus, `korg.display.number` neben `textNumber`, die `korg.read.*`-Aufrufe hinter
  Eigenschaften. (Urteil)

## Ergebnisse

| Befund | Marker |
|---|---|
| Ein Plugin schreibt `korg.current.key` und `korg.current.level`, liest `korg.current.tempo` und `korg.current.syncGroup` neben `korg.pattern.current.*` und bekommt die Werte, die im RAM stehen (Fall `pattern_parts:plugin_sets_and_reads_by_name`, 17 von 17 Fällen grün) | gemessen (Hacktribe, rot, blau) |
| Der Compiler meldet jede alte Form als Warnung mit Ersatz und API-Version, der Block bleibt gleich | Test |

## Offen

- Entfernen der alten Formen erst in einer späteren Version, angekündigt in den Release Notes zu 1.5.
