# BLECH: Laufzeit und Platz der Patches

Stand 20.10.2026. **Gemessen im Emulator und an den erzeugten Patchdateien.**
Grundlage ist `feat/1.3-batch4`, Commit `8e235d6c95a76924f87efb3c433f57db6a138afa`.
Die Produktdateien wurden für diese Untersuchung nicht geändert. Drei kleine Änderungen an
der Plugin-Laufzeit wurden ausschließlich als getrennte Prototypen ausgeführt.
Die parallele Arbeit am Splash-Zweig ist unten als eigener Stand erfasst.

Ergebnis: Im gewöhnlichen Betrieb ist der zusätzliche ARM-Aufwand klein. Es gibt aber einen
deutlich teureren Fall bei den Pad-Farben, vermeidbare Arbeit beim Plugin-Laden und eine
knappe, stark verteilte Platzreserve auf den Samplern. Viele kleine Patches sind bereits
angemessen gebaut und rechtfertigen keinen eigenen Umbau.

Die [Messzahlen](2026-10-20-patch-performance-zahlen.json) enthalten die drei Speicherbilanzen,
die Profilläufe und die Prototypvergleiche. Originaldateien, erzeugte VSBs, vollständige
Prüfprotokolle und Versuchsskripte liegen ausschließlich im privaten Messpaket.

## Umfang und Methode

Die Auswahl erfolgt mit derselben Funktion `selectFor` wie im Patcher: 18 Patches auf
Hacktribe, 19 auf Korg rot und 12 auf dem Synth. Insgesamt sind es 19 verschiedene
Patchfamilien. Dateien, die in keinem gewählten Satz stehen, werden dadurch nicht zu einer
zusätzlichen Laufzeitlast gerechnet. Die drei vollständigen Sätze lassen sich auf die
jeweiligen Originaldateien anwenden.

Die Speicherrechnung verwendet die aufgelösten Schreibbereiche von `applyPatches`,
die `ram`-Deklarationen und die freigegebenen Bereiche aus
[patch-ram.mjs](../../data/patch-ram.mjs). Jeder dieser Bereiche wurde am jeweiligen
Original erneut auf ausschließlich FF geprüft. Überlappende Intervalle werden vereinigt.

Die Profile zählen ausgeführte ARM-Blöcke, jeweils Blockgröße geteilt durch vier. Alle
Vergleiche beginnen mit einer selbst erzeugten Patternbank, virtueller Karte und simuliertem
Netzteil. Gemessen werden je zwei Sekunden Gerätezeit: Stillstand, Wiedergabe eines Parts mit
einer Note auf jedem vierten Step, dieselbe Wiedergabe in KEYBOARD und ein besonderer Fall
in SEQUENCER. Dieser verwendet vier gleichbleibende Noten, Gate 127, 64 Steps und nur am
ersten Step einen Trigger. Der Transportzustand wird für jede Messung geprüft.

Die Prozentwerte unten sind **Modellwerte**: ARM-Befehle mal 5 ns geteilt durch Gerätezeit.
Sie sind keine gemessenen CPU-Prozente des echten Geräts. Der Emulator bildet weder reale
Cachekosten noch die DSP-Audioarbeit oder reale Kartenwartezeiten vollständig ab.
Die Befehlszählung an Blockgrenzen ist eine Näherung, kein Zähler für einzelne Hardwarezyklen.

## Platz

VSB-Dateien bleiben gleich groß. Entscheidend ist die Belegung der darin freigegebenen
Code- und RAM-Bereiche, nicht die Größe der JSON-Datei oder des Quelltexts.
Zusätzliche Bytes enthalten auch Tabellen und Plugin-Bytecode; sie sind nicht sämtlich ARM-Code.

| Build | Freigegebene Bereiche | Neue Code- und Datenbereiche | Reserviertes RAM | Ohne Belegung oder Reservierung | Größte einzelne Lücke |
|---|---:|---:|---:|---:|---:|
| Hacktribe | 572992 B | 82168 B | 448967 B | 41857 B | 3512 B |
| Korg rot | 572992 B | 82379 B | 448967 B | 41646 B | 3512 B |
| Synth | 911356 B | 70764 B | 397984 B | 442608 B | 329996 B |

