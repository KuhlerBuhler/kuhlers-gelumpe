# Die Gerätekarte

Jedes editierbare Feld der Electribe wird einmal als Daten beschrieben, in
`data/map/`. Die Oberfläche wird daraus erzeugt, der Linter liest daraus, die
Doku auch. Eine neue Messung heißt: ein Eintrag mehr oder ein Eintrag genauer,
und das Feld ist sofort im Editor.

Gemessen ist alles an einer Korg Electribe 2 Sampler mit Firmware 2.02 und
Hacktribe. Bei einem anderen Stand verschieben sich die Adressen.

## Ein Eintrag

Am Beispiel Cutoff (gekürzt, die echten Einträge stehen in `data/map/pattern.mjs`):

```json
{
  "id": "part.cutoff",
  "label": { "de": "Cutoff", "en": "Cutoff" },
  "area": "parts",
  "where": { "offset": 13 },
  "repeat": [{ "count": 16, "stride": 816, "label": "Part" }],
  "type": "u8",
  "transport": ["pattern-sysex", "e2sallpat"],
  "convert": "cutoffHz",
  "unit": "Hz",
  "range": [0, 127],
  "source": "measured",
  "evidence": "measure:2026-09-17/cutoff-resonance-peak"
}
```

Ein Feld, das an mehreren Stellen steht, trägt `sites` statt `where`. Die Länge
des Insert-Menüs steht zum Beispiel dreizehnmal in der Firmware, jede Stelle mit
ihrer Rechenvorschrift. Ein Feld, dessen Bedeutung vom Baustein in derselben
Stufe abhängt, trägt `when: { offset, equals }`; zwei Felder dürfen dieselben
Bytes belegen, wenn sie sich über `when` ausschließen. `tables` beschreibt, wo
ein Block wiederholt in der Firmware liegt. Ein Block, der ein Eintrag einer RAM-Tabelle außerhalb des
Abbilds ist (die drei Sample-Tabellen), trägt `meta.table` mit Adresse, Abstand und Anzahl, und
`ramEntry` in `src/map/address.mjs` macht aus einem Index die Adresse.

| Feld | Inhalt |
|---|---|
| `id` | stabiler Name, über den Linter, Oberfläche und Presets das Feld ansprechen |
| `label` | was die Oberfläche anzeigt |
| `area` | der Bereich der Oberfläche |
| `where` | wo die Bytes liegen, relativ zum Block. Bleibt intern. |
| `sites` | statt `where`, wenn ein Wert an mehreren Stellen steht |
| `repeat` | Ebenen für wiederholte Felder, je mit Anzahl, Abstand und Namen. Eine Step-Note ist Part mal Step mal Note: drei Ebenen. |
| `type` | `u8`, `s8`, `u16le`, `latin1:16`, `bytes:4` und so weiter |
| `transport` | auf welchen Wegen das Feld aufs Gerät kommt |
| `firmware` | für welchen Firmware-Stand die Adresse gilt, Pflicht bei allem, was in der Firmware liegt |
| `convert` | benannte Umrechnung zwischen Byte und Klartext |
| `edit` | `readonly` oder `expert` für Felder, die nicht frei bearbeitbar sind |
| `source` | `korg-spec`, `measured`, `derived` oder `unknown` |
| `evidence` | worauf sich der Eintrag stützt, in fester Form (siehe unten) |

Wie aus einem Eintrag eine Adresse wird, entscheidet je Weg eine eigene kleine
Funktion (`src/map/address.mjs`), nicht der Eintrag. Ein Part-Feld liegt im
Pattern-Puffer für die Pattern-SysEx und in der Backup-Datei hinter einem
`0x10100` großen Kopf. Ein FX-Feld liegt im RAM bei `0xC00B4F30 + ...` und in
der Datei bei `ram - 0xC0000000 + 0x100`. Die Karte sagt nur, was das Feld ist
und wo im Block.

Die Preset-Tabellen (`tables`) gelten für Hacktribes Anordnung: 100 Records hintereinander. Korgs Build legt sie
verstreut ab und findet sie über ein Feld mit Zeigern. Die Karte beschreibt das als `pointerTables`
(`data/map/firmware.mjs`, `POINTER_TABLES` in `src/map/index.mjs`): je Art das Literal hinter dem Getter, die
Klemme, die Zeigerfelder je Build und der Platz, den der Patch `preset-tables` für weitere Records lässt. Wo ein
Record liegt, sagt `recordOf` in `src/presets.mjs` aus dem Zeigerfeld der geladenen Datei, für jeden Build gleich
([Messung](messungen/2026-10-15-preset-tabellen.md)).

## Wo das Wissen liegt

- **Die Karte** (`data/map/`) beschreibt jedes Feld einmal: Kennung, Bezeichnung,
  Block und Offset, Typ, Transport, Umrechnung, Quelle und Beleg.
