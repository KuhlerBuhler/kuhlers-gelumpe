# Stufe 1 und Stufe 2 im DSP-Simulator: alle Paare

Stand 2026-11-13. Hergeleitet, nicht am Gerät gemessen.

## Aufbau

Der DSP-Code der Firmware (Hacktribe, rote) läuft im Blackfin-Simulator von GNU gdb 15.2 mit Init, Postfach-Handlern und
Frame-Funktion ([DSP im Simulator](2026-11-12-dsp-im-simulator.md)). Je Paar nimmt der Emulator den Verkehr zwischen CPU und
DSP auf: Insert-Effekt mit Baustein A in Stufe 1 und B in Stufe 2 auf jedem Part, Pad 1 spielt eine Note. Der Simulator spielt
den Verkehr nach, mit Rauschen als Eingang, und läuft 560 ms über die Note hinaus.

Bewertet wird je Paar:

- **Absturz (X):** der Simulator bricht mit einer Ausnahme ab (unausgerichteter Zugriff, Speicherschutz, ungültiger Befehl).
- **Fremder Speicher (o):** der Code von Stufe 1 oder 2 schreibt außerhalb seiner Parameter, seines Zustands, seiner
  Argumente, des Stacks und (nur Stufe 1, die als einzige Speicher bekommt) seines SDRAM-Bereichs.
- **Läuft (.):** weder noch.

20 Bausteine (`0x00` thru, `0x01` bis `0x0a`, `0x0f` bis `0x16`, `0x18`), 400 Paare, etwa 20 s je Paar.

## Abgleich mit dem Gerät

| Paar | Gerät | Simulation |
|---|---|---|
| `0x09` vor `0x0a` | Absturz | Absturz |
| `0x0a` vor `0x09` | Absturz | fremder Speicher |
| `0x15` vor `0x18` | Ton weg | fremder Speicher |
| `0x0a` vor `0x16` | stumm | fremder Speicher |
| `0x0a` vor `0x01`, `0x0a` vor `0x08` | läuft, kein Ton | Absturz |
| `0x0a` vor `0x02` | Absturz | **läuft** |
| `0x0a` vor `0x03` bis `0x07`, `0x0a`, `0x10`; `0x15` vor `0x0a`; `0x10` vor `0x06`; `0x02` vor `0x10`; `0x09` vor `0x00` | läuft | läuft |

Ein Paar am Gerät wird nicht erkannt (`0x0a` vor `0x02`). "Fremder Speicher" heißt am Gerät mal Absturz, mal kein Ton. Was
die Simulation durchlässt, ist also nicht sicher, nur nicht auffällig.

## Ergebnis

400 Paare: 174 laufen, 152 Absturz, 74 fremder Speicher. Zeile Stufe 1, Spalte Stufe 2.

| 1 \ 2 | 00 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 0a | 0f | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **00** | . | X | . | . | . | . | . | . | X | o | . | . | . | X | X | o | . | o | o | o |
| **01** | . | X | X | . | . | X | . | . | X | o | X | . | . | X | X | X | X | o | X | X |
| **02** | . | X | . | . | . | . | . | . | X | o | . | . | . | X | X | o | . | o | o | o |
| **03** | . | X | . | . | . | . | . | . | X | o | . | . | . | X | X | o | . | o | o | o |
| **04** | . | X | . | . | . | . | . | . | X | o | . | . | . | X | X | o | . | o | o | o |
| **05** | . | X | . | . | . | . | . | . | X | o | . | . | . | X | X | o | . | o | o | o |
| **06** | . | X | . | . | . | . | . | . | X | o | . | . | . | X | X | o | . | o | o | o |
| **07** | . | X | X | . | . | X | . | . | X | o | . | . | . | X | X | X | . | X | X | X |
| **08** | . | X | X | . | . | X | . | . | X | o | . | . | . | X | X | X | . | o | X | X |
| **09** | . | X | X | . | . | X | . | . | X | o | X | . | . | X | X | X | . | X | X | X |
| **0a** | . | X | . | . | . | . | . | . | X | o | . | . | . | X | X | o | . | o | o | o |
| **0f** | . | X | X | . | . | X | . | . | X | o | X | . | . | X | X | X | X | o | X | X |
| **10** | . | X | . | . | . | . | . | . | X | o | . | . | . | X | X | o | . | o | o | o |
| **11** | . | X | X | . | . | X | X | X | X | o | X | X | . | X | X | X | X | X | X | X |
| **12** | . | X | X | X | . | X | X | X | X | o | X | X | . | X | X | X | X | X | X | X |
| **13** | . | X | X | . | . | X | . | . | X | o | . | . | . | X | X | X | . | X | X | X |
| **14** | . | X | . | . | . | . | . | . | X | o | . | . | . | X | X | o | . | o | o | o |
| **15** | . | X | . | . | . | . | . | . | X | o | . | . | . | X | X | o | . | o | o | o |
| **16** | o | X | X | o | o | X | o | o | X | o | o | o | o | X | X | o | o | o | X | X |
| **18** | . | X | X | . | . | X | . | . | X | o | X | . | . | X | X | X | . | X | X | X |

- `0x11` (Chorus) und `0x12` (Flanger) brauchen Speicher, Stufe 2 bekommt keinen: Absturz hinter jedem Baustein.
- `0x13` (Phaser) und `0x15` (Lautstärke-Modulation) in Stufe 2: hinter jedem Baustein Absturz oder fremder Speicher.
- `0x05` (Limiter) in Stufe 2 hängt von Stufe 1 ab: hinter `0x0a` läuft er (wie gemessen), hinter `0x01`, `0x07`, `0x08`,
  `0x0f`, `0x11`, `0x12`, `0x13`, `0x18` Absturz. Ebenso `0x0a` hinter `0x01`, `0x0f`, `0x11`, `0x12`, `0x18`.

## Im Baukasten

`data/findings.mjs` führt die Paare, die die Gerätemessungen noch offen lassen, als `stage2Pair` (96 Paare). Bausteine, die in
Stufe 2 schon gemessen abstürzen oder stumm bleiben (`0x01`, `0x02`, `0x08`, `0x09`, `0x16`, `0x18`), und Stufe 1 `0x09` und
`0x16` stehen dort schon. Der Baukasten sperrt die Paare wie die gemessenen, der Türsteher meldet sie (`stage2-pair`).

Zwei Katalog-Effekte fallen darunter: Bass Enhancer (`0x07` vor `0x05`) und Hardtekk Kick (`0x0f` vor `0x05`). Beide sind
am Gerät noch nicht geprüft ([Neue Effekte](2026-11-11-neue-effekte.md), offen Punkt 3).

## Am Gerät zu prüfen

1. Bass Enhancer und Hardtekk Kick.
2. `0x07` vor `0x05`, `0x01` vor `0x0a`, `0x18` vor `0x0a` (Absturz erwartet).
3. `0x0a` vor `0x11`, `0x0a` vor `0x13`, `0x0a` vor `0x15` (Absturz oder kein Ton erwartet).
4. `0x0a` vor `0x14`, `0x0a` vor `0x0f`, `0x03` vor `0x05` (laufen erwartet).