Das sind auf den Samplern etwa 40,7 bis 40,9 KiB in vielen Lücken. Eine neue zusammenhängende
Routine mit beispielsweise 8 KiB passt dort nicht ohne Umverteilung hinein. Die Rechnung ist
eine Obergrenze für freie Belegung: Manche Lücken sind bewusst als Wachstumsspielraum für
benachbarte Codebereiche belassen. Ein Patch muss weiterhin seine FF-Prüfung und die
gemeinsame Überlappungsprüfung bestehen.

Der größte Posten ist `script-runtime`: 55360 neue Bytes auf den Samplern, davon 15476 Byte
für den eingebauten Blechy-Block, sowie 339648 Byte reserviertes RAM. Innerhalb des RAMs
beansprucht der Prüfer für Plugin-Bytecode **163840 Byte Arbeitsbereiche**, obwohl diese
beim gewöhnlichen Ausführen der Plugins nicht benötigt werden. Der Plugin-Pool selbst
hat weitere 131072 Byte. Pool, Prüfspeicher und Programmcode sind unterschiedliche Posten.

Die erste Laufzeit-Codefläche hat noch 2092 Byte vor der Menütabelle, die zweite 2816 Byte.
Zwischen Laufzeitdaten und Menüeinträgen liegen nur noch 48 Byte. Größere Ergänzungen brauchen
deshalb eine bewusste Speicherplanung. Die vorhandenen Bauprüfungen erkennen Überschreitungen.

## Gewöhnlicher Betrieb und lange Bindungen

| Fall | Hacktribe original / BLECH | Korg rot original / BLECH | Synth original / BLECH |
|---|---:|---:|---:|
| Stillstand | 4,018 / 4,143 % | 4,018 / 4,143 % | 4,997 / 5,064 % |
| Wiedergabe | 10,703 / 10,810 % | 10,703 / 10,811 % | 11,014 / 11,118 % |
| Wiedergabe, KEYBOARD | 10,680 / 11,028 % | 10,680 / 11,027 % | 10,997 / 11,328 % |
| Vier Noten mit langen Bindungen, SEQUENCER | 17,842 / 22,092 % | 17,839 / 22,086 % | 18,054 / 18,173 % |

**Gemessen:** Im letzten Fall steigt die gesamte gezählte ARM-Arbeit auf den Samplern um
etwa 23,8 Prozent gegenüber dem jeweiligen Original. Das sind etwa 4,25 Prozentpunkte im
Zeitmodell, keine 24 Prozent zusätzliche Hardwareauslastung. Auf dem Synth ist die neue
Bindungsauswertung nicht aktiv; dort bleibt der Unterschied klein.

Auf Hacktribe entfallen in diesem Fall während zwei Sekunden 19437547 gezählte Befehle auf
`pad-colors`. Die Eintritte werden zusätzlich gezählt: `pc_chord` 2737-mal,
`pch_tied` 290337-mal, `pc_follow` 288-mal und `pc_map` 2449-mal.
Ein normaler Wiedergabelauf liegt für denselben Patch bei 44502 Befehlen.

**Codebefund:** [pad_colors.py](../../tools/patch/pad_colors.py) ruft beim Senden einer
Pad-LED `pc_follow` auf. Das untersucht wiederum nachfolgende Pads; deren gebundene Noten
werden erneut rückwärts und vorwärts verfolgt. Die schon vorhandene Unterdrückung gleicher
LED-Nachrichten spart Übertragungen, verhindert aber diese wiederholte Berechnung nicht.

**Empfehlung mit höchster Priorität für den laufenden Betrieb:** Bindungsdaten einmal in
einem klar abgegrenzten LED-Update berechnen und die Sendefunktion auf das Ergebnis zugreifen
lassen. Ein Cache braucht eindeutige Invalidierung bei Part, Bar, Pattern, Noten, Gate,
Triggern und Voice-Zuweisung. Cursor und Helligkeit bleiben aktuelle LED-Werte. Die
Verantwortung gehört in die Pad-Darstellung; ein zusätzlicher versteckter Aufruf aus einem
fremden Patch wäre kein sauberer Ersatz. Dieser Umbau ist noch nicht implementiert oder
als Beschleunigung beziffert.

