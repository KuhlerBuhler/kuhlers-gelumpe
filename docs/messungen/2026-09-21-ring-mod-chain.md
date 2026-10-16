# Ringmodulator mit zweiter Stufe

Gehört am 2026-09-21.

| Kette | Ergebnis |
|---|---|
| `0x16` allein | läuft (auch in Werkspresets) |
| `0x0a -> 0x16` | kein Ton, Gerät läuft weiter |
| `0x16 -> 0x0a` | kein Ton, zweimal unabhängig gebaut |

Die zweite Zeile entstand einmal durch Tausch der beiden 74-Byte-Stufenblöcke
eines bestehenden Records, einmal aus einer echten zweistufigen Hülle (Talk
Filter) mit dem unveränderten Stufe-1-Block aus Ring Delay 1. Beide stumm.

Daraus auch: ein Stufenblock lässt sich nicht zwischen Stufe 1 und 2
verschieben. Der getauschte Record ist formal gültig und spielt nichts.
