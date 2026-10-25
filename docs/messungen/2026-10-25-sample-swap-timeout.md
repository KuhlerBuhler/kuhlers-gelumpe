# Sample-Swap: RAM-Besitz und ein begrenzter DSP-Transfer

Stand: 25.10.2026. Fortsetzung der [ersten Untersuchung](2026-10-25-sample-swap.md).
Beleg: `measure:2026-10-25/sample-swap-timeout`.

Umfang dieser Runde: Forschung und Timeout. Ein Sample-Cache und eine neue
Pattern-Umschaltung werden noch nicht aktiviert. **Gemessen** unterscheidet
Abbild, Emulator und Gerät; **hergeleitet** bezeichnet Schlussfolgerungen aus
diesen Befunden. **Offen** bleibt alles ohne passenden Versuch.

## Der Bereich von rund 47 MiB ist kein dauerhaft freier Speicher

**Gemessen am Abbild:** Der Puffergeber `0xC00369F0` gibt die Basis
`0xC0D3A940` zurück und meldet `0x01A00100` Byte Kapazität. Damit gehört
`[0xC0D3A940, 0xC273AA40)` weiterhin der Firmware. Die Umrechnung bleibt
`file = ram - 0xC0000000 + 0x100`, ausschließlich innerhalb der
2-MiB-Nutzlast eines VSB-Abbilds.

**Bereits gemessen im Emulator:** `IMPORT ALL PATTERN` schreibt bis
`0xC1122940` und damit in den Bereich oberhalb von `0xC1010000`, siehe
[RAM- und Stack-Messung](2026-10-24-ram-task-stack.md). Dass normales Spielen
dort keine Bytes ändert, hebt diesen Besitz nicht auf.

**Gemessen am Abbild:** 23 direkte Aufrufstellen des Puffergebers:

```text
C002E488 C002F390 C002F638 C00309AC C003100C C0031138
C00362B8 C00384EC C00387B0 C0039BFC C003A418 C003A930
C003AD14 C003B35C C003C1F8 C003C39C C004D258 C004D888
C004F75C C004F940 C0050278 C0056B74 C0076380
```

**Hergeleitet aus erneut gelesenem ARM-Code:** Bei `0xC004F940` wird die
Kapazität mit der doppelten Samplelänge verglichen und anschließend ab
Basis plus Fortschritt beschrieben. Bei `0xC0050278` wird die Basis global
gespeichert und die gesamte Quellgröße plus zwei Byte gegen die Kapazität
geprüft. `0xC0056B74` holt den Puffer; der Aufruf bei `0xC0056B88` löscht
seine gesamte gemeldete Kapazität. Die genaue UI-Zuordnung der letzten beiden
Wege bleibt offen. Schon diese Verbraucher verbieten die Annahme, nur die
ersten 64 KiB würden jemals benutzt.

**Hergeleitet:** Einen rund 47 MiB großen Cache braucht die Firmware mit
ausdrücklichem Besitzwechsel: Inhalt vor einem Fremdzugriff freigeben oder
sichern, aktive Sampledaten an einer sicheren Stelle halten, danach neu
laden. Alle Verbraucher und die rohen SysEx-Puffer müssten dabei berücksichtigt
werden. Den Puffergeber auf eine kleine Größe zu begrenzen wäre eine Änderung
der bestehenden Samplefunktionen und kein Nachweis freien RAMs.

Der obere Bereich `[0xC274F000, 0xC4000000)` mit rund 24,69 MiB bleibt ein
Kandidat. Startstack und Interrupt-/Leerlaufstack darunter bleiben ausgespart.
Vier getrennte Vorausladesätze mit je 12 MiB würden selbst 47 MiB ohne
Verwaltungsdaten überschreiten; Sample-Deduplizierung und der Fall eines
unvollständig haltbaren Vorausladesatzes gehören deshalb in einen späteren Bauplan.
Das ist keine neue Obergrenze für die Datei auf der Karte.

