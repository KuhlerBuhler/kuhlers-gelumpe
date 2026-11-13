# Sample-Sammlung: einen Slot dauerhaft speichern

Stand: 27.10.2026. Fortsetzung der [Swap-Prüfung](2026-10-27-sample-swap-1-4.md).
Beleg: `measure:2026-10-27/sample-store`.

Ziel ist das [Speichern jedes geänderten Slots](../plans/2026-10-27-sample-store.md)
ohne Gesamtexport. Die Emulatorversuche benutzen selbst erzeugte Samples
und eigene Firmwaredateien. Der freigegebene Kartentest vom 28.10. ist
getrennt weiter unten beschrieben.

## Gemessen: neue Daten am Ende, ein neuer Index

Eine erzeugte Datei enthält die Slots 500 und 501, mit den Namen `first`
und `second`. Eine neue Version von Slot 500 mit Namen `replacement` wird
am Ende angehängt. Der alte Block bleibt erhalten. Danach wird nur dessen
Index auf den neuen Block umgestellt. Slot 501 liegt jetzt im Dateiverlauf
vor Slot 500, obwohl seine Slotnummer größer ist.

| Prüfung | Ergebnis |
|---|---|
| App-Leser `parseSampleFile` | neue Version von 500, unveränderter Slot 501 |
| App-Leser `parseRemote` | gleiches Ergebnis, ohne das Audio vollständig zu lesen |
| Normaler Firmware-Lader | neue PCM-Daten von 500, unveränderte Daten von 501 |
| Swap-Lader mit verkleinertem Testbudget | neue Daten von 500; Slot 501 später nachgeladen und unverändert |
| Alte, nicht mehr referenzierte Daten | bleiben liegen und werden nicht als Sample geladen |

Die beiden Firmwarefälle bestehen mit den eigenen roten Originaldateien,
Korg 2.02 und Hacktribe, nach Anwenden des aktuellen BLECH-Satzes.
Wiederholbar mit `test/sample-persistence.test.mjs` und
`tools/emu/sample_persistence_cases.py`. Die Daten entstehen im Test,
keine Musterdatei wird im Repo abgelegt.

Zusätzlich liest der entfernte App-Leser simulierte Indexpositionen bei
256 MiB, 1 GiB, 2 GiB und am Ende des 32-Bit-Dateibereichs. Die Prüfung
legt keine riesige Datei an; ihr Leser liefert nur die kleinen angefragten
Bereiche. Das belegt die unsigned Auswertung des Index, nicht die
Erreichbarkeit dieser Größen über den derzeitigen USB-Befehl.

## Gemessen: der Einzelimport speichert noch nicht

Im Korg-Emulator mit BLECH, erzeugter Sammlung und `imp.wav`:

| Aufrufstelle | Funktion und Parameter |
|---|---|
| `0xC0038DE0` | `0xC003644C`, Pfad und gewünschter nullbasierter Slot |
| `0xC003646C` | `f_open` bei `0xC009DB60`, Pfad `SD:/imp.wav`, Modus 1 |
| `0xC00364B4` | Parser `0xC0035B10`, Dateiobjekt, Deskriptor, Zielslot, Quellpfad |
| `0xC003621C` | vorhandener Parser-Haken vor der Reservierung |
| `0xC003629C` | Platzvergabe `0xC004EDF0` mit dem Deskriptor |

Der beobachtete Zielslot war 500. Die Sammlung auf der Karte blieb
bytegleich und enthielt weiterhin ihre sechs ursprünglichen Indexeinträge.
Es gab in diesem Import keinen Aufruf von `f_write`. Der Import ist also
kein bereits vorhandener dauerhafter Einzel-Speicherweg.

Der Haken des Boot-Laders bei `0xC0036510` ist nicht die Öffnungsstelle
dieses Einzelimports. Die Änderung muss den Einzelpfad ausdrücklich
erfassen, statt nur das Startladen zu erweitern.

## Gebaut und im Modell gemessen: Transaktion je Slot

`src/sample-transaction.mjs` enthält einen blockweisen Schreibkern mit
einem exklusiv besessenen Dateiadapter. Er ist noch nicht an die Firmware
oder die USB-Dateibefehle angeschlossen.

Normaler Ablauf für eine bestehende Sammlung: nur der neue vollständige
RIFF/WAVE-Eintrag wird angehängt und durch Zurücklesen geprüft. Dann wird
eine 4160 Byte große Wiederherstellungsdatei mit altem Kopf, Zielslot,
Größen und Prüfsummen geschrieben und zurückgelesen. Erst danach ändern
sich vier Byte des Index. Der Kopf wird erneut geprüft, anschließend
wird die Wiederherstellungsdatei entfernt. Erfolg wird erst dann gemeldet.

