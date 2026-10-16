# Synth-Filter auf Korgs Original: der Patch, im Emulator geprüft

Stand 2026-10-15. Kein Gerätezugriff, alles im Emulator (Korgs Original 2.02 und Firmware 2.02 mit Hacktribe, eigene `SYSTEM.VSB`-Dateien, eigener Flash-Dump), am Gerät ist nichts bestätigt.
Setzt die [Korrektur zu den Filtertypen](../hintergrund/dsp-erster-blick.md) um: Korgs Oberfläche bietet nur OFF und die drei electribe-Filter an, obwohl alle 16 Typen mit Namen, Tabellen und
DSP-Code in der Firmware stehen. Die Prüfungen sind `tools/emu/synth_filter_cases.py` (läuft in `tools/emu/check.py` mit, Namen in Klammern), der Patch ist `data/patches/synth-filters.json`,
gebaut von `tools/patch/synth_filters.py`. Marker: **gemessen**, **hergeleitet**, **offen** (am Gerät zu prüfen).

## Was der Patch tut

Auf Korgs Build (der Patch ist nur dafür, `builds: ["stock"]`; in Hacktribes Build ist das Verhalten schon da, ein Satz überspringt den Patch dort wegen `notNeededOn`):

| Eingabe | Wirkung |
|---|---|
| LPF (Taste `0x12`) | läuft durch die LPF-Familie: electribe, MS20, MG, P5, OB, Acid, dann OFF, dann wieder electribe |
| HPF (Taste `0x14`) | electribe, MS20, P5, OB, Acid, OFF |
| BPF (Taste `0x16`) | electribe, MS20, P5, OB, Acid, OFF |
| Taste einer anderen Familie, als der Part gerade hat | der Typ derselben Bauart (7 auf LPF gibt 1, 8 gibt 2, 9 gibt 4, 10 gibt 5, 11 gibt 6; MG hat weder HPF noch BPF, dort kommt der electribe-Filter) |
| Pattern mit Synth-Typ wählen | der Part behält den Typ (Korgs Setter faltet ihn sonst auf den electribe-Filter) |
| EXIT beim Einschalten | Korgs Firmware, wie sie ist (die Tasten und der Setter laufen mit den ursprünglichen Befehlen) |

Es gibt keinen Menüpunkt und keinen Merker dafür. Namen und Lampen kommen von der Firmware selbst: die Anzeige schlägt den Namen des Typs in ihrer Namensliste nach
(`0xC00785C0`, Zeiger auf die Namen der Typen 1 bis 16), die Lampe der Taste (LED `0x0C`, `0x0D`, `0x0E`) brennt für die ganze Familie.

## Wo die Auswahl sitzt (gemessen, Emulator)

Der Weg einer Filtertaste in Korgs Build, mit einem Schreib-Hook auf das Part-Byte und einer Spur der ausgeführten Blöcke:

