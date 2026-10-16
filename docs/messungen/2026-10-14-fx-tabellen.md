# FX-Tabellen: Parameterspannen und Wahlnamen aus dem DSP-Strom

Stand 2026-10-14. Offline, Firmware 2.02 (Hacktribe und Korgs Stock-VSB aus dem Systemupdate 2.02),
dazu der Emulator für die Filterfrage. Kein Gerät. Markierungen: **gemessen** (ausgeführt, Befehl
genannt), **hergeleitet** (aus Code oder Daten geschlossen), **offen**. Die Messskripte liegen nicht
im Repository; dort liegen nur `tools/fx-tables.py` und das, was es schreibt (Zahlen, keine Namen,
keine Firmwarebytes).

Vorgeschichte: [2026-10-14-fx-einheiten.md](2026-10-14-fx-einheiten.md) fand null Lesezugriffe auf
`0xC011F000` bis `0xC0124000` und schloss, die CPU-Seite benutze die Namenstabellen nicht. Das stimmt, und hier
steht der Grund.

## Kurzfassung

1. **Die Tabellen sind DSP-Daten.** Der Bereich liegt im DSP-Strom (`0xC00F9E10` bis `0xC013C0B0`), den der ARM
   nur am Stück zum Blackfin hochlädt. Er gehört zu den Effekt-Deskriptoren des DSP, nicht zur Oberfläche. Der
   ARM verweist nur auf den Anfang des Stroms (ein Literal bei `0xC0011AB4`).
2. **Aufbau entschlüsselt.** 66 Deskriptoren, je Einheit eine Parameterliste mit Name, Vorgabe, Minimum und
   Maximum. Die Einheitennummer des ARM ist der Index. 521 Parameter in 44 Einheiten, die Vorgaben stimmen mit
   `data/units.json` überein (517 von 519 verglichenen).
3. **Wertebereiche sind drin, Einheiten fast nicht.** Spannen (zum Beispiel Gain -36 bis 36, Dry/Wet 0 bis
   100, Threshold -60 bis 0) ja; dB, Hz und ms stehen nirgends. Die einzigen Einheiten im Strom sind zwei
   Beschriftungstabellen: Zeitverhältnis in Prozent (0.5% bis 400.0%, 128 Werte) und der Looper-Schritt (-16 bis 16).
4. **Wahlnamen und Beschriftungen für 26 Felder.** Die DSP-eigenen Textfunktionen kopieren Namen wie "LR Mix",
   "2stage", "SAWPLUS" oder holen "33.3%" aus einer Zeigerliste. Daraus stehen jetzt 26 Felder in der Karte, mit
   Adresse der Funktion als Beleg.
5. **Nicht aus Hacktribe.** Der DSP-Strom ist in Stock und Hacktribe byte-gleich.
6. **FX-Preset-Editing bei Hacktribe ist Editor und SysEx/NRPN**, kein Menü am Gerät (soweit lesbar, Wikiseite
   selbst nicht ladbar).
7. **Korgs Parameter Guide**: zuerst nicht geprüft (Lizenzbestätigung), später gelesen: er hat keine
   Parameterdaten für Effekte, nur Typlisten (Abschnitt 7).
8. **Filter:** Stock bietet nur electribe LPF, HPF, BPF, Hacktribe alle Familien. Die Daten sind gleich, die
   Oberfläche nicht. Die frühere Annahme in [dsp-erster-blick.md](../hintergrund/dsp-erster-blick.md) ist dort
   korrigiert.

## Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| Der Bereich `0xC011F000` bis `0xC0124000` liegt im DSP-Strom, der Anfang von `0xC011F000` ist DSP-Adresse `0x1F004CC` | gemessen | Strom bei Datei `0xF9F10`, `0x422A0` Byte; Block `0x1F00438`, `0x20DC` Byte; `dsp_extract.vsb_offset` auf beide Grenzen |
| Kein ARM-Wort zeigt in den Strom außer dem Anfang | gemessen | Wortsuche über das ARM-Abbild: vier Treffer, `0xC0011AB4` = `0xC00F9E10` (Upload), drei Wörter mitten in Thumb-2-Code bei `0xC00C9BD4`, `0xC00CBD54`, `0xC00CDF3C` (Befehlsbytes, kein Zeiger) |
| Strom und Bereich in Stock und Hacktribe gleich | gemessen | md5 `5c3923ba...` des Stroms, md5 `674f871b...` von `0xC011F000` bis `0xC0124000`, `cmp` der SDRAM-Abbilder beider Extraktionen |
| 66 Deskriptoren bei DSP `0x4C30`, je `0x34` Byte: Name `+0`, Anzahl `+4`, Liste `+0x14` | gemessen | `desc.py` über das extrahierte SDRAM-Abbild; Namen "[I] ...", "[M] ...", 44 Einheiten mit Parametern |
| Parameterrecord 20 Byte: Name, Vorgabe `+5`, Min `+6`, Max `+8` und `+10` (gleich) | gemessen | 521 Records, `max == max2` überall; Namen und Vorgaben gegen `units.json` |
| Einheitennummer des ARM = Deskriptorindex | gemessen | alle Einheiten aus `units.json`, die der DSP mit Parametern hat: Anzahl und Vorgaben gleich bis auf Cheap Comp und die Mute-Einheit (`tools/fx-tables.py` meldet sie auf stderr) |
| Gespeichertes Byte = angezeigter Wert minus Minimum | hergeleitet | 0 von 521 Vorgaben über `max - min`; 31 Vorgaben liegen außerhalb von `[min, max]`, die direkte Lesart wäre unmöglich (Beispiel EQ-Gain, Vorgabe 36 in -36 bis 36) |
| 861 von 862 Werksparametern mit Spanne liegen in `[0, Spanne]`, einer nicht | gemessen | `factory-check:fx-param-ranges`: Tape Echo (MFX 21 "Tap Delay Sync"), Spread 127 über 100 |
| Einheiten (dB, Hz, ms, %) stehen nicht in den Tabellen | hergeleitet | 1264 Zeichenketten des Pools gelesen, keine Zeichenkette mit dB, Hz, kHz, ms oder Cent; Einheiten nur in den Zeigerlisten `0x1F0D368` (Prozent) und `0x1C7C230` (Looper-Schritt) |
| 26 Felder tragen Namen oder Beschriftung ihrer Textfunktion | gemessen | `jt.py` (Sprungtabellen), `fdis.py` (Funktionen), `ptrtabs.py` (Zeigerlisten), `factory-check:fx-filter-output` für die Filterausgabe; die Vorgabe des Zeitverhältnisses (Byte 65) steht auf "100.0%" |
| Hacktribe-FX-Editing ist SysEx und NRPN | hergeleitet | `ht_fx_midi.py` (get/set IFX und MFX, Edit-Buffer per SysEx; `set_param` per NRPN), `ht_nrpn_format.py` (Wert `Int8ul`, keine Spanne) |
| Stock zeigt nur electribe-Filter, Hacktribe alle | gemessen | siehe Korrektur in [dsp-erster-blick.md](../hintergrund/dsp-erster-blick.md), 20 Emulatorläufe |

## 1. Die Tabellen

### 1.1 Wo sie liegen und warum der ARM sie nicht liest

Der DSP-Strom besteht aus Boot-Blöcken (16 Byte Kopf, XOR 0). Im ARM-Abbild liegen die Köpfe zwischen den
Daten, deshalb ist ein Datenbereich dort nicht zusammenhängend: dieselben Zeichenketten stehen in der VSB
ab `0xC011EF70` (DSP `0x1F0043C`) bis `0xC0123F28` (DSP `0x1F05520`), mit Kopf-Einschüben dazwischen.

