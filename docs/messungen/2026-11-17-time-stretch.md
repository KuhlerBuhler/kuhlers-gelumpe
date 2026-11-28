# Time Stretch: offline auf dem ARM, live im DSP

Stand 17. November 2026. Frage: geht Tempo
ändern ohne Tonhöhe auf dem Electribe 2 Sampler mit blechtribe? Zwei getrennte Stufen: offline (Sample einmal neu
rechnen, Faktor rund 85 bis 115 %) und live (Stretch im Blackfin beim Abspielen, per Regler oder BPM).

Grundlage: [DSP](../glossary.md#dsp)-Programm aus [Hacktribe](../glossary.md#hacktribe) 2.02 (sha256 `7cb4825c184a7e3f…`), ausgepackt mit
[`dsp_extract.py`](../../tools/dsp/dsp_extract.py), disassembliert mit Blackfin-binutils 2.42. ARM-Messung in Unicorn
mit den Gerätekosten aus [Emulator-Timing](2026-10-16-emulator-timing.md). Kein Gerätezugriff, kein gekoppelter
DSP-Lauf.

Marker: **gemessen** (in dieser Arbeit ausgeführt und gezählt), **gelesen** (Code oder Doku gelesen, mit Adresse oder
Link), **hergeleitet** (aus gemessenen oder gelesenen Werten gerechnet), **Urteil** (Einschätzung).

## Kurz

| Stufe | Ergebnis | Marker |
|---|---|---|
| Offline auf dem ARM | **machbar**. WSOLA in Festkomma für 4 s mono 48 kHz: 0,34 bis 0,67 s Gerätezeit mit grober Suche, 1,3 bis 2,5 s mit mittlerer, 4,9 bis 9,6 s mit voller | gemessen (Befehle), hergeleitet (Gerätezeit) |
| Offline auf dem DSP | **nicht sinnvoll**. Der DSP hat kaum freie Zeit und kein Programm dafür; der ARM ist zu rund 80 % frei | hergeleitet, Urteil |
| Rückweg in den Sample-Speicher | **machbar** über den Host-Port wie beim Sample Swap; Tabellen auf dem ARM nachziehen | gelesen, hergeleitet |
| Live ohne DSP-Patch | **nicht machbar** in brauchbarer Qualität: der ARM kann den Lesezeiger einer Stimme springen lassen, aber ohne Überblendung, also mit Klicks | gelesen, Urteil |
| Live mit DSP-Patch | **unklar**. Lesezeiger, Schrittweite und Fetch sind gefunden, ein Vorbild mit zwei Leseköpfen gibt es schon (Generator `0x20`). Offen ist, ob bei vollem Pattern Zeit frei ist | gelesen, hergeleitet, offen |

## 1. Offline

### Messung: WSOLA auf dem ARM926

WSOLA (überlappende Rahmen, Versatz per Korrelation gesucht) in C, Festkomma, ohne Division und ohne FPU, gebaut für
`armv5te` mit `-mcpu=arm926ej-s -O2` (824 Byte Code). Unicorn führt es auf einem Testsignal aus: 4 s mono 48 kHz
(192000 Samples), abklingende 55-Hz-Schläge alle 0,5 s plus Rauschen. Rahmen N = 1024 (21 ms), Hop 512, Suche ±256
Samples (±5 ms). Gezählt werden Befehle, Multiplikationen und gelesene Bytes; die Gerätezeit folgt aus 5 ns pro Befehl,
+6,7 ns pro Multiplikation und +0,5 ns pro Byte bei Cache-Treffer oder +6,8 ns pro Byte beim Streamen
([Emulator-Timing](2026-10-16-emulator-timing.md), gemessen am Gerät).

`corr_step`/`search_step` dünnen die Korrelation und die Versatzsuche aus (1 = jedes Sample, 4 = jedes vierte).

| Faktor | Suche | Ausgabe | Befehle | Gerät, Cache-Treffer | Gerät, Streamen |
|---|---|---|---|---|---|
| 85 % | voll (1/1) | 162816 (0,848) | 841 Mio. | 4,9 s | 7,1 s |
| 85 % | mittel (2/2) | 162816 (0,848) | 215 Mio. | 1,3 s | 1,8 s |
| 85 % | grob (4/4) | 162816 (0,848) | 58 Mio. | 0,34 s | 0,50 s |
| 115 % | voll (1/1) | 220160 (1,147) | 1138 Mio. | 6,7 s | 9,6 s |
| 115 % | mittel (2/2) | 220160 (1,147) | 291 Mio. | 1,7 s | 2,5 s |
| 115 % | grob (4/4) | 220160 (1,147) | 79 Mio. | 0,46 s | 0,67 s |

**Gemessen**: die Zeilen oben (Befehle, Multiplikationen, Bytes in Unicorn gezählt). **Hergeleitet**: die Gerätezeit.
Die Wahrheit liegt nah an der Spalte Cache-Treffer: Korrelation und Referenz lesen je 1 KiB, das passt in den 16-KiB-D-Cache
und wird pro Versatz wiederverwendet (hergeleitet). Die Spalte Streamen ist die obere Schranke.

**Urteil**: mit Suchschritt 2 bis 4 ist die Qualität für Drum-Loops üblich ausreichend; das ist nicht gehört, nur
gerechnet. Ein Phasenvocoder wäre ohne FPU um ein Vielfaches teurer (Urteil, nicht gemessen).

### Wo es laufen kann

- ARM-Last: im Emulator ist der ARM bei laufendem Pattern zu rund 80 % frei
  ([CPU-Last](2026-11-08-cpu-last-blech.md), gemessen dort). Eine Rechnung von 0,3 bis 2,5 s passt also, wenn sie in
  kleinen Stücken in einer niedrig priorisierten Aufgabe läuft und den Sequencer nicht blockiert (hergeleitet).
- Speicher: Eingabe 384 KB, Ausgabe bei 115 % rund 442 KB, Akkumulator als 32 Bit doppelt so groß (hergeleitet). Frei sind
  `0xC1010000..0xC4000000`, rund 47 MiB, davon belegt Sample Swap `0xC274F000..0xC4000000`
  ([RAM frei](2026-10-22-ram-frei.md), gelesen).
- DSP: das volle Pattern braucht laut Schätzung schon 10 000 bis 15 000 der 10 752 Zyklen pro Sample
  ([Idee 52](../ideen/52-ton-im-emulator.md), hergeleitet dort). Offline-Rechnen auf dem DSP lohnt nicht (Urteil).

### Rückweg in den Sample-Speicher

Die Samples liegen im DSP-SDRAM, nicht im ARM-RAM. Der Weg dahin ist derselbe wie beim Sample Swap
(feature/sample-swap-native-dsp, #166):

1. Quelle lesen: das Original aus dem DSP-SDRAM über den Host-Port (`0x60000000` Daten, `0x60000002` Steuerung,
   Lesen mit `0xA9`) oder direkt von der Karte (gelesen, Sample Swap).
2. Auf dem ARM rechnen (siehe oben).
3. Zurückschreiben mit Host-Port `0xAB` an freien DSP-Speicher. Am Gerät gemessen 11 MiB/s, also rund 35 ms für
   375 KiB (gemessen dort, hergeleitet hier). Das erste Nutzer-Sample liegt bei `0x365EC0`; Sample Swap legt oberhalb des
   Rings bei `0x365EE0` an (gelesen).
4. Tabellen nachziehen: Abspieltabelle `0xC0362EE8 + i·0x10` (Start, Loop, Ende, One-Shot), Metadaten
   `0xC036AD88 + i·0x45C` (PCM-Länge bei +4, Rate bei +16, 64 Slice-Einträge) und die Stimmenvorlage, die der ARM an
   den DSP schickt (gelesen: [Sample-Metadaten](2026-10-07-sample-metadaten-ram.md); welche Felder alle mitwachsen
   müssen, hergeleitet).

Bei Faktor über 100 % wird das Sample länger. Dann braucht es freien DSP-Speicher statt Überschreiben an Ort und Stelle;
das liefert die Verwaltung aus Sample Swap (hergeleitet). Die Samples insgesamt fassen 25 MiB (gelesen).

**Ergebnis offline: machbar.**

## 2. Live

### Wie die Stimme ihr Sample liest

Alles gelesen im DSP-Programm, die Bedeutung der Felder ist hergeleitet.

- **Stimmenblöcke**: 24 Blöcke à `0x1A` Worte ab `0xFF900EAC` (Parameter `0x43AB`). w0 Gate, w1 Note
  (1/256 Halbton), w2 Tonhöhenversatz, w3 Generatortyp, w10 Startadresse im DSP-SDRAM.
- **Stimmenschleife** `0xFFA0141A`, einmal pro Sample: `P5 = 0xFF9030A4`, `P4 = [P5+0xC] = 0xFF802870`. Für jede
  Stimme mit Gate holt sie den Generator aus der Tabelle bei `0xFFB00010` über w3 und ruft ihn mit `P2 = &w4`, danach
  Gain und Summe in den Part-Bus `[P4+0x20+2·idx]`. Rumpf rund 52 Befehle (gezählt).
- **Generatortabelle** `0xFFB00010` (aus ROM `0x01F02478`): `0x22` → `0xFFA02EDE` (Sample-Player). Die Liste aus dem
  GNU-Simulator (`0x21` → `0xFFA02EDE`, `0x22` → `0xFFA0331E` "Codec-Eingang") war um einen Platz verschoben, ein Fehler des
  Simulators beim Kopieren der Tabelle ([Korrektur](2026-11-12-dsp-im-simulator.md#korrektur-1611)). Die Adressen
  `0xFFA0314E`, `0xFFA0331E`, `0xFFA0346C`, `0xFFA03508`, `0xFFA0363E`, `0xFFA03714` gehören also zu den Typen um eins
  über den alten Angaben (hergeleitet).
- **Sample-Player `0x22`** (`0xFFA02EDE`):
  - Lesezeiger: 40-Bit-Phasenakku in w5 (A0.X) und w6 (A0.W). Position = A0 >>> 13, also 13 Nachkommabits,
    `0x2000` = 1,0.
  - Schrittweite (Pitch-Inkrement): w7, wird jedes Sample auf A0 addiert.
  - Loop: Start w4 >>> 1, Länge w8 >>> 1, Ende = Start + Länge, Umbruch mit A0 -= Länge << 13. w13 Modus (0 bis 4),
    w12 Richtung, w11 Nachbarversatz für die Interpolation, w15 Ausgabeshift.
  - Fetch: schreibt die SDRAM-Adresse `pos·2 + w10` in die MDMA-Quelldeskriptoren `[P0]` und `[P0+0xC]`, ein Sample im
    Voraus. Im nächsten Sample wartet er auf `MDMA_D0_CURR_DESC_PTR` `0xFFC00F20` (Schleife bei `0xFFA02F2A`) und liest
    die zwei geholten Halbworte über L1-Zeiger. Gestartet wird die MDMA in der Rahmenfunktion
    (`0xFFA0187E..0xFFA01890`).
  - Dann lineare Interpolation, Ende-Flag und Release-Gain im Zustand.
  - Hauptpfad rund 133 Befehle, grob 190 bis 210 Zyklen pro Stimme und Sample ohne MDMA- und SDRAM-Wartezeit (gezählt,
    Zyklen hergeleitet).
- **Wer w7 setzt**: Kommando `0x2B` (Handler `0xFFA051C0`) schreibt w1 = Note << 16 und ruft `0xFFA06970` mit
  `R2 = &w4`. Über die Typtabelle `0x01F03068` landet Typ `0x21` bei `0xFFA06FF0`, der `0xFFA068C8`
  (Tonhöhe in Rate umrechnen) und `0xFFA07394` (Wort relativ zur Stimme schreiben) ruft. Der DSP rechnet die Schrittweite
  also selbst aus der Note; für Typen ab `0x21` ohne Klemme auf `0x7FFF` (gelesen; dass das Zielwort w7 ist,
  hergeleitet).
- **Tempo im DSP**: FIFO-Code `0x20` schickt das Tempo in 1/100 BPM an alle Kanäle, der DSP hält es bei `0xFF900004`
  (gelesen).

### Zwei Leseköpfe gibt es schon: Generator `0x20`

`0xFFA0314E` (rund 140 Befehle, gezählt) liest mit zwei Köpfen I0/I1 aus einem Ringpuffer (B0/L0 aus Stimmenworten) und
blendet sie mit einem Dreieck (Betrag der Phase) über; vier direkte 16-Bit-Lesezugriffe ins SDRAM (gelesen). Das ist
der klassische Zwei-Kopf-Pitch-Shifter (hergeleitet), also genau das Muster für granularen Stretch: beide Köpfe laufen
mit Rate 1,0 (Tonhöhe bleibt), der Anker der Körner wandert mit der Stretch-Rate weiter.

### Ohne DSP-Patch

Der ARM kann mit Postfach-Kommando 0/1 jedes Stimmenwort setzen (gelesen, [DSP-Modell](2026-11-12-dsp-modell.md)),
also auch w5/w6 (Lesezeiger). Damit springt der Kopf grob alle paar Millisekunden zurück oder vor. **Urteil**: ohne
Überblendung klickt jeder Sprung; mit zwei Stimmen und Velocity-Gain als Überblendung in 1-ms-Schritten ginge es
holprig, kostet aber zwei Stimmen pro Spur und viel Postfach-Verkehr. Nicht brauchbar als Feature.

### Mit DSP-Patch

Neuer Generatortyp nach dem Vorbild von `0x20`, gespeist aus dem Sample statt aus einem Ring:

- zwei Köpfe mit Schrittweite = Pitch, Körner von rund 20 bis 40 ms, Dreieck-Überblendung;
- der Anker rückt pro Sample um `Stretch × Schrittweite` vor;
- Stretch = aktuelles BPM aus `0xFF900004` geteilt durch Original-BPM des Samples, oder ein Wert vom Regler
  (SHIFT+EDIT) per Postfach.

Kosten grob 2 × 140 bis 200 Zyklen pro Stimme und Sample (hergeleitet aus den Zählungen oben), also rund 400 Zyklen.
Bei vier gestretchten Stimmen rund 1600 Zyklen, 15 % des Budgets von 10 752 Zyklen pro Sample (516 MHz / 48 kHz,
hergeleitet). Der zweite Kopf braucht einen zweiten MDMA-Deskriptor oder direkte SDRAM-Lesezugriffe wie bei `0x20`.

**Offen**:

- Freie DSP-Zeit bei vollem Pattern. Idee 52 schätzt 10 000 bis 15 000 Zyklen pro Sample, also nahe am Budget
  (hergeleitet dort). Gemessen ist das nicht. Die "DMA ~15 %" aus der QEMU-Arbeit sind Host-Zeit des Workers, keine
  DSP-Zyklen (gelesen im Plan).
- Ob die Stimmen im DSP-Simulator Nutzer-Samples wirklich aus dem SDRAM lesen, ist noch nicht beobachtet
  (offen in [Sample Swap nativ](https://github.com/KuhlerBuhler/kuhlers-gelumpe/tree/feature/sample-swap-native-dsp)).
- Platz im L1-Programmspeicher für einen neuen Generator (nicht geprüft).

**Ergebnis live: unklar, ohne DSP-Patch nicht machbar.**

## Alternative, die es schon gibt

Slice-Modus: 64 Slices pro Sample stehen in den Metadaten (gelesen). Slices im Tempo neu getriggert ändern das Tempo
ohne Tonhöhe, ganz ohne Stretch (Urteil). Für Drum-Loops reicht das oft.

## Belege

| Behauptung | Wie belegt |
|---|---|
| WSOLA-Zahlen | Unicorn-Lauf, `wsola.c` und `run_wsola.py` (Scratchpad, nicht im Repo), Befehle pro Block mit capstone gezählt |
| Gerätezeit pro Befehl/Byte | [Emulator-Timing](2026-10-16-emulator-timing.md) |
| Generatoren `0xFFA02EDE`, `0xFFA0314E`, Stimmenschleife | `objdump -D -b binary -m bfin --adjust-vma=0xFFA00000` auf den ausgepackten L1-Code |
| Setter `0x2B` → `0xFFA068C8`/`0xFFA07394` | dieselbe Disassemblierung, ROM-Region `0x01F00000` für die Typtabelle |
| Postfach, Host-Port, Tempo `0x20` | [DSP-Modell](2026-11-12-dsp-modell.md), [DSP im Simulator](2026-11-12-dsp-im-simulator.md) |
| DSP-Budget voll | [DSP-Modell](2026-11-12-dsp-modell.md), [SDRAM-Freiraum](2026-11-20-dsp-sdram-freiraum.md) |
| ARM frei | [CPU-Last](2026-11-08-cpu-last-blech.md), [RAM frei](2026-10-22-ram-frei.md) |
