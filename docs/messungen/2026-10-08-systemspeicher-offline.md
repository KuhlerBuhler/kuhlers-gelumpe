# Task-Stacks, Heap und Arbeitsbuffer, offline gemessen

Stand 8. Oktober 2026. Neue Untersuchung der originalen ARM-Initialisierung
und Speicherverwaltung aus dem vorhandenen CPU-Dump; keine Gerätebefehle.
Der Dump ist zeitlich zusammengesetzt, SHA256
`c114f10457b1dabc3ad6f8694aa3af9be63c5429da627c6358490ce781e0f26a`.
Intervalle sind halb offen, Endadressen nicht enthalten.

## Zehn Task-Stacks

**Gemessen offline:** Task-Anzahl 10 bei 0xC00A38E8, ID-Liste ab
0xC00A3780, zehn Deskriptoren à 32 Byte ab 0xC00A37A8. Je Deskriptor:
+8 Einstieg, +12 Priorität, +16 Stackgröße, +20 Stackbasis.
Die Runtime-Kontrollblöcke liegen ab 0xC06A24E4, ebenfalls 32 Byte je Task;
+8 zeigt zum Deskriptor, +24 trägt einen Stackzeiger.

**Gemessen offline:** Routine 0xC00003D8 lädt Größe und Basis, berechnet
Stackende, legt Einstieg bei Ende-4 und Startargument bei Ende-8 ab und
setzt den gespeicherten Zeiger auf Ende-8. Die Routine einschließlich
Ready-Queue-Einreihung 0xC00018F0 wurde in Unicorn für alle zehn
Deskriptoren ausgeführt. Für den Initialisierungstest waren Queues und
Kontrollblöcke bewusst neu initialisiert. Kein Task wurde gestartet.

| Task-ID | Stackstart | Ende exklusiv | Byte | Einstieg |
|---|---|---|---:|---|
| 1 | `0xC0200000` | `0xC02023A8` | 9,128 | `0xc002ab7c` |
| 2 | `0xC02023A8` | `0xC02047A8` | 9,216 | `0xc002aa34` |
| 3 | `0xC02047A8` | `0xC0208FA8` | 18,432 | `0xc002a3c0` |
| 4 | `0xC0208FA8` | `0xC020B3A8` | 9,216 | `0xc002b144` |
| 5 | `0xC020B3A8` | `0xC030B3A8` | 1,048,576 | `0xc002a598` |
| 6 | `0xC030B3A8` | `0xC030D7A8` | 9,216 | `0xc00245f0` |
| 7 | `0xC030D7A8` | `0xC030FBA8` | 9,216 | `0xc002c980` |
| 8 | `0xC030FBA8` | `0xC0311FA8` | 9,216 | `0xc001da9c` |
| 9 | `0xC0311FA8` | `0xC03143A8` | 9,216 | `0xc002b220` |
| 10 | `0xC03143A8` | `0xC03167A8` | 9,216 | `0xc002aacc` |

**Gemessen offline:** Alle zehn Bereiche grenzen lückenlos aneinander,
vereint `[0xC0200000, 0xC03167A8)`, 1.140.648 Byte. Alle gespeicherten
Stackzeiger im vorhandenen Dump liegen im jeweiligen beschriebenen
Stackbereich; alle Runtime-Deskriptorzeiger stimmen mit der statischen
Tabelle überein. Task 5 reserviert einen auffällig großen Stack von 1 MiB;
der tatsächliche Hochwasserstand wurde nicht bestimmt.

**Vermutet/offen:** Task-Namen/Funktionen und weitere IRQ-/CPU-Modus-/
Loader-Stacks sind nicht abschließend zugeordnet. Die Tabelle belegt
keine ausschließliche Besitzzuordnung jedes Bytes und keine maximale
spätere Stacktiefe. Die Bereiche sind kein freier Uploadspeicher.

## Heap für die untersuchte C++-Allokation