## Beobachtung einer Sitzung

Werkzeug: [highram_watch.py](../../tools/emu/highram_watch.py), eigene Firmware
außerhalb des Repositories, alle Samples und Dateien aus Formeln erzeugt.
Die Wache erfasst CPU-Schreiben und Lesen mit Phase und Programmzähler.
Nur durchlaufene Wege mit Abschlussnachweis dürfen als gemessen gelten.

**Gemessen im neuen vollständigen Emulatorlauf:** 232,95 Sekunden Gerätezeit,
16 Phasen, am Ende ausgeschaltet, keine Assertions. Eigene Hacktribe-Datei mit
SHA-256 `2df156c8fb7a1bddf7799111b40b04665c89e2341ad5dfaadad09ca92be3fc3f`,
40 berechnete Samples. Abschlussnachweise:

| Weg | Beobachteter Abschluss |
|---|---|
| IMPORT SAMPLE | Seite gefunden, danach Exportdatei um 60000 Byte größer als beim Start |
| EXPORT ALL SAMPLE | Datei mit 1713376 Byte entstanden, weiter 40 belegte Plätze |
| EXPORT ALL PATTERN | Datei mit 4161792 Byte entstanden |
| IMPORT ALL PATTERN | Seite gefunden, Kopie von 4096000 Byte bis `0xC1122940` im Arbeitspuffer und danach zurück in die Patternbank beobachtet |
| Danach Spielen, Wechsel und Ausschalten | Hauptbildschirm erreicht, keine Assertion, Firmware am Ende ausgeschaltet |

Die Kopie in den unteren Bereich kommt von `0xC0018178` und `0xC009BB2C`,
das anschließende Lesen von `0xC0009880` bis `0xC000989C` mit Rückkehr nach
`0xC00476E0`. Oberhalb von `0xC274EA3C` gab es in keiner Phase einen Lese-
oder Schreibzugriff. Der tiefste beobachtete neue Stackzugriff lag bei
`0xC274E92C`. Das bestätigt die früheren Befunde für diese Sitzung, keine
allgemeine Freigabe sämtlicher Modi.

**Gemessen im neuen Emulatorversuch:** Vier synthetische Samples geladen,
Sampling-Fenster geöffnet, zweimal REC, zehn Sekunden gewartet, STOP und EXIT.
Kein Assert, weiter vier Plätze. Die einzigen Puffergeberaufrufe stammen vom
Laden beim Start; nach dem Start wurde der beobachtete Bereich nicht benutzt.
Damit wurde die Oberfläche erreicht, aber keine Aufnahme abgeschlossen.

**Offen:** Sampling und Resampling mit echtem DSP-Audio und DMA. Der
[Emulator](../emulator.md) erzeugt beides nicht. Ein sichtbares Aufnahmefenster
ohne neue, wieder lesbare Aufnahme beweist die Speicherbelegung dieser Wege
nicht. Eine Freigabe für alle Modi liegt damit weiterhin nicht vor.

## Dateikopf und zukünftige Umschaltung

**Gemessen am Dateiformat:** Der Kopf von `e2sSample.all` enthält die Kennung
und 1020 Slot-Dateioffsets, keine Namen. Namen liegen in den `esli`-Blöcken
der einzelnen RIFF-Dateien. Die gewünschte Startstrategie braucht deshalb
keine neue Datei: erst den Kopf lesen, dann für das erste Pattern die
benötigten Metadaten und Audiodaten. Weitere Namen lassen sich bei Bedarf lesen.

**Hergeleitet und am ARM-Abbild gegengeprüft:** Ein Gate am Nummerngetter
bei `0xC005F1C4` allein genügt nicht. Die Engine folgt bei gleicher Nummer
weiter der Chain. Der normale Wechsel schreibt die neue Nummer zuerst bei
`0xC0079ACC`, der Chain-Wechsel nach Zielauflösung bei `0xC0079A74`.
Ein späteres Bereitschafts-Gate muss vor diesen Änderungen liegen und beim
Chain-Weg den bereits veränderten Wiederholungszähler erhalten. Erst den
Ladeauftrag zu blockieren wäre zu spät.