## Plugin-Laufzeit: drei getrennte Prototypen

### Prüfpuffer nur bis zur tatsächlichen Codelänge vorbereiten

In [script_vm.s](../../tools/patch/script_vm.s) leeren fünf Stellen Arbeitsbereiche immer
für `LIM_CODE`, also 16384 Byte. Das betrifft die Befehlsgrenzen und mehrere Zustände der
Funktions- und Ereignisprüfung. Auch ein kleines LED-Plugin bezahlt diese Arbeit mehrfach.

Der Prototyp ersetzt an diesen fünf Stellen die maximale durch die bereits geprüfte
tatsächliche Codelänge `RT_CODESIZE`. Die reservierten Bereiche bleiben unverändert.
Beim nativen Laden aller zehn Presets sinkt die Zählung von **15148903 auf 3558598
ARM-Befehle**, also um 76,5 Prozent. Der VM-Block wird dabei 12 Byte kleiner.

**Grenze:** Das ist das Prüfen und Eintragen bereits im RAM liegender Blöcke. SD-Lesen,
gesamte Einschaltzeit und reale Kartenwartezeiten sind damit nicht um 76,5 Prozent verkürzt.
Die 16 vorhandenen nativen VM-Prüfungen bestehen auch mit diesem Prototyp, einschließlich
ungültiger Programme, atomarem Ladefehler, Poolgrenzen, Registererhalt und Zeitlimit.

### Operanden ohne zusätzlichen Registerstapel decodieren

`decode_operands` sichert für jeden Aufruf Register, die durch eine reine Blattroutine
ersetzt werden können. Der Prototyp verwendet ausschließlich die freien Aufrufregister;
die Formate und alle bestehenden Größen-, Stack-, Fuel- und Zeitprüfungen bleiben erhalten.
Der VM-Block wird 24 Byte kleiner.

1224 Vergleichsvektoren je Fassung decken alle 34 Opcodes, beide Operanden, Grenzwerte und
vier Byteausrichtungen ab. Ergebnisse, geschützte Register und Eingabespeicher stimmen
überein. Auch die 16 nativen VM-Prüfungen bestehen.

| Plugin, jeweils zwei Sekunden Laufzeit | Weniger Befehle innerhalb der Plugin-Laufzeit |
|---|---:|
| Mandelbrot | 4,11 % |
| Life | 4,25 % |
| Pong | 1,97 % |

Das sind Gewinne für den ganzen gemessenen Laufzeitbereich, nicht nur für den Decoder.
Andere Teile des Geräts sind nicht im Nenner dieser drei Werte enthalten.

### ARM-MUL statt Bit-Schleife

[script_vm.py](../../tools/patch/script_vm.py) erzeugt für die Plugin-Multiplikation noch
eine Schleife über die Bits des zweiten Faktors. Der vorhandene Assembler unterstützt
bereits `mul`, das an anderen Stellen der Laufzeit verwendet wird.

Der Prototyp ersetzt diese Schleife durch `mul r3, r0, r1` und `mov r0, r3`.
2225 Vergleichspaare je Fassung, einschließlich negativer Werte und 32-Bit-Überläufe,
liefern dasselbe Ergebnis. Der kleine vollständige Testhandler braucht durchschnittlich
559 statt 707,44 ARM-Befehle; der VM-Block wird 20 Byte kleiner. Die 16 nativen
VM-Prüfungen bestehen ebenfalls.

Im vollständigen Mandelbrot-Ausschnitt spart dieser einzelne Eingriff jedoch nur **1,09
Prozent** der Laufzeitbefehle, bei Life 0,12 und bei Pong 0,03 Prozent. Das ist ein guter
kleiner Eingriff, aber kein Beleg für einen wesentlich schnelleren Bildaufbau.

### Warum diese Änderungen das Bild noch nicht schneller fertigstellen

Bei beiden im ganzen Satz ausgeführten Prototypen sind nach jeweils 50 Frames die
Bildprüfsummen und die erfassten Fortschrittswerte von Mandelbrot, Life und Pong identisch.
Kein Pluginfehler und keine Firmware-Assertion. Mandelbrot begrenzt seine Arbeit weiterhin
über `BUDGET` und `used`; Life verteilt Rechnen und Zeichnen weiterhin auf seine Frames.

