# Preset-Tabellen: wo Korg sie ablegt, was Hacktribe verschiebt, wer sie liest

Stand 2026-10-15. Im Emulator und offline, kein Gerät. Eingaben: Korgs `SYSTEM.VSB` aus dem Systemupdate 2.02
(sha256 `1d0f0689...`), eine eigene, bearbeitete Hacktribe-Datei (`b0890899...`) und das eigene Flash-Abbild vom
2026-10-09 (`e177a321...`). Markierungen: **gemessen** (ausgeführt, Befehl genannt), **offline** (Code oder Daten
gelesen), **hergeleitet**, **offen**. Die Dateien liegen nicht im Repository, nur Ergebnisse, Adressen und Hashes.
Davor: [Korgs Original im Emulator](2026-10-14-stock-emulator.md), [BLECH auf Korgs Original](2026-10-14-stock-blech.md),
[FX-Tabellen im RAM](2026-09-14-fx-ram-write.md).

## Kurzfassung

1. **Beide Builds finden ein Preset über zwei winzige Funktionen.** Sie nehmen einen Zeiger aus einem Feld von
   100 Einträgen und kürzen den Index auf 99. Der Code der Funktionen ist in beiden Builds derselbe, nur die Adresse des
   Feldes in einem Literal dahinter ist verschieden. Alles andere (Menü, Pattern, Klangweg) geht durch diese beiden.
2. **Korg legt die Records verstreut ab, Hacktribe hintereinander.** Korgs Build hat 200 Records zu `0x20C` Byte in drei
   Läufen, dazwischen liegen die beiden Zeigerfelder, Insert und Master durcheinander. Hacktribe legt denselben Block
   (er endet bei beiden an `0xC00C1BE0`) neu aus: Zeigerfeld, 100 Insert-Records, Zeigerfeld, 100 Master-Records.
   Das ist die Form, die die Gerätekarte beschreibt. Hacktribe verschiebt also Felder und Records, nicht den Code der Getter.
3. **Der Grund für Hacktribes Umbau ist hergeleitet, nicht überliefert.** Hacktribes Patch ist ein bsdiff (`BSDIFF40`,
   17 KB) ohne Quelltext; was er tut, steht hier aus dem Vergleich der Dateien. Feste Schrittweite macht jedes Preset
   per Nummer adressierbar (Lesen und Schreiben über SysEx `0x52` bis `0x57`, der Editor); mehr Insert-Presets brauchen
   eine längere Menüliste (14 Stellen) und ein größeres Reglergedächtnis, das in Korgs Build an der Rückseite des
   Speichers hängt und nicht wachsen kann.
4. **Es gibt vier Dinge, die an der Zahl der Presets hängen, und einen Index, der bei 127 endet:** die Getter (Feld
   und Klemme 99), die Menülängen (Insert 14 Stellen, Master 1), das Reglergedächtnis des Insert-Effekts (16 Parts mal
   Menülänge Byte, 5 Literale) und der Index selbst, der in der Firmware 7 Bit breit ist.
5. **BLECH bekommt den Patch `preset-tables`.** Er lässt jeden Record, wo er ist, setzt neue Zeigerfelder mit 128 Einträgen,
   hebt die Klemme auf 127, verlegt das Reglergedächtnis auf 16 mal 128 Byte und lässt Platz für 28 weitere Records je
   Tabelle. In beiden Builds derselbe Patch, mit zwei Fassungen für die Prüfsummen. Mehr als 128 geht nicht, ohne das
   Format der Pattern zu ändern (siehe "Entscheidungen").
6. **Gemessen im Emulator:** die Werks-Presets kommen mit denselben Bytes zurück, die Menüs laufen bis zum Ende und
   springen zurück, ein hinzugefügter Platz schickt dem DSP dieselben Übertragungen wie sein Vorbild, in beiden Builds,
   mit den Tabellen voll bis 128.

## Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| Hacktribes Patch ist eine bsdiff-Datei ohne Skript, das die Tabellen beschreibt; Lizenz AGPL 3 | offline | Kopf `BSDIFF40`, Verzeichnis `scripts/` nur Werkzeuge für Patterns und Samples; `LICENSE` ist die GNU Affero GPL 3 |
| Der Insert-Getter liegt bei `0xC003E738`, der Master-Getter bei `0xC003E750`, beide lesen `array[min(i, 99)]` | offline, gemessen | Disassembly; `tools/emu/preset_probe.py` ruft sie mit 0, n-1, n, 99, 100, 127, 255 auf |
| Der Code beider Getter und alle ihre 14 Aufrufer sind in Korgs und Hacktribes Datei gleich, nur die Literale `0xC003E74C` und `0xC003E764` weichen ab | offline | Bytevergleich der Regionen, Aufrufer über alle `BL` des Abbilds gesucht |
| Korg: Zeigerfeld Insert `0xC00ADF94`, Master `0xC00AF390`, je 100 Einträge; Hacktribe: `0xC00A7F60` und `0xC00B4DA0` | offline, gemessen | Literale gelesen, Einträge im Emulator über die Getter zurückgegeben |
| Korgs 200 Records liegen in drei Läufen (47 Records ab `0xC00A7F60`, 9 ab `0xC00AE124`, 144 ab `0xC00AF520`), die Zeigerfelder dazwischen; kein Record ist doppelt benannt | offline | Zeiger beider Felder sortiert, 200 verschiedene Adressen |
| Korg benennt 38 Insert- und 32 Master-Presets, die übrigen Einträge zeigen auf unbenannte Records mit Vorgabebytes (keine Nullen) | offline | alle 100 Zeiger je Feld gelesen |
| Hacktribe legt denselben Block (`0xC00A7F60` bis `0xC00C1BE0`) neu aus: Feld, 100 Records, Feld, 100 Records | offline | wie oben, Läufe: 100 und 100 |
| Die 38 Insert-Presets in Korgs Datei sind Byte für Byte die Slots 1 bis 38 von Hacktribes Datei | offline | SHA-256 über jeden Record |
| Drei Master-Slots (11, 21, 32) unterscheiden sich zwischen Korgs Datei und der eigenen Hacktribe-Datei (Plate Reverb, Tap Delay Sync, Tube Drive an Stelle von Jag Filter, Touch Wah, Auto Pan) | offline | SHA-256; wer sie geändert hat, ist nicht zu trennen, siehe "Eigene Presets" |
| Das Reglergedächtnis des Insert-Effekts hat in Korgs Build 16 Zeilen zu 38 Byte bei `0xC0692278` (`0x260` Byte), das nächste Wort der Firmware liegt bei `0xC06924D8`, es kann nicht wachsen; Hacktribe hat es auf `0xC013C200` im Abbild verlegt | offline | 5 Literale (`0xC00980A8`, `0xC0098100`, `0xC0098144`, `0xC0098168`, `0xC00981B4`), Zeilenlänge `mov r2, #n` bei `0xC0098084` |
| Das Reglergedächtnis ist nach dem Start gleich gefüllt, wenn der Patch es verlegt hat | gemessen | `preset_cases.py`: `presets:knob_memory`, 608 Byte vor und nach dem Patch gleich |
| Ohne den Patch endet der INSERT-Regler bei der Menülänge und springt auf 0; der Master-Setter nimmt jeden Wert | gemessen | `preset_probe.py` auf Korgs und Hacktribes Datei, 41 Schritte, Master 0, 31, 32, 33, 99, 100, 127 |
| Mit dem Patch bleibt jeder Werks-Record, wo er war, und der Getter liefert für 100 bis 127 den Record von Eintrag 1, für 128 und mehr den von 127 | gemessen | `presets:*_factory_unchanged`, `presets:*_getter_to_127` auf beiden Builds |
| Mit den Tabellen voll (128 Einträge) läuft der INSERT-Regler alle Einträge durch, springt von 127 auf 0, und es gibt keine Assertion | gemessen | `presets:added_ifx_walk` |
| Wähle ich einen hinzugefügten Platz, bekommt der DSP so viele und dieselben Übertragungen wie beim Vorbild: Insert 14 gegen 14, Master 11 gegen 11 | gemessen | `presets:added_ifx_dsp`, `presets:added_mfx_dsp` |
| In der eigenen Hacktribe-Datei steht die Zeilenlänge bei `0xC0098084` auf 49, die 13 Stellen der Insert-Menülänge auf 59 | offline | Lesen der Datei; die Zeilenlänge fehlt in der Liste der Karte (`menu.ifxCount`) |

## Wo Korg sie ablegt

Der Block `0xC00A7F60` bis `0xC00C1BE0` (0x19C80 Byte) hält in Korgs Build 200 Records zu 524 Byte und zwei Zeigerfelder zu 400
Byte. Wer ein Preset sucht, geht nicht über Adresse und Schrittweite, sondern über das Feld. Die Läufe in der Reihenfolge der
Adressen:

