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

`tools/patch/stage2_memory.py`, im BLECH-Set als `stage2-memory`. Fünf Befehle der Schleife, die Länge von Heap 1 und ein Block im Startstrom:

| Adresse | vorher | nachher |
|---|---|---|
| `0x01F0C166` | `R2 = 0x50` | `R2 = 0x5C28` (Koeffizienten Stufe 2 minus Zustand Stufe 1) |
| `0x01F0C16A` | `R3 = 0x70` | `R3 = 0x4A74` (Zustand Stufe 2 minus Zustand Stufe 1) |
| `0x01F0C178` | `R2 = R1 + R2` | `R2 = R5 + R2` |
| `0x01F0C1CC` | `[I0++] = R6` (0) | `[I0++] = R0` (Puffer des Parts) |
| `0x01F0C1EC` | `R4 = 0x1B4` | `R4 = 0xB4` |
| `0x01F02448` | Heap 1: `0x39FF` Bytes | `0x1D20` Bytes (Heap-Tabelle: Basis, Länge, Nummer) |
| Startblock 145 (Datei `0x130918`) | füllt `0xFF900CD0` bis `0xFF903FF0` mit Nullen (`0x3320`) | bis `0xFF908000` (`0x7330`), Prüfbyte des Kopfs `0x0D` zu `0x5D` |

Danach:

- Zustand Stufe 2: `0xFF906320 + 0x118 * Part`. Stufe 1 hat `0xA0` Bytes bis zu den Mixer-Wörtern.
- Koeffizienten Stufe 2: `0xFF9074D4 + 0xB4 * Part`, bis zum Ende von Bank B (`0xFF908000`). Stufe 1 behält die ganzen
  `0xA0` Bytes des Part-Blocks.
- SDRAM Stufe 2: der Puffer des Parts.
- Heap 1: `0xFF904600` bis `0xFF906320` statt bis zum Ende von Bank B.
- Beim Start steht in Bank B ab `0xFF900CD0` bis zum Ende überall 0.

Der DSP-Strom hat keine Prüfsumme über die Nutzdaten (keine Callback- oder CRC-Flags, Block 107 trägt Flag `0x1`). `check.py`
lässt am DSP-Strom genau diese Änderungen durch und sonst nichts (`tools/emu/stage2_memory_check.py`).

## Heap 1 und der erste Versuch

Ab `0xFF904600` (über dem Stack) liegt Heap 1 des DSP, laut Heap-Tabelle bei `0x01F02440` bis zum Ende von Bank B. Das
Betriebssystem des DSP nimmt daraus die Stacks und Kontrollblöcke seiner Tasks. Der Simulator ruft die Audio-Funktion direkt
auf und überspringt den Start des Betriebssystems, deshalb sah er den Heap nicht.

Der erste Stand des Patches legte Stufe 2 nach `0xFF904600` und `0xFF905000`, mitten in den Heap. Vor dem Flashen am Gerät
gelesen (Rot, alte Firmware, Leerlauf, zweimal im Abstand von 2 s, Host-Port-Lesen der Firmware): `0xFF905250` bis
`0xFF9053A0` ändert sich und hält gesicherte Register und Rücksprünge `0xFFA0xxxx`, also einen Task-Stack. Im Kopf von
Heap 1 steht bei `+0xC` `0xFF9054E0`; gelesen als Ende des belegten Teils (hergeleitet aus der Heap-Init `0x01F100D4`,
nicht aus dem Allocator) sind `0xEC0` Bytes belegt. `0xFF906180` bis `0xFF907FFF` änderte
sich nicht.

Jetzt endet Heap 1 bei `0xFF906320` (`0x1D20` Bytes, knapp doppelt so viel wie belegt), und Stufe 2 nimmt die `0x1CE0`
Bytes darüber. Reicht der Heap einmal nicht, liefert er keinen Speicher, statt Stufe 2 zu überschreiben. Nach Spielen und
Stoppen am Gerät gelesen: das Ende steht weiter bei `0xFF9054E0`.

## Baustein `0x15` und das Wort unter den Koeffizienten

