# Sample-Swap: physische Belegungen gegen ungesicherte Änderungen schützen

Stand: 05.11.2026. **Gemessen im ARM-Modell und im Emulator** mit erzeugten
Samples. Kein Gerät, Klang oder DMA. Ergänzung zur
[Schutzprüfung](2026-10-31-sample-swap-schutz-review.md) und zum
[verbundenen Ausgangsstand](2026-11-04-sample-swap-integration.md).

## Gemessen: Wiedergabepunkte und gemeinsame Aliase

Die Signatur umfasst die Metadatenzeile, die 16 Byte aus `PLAYBACK` und die
32 Byte der logischen Namenszeile. Die bisherige Kombination aus XOR und
Addition konnte einzelne Änderungen um 256 unverändert abbilden. Der
wortweise FNV-Durchlauf erkennt die vier geprüften Wiedergabefelder.
Eine Signatur allein ist weiterhin kein Nachweis einer gespeicherten PCM.

Erkannte Änderungen setzen eine bleibende Marke der physischen Belegung.
Ein sauberer Alias kann dadurch keinen veränderten Alias verdrängen. Die
Marke bleibt auch nach Rückkehr zu gleichen Metadaten erhalten. Andere
saubere Belegungen bleiben nutzbar.

Die neuen Modellfälle stehen in `tools/patch/test_sample_protection.py`.
Sie prüfen auch einen nativen Reservierungsaufruf mit unveränderten
Metadaten und gleicher PCM-Länge: Trotz gleicher Signatur bleibt die
physische Belegung geschützt.

## Gemessen: begrenzter Schutzdurchlauf und kurze Freigabe

Ein Schutzdurchlauf betrachtet jeden der 499 Nutzerplätze höchstens einmal.
Mehrere Löschungen innerhalb derselben Platzsuche verwenden diesen Stand
weiter. Der Modellfall mit vier Verdrängungen berechnet vier Signaturen,
nicht vier vollständige Tabellenläufe.

Der Durchlauf prüft zwischen Zeilen das bestehende 15-ms-Schrittbudget.
Im Modell wird dieses Budget nach jeweils vier Signaturen erreicht.
Alle 499 Zeilen werden über mehrere Schritte ohne erneutes Hashen bearbeitet.
Signaturen werden mit freien Interrupts berechnet. Bitmap-Änderungen und
die letzte Besitzprüfung vor dem CPU-Löschen sind kurze kritische Abschnitte.
Ein bereits maskierter Aufruf beginnt keinen neuen Schutzdurchlauf.

Ein langsamer Kartenlesezugriff darf die Suche nicht endlos vertagen.
Freier DSP-Platz benötigt keinen Schutzscan. Eine bereits vertagte Suche
wird vor dem nächsten Metadatenlesen fortgesetzt. Zwei zusätzliche
Modellfälle prüfen das mit einem Kartenlesen, das jeweils das gesamte
Schrittbudget verbraucht.

Ein Mutationszähler und die Cache-Generation entwerten vorbereitete
Entscheidungen. Eine spätere Mutation verhindert das Löschen. Überlauf
des Zählers sperrt die Freigabe bis zur Initialisierung einer neuen Sammlung.
Dies ist eine Prüfung des kooperativen Zeitbudgets, keine Zeitmessung am Gerät.

## Hergeleitet: native Änderungsgrenzen

Die Funktionen und ihre vollständigen geprüften Spans sind in beiden roten
Originalen identisch. Der Builder prüft ihre SHA256 vor dem Patchen.

| Funktion | Einstieg | Parameter der nativen Funktion |
|---|---|---|
| Löschen | `0xC004E558` | roher Importschlüssel |
| Reservieren | `0xC004EDF0` | Deskriptor, logischer Slot bei `+0` |
| Startpunkt | `0xC004E63C` | roher Importschlüssel, vorzeichenbehaftetes Frame-Delta |
| Endpunkt | `0xC004E710` | ebenso |
| Loopstart | `0xC004E7E8` | ebenso |
| Umbenennen | `0xC004E8C8` | roher Importschlüssel, Zeiger auf 16 Namensbytes |
| Slice-Daten leeren | `0xC004E93C` | roher Importschlüssel |
| Deskriptor zurücknehmen | `0xC004EFF4` | Deskriptor, logischer Slot bei `+0` |