**Hergeleitet aus dem bestehenden BLECH-Code:** Sync-Gruppen übernehmen live
geänderte Sample-IDs nur bei einer Abweichung vom ursprünglichen Bankpattern.
Der Bedarf des Zielpatterns muss diese Regel berücksichtigen. Der Copy-Haken
bei `0xC004AC44` gehört bereits diesem Patch und darf keinen zweiten Besitzer
bekommen.

**Offen:** Vollständiger zentraler Bindepunkt für Sample-Auswahl, MIDI und
Slice-Wege sowie das Ende einer DSP-Stimme. Note-Off, Mute und Abwahl sind
dafür kein Nachweis. Der alte Samplebereich kann noch von einer Loop- oder
Release-Stimme gelesen werden. Vor einem Swap müssen solche Bereiche
nachweislich geschützt bleiben.

## Warum ein Timeout im vorhandenen Wrapper allein nicht reicht

**Hergeleitet aus dem ARM-Code:** `0xC0014284` ruft das unbegrenzte
`wai_sem(1)` bei `0xC0000D80` auf und ignoriert dessen Rückgabe. Auch die
unteren Transferfunktionen liefern keinen verwendbaren Fehlerstatus. Nach
dem Transfer überschreibt die Freigabe bei `0xC0000CA8` erneut die Rückgabe.
Ein Rücksprung aus einer inneren Warteschleife könnte daher fälschlich wie
ein erfolgreicher Transfer aussehen.

Die äußeren Wartestellen des Schreibwegs liegen bei `0xC00146F4`,
`0xC001470C`, `0xC00147A4` und `0xC001480C`, die entsprechenden Lesestellen
bei `0xC0014904`, `0xC001491C`, `0xC00149C4` und `0xC0014A2C`.
Nur den GPIO-Helfer zu ändern begrenzt die übrigen Statusschleifen nicht.

**Umsetzung:** Der neue Messpfad erhält einen eigenen DSP-Transport mit
ausdrücklichem Status. Er versucht Semaphore 1 einmal atomar zu übernehmen;
bei Belegung kommt er ohne Portzugriff mit `BUSY` zurück. IRQs bleiben nur
für diese kurze Übernahme gesperrt. Alle GPIO- und Statuswartezeiten erhalten
eine Gerätezeitgrenze und zusätzlich eine endliche Zahl von Prüfungen, damit
ein stillstehender Timer keinen Hänger erzeugt.

Ein Abbruch nach Beginn des Kommandokopfs hinterlässt einen unbekannten
Protokollzustand. Der neue Pfad verriegelt dann weitere eigene DSP-Transfers
bis zum Neustart. Er behauptet weder eine erfolgreiche Wiederherstellung
noch eine erfolgreiche Sample-Aktivierung. Die alten nativen Transferfunktionen
werden nicht global ersetzt; ihre übrigen Aufrufer behandeln weiterhin keinen
solchen Fehlerstatus. Das ist eine Grenze dieses vorbereitenden Patches.

### Aufruf und Grenzen der neuen API

Builder: [sample_swap_io.py](../../tools/patch/sample_swap_io.py).
Einstieg `transfer`, Register `r0 = 0` für Lesen oder `1` für Schreiben,
`r1 = ARM-Puffer`, `r2 = DSP-Byteoffset`, `r3 = Zahl der 16-Bit-Wörter`.
Die Rückgabe enthält in `r0` den Status und in `r1` die vollständig
übertragenen Wörter. Erfolgreich bedeutet Status null und die volle Wortzahl.