Eine Löschung ändert nur den Offset auf null. Die Datei wird nicht
zusammengeschoben. Ist die neue Fassung auf Karte vollständig, kann die
Wiederherstellung den Index fertigstellen. Ist der angehängte Block
unvollständig oder seine CRC falsch, stellt sie den alten Index her.
Bei Lesefehlern oder einer ungültigen Wiederherstellungsdatei bleibt der
Vorgang stehen, statt ungeprüft einen Kopf darüberzuschreiben.

Die Prüfung `test/sample-transaction.test.mjs` benutzt einen Adapter mit
getrenntem flüchtigem und dauerhaftem Zustand. Sie unterbricht nach jedem
Schreib- und Flush-Schritt. Weitere Fälle beschädigen den betroffenen
512-Byte-Indexsektor, liefern kurze Schreibzugriffe, verändern neue Daten
oder verändern einen fremden Indexsektor. Große Offsets werden ohne große
RAM-Zuweisung geprüft. Bei gültiger Wiederherstellung bleiben andere
Slots erhalten. Die normalen Bibliotheks-Schreibzugriffe umfassen nur
die neuen Samplebytes und vier Indexbytes, ohne Kopieren anderer Samples.

**Grenze:** Diese Prüfungen setzen die zugesagten dauerhaften Grenzen des
Adapters voraus. Sie beweisen keine beliebige Stromausfallsicherheit
einer echten microSD, ihrer FAT oder des Controllers.

## Gebaut und im Emulator gemessen: nativer Speicherweg

`tools/patch/sample_store.py` benutzt Öffnen, Lesen, Schreiben, Schließen,
Positionieren und Entfernen der Firmware. Der neue Haken vor dem Öffnen
der Sammlung bei `0xC0036510` führt zuerst die Wiederherstellung aus.
Ein erzeugter Fall beschädigt den betroffenen Indexsektor und startet die
vollständige Firmware. Beide roten Builds laden anschließend die neue
Version und das unveränderte zweite Sample; die Transaktionsdatei ist entfernt.

`tools/patch/sample_import.py` enthält einen eigenständig aufrufbaren
Importdienst. Der Firmware-Parser erzeugt den Deskriptor, hält jedoch vor
der DSP-Reservierung an. Header, PCM, gegebenenfalls ein Füllbyte und der
Deskriptor bilden einen vollständigen RIFF-Eintrag. Die PCM-Daten werden
blockweise von der Quelldatei gelesen. Es wird kein vollständiges Sample
im ARM-RAM gehalten.

`tools/emu/sample_store_cases.py` prüft diesen Dienst mit den tatsächlichen
Dateifunktionen: Anhängen eines Slots, Löschen ohne Verschieben anderer
Audio-Daten, Import einer erzeugten WAV bei absichtlich vollem DSP-Zeiger
und Laden nach Neustart ohne Gesamtexport. Beide roten Builds bestehen.
Der Dienst ist noch nicht am normalen Import-Menü angeschlossen.

Das ARM-Modell prüft außerdem Fehler an allen sechs Dateischließstellen
eines Imports und beim Entfernen der Transaktionsdatei. Kein Fehler wird
als Erfolg gemeldet. Vor dem Journal bleibt der alte Index erhalten;
mit Journal lässt sich die vollständige neue Version wiederherstellen.
Das sind Dateifunktions- und Emulatorprüfungen, keine Geräte-Abbruchtests.

Die automatische Platzwahl liest den vollständigen Kopf und wählt den ersten
freien Nutzerplatz daraus. Sie benutzt keine DSP-Aktivflags. Ein ungültiger
Kopf, eine volle Belegung oder ein Fehler beim Dateischließen liefert keinen
scheinbar freien Platz. Im Emulator wird der zuvor im Index gelöschte Slot
erneut belegt, während die anderen Karten-Slots erhalten bleiben. Auch diese
Fassung lädt nach Neustart ohne Gesamtexport.

Das ARM-Modell benutzt außerdem dünn belegte Dateien mit Größen oberhalb von
256 MiB, 1 GiB und 2 GiB sowie bis an die 32-Bit-Dateigrenze. Anhängen und
Index bleiben vorzeichenlos; ein Größenüberlauf wird vor dem ersten Schreiben
verweigert. Die echte FAT und ihre Clusterketten sind in diesen großen Fällen
ersetzt. Das ist noch kein Gerätetest einer fast 4 GiB großen Sammlung.

## Im Emulator gemessen: Schutz einer anderen Slotnummer

Ein erzeugter Zuordnungsfall zeigt den Fehler der bisherigen Verdrängung:
Slot 603 zeigt auf dieselben physischen Daten wie Slot 601. Der Part benutzt
603. Der alte Vergleich der sichtbaren Slotnummern bot trotzdem 601 zur
Verdrängung an. Zwei ARM-Regressionen reproduzieren diesen Fall.