Weniger ARM-Arbeit schafft Reserve. Für mehr Bildfortschritt pro Frame muss anschließend
das Arbeitsbudget anhand der schnelleren Laufzeit neu geprüft werden. Spieltempo,
Reaktionszeit und Schutz vor zu langen Handlern bleiben eigene Anforderungen.
Die drei Einzeleinsparungen dürfen nicht ungeprüft addiert werden.

## Weitere Platzgewinne

### SysEx-Puffer: 19 KiB ohne kleinere Nachrichten

[blech_sysex.py](../../tools/patch/blech_sysex.py) reserviert 57088 Byte für `BUF` bis
`BUF_END`. Die eigene Bauprüfung verlangt für 32768 Nutzbytes einschließlich Packreserve
37544 Byte. Aufgerundet auf 37632 Byte, mit Ende `0xC019A400`, würde der belegte Bereich
**19456 Byte zusammenhängend** vor dem unveränderten Dateiarbeitsbereich freigeben.
Die maximale Nachrichtengröße müsste dafür nicht sinken.

Die native Packroutine wurde mit dem bisherigen und diesem kleineren Bereich verglichen:
80 Fälle, 16- und 20-Byte-Antwortköpfe, verschiedene Restlängen und Datenblöcke bis 32768
Byte. Alle Ausgabebytes und die Speicherwächter vor und hinter den Bereichen stimmen.

**Noch nicht freigegeben:** Das prüft ausschließlich die Packroutine mit überlappenden
Ein- und Ausgaben. Vor einer Änderung müssen vollständige READ, WRITE, FLASH und FILE,
kurze Antworten, Fehlerpfade und beide MIDI-Anschlüsse auf allen Builds geprüft werden.
Der Gewinn steht im bestehenden Satz noch nicht zur Verfügung.

### Größere Neuordnung erst mit festgelegten Lebenszeiten

Die 160 KiB Prüfarbeitsbereiche der VM sind ein größerer langfristiger Kandidat. Sie
dürfen nicht einfach auf Variablen, laufende Plugins, Dateipuffer oder die doppelte
Speicherdatei gelegt werden. Nötig wäre ein ausdrücklich besessener temporärer Bereich
oder eine andere Prüfdatenstruktur, mit abgesichertem Fehlerfall während des Imports.
Eine konkrete freigebbare Größe wurde dafür noch nicht bewiesen.

## Bewertung jeder aktiven Patchfamilie

Neue Bytes und RAM beziehen sich in dieser Tabelle auf Korg rot im Grundstand; die
genauen Fassungen aller drei Builds stehen in den Messzahlen. Neue Bytes meinen Code
und Daten innerhalb der freien Bereiche. Änderungen vorhandener Tabellen oder Bilder
sind dadurch nicht fälschlich neuer Programmcode.

