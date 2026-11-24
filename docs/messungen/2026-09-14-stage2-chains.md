# Zweistufige Insert-Ketten, Handversuche

Gemessen 2026-09-14 über RAM, am Gerät gehört, ohne den Patch `stage2-memory`
(eigener Speicher für Stufe 2, [Patcher](../patcher.md)); mit ihm laufen die Paare in der
Simulation ohne Absturz ([Messung](2026-11-13-stufe2-speicher.md)).

| Stufe 1 | Stufe 2 | Ergebnis |
|---|---|---|
| `0x15` level_mod | `0x0a` filter | läuft |
| `0x02` sr1_comp | `0x10` acid driver | läuft |
| `0x15` level_mod | `0x18` short delay | Ton im ganzen Gerät weg, Neustart nötig |
| `0x09` decimator | `0x0a` filter | Absturz |
| `0x09` decimator | keine | läuft |

Am Gerät belegt: ein Master-Baustein (Reverb `0x36`)
in einer Insert-Kette hängt das Gerät auf. Ein Master-Platz führt genau einen
Baustein aus.

Korgs eigene zweistufige Presets benutzen in Stufe 2 nur `0x06`, `0x0a` und
`0x10`, in den Ketten `0x10 -> 0x06`, `0x0a -> 0x0a` und `0x0a -> 0x10`.