| Was | DSP-Adresse | ARM-Abbild (Anfangsbyte) |
|---|---|---|
| 66 Deskriptor-Zeiger | `0x4C30` | `0xC00FED74` |
| Deskriptor "[I] NoFx(Thru)" | `0x42D8` | |
| Einheitennamen "[I/Dbl] ...", "[M] ..." | `0x1F00A14` ff. | `0xC011F548` |
| Parameterlisten (Beispiel 2 Band EQ) | `0x1C7DCC0` | `0xC011B164` |
| Parameterrecords, Namen mit Zeilenmarken | `0x1F00514` bis `0x1F04E34` | in `0xC011EF70` bis `0xC0123F28` |

Der Strom wird einmal hochgeladen (`0xC0011AB8`, Literal `0xC0011AB4`). Danach liegen die Tabellen im SDRAM des
Blackfin, und nur dessen Code liest sie. Aus der Hostschnittstelle kommen sie nie zurück: der ARM schickt
Befehle und Rohwerte und liest nur Zustände. Das erklärt die null Lesezugriffe der früheren Messung.

### 1.2 Struktur

```
Zeiger-Tabelle bei 0x4C30:  66 Zeiger auf Deskriptoren (Index = Einheitennummer des ARM)
Deskriptor (0x34 Byte):     +0 Name, +4 Parameterzahl, +5/+6 Speicherflags, +8 Flags (0x10000 = Master),
                            +0x14 Zeiger auf Liste von Zeigern, +0x18 Prozessfunktion, +0x1C, +0x20 Init
Parameterrecord (20 Byte):  +0 Name (Zeilenmarke, dann Name), +5 Vorgabe, +6 Min (s16), +8 Max (s16),
                            +10 Max, +12 Funktion (Wert ändern), +16 Funktion (Text, oder nur ein RTS)
```

Die Zeilenmarken vor dem Namen sind zwei Zeichen: `"  "`, `". "`, `"./"`, `" /"`. Ich lese sie als Gruppierung
der Regler auf Seiten (`./` allein in einer Gruppe), nicht als Teil des Namens. Hergeleitet, nicht gebraucht.

Daneben liegt in den Pools eine zweite, ältere Tabellenart: Records zu 24 Byte mit langem und kurzem Namen
("Dry:Wet" und "DRY:WET", "SyncNote" und "S.NOTE") und eigenen Spannen, dazu Namen von Einheiten, die keinen
Deskriptor mehr haben (Amp-Simulation: "AmpType", "CabType", "Presence"; die Nummern 11 bis 14 sind
Platzhalter). Wer sie benutzt, ist nicht verfolgt (**offen**): kein Zeigerwort führt auf sie, vermutlich laden
sie Befehle des DSP über Direktwerte. Für die Karte werden sie nicht gebraucht.

### 1.3 Zu `units.json` und Hacktribe

Von 519 verglichenen Parametern stimmen die Vorgaben bei 517 (**gemessen**, `analyze.py`). Die Namen stimmen
bis auf Schreibweisen (24 Abweichungen wie `frequency` zu "Fc", `bit_depth` zu "Bit"). Die Tabelle von
hacktribe-editor stammt also aus diesem Strom oder einem gleichen; die DSP-Tabelle selbst ist nicht von Hacktribe
(Strom identisch zu Stock).

Zwei Abweichungen, beide in `units.json`:

- **`I_cheap_comp`**: units.json hat 4 Parameter, der DSP 6 (HPF b1, Peak Hold b1, Env LPF a0, Envelope Bit Shift
  Amount, Sens, Output Level). Auch die Stellen von `env_bit_shift_amount` (2 statt 3) und `output_level`
  (3 statt 5) weichen ab. Ob der ARM-Datensatz dem einen oder dem anderen folgt, ist **offen**; ein
  Werkspreset mit dieser Einheit würde es entscheiden. Die Karte lässt diese Einheit deshalb ohne Spannen.
- **`nofx_mute`** (`0x27`): units.json hat 11 Parameter, der DSP einen ("Fader").

## 2. Spannen

`tools/fx-tables.py SYSTEM.VSB > data/map/fx-ranges.mjs` schreibt je Einheit und Parameterstelle `[min, max]`
(41 Einheiten). Es verlangt, dass Anzahl und Vorgaben mit `units.json` übereinstimmen, sonst wird die Einheit
übersprungen (stderr nennt sie).