| Patch | Neue Bytes / RAM | Befund und Empfehlung |
|---|---:|---|
| `splash-editor` | 3392 / 4096 | Start und bewusste Editor-/Importaktion. Bereits wortweise Bildkopie. Belassen; kein gemessener Engpass im Normalbetrieb. |
| `mfx-switch` | 1928 / 352 | Frühe Rückkehr, wenn MFX 2 aus ist; Typwechsel bei Bedarf und gedrosselte LED-Auffrischung. Belassen. |
| `pattern-switch` | 2324 / 827 | Synchronisierte Übernahme erfolgt beim Patternladen; der normale Tick ist klein. Der Vergleich des ungespeicherten Patterns ist an Bedienung gebunden. Keinen unvollständigen Dirty-Merker als Ersatz einführen. |
| `tap-motion` | 1336 / 64 | Der ONCE-Durchlauf endet sofort ohne markierte Lanes. 17 Lanes werden erst bei Bedarf betrachtet. Belassen. |
| `note-assistant` | 1752 / 64 | Hinweise werden bei neuen Noten berechnet und LED-Werte vor dem Senden verglichen. Die Modulo-12-Schleife ist ein kleiner weiterer Kandidat, kein nachgewiesener Hauptengpass. |
| `dice` | 1216 / 64 | Nur bei Tasteneingabe; bereits native Multiplikationen und begrenzte Stepzahl. Kein laufender Dienst nur für diese Funktion. Belassen. |
| `pad-colors` | 2684 / 64 | Wichtigster belegter Engpass im laufenden Betrieb: wiederholte TIE-Auswertung durch `pc_follow`. Update und Versand trennen oder sauber zwischenspeichern. |
| `ifx-idle` | 484 / 64 | Betrachtet 16 Parts alle 40 ms, Effektwechsel nur an Zustandsübergängen. Kleiner ARM-Aufwand; echte DSP-Ersparnis wurde hier nicht gemessen. Belassen. |
| `load-bar` | 2444 / 64 | Im Grundstand nur während des Sampleladens aktiv, danach wenige Guard-Befehle. Die neue Ladeanimation und der zusätzliche Bildschirm-Look sind getrennt zu bewerten, siehe Nachtrag. |
| `sample-errors` | 852 / 256 | Fehlerklassifikation während des Ladens, kein dauernder Suchlauf. Prüfungen und verlässlichen Abbruch erhalten. Belassen. |
| `script-runtime` | 55360 / 339648 | Gemessene Kandidaten bei Laden, Decoder und MUL. Im Stillstand zusätzlich 88 LED-Plätze und 16 Mutes pro Frame; deutlich kleinere Last als der TIE-Fall. |
| `blechtribe` | 0 / 0 | Ersetzt vorhandene Ordnertexte, keine zusätzliche Schleife. Keine sinnvolle Laufzeitoptimierung. |
| `splash` | 0 / 0 | Ersetzt ein vorhandenes 1024-Byte-Bild. Kein neuer Code. |
| `blech-theme` | 0 / 0 | Ersetzt vorhandene Texte, Fonts und Bilder. Die Wirkung eines zusätzlichen Zeichenfilters gehört nicht in diese statische Größe. |
| `preset-tables` | 1024 / 31392 | Tabellenindirektion bleibt dieselbe; Reserven für weitere Presets und Reglerzustände. Verkleinern würde eine zugesagte Kapazität betreffen. Belassen. |
| `synth-filters` | 191 / 0 | Nur Korg rot; bereits kleine konstante Nachschlagetabelle für die Tasten. Belassen. |
| `power-off` | 1244 / 0 | Bild nur während der vorhandenen Ausschaltwartezeit. Kein gewöhnlicher Laufzeitgewinn durch weiteres Kürzen. |
| `doom-loader` | 2740 / 10572 | Im Normalstart kurzer Tastentest, SD-Laden und SHA nur im Doom-Modus. Externe Doom-Engine ist nicht Bestandteil dieser VSB-Codegröße. Keine Aussage über den noch offenen echten Doom-Startfehler. |
| `blech-sysex` | 3408 / 61440 | Auf Anfragen begrenzt; CRC und Bereichsprüfung erhalten. Nibble-CRC ist platzsparend. Bessere konkrete Platzchance ist der oben geprüfte Bufferzuschnitt. |

Zur Laufzeit gehört außerdem die Anzeige ungespeicherter Änderungen in
[script_shortcuts.s](../../tools/patch/script_shortcuts.s). Sie vergleicht das Pattern
bereits nur alle acht Frames und verlässt den Vergleich beim ersten Unterschied.
Ein neuer Dirty-Merker müsste auch Sequencer-, MIDI- und alle nativen Editierwege sicher
erfassen. Für den hier kleinen gemessenen Aufwand ist das kein vorrangiger Umbau.

Die Display-API arbeitet bei Rechtecken bereits mit Seitenmasken und Bitmaps mit
Byte-Spalten, nicht durchgehend mit einzelnen Pixelaufrufen. Geschlossene Apps erhalten
keine `frame`-Handler. Diese vorhandenen Optimierungen sollten erhalten bleiben.

## Nachtrag zum parallelen Splash-Zweig