Die Wiedergabepunkt-Funktionen dienen mit Delta null auch als Getter. Ein
solcher Aufruf setzt keine Marke. Ein Delta ungleich null kann an einer
Grenze ohne Wertänderung enden; der Schutz bleibt dann vorsichtig gesetzt.

Ein roher Importschlüssel 600 entspricht der gespeicherten Importnummer 650.
Der Adapter berücksichtigt diese Verschiebung vor `physical_import`.
Der eigene Swap-Publish und das eigene Löschen umgehen den Mutationsmarker
nur an ihren exakten Rücksprungadressen, nicht über das globale `INSTEP`.

## Gemessen und hergeleitet: geprüfter Ladeabschluss

Der Sammlungslader ruft den Parser bei `0xC00366FC` mit angefordertem Slot
minus eins auf. Der erwartete logische Slot stammt daher aus seinem
Dateikopf und Iterator, wie beim bestehenden Skip-Haken. Ein erfolgreicher
Parser muss genau diesen Slot im Deskriptor zurückgeben.

Ein Prüfwert liegt im eigenen Stackrahmen dieses Aufrufs. Der native
Reservierungsaufruf bei `0xC003629C` aktualisiert ausschließlich diesen
Prüfwert. Eine fremde Mutation ersetzt ihn nicht. Nach erfolgreichem
Dateiladen wird die Signatur nur bei unveränderter Revision bestätigt.
Der globale Abschluss markiert keine Zeilen pauschal als sauber.

Der originale Parserrahmen umfasst `0x4F0` Byte. Die gespeicherte
Aufruferadresse liegt bei `sp + 0x4EC`. Die vorhandene Cursor-Erweiterung
besitzt einen zusätzlichen 24-Byte-Rahmen. Beide Varianten werden geprüft;
die Erweiterung wird nur anhand ihres exakten eigenen Einstiegscodes und
der Aufruferadresse erkannt. Ein unbekannter Aufbau bestätigt keine Zeile.

Auch ein Swap-Publish übergibt seine unter IRQ-Schutz erfasste Revision
an die anschließende Signaturberechnung. Eine Mutation oder ein erschöpfter
Zähler während dieser Berechnung kann keine saubere Marke erzeugen.
Die reine Part-Aktualisierung bestätigt selbst keine Dateiversion.

## Gemessen: native Gegenproben auf beiden roten Builds

`tools/emu/sample_protection_cases.py` ist in die vollständigen Swap-Fälle
eingehängt. Drei neue Fälle bestehen auf Stock und Hacktribe:

- Ein tatsächlich geladener Slot ist zunächst verdrängbar. Der native
  Startpunkt-Getter lässt ihn sauber; das native Delta eins schützt ihn.
- Ein nativer Import ersetzt 40000 Byte PCM an derselben DSP-Adresse.
  Im Modell zurückgesetzte Namen, Metadaten und Wiedergabepunkte erzeugen
  wieder die gleiche Signatur; der Slot bleibt trotzdem geschützt.
- Eine kleine Sammlung startet mit Modus 0. Der echte Kartenschreiber
  vergrößert sie über das Budget, `catalogue_end` aktiviert Modus 1.
  Der unveränderte zweite Slot bleibt mit seiner echten Startmarke verdrängbar.

Die beiden Wiedergabe- beziehungsweise Importfälle lassen die Bibliothek
auf der Karte bytegleich. Der dritte Fall ändert sie absichtlich über den
journalisierten Schreiber. Der zweite Fall kennzeichnet die Rücksetzung
der CPU-Tabellen ausdrücklich als Modellannahme.

## Hergeleitet: Code und Zustandsflächen

Der zusätzliche Code liegt im geprüften FF-Bereich `0xC019C400` bis
`0xC019E000`, Ende ausschließlich. Der Standardbereich des separaten
DSP-Transportbausteins beginnt dahinter und bleibt frei. Der Builder prüft beide Originale;
das gesamte Patchset prüft die übrigen Belegungen. Es gilt weiterhin
`file = ram - 0xC0000000 + 0x100`.

Die 160 Byte Schutzstatus liegen bei `0xC276CE80` bis `0xC276CF20`.
Das ist der freie Rest hinter den 1000 Cache-Indexrecords, vor `LIST`
bei `0xC276D000`. `cache_reset` überschreibt diesen Rest nicht. Es wird
keine weitere PCM-Cachefläche belegt. Dies ersetzt keinen Nachweis der
RAM-Freiheit während Sampling, Resampling oder DMA.

