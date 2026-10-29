# BEAT 8: Steps als Achtel, ein Pattern doppelt so lang (29.10.)

Stand 29.10.2026, Emulator mit Hacktribe 2.02, Korgs rotem 2.02 und Korgs blauem 2.02. Wunsch: ein Pattern läuft doppelt so
lang, bei 160 BPM so, als stünde das Tempo auf 80, also 8 Takte statt 4, und zwei Geräte laufen trotzdem normal synchron. Patch
`data/patches/beat-eighth.json` (rot) und `data/patches/beat-eighth-synth.json` (blau), Bauer `tools/patch/beat_eighth.py`, Fälle
`tools/emu/beat_eighth_cases.py`. Am Gerät nicht geprüft.

Marker: **gemessen** heißt im Emulator ausgeführt und gesehen, **offline** heißt Code gelesen, dazu **hergeleitet** und **offen**.

## Was BEAT macht

| Befund | Marker |
|---|---|
| BEAT ist Byte 38 im Pattern-Block (`pattern.beat`), der Getter `0xC004A378` liest es (`ldrb r0, [r0, #0x2a]`) | offline |
| Beim PLAY nimmt der Sequencer `Tabelle[BEAT]` aus `0xC00E2DDC` (`06 03 08 04`) als Teiler, 96 geteilte Ticks sind ein Step; vier Stellen (`0xC005D84C`, `0xC005E534`, `0xC005E65C`, `0xC005EA80`), keine prüft den Bereich | offline |
| Hinter der Tabelle stehen vier Nullbytes, dann ein Zeigerfeld; auf `0xC00E2DE0` bis `0xC00E2DE7` zeigt kein Literal | offline |
| Der Teiler 12 gibt 1152 Ticks je Step, eine Achtel | hergeleitet |
| Korgs Firmware mit BEAT 4 und Nullbyte in der Tabelle: Teiler 0, ein Step alle 2 ms, die Anzeige zeigt "?", keine Assertion | gemessen |
| Der Teiler wird beim PLAY genommen und steht danach in `0xC06900A0` | gemessen |

## Der Patch

- `0xC00E2DE0` = 12: BEAT 4 ist ein Step je Achtel.
- Seite BEAT im Pattern Menü: die Klemme `0xC007D13C` geht bis 4 statt 3. Die Anzeige nimmt für 4 einen eigenen Text `\\8` (zwei
  Pixel Abstand wie bei `\\8 Tri`, der Backslash ist im Font ein Pixel breit) statt "?", der Listentext `0xC008C124` dazu `8`.
- Export: EXPORT AUDIO und die übrigen Exporte rechnen die Länge eines Parts in Samples bei 48 kHz aus Steps je Viertel (`08 03 06`
  für BEAT 1 bis 3) und Steps je Takt (`10 0C 0C`); BEAT 0 und alles über 3 nimmt 4 und 16. Vier Stellen mit demselben Muster
  (`0xC002ED28`, `0xC00327E8`, `0xC00334C8`, `0xC003371C`): `cmp #2` wird `cmp #3`, die zwei Literale zeigen auf Kopien der Tabellen
  mit einem vierten Eintrag, 2 Steps je Viertel und 16 je Takt. Die Funktion bei `0xC002ED08` ist eine davon, die anderen drei
  lesen BEAT aus einer Ablage oder aus dem Block eines anderen Patterns (EXPORT P.SET AUDIO und CHAIN AUDIO, hergeleitet aus der Lage).
- Slices (nur rot): `0xC009A934` baut die Step-Zuordnung eines geslicten Samples (64 Byte am Part-Objekt `+0x108`) aus einer
  Tabelle 4 mal 4, Zeile der Beat, auf den das Sample geschnitten ist, Spalte BEAT, Index `(Zeile << 2) | BEAT`. BEAT 4 läse die
  nächste Zeile. Der Aufruf des Getters wird `ldrb r0, [fp, #0x2a]` und `and r0, r0, #3`, BEAT 8 nimmt also die Spalte von BEAT 16.
- Die neuen Daten (Text und die zwei Tabellen) liegen bei `0xC014FC00`, `FF` in allen drei Builds, vor dem Versionstext. Die
  Tabellen sind Kopien der Firmware mit einem Byte darüber. Kein eigener Code, kein Haken, keine Startphase.
- Blau: dieselbe Tabelle bei `0xC00C95B4`, dieselben vier Exportstellen, Klemme `0xC006F728`, Anzeige `0xC0071A20`; die Stellen
  stehen in `data/synth-map/beat-eighth.json`. Listentext und Slices gibt es dort nicht.
- Die App: `pattern.beat` nimmt 0 bis 4, 4 heißt "8tel". Patterns mit 4 laufen auf Korgs Firmware mit 500 Steps je Sekunde
  (siehe oben); eine Linter-Regel dafür gibt es bewusst nicht.

## Fälle (`tools/emu/beat_eighth_cases.py`, Hacktribe 2.02 nur mit diesem Patch, leerer Flash)