| Status | Bedeutung |
|---|---|
| 0 | vollständig übertragen |
| 1 | ungültige Länge, Ausrichtung oder Speichergrenzen |
| 2 | Semaphore belegt, kein Portzugriff |
| 3 | unzulässiger Task-/IRQ-Kontext |
| 4 | Timer nicht in der geprüften Konfiguration |
| 5 | Zeitgrenze oder Pollgrenze erreicht |
| 6 | verriegelter Transport oder fehlgeschlagene Freigabe |

Erlaubt sind ganze 16-Wort-Gruppen, höchstens 32768 Wörter, also 64 KiB pro
Aufruf. Der ARM-Puffer muss vollständig im oberen RAM liegen und darf weder
den ausgeführten Code noch seinen Zustand überschreiben. Der DSP-Bereich
muss hinter der Werksbank und vollständig innerhalb des aktuellen
Nutzerbereichs liegen. Dass dieser Bereich zum ausdrücklich freigegebenen
Sample gehört und nicht gespielt wird, muss der Aufrufer zusätzlich prüfen.

Die resident erzeugte Variante belegt 812 Byte ab `0xC019E000` und ein
Zustandswort bei `0xC019EFF0`. Der Builder verlangt gelöschten Speicher in
der gesamten reservierten Codefläche und prüft die verwendeten nativen
Routinen anhand ihrer SHA-256-Werte. Ein vorhandener BLECH-Patch darf keinen
zweiten Besitzer desselben Bereichs einführen. Es gibt keinen neuen Haken
in den normalen Start oder die nativen Transferfunktionen. Im regulären
BLECH-Patchsatz wird diese API noch nicht aktiviert.

Begrenzung: 100 ms nach Timer 3 und höchstens eine Million Prüfungen pro
Aufruf. IRQs sind bei der einmaligen Semaphore-Übernahme höchstens acht
ARM-Befehle lang gesperrt. Die geprüften aufrufbaren Versionen sind Stock
und Hacktribe des roten Samplers mit Firmware 2.02. Für den blauen Synth
fehlen die benötigten bestätigten Zuordnungen; er wird verweigert.

## Stand der Geräteprüfung

Die vorhandenen Messungen liegen in der [ersten Untersuchung](2026-10-25-sample-swap.md):
rund 11 MiB/s aus RAM bei gestopptem Gerät, rund 10 MiB/s beim Spielen,
rund 3 MiB/s Kartenlesen bei 12,5 MHz und rund 5,2 MiB/s bei 25 MHz.
Sie sind keine neuen Messwerte dieser Runde. Für die frühere Hörbeobachtung
liegt keine externe Aufnahme vor.

**Gemessen in dieser Runde, nur CPU-RAM:** Nach einer unerwarteten BLECH-Antwort
beim Lesen der Patternbank wurde der Versuch ohne DSP-Schreiben abgebrochen.
Acht gleichzeitige Sitzungen teilten sich die Umgebung. Nach einer ausdrücklich
gewünschten Pause von zehn Minuten liefen Discovery, INFO und die Transportabfrage
wieder durch; das Gerät meldete gestoppt. Das belegt keine exklusive Portnutzung.

Der neue endliche ARM-Scan las anschließend alle 4000 Parts der 250 Bankpattern
und die 16 Parts des aktuellen Patterns. Er meldete vollständig zurück und
stellte seine CPU-Arbeitsbereiche wieder her. Kein DSP-, Karten- oder
Taktzugriff. Platz 645 kommt in der Bank vor und ist deshalb kein allgemein
unbenutzter Testplatz. Unter den 499 Nutzerplätzen fand die konservative
Prüfung keinen geladenen Platz mit mindestens 1 KiB PCM, ausgerichtetem
DSP-Offset und ohne eine der geprüften ID-Referenzen. Deshalb wurde kein
neuer DSP-Test gestartet.