Die Verdrängung löst nun auch die geschützten Slots durch die drei Tabellen
zum physischen Metadateneintrag auf. `case_alias_eviction` in
`tools/emu/swap_cases.py` prüft beide roten Builds mit erzeugten Daten:
Der unabhängige Slot wird freigegeben, die vom Part verwendeten Daten bleiben
bytegleich. Reicht der übrige Platz nicht, wird kein geschützter Block verdrängt.
Das belegt Zuordnung und Dateninhalt, keine ausklingenden Stimmen oder Klang.

Die vollständige Patchprüfung führt außerdem die Transaktions- und
Importfälle aus, sobald der native Speicherkern vorhanden ist.

## Im ARM-Modell gemessen: Bibliothekswechsel und Fehlersperre

Vier weitere Regressionen zeigen beim bisherigen Öffnungshaken:
Ein alter Lesehandle wurde nicht geschlossen, die Cache-Generation blieb
gleich, kleine Dateien hinterließen keinen gespeicherten Pfad und ein
erneutes Öffnen löschte die DSP-Protokollfehler-Sperre. Das Modell ersetzt
die Dateifunktionen durch protokollierte Rückgaben und beobachtet die
Reihenfolge der tatsächlichen ARM-Aufrufe.

Der Haken macht nun die alten Ladeaufträge ungültig, leert die Cachezeiger
und schließt den alten Leser vor der Wiederherstellung. Auch für kleine
Sammlungen bleiben Pfad und Zustand initialisiert. Ein Schließfehler
verweigert den neuen Ladeversuch. Eine DSP-Fehlersperre bleibt gesetzt;
nur der uninitialisierte Wert beim Kaltstart wird zu null.

Die Prüfung aller Zustands-Schreibzugriffe fand zusätzlich ein kurzes
MODE-0-Fenster während des Zurücksetzens. Der aktive oder fehlerhafte
Wechsel veröffentlicht jetzt zuerst MODE 2. MODE, Generation und DSP-Sperre
werden beim anschließenden Leeren ausgelassen. Erst nach erfolgreichem
Öffnen wird der endgültige Modus veröffentlicht. Die neue Regression
prüft den erfolgreichen und den gesperrten Wechsel ohne Zwischenwert null.

Eine weitere Regression ruft den vollständigen Bibliothekslader mit
gesetzter DSP-Protokollsperre auf. Vor der Korrektur liefert er zwar Fehler 4,
hat aber bereits die aktive Metadatentabelle gelöscht: Der native Aufruf
`0xC0036500` liegt vor dem Öffnungshaken. Der zusätzliche Schutz bei
`0xC00364F4` prüft die Sperre vor diesem Aufruf und erhält bei Verweigerung
die vollständige Tabelle. Der Wert `0xFFFFFFFF` bleibt als noch nicht
initialisierter Kaltstartzustand erlaubt.

Der Schutz liegt nach dem gemeinsamen Registerprolog. Damit erreicht ihn
auch der vorhandene Ladefehler-Patch über seinen eigenen Aufruf des
Laderumpfs; dessen Einstieg bei `0xC00364F0` bleibt in dessen Besitz.
Die Regression steht in `tools/emu/sample_persistence_cases.py`.

## Im Emulator gemessen: Abschluss der Sample-Bearbeitung

Mit erzeugten Samples führt Bildschirm 37 zu SAMPLE EDIT; ENTER öffnet
Bildschirm 38 mit den zehn Bearbeitungsseiten. Eine Änderung am Startpunkt
schreibt zunächst die Wiedergabetabelle. Bestätigen beendet die Eingabe;
EXIT aus den Bearbeitungsseiten führt wieder zu Bildschirm 37.

Dabei wird der Kommando-Abschluss bei `0xC0039420` aufgerufen. Er übernimmt
den vorbereiteten Deskriptor über `0xC004EFF4` in Namen, Wiedergabe und
Metadaten. Das ist eine erfasste Abschlussstelle, noch keine automatische
Speicherung. Der Löschaufruf im zugehörigen Kommando liegt bei `0xC00395B8`
und ruft `0xC0035994` mit der gewählten Slotnummer auf. Dieser löst über
`0xC004E4EC` zur Importnummer auf, bevor der DSP-Platz freigegeben wird.
Die neue Kartenspeicherung ist dort noch nicht angeschlossen.

## Im Emulator gemessen: Importkommando und tatsächliche Partauswahl

Der Einzelimport-Handler `0xC0038D80` bekommt den zuvor kopierten Dateipfad
über die globale String-Instanz bei `0xC0345A24`. Die Slotwahl ist die
angezeigte Nummer minus eins; ohne Auswahl ist sie `-1` für automatisch.
Der Aufruf bei `0xC0038DE0` übergibt Pfad und Slot an `0xC003644C`.
Dessen Status landet unverändert in Byte `+0x18` des Kommandoobjekts.