Lesart (**hergeleitet**): das gespeicherte Byte ist der angezeigte Wert minus `min`. Die Vorgabe liegt in allen
521 Fällen in `[0, max - min]`, in 31 nicht in `[min, max]`; die Werksparameter bestätigen die Obergrenze (861
von 862 mit Spanne, `factory-check:fx-param-ranges`). Beispiele: EQ-Gain -36 bis 36 (Byte 0 bis 72, Vorgabe 36
ist 0), Threshold -60 bis 0, Dry/Wet 0 bis 100, EQ-Frequenz 0 bis 58 (59 Stufen), Q 0 bis 95.

Was die Karte daraus macht (`tools/units-to-map.mjs`): `range: [0, max - min]`, bei negativem `min` dazu ein
Wandler `fxShiftN` (zeigt Byte minus N, "+12", "0", "-5"), bei Wahlfeldern die Obergrenze für das Eingabefeld.
Nicht angefasst: Spanne 0 bis 0 (28 Parameter, alle mit Vorgabe 0: der Eintrag erklärt keine Spanne) und die
Bit-Tiefe des Decimators (Minimum 4: ob Byte oder Wert, geben Tabelle und Werkspresets nicht her, beides passt).

**Einheiten gibt es kaum.** Ob -36 bis 36 Halbdezibel oder Dezibel sind, ob 0 bis 58 eine 1/6-Oktav-Reihe ist,
steht nirgends im Strom. Wer es wissen will, liest die Koeffizientenfunktionen (`c`-Zeiger der Records), das
ist die Rechnung aus [dsp-erster-blick.md](../hintergrund/dsp-erster-blick.md) Abschnitt 2.2, oder misst am Gerät. Die Seite zeigt deshalb
Zahlen ohne Einheit. Ausnahmen sind die zwei Beschriftungstabellen in Abschnitt 3.

## 3. Wahlnamen und Beschriftungen

Jeder Parameterrecord hat eine Textfunktion (`+16`). Bei 48 Parametern ist sie mehr als ein `RTS`, bei den
Wahlfeldern kopiert sie den Namen zum Wert in einen Puffer: aus einem Zweig `Wert == 0`, `Wert == 1` oder über
eine Sprungtabelle, Zeichen für Zeichen aus einer Kette bei `0x1F0xxxx`. Die Reihenfolge ist die des Codes.

Umgesetzt (alle mit `choiceEvidence` auf die Textfunktion, Adresse im ARM-Abbild):

| Feld | Namen (Byte 0, 1, ...) | Einheiten |
|---|---|---|
| Output Sel (Filter) | LPF4, LPF3, LPF2, BPF, HPF | `0x0A` |
| Envelope Select | LR Mix, LR Indv | `0x01`, `0x02`, `0x05`, `0x28`, `0x29`, `0x2A` |
| Mask Type | Simple, Absolute | `0x09`, `0x3E` |
| Phaser Type, Phase, Mod Wave | 2stage, 4stage / +, - / LFO Tri+, LFO Sin+ | `0x13`, `0x33` |
| Mod.Delay Mod Wave, FB Type | LFO Tri+, LFO Sin+ / Stereo, Cross | `0x3B` |
| Looper Type | Looper, RevLooper, TriggerLooper | `0x3F` |
| Level Mod Type | mpy, add | `0x15`, `0x35` |
| Level Mod Source, Mod Source (MMF) | SAW, TRI, SIN, SQU, EXP, LOG, LOGH, ---, SAWPLUS ... LOGHPLUS, ------- (16) | `0x15`, `0x35`, `0x2D` |

Gegen die Werkspresets geprüft ist nur der erste Eintrag: die Presets "Low Pass Filter", "LP Drive" halten 2
(LPF2), "Band Plus Filter", "BP Drive" 3 (BPF), "High Pass Filter", "HP Drive" 4 (HPF), und zwar alle neun
(`factory-check:fx-filter-output`). Die übrigen Listen stehen auf dem Code allein. Die Namen "---" und
"-------" in der Quellenliste lese ich als "keine Quelle", ohne Beleg.