**Offen, ausdrücklich zurückgestellt:** Neue RAM-zu-DSP- und Karte-zu-DSP-
Zeiten mit der begrenzten API, sowohl gestoppt als auch beim Spielen, sowie
der Vergleich bei 12,5 und 25 MHz. Die Forschungs- und Timeout-Arbeit wird
ohne diese neuen Gerätemessungen abgeschlossen. High Speed mit 50 MHz bleibt
aus; dafür ist erst ein Versuch mit einer entbehrlichen microSD vorgesehen.
Kein Flash-Schreiben und keine Änderung an Samples auf der Karte.

### Vorbereiteter Gerätetest

Werkzeug: [sample_swap_paths.py](../../tools/device/sample_swap_paths.py).
Es läuft standardmäßig nur als Plan ohne MIDI. Der eigentliche Test braucht
eine eigene unveränderte Stock- oder Hacktribe-Datei, ein ausdrücklich
entbehrliches geladenes PCM16-Sample und einen allein nutzbaren MIDI-Port.
Zuerst 1 KiB gestoppt, danach bis 64 KiB, erst danach unter Wiedergabe mit
externer Aufnahme. Die folgenden Befehle sind vorbereitet, noch nicht als
erfolgreiche DSP-Messung dieser Runde ausgeführt:

```bash
python tools/device/sample_swap_paths.py --plan --kib 1
python tools/device/sample_swap_paths.py --execute --vsb "$OWN_VSB" --slot 999 --kib 1 --unused-confirmed --stopped-confirmed
python tools/device/sample_swap_paths.py --execute --vsb "$OWN_VSB" --slot 999 --kib 64 --unused-confirmed --stopped-confirmed --clock-mhz 12.5
python tools/device/sample_swap_paths.py --execute --vsb "$OWN_VSB" --slot 999 --kib 64 --unused-confirmed --stopped-confirmed --clock-mhz 25
```

Slot 999 ist eine vorgeschlagene Vorbereitung, kein vorhandener freigegebener
Messplatz. Für den Wiedergabeversuch ersetzt `--playback-confirmed` die
Stop-Bestätigung. `--json` kann den Ergebnisbericht außerhalb des Repositories
speichern; PCM-Daten werden weder ausgegeben noch gespeichert.

Der Test verlangt identische Import- und Zwischenindizes des Ziels, löst
zusätzlich alle verwendeten rohen IDs über Momentaufnahmen der drei Tabellen
auf und verweigert auch fremde IDs, die auf denselben physischen Platz zeigen.
Wegen der noch nicht vollständig geklärten ID-Normalisierung werden drei
benachbarte sichtbare Indizes berücksichtigt. Unklare Zuordnungen führen zum
Abbruch. Diese Prüfung ersetzt keine Klärung der Stimmenlebensdauer.

Zwei begrenzte DSP-Lesevorgänge sichern und vergleichen den Ausgangsinhalt.
Der Dateikopf und die RIFF-Blöcke bestimmen den PCM-Offset auf der Karte;
deren gelesener Anfang muss dem DSP-Inhalt entsprechen. Danach schreibt der
RAM-Versuch XOR-veränderte Bytes, liest sie zurück und stellt das Original
wieder her. Der Kartenversuch ersetzt erneut veränderte DSP-Bytes durch
Kartenlesen und DSP-Schreiben innerhalb eines EXEC. Öffnen und Positionieren
liegen außerhalb seiner Zeitmessung. Vorheriges Prüfen kann Kartencaches
erwärmen; der Versuch belegt keine Kaltstart-Latenz.

Nur bestätigte Rückgaben erlauben Aufräumen. Eine unbestätigte EXEC-Antwort
beendet jeden weiteren Zugriff; ein bestätigter DSP-Protokollfehler bleibt
bis zum Neustart verriegelt. Die nativen FatFs-Aufrufe haben weiterhin keinen
eigenen Timeout. Der Kartentakt wird nur bei ausdrücklichem Parameter geändert
und nach bestätigtem Abschluss wiederhergestellt. Das Werkzeug beweist keine
Fehlerbegrenzung der gesamten Firmware und keine reale DSP-Speichergrenze.