In beiden roten Builds liefern erzeugte gültige WAVs Status 0, fehlende
Dateien 4, beschädigte RIFF-Dateien 32 und eine falsche Endung 36.
Der tatsächliche Kommandoauftrag mit Nummer `0x22` schließt bei Erfolg
das Fortschrittsfenster. Bei Fehler öffnet `0xC0083DB0(0x1B, Status)`
das native Fehlerfenster.

Die anschließende Aktualisierung bei `0xC0038DEC` läuft auch bei Fehlern.
Sie erhält die ursprüngliche Slotwahl, nicht einen zurückgegebenen Slot.
`0xC009A0A8` vergleicht gegen den aufgelösten physischen Metadatenindex;
bei `-1` aktualisiert sie alle 16 Parts. Diese Stelle darf daher erst nach
geprüfter Veröffentlichung einer neuen DSP-Version benutzt werden.

Die Partfunktion `0xC0099D88` kopiert den gewünschten Samplewert aus
dem Part-Record nach Partobjekt `+0x34`. Im Modell ändert sich dieser
tatsächliche Wert erst beim Aktualisieren von 500 auf den noch fehlenden
Slot 501. Ein alleiniger Haken bei `0xC0099FFC` erfasst nicht alle Wege:
`0xC0098BF8` und `0xC0098C70` rufen die Kopierfunktion direkt auf.
Der spätere [Part-Versuch](2026-10-28-sample-swap-stimmen.md) sichert
beide Eingänge und aktualisiert den Part erst nach vollständigem Nachladen.
Die Versionsverwaltung beim dauerhaften Ersetzen bleibt offen.

Die native Reservierung `0xC004EDF0` löst ihren physischen Platz aus der
alten Importnummer des gewählten Namenseintrags auf. Erst danach kopiert
sie die neuen Deskriptordaten einschließlich der Importnummer in diesen
Namenseintrag. Das sind zwei verschiedene Zuordnungen, wenn ein Alias
ersetzt wird.

Mit erzeugten Samples verweisen die Slots 500 und 600 zunächst über
Importnummer 550 auf denselben physischen Platz 500. Der gewöhnliche
WAV-Import nach Slot 600 erzeugt dagegen Importnummer 650. Der native
Lösch- und Reservierungsweg schreibt die neuen 800 Byte am Platz 500;
danach löst der Name 600 über Nummer 650 wieder den alten Platz 600 mit
600 Byte auf. Eine anschließende Partaktualisierung repariert diese
Zuordnung nicht. Das gleiche Ergebnis tritt in beiden roten Builds auf.
Der neue Kartenimport darf diese Folge nicht als Veröffentlichung einer
neuen DSP-Version übernehmen. Alte Aliase und noch aktive Stimmen brauchen
weiterhin ihre alte Version, bis der neue Platz vollständig bereitsteht.

## Im Emulator gemessen: getrennte Veröffentlichung einer neuen Version

`tools/emu/sample_residency_probe.py` setzt zwei erzeugte Slots 500 und
600 auf dieselbe Importnummer 550 und erzeugt mit nativen Notenaufrufen
zwei Stimmen. Der native WAV-Parser bereitet danach 800 Byte neue PCM
für Slot 600 vor. Der begrenzte Transfer schreibt sie in einen freien
DSP-Bereich. Erst danach setzt der Versuch Metadaten, Wiedergabe und
den Namenseintrag auf den vorgegebenen freien Platz 601 mit Importnummer
651 um. Ein bisher leerer Name, der diesen Platz referenzierte, wird auf
einen anderen vorgegebenen inaktiven Platz umgebunden.

In beiden roten Builds bleiben die alte PCM von Slot 500 und die beiden
Stimmen mit Importnummer 550 erhalten. Eine anschließend erzeugte Stimme
für Slot 600 trägt Nummer 651; ihre PCM stimmen bytegleich mit der neuen
Quelle überein. Der umgebundene leere Slot bleibt unbenutzt. Kein Assert
tritt auf.

Das ist ein kontrollierter Modellversuch mit vorgegebenen freien Plätzen,
keine eingebaute Platzsuche. Während der CPU-Tabellenänderung steht die
Emulation; gleichzeitige Interrupts und Bearbeitung sind nicht geprüft.
Die ARM-Stimmen bleiben im DSP-Modell angelegt, aber weder Klang noch ihr
echtes Ende werden nachgebildet. Der Versuch belegt die getrennten
Bindungen und ersetzt weder die Besitzschicht noch den Gerätetest.

## Hergeleitet: Aufnahmeabschluss und DSP-Leseweg

`0xC0082F1C(Transportobjekt, Startvariante)` beginnt die Aufnahme über
`0xC0013D98(1, Konfiguration704, Konfiguration708, DSP-Anfang)`.
`0xC0082D40` stoppt sie und ruft `0xC004F128(Slot, Konfiguration704,
Konfiguration708)` auf. Der Finalisierer liest das Aufnahmeende über
`0xC004E23C` aus DSP-Adresse `0xFF903210`, veröffentlicht Metadaten und
Wiedergabetabelle und setzt den nächsten freien DSP-Zeiger. An dieser
Abschlussstelle gibt es keinen ARM-Puffer mit der aufgenommenen PCM.