**Zwei Textfunktionen holen die Beschriftung aus einer Zeigerliste statt aus Zweigen** (`ptrtabs.py` fand alle
Zeigerlisten mit mindestens acht aufeinanderfolgenden Zeigern auf Zeichenketten des Pools: genau drei, zwei davon Kopien):

| Feld | Werte | Beschriftung | Einheiten |
|---|---|---|---|
| `off_time_ratio` (Delay-Zeit als Anteil, "[off]Time Ratio") | 0 bis 127 | "0.5%", "1.0%" ... "100.0%" (Byte 61 bis 65, fünfmal) ... "400.0%" | Short Delay `0x18` (Liste `0xC012C04C`), Mod.Delay `0x3B` (Liste `0xC012B93C`, gleicher Inhalt, geprüft) |
| `step` (Looper) | 0 bis 18 | -16, -8, -4, -2, -1.5, -1.0, -0.5, -0.25, -0.125, 0.0, 0.125, 0.25, 0.5, 1.0, 1.5, 2.0, 4.0, 8.0, 16.0 | KPQ Looper `0x3F` (Liste `0xC01196E0`) |

Die Prozente heißen im Strom nur "%". Dass sie ein Verhältnis zur Delay-Zeit des Tempos meinen, ist hergeleitet
aus dem Parameternamen; die Vorgabe 65 des Short Delay (100.0%) passt dazu. Der Looper-Schritt trägt im Strom
keine Einheit, die Zahlen sehen nach Faktoren aus; die Karte nennt keine.

Nicht umgesetzt (**offen**): rund 20 weitere Textfunktionen, darunter Flanger/Chorus-Wellenform (`0x3728`,
`0x10062`) und Decimator "Bit". Die Namen von Wahlfeldern, die schlicht fehlen, bleiben Zahlen.

## 4. Hacktribe: "FX Preset Editing"

- **Wiki.** Die Seite `hacktribe/wiki/FX-Preset-Editing` besteht aus einem Satz mit Verweis auf die Wiki von
  hacktribe-editor (Zweig `ht-cli`). Diese Seite ließ sich nicht laden (404 oder Fehlerseite), ihr Inhalt ist
  **offen**. Die Hacktribe-Startseite führt "FX preset editing", "New MFX", "More IFX" und "Import/Export FX"
  nur als Stichworte.
- **Quelle.** `ht_fx_midi.py` (hacktribe-editor, `main`): IFX und MFX lesen und schreiben, `get_edit_buffer`
  und `add_ifx` per SysEx, einzelne Parameter (`set_param`) und Steuerzeilen (`map_param`, `edit_map`) per
  NRPN. Der Wert ist ein Byte (`Int8ul`, Kommentar: gültige Werte noch zu bestimmen), keine Spanne, keine
  Einheit. Ein Menü am Gerät kommt in diesem Code nicht vor. **Hergeleitet:** FX-Preset-Editing geht über den
  Editor und SysEx/NRPN, nicht über die Tasten.
- **Emulator.** Nichts zu erreichen, wo kein Menü ist. Was die Oberfläche am Gerät von FX-Werten zeigt, steht in
  `2026-10-14-fx-einheiten.md`: IFX EDIT zeigt eine Zahl von 0 bis 127 und keinen Namen.

## 5. Korgs Parameter Guide

Der Parameter Guide zum electribe sampler ist als `electribe_sampler_PG_E3.pdf` verlinkt (Datei "PG_E3",
Stand 2016.07.21, 815,8 KB) auf
`https://www.korg.com/us/support/download/manual/0/368/3174/`. Der Download verlangt die Bestätigung der
Lizenzvereinbarung. Sie wurde zunächst nicht bestätigt, die Datei nicht geholt und nicht gelesen. Gelesen wurde
sie später, siehe Abschnitt 7.