| Von | Bis | Inhalt |
|---|---|---|
| `0xC00A7F60` | `0xC00ADF94` | 47 Records |
| `0xC00ADF94` | `0xC00AE124` | Zeigerfeld Insert, 100 Einträge |
| `0xC00AE124` | `0xC00AF390` | 9 Records |
| `0xC00AF390` | `0xC00AF520` | Zeigerfeld Master, 100 Einträge |
| `0xC00AF520` | `0xC00C1BE0` | 144 Records |

Die Einträge 1 bis 38 (Insert) und 1 bis 32 (Master) zeigen auf die Werks-Presets, die übrigen 62 und 68 auf unbenannte
Records. In welcher Reihenfolge Korg die 200 Records in den Läufen verteilt hat, folgt keiner Regel, die ich gefunden hätte;
darum gibt es für Korgs Build keine Tabelle mit fester Schrittweite.

## Was Hacktribe verschiebt

Vergleich von Korgs Datei mit der eigenen Hacktribe-Datei unter `0xC00A0000`: 55 kleine Bereiche, 218 Byte, dazu Hacktribes
eigener Code ab `0xC0140000` und die verlegten Tabellen. Davon gehören zu den Presets:

| Was | Korg | Hacktribe | Wozu |
|---|---|---|---|
| Zeigerfeld Insert, Literal bei `0xC003E74C` | `0xC00ADF94` | `0xC00A7F60` | die Records liegen hintereinander |
| Zeigerfeld Master, Literal bei `0xC003E764` | `0xC00AF390` | `0xC00B4DA0` | ebenso |
| Records | 3 Läufe, verstreut | `0xC00A80F0` (100), `0xC00B4F30` (100) | feste Schrittweite `0x20C`, jede Nummer ist ein Platz |
| Menülänge Insert | 38 an 14 Stellen | länger, an denselben Stellen | mehr Presets in der Liste (wie viele, siehe "Eigene Presets") |
| Menülänge Master | 32 an einer Stelle | an derselben | die eigene Datei hat 49, das ist meine Änderung |
| Reglergedächtnis Insert | `0xC0692278`, 38 je Zeile | `0xC013C200` im Abbild, Zeilenlänge 49 | die Zeile wird länger, hinter dem Gedächtnis steht in Korgs Speicher anderes |

Die Menülängen in der eigenen Hacktribe-Datei sind 59 und 49, die Zeilenlänge des Reglergedächtnisses 49 (die Liste der Karte
kennt diese Stelle nicht, siehe unten, sie ist also nicht von uns geändert worden). Das spricht für 49 Insert-Einträge in
Hacktribes Paket, 11 mehr als Korg; ich schätze, dass Hacktribe selbst nur etwa 5 mitbringt. Das ist hier nicht aufgelöst.
Dazu kommt der übrige Unterschied, der nicht die Presets betrifft: Hacktribes SysEx-Befehle, Filter, Effekte, Gruppen-Grooves
und die Karten-Ordner.

**Eigene Presets.** Viele Insert-Presets in der eigenen Hacktribe-Datei habe ich selbst gebaut, nicht Hacktribe (Hacktribe
selbst bringt wenige mit). Die Hash-Liste `data/originals.mjs` stammt von einem Stand der SD-Karte "vor unseren Änderungen", nicht
aus dem Hacktribe-Paket; die Zahl 49 dort ist darum keine Zahl von Hacktribe. Wer was gebaut hat, lässt sich aus den Dateien nicht
trennen und musste hier auch nicht getrennt werden: der Patch lässt jeden Record, wo er ist, und löscht oder verschiebt nichts.

## Alle Stellen, die an der Zahl der Presets hängen

| Stelle | Korg | Was dort steht | Der Patch |
|---|---|---|---|
| Literal Insert-Getter `0xC003E74C` | `0xC00ADF94` | Adresse des Zeigerfelds | neues Feld `0xC017C000` |
| Literal Master-Getter `0xC003E764` | `0xC00AF390` | ebenso | neues Feld `0xC017C200` |
| Klemmen `0xC003E73C`/`40` und `0xC003E754`/`58` | `cmp r0, #99`, `movhs r0, #99` | größter Index | 127 |
| Menülänge Insert (13 Stellen: 7 Anzahl, 6 letzter Index) | 38, 37 | siehe [FX-Tabellen im RAM](2026-09-14-fx-ram-write.md) | bleibt, der Editor setzt sie |
| Zeilenlänge des Reglergedächtnisses `0xC0098084` | `mov r2, #38` | Schrittweite für `mla` | bleibt, der Editor setzt sie mit |
| Menülänge Master `0xC003EFE4` | `mov r0, #32` | einzige Stelle | bleibt, der Editor setzt sie |
| Reglergedächtnis, 5 Literale | `0xC0692278` | Adresse der 16 Zeilen | neue Tabelle `0xC017C400`, 2048 Byte |
| Indexmaske in `0xC003ED04` (Preset in einen Kanal setzen) | `and r9, r0, #127` | der Index ist 7 Bit breit, Bit 7 ist ein Merker im selben Byte | bleibt, begrenzt auf 128 |