Der gemeinsame Einzel- und Gesamtexport benutzt
`0xC0039B2C(Objekt, Datei, Deskriptor, DSP-Anfang; PCM-Bytes auf dem Stack)`.
Er liest über `0xC004EDDC(ARM-Ziel, DSP-Byteoffset, Anzahl16BitWörter)`
höchstens 64 KiB pro Block zurück. Die nativen GPIO- und Statuswartepfade
haben keine Zeitgrenze; die Rückgabe null ist kein Übertragungsnachweis.

Der vorhandene eigene Transport kann bereits begrenzt lesen. Er verlangt
jedoch 32-Byte-DSP-Ausrichtung und Wortzahlen in 16er-Gruppen. Der native
Leser behandelt Reste über einen 32-Byte-Puffer und liest dabei über das
logische Sample-Ende hinaus. Die Aufnahmegrenzen und dieser Unterschied
müssen vor dem Anschluss an die dauerhafte Speicherung geklärt werden.
Die Bezeichnungen der Konfigurationswerte und die Resampling-Quellen
sind noch nicht über die Oberfläche bestätigt.

## Im Emulator gemessen: synthetischer Aufnahmeabschluss

`tools/emu/sample_capture_cases.py` gibt dem DSP-Modell erzeugte PCM und
einen dazu passenden Aufnahme-Endzeiger vor. Das ist eine Modellannahme,
keine Audioaufnahme. Der unveränderte Abschluss erzeugt in beiden roten
Builds einen aktiven Slot mit 2050 Byte und setzt Zustand 11 auf 12.
Direktes natives Rücklesen und ein vollständiger Einzel-Export erhalten
die erzeugte PCM Byte für Byte. Der Emulator hat weder Audio noch DMA;
echte Aufnahme, Resampling und autonomes Aufnahmeende bleiben offen.

Der Aufnahmebeginn liegt im Test zwei Byte hinter einer 32-Byte-Grenze,
auch die Länge ist kein Vielfaches von 32. Der eigene begrenzte Leser in
`tools/patch/sample_swap_io.py` liest diesen Bereich in beiden Builds
ebenfalls bytegleich zurück. Die vier Byte vor und nach dem ARM-Ziel
bleiben unverändert. Der Lesebefehl rundet seine Wortzahl auf einen vollen
16-Wort-Block auf und nimmt die übrigen Wörter vom Port ab, ohne sie in den
Zielpuffer zu schreiben. Das entspricht der Blockbreite des nativen Lesers.

19 ARM-Modelltests prüfen zusätzlich einzelne Wörter, Restgruppen,
Puffergrenzen und den Timeout nach einem teilweise gelesenen Auftrag.
Der Rückgabewert zählt nur kopierte Wörter. Ein unterbrochenes Protokoll
bleibt gesperrt; der zweite Aufruf greift nicht erneut auf den Port zu.
Schreiben verlangt weiterhin 32-Byte-Ausrichtung und vollständige Blöcke.

Die angeforderte PCM muss innerhalb des belegten Bereichs liegen. Auch
der aufgerundete Portzugriff darf die im Leser hinterlegte DSP-Obergrenze nicht
überschreiten. Passt der letzte Block dort nicht mehr, beginnt der
Portzugriff entsprechend früher. Zusätzliche Wörter am Anfang werden
abgenommen und verworfen. Modellfälle mit einem, 15, 17 und 31 Wörtern
direkt an der Obergrenze und zwei Byte davor prüfen Adresse, Wortzahl und
beide ARM-Puffergrenzen. Der neue Leser ist noch nicht an die Aufnahmebedienung
angeschlossen und wurde noch nicht am Gerät geprüft.

## Hergeleitet und als Speichergrenze geprüft: untere Cachegrenze

Die neue Grenzprüfung vergleicht beide Cachebereiche mit dem gemessenen
freien RAM ab `0xC1010000` und spart den Task-Stack bei `0xC274E000`
aus. Sie reproduziert beim bisherigen Anfang `0xC0D3A940` eine
Unterschreitung der vorgegebenen freien Region. Der aktuelle untere Cache
beginnt deshalb bei `0xC1010000` und endet weiterhin bei `0xC273AA40`.
Der obere Cache bleibt bei `0xC276F000` bis `0xC4000000`.

Zusammen sind das rund 47,73 MiB. Die Beschränkung auf normale Wiedergabe,
das Verwerfen beim Arbeitspuffer-Geber und die Prüfsumme bleiben nötig.
Die Grenzprüfung ersetzt keinen Nachweis über echte DMA-Zugriffe.