- Taste `0x12`, `0x14`, `0x16` kommt in `0xC006FC80` an (der Sprung bei `0xC00702C0` geht in Korgs Build dorthin, in Hacktribes Build auf neuen Code bei `0xC0150000`). Die Funktion holt den aktuellen Typ des Parts über den Getter `0xC0048E18` (nach `r5`, die Taste liegt in `r4`), wählt den neuen Typ und erzeugt mit `0xC007BFDC` ein Befehlsobjekt.
- **Die Auswahl** sind drei Sprungtabellen ab `0xC006FCE8`: sie kennen die Typen 0 bis 12 und geben nur 0, 1, 7 oder 12 zurück. LPF macht aus 0, 7, 12 den Typ 1 und aus 1 den Typ 0, HPF aus 0, 1, 12 den Typ 7 und aus 7 den Typ 0, BPF aus 0, 1, 7 den Typ 12 und aus 12 den Typ 0, alles andere ergibt 0.
- Das Befehlsobjekt wird über `0xC007C028` ausgeführt und ruft den **Setter** `0xC00495B8`. Der schreibt das Byte (`strb` bei `0xC0049618`, Objekt + `0x330` je Part + `0x810`, im gespeicherten Pattern liegt es bei `0x80C`) und meldet die Änderung (`0xC004B208`, Parameter 29, danach `0xC0030CF4` und `0xC003BA38`).
- **Der Setter faltet.** Vor dem Schreiben macht er aus den Typen 2 bis 6 die 1, aus 8 bis 11 die 7, aus 13 bis 16 die 12 (Bitmasken `0x1F`, `0x3C0`, `0x7800` über `Typ - 2`), aus allem über 16 die 1. Ein bedingter Sprung (`0xC00495DC`) überspringt das Falten für 0 und 1. Das war die offene Frage der Korrektur: **dieser Sprung ist der Schalter**, nicht die Taste allein. Ein Patch nur an der Taste hätte Typ 2 bis 16 zwar angezeigt, aber als electribe-Filter gespeichert.
- **Hergeleitet:** Hacktribe unterscheidet sich im Setter in genau diesem einen Sprung, er ist dort unbedingt (`0xC00495DF`, ein Byte), und leitet die Tastenfunktion über `0xC00702C0` auf eigenen Code um. Die DSP-Daten sind in beiden VSBs byte-gleich (Datei `0xF9F10` bis `0x13C1B0`, gemessen). Die übrigen etwa 130 geänderten Bytes unterhalb `0xC0099000` sind die FX-Tabellen und Zähler (Effektanzahlen `0x26` auf `0x3B`, Grenzen und Umleitungen), nicht die Filter.

## Die Reihenfolge von Hacktribe (gemessen)

Auf Hacktribes Build den Typ des Parts auf jeden Wert 0 bis 16 gesetzt, die Taste gedrückt, das Part-Byte gelesen. Die Tabelle ist im Patch (`types`, 3 mal 17 Byte, Zeilen LPF, HPF, BPF) und in den Prüfungen (`MEASURED`) dieselbe:

| aktuell | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LPF | 1 | 2 | 3 | 4 | 5 | 6 | 0 | 1 | 2 | 4 | 5 | 6 | 1 | 2 | 4 | 5 | 6 |
| HPF | 7 | 7 | 8 | 7 | 9 | 10 | 11 | 8 | 9 | 10 | 11 | 0 | 7 | 8 | 9 | 10 | 11 |
| BPF | 12 | 12 | 13 | 12 | 14 | 15 | 16 | 12 | 13 | 14 | 15 | 16 | 13 | 14 | 15 | 16 | 0 |

Typen: 1 electribe LPF, 2 MS20, 3 MG, 4 P5, 5 OB, 6 Acid (LPF); 7 electribe, 8 MS20, 9 P5, 10 OB, 11 Acid (HPF); 12 electribe, 13 MS20, 14 P5, 15 OB, 16 Acid (BPF), die Namen aus der Namensliste der Firmware.
Ein aktueller Typ über 16 ergibt auf jeder Taste 0 (gemessen mit 17, 18, 40 und 255; der Setter lässt so einen Wert nie stehen).

**Gewählt:** genau diese Reihenfolge, nicht eine eigene. Sie ist die von Hacktribe, damit ein Pattern, ein Handgriff und eine Anleitung auf beiden Builds dasselbe bedeuten. Sie hat eine Regel: in der eigenen Familie
der Reihe nach, nach dem letzten OFF, aus OFF der erste; aus einer anderen Familie der Typ derselben Bauart, MG ohne Gegenstück geht auf electribe. `next_type` in `tools/patch/synth_filters.py` ist diese Regel,
die Tabelle im Patch kommt daraus, die Prüfung `table` hält sie gegen die gemessenen Zahlen.

## Der Patch (zwei Stellen, eigener Code)

| Adresse | Was | Warum |
|---|---|---|
| `0xC006FCE8` | der Vergleich der Taste mit `0x14` wird ein Sprung in `select` (Code bei `0xC0190000`, 191 Byte mit der Tabelle) | `select` liest den neuen Typ aus der Tabelle (Zeile = Taste, Spalte = aktueller Typ) und kehrt bei `0xC006FDDC` zurück, wo die Firmware den Typ mit dem aktuellen vergleicht und ihr eigenes Befehlsobjekt baut |
| `0xC00495DC` | der bedingte Sprung über das Falten wird ein Sprung in `store` | `store` überspringt das Falten für jeden Typ |