Der Rest: die beiden Getter haben 7 Aufrufer je Art, der Kanal-Setzer kopiert nur den Record (`0x20C` Byte) in den Kanal
(`0xC003E768`), nichts anderes hängt an einer Tabellengröße. Die zwei Pattern-Wege lesen die Typen aus dem Pattern:
der Insert-Weg (`0xC0048F70`) klemmt auf die Menülänge (`cmp r0, #37`, eine der sechs Stellen "letzter Index"),
der Master-Weg (`0xC0048888`) liest das Byte ohne Klemme.

## Messungen im Emulator

Aufruf: `tools/emu/preset_probe.py --vsb DATEI --flash dump.bin [--compat]`, die Fälle des Patches
`tools/emu/preset_cases.py cases --base BASIS --patched NEU`, in `check.py` eingebunden. Mit `tools/preset-add.mjs --vsb DATEI
--out VOLL --ifx max --mfx max` füllt dieselbe Funktion wie der Editor die Tabellen, und `preset_cases.py` prüft dann die
hinzugefügten Plätze (BASIS ist die Datei mit Patch, NEU die gefüllte).

| Datei | Insert | Master | INSERT-Regler | Master-Setter |
|---|---|---|---|---|
| Korg, unverändert | Menü 38, Getter(99) und Getter(100) bis (255) liefern denselben Record | Menü 32, ebenso | `37` springt auf `0` | nimmt 0, 31, 32, 33, 99, 100, 127 |
| Hacktribe (eigene Datei), unverändert | Menü 59 | Menü 49 | `58` springt auf `0` | ebenso |
| Korg mit Patch | Getter(100) bis (255) liefern Eintrag 1 | ebenso | gleich | gleich |
| Korg mit Patch, Tabellen voll | Menü 128, 90 Plätze hinzugefügt | Menü 128, 96 Plätze hinzugefügt | 128 Einträge, Sprung auf 0 | Auswahl bis 127 |
| Hacktribe mit Patch, Insert voll | Menü 128, 69 Plätze hinzugefügt | Menü 49 (Platz 50 trägt ein verstecktes Preset, der Editor überschreibt es nicht) | wie oben | wie oben |

## Entscheidungen

1. **128 Plätze je Tabelle, nicht 100 mehr.** Der Index ist in der Firmware 7 Bit breit (`and r9, r0, #127`, Bit 7 des selben Bytes
   ist ein Merker). 100 Plätze mehr als Korgs 38 und 32 wären 138 und 132. Das ginge nur, wenn das Byte im Pattern und der
   Weg durch `0xC003ED04` umgebaut würden; das ist ein eigener Eingriff in das Format der Pattern und keiner, den ich nebenbei
   mache. Mit 128 sind es **90 weitere Insert-** und **96 weitere Master-Presets** auf Korgs Build.
2. **Kein Record wird bewegt.** Die neuen Zeigerfelder zeigen für die ersten 100 Einträge auf dieselben Records wie die
   alten, die Einträge 101 bis 128 zeigen auf Eintrag 1, bis der Editor ihnen einen eigenen Record gibt. So gibt es zu keiner
   Zeit einen Platz aus Nullen, den man wählen könnte, und der Patch trägt keine Presets und keinen Hash über Presets, die ein
   Nutzer geändert haben kann. Er funktioniert deshalb auch auf der bearbeiteten Hacktribe-Datei.
3. **Hacktribe: umziehen, nicht erweitern.** Hacktribes Felder haben 100 Plätze, die Klemme steht auf 99, und hinter dem Feld
   liegen die Records des anderen Typs. Ein Feld in Hacktribes Lage zu erweitern geht nicht, ein neues Feld zu setzen ist
   derselbe Patch wie für Korg. Beide Fassungen unterscheiden sich nur in den Prüfsummen der Bytes, die sie ersetzen.
4. **Der Patch ändert keine Menülänge.** Mit ihm zeigt jedes Menü genau das, was es ohne ihn zeigt. Wer ein Preset hinzufügt,
   setzt die Menülänge an allen Stellen; das tut `src/presets.mjs`, nicht die Firmware. So bleibt EXIT beim Einschalten, wie
   es war: der Patch hat keinen Code, der übergangen werden könnte, und die Werks-Menüs sind dieselben.