## Gemessen: Prüfungen vor den direkten Tune- und Pegelmarken

Die abschließende Prüfung des unveränderten Laufzeitstands besteht:

| Prüfung | Ergebnis |
|---|---|
| `npm test` | 1366 bestanden, 161 ausgelassen, kein Fehler |
| `npm run test:e2e` | 285 bestanden, 1 ausgelassen, kein Fehler |
| Gezielte native Prüfung Stock | 57 bestanden, keine Auslassung |
| Gezielte native Prüfung Hacktribe | 57 bestanden, keine Auslassung |

Die nativen Fälle umfassen Start, Patternwechsel, Chain, Verdrängung,
Part-Auswahl, Aliase, Stimmen, Kopierunterbrechungen, Import und Snapshot.
Die angepasste Part-Aktualisierungsprobe bestätigt keine Dateiversion;
ihre Swap-Aktivierung und ihr Stimmenabschluss bleiben Modellannahmen.
Beide roten Originale erzeugen denselben Patch; das gesamte Patchset
besteht die Hook- und Speicherprüfung. Eine zusätzliche Codeprüfung findet
nach den Korrekturen keinen weiteren konkreten Fehler im geprüften Umfang.

## Offen

Die vollständige Verifikation aller Originale und die Gerätefreigabe sind
nicht abgeschlossen; `verified.json` bleibt unverändert. Die ausgelassenen
Standardtests zählen nicht als Firmwareprüfung.

Die statische Nachprüfung beider Originale belegt den folgenden zusätzlichen
Schreibpfad, der noch nicht in den Schutz eingebunden ist. Tune und Pegel
sind inzwischen an ihren direkten Schreibstellen geschützt, siehe unten:

| Funktion | Einstieg | Schreibgrenze |
|---|---|---|
| PCM-Block schreiben | `0xC0014284` | DSP-Byteziel in `r0`, ARM-Quelle in `r1`, Halbwortanzahl in `r2`, auf 16 Bit gekürzt |

Der Sample-Schreiber `0xC004EF28` ruft diese Blockfunktion auf. Kleine
Schreibaufträge bis 15 Halbwörter werden vorher auf einen 32-Byte-Block
ergänzt. Die Zuordnung sämtlicher Normalize- und Truncate-Abläufe zu diesen
Schreibgrenzen ist damit noch nicht belegt. Die
[separate PCM-Gegenprobe](2026-11-05-sample-pcm-schreibpfade.md) hält den
reproduzierten Fehler und die Anforderungen an den Anschluss fest.

Der Aufnahmeabschluss `0xC004F128` verwendet sein `r0` unmittelbar als
physischen Tabellenindex. Eine Gleichsetzung mit dem logischen Slot war
nur im Identitätsmodell zulässig. Er veröffentlicht Tabellen ohne
`RESERVE` oder die genannte PCM-Blockfunktion.

Wiederverwendete Schutzsichten setzen vollständige Änderungsmarkierungen
voraus. Die genannten zusätzlichen Pfade bleiben daher ein Freigabeblocker.
Auch
sämtliche Time-Slice- und Aufnahmegrenzen einschließlich realem DMA sowie
die Freigabe nach sicher zurückgenommener Bearbeitung bleiben offen.
Die vorhandenen Haken sind kein Vollständigkeitsbeweis aller Mutationen.

Journal-I/O-Fehler, DSP-Kontext nach wartendem Ressourcenerwerb, native
Wartebudgets und die vollständige RAM-Prüfung aller Modi bleiben eigene
offene Aufgaben. Der dauerhafte Menü-Schreiber und die physischen
Versionszuordnungen zum aktuellen Dateikopf sind noch nicht vollständig
angeschlossen. Die Tune- und Pegelergänzung erfolgte ohne Gerätezugriff, Commit, Push oder Merge.


## Hergeleitet: direkte Tune- und Pegelschreibstellen

Die nativen Setter umgehen die oben genannten Start-, Loop- und
Deskriptorfunktionen. Beide erhalten den ausgewählten logischen Slot aus
`r0 + 0x3FC`. `r1` zeigt auf einen Zeiger zu einem Wertobjekt; dessen Wort
bei `+4` ist der neue UI-Wert. `r2` steuert die zusätzliche UI-Mitteilung.