Aus dem Paket `electribe-fx-modding` (eine frühere eigene Arbeit des Autors) stammt der Hinweis, dass Korgs
Workstation-Handbücher (M3 Parameter Guide, R3 Effect Guide) dieselben Effekte mit Wertebereich beschreiben, zum
Beispiel "High Damp [000...100%]" für den Decimator. Das ist ein Wegweiser, kein Beleg für den Sampler-Guide.
Mit der PDF ließe sich jede Spanne dieser Tabellen gegen die Angaben prüfen und Einheiten als
`korg-spec:<Abschnitt>` nachtragen.

## 6. Filter

Siehe die Korrektur in [dsp-erster-blick.md](../hintergrund/dsp-erster-blick.md). Kurz: Stock und Hacktribe
tragen dieselben Filterdaten, aber nur Hacktribe bietet in der Oberfläche alle Typen an (gemessen im Emulator).
Die 16 Namen stehen in beiden VSBs bei `0xC00A6D4F` (Zeigerliste `0xC00785C0`), in der Reihenfolge der Typen 1 bis
16: electribe, MS20, MG, P5, OB, Acid für LPF; electribe, MS20, P5, OB, Acid für HPF; electribe, MS20, P5, OB,
Acid für BPF. Hacktribe zeigt im Emulator auf der LPF-Taste Typ 2 bis 6 in dieser Reihenfolge. Der
Wandler `filterType` in `src/map/convert.mjs` benennt bisher nur 0, 1, 7 und 12; die übrigen als
"Hacktribe-Filter N". Mit diesen Namen ließe er sich vervollständigen, das ist noch nicht gemacht.

## 7. Parameter Guide gelesen: keine Parameterdaten für Effekte

Die PDF (`electribe_sampler_PG_E3.pdf`, 20 Seiten, Stand 2016.07.21) wurde danach geholt und gelesen.
Abschnitt 5 ist damit erledigt. Kurzfassung: **der Guide nennt für Effekte keine einzige
Einheit und keine Spanne pro Parameter.** Es gibt keine Parameterliste für Insert- oder Master-Effekte, die man
der Karte zuordnen könnte. Deshalb kamen weder Einheiten noch neue Wahlnamen in die Karte, und die Presets-Seite
blieb unverändert: eine Einheit ohne Beleg wäre geraten (Threshold -60 bis 0
sieht nach dB aus, ist aber nur eine Vermutung).

Was der Guide zu Effekten enthält (alles **gemessen**, Seite = PDF-Seite = gedruckte Seite):

| Angabe | Seite | Inhalt |
|---|---|---|
| `MFX TYPE` | 3 | Bereich 01 bis 32, Verweis auf die Typliste |
| MFX-Typliste | 17 | 32 Namen mit Nummer; Seq Reverse, Seq Doubler, Odd Stepper, Even Stepper ohne Motion Sequence |
| IFX-Typliste | 17 | 38 Namen mit Nummer (26 links, 27 bis 38 in der rechten Spalte) |
| Modulationsziel "IFX Edit" | 15, 16 | nur der Name des Ziels, kein Wertebereich |

Die Namen in den Typlisten sind die Namen der Werkspresets, nicht die von Parametern. Die einzigen Zahlen mit
Einheit im ganzen Guide (BPM 20.0 bis 300.0, Swing -50% bis +50%, Play Level Normal oder +12 dB, Sample Tune
-63 bis +63) gehören zu Pattern, Part und Sample, nicht zu Effekten. "Delay Time" kommt nur als Beispiel für
tempo-synchrone Einstellungen bei der externen Clock vor (Seite 7), ohne Notenwerte oder Bereich.

**Abweichungen zwischen Guide und VSB** (Preset-Namen in der eigenen `SYSTEM.VSB`, gelesen mit `VsbImage.list`):

