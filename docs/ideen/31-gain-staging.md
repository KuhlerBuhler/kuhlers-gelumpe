# Idee 31: Gain-Staging-Helfer

Stand: im Editor gebaut (Linter-Regeln und Pegel-Ansicht im Bereich Presets), am Gerät ungehört. Zurück zu den [Ideen](../ideen.md).

Pegel sinnvoll skalieren und vor unspielbaren Werten warnen; die Standard-Ausgangsverstärkung per Patch neu abstimmen.

Befund (gemessen): Part-Level und `pattern.playLevel` gehen bis 127, der FX-`output_level` in Presets liegt bei etwa 30, ein globaler Master-Pegel ist nicht gespeichert (Volume ist ein analoger Regler). Die Gain-Kurve selbst zu ändern wäre DSP.

Unspielbare Werte aus den Hörtests ([Pegel](../messungen/2026-09-21-loudness.md)): `output_level` 124 in einem Verzerrer-Preset, Werte um 38 bis 60 waren brauchbar; `output_gain` 95 bei `0x15` übersteuerte an jeder Reglerstellung.

## Was gebaut ist

- **Warnungen im Linter** ([Linter](../linter.md)). Beide gehörten Fälle sind Befunde in `data/findings.mjs` mit der Messung als Beleg und kommen als Warnung mit dem Hinweis "gehört" (`output-too-loud`): `output_level` ab 124 beim Verzerrer (`0x0f`) und `output_gain` ab 95 beim Pegelmodulator (`0x15`). Dazwischen, über 60 und bis 90, ist nichts gehört: `output-above-usable`, eine Warnung, die sagt, dass der Bereich ungetestet ist. Über 90 bleibt bei jedem Baustein die allgemeine Warnung. Es ist jeweils eine Warnung und kein Fehler, das Gerät nimmt die Werte an, und der Türsteher lässt sie nach Bestätigung durch.
- **Werksvergleich.** Erreichen die Werks-Presets desselben Bausteins den Wert selbst, bleibt der Linter still: der Decimator liefert `output_level` 127 ab Werk. Die Prüfung `factory-check:gain-staging` hält die beiden gehörten Fälle gegen die Werks-Presets desselben Bausteins: keines kommt an die gehörten Werte heran (der Pegelmodulator liegt bei 32 bis 36). Sie läuft mit `npm run test:local`.
- **Pegel-Ansicht** (Bereich Presets, unter dem Effekt-Editor). Holt das Pattern aus dem Puffer des Geräts oder Emulators und zeigt Pattern-Lautstärke, die 16 Part-Pegel und die Ausgangspegel der Insert-Presets, die die Parts benutzen. Ein Faktor oder ein Zielwert für den lautesten Part skaliert alle Part-Pegel mit demselben Faktor, die Pattern-Lautstärke auf Wunsch auch. Eine Vorschau zeigt vorher und nachher, bevor etwas gesendet wird. Würde der lauteste Pegel über 127 steigen, wird der Faktor auf den begrenzt, der genau 127 trifft, damit das Verhältnis bleibt; ein Pegel über 0 rundet nie auf 0. Gesendet wird über den normalen Pattern-Weg (Sicherung des Puffers, Türsteher, Bestätigung, Zurücklesen, Rücknahme).

## Entscheidungen

- Die Insert-Pegel werden **angezeigt, nicht skaliert**. Ein Preset kann mehrere Parts und Patterns bedienen, und es zu ändern ist Sache des Effekt-Editors (Knopf "Im Editor öffnen"). Das Master-Preset ist nicht dabei.
- Der Zugang ist der Puffer des Geräts, kein Dateieditor: Patterns haben im Editor keine Dateiseite mehr.
- **Hergeleitet, nicht geprüft:** der Menüplatz eines Parts ist der gespeicherte Typ plus 1 (das Insert-Menü hat 38 Einträge, beobachtet sind Typen von 0 bis 37, mit Hacktribe darüber). Die Zuordnung Part zu Preset in der Ansicht steht darauf.
- "Verzerrer-Preset" aus der Messung ist als `0x0f` (Distortion) gelesen. Bei einem anderen Baustein gilt nur die allgemeine Grenze von 90.

## Offen

- Am Gerät hören, ob die Skalierung im Satz so klingt, wie die Vorschau verspricht.
- Die Standard-Ausgangsverstärkung per Patch neu abstimmen ist nicht angefangen.
- Die Obergrenze des Bereichs zwischen 60 und dem gehörten Fehlerfall ist offen; dort steht die Warnung "ungetestet".