| Wert | Setter | Schreibstelle | Tatsächliches Ziel |
|---|---|---|---|
| Tune | `0xC007F980` | `0xC007F9F0` | Halbwort `r2` nach `[r3 + 0x14]` |
| Sample-Pegel | `0xC007F8A8` | `0xC007F94C` | Byte `r5` nach `[r6 + 0x0A]` |

Tune verschiebt den UI-Wert vor dem Schreiben um acht Bit nach links.
Der Schutz vergleicht deshalb das gekürzte Halbwort, beim Pegel das
gekürzte Byte. Identische Werte setzen keine Marke. Eine tatsächliche
Änderung markiert die schon aufgelöste physische Zeile vor dem Schreiben.
Der aktuelle UI-Slot wird dafür nicht noch einmal gelesen.

Die Klangwirkung des Pegelbytes wurde nicht gemessen.
Die Wrapper erhalten Register, Stack, IRQ-Zustand und Statusflags. Das ist
beim Pegel notwendig, weil der unmittelbar folgende bedingte Sprung die
Flags von `cmp r7, #0` vor der ursprünglichen Schreibstelle verwendet.
Vergleich, Marke und tatsächlicher Store liegen in derselben kurzen
IRQ-Sperre. So kann zwischen Marke und Änderung keine andere Task eine
saubere Version bestätigen. Die Division des Tabellenzeigers liegt vor
dieser Sperre und ist durch 999 Zeilen begrenzt. Ein
Zeiger außerhalb der Tabelle oder zwischen zwei Zeilen setzt keine fremde
Marke. Die vollständigen Setter-Spans werden vor dem Patchen auf beiden
roten Originalen geprüft.

## Gemessen: Gegenproben der direkten Schreibstellen

Die neuen Modellfälle reproduzierten vor dem Anschluss sieben Fehler.
Danach bestehen 24 Schutztests einschließlich der bisherigen Fälle.
Zusätzlich geprüft sind negative Tune-Werte, gleiche gekürzte Werte,
Modus 0 und 2, maskierte Interrupts, ungültige Zeilenzeiger und das
Zurückdrehen auf den Ausgangswert. Register und vollständiger CPSR bleiben
an der Fortsetzung unverändert. Eine zusätzliche zunächst zweimal
fehlschlagende Gegenprobe prüft die gemeinsame IRQ-Sperre von Marker und
Store sowie die vorherige unmaskierte Zeigerauflösung.

Die nativen Fälle rufen beide vollständigen Setter mit erzeugten
Wertobjekten auf. Die physische Marke wird vor dem Signaturscanner geprüft;
damit kann der Scanner einen fehlenden Store-Hook nicht verdecken.
Ein gezielt eingeschobener Wechsel des UI-Slots unmittelbar vor dem Store
prüft, dass weiterhin das bereits aufgelöste Ziel geschützt wird. Dieser
Auswahlwechsel und die zusätzliche logische Aliaszuordnung sind
Modellannahmen. Kein Gerät und kein Audio wurden verwendet.


## Gemessen: Prüfung der atomaren Tune- und Pegelergänzung

Der unveränderte Laufzeitstand besteht `npm test` mit 1366 bestandenen und 161 ausgelassenen Tests. `npm run test:e2e` besteht mit 285 bestandenen und 1 ausgelassenen Tests. Beide Läufe haben keinen Fehler. Die Schutzmodelle umfassen 24 Fälle.

Je rotem Build bestehen 35 gezielte native Checks: Patternwechsel, fünf Schutzfälle, acht Snapshotfälle und 21 Startchecks. Die vollständige Patchanwendung gelingt auf beiden Originalen, die unabhängig erzeugten Patchdateien sind identisch. Die enge Codeprüfung hat nach den Korrekturen keinen offenen Befund.

Die separate `--pcm-write`-Gegenprobe schlägt auf beiden Builds weiterhin erwartungsgemäß fehl: veränderte DSP-Daten, keine Marke und erlaubte Verdrängung. Sie zählt ausdrücklich nicht zu den bestandenen Checks. Das Gesamtfeature bleibt dadurch und durch die weiteren offenen Punkte ohne Freigabe für 1.4. Kein vollständiger Releasecheck und kein Gerätetest wurden vorgenommen.