| Preset | Guide | VSB | Lesart |
|---|---|---|---|
| IFX 1 bis 38 | 38 Namen | alle 38 gleich (Namen in der VSB auf 15 Zeichen gekürzt) | passt |
| IFX 39 bis 59 | nicht im Guide | 21 weitere Presets (Lag, KP2 Comp, die Drive-Filter, die Delays 9/32, 3/32, 1/12 und so weiter) | Hacktribe, ohne Guide-Beleg |
| MFX 1 bis 32 | 32 Namen | 29 gleich | |
| MFX 11 | Jag Filter | Plate Reverb | abweichend |
| MFX 21 | Touch Wah | Tap Delay Sync | abweichend |
| MFX 32 | Auto Pan | Tube Drive | abweichend |
| MFX 33 bis 35 | nicht im Guide | Jag Filter, Touch Wah, Auto Pan | die drei verdrängten Typen stehen hinten |
| MFX 36 bis 50 | nicht im Guide | 15 weitere Presets | Hacktribe, ohne Guide-Beleg |

Hergeleitet: Hacktribe tauscht drei Master-Presets gegen eigene und hängt die drei Originale an Nummer 33 bis
35 an. Der Editor hält sich an die VSB, nicht an den Guide; die Nummern der Typliste gelten für Presets, nicht
für Bausteine (`unit`), und die Karte ist nach Bausteinen gebaut.

**Spannen und Vorgaben gegen die DSP-Tabellen:** nicht prüfbar, der Guide hat auf der Parameterebene nichts, das
man gegen `fx-ranges.mjs` halten könnte. Es gibt deshalb auch keine Abweichung zu melden. Die Unsicherheiten aus
Abschnitt 2 gelten unverändert: Einheit von -36 bis 36 (Dezibel oder Halbdezibel), Schrittweite der 59 Stufen
der EQ-Frequenz, Bit-Tiefe des Decimators.

Wo Einheiten herkommen könnten (nicht geprüft, nur Wegweiser):

- Korgs Parameter Guide zur electribe-2-Familie oder ein eigener Effekt-Guide, falls es einen gibt. Der Guide PG_E3 ist
  es nicht.
- Die Koeffizientenfunktionen im DSP (Abschnitt 2): sie rechnen mit den Bytes, aus der Formel lässt sich die
  Einheit herleiten, etwa Gain als dB über `10^(x/20)`. Das wäre `derived:` und nicht `korg-spec:`.
- Eine Messung am Gerät oder im Emulator, mit dem Spektrum eines Testsignals.
- Die Workstation-Handbücher (M3, R3), die dieselben Effekte mit Bereich beschreiben (Abschnitt 5): ob die
  Parameter des Samplers gleich laufen, wäre erst zu zeigen.

## Was im Repository neu ist

- `tools/fx-tables.py`, `data/map/fx-ranges.mjs` (Zahlen, nicht die Namen).
- `tools/units-to-map.mjs` übernimmt Spannen und Wahlwandler in `data/map/fx-params.mjs` (449 von 539 Feldern
  tragen jetzt eine Spanne, 89 den Wandler `fxShiftN`, 26 eine Wahlliste oder Beschriftung).
- `src/map/convert.mjs`: `fxShiftN` und die Wahlwandler. `site/app/fx.mjs`: Eingabefeld folgt der Spanne.
- Tests: Beleg und Form der Spannen (`test/map.test.mjs`), `fxShift36` (`test/convert.test.mjs`),
  `factory-check:fx-param-ranges` und `fx-filter-output` (`test/factory-checks.mjs`, mit `npm run test:local`).
- Im Browser geprüft: Presets-Seite mit der eigenen VSB, Preset "Low Pass Filter" zeigt die fünf
  Ausgänge, "Phaser" die Wahlfelder, "Low EQ" Gain 0 (Byte 36) mit Schieber 0 bis 72.

## Nächste Schritte

1. Einheiten aus einer anderen Quelle holen: der Parameter Guide gibt sie nicht her (Abschnitt 7).
2. `I_cheap_comp` klären (4 oder 6 Parameter) mit einem Werkspreset oder einem Gerätetest.
3. Weitere Textfunktionen verfolgen (Decimator-Bit, Flanger/Chorus-Wellenform), dann die Wahlwandler ergänzen.
4. `filterType` mit allen 16 Namen versehen.
