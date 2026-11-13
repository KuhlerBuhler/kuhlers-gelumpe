# Eigener Speicher für Stufe 2: warum Paare abstürzen und der Patch dagegen

Stand 2026-11-13. Hergeleitet im DSP-Simulator, nicht am Gerät gemessen. Gilt für die roten Builds (Hacktribe und Korg 2.02).

## Ursache

Beim Start legt das DSP-Programm für jeden der 16 Parts zwei Argument-Blöcke an, je einen für Stufe 1 und Stufe 2 des
Insert-Effekts (Schleife bei `0x01F0C140`, Argumente ab `0xFF902B7C`, `0x50` je Part). Jeder Block nennt dem Baustein seinen
Zustand, seine Koeffizienten und seinen Verzögerungsspeicher im SDRAM.

| | Stufe 1 | Stufe 2 |
|---|---|---|
| Koeffizienten | Part-Block `+0xD0`, `0x50` Bytes | direkt dahinter, `0x50` Bytes, bis in die Mixer-Wörter (IFX ON, Pan, MFX SEND) und den nächsten Part |
| Zustand | `0xFF9018AC + 0x118 * Part + 0x20`, `0x50` Bytes | `0x50` dahinter, bis in die Mixer-Wörter des Zustands (`+0xC0`) |
| SDRAM | eigener Puffer, `0x2EE00` Bytes | Adresse 0, also der DSP-Code im SDRAM |

Was die Bausteine wirklich brauchen, hat der Simulator gemessen: jeder Baustein allein, in beiden Stufen, alle Schreibzugriffe
relativ zu seiner Basis. Koeffizienten bis `0xA0` Bytes (`0x01`), `0x88` (`0x0f`), `0x84` (`0x09`), `0x78` (`0x07`, `0x11`).
Zustand bis `0x84` Bytes (`0x11`). Fast jedes Paar schreibt also in den Nachbarn, und jeder Baustein mit Verzögerungsleitung
(`0x11`, `0x12`, `0x16`, `0x18`) überschreibt in Stufe 2 den DSP-Code.

## Patch

`tools/patch/stage2_memory.py`, im BLECH-Set als `stage2-memory`. Fünf Befehle der Schleife:

| Adresse | vorher | nachher |
|---|---|---|
| `0x01F0C166` | `R2 = 0x50` | `R2 = 0x2D54` (Koeffizienten Stufe 2 minus Zustand Stufe 1) |
| `0x01F0C16A` | `R3 = 0x70` | `R3 = 0x3754` (Zustand Stufe 2 minus Zustand Stufe 1) |
| `0x01F0C178` | `R2 = R1 + R2` | `R2 = R5 + R2` |
| `0x01F0C1CC` | `[I0++] = R6` (0) | `[I0++] = R0` (Puffer des Parts) |
| `0x01F0C1EC` | `R4 = 0x1B4` | `R4 = 0xA0` |

Danach:

- Koeffizienten Stufe 2: `0xFF904600 + 0xA0 * Part`. Stufe 1 behält die ganzen `0xA0` Bytes des Part-Blocks.
- Zustand Stufe 2: `0xFF905000 + 0x118 * Part`, bis `0xFF906180`. Stufe 1 hat `0xA0` Bytes bis zu den Mixer-Wörtern.
- SDRAM Stufe 2: der Puffer des Parts.

`0xFF904600` bis `0xFF906180` liegt in L1-Datenbank B über dem Stack des DSP (`0xFF904000` bis `0xFF9045FF`). Als Cache
schaltet das Programm nur die obere Hälfte von Bank A (`DMEM_CONTROL = 0x100B`). Kein Boot-Block lädt dorthin (der Generator
prüft das), und in 400 Paaren schreibt dort sonst niemand.

Der DSP-Strom hat keine Prüfsumme über die Nutzdaten (keine Callback- oder CRC-Flags, Block 107 trägt Flag `0x1`). `check.py`
lässt am DSP-Strom genau diese fünf Befehle durch und sonst nichts (`tools/emu/stage2_memory_check.py`).

## Ergebnis im Simulator

400 Paare wie in [Stufe 1 und Stufe 2 im DSP-Simulator](2026-11-13-stufe2-simulation.md): 361 laufen, 0 Absturz,
39 fremder Speicher. Vorher 174, 152, 74.

| 1 \ 2 | 00 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 0a | 0f | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **00** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **01** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **02** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **03** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **04** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **05** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **06** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **07** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **08** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **09** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **0a** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **0f** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **10** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **11** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **12** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **13** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **14** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **15** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |
| **16** | o | o | o | o | o | o | o | o | o | o | o | o | o | o | o | o | o | o | o | o |
| **18** | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | . | o | . |

Was bleibt:

- **`0x16` in Stufe 2 (Spalte):** der Baustein liest beim Start vier Tempo-Ressourcen (Argumente `+0x18` bis `+0x24`), die das
  Programm nach der Schleife nur Stufe 1 gibt. In Stufe 2 bekommt er 0 und schreibt in den DSP-Code. Bleibt gesperrt.
- **`0x16` in Stufe 1 (Zeile):** schreibt `0xFF802DC0`, seine eigene Ressourcen-Tabelle, genau wie allein. Kein Fehler des
  Paares; am Gerät schon als `stage1NeedsSolo` gemessen (kein Ton mit zweiter Stufe).
- **Zwei Bausteine mit Verzögerungsleitung** (`0x11`, `0x12`, `0x16`, `0x18` in Stufe 1 vor `0x11`, `0x12`, `0x18` in
  Stufe 2): jeder nimmt den ganzen Puffer des Parts. Der Simulator sieht das nicht als fremden Speicher, die beiden
  Verzögerungsleitungen überschreiben sich aber. Erwartet: falscher Klang, kein Absturz. Bleibt gesperrt.

Der Simulator gibt keinen Ton aus. "Läuft" heißt: kein Absturz und nichts außerhalb des eigenen Speichers, nicht "klingt
richtig".

## Sperren im Baukasten

`data/findings.mjs` bleibt in diesem Stand unverändert. Die Sperren gelten für jede Firmware, auch für Blau, ältere
Versionen und Effekte, die geteilt werden. Lockern geht erst nach dem Gerätetest, und nur für Firmware mit `stage2-memory`.

## Blau

Die Schleife gibt es auf Blau auch (`0x01F0C0D4`, Zustandsbasis in `R6`). Der entsprechende Patch wäre `0x01F0C0FA`,
`0x01F0C0FE`, `0x01F0C10C` (`R2 = R6 + R2`), `0x01F0C160`, `0x01F0C180`. Er ist nicht im Simulator geprüft, und ob Bank B
auf Blau darüber frei ist, steht noch aus.

## Am Gerät zu prüfen (Rot, Firmware mit `stage2-memory`)

1. Normaler Start, Katalog-Effekte und Werkspresets klingen wie vorher.
2. `0x07` vor `0x05`, `0x0f` vor `0x05` (vorher Störgeräusche, jetzt sauber erwartet).
3. `0x0a` vor `0x01`, `0x09` vor `0x0a`, `0x0a` vor `0x09` (vorher Absturz oder kein Ton).
4. `0x11` (Chorus) und `0x12` (Flanger) in Stufe 2, etwa hinter `0x0a` (vorher Absturz).
5. `0x18` (Short Delay) in Stufe 2 hinter `0x0a` (vorher Ton weg am ganzen Gerät).