## Entscheidung nach dieser Forschung

**Hergeleitet:** Ein Cache kann Kartenlatenz vermeiden, aber die rund 47 MiB
sind ohne geregelten Besitzwechsel nicht nutzbar. Die neue API stellt für
spätere Aufrufer einen endlichen, prüfbaren DSP-Transfer bereit. Sie ist noch
kein Sample-Swap und behebt die alten unbegrenzten Aufrufer nicht global.

Weder Tausch mitten im Spielen noch Tausch am Patternwechsel sind damit
freigegeben. Für beide fehlen bestätigte Stimmenlebensdauer und vollständige
Bindung der Slots; für dauerhaften Cache zusätzlich die Aufnahme-/DMA-Wege.
Ein grundsätzlicher Ausschluss des Swaps folgt daraus nicht. Der nächste Bau
braucht zuerst eine Lösung für diese Besitzer und eine bestätigte Übertragung
mit der begrenzten API. Die neuen Gerätetests bleiben ausdrücklich offen.

## Prüfungen ohne Gerät

**Gemessen:** Alle neuen Testdaten entstehen im Test selbst. Die 14
ARM-/Builder-Prüfungen führen den assemblierten Transport mit simuliertem
Host-Port aus. Die 25 Prüfungen des Messwerkzeugs decken unter anderem
Treiber, Aliasauflösung, Abbruch und Wiederherstellung ab. Die gezielte
Node-Prüfung mit Dokumentation und Assemblerzuordnung bestand 21 Prüfungen.

| Vollständige Prüfung | Ergebnis |
|---|---|
| `GELUMPE_JOBS=2 npm test` | 1071 bestanden, 148 übersprungen, keine Fehler oder Abbrüche |
| `GELUMPE_JOBS=1 node --test --test-concurrency=1 "test/*.test.mjs"` | 1071 bestanden, 148 übersprungen, keine Fehler oder Abbrüche |
| `node --test --test-concurrency=1 --test-timeout=180000 "test/e2e/*.e2e.mjs"` | 190 bestanden, einer übersprungen, keine Fehler oder Abbrüche |
| `tools/emu/check.py`, optionaler API-Patch auf eigener Stock-Datei | 19 Prüfungen bestanden, darunter alle 15 Startszenarien |
| `tools/emu/check.py`, optionaler API-Patch auf eigener Hacktribe-Datei | 19 Prüfungen bestanden, darunter alle 15 Startszenarien |

Beide Firmware-Prüfungen liefen vollständig ohne Ausnahmen und ohne
`--quick`. Der vollständige BLECH-Satz lässt sich zusammen mit der optionalen
API auf beide eigenen Originaldateien anwenden. Ein zusätzlicher Test über
den echten JS-Patcher prüft die RAM-Deklarationen und weist einen zweiten
Besitzer des reservierten Code-Rests ab. Die ursprüngliche doppelte
Deklaration der geschriebenen Bereiche wurde damit erkannt und korrigiert.

Frühere Gesamtläufe mit hoher Parallelität trafen Compiler-, Socket- und
Browser-Zeitgrenzen; eine fehlende Zuordnung des neuen Unicorn-Tests wurde
im Teststarter korrigiert. Die vollständigen seriellen Läufe oben sind die
abschließende Kontrolle mit begrenzter Parallelität. Kein Produktlimit und
keine Testzeitgrenze wurde dafür gelockert. Diese Prüfungen belegen weder
Klang noch einen echten Host-Port oder abgeschlossene Aufnahmewege.

**Weiterhin offen:** Der abschließende Aufruf `npm run test:e2e` mit
Standardparallelität traf erneut das 180-Sekunden-Limit der Accessibility-
Datei. Deren vollständiger serieller Lauf besteht. Der npm-Unit-Aufruf oben
ist grün; eine Freigabe sämtlicher paralleler Standardprüfungen liegt nicht vor.