| Fall | Ergebnis | Marker |
|---|---|---|
| BEAT 0 bis 3 bei 160 BPM wie vorher: 93,77, 46,91, 124,95 und 62,51 ms je Step | ja | gemessen |
| BEAT 8 bei 160 BPM: 187,5 ms je Step, Teiler 12, das Doppelte von BEAT 16 (93,77 ms) | ja | gemessen |
| BEAT 8 bei 160 BPM gleich BEAT 16 bei 80 BPM: 187,5 gegen 187,5 ms | ja | gemessen |
| MIDI Clock out bleibt beim echten Tempo: F8 alle 15,63 ms bei 160 BPM mit BEAT 8, 31,26 ms bei 80 BPM | ja | gemessen |
| Clock Mode External MIDI, F8 genau 160 BPM: BEAT 8 zählt 12 Pulse je Step (187,43 ms), BEAT 16 zählt 6 (93,73 ms) | ja | gemessen |
| Seite BEAT: das Rad geht 0, 1, 2, 3, 4 und bleibt bei 4, zurück bis 0 und bleibt dort; bei 4 steht `\\8`, nirgends "?"; im Bildspeicher steht die 8 an derselben Stelle wie die 8 von 8 Tri und endet an der rechten Kante von 16 und 32 | ja | gemessen |
| BEAT 4 auf der Seite, WRITE: der Bankplatz hat 4, anderes Pattern und zurück, wieder 4 | ja | gemessen |
| Gate Arp mit gehaltenem Pad, beim Spielen: BEAT 8 bei 160 und BEAT 16 bei 80 je 17 Noten, 184,62 ms im Mittel | ja | gemessen |
| Gate Arp gestoppt nach einem PLAY: beide 16 Noten, 187,6 ms | ja | gemessen |
| Exportlänge (`0xC002ED08`, zwei Takte): BEAT 8 bei 160 BPM 288000 Samples wie BEAT 16 bei 80, BEAT 0 bis 3 wie die Formel der Firmware | ja | gemessen |
| Slices: für 16 und 32 Slices, geschnitten auf jeden der vier Beats, ist die Zuordnung mit BEAT 8 gleich der mit BEAT 16 (16 Slices auf 16tel: Step n spielt Slice n) | ja | gemessen (Anzahl und Beat der Slices im Emulator vorgegeben) |
| REC eines Reglers, ein Wert je 187,5 ms nach der Uhr, nicht nach dem Step: BEAT 8 bei 160 und BEAT 16 bei 80 treffen dieselben 32 Steps, die Spur ist Byte für Byte gleich, 32 Werte, also 2 Takte zu 16 Steps | ja | gemessen |

Blau (Korgs blaues 2.02 mit dem BLECH-Satz): Seite BEAT wie rot, Exportlänge (`0xC002BBC4`) wie rot, nach PLAY mit BEAT 8 Teiler 12
und F8 alle 15,63 ms bei 160 BPM. Gemessen. Die Noten selbst sind auf der blauen nicht gemessen, die Messpunkte der Engine sind die
des Samplers.

## Gate Arp

Der Gate Arp richtet sich nach dem Teiler, den der Sequencer beim letzten PLAY genommen hat (gestoppt nach PLAY: BEAT 32 bei 160 BPM
46,89 ms, 8 Tri 125,03 ms; gemessen). Er braucht darum nichts Eigenes, mit dem Tabelleneintrag ist BEAT 8 bei 160 schon BEAT 16 bei
80. Vor dem ersten PLAY nach dem Einschalten steht der Teiler auf 6, egal welcher BEAT: das macht die Firmware bei jedem BEAT so
(gemessen mit BEAT 32).

## Was mitgeht

| Was | Bei BEAT 8 | Marker |
|---|---|---|
| Swing, Gate, Groove | in 1/96 Step, wachsen mit; Swing wird Achtel-Swing | hergeleitet |
| Motion Sequence, TAP Motion | ein Wert je Step, siehe REC oben | gemessen |
| LENGTH | 16 Steps je Takt bleiben, 4 Takte sind 64 Achtel, also 8 echte Takte | hergeleitet |
| TAP-LED | blinkt im echten Viertel (375 ms bei 160 BPM) | gemessen |
| Plugin-Ereignis `beat` | bleibt jeder vierte Step, mit BEAT 8 also jede halbe Note des echten Tempos | offline |
| Triolen-Sonderfälle `0xC005C790`, `0xC005EB9C` | 4 ist keine Triole, wie BEAT 16 | offline |

## Offen

- Am Gerät nicht geprüft.
- Chain, Sync Group und Pattern Set mit BEAT 8 sind nicht gelaufen.
- Die drei Exportstellen außer `0xC002ED08` sind nur gelesen, nicht im Emulator aufgerufen.
- 13 weitere Stellen im Code lesen ein Byte bei `+0x2A` (etwa `0xC0030A54`); ob sie das Pattern meinen, ist nicht geprüft. Ein
  Lese-Watch auf das BEAT-Byte hat beim Spielen nur den Getter beim Start gesehen (gemessen).