- **Die Befunde** (`data/findings.mjs`) halten Wissen über Verhalten fest: welche
  Einheit in Stufe 2 läuft, wo bei einem Parameter "aus" liegt, welche Lautstärke
  unspielbar ist. Das ist kein Ort im Speicher, sondern Wissen über Bausteine. Es
  folgt denselben Regeln für `source` und `evidence`.
- `src/layout.mjs` ist nur noch eine Sicht auf beides, für Code, der älter ist
  als die Karte. Dort kommen keine neuen Zahlen mehr hinein.
- `data/map/fx-params.mjs` wird aus `data/units.json` (AGPL, aus
  [hacktribe-editor](https://github.com/bangcorrupt/hacktribe-editor)) mit
  `node tools/units-to-map.mjs` erzeugt und nie von Hand bearbeitet. Ein Update
  von dort ist ein Lauf des Skripts.

## Belege

`evidence` hat eine von vier Formen, `test/map.test.mjs` erzwingt sie:

| Form | Bedeutung |
|---|---|
| `measure:<datum>/<name>` | eine Messung, Datei `docs/messungen/<datum>-<name>.md` muss existieren |
| `factory-check:<name>` | eine Prüfung gegen die Werks-Presets in `test/factory-checks.mjs` |
| `korg-spec:<abschnitt>` | eine Stelle der öffentlichen MIDI-Implementation von Korg |
| `derived:<quelle>` | aus einer anderen Quelle abgeleitet, zum Beispiel hacktribe-editor |

Ein bloßer Verweis auf ein Dokument ist kein Beleg. Felder, die niemand
versteht, tragen `source: "unknown"` und `edit: "expert"`.

Der Kartentest prüft außerdem: jede `id` ist eindeutig, jede `convert` gibt es,
`range` passt in `type`, und keine zwei Einträge belegen dieselben Bytes (außer
über `when`).

**Eine Behauptung prüfen, bevor sie in die Karte kommt.** Vier Presets sind
keine Messung. Mehrere Aussagen aus frühen Notizen waren falsch, als sie gegen
die Werks-Presets derselben Einheit gehalten wurden. Darum wird eine Aussage vor
dem Eintrag gegen die Werks-Presets geprüft, und das Ergebnis ist der Beleg: eine
Prüfung in `test/factory-checks.mjs`, die lokal mit eigenen Dateien läuft:

```bash
E2_VSB=/pfad/SYSTEM.VSB E2_PATTERNS=/pfad/backup.e2sallpat npm run test:local
```

## Umrechnungen

Umrechnungen sind eine kleine Bibliothek mit Namen (`src/map/convert.mjs`), keine
Formeln in der Karte.

| Name | Was | Grundlage |
|---|---|---|
| `cutoffHz` | `654 Hz * 2 ** ((byte - 64) / 12.09)`, ein Halbton je Schritt | gemessen |
| `oscPitchCents` | Tabelle -63 bis +63, drei lineare Zonen, ±2 Oktaven | gemessen |
| `envTime` | Attack und Decay teilen eine Kurve, 30 ms bis 5,3 s | gemessen |
| `resonanceDb` | 0 bis +24 dB, bei 127 Selbstoszillation | gemessen |
| `modSpeed` | Stufen zu je 8 Byte: 12 gemessene Notenwerte von 1/2 bis 1/64, darunter nicht aufgelöst | gemessen |
| `modType` | die offizielle Liste mit 72 Namen | Korg-Liste, 4 von 4 gegengeprüft |
| `filterType` | Byte 0 ist Aus, die Liste ist einsbasiert | gemessen und Korg-Liste |
| `noteName` | Notennummer zu C-1 bis G9, Step-Noten mit Versatz 1 | belegt |
| `scale` | im Pattern 35 Tonleitern nach Korgs Liste, die Tabelle in der Firmware hat 32, Namen um eins versetzt | Korg-Spec und dekodiert |
| `bipolar63` | Ruhepunkt in der Mitte, zum Beispiel `level_mod_int` | gemessen |
| `signed8` | -128 bis 127 als Rohwert, ohne Einheit: der Tune eines Samples, dessen Skala nicht gemessen ist | Rohwert, keine Einheit behauptet |
| `plain` | 0 bis 127 ohne Einheit, wo keine bekannt ist | |

Manche Umrechnungen bilden mehrere Bytes auf denselben Klartext ab: die
Modulationsgeschwindigkeit hat 15 Notenwerte für 128 Bytes. Darum wird nicht
`zuByte(vonByte(b)) === b` geprüft, sondern dass Hin und Zurück stabil ist.
Ein Feld, das nicht angefasst wurde, behält sein Byte: es wird nie durch eine
Umrechnung neu geschrieben.

## Was die Karte abdeckt

| Bereich | Weg aufs Gerät | Stand |
|---|---|---|
| Pattern: Name, Tempo, Swing, Länge, Beat, Key, Scale, Groove, MFX | Pattern senden, Backup-Datei | Korg-Spec, mit Differenzproben bestätigt |
| 16 Parts: Sample, Osc Pitch, Filter, Cutoff, Resonanz, Hüllkurve, Glide, Modulation, IFX, Amp | wie oben | großteils gemessen, Byte 38 offen |
| Steps: An, Trigger, Gate, Velocity, vier Noten | wie oben | belegt. Ein Step klingt nur, wenn An und Trigger gesetzt sind. |
| Motion Sequences | wie oben | Korg-Spec, am Gerät nicht geprüft |
| IFX- und MFX-Presets | live ins RAM (Hacktribe), Firmware (beide Builds, über die Zeigerfelder) | weitgehend, 23 von 28 Map-Bytes unbekannt; bei Korgs Build nur aus der Datei, mit dem Patch `preset-tables` bis 128 Plätze je Art |
| 72 Modulationsarten | Firmware | Name, Ziel, Vorgabe-Tiefe, Vorgabe-Speed und Kurve editierbar (Seite Modulationen), Wellenform, Sync, Polarität bekannt, Felder ab `+0x29` offen |
| 32 Tonleitern | Firmware | dekodiert |
| Groove-Templates | live ins RAM, Firmware | Format aus hacktribe-editor, am Gerät nicht geprüft |
| Global-Einstellungen | Global-SysEx | Korg-Spec, Menüseiten gemessen (siehe `data/map/global.mjs`) |
| Startbild | Firmware | belegt, 128 mal 64, ein Bit je Pixel |
| Menülängen | live ins RAM, Firmware | belegt |
| Samples: Name und Tune | live ins RAM | am Gerät geschrieben ([Namen](messungen/2026-10-07-sample-name-ram.md), [Metadaten](messungen/2026-10-07-sample-metadaten-ram.md)), editierbar auf der Seite Samples |
| Samples: Kategorie, Import-Nummer, Samplerate, PCM-Länge, Stereo, Start, Loop, Ende, One-Shot, Slices, Steps | RAM, nur lesen | gemessen durch Bytevergleich mit der Sample-Datei, was ein Schreiben bewirkt ist nicht gemessen. Die Einheit von Start, Loop und Ende und die Skala von Tune sind offen |

"Alles" heißt: alles, was entschlüsselt ist. Unbekanntes gibt es im Expertenmodus.

### Zwei Kopien der Modulationstabelle

Das Firmware-Abbild enthält die Tabelle der 72 Modulationsarten zweimal: bei Dateioffset `0xD82EC` (die
Kopie von Korg) und bei `0x1A00FC` (die Kopie, die Hacktribe anlegt). Die Einträge sind gleich, nur die
ersten vier Bytes des ersten unterscheiden sich. Welche Kopie die Firmware liest, ist gemessen
(`measure:2026-10-14/offene-fragen`, Abschnitt 9.1): bei Hacktribe die zweite, die erste nie. Bei Korgs
Firmware gibt es nur die erste.

`table.modType` zeigt auf die zweite Kopie, `table.modTypeStock` auf Korgs. Beschrieben wird immer die
Kopie, die gelesen wird, und welche das ist, entscheidet `src/modtable.mjs` am Abbild, nicht an einer
festen Adresse: die beiden Tabellenleser im Code laden die Adresse der Namen von Eintrag 0 aus Literalen,
und die Kopie, auf die diese Wörter zeigen, gilt. Zeigt nichts oder mehr als eine Kopie dorthin, wird
nichts gefunden und nichts geschrieben. Der Beleg ist `factory-check:mod-table-read-copy`.

### Der Eintrag einer Modulationsart

Das Fenster eines Eintrags in der Karte beginnt vier Byte vor dem Datensatz, den die Firmware liest (der Datensatz
beginnt beim Namen): die ersten vier Byte des Fensters sind das Ende des Datensatzes davor. Ab `+0x14` hat jedes Byte ein
Feld in der Karte, gemessen im Emulator ([Stufe 2](messungen/2026-10-15-modulation-stufe2.md)): die Wellenform, die
Geschwindigkeitsbereiche und sechs Slots mit je Quelle, Ziel, Stärke von und bis und einem Merker für die Tiefe. Das Byte
`+0x19` ("Ziel") liest die Firmware nie, die Ziele stehen je Slot. Die neuen Felder haben keinen Transportweg
(`transport: []`) und sind im Expertenmodus. Die Seite Modulationen bearbeitet die Slots 0 bis 4 (Quelle 0 Hüllkurve,
1 LFO, 2 aus; Ziel 0 bis 10; Stärke von und bis; Tiefe folgt) und die Kurve 0 bis 6 als Wellenform, das Byte "Ziel" zeigt
sie nur an. Der sechste Slot liegt halb im nächsten Fenster und bleibt unberührt, ebenso die Zwischenwerte und die
freien Bytes.

### Groove-Templates

Das Format hat bangcorrupt im
[hacktribe-editor](https://github.com/bangcorrupt/hacktribe-editor) entschlüsselt
(`extra/e2_groove_template.py`, AGPL-3.0). Es steht als Karteneintrag mit
`source: derived`, bis es am Gerät nachgeprüft ist.

| Offset | Inhalt |
|---|---|
| `+0x00` | Kennung `GVST` |
| `+0x10` | Name, 15 Zeichen |
| `+0x22` | Länge in Steps, neu angelegt 64 |
| `+0x30` | 64 Steps zu je 4 Byte: Versatz, Velocity, Gate, `0xFF` |
| letzte 4 Byte | Kennung `GVED` |

Ein Record ist `0x140` Byte, die Tabelle liegt bei `0xC0143B00`. Geschrieben wird
per RAM-Befehl, es gibt keinen eigenen Groove-Befehl. Nach dem Beispielskript
dort ist ein Versatz von 48 ein halber Step, ein Step hat also 96 Einheiten, und
Gate 96 heißt gebunden.

Offen, bevor es in Klartext editierbar wird:

- 96 oder 128 Plätze? hacktribe-editor lässt nur die Plätze 0 bis 95 zu, bis das
  geklärt ist, gilt die kleinere Zahl.
- Ob Velocity absolut oder relativ ist. Neu angelegt steht sie auf 96, das Beispiel
  ändert sie um -32. Das spricht für einen Ruhewert in der Mitte, ist aber nicht
  gemessen.
- Ob der Versatz vorzeichenbehaftet ist.
- hacktribe-editor hat beim Groove-Lesen dieselbe Kanalfalle wie Hacktribe: die
  Funktion nimmt einen Kanal entgegen und schickt fest Kanal 0 weiter. Dieser
  Code nimmt den Kanal aus der Gerätesuche.

## Expertenmodus

Unbekannte Felder sind hinter einem Schalter als Zahl bearbeitbar. Dafür gelten
eigene Regeln:

1. Jedes unbekannte Feld ist markiert, mit dem Hinweis, dass seine Wirkung
   niemand kennt.
2. Der Probelauf läuft trotzdem. Er prüft bei unbekannten Feldern nur, ob der
   Befehl ankommt, nicht was er bewirkt.
3. Änderungen an unbekannten Feldern gehen zuerst den flüchtigsten Weg: für
   Felder in der Firmware nur live ins RAM, für Felder im Pattern nur in den
   Pattern-Puffer des Geräts. Den dauerhaften Weg gibt es nur mit einer zweiten,
   ausdrücklichen Bestätigung.
4. Unbekannte Modulationsfelder gehen nie in die Firmware, solange offen ist, ob
   die Modulationstabelle im RAM live wirkt.
5. Aus einem bestätigten Fund wird ein Karteneintrag mit `source: measured`.

## Eingaben prüfen

Alles, was von außen kommt, wird geprüft, bevor der Editor es anzeigt.

- **Firmware-Datei:** erst Größe, dann Fingerabdruck, dann lesen. Eine zu kurze
  Datei bekommt eine klare Meldung. Der Fingerabdruck erkennt auch eine Datei, die
  dieser Editor schon verändert hat, damit sie nicht als "Original" gilt.
- **Backup-Datei:** Kennung, Größe und die Rahmen jedes Patterns, bevor etwas
  angezeigt wird.
- **Antworten vom Gerät:** Länge und Kopf jeder Antwort werden geprüft, bevor sie
  dekodiert wird. Clock und Active Sensing auf derselben Leitung werden
  herausgefiltert.

## Zwei Fallen

**Die 7-Bit-Kodierung verliert einen Block.** Die Referenzimplementierung in
Hacktribe verliert den letzten Block, wenn die Eingabelänge bei Division durch
sieben den Rest sechs lässt. 524, die Größe eines Preset-Records, ist so eine
Länge. Es fiel nie auf, weil Schreibzugriffe in zwei Hälften zu 256 und 268
gehen, die beide glatt teilen. `src/bytes.mjs` macht es richtig,
`test/bytes.test.mjs` hält das fest.

**Records werden bearbeitet, nie gebaut.** Auf jedes Gerätebyte folgen fünf Bytes,
und 23 von 28 Bytes eines Map-Eintrags bedeuten uns nichts. Ein Record aus Nullen
wird am Gerät gewählt und bleibt stumm. `FxRecord` umhüllt nur bestehende Bytes,
und `adoptStage` weigert sich, einen Stufenblock zwischen Stufe 1 und Stufe 2 zu
verschieben, weil das von Hand genau so ein stummes Preset ergab.
