# Stufe 2, automatische Messreihe

Übernommen am 2026-09-21 aus der Modding-Doku (Version 3,
`07-kombinationsregeln.md`). Das Datum der Messreihe selbst ist dort nicht
festgehalten; sie lief zwischen dem 2026-09-14 und dem 2026-09-21.

Aufbau: Filter `0x0a` fest in Stufe 1, Stufe 2 nacheinander mit jedem
Baustein, Aufnahme und Pegelmessung je Kette (`fxlab.py sweep stage2`). Zwei
unabhängige Läufe, gleiches Ergebnis.

| Stufe 2 | Ergebnis |
|---|---|
| `0x01` mkp2_comp | läuft, kein Ton |
| `0x02` sr1_comp | Absturz |
| `0x03` cheap_comp | läuft |
| `0x04` punch | läuft |
| `0x05` limiter | läuft |
| `0x06` eq_2_band | läuft |
| `0x07` eq_4_band | läuft |
| `0x08` exciter | läuft, kein Ton |
| `0x09` decimator | Absturz |

Die übrigen Bausteine sind in Stufe 2 nicht gemessen.