`feat/1.3-splash-directions` enthält den Grundstand bereits und ergänzt in Commit
`d0510b9cccc3938783e74e945024a80ef3c72963` die neue Ladeanimation und das Tuben-Startbild.
Darauf liegen uncommittete Änderungen am allgemeinen Bildschirm-Look. Für diesen Nachtrag
wurden ausschließlich die erzeugten Patchdateien und das Hook-Verzeichnis in eine private
Kopie übernommen. Ihre Prüfsummen stehen in den Messzahlen. Der nur lesende Neuaufbau des
Ladepatchs aus dem dortigen Generator stimmt mit der kopierten Patchdatei überein.
Keine Datei dieses fremden Arbeitsstands wurde verändert.

Mit diesem Snapshot sinkt die nicht belegte oder reservierte Fläche auf **34413 Byte bei
Hacktribe und 34202 Byte bei Korg rot**. Die größten Lücken betragen 3328 beziehungsweise
3224 Byte. Für das zusätzliche Aussehen kommen zwei Bildpuffer und Boxdaten hinzu, zusammen
2688 Byte RAM. Beim Synth bleibt die Flächenbilanz gleich; er bekommt diesen Lade-/Lookpatch
nicht. Der Snapshot ist ein eigener Prüfgegenstand und keine Freigabe späterer Änderungen.

Der allgemeine Look speichert den Rohframe zwischen und zeichnet bei gleichem Inhalt
nicht neu. Auf Hacktribe wurde derselbe Snapshot mit DISPLAY INVERT an und aus geprüft;
der neue Look ist an die eingeschaltete Invertierung gebunden.

| Fall, je zwei Sekunden | Look an / aus, Modellwert |
|---|---:|
| Stillstand | 4,139 / 4,114 % |
| Wiedergabe | 10,805 / 10,781 % |
| Wiedergabe, KEYBOARD | 11,023 / 10,998 % |
| Lange Bindungen | 22,088 / 22,066 % |
| BLECH-Menü | 4,839 / 4,757 % |

Der gemessene Mehrbedarf liegt in diesen Fällen zwischen etwa 0,02 und 0,08 Prozentpunkten
des Modells. **Kein vorrangiger Laufzeitengpass in diesen geprüften Ansichten.** Ein
zusätzlicher Durchlauf über alle Menü- und Fensterarten ist damit nicht ersetzt.

Für das Laden wurde außerdem das vorhandene Werkzeug
[cpu_profile.py](../../tools/emu/cpu_profile.py) verwendet: eigene Bank mit 20 Samples,
insgesamt 20 Sekunden PCM-Audio, Dateigröße 1948736 Byte.

| Firmware | ARM-Befehle je Dateibyte | Beschäftigt im Modell |
|---|---:|---:|
| Hacktribe original | 71,3 | 18,3 % |
| BLECH-Grundstand | 71,2 | 18,2 % |
| Splash-/Look-Snapshot | 71,5 | 18,3 % |

Die neue Animation erzeugt in diesem Versuch keinen großen zusätzlichen ARM-Aufwand beim
Laden. Die angezeigten Loaderzeiten von rund 3,8 Sekunden stammen vom festen Kartenraster
des Emulators und sind kein Nachweis einer schnelleren oder gleich schnellen echten SD-Karte.

## Weitere Kandidaten ohne bezifferten Gewinn

- `mem_fill` füllt weiterhin byteweise. Ein Wortpfad für ausgerichtete Bereiche könnte
  auch Initialisierung und größere Variablenbereiche beschleunigen. Vorher sind ungerade
  Längen, Startausrichtung und Registervertrag zu prüfen.
- `signed_divide` verarbeitet DIV und MOD mit 32 Bitschritten. Sichere Sonderfälle wie
  Zweierpotenzen sind prüfbar. Ein einfaches Ersetzen von Modulo durch AND ist bei
  negativen Zahlen nicht allgemein gleichwertig.
- Die 88 LED-Plätze werden auch ohne neue LED-Anfragen vorbereitet und durchsucht.
  Ein expliziter Pending-Zähler könnte Arbeit sparen, braucht aber korrekte Behandlung
  von Rückstau und Zustellstatus. Die gemessene Last ist hier klein.