5. **Neue Plätze sind Kopien.** Der Editor kopiert einen vorhandenen Record in den nächsten Platz und hängt ` n` an den Namen
   (höchstens 15 Zeichen). Ein Record wird nie gebaut, nur kopiert und dann bearbeitet.
6. **Keine Sample-Plätze, keine Namen angefasst.** Der Patch berührt weder Sample-Tabellen noch Sample-Namen.

## Muster mit Presets über dem Menü, ohne den Patch

Gemessen mit `preset_probe.py --compat`: das Pattern im RAM bekommt Master-Typ und Insert-Typ von Part 1 gesetzt, die Routine
`0xC004A8E4` setzt Effekte aus dem Pattern, danach wird gelesen, was im Pattern steht.

| Gerät | Menüs | Master im Pattern | danach im Pattern | Record des Master-Getters | Insert im Pattern | danach im Pattern |
|---|---|---|---|---|---|---|
| Korg, unverändert | 38 und 32 | 32 | 32 | unbenannt | 38 | **0** |
| | | 50 | 50 | unbenannt | 60 | **0** |
| | | 127 | 127 | unbenannt | 127 | **0** |
| Hacktribe (eigene Datei) | 59 und 49 | 49 | 49 | "Multi Tap" (verstecktes Preset) | 59 | **0** |
| | | 67 | 67 | unbenannt | 81 | **0** |
| | | 127 | 127 | unbenannt | 127 | **0** |
| Korg, Patch, Tabellen voll | 128 und 128 | 128 | 128 | Record 127 | 128 und mehr | 0 |
| | | 127 | 127 | "Mod Delay 128" | 127 | 127 |

Ein Insert-Typ gleich der Menülänge oder darüber kommt als 0 zurück, ein Typ darunter bleibt (Hacktribe: 58 bleibt, 59 wird 0).

Heißt: auf einem Gerät ohne den Patch (oder mit kürzerem Menü) spielt ein Insert-Typ über der Menülänge als Preset 1,
und **die Zahl im Pattern wird beim Anwenden auf 0 gesetzt**; speichert der Nutzer das Pattern danach, ist die Nummer weg.
Ein Master-Typ über dem Menü bleibt im Pattern stehen und zeigt auf den Record an dieser Stelle, bei Korg ein unbenannter
Platz mit Vorgabebytes, bei Hacktribe ebenso, ab Index 100 der letzte Record. Es gab in keinem Fall eine Assertion. Welcher Klang
dabei entsteht, ist nicht gemessen.

## Befund zu `menu.ifxCount`

Die Zeilenlänge des Reglergedächtnisses (`0xC0098084`) gehört zur Insert-Menülänge, steht aber nicht in der Liste der
Stellen der Karte (`data/map/firmware.mjs`, `IFX_COUNT`). Wird die Menülänge dort geändert, bleibt sie bei Hacktribes Wert.
In der eigenen Hacktribe-Datei steht sie auf 49, die 13 Stellen auf 59. Folge: die Firmware initialisiert 16 Zeilen zu 49 Byte,
liest aber Zeilen zu 59; die Bytes dahinter bleiben `0xFF` und werden beim Lesen auf 127 geklemmt. Das ist in der Datei messbar
(Liste oben), die Wirkung am Gerät ist nicht gemessen. Im Emulator gemessen an Korgs Datei mit Menülänge 128 und Zeilenlänge
38: die Zeilen 5 bis 15 des Gedächtnisses bleiben `0xFF`, erst mit Zeilenlänge 128 ist jedes Byte gesetzt (`presets:knob_memory`). `src/presets.mjs` setzt die Zeilenlänge mit; die Karte ist nicht
geändert, weil `identify` sonst die vorhandene Datei als "Stellen nicht einig" ablehnen würde.

## Offen

- Live ins RAM für die Plätze 101 bis 128 (die Karte beschreibt die Tabellen als zusammenhängend, die Plätze der Reserve
  liegen woanders; `allowedRegions` in `src/plan.mjs` kennt sie nicht).
- Am Gerät ist nichts geprüft: weder der Patch noch das Hinzufügen.
- Welcher Klang entsteht, wenn ein Pattern einen Master-Typ über dem Menü nennt.
- Wie viele der Insert-Presets nach Platz 38 in Hacktribes Paket stehen und wie viele meine eigenen sind.