Der vollständige Sitzungsfall in `tools/emu/swap_cases.py` beobachtet
zusätzlich den ursprünglichen Arbeitspuffer ab `0xC0D3A940`. Nach dem
höheren Cachebeginn wären gewöhnliche Import- und Exportzugriffe sonst
aus der Beobachtung gefallen. Der Test verlangt weiterhin tatsächliche
Schreibzugriffe dieser Funktionen und prüft, dass sie erst nach dem
Verwerfen beginnen; zusätzlich zählt er die Zugriffe im Cachebereich.

Mit erzeugten Daten im Stock-Emulator schreibt `IMPORT SAMPLE` 10432-mal
in den Arbeitspuffer, aber nicht in den Cache. `EXPORT ALL SAMPLE` schreibt
in derselben Sitzung 40000-mal unterhalb des Caches. `IMPORT ALL PATTERN`
schreibt 1041408-mal in den Arbeitspuffer, davon 281360-mal in den Cache.
Kein beobachteter fremder Zugriff geschieht vor dessen Verwerfen. Das sind
Anzahlen von CPU-Schreibzugriffen, keine Bytezahlen. Der Bereich ist damit
ausdrücklich nicht in jedem Modus frei. Die Aufnahmefolge zeigt mangels
DMA-Modell keine solchen Zugriffe und belegt keine Hardware-Freiheit.

Weitere ARM-Regressionen reproduzieren überlaufende Größenrechnungen beim
Vorausladen und Installieren. Vor der Korrektur konnte eine ungültige
PCM-Länge einen Auftrag außerhalb des RAM oder über einem geschützten
DSP-Platz starten. Auch ein Cachezeiger unterhalb der unteren Grenze
wurde angenommen.

Beide Starter prüfen jetzt vor Rundung und Platzvergabe eine positive,
gerade PCM-Länge innerhalb des bisherigen 25-MiB-DSP-Budgets. Damit passen
Rundung, Deskriptoraufschlag und Adressaddition in 32 Bit. Ein Cachezeiger
muss zusätzlich innerhalb eines erlaubten Bereichs liegen. Die 29
ARM-Modelltests bestehen. Diese Prüfung begrenzt einzelne DSP-Aufträge,
nicht die Bibliotheksdatei; die tatsächliche physische DSP-Grenze bleibt offen.

## Hergeleitet und im ARM-Modell geprüft: Grenzen der Slot-Tabellen

Die native Initialisierung bei `0xC004E324` begrenzt ihre Metadatenschleife
mit dem Wert 999 aus `0xC004E3C4`. Dieser Wert stimmt in beiden roten
Original-Builds überein; die Initialisierungen selbst sind nicht bytegleich.
Die Einträge haben jeweils `0x45C` Byte. Hinter Eintrag 998 beginnt bei
`0xC047B08C` bereits der Namensbereich. Auch die erste Zuordnungstabelle
endet nach 999 Einträgen unmittelbar an der nächsten Tabelle.

Die bisherige Platzsuche las 1000 Metadateneinträge. Ihr letzter Zugriff
behandelte damit Namensdaten wie eine weitere DSP-Belegung. Außerdem
ließen die Zuordnungsprüfungen Indizes bis 999 oder 1023 zu. Drei neue
Modelltests mit erzeugten Tabellen reproduzieren diese Fehler und prüfen
auch den letzten gültigen Eintrag 998. Der Allocator und alle Schritte
der Zuordnung begrenzen sich jetzt auf 999 Einträge. Die insgesamt 32
ARM-Tests bestehen; der Builder prüft den nativen Grenzwert vor dem Bau.
Größe und Offsetfelder des 4096-Byte-Dateikopfs bleiben unverändert.

## Am Gerät gemessen: installierter Stand

Am 27.10. antwortet der rote Sampler über den Linux-Laptop auf Gerätesuche,
BLECH INFO und CRC-geprüftes RAM-Lesen. Die Gerätesuche meldet Korg 2.02.
Der Haken bei `0xC0036510` stimmt mit dem unveränderten Original überein;
der vorgesehene Speicherbereich ab `0xC019A400` enthält weiterhin den
Originalinhalt. Der Swap-Zustand beginnt mit vier uninitialisierten Wörtern.
Dieser entwickelte Speicherpatch ist damit nicht auf dem Gerät installiert.
Die BLECH-Produktversion wurde durch diese Protokollabfrage nicht bestimmt.
Es wurden keine RAM-, DSP-, Karten- oder Flash-Schreibbefehle ausgeführt.

Am 28.10. stimmt eine zusätzliche CRC-geprüfte 64-Byte-Leseprobe bei
`0xC0170000` mit dem Code der eigenen Hacktribe-Referenz überein. Die
eigene Stock-Referenz ist dort gelöscht. Damit ist der erwartete
Hacktribe-Code nach dem gemeldeten Neustart bestätigt; die
BLECH-Produktversion wird daraus weiterhin nicht abgeleitet.

## Am Gerät gemessen: eigener Kartentest am 28.10.