`0x15` hält in seinem Zustand (`+0x8`) einen Zeiger auf das Wort `0xC8` unter seinen Koeffizienten, in Stufe 1 also
Part-Block `+0x8`. Jedes Frame liest er es, rechnet mit dem Wert und schreibt ihn unverändert zurück (`0xFFA0784A`).
Mit Koeffizienten im Abstand `0xA0` lag das Wort in Stufe 2 im Heap oder in den Koeffizienten des übernächsten Parts:
nichts kaputt, aber `0x15` hätte mit fremden, sich ändernden Werten gerechnet. Darum der Abstand `0xB4` und `0x34`
Bytes Lücke zwischen Zustand und Koeffizienten: das Wort liegt für jeden Part in Speicher, den kein Baustein der Stufe 2
benutzt (`0x14` Bytes hinter den Koeffizienten zwei Parts tiefer, die Lücke, oder das ungenutzte Ende des Zustands von
Part 15). `build_patch` prüft das.

## Zufälliger Speicher beim Einschalten

Erster Gerätetest (Rot, Firmware mit dem Patch ohne den Startblock, 2026-11-14): auf Pad 5 liefen alle Paare aus der
Liste unten, auf Pad 8 hängte `0x0a` vor `0x12` den DSP. Pads ließen sich noch wechseln, Regler und IFX an/aus nicht mehr;
nach einem Samplewechsel und Spielen des Pads stürzte das ganze Gerät ab. IFX muss dafür nicht an sein, der Effekt ist
auch bei IFX aus geladen.

Die Lesung von Bank B im Leerlauf (alte Firmware) zeigt, warum es vom Pad abhängt: `0xFF9054E0` bis `0xFF908000` hält
zufällige Bytes vom Einschalten, die niemand schreibt. Der Startstrom löscht nur bis `0xFF903FF0`, kein anderer Block lädt
darüber. Stufe 2 startete also auf Müll, für jeden Part anderem. Der Simulator hat dort Nullen und sah es nicht.

Darum füllt der Startblock 145 jetzt bis zum Ende von Bank B. Er löscht damit auch den Bereich des Stacks
(`0xFF904000` bis `0xFF904600`); das ist harmlos, solange der Stack des Boot-ROMs dort nicht liegt (angenommen, nicht
geprüft). `stage2_memory.py` prüft, dass kein anderer Block in den neu gelöschten Bereich lädt.

## Ergebnis im Simulator

400 Paare wie in [Stufe 1 und Stufe 2 im DSP-Simulator](2026-11-13-stufe2-simulation.md), mit der Aufteilung oben: 361
laufen, 0 Absturz, 39 fremder Speicher. Vorher 174, 152, 74. Erlaubt sind Stufe 2 und die Wörter darin, die kein Baustein
benutzt (`free_word`).

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

Befunde, die der Patch behebt, tragen in `data/findings.mjs` `fixedBy: "stage2-memory"`: Stufe 2 mit `0x01`, `0x02`,
`0x08`, `0x18`, der Decimator `0x09` in Stufe 1 und alle Paare außer Delay hinter Delay (erste Stufe `0x11`,
`0x12`, `0x16` oder `0x18`, zweite `0x11`, `0x12` oder `0x18`) und außer `0x11` oder `0x12` in Stufe 2. Gesperrt bleiben
diese Paare, `0x09` in Stufe 2 und `0x16` in beiden Stufen.

`0x11` und `0x12` in Stufe 2 stürzen am Gerät trotz Patch ab: `0x0a` vor `0x12` hängte die Audio-Engine (Rot, Firmware
`ef02f1d2` mit allen sieben Änderungen, 2026-11-14), im Simulator lief das Paar. `0x11` ist gesperrt, weil es zur selben
Familie gehört, am Gerät nicht geprüft. `0x0a` vor `0x09` (Decimator in Stufe 2) stürzte am Gerät ebenso ab.
`0x0a` vor `0x18` lief am Gerät.

Die App gibt die behobenen Befunde frei, solange die Firmware den Patch trägt. Mit gelesener Firmware prüft
`hasStage2Memory` das erste Wort des Patches (Datei `0x12A8D6`), ohne gelesene Firmware gilt der Patch als vorhanden.
Die Kartendatei `e2sFx.all` gibt sie auf Rot frei, der Baukasten immer. Blau trägt den Patch nicht und bleibt gesperrt.

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
6. Alle Paare auf mehreren Pads, besonders `0x0a` vor `0x12` auf Pad 8 (hing ohne den Startblock).
