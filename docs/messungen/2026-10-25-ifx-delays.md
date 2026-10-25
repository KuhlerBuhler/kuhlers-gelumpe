# Slap Delay und Long Delay im Insert (25.10.)

Zwei neue Insert-Effekte im Katalog (`data/fx/catalog.mjs`), beide auf dem Insert-Baustein Short Delay (`I_short_delay`, `0x18`), so wie
die Delays davor. **Am Gerät nicht gehört**, im Emulator ist kein Ton.

## Was der Baustein annimmt (hergeleitet)

Die Spannen stehen in `data/map/fx-params.mjs` (Beleg `derived:vsb-table/0xC00FED74`), die Notenwerte und Faktoren in
[FX-Katalog neu](2026-10-22-fx-katalog-neu.md), Abschnitt 1.

| Parameter | Spanne | Bedeutung |
|---|---|---|
| `tempo_sync` | 0 bis 1 | 1: Zeit aus Notenwert mal Faktor, 0: `off_delay_time` mal `off_time_ratio` |
| `on_syncnote` | 0 bis 63 | Notenwert, 1 ist 1/32, 3 ist 1/16, 10 ist 3/8, 11 ist 1/2 |
| `on_time_ratio` | 0 bis 63 | Faktor, 35 ist 1 |
| `off_delay_time` | 0 bis 74 | Zeit ohne Sync, Einheit offen |
| `fb_depth`, `high_damp`, `low_damp` | 0 bis 127 | Wiederholungen und Filter in der Rückkopplung |

Ein langes Delay ist also ein großer Notenwert, ein kurzes ein kleiner. Eine eigene Typkennung für "Long" gibt es im Insert nicht,
beide sind Presets des einen Bausteins.

## Was gebaut ist

| Name | Sync | Zeit | Feedback | Dämpfung hoch, tief | Wet |
|---|---|---|---|---|---|
| Slap Delay | an | 1/32 mal 1 | 35 | 60, 15 | 100 |
| Long Delay | an | 3/8 mal 1 | 70 | 50, 25 | 90 |

Die Regler gehen wie bei den anderen Delays: Regler 1 mischt das Echo dazu, beide Regler stellen das Feedback. Das Feedback bleibt unter 90
([Pegel](2026-09-21-loudness.md)).

## Offen

- Klang am Gerät, besonders ob 3/8 beim Long Delay noch in den Puffer passt. Die Werkspresets gehen im Insert nur bis 9/32 (0,28), 3/8
  ist 0,375. Die obere Grenze ist nicht gemessen. Wenn der Puffer zu kurz ist, ist der Notenwert zu groß, dann reicht ein kleinerer
  (Notenwert 9, 1/3).
- Die Einheit von `off_delay_time` und ob "1" ein Takt oder eine Viertel ist, siehe [FX-Katalog neu](2026-10-22-fx-katalog-neu.md).