Nach dem erneuten Start mit BLECH und Hacktribe stimmen die geprüften
nativen Dateifunktionen weiterhin mit der Referenz überein. Die Vorprüfung
bestätigt STOP, Hauptseite ohne Fenster und einen freien MIDI-Port.
Die Ausführung wurde ausdrücklich freigegeben.

`tools/device/sample_store_probe.py` lädt ausschließlich seinen eigenen
ARM-Schreibkern in gesicherten RAM und benutzt eine neue, zufällig benannte
`BTxxxxxx.all` im Kartenwurzelverzeichnis. Die aktive Sample-Sammlung und
der DSP werden nicht beschrieben. Die 13 bestätigten Aufrufe prüfen:

- Testdatei und Journal sind anfangs nicht vorhanden.
- Zwei erzeugte Samples mit je 512 Frames werden angehängt.
- Der erste Slot wird durch einen neuen Block mit 1024 Frames ersetzt.
- Löschen des zweiten Slots ändert nur seinen Indexeintrag.
- Nach jeder Änderung stimmt die vollständig zurückgelesene Datei Byte
  für Byte mit den erzeugten Sollwerten überein.
- Journal und Testdatei sind am Ende nicht vorhanden. Alle vier benutzten
  RAM-Bereiche wurden zurückgeschrieben und durch Rücklesen geprüft.

Alle Dateiaufrufe liefern Erfolg; die vier erwarteten Abwesenheitsprüfungen
liefern Status 4. Keine Ausführung und keine Kommunikation bleibt
unbestätigt. Für das Ersetzen wurden 319,26 ms und für das Index-Löschen
253,20 ms innerhalb des ARM-Aufrufs gemessen. Das sind vollständige
Transaktionen mit Prüfen und Journal, keine PCM-Durchsatzmessungen.
Zwei weitere Schreibzeiten sind wegen der Zeitgeber-Gültigkeitsprüfung
nicht auswertbar und werden nicht als Messwerte benutzt.

Der Test belegt den Schreibkern mit kleinen erzeugten Daten auf dieser
Karte. Er belegt weder die Anbindung an die normale Bedienung noch
Stromausfallfestigkeit, volle Karte oder Schreiben während der Wiedergabe.
Es wurde keine Firmware installiert und nicht in Flash geschrieben.

## Hergeleitet: Grenzen und gemeinsamer Besitzer

Der Kopf hat 1020 Offsets zu je 32 Bit. Die Firmware nutzt für die normalen
User-Slots 500 bis 998, angezeigt als 501 bis 999. Auch die FAT32-Dateigröße
ist ein 32-Bit-Wert. Die Beseitigung der DSP-Grenze macht dieses Format
deshalb nicht unbegrenzt groß: 4294967295 Byte bleiben eine technische
Obergrenze der einzelnen Datei. Die native Erreichbarkeit bis zu dieser
Grenze ist nicht vollständig gemessen.

Der derzeitige USB-Weg begrenzt Sample-Dateizugriffe zusätzlich auf
`0x10000000`, also 256 MiB. Darüber hinaus kodiert er die Dateiauswahl in
Bit 30 und 31 des Offsets. Für vollständige 32-Bit-Dateioffsets müssen
Dateiauswahl und Offset getrennt übertragen werden. Eine größere
Grenzkonstante allein genügt nicht.

Der bisherige App-Änderungsplan verdichtet bei Entfernen und bei bereits
vorhandenen Lücken. Er ist deshalb noch nicht der neue Slot-Schreibweg.
Ebenso schützt die exklusive Sitzung eines USB-Clients nicht gegen einen
anderen Schreiber in der Firmware. Import, Bearbeitung, Aufnahme, Swap
und USB brauchen denselben geräteseitigen Besitzer des Dateizugriffs.

## Offen

- Nativen Importdienst an die Bedienung anbinden, Zielslot aus der
  Kartenbelegung wählen und erst nach dem Kartenabschluss nachladen.
- Abschlussstellen von SAMPLE EDIT, Löschen und echter Aufnahme kartieren
  und an denselben Weg anschließen.
- Alte USB-Schreibwege, Index-Cache und offene Handles gemeinsam koordinieren.
- `EXPORT ALL SAMPLE` erst nach geprüftem Ersatz aller Speicherwege entfernen.
- Große echte Dateien, volle Karte und Stromunterbrechungen am Gerät prüfen.

Die bestandenen Swap-Prüfungen aus der vorigen Runde bleiben Belege für
deren Stand, nicht für eine bereits eingebaute automatische Speicherung.

## Vorbereiteter Gerätetest für den Schreibkern

`tools/device/sample_store_probe.py` prüft den eigenen ARM-Schreibkern unabhängig
vom installierten Swap-Patch. Ohne Schalter stellt es nur den Ablauf dar.
`--preflight` mit der eigenen VSB liest Gerätekennung, Protokollfähigkeiten,
Dateifunktionen und den aktuellen Zustand. Dabei werden keine RAM-, DSP-,
Karten- oder Flash-Schreibbefehle gesendet.