**Gemessen offline:** New-Wrapper 0xC0028DCC → 0xC0008F30 → Allocator
0xC0008F70. Delete-Wrapper 0xC0028DD4 → 0xC0008F50 → 0xC000EE6C.
Heapwachstum läuft über 0xC000A3B0 → 0xC002CEFC.

**Gemessen offline:** 0xC002CEFC initialisiert den Cursor bei 0xC03404AC
mit 0xC06A2940. Der Code vergleicht den neuen Cursor mit 0xC08A2940.
Damit ist der vorgesehene Pool `[0xC06A2940, 0xC08A2940)`, 2.097.152
Byte. Snapshot-Cursor 0xC06CE000 liegt darin. Freilisten-/Allocator-
Verwaltung liegt zusätzlich außerhalb des Pools, u. a. bei 0xC00F8E60;
auch diese Strukturen sind kein editierbarer Parameterbereich.

**Gemessen offline:** Fünf Tests der unveränderten Wachstumsroutine:
Initialisierung +8 Byte, exaktes Füllen bis zur Obergrenze, ein Byte über
vollem Pool (Rückgabe 0, Cursor unverändert), Wachstum vom Snapshot-Cursor
um 4.096 Byte sowie negativer Schritt -8 direkt an der Basis. Im letzten
Fall unterschreitet der Cursor die Basis: die Routine prüft hier die obere,
aber keine untere Grenze. Das ist ein Nachweis dieses Aufrufverhaltens,
keine Aussage, dass reguläre Allocator-Aufrufe diese Vorbedingung verletzen.

**Gemessen offline:** Sechs originale New-/Delete-Aufrufe für 1, 16,
524, 1.172, 4.096 und 65.536 Byte. Alle Rückgaben liegen mit der
angeforderten Nutzlänge im Pool, Beschreiben künstlicher Nutzdaten und
Freigabe kehren zurück. Die Heap-Locks waren für diesen isolierten Test
über das bestehende Enable-Flag bei 0xC03404B0 deaktiviert. Daher kein
Nachweis der Threadsicherheit oder des Verhaltens bei Speichermangel
im vollständigen Allocator.

**Schutzvorschlag:** Gesamten Pool und Verwaltungsdaten gegen generische
Writes sperren. Ein zurzeit freier Heapblock bleibt Eigentum der
Speicherverwaltung. Keine direkte Cursoränderung, keine unvalidierten
Argumente für Reservierungs-/Freigabefunktionen.

## Großer Datei-/Sample-Arbeitspuffer

**Gemessen offline:** Puffergeber 0xC00369F0 tatsächlich ausgeführt:
Rückgabe 0xC0D3A940, ausgegebene Kapazität 0x01A00100 = 27.263.232 Byte.
Beschriebenes Intervall `[0xC0D3A940, 0xC273AA40)`. Die bereits geprüften
Import-/Exportpfade nutzen daraus insbesondere 65.536-Byte-Transfers.

**Gemessen offline:** Die bereits bekannten Hook-/Flash-Staging-Adressen
0xC1000000 und 0xC2000000 liegen beide innerhalb dieses angegebenen
Intervalls. **Vermutet/offen:** Ob ihre Nutzung zeitlich zuverlässig von
Import/Export getrennt wird, ist ungeklärt; mögliche Überschneidungen
müssen vor einem eigenen Helfer ausgeschlossen werden.

**Vermutet/offen:** Diese Kapazitätsangabe belegt keine exklusive Belegung
jedes Bytes zu jedem Zeitpunkt. Weitere Nutzer, Lebensdauer und alle
Unterbereiche sind offen. Trotzdem keine Freigabe als angeblich leerer
Uploadbereich. Der Name Arbeitsbuffer ist keine PCM-Speicherbasis.

[Speicherkarte und Schutzgrenzen](../speicherbereiche.md).
Rohdaten und Emulator-Fixtures bleiben außerhalb des Repositories.
