# Sample-Speicherung: native Bestätigungen und Tabellen

Stand: 30.10.2026. **Gemessen im Emulator** mit selbst erzeugten Samples,
ohne Gerät, Klang oder DMA. Die neuen Oberflächenversuche gelten für
Stock 2.02. Der Importversuch und die Part-Zuordnung wurden auf Stock
und Hacktribe geprüft. Ergänzung zum
[dauerhaften Speicherweg](2026-10-27-sample-store.md).

## Gemessen: Import verändert bislang nur den DSP

Der aktuelle Swap-Patch lädt eine erzeugte Bibliothek mit sechs Einträgen
und 491488 Byte. Der native Import wählt ausdrücklich den internen Slot
500, also den sichtbaren Platz 501. Der Aufruf bei `0xC0038DE0` übergibt
den Pfad und diesen Slot an `0xC003644C`.

Der Import liefert Erfolg null. Die neue PCM mit 40000 Byte liegt danach
vollständig im DSP. Die gesamte Bibliotheksdatei bleibt dagegen bytegleich;
der Indexeintrag für Slot 500 zeigt weiter auf Offset 4096. Der Swap meldet
den Slot weiterhin als resident, weil seine bisherige Prüfung nur das
Geladen-Flag der aufgelösten Metadatenzeile betrachtet.

**Hergeleitet:** Der dauerhafte Import benötigt neben dem Kartenschreiber
eine Zuordnung zwischen gespeichertem Eintrag und geladener DSP-Version.
Ein gültiges Geladen-Flag allein reicht nach einer Slot-Ersetzung nicht.

## Gemessen: Sample-WRITE und EXIT sind verschiedene Grenzen

Die Sample-Auswahl ist Bildschirm 37, ENTER öffnet die Bearbeitung auf
Bildschirm 38. Veränderte Start- und Loop-Punkte wirken zunächst auf die
Wiedergabetabelle. EXIT ohne WRITE ruft Kommando `0x21` über
`0xC0039420` und `0xC004EFF4` auf und stellt die alten Werte zurück.

Schon das erste WRITE ruft Kommando `0x25` und `0xC00396D8` auf. Darin
sichert `0xC004EBD4` den veränderten Deskriptor nach `0xC0345A2C`.
Nach abgeschlossenem WRITE erhält EXIT die neuen Start- und Loop-Punkte.
Ein weiteres WRITE nach Abschluss ruft denselben Auftrag erneut auf.
Das angezeigte Fenster `0x19` gehört zum allgemeinen Kommandoablauf;
es belegt kein Pattern-WRITE.

Der Snapshot-Aufruf hat diese Parameter:

| Parameter | Bedeutung |
|---|---|
| r0 | interner logischer Slot |
| r1 | Ziel des Deskriptors, beim nativen WRITE `0xC0345A2C` |
| r2 | Ausgabezeiger auf die DSP-Bytebasis |
| r3 | Ausgabezeiger auf die PCM-Bytelänge |
| fünftes Stackargument | null bei Öffnen und WRITE, vollständige PCM-Extent |

Rückgabe eins bezeichnet einen gültigen geladenen Snapshot. Der
Deskriptor umfasst `0x494` Byte, davon `0x45C` Byte Metadaten; er enthält
keine PCM. Die zwölf zusätzlichen Bytes der Swap-Deskriptorfläche sind
kein Teil dieses nativen Deskriptors.

Die Bytes `0xC0345A20` und `0xC0345A28` werden bereits beim Öffnen der
Bearbeitung beziehungsweise der Slice-Vorbereitung gesetzt.
**Hergeleitet:** Sie belegen keine inhaltliche Änderung. Ein unverändertes
WRITE braucht einen Inhaltsvergleich, damit kein gleicher Block erneut
angehängt wird.

## Gemessen: Aufnahmebestätigung und Löschen

Ein Aufnahmeabschluss mit erzeugter PCM öffnet Fenster `0x2A` im
Transportzustand 12. WRITE bestätigt über denselben Auftrag `0x25`,
schließt das Fenster und erhält den neuen Slot. EXIT verwirft den
unbestätigten Slot über Auftrag `0x24`. ENTER bestätigt die Aufnahme nicht.
Dieser Versuch gibt PCM und Aufnahmeende im Modell vor; er beweist
keine echte Aufnahmequelle oder sämtliche Resampling-Varianten.

Beim Löschen eines bestehenden Samples öffnet das erste ENTER nur die
Bestätigung. EXIT daraus löscht nichts. Erst das zweite ENTER sendet
Auftrag `0x24` an `0xC0039588`. Über `0xC0035994` und `0xC004E558`
wird die aufgelöste physische Zeile als ungeladen markiert. Die Karte
bleibt im bisherigen Ablauf unverändert.

## Hergeleitet und im Modell geprüft: der alte Info-Spiegel

`0xC004FB6C` ist ein Spiegelabgleich und kein SD-Kartenschreiber. Er
vergleicht sechs Records aus Namen, drei Zuordnungstabellen, Wiedergabe
und Metadaten mit dem RAM-Spiegel ab `0xC0C9A940`. Bei Unterschieden
führt `0xC004C3D4` über `0xC002A218` und `0xC0029AB8` einen
640-KiB-Auftrag an den seriellen NOR-Flash aus: Bereich `0x6B0000`
bis `0x750000`, Ende ausschließlich.

Die Kennung `0x6B` wird um 16 Bit verschoben. Der volle Auftrag wurde
im Modell vor dem Schreiben beobachtet. Ein zusätzlicher erzeugter
4-KiB-Sektor wurde über denselben nativen Adapter geschrieben und
zurückgelesen: ein Löschen, 16 Programmierseiten und bytegleiche Daten.
Der Code ruft dazu `0xC001E7BC` und `0xC001E6B0` mit den SPI-Befehlen
`0x20` und `0x02` auf.

Die synthetischen Importschlüssel ab 500 überschreiten bereits den dort
gelesenen Grenzwert 500 und verlassen den Spiegelabgleich vorher. Ihr
ausbleibender Flashauftrag beweist keine allgemeine Flashfreiheit aller
Sample-Bearbeitungen. Der neue Kartenschreiber darf diesen alten
Flashpfad nicht als eigene Speicherung verwenden.

## Hergeleitet und gemessen: Parts und Stimmen

Die logische Auswahl steht am Part bei `+0x34`. Die geprüfte native
Part-Bindung speichert dort keinen dauerhaften Importschlüssel. Bei einer
ungeladenen Auswahl kann das Feld bereits den gewünschten Slot enthalten,
während der abgeleitete Sampletyp bei `+0x39` noch `0xFF` ist.

Die Importnummer bei `+0x40` gehört zur Stimme. Alte Stimmen behalten
dadurch ihre alte Zuordnung auch nach einer Namensumbindung. Das ersetzt
nicht die Prüfung ihrer tatsächlichen Lebensdauer am Gerät. Die allgemeine
native Part-Aktualisierung erwartet außerdem einen physischen Index;
ein logischer Slot darf ihr nicht ungeprüft übergeben werden.

## Offen

Die bestätigten Menüs sind noch nicht an den journalisierten Schreiber
angeschlossen. Versionszuordnung, laufende Reservierung freier
Importschlüssel und das Entfernen des Gesamtexports folgen gemeinsam.
Die genaue PCM-Reihenfolge beim Stereo-Rücklesen, sämtliche Slice- und
Rename-Bestätigungen sowie reales Aufnahme- und Resampling-DMA bleiben
gesondert zu prüfen. Der Projektcontainer bleibt zurückgestellt.