Der ausführende Modus verlangt `--execute`, `--card-write-confirmed`, eine eigene
VSB sowie Bericht und ein neues Backup-Verzeichnis außerhalb des Repos. Der Test
benutzt ausschließlich einen zufälligen Namen `BTxxxxxx.all` im Wurzelverzeichnis und
dessen Journal. Eine vorhandene Datei oder ein Schließfehler bei der Vorprüfung
wird verweigert. Danach werden zwei selbst erzeugte Einträge angelegt, einer
ersetzt und einer im Index gelöscht. Nach jedem Schritt wird die vollständige
Testdatei zurückgelesen. Am Ende wird nur die eigene Testdatei entfernt und der
benutzte RAM wiederhergestellt und verglichen.

Der eigene Code, Puffer und Quelle liegen oberhalb des Task-Stacks. Der übliche
EXEC-Einstieg ist 1024 Byte groß. Für die weiter entfernten Dateifunktionen benutzt
der Test eigene Sprungbrücken. Bei unbestätigter Ausführung oder einem Fehler der
Kommunikation folgen keine weiteren Schreibversuche oder automatische Bereinigung.
Vor und während des Tests müssen Hauptseite, STOP und ein freier MIDI-Port bestehen.

Zehn Modellfälle prüfen Ablauf, Namenskollision, Schließfehler, Bereichsgrenzen,
fehlende Bestätigung und Wiederherstellung. Derselbe Ablauf besteht zusätzlich mit
den tatsächlichen Dateifunktionen beider roten Original-Builds im Emulator. Die
aktive, erzeugte Sammlung bleibt dabei bytegleich. Das beweist noch keinen
Stromausfall und keine Wiedergabe auf dem Gerät.

Die erste lesende Vorprüfung am 27.10. hielt bei Bildschirm 3 ohne Fenster an,
weil der Test die Hauptseite 1 verlangt. Nach dem Neustart am 28.10. bestanden
Vorprüfung und freigegebener Kartentest, siehe den Abschnitt zum eigenen
Kartentest oben. Die Testdatei und ihr Journal sind entfernt, der Arbeits-RAM
ist wiederhergestellt und vollständig geprüft. Ein freier MIDI-Port bei der
Vorprüfung verhindert nicht, dass später ein anderer Client dazukommt.

## Hergeleitet: USB-Aufträge und Dateibesitz

Die vorhandenen Dateibefehle laufen über den CommandTask-Haken bei
`0xC0026418`. Auch Import und Swap arbeiten in diesem Task. Das serialisiert
einzelne Dateiaufrufe, reserviert die Sammlung aber nicht über mehrere
USB-Nachrichten hinweg. Der bisherige `FILE_BEGIN`-Befehl `0x66` beschreibt
einen ausstehenden Block. Erst `DATA` mit `0x63` öffnet, schreibt und schließt
die Datei und prüft sie durch erneutes Lesen. Ein dauerhaft gehaltenes
Dateiobjekt oder ein Transaktionsbesitzer entsteht daraus nicht.

Der ausstehende Block trägt keine Sitzungskennung. Der USB-Schreibweg kennt
weder die Swap-Generation noch dessen offene Lesehandles oder das Journal.
Eine exklusive Sitzung in einem einzelnen App-Client reicht deshalb für den
gemeinsamen Besitzer nicht aus. Auch ein angehaltener Ladeauftrag kann noch
PCM im gemeinsamen Arbeitspuffer halten; der Puffer darf erst nach seiner
Invalidierung für einen anderen Auftrag verwendet werden.

Die Dateiauswahl steckt bisher in Bit 30 und 31 des Offsetworts. Diese Bits
werden vor dem Zugriff entfernt; zusätzlich gilt die Grenze von 256 MiB.
Ein vollständiger 32-Bit-Offset und die Journalrolle brauchen eine getrennte
Dateiauswahl. Im untersuchten Protokoll sind die Befehlsnummern `0x74` bis
`0x78` und `0x7C` bis `0x7F` unbelegt. Das ist noch keine Festlegung eines
neuen Protokolls und keine bereits angebotene Fähigkeit.

Der native Abschluss `0xC009E3DC` ruft die Synchronisierung bei
`0xC009E2C8` auf. Über `0xC009BEE0` und `0xC009BAF8` erreicht sie
`disk_ioctl` mit `CTRL_SYNC`. Der SD-Treiber beantwortet diesen Befehl bei
`0xC003FF4C` unmittelbar mit null. Daraus folgt das Zurückschreiben der
Softwarepuffer, aber kein belegter Hardware-Cacheflush der Karte. Rücklesen
und Journalprüfung bleiben nötig; Stromausfallfestigkeit bleibt ein Gerätetest.
