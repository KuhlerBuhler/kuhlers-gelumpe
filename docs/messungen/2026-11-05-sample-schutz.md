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

## Gemessen: abschließende Prüfungen

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

Die statische Nachprüfung beider Originale belegt zusätzliche Live-Schreiber,
die noch nicht in den Schutz eingebunden sind:

| Funktion | Einstieg | Schreibgrenze |
|---|---|---|
| Tune | `0xC007F980` | `0xC007F9F0`, Halbwort `META + 0x14` |
| Play-Level | `0xC007F8A8` | `0xC007F94C`, Byte `META + 0x0A`; Wirkung weiterhin nicht gemessen |
| PCM-Block schreiben | `0xC0014284` | DSP-Byteziel in `r0`, ARM-Quelle in `r1`, Halbwortanzahl in `r2`, auf 16 Bit gekürzt |

Der Sample-Schreiber `0xC004EF28` ruft diese Blockfunktion auf. Kleine
Schreibaufträge bis 15 Halbwörter werden vorher auf einen 32-Byte-Block
ergänzt. Die Zuordnung sämtlicher Normalize- und Truncate-Abläufe zu diesen
Schreibgrenzen ist damit noch nicht belegt.

Der Aufnahmeabschluss `0xC004F128` verwendet sein `r0` unmittelbar als
physischen Tabellenindex. Eine Gleichsetzung mit dem logischen Slot war
nur im Identitätsmodell zulässig. Er veröffentlicht Tabellen ohne
`RESERVE` oder die genannte PCM-Blockfunktion.

Wiederverwendete Schutzsichten setzen vollständige Änderungsmarkierungen
voraus. Die genannten zusätzlichen Pfade bleiben daher ein Freigabeblocker.
Auch
sämtliche Time-Slice- und Aufnahmegrenzen einschließlich realem DMA sowie
die Freigabe nach sicher zurückgenommener Bearbeitung bleiben offen.
Die genannten acht Haken sind kein Vollständigkeitsbeweis aller Mutationen.

Journal-I/O-Fehler, DSP-Kontext nach wartendem Ressourcenerwerb, native
Wartebudgets und die vollständige RAM-Prüfung aller Modi bleiben eigene
offene Aufgaben. Der dauerhafte Menü-Schreiber und die physischen
Versionszuordnungen zum aktuellen Dateikopf sind noch nicht vollständig
angeschlossen. Es gab keinen Gerätezugriff, Commit, Push oder Merge.