Mit EXIT beim Einschalten (Bit 13 des Wortes bei Panelobjekt + `0x18`) führen beide Stellen die ursprünglichen Befehle aus: `select_original` den Vergleich und den Rücksprung hinter ihn, `store_fold` den Weg ins Falten.
Der Code liest nur das Panelobjekt und schreibt nichts außer `r0` bis `r4` (die Firmware setzt `r3` direkt dahinter neu). Kein RAM, nichts auf dem Flash oder der Karte, kein Menüpunkt. Der Patch trägt keine Bytes der Firmware.

**Startphase.** Der Setter läuft schon beim Start (die 16 Parts des ersten Patterns, etwa 310 ms nach dem Einschalten, lange nach den Rettungswegen bei 57 bis 60 ms), die Taste nicht. Der Patch nennt das Wort und seinen Code
in `startPhase`, dort schaut `store` nur ins Panelobjekt und auf die Kill-Taste. Der Platz `0xC0190000` bis `0xC0190100` ist in Korgs Abbild frei (FF) und liegt zwischen den Bereichen des Patternwechsels und
der Plugin-Laufzeit; Hacktribes Code bei `0xC0150000` und ab `0xC0170000` ist auf Korgs Build leer und wird nicht benutzt.

## Prüfungen (Fälle in `synth_filter_cases.py`, Korgs Build mit dem ganzen BLECH-Satz, eigener Flash)

- **Die Tasten** (`lpf_cycle`, `hpf_cycle`, `bpf_cycle`): aus dem electribe-Filter acht Mal LPF gibt 2, 3, 4, 5, 6, 0, 1, 2, HPF gibt 7 bis 11, 0, 7, 8, BPF gibt 12 bis 16, 0, 12, 13.
- **Die Tabelle** (`*_table`): von jedem aktuellen Typ 0 bis 16 und von 17, 40, 255 aus gibt jede Taste, was Hacktribes Tasten gaben, 60 Drücke ohne Abweichung.
- **Die Namen** (`*_names`): bei jedem Druck schlägt die Anzeige den Eintrag des angezeigten Typs in der Namensliste nach, und der Text dahinter ist der erwartete ("MS20 LPF", "MG   LPF", "P5 LPF", "OB LPF", "Acid LPF", "MS20 HPF" und so weiter).
- **Die Lampen** (`*_leds`): die Lampe der Taste brennt für die ganze Familie, bei OFF sind alle drei aus.
- **Die Meldung** (`*_message`): jeder Druck gibt genau eine Parameter-Meldung (Parameter 29) mit dem neuen Typ als Wert, wie bei Hacktribe.
- **Die Bilder** (`*_frames`, `electribe_frames_are_korgs`): jeder Typ hat ein eigenes Anzeigebild, dasselbe bei jedem Wiedersehen; die Bilder von OFF und der drei electribe-Filter sind die der Firmware mit EXIT beim Einschalten.
- **Pattern laden** (`load_keeps_type`, `load_leaves_slot`): ein Slot mit Typ 2 bis 6, 8 bis 11 oder 13 bis 16 an Part 1 wird gewählt, der Part hat den Typ, die Lampe der Familie brennt, der Slot ist unverändert; 17 und 40 werden zu 1 (wie bei Hacktribe).
- **Hin und zurück** (`roundtrip`): LPF zweimal (MG, Typ 3), WRITE, WRITE, MENU, der Slot hält 3; ein anderes Pattern wählen und zurück, der Part hat wieder 3 (das andere Pattern hat seinen eigenen Typ).
- **Gegen Hacktribe, lokal** (`*_equals_hacktribe`, nur mit `E2_HACKTRIBE_VSB`): dieselben 14 Drücke auf Hacktribes Datei geben Part-Byte, Lampen und Anzeigebild Druck für Druck gleich. Gemessen mit der eigenen Datei und einer Kopie von Korgs Build, die nur diesen Patch trägt (mit dem ganzen BLECH-Satz unterscheiden sich die Anzeigebilder wegen des Themes): gleich bei allen 14 Drücken je Taste. Beim Laden der Patterns stimmen Part-Byte, Lampen und die Parameter-Meldungen von Hacktribe und der Kopie ebenfalls überein (einmal gemessen, nicht Teil der Fälle).