- Eine größere CRC-Tabelle würde zusätzliche Daten brauchen. Zuerst müsste ein
  vollständiger Transfer zeigen, dass die CRC und nicht MIDI-/USB-Wartezeit begrenzt.
  Die vorhandenen CRC- und Bereichsprüfungen werden dadurch nicht entbehrlich.

## Grenzen und Reihenfolge

1. **Pad-Darstellung:** größter belegter zusätzlicher Aufwand bei laufender Musik.
   Vor dem Umbau eine eindeutige Update-/Cache-Verantwortung festlegen; Noten-, Gate-,
   Trigger- und Patternänderungen sowie beide Sampler und Synth dagegen prüfen.
2. **Plugin-Lader und Decoder:** kleine, bereits isoliert geprüfte Änderungen an der
   richtigen Quelle. Danach zusammen mit MUL neu vermessen und den vollständigen
   Firmware-Prüflauf auf allen drei Builds ausführen. Die bisherigen Einzelläufe sind
   keine kombinierte Freigabe.
3. **SysEx-Bereich verkleinern:** konkrete 19-KiB-Chance; vor Nutzung vollständige
   Protokoll- und Grenzprüfungen, kein Reduzieren der maximalen Blockgröße als Abkürzung.
4. **Größere Speicherneuordnung und höheres Plugin-Arbeitsbudget:** eigener Entwurf,
   anschließend Gerätezeit, Bedienbarkeit und reale Audio-/MIDI-Wirkung messen.

Es wurde kein Gerät angesprochen und keine Firmware installiert. Die zuvor verschobenen
Gerätetests bleiben verschoben. Die Emulatorbefunde erlauben keine Aussage über reale
Polyphoniegewinne, Klang oder die verfügbare Laufzeitreserve des DSP.

## Prüfstand dieser Untersuchung

| Prüfung | Ergebnis |
|---|---|
| Vollständige Patchauswahl auf den drei Originaldateien | Grundstand und Splash-Snapshot lassen sich jeweils anwenden |
| Laufzeitprofile | 62 Abschnitte ohne Firmware-Assertion; einschließlich der beiden Prototypen und des Look-Vergleichs |
| Vorhandene native VM-Prüfungen | jeweils 16 von 16 für begrenztes Leeren, Decoder und MUL |
| MUL-Gleichheit | 2225 Zahlenpaare je Fassung |
| Decoder-Gleichheit | 1224 Vektoren je Fassung, Ergebnisse und Speicherwächter gleich |
| Kleinerer SysEx-Puffer | 80 native Packfälle bestanden, vollständiges Protokoll noch offen |
| `npm test -- --test-concurrency=2` | 1070 Tests, 925 bestanden, 2 fehlgeschlagen, 143 übersprungen |
| `npm run test:e2e` | 163 Tests, 162 bestanden, 0 fehlgeschlagen, 1 übersprungen |
| Dokumentationsprüfung | 9 von 9 bestanden |

Die zwei Unit-Fehler sind im unveränderten Ausgangsstand reproduzierbar:
`note-assistant.test.mjs` und `pattern-switch.test.mjs` suchen beim Speichern der Flags
einen bestimmten Textablauf bis `str r0, [r7, #12]`. Der aktuelle Code sammelt die Flags
zwischenzeitlich in `r10` und speichert diesen. Das erklärt die Textprüfungsfehler; eine
gesonderte Funktionsprüfung der gesamten Einstellungssicherung gehört nicht zu diesem Audit.
Der Unit-Gesamtlauf wird deshalb ausdrücklich nicht als grün bezeichnet.

Beim ersten Browserlauf fehlte im übernommenen Abhängigkeitsverzeichnis
`@axe-core/playwright`. Nach eigener Installation der Abhängigkeiten aus `package-lock.json` im
Audit-Arbeitsstand besteht der vollständige Browserlauf. Produktcode wurde dafür nicht geändert.
Die vollständigen Logs bleiben im privaten Messpaket.

Kein Patch wurde als optimierte Produktfassung gespeichert. Der komplette `check.py`-Satz
wurde für diese Untersuchung nicht als neue Freigabe ausgeführt. Vor dem Einbau bleiben
kombinierte Regression, alle drei Firmwarebuilds und die oben genannten Geräteprüfungen nötig.
