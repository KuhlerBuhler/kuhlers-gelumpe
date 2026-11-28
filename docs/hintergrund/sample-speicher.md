# Sample-Speicher: oberes RAM, Schreibwege, Dateibesitz und Journal

Was am Gerät und im Emulator über den Speicher der Samples gemessen ist: das obere RAM, die Aufnahme, die Schreibwege auf
den PCM-Speicher und ihr Schutz, der Besitz der Sample-Datei auf der Karte, das Journal und die Erstanlage. Das Format der Datei
steht in [sample-datei.md](sample-datei.md), die Karte des Flash in [speicherbereiche.md](../speicherbereiche.md). Die Messnotizen
dazu sind nicht mehr im Baum, sie stehen in der Git-Historie (`git show 03c7827adc7b:docs/messungen/<Datei>`). Weiter gelesen werden
kann in [Sample-Store](../messungen/2026-10-27-sample-store.md) und [Sample-Swap-Schutz](../messungen/2026-10-30-sample-swap-schutz.md).

Markierungen wie sonst: **gemessen am Gerät**, **gemessen im Emulator**, **offline gelesen** (Disassembly), **hergeleitet**, **offen**.
Alle Adressen gelten für Firmware 2.02 mit [Hacktribe](../glossary.md#hacktribe) auf der roten Electribe, wenn nichts anderes steht.

## 1. Oberes RAM `0xC274F000` bis `0xC4000000`

Der Bereich (Ende ausgeschlossen) ist 25.890.816 Byte groß, 24,69140625 MiB, 396 Blöcke, 6321 Seiten zu 4 KiB. Im RAM-Dump vom
Gerät war er nicht leer, ein Besitzer ist nicht bekannt ([Laufzeit](skript-laufzeit.md)). Am Gerät ist er mit einem Muster
geprüft worden, die Frage war, ob die Firmware ihn im Leerlauf und bei den Sample-Wegen anfasst.

**Messaufbau (gemessen am Gerät):** rote Electribe, Korg 2.02 und Hacktribe, ein minimaler BLECH-SysEx-Build. Das Wort an jeder
Adresse ist `ARM-Adresse XOR Muster`, geschrieben über die gecachte Adresse und geprüft über den ungecachten Spiegel
`0xC674F000..0xC8000000`. Muster am 06.11.: `0x73A96C25`, nach einem Neustart am 08.11.: `0x36E2B951`. Steuerregister
bleibt `0x0005107D`, TCM roh `0x1C`.

| Fall | Ergebnis (gemessen am Gerät) | Quelle |
|---|---|---|
| Füllen und sofortiger Leerlaufvergleich | alle 396 Blöcke, 6321 Seiten: 0 Seiten weichen im Spiegel oder in der gecachten Sicht ab, kein Timeout, kein Schreiber im Leerlauf. Hostzeit rund 45,8 s (Füllen) und 47,9 s (Prüfen), das ist SSH, SysEx und Tabellenlesung, nicht die RAM-Geschwindigkeit | Messung 2026-11-06/sample-ram-cache-geraet |
| 1 MiB USB-Lesen (32 Blöcke zu 32 KiB ab `0xC0D3A940`, nur INFO und READ, 2 INFO und 204 READ) | Muster in `0xC274F000..0xC4000000` unverändert: 0 von 6321 Seiten weichen ab, Hostzeit 4,251 s einschließlich Wächter | Messung 2026-11-06/sample-ram-usb |
| ein manueller nativer WAV-Import (`import.wav`, Name `import`, Zielplatz 541 = intern 540, PCM 100.000 Byte) | aktive physische Zeilen 40 auf 41, die Metadaten-Prüfsummen der 40 alten Zeilen gleich, nächster freier DSP-Platz 27.563.200 auf 27.663.200; danach 0 Seiten abweichend in Spiegel und Cache, kein Timeout | Messung 2026-11-08/sample-ram-import |
| Aufnahme: vier Läufe (Abschnitt 2) | alle 396 Blöcke, 6321 Seiten unverändert, alle drei Änderungskarten leer, Steuerregister `0x0005107D`, TCM roh `0x1C`, kein Timeout | Messung 2026-11-06/sample-ram-aufnahme |
| SAMPLE EDIT: Startpunkt ändern und mit EXIT verwerfen | Muster nach EXIT unverändert (gleiche 396 Blöcke, 6321 Seiten) | Messung 2026-11-08/sample-ram-bearbeiten |

**Grenzen (offen):**

- Der Besitz des ganzen RAM und alle Betriebsarten sind nicht bewiesen. Ein unverändertes Muster beweist nicht, dass kein Besitzer,
  Leser oder DMA dort arbeitet.
- Der Bereich ist **nicht** als Swap-Cache freigegeben. Geprüft ist nur der Import eines Platzes, nicht Mehrfachimport, `.all`,
  volle Bibliothek, Sample Edit, Löschen oder Export. Das DSP-Audio wurde nicht zurückgelesen.
- Das Muster bleibt im Testbereich stehen: eine Messsitzung endet mit einem Neustart, bevor normal gearbeitet wird.
- Ein 4-Minuten-Fenster am 08.11., in dem ein Import von `import.wav` (Platz 541) von Hand ausgelöst werden sollte, sah keinen
  Import. Das ist offen und kein Fehler des Importers.
- USB-Schreiben, andere Blockgrößen und USB-Übertragungen während PLAY sind nicht gemessen.
- Ein Lauf ohne Hacktribe (Korgs Original) ist nur im Emulator gemacht, der aktive TLB und weitere Besitzer sind nicht geklärt.

### Prüfwerkzeug `tools/device/sample_ram_canary.py`

Das Werkzeug füllt und prüft den Bereich mit dem Muster. Es nutzt nur `0xC274F000..0xC4000000`, prüft 224 Seiten je Teilprüfung
(die Tabelle passt in das erste KiB bei `0xC1000000`) und läuft nur bei ausgeschalteter MMU und ausgeschaltetem D-Cache. Es ruft
je einmal Füllen oder Prüfen auf der Hauptseite bei STOP auf und verlangt `--execute --operation fill --ram-overwrite-confirmed
--port-idle-confirmed --stopped-main-confirmed`. Sieben Codebereiche werden mit dem Original verglichen, das ist eine
Abbruchprüfung und kein Beweis der Gleichheit. Zusätzlicher Code (Doom-Lader `0xC017CC00`, Plugin-Code `0xC0150300`, Versionsbereich,
Varianten-Literal) lässt es abbrechen, vier synthetische Gegenfälle brechen vor dem ersten Aufruf ab. Voraussetzung ist ein frischer,
bekannter Minimal-Build. Nach der Sitzung folgt ein Neustart. Nach dem Plan werden Füllen und danach getrennte Prüfungen nach
Aufnahme, Resampling, Import, Export und USB bei STOP auf der Hauptseite gemacht. Quelle: Messung 2026-11-05/sample-pcm-fehler und
Messung 2026-11-06/sample-ram-vorpruefung.

**Vorprüfung am Gerät (nur lesen):** Korg-Suchmodell `0x24`, Version 2.02, MIDI-Kanal 10, Bibliothekslader `0xC00364F4` gleich dem
eigenen Original (Sample-Swap-Haken nicht eingebaut), Literalbereich `0xC004FAF8` gleich dem eigenen Hacktribe-Original. Das
BLECH-Update liest `KORG/blechtribe/System/SYSTEM.VSB`; die Bereiche `0xC00307B0` (212 Byte) und `0xC0035720` (112 Byte) stimmen mit dem
Original überein, das Update löscht keine Kartendateien.

### Was `highram_watch` am Gerät zeigte

Messung mit `--capture` (Sampling und Resampling, mono und stereo, Fenster 42): kein CPU-Zugriff über den Stackbereich. Der Import
der Patternbank schreibt den Arbeitspuffer bis `0xC1122840`, `0xC009BB2C` schreibt nach `0xC1122940`, also hinter den geplanten
Cache-Anfang `0xC1010000`. Der Puffer des Importers ist 4.096.000 Byte ab `0xC0D3A940`. Der untere Bereich darf nur über eine
ausdrückliche, abbrechbare Übergabe benutzt werden. Voller Lauf: 40 Samples, 24.000.000 Byte, exportierte `e2sSample.all`
23.553.376 Byte, Patternbank 4.161.792 Byte. Quelle: Messung 2026-11-05/sample-pcm-fehler.

## 2. Aufnahme

**gemessen am Gerät** (rot, vier Läufe, kurze Aufnahmen). Quelle und Kanalmodus liegen in `manager+0x708` und `manager+0x704`
(über das native Fenster 42 geprüft, VTable `0xC00E3AA8`), der Transportzustand in `transport+0x308`, der DSP-Frei-Zeiger bei
`0xC00F9C80`.

| Lauf | Quelle, Modus | DSP-Zeiger wächst um |
|---|---|---|
| Resampling mono | 1, 0 | 254.872 Byte |
| Audio In mono | 0, 0 | 273.962 Byte |
| Audio In stereo | 0, 1 | 703.820 Byte |
| Resampling stereo | 1, 1 | 479.984 Byte |

Zustand je Lauf: 10 bereit, 11 nimmt auf, 12 fertig, nach EXIT wieder 0. Werden alle vier Aufnahmen verworfen, steht der
DSP-Zeiger exakt wieder auf 27.563.200. Die 40 aktiven Zeilen der physischen Tabelle `0xC036AD88` (1000 Zeilen zu `0x45C`) sind
nach Identität und SHA256 vor und nach den Läufen gleich. Eine Aufnahme, die als Audio In mono vorbereitet war, startete mit Quelle 1: Resampling
ist am Gerät bestätigt. Keine lange Aufnahme, kein WRITE, kein volles DSP-Gedächtnis gemessen. Quelle: Messung 2026-11-06/sample-ram-aufnahme.

**Aufnahme bestätigen und löschen (offline gelesen):** Das Ende der Aufnahme öffnet Fenster `0x2A` im Transportzustand 12. WRITE
bestätigt über Auftrag `0x25`, EXIT verwirft über `0x24`, ENTER bestätigt nicht. Beim Löschen fragt das erste ENTER nur, EXIT löscht
nichts, das zweite ENTER sendet Auftrag `0x24` (`0xC0039588` nach `0xC0035994`/`0xC004E558`) und setzt die physische Zeile auf
nicht geladen. Die Karte bleibt dabei unverändert. Quelle: Messung 2026-10-30/sample-speichergrenzen.

**Aufnahmepfade (offline gelesen):** Das Sampling öffnet als Fenster 42 über `0xC0083DB0`; Bildschirm 41 ist ein anderer Objekttyp.
Der Manager `0xC0035AD8` hält Mono/Stereo (`+0x704`) und Audio In/Resampling (`+0x708`), die Handler sind `0xC006B3FC` und
`0xC006B440`. Der zweite Parameter von `0xC0082F1C` ist **nicht** die Quelle: Resampling mit einem Wert ungleich null startet auch PLAY.
STOP kann das Fenster ersetzen, der alte Objektzeiger darf nicht weiterverwendet werden. Der Zeitscheiben-Pfad `0xC00395E4` ruft
`0xC0050208`, das Anwenden `0xC004FE08` nimmt den Deskriptor mit `0xC004EFF4` zurück, ein Blockschreiber kommt dort nicht vor. Im
geprüften SAMPLE EDIT gibt es keine Einträge Normalize oder Truncate. Quelle: Messung 2026-11-05/sample-pcm-schreibpfade.

**Speicheranzeige im Sampling-Fenster (gemessen im Emulator, HT und rot):** Korgs Zeile "Memory" (deutsch "Speicher") auf der
dritten Seite des Fensters 42 schätzte freie Sekunden: `0xC007DE80` nimmt die freien Bytes von `0xC004E218`, halbiert, teilt durch
48000 und halbiert in Stereo noch einmal (Beispiel: 25.894.400 Byte frei zeigen "269 [secs]" in Mono). Mit dem Sample-Swap zeigt die
Zeile den freien Sample-Speicher in MB mit einer Nachkommastelle, abgerundet, zum Beispiel "24.6 [MB]". Bei ausgeschaltetem Swap ist
das Korgs eigene Zahl. Bei eingeschaltetem Swap zählt auch jede Lücke, die eine Verdrängung unter dem DSP-Frei-Zeiger hinterlässt
(Abschnitt "Verdrängen" in [Sample-Swap](sample-swap.md)). Eine Aufnahme beginnt weiter am Frei-Zeiger, Korgs Prüfungen beim Öffnen
des Samplings (`0xC006F71C`) und beim Laden (`0xC0036234`) behalten Korgs Zahl. Die Haken sitzen in der Zeile selbst
(`0xC008C698`, `0xC008C6AC`, `0xC008C6C4`), die Texte "Memory"/"Speicher" aus lang-de bleiben unberührt. Quelle: Emulatorfälle
`swap:the_memory_line_*` in `tools/emu/swap_cases.py`.

## 3. SAMPLE EDIT und Sicherungsdeskriptor

**offline gelesen:** Auswahl `0xC007EC74(mgr, delta, notify)` auf Bildschirm 37, ENTER öffnet Bildschirm 38 und Kommando `0x20` macht
den Schnappschuss. WRITE (Taste `0x0E`) gibt Kommando `0x25` aus, ohne weiteres ENTER. EXIT ohne WRITE gibt Kommando `0x21` aus
(`0xC0039420` nach `0xC004EFF4`) und stellt die alten Werte wieder her. Das Fenster `0x19` ist allgemein, es gibt kein
Pattern-WRITE. Nach WRITE behält EXIT die neuen Punkte, ein zweites WRITE gibt denselben Auftrag erneut aus. Das Menü hat keine
Seiten NORMALIZE oder TRUNCATE, Start, Ende und Loop sind echte Punkte. Quelle: Messung 2026-10-30/sample-speichergrenzen und Messung 2026-11-06/sample-ram-cacheprobe.

**Sicherung (hergeleitet aus Code und am Gerät geprüft):**

| Ort | Bedeutung |
|---|---|
| `0xC0345A20` | Byte, Sicherung gültig |
| `0xC0345A2C` | Sicherungsdeskriptor: Eingabeindex am Anfang, Name, Mapping-Schlüssel; `0x494` Byte mit `0x45C` Byte Metadaten, ohne PCM (die 12 Zusatzbytes des Swaps gehören nicht dazu) |
| `0xC0039514` | liest den gewählten Eintrag aus dem Sample-Manager und ruft `0xC004EBD4`, das den Eingabeindex an den Anfang schreibt und die Namenszeile kopiert |
| `0xC0039420` | EXIT-Pfad, übergibt den Deskriptor an die native Wiederherstellung `0xC004EFF4` |
| `0xC004E63C` | nativer Startpunkt-Getter |
| `0xC007EC74` | Auswahlwechsel |

Aufrufparameter des Schnappschusses: r0 interner Platz, r1 Ziel `0xC0345A2C`, r2 DSP-Byte-Basis (aus), r3 PCM-Länge (aus), fünftes
Stack-Argument 0, Rückgabe 1 = gültig geladen. `0xC0345A20`/`0xC0345A28` werden beim Öffnen oder bei der Slice-Vorbereitung gesetzt,
ohne den Inhalt zu ändern, ein unverändertes WRITE braucht also einen Inhaltsvergleich.

**Falle:** Ein geschlossener Bearbeitungsbildschirm allein beweist nicht, dass das richtige Sample zurückgesetzt wurde. Auswahl, Sicherungsindex und
Sicherungsname müssen vor der Änderung stimmen, danach muss der Startpunkt zurückkehren. Quelle: Messung 2026-11-08/sample-ram-bearbeiten.

**gemessen am Gerät (ein mono Sample, nicht jede Bearbeitungsart):** Beim ersten Versuch gehörte die Sicherung zu einem anderen
Sample (Sicherungsindex 500 `t501` gegen Ziel 540 `import`), der Startpunkt stand auf 67 statt 0. Die Aufräumung von Hand stellte
Startpunkt, 41 Metadaten-Prüfsummen und den DSP-Frei-Zeiger 27.663.200 wieder her. Mit passender Sicherung: Startpunkt 0 auf 18, EXIT
ohne WRITE setzt auf 0 zurück (Sicherung gültig 1 auf 0), die Metadaten aller 41 Zeilen und der DSP-Frei-Zeiger bleiben gleich.

**gemessen im Emulator:** 17 Gegenfälle, darunter physische Zeile ungleich logischem Platz und Start in Frames bei mono und stereo.
EXIT setzt den Startpunkt zurück. Ein Auswahlwechsel nach der Sicherung (`0xC007EC74`) lässt den Start des anderen Samples auf 1 (die
Wirkung der falschen Auswahl ist so nachgestellt). WRITE behält den Wert 1 nach EXIT, die Sicherung bleibt nach WRITE gültig,
Flash- und Kartenbytes sind unverändert.

**offen:** Beim Eintritt in Sample Edit (Bildschirm 38) fehlte einmal eine Leseantwort länger als 6 s, Ursache unbekannt, nicht durch
Wiederholung verdeckt. WRITE, Löschen, Export, andere Edit-Parameter und das Zurücklesen des DSP-Audios sind nicht geprüft.

## 4. Native Sample-Funktionen und Schlüssel

**offline gelesen** (in beiden roten Originalen gleich, SHA geprüft):

| Funktion | Adresse | Parameter |
|---|---|---|
| löschen | `0xC004E558` | roher Importschlüssel |
| reservieren | `0xC004EDF0` | Deskriptor, logischer Platz bei `+0` |
| Startpunkt | `0xC004E63C` | roher Schlüssel plus Delta (signiert, in Frames) |
| Ende | `0xC004E710` | wie Startpunkt |
| Loop-Start | `0xC004E7E8` | wie Startpunkt |
| umbenennen | `0xC004E8C8` | Schlüssel, Zeiger auf 16 Namensbytes |
| Slice-Daten leeren | `0xC004E93C` | |
| Deskriptor zurückrollen | `0xC004EFF4` | |

Bei Start, Ende und Loop-Start ist Delta 0 ein Getter und setzt keine Marke. Der rohe Importschlüssel 600 entspricht der gespeicherten
Importnummer 650 (Versatz 50), ein Adapter korrigiert ihn vor `physical_import`. Veröffentlichen und Löschen des Swaps umgehen die
Änderungsmarke nur an ihren genauen Rücksprungadressen, nicht über ein globales INSTEP. Der Importer einer Menü-WAV läuft in Task
`0xC06A2564`. Quelle: Messung 2026-11-05/sample-schutz.

Weitere Fälle: In Teilen und Stimmen steht die logische Wahl im Part bei `+0x34`. Eine nicht geladene Wahl kann schon den gewünschten
Platz halten, während der abgeleitete Typ `+0x39` `0xFF` ist. Die Importnummer `+0x40` gehört zur Stimme. Der native Part-Update
erwartet einen physischen Index, nie einen logischen Platz übergeben. Quelle: Messung 2026-10-30/sample-speichergrenzen.

Die Slice-Vorbereitung `0xC00395E4` über `0xC0050208` verlangt: Umfang plus 2 Byte streng unter `0x01A00100`, Blöcke bis `0x8000`
16-Bit-Wörter (derselbe Arbeitspuffer wie Import und Export). Quelle: Messung 2026-11-06/sample-ram-cacheprobe.

Der Host-Befehl `0x3B` trägt sieben 16-Bit-Wörter, der Sender rundet die Übertragung auf 16 Wörter auf. Manager `+0x708`/`+0x704`
sind Quelle und mono/stereo, das zweite Argument von `0xC0082F1C` erlaubt nur den PLAY-Start. Der WAV-Schreiber nimmt R1 `FIL*`, R2
Deskriptor, R3 DSP-Byteversatz, die PCM-Byteanzahl als fünftes Stack-Argument, R1 ist bei `0xC0039B38` gesichert. Die SD-FIFO-Schleifen
haben keinen EDMA-Deskriptor (`0xC00180F0`, `0xC0017F18`). Quelle: Messung 2026-11-06/sample-ram-cacheprobe.

### Bedienwege des Imports

Der Import-Browser (Bildschirm 39) nimmt WAV und `.all`; `.all` zeigt die Bestätigung "Import All Samples", Kommando `0x12` ruft
`0xC0038D80` (weiterer direkter Aufrufer: Startpfad `0xC0038D60`). Einen eigenen DATA-UTILITY-Eintrag für den Gesamtimport gibt es
nicht. Quelle: Messung 2026-11-06/sample-ram-cacheprobe.

**Menü-Import (gemessen im Emulator, Quelle: Messung 2026-11-09/sample-import-menue):**

- Das Menü schlägt Platz 501 vor, auch wenn er belegt ist; bei Annahme geht r1=500 hinein. Der native Pfad reserviert DSP-Platz und
  lädt 40.000 PCM-Byte, die Datei bleibt byteidentisch. Ist Platz 503 auch auf der Karte frei, meldet der Import Erfolg bei
  `0xC0038DE4`, der Name erscheint, aber die Karte hat noch den alten Index.
- Ohne `.all` (Ordner da) erreicht der Startbefehl die Existenzprüfung `0xC0038D50` mit `SD:KORG/blechtribe/Sample/e2sSample.all`, der
  Lader `0xC00364F0` läuft nicht, 128 Pfadbytes des Swap-Zustands bleiben `0xFF`.
- Schlägt das Schließen der WAV-Quelle fehl, gibt der Import Fehler 4 zurück. Das gemeinsame Dateiobjekt bleibt gesperrt, bis das Schließen
  bestätigt ist (gäbe man es frei, könnte ein zweiter Import es benutzen und die Bibliothek ändern). Der zweite Import bekommt Fehler 4, die
  Katalogprüfung schließt die alte Quelle bei Wiederholung.
- Ein abgelehnter Import (ungültiges Audioformat) verlässt den Normalbetrieb und gibt den Dateibesitz frei. Ein von der Karte
  bestätigter neuer Platz aktiviert den Swap trotz der Fehlermeldung. Das Ziel muss gegen den Kartenindex geprüft werden, ein
  Überschreiben braucht eine bewiesene Bestätigung.

**Import auf einen freien Platz (Regeln, Quelle: Messung 2026-11-10/sample-import-karte):** Der Menü-Import hängt die WAV im Kartenformat an
und ändert in der alten Datei nur die 4 Byte des neuen Platz-Versatzes, das PCM gleicht der WAV. Am Import wird kein DSP-Platz
reserviert (der Zeiger bleibt bei `0x01C65EC0`), der Name ist über die native Namensabfrage sichtbar, das PCM kommt bei der Auswahl in
den DSP. Fehlt die Datei, legt derselbe Pfad die erste Bibliothek an, wenn der Ordner Sample existiert. Ein auf der Karte belegter Platz
wird abgewiesen, auch wenn der DSP ihn nicht hält (Bibliothek byteidentisch). Das Menü darf einen belegten Platz vorschlagen,
der Nutzer wählt einen freien, Überschreiben über dieses Menü ist nicht freigegeben. Import nur bei STOP ohne Aufnahmeergebnis: der
Besitz wird geprüft und gesetzt, bevor einer der beiden Pfade unterbrochen werden kann; ein modellierter Aufnahmezustand bricht den
Import ab, ein gehaltener Importbesitz sperrt den nativen Aufnahmestart. EXIT am Start behält den nativen Pfad. Ein Schließfehler der
WAV bleibt ein Fehler, auch wenn der Platz schon auf der Karte steht. Keine Flash-Schreibzugriffe. Eine große Stock-Probe wächst von
54.562.848 auf 54.604.080 Byte, das Audio ist nach einem Neustart gleich.

**Alter Info-Spiegel (Flash-Pfad, offline gelesen):** `0xC004FB6C` vergleicht sechs Datensätze (Namen, drei Mapping-Tabellen, Playback,
Metadaten) mit dem RAM-Spiegel `0xC0C9A940`; bei Abweichung läuft `0xC004C3D4` nach `0xC002A218` nach `0xC0029AB8` und schreibt
640 KiB seriell in `0x6B0000..0x750000` (Ende ausgeschlossen, Id `0x6B` um 16 verschoben), im Modell einschließlich eines zusätzlichen
4-KiB-Sektors geprüft (1 Löschen, 16 Programmseiten, `0xC001E7BC`/`0xC001E6B0`, SPI `0x20`/`0x02`). Synthetische Importschlüssel ab 500
verlassen den Weg vorher. Ein neuer Kartenschreiber darf diesen Flash-Weg nicht benutzen. Der Import (`0xC0038DE0` nach `0xC003644C`) ändert
zunächst nur den DSP (6 Einträge, 491.488 Byte, Platz 500). Quelle: Messung 2026-10-30/sample-speichergrenzen.

## 5. Schreibwege auf den PCM-Speicher und ihr Schutz

**offline gelesen und im Emulator geprüft.** Ungeschützt gefundene Wege:

- Blockschreiber `0xC0014284`: DSP-Byteziel r0, ARM-Quelle r1, Halbwortzahl r2 auf 16 Bit gekürzt. Der Schreiber `0xC004EF28` ruft ihn
  und schreibt unter 15 Halbwörtern aufgefüllt auf einen 32-Byte-Block. Aufrufer von `0xC004EF28` bei `0xC003631C` und `0xC00363E0`.
- Aufnahme-Ende `0xC004F128` nimmt sein r0 direkt als **physischen** Tabellenindex (die Gleichsetzung mit dem logischen Platz gilt nur im
  Identitätsmodell) und veröffentlicht Tabellen ohne RESERVE oder Blockfunktion.
- `0xC003DDE0` und `0xC00762E8` schreiben interne Bereiche `0xFF900018` und `0xFF900A38` (nicht die Nutzerbank). `0xC004FA74` gehört
  zur L/R-Verschmelzung `0xC004F490`, deren drei Aufrufer dem Werkslader `0xC004D860` folgen (Start, Werkszustand, Rückfall nach
  fehlgeschlagenem Volllade); ein normaler WAV-Import nutzt sie nicht. Die Schleifengrenze aus dem MSVS-Kopf wird nur gegen 999
  geprüft, nicht gegen 421 oder 274.
- Eine reine PCM-Änderung ohne Änderung von Metadaten, Playback- oder Namenszeile hinterlässt keine Marke (reproduzierter Fehler,
  `sample_protection_cases.py --patched ... --pcm-write`).

Quelle: Messung 2026-11-05/sample-schutz und Messung 2026-11-05/sample-pcm-schreibpfade.

**Aufgabenkennung eines nativen Aufrufs (offline gelesen):** `0xC0001480` schreibt die Tasknummer `((Kontrollblock - 0xC06A24E4) >> 5) + 1`
über `0xC06A289C`; es gibt 10 Kontrollblöcke zu 32 Byte, nötig ist IRQ-Tiefe 0. `0xC0000D80` (acquire) reiht den Block über `0xC0001D14` ein und ruft den Planer `0xC0001760`. Die Kernel-Spannen sind in beiden Originalen gleich. Im Emulator wird der Blockschreiber
aus dem Bildschirm-Tick in Task 4 mit IRQ-Tiefe 0 gerufen (Ressource frei, belegt, frei); INSTEP ist ein globales Flag und beweist keine
Taskzugehörigkeit. Quelle: Messung 2026-11-05/sample-pcm-schreibpfade.

### Entwurf des Schutzes

- **Signatur** = FNV über Metadatenzeile, 16 Byte PLAYBACK und 32 Byte Namenszeile (eine XOR-plus-Add-Summe übersähe Änderungen um
  256). Eine erkannte Änderung setzt eine bleibende Marke an der **physischen** Zeile: ein Alias darf keinen geänderten Alias
  verdrängen, die Marke überlebt eine Rückänderung. Das gilt auch, wenn der Wert auf den alten zurückgestellt wird.
- Ein Durchlauf besucht jeden der 499 Nutzerplätze höchstens einmal, das Schrittbudget von 15 ms ist nach 4 Signaturen erreicht. Signaturen
  laufen bei freien Interrupts, Bitmap-Änderungen und die letzte Besitzprüfung in kurzen kritischen Abschnitten. Ein Änderungszähler
  und die Cache-Generation machen vorbereitete Entscheidungen ungültig, ein Zählerüberlauf sperrt die Freigabe bis zu einer neuen Sammlung.
- **Bereichsschutz der PCM-Schreiber:** Jede aktive Nutzerzeile mit überlappender Spanne wird dauerhaft als geändert markiert, Aliase
  teilen die Marke, überlaufende oder beschädigte Umfänge werden vorsichtig behandelt. Ein fremdes Schreiben in freien Nutzerraum macht einen
  noch nicht veröffentlichten Swap-Auftrag ungültig, vorbereitete Entscheidungen und Schutzrevision werden vor den Audiodaten
  verworfen. Interne DSP-Befehlsbereiche und Aufrufe ohne Datenwörter sperren nichts.
- **Ausnahme beim Boot:** nur die eigene reservierte Zeile des Parsers (geprüft: nativer Aufrufpfad, Parser-/Cursor-Frame, Rücksprung
  nach `ss_boot_parse`, gespeicherter Platz, physische Map, Umfang, Revision, kein offener Swap-Auftrag). Ein fremder DSP-Schreiber
  beim vollen Laden ändert die Revision, dann wird keine saubere Ausgangsversion veröffentlicht.
- Im schlechtesten Fall (499 Zeilen geschützt) 27.544 ARM-Instruktionen im Modell, keine Interrupt-Latenz gemessen. Der Patch hat 132
  Haken. Gegenfälle: `tools/emu/.venv/bin/python tools/emu/sample_protection_cases.py --patched EIGENER_PATCH.VSB --pcm-write`
  (auch `--pcm-boot`, `--pcm-edges`).
- **Aufnahme:** Das Schutzbit der **physischen** Zeile wird nach erfolgreichem Lesen des DSP-Endzeigers und vor der ersten Änderung des
  DSP-Frei-Zeigers bei `0xC004F188` gesetzt; die Schutzrevision steigt, vorbereiteter Auftrag und gestufter Puffer werden ungültig (eine
  vorbereitete Entscheidung bliebe sonst gültig, obwohl die neue Aufnahme DSP-Fläche belegt). Quelle: Messung 2026-11-10/sample-aufnahme-schutz.

**offen:** reale Interrupt-Latenz des Bereichsschutzes, Besitzprüfung nach einem Ressourcen-Warten, Schutzrevision, wenn eine Aufnahme
veröffentlicht wird (DSP-intern, nicht über den Blockschreiber), volle RAM- und DMA-Freigabe. Quelle: Messung 2026-11-09/sample-pcm-bereichsschutz.

### Drehregler: Tune und Level

Direkte Schreibstellen (offline gelesen, Quelle: Messung 2026-11-05/sample-schutz und Messung 2026-11-05/sample-pcm-fehler):

| Setter | Speicherstelle | Was |
|---|---|---|
| `0xC007F980` (Tune) | `0xC007F9F0` | Halbwort r2 nach `[r3+0x14]`, der UI-Wert wird zuerst um 8 nach links geschoben |
| `0xC007F8A8` (Sample-Pegel) | `0xC007F94C` | Byte r5 nach `[r6+0x0A]` |
| `0xC007F0EC` (Tune), `0xC007EFE8` (Level) | | Regler-Schreibstellen, geschützt; der Zeiger liegt 16 beziehungsweise 8 Byte in der physischen Metadatenzeile |

Der Platz kommt aus `r0+0x3FC`, r1 ist ein Zeiger auf das Wertobjekt, sein Wort `+4` der Wert. Der Wrapper muss die Flags erhalten
(`cmp r7,#0` vor dem Store). Vergleich, Marke und Store laufen in einer IRQ-Sperre, die Zeigerdivision vor der Sperre ist durch 999
Zeilen begrenzt. Ein Zurückstellen auf den alten Wert löscht die Marke nicht.

### Geprüfte Ladung und Transport

- **Geprüfter Abschluss des Ladens:** Der Sammlungslader ruft den Parser `0xC00366FC` mit angefordertem Platz minus 1; erwartet wird der
  Platz aus dem Dateikopf oder dem Iterator. Ein Prüfwert liegt im Stackrahmen des Aufrufs und wird nur vom nativen Reserve-Aufruf bei
  `0xC003629C` aktualisiert. Der Originalrahmen des Parsers hat `0x4F0` Byte, die Rücksprungadresse liegt bei `sp+0x4EC`, die
  Cursor-Erweiterung fügt einen Rahmen von 24 Byte hinzu. Unbekanntes Layout bestätigt keine Zeile.
- **Block-Haken** `0xC00141F8`/`0xC0014284` bekommen einen eigenen begrenzten Kontext außerhalb eines Swap-Schritts. Ein Fehler läuft
  über `0xC004EF58` (kleines Blocklesen), `0xC0036320` und `0xC00363E4` (normales PCM-Schreiben, letzter Teilblock) bis zum
  Parser-Ausgang mit Status 4. Die Tests nehmen WAVs mit 1, 16 und 17 Frames.
- **DSP-Transportstatus** hat drei Zustände: 0 bereit, 1 laufender Transfer, 2 verriegelter Fehler. Ein fremder Zustand 1 heißt belegt,
  nicht Fehler; ein Rest-1 nach erworbenem Port ist ein abgebrochener Auftrag und verriegelt. Ein fremder Fehler wird nicht auf 1 gesetzt
  oder gelöscht. Geprüft wird in einer kurzen IRQ-Sperre.
- **Veralteter Auftrag:** Eine native Metadatenänderung beendet den laufenden Swap-Auftrag, ohne unveränderte Cache-Einträge zu
  verwerfen. Suche, Reservierung und Aktivierung teilen eine Schutzrevision. Rückgabewert 7 beendet einen veralteten Auftrag, ohne einen
  DSP-Protokollfehler vorzutäuschen. Der Ladepfad nimmt Blöcke zu 64 KiB (Konstante CHUNK), ein privates 16-KiB-Limit wäre zu eng.
- **Zeitbudget:** 100 ms bei gültigem 150-MHz-Timer plus Pollzahl; das Kernel-Acquire `0xC0000D80` kann noch warten. PCM-Aufträge brauchen
  nach einem blockierenden Acquire eine Bibliotheks-Id. Die Zahl von 10 bis 11 MiB/s des alten Transports gilt hier nicht.

## 6. Speicherplatz der Schutzlogik

Der Schutzcode liegt im FF-Bereich `0xC019C400..0xC019E000` (Ende ausgeschlossen); der DSP-Transportbereich beginnt dahinter und bleibt
frei. 160 Byte Schutzzustand liegen bei `0xC276CE80..0xC276CF20` im freien Rest hinter den 1000 Cache-Indexsätzen und vor LIST
`0xC276D000`; `cache_reset` überschreibt ihn nicht. Dateiadresse = `ram - 0xC0000000 + 0x100`. Die Routinen des Speicherns liegen ab
`0xC0186800` bis vor `0xC0188000` (in beiden roten Originalen auf `FF` geprüft); der DSP-Messbereich `0xC019E000` bleibt frei.
Quelle: Messung 2026-11-05/sample-schutz und Messung 2026-11-11/sample-aenderungen-speichern.

## 7. Dateibesitz auf der Karte

**Besitz der Sample-Datei (offline gelesen, im Emulator geprüft, Quelle: Messung 2026-10-29/sample-dateibesitz):**

- Ein tokenbasierter Besitzer hält aktuellen Token, letzten Token, Katalog-ungeklärt-Flag und Zugriffsart (Lesen, Schreiben,
  Wiederherstellung). Nach dem Start sind Lesen und Schreiben gesperrt, bis eine bestätigte Wiederherstellung lief. Ein Schreibversuch
  lässt den Katalog ungeklärt (ein Loslassen allein beweist nichts), ein Lesefehler ebenso, bis eine geprüfte Wiederherstellung läuft.
  Nur der aktuelle Leser mit geklärtem Katalog darf den Ladepfad benutzen. Der atomare Auftrag braucht weniger als 80 Instruktionen
  bei maskierten IRQs.
- `close_reader` hält drei Zustände (zu, offen, Schließen ungeklärt). Der native Lader ignoriert einen F_CLOSE-Fehler beim Wechsel der
  Cache-Generation und öffnet denselben Arbeitsbereich neu, ein gescheitertes Kopflesen hinterlässt ein unverfolgtes offenes Handle. Der
  Patch sperrt nach einem fehlgeschlagenen Schließen das nächste Öffnen.
- Der Bootlader fragt Wiederherstellungsbesitz an, bevor er die Sample-Tabellen zurücksetzt. Der Swap-Schritt fordert einen Leser an, bevor
  er einen Auftrag wählt, liest oder kopiert; belegt oder ungeklärt lässt Auftrag, Generation und Tabellen unberührt. F_READ-, Kurzblock-
  und Seek-Fehler setzen den Ladepfad auf Fehler, spätere Durchläufe machen nicht weiter.

**Gemeinsame Grenze des Kartenschreibers (Quelle: Messung 2026-10-31/sample-dateibesitz):** `catalogue_begin` und `catalogue_end` benutzen
das vorhandene Dateisperre und die vorhandenen Puffer (kein neues RAM, kein Flash-Zugriff). Begin lehnt ab bei nicht initialisierter oder durch EXIT
umgangener Laufzeit, DSP-Fehler und konkurrierendem Dateibesitzer. Nach dem Erwerb der Wiederherstellungssperre: Musterwechsel
sperren und Cache-Generation erhöhen, alte Ladeaufträge, vorbereitete Blöcke und Cache-Einträge ungültig machen, den gemeinsamen Leser
schließen, das Journal auflösen und den echten Dateikopf lesen und prüfen. Der Schreiber hält die Sperre bis End. End schließt wieder,
prüft das Journal, liest den echten Index auch nach einem gemeldeten Schreibfehler; ein früherer Operationsfehler bleibt ein Fehler.
Schließ-, Wiederherstellungs- und Lesefehler lassen den Katalog ungeklärt und den Swap gesperrt, ein gesetzter DSP-Fehler hält ihn
gesperrt. Eine kleine Datei geht zurück in den normalen Ladepfad, eine große in den Swap. `owner_check_recovery` verlangt den aktuellen
Wiederherstellungs-Token, Taskkontext und gestartete Firmware ohne laufenden Interrupt; ein ungültiger Abschluss lässt den Besitzer
unberührt. Zwei Gegenfälle sind abgedeckt: ein Abschluss mit gültigem Token bei maskierten Interrupts prüft den Kontext vor dem ersten Dateizugriff
(die alten Sperrfunktionen lehnten erst danach ab); die Generation wird nach der Änderungssperre neu geprüft, weil ein UI-Frame sie zwischen
Vorprüfung und Sperre auf `0xFFFFFFFF` heben könnte und die nächste Erhöhung auf 0 überliefe (ein solcher Auftrag endet ohne Dateizugriff).

**offen:** normale Import-, WRITE-, Lösch- und Aufnahme-Bestätigungen sind noch nicht an diese Grenze angeschlossen; ein erster Import
ohne vorhandene Bibliothek hat keine frühe Initialisierung von Standardpfad und Laufzeitzustand; ein fehlgeschlagenes Schließen der
Import-Quelle muss ein unklarer Dateizustand bleiben; physische Versionsmarken und neue DSP-Zeile sind nicht veröffentlicht; voller Export,
echtes Aufnahme-DMA, Stimmenschwanz und ein 25-MHz-Test auf einer Ersatzkarte fehlen.

## 8. Journal, Erstanlage und Fehlerfälle

**Journal (gemessen im Emulator, Quelle: Messung 2026-11-10/sample-journal-wiederanlauf):** Ein 512-Byte-`.txn` nach einem kurzen Schreiben
sperrte alle weiteren WAV-Importe, obwohl der Platzindex unverändert war. Ein vollständiges Journal ist ein 64-Byte-Vorspann
(Journal-Prüfsumme, Prüfsummen des alten und des beabsichtigten neuen Kopfs) plus 4096 Byte alter Kopf. Die Wiederherstellung öffnet
die Bibliothek nur lesend; alle übrigen Journal-Kopfbytes müssen dem alten Kopf gleichen, das neu gebaute Journal samt gespeicherten
Prüfsummen und Längengrenzen wird geprüft, erst dann wird das Bruchstück entfernt. Sie nimmt nie einen neuen Platz aus dem Bruchstück
und kürzt die Datei nie (ein abgebrochenes Anhängen kann unverlinkte Bytes lassen, der nächste Import hängt am echten Dateiende an).
Bruchstücke mit 64, 65, 512 und 4159 Byte werden entfernt; kurzer Vorspann, geändertes Bruchstück, geänderter Platzindex und kürzere
Bibliothek werden abgelehnt. Menütest: Fehler 4, Platz bleibt leer, ein Neustart entfernt es ebenfalls, der nächste Import gelingt.

**Gemessene Ausfälle des WAV-Imports (gemessen am Gerät, rot, erzeugte Karte; Quelle: Messung 2026-11-10/sample-import-kartenfehler):**

| Fall | Ergebnis |
|---|---|
| Karte mit nur 4 freien Clustern | Menüfehler, alte Samples bleiben, neuer Index leer |
| Neustart nach dem Anhängen, vor dem Journal | alte Samples bleiben, Block nicht sichtbar |
| Neustart mit geprüftem Journal vor der Indexänderung | die Firmware stellt den Index her und lädt das neue Sample |
| 2 von 4 Indexbytes geschrieben | Menüfehler, das Journal stellt den ganzen Index her, auch von diesem Kartenzustand aus |
| einmaliger Fehler beim Entfernen des geprüften Journals | Fehler angezeigt, nach der Wiederherstellung Sample vollständig und Journal weg |
| 512 von 4160 Journalbytes geschrieben | alte Samples byteidentisch, neuer Index leer, das **unvollständige Journal bleibt** und ein weiterer Import wird auch nach einem Neustart abgelehnt |

Ein abgebrochener Vorgang kann unverlinkte Bytes am Dateiende lassen (keine automatische Verdichtung). Echter Stromausfall der Karte,
Entnahme und Schreibfehler des Controllers sind nicht gemessen.

**Erstanlage (gemessen im Emulator, Quelle: Messung 2026-11-10/sample-datei-erstanlage):** Das FatFs kann nicht umbenennen, deshalb
legt der Patch vor dem ersten Schreiben eine leere Statusdatei an: `.txh` für den neuen Bibliothekskopf, `.txp` für das Journal
(beide Endungen reserviert, vorhandene Dateien werden nicht überschrieben). Eine markierte Bibliothek wird nur lesend geöffnet; gleichen
die Bytes dem Anfang eines leeren Kopfs, werden die fehlenden Bytes ergänzt, sonst bleibt sie unberührt. Ein Journal unter 64 Byte wird
geprüft (Marke, Signatur- und Versionspräfix, gültiger Kopf, Prüfbytes des alten Kopfs). `.txp` wird vor der ersten Indexänderung
entfernt. Beim Laden wird zuerst das Journal geprüft; ein zusätzliches Öffnen und Schließen gibt es nur bei einem Kopf unter 4096 Byte.
Übrige Statusdateien dürfen bis zum nächsten Schreiben liegen bleiben.

Falle: Bei einer erzeugten Bibliothek mit 50.680.384 Byte gab das erste Wieder-Öffnen der `.all` bei PLAY durch Hacktribe FatFs-Status 1,
und der Swap blockierte den Wechsel. Ursache waren die zusätzlichen Kartenabfragen für die Statusdateien (ohne sie lief der Wechsel).
Warum es scheitert und ob es am Gerät vorkommt, ist offen. Der Patch prüft deshalb nur, wenn ein Journal existiert oder der Kopf unter
4096 Byte ist. Emulator-Fälle: Kopfschreiben auf 0 oder 512 Byte und Journal auf 0 oder 63 Byte begrenzt gibt Menü-Importfehler 4, der
Neustart gelingt auf Stock und Hacktribe, alter Index und Audio bleiben, der nächste WAV-Import gelingt, der neue Platz ist zunächst nicht
geladen. **offen:** echter Stromausfall, Reihenfolge der Sektorschreibvorgänge, defektes Dateisystem.

## 9. WRITE, Löschen und neue Aufnahme speichern

Entwurf, im Emulator geprüft, **am Gerät nicht gelaufen** (Quelle: Messung 2026-11-11/sample-aenderungen-speichern).

**Haken (offline gelesen):** Der native WRITE-Task-Haken `0xC0039708` sitzt nach dem logischen Platz und vor dem alten RAM-Schnappschuss
samt Flash-Vergleich. Der Bestätigungsschnappschuss liegt bei `0xC0345A2C` mit Gültigkeitsbyte `0xC0345A20`, Fehler gehen in das
vorhandene Status-Byte des Kommando-Tasks. Der bestätigte Löschhaken `0xC00395B8` entfernt den Eintrag aus dem Kartenindex samt
Katalogprüfung, dann das CPU-Löschen. Das EXIT einer unbestätigten Aufnahme verwirft nur die DSP-Zeile, keinen Karteneintrag. Die
Flash-Spiegel-Aufrufe werden auf diesen Wegen nicht benutzt, EXIT am Start behält den nativen Pfad.

**Zuordnung:** Der Karteneintrag braucht ein normalisiertes logisches Mapping, der native Bestätigungsschnappschuss das ursprüngliche
physische. Der Schnappschussleser hält beide Deskriptoren und streamt das ganze PCM in begrenzten Blöcken.

**Aufnahmeplatz:** Die Suche deckt Kartenindex, geladene native Zeilen und Aliase ab, prüft alle Zwischenzeilen des dreistufigen
Mappings und läuft nach dem DSP-Aufnahmestopp. Ein ausgelagertes Sample ist kein freier Platz. Ein eindeutig gemappter bestätigter
Schnappschuss kann den Schutz gegen Auslagern verlieren, eine gemeinsam benutzte physische Zeile bleibt geschützt. Ein bestätigtes
Löschen einer gemeinsam benutzten Zeile wird vor jeder Kartenänderung abgelehnt. Bei einem Schreibfehler bleibt das PCM als "geändert"
geschützt, WRITE in SAMPLE EDIT kann wiederholen, EXIT aus der Fehlermeldung ist kein Verwerfen. Fehlt die Bibliothek am Start, werden
Journal und Dateiabwesenheit unter demselben Dateibesitz geprüft, ein Fehler sperrt die Suche, die erste bestätigte Aufnahme legt die
Bibliothek an.

**Speicher und Besitz:** Der Schnappschuss nutzt den vorher abgelegten oberen Cache unter exklusivem Dateibesitz, ohne gemeinsames Handle
mit dem offenen Sample-Leser, mit derselben Eintragssperre wie der Kartenschreiber; ein aktiver Transport sperrt neue Speicheraufträge. Alte
Blöcke bleiben nach Ersetzen und Löschen in der Datei, der Platzindex entscheidet, welche Version zählt. Adressen siehe Abschnitt 6.

**Gerätetest (vorbereitet, nicht gelaufen):**

1. Zur installierten Basis passenden Testbuild und separate Testkarte verwenden. Ein geladenes User-Sample in SAMPLE EDIT ändern, WRITE
   drücken, nach dem Neustart Startpunkt, Name und Ton prüfen. EXIT ohne WRITE getrennt prüfen.
2. Audio In und Resampling jeweils mono und stereo aufnehmen, mit WRITE bestätigen, nach dem Neustart prüfen. Eine weitere Aufnahme mit
   EXIT verwerfen.
3. Ein entbehrliches Sample bestätigt löschen. Nach dem Neustart müssen der freie Platz und die übrigen Samples erhalten sein.
4. Auf der Testkarte Schreibfehler und Wiederanlauf prüfen. Bei fehlgeschlagenem Aufnahme-WRITE darf das PCM bis zur erfolgreichen
   Wiederholung nicht ausgelagert werden. Stromunterbrechung erst mit gesicherten Testdaten prüfen.

Der Nachweis für Aufnahme-DMA, Cachebesitz und Live-Wiedergabe bleibt davon getrennt.

## 10. Kategorie Wave und der HT-Lader

Warum der Bericht "HT liest `e2sSample.all` ohne Wave-Sample nicht" nicht reproduzierbar ist und was die Ursache sein dürfte
(hergeleitet, nicht bestätigt; die Datei aus dem Bericht ist weg): Der Originallader bricht die **ganze** Datei beim ersten Eintrag ab, dessen
Wellennummer (`esli[20:22]`) höchstens 49 ist (Oszillatorplatz). Ein Werkzeug, das statt der Kategorie das Nachbarfeld ändert, ergäbe genau
dieses Bild. BLECHs `SKIP_SITE`-Haken (abgelehnten Eintrag überspringen statt abbrechen) ist die Abhilfe.

- Jeder leere Platz bekommt beim Start die Kategorie 17 (HT: nach dem Laden von 499 Samples noch 226 Einträge, rot 79). "Kein Wave" gibt es
  also nur in der Datei, nie im RAM. Die Leerfunktion `0xC004DF90` schreibt 17 an `0xC004E178`; DELETE SAMPLE macht ein gelöschtes
  Sample deshalb wieder zu "Wave" (Aufrufer nicht bestätigt, drei Aufrufer `0xC004E360`, `0xC004F1A8`, `0xC004F5B4`).
- Der HT-Lader gleicht dem roten bis auf zwei Konstanten (`0xC004D97C` `bne` auf `nop`, Literale `0xC004E3BC`/`0xC004FAF8`: Platz- und
  Wellenzahl). Das Laden kopiert `esli[2:34]` ohne Kategorieprüfung in den Namenseintrag (memcpy `0xC004EE94`) und lehnt nur ab bei
  Wellennummer höchstens 49 (`cmp r3,#0x31` bei `0xC004EE04`), belegtem Platz oder zu großem Sample.
- Der Kategoriesprung des OSC-Rads (`0xC0040DD0`/`0xC0040E5C`) läuft, bis eine andere Kategorie erscheint; Oszillatoren 0 bis 17 haben
  immer andere Kategorien, also hängt es nie, auch wenn alle Samples gleich sind (Schleife `0xC0040E0C..0xC0040E48`, Umbruch bei `0x3E5`).

Quelle: Messung 2026-11-17/sample-kategorie-wave. Weiteres zu freien Plätzen: [HT-Oszillator-Plätze](../messungen/2026-11-08-ht-osc-freie-plaetze.md), zur Kategorie: [Sample-Kategorie](../messungen/2026-11-21-sample-kategorie.md).

## 11. Ordner Media

(Gemessen im Emulator, Quelle: Messung 2026-11-14/media-ordner; Näheres zur Ladeanimation in [ladeanimation.md](ladeanimation.md).) Das
IMPORT-Menü listet zuerst `Media/`, dann das Wurzelverzeichnis. `media_write` schreibt einen 62-Byte-Kopf und legt fehlende Ordner mit
`f_mkdir` an. `media_get` und `media_set` (`+4`/`+8`) lesen und schreiben Byte 14 über `f_open`, `f_lseek` und `f_write` von einem Byte,
ohne die Datei neu zu schreiben (das 2.02-FatFs hat kein `f_truncate`).

**Gerätetest (offen):**

1. Start mit und ohne `Media/loading.blla`.
2. Byte 14 aus dem Menü und aus der App setzen.
3. `Media/splash.bmp` mit einem anderen Bild.

Die 67 Schritte "page index N equals stock" in `splash_cases` brauchen eine Basis mit BLECH-Satz.

## 12. Entscheidungen zu mehr Sample-Speicher

(Quelle: Idee 25.) Kompression hilft dem Platz auf der Karte, nicht der Menge, die zugleich spielbar ist. Entwurf: rund 10 bis 12 MB je
Pattern, DMA bleibt zunächst aus. Die Ausstattung (24,7 MiB freies RAM, 11 MiB/s, Lader und Vorladen) steht schon in
[RAM-Task-Stack](../messungen/2026-10-24-ram-task-stack.md) und [Speicherbereiche](../speicherbereiche.md).