### DSP

**Gemessen:** der DSP-Strom ist in beiden Builds byte-gleich, die Kerne und Tabellen sind also dieselben. Was der Emulator vom Typ an den DSP gibt, ist die Parameter-Meldung der Firmware (`0xC004B208`, Part, Parameter 29,
Wert = Typ), und sie ist bei jedem Typ auf beiden Builds gleich (Druck für Druck und beim Laden). Die Übertragungen über den Host-Port (`0x60000000`) zeigen beim Tastendruck, beim Pad und beim Abspielen in beiden Builds
nichts, was vom Typ abhängt: die DSP-Attrappe nimmt keine Stimmen an. **Offen:** ob die Klänge am Gerät so klingen wie bei Hacktribe. Dass der DSP-Strom gleich ist und das Part-Byte gleich ankommt, ist die Herleitung, kein Hörtest.

## Ohne den Patch (EXIT beim Einschalten, oder Korgs Firmware wie geliefert)

**Gemessen** (`kill_keys_are_korgs`, `kill_folds_synth_types`, `kill_write_loses_type`):

- Die Tasten kennen nur OFF und die electribe-Filter: LPF aus dem electribe-Filter gibt 0, 1, 0; HPF gibt 7, 0, 7; BPF gibt 12, 0, 12.
- Ein Pattern mit Synth-Typ an Part 1 wird beim Wählen **gefaltet**: 2 bis 6 werden 1, 8 bis 11 werden 7, 13 bis 16 werden 12, alles über 16 wird 1. Der Part spielt dann den electribe-Filter derselben Familie, die Lampe der Familie brennt, die Anzeige zeigt den electribe-Namen. Eine Warnung gibt es nicht.
- Der Slot im Speicher behält den Wert, bis das Pattern geschrieben wird. **WRITE speichert den gefalteten Typ**: der Synth-Typ ist dann im Slot weg, auch wenn man nichts verändert hat. Wer Patterns aus Hacktribe oder aus diesem Editor mit Synth-Filtern auf Korgs Original ungepatcht öffnet und schreibt, verliert den Typ.

## Entscheidungen

1. **Reihenfolge von Hacktribe**, nicht eine eigene (siehe oben): Muster, Anleitungen und Gewohnheit gelten auf beiden Builds.
2. **Der Setter ändert sich mit.** Eine Auswahl nur an der Taste reicht nicht, weil der Setter faltet. Beide Stellen laufen nur, wenn EXIT beim Einschalten nicht gehalten wurde.
3. **Kein Merker, kein Menüpunkt.** Der Patch ist an, wenn er in der Firmware ist, und aus mit EXIT beim Einschalten, wie die anderen Patches des Satzes. Eine Menüseite (wie TAP MOTION) wäre nachrüstbar, ist nicht verlangt.
4. **Nur Korgs Build** (`builds: ["stock"]`, `notNeededOn: ["hacktribe"]`). Hacktribes Build hat das. Die Samples und ihre Namen bleiben unberührt: die Oszillatornamen der Slots 19 bis etwa 260, die Hacktribe in die Werks-Sample-Namen schreibt, gehören nicht zu diesem Patch und kommen nicht mit.
5. **Platz `0xC0190000`** bis `0xC0190100`, ohne RAM.

## Offen

- Am Gerät: Klang der Synth-Filter bei Korgs Build, Tastenverhalten, die Lampen.
- Weitere Wege, den Filtertyp zu setzen (MIDI, SysEx, der Pattern-Import über die Karte) laufen über denselben Setter und sind darum von der Faltung mit betroffen; der Emulator-Test deckt den Pattern-Wechsel ab, die anderen sind nicht eigens geprüft.
- Anzeige des Filtertyps in den Menüs des Parts (falls es dort einen Eintrag gibt) nicht geprüft.
