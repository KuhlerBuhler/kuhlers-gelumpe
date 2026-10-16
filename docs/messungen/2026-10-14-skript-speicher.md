# Plugin Speicher: korg.store über die Karte

Stand 2026-10-14. Kein Gerätezugriff. Alles im
Emulator mit virtueller Karte und in Unicorn mit einem vorgetäuschten FatFs
geprüft. Markierungen: **gemessen**, **hergeleitet**.

## Umsetzung

- **API** (Vertrag, `since` 2, API Version 2): `korg.store.get(slot, vorgabe)`,
  `korg.store.set(slot, wert)`, `korg.store.save()`. 16 Plätze je Plugin, ein
  Platz gilt als belegt, sobald er gesetzt wurde (Maske im Eintrag). Ein Block,
  der keine der Funktionen nutzt, trägt weiter API Version 1 (gemessen im Test).
  Der Plugin-Eintrag wächst von 200 auf 268 Byte (Maske und 16 Werte).
- **Datei** (`src/script/store.mjs`, Vertrag `STORE`): `store.a.bin` und `store.b.bin`
  wechseln sich ab, Kopf mit `GSST`, Version, Anzahl, Generation und CRC-32,
  je Plugin ein Eintrag zu 84 Byte. Der Start liest beide, nimmt die neuere gültige
  Datei und gibt jedem geladenen Plugin seine Werte vor dem Rumpf.
- **Schreiben** (`tools/patch/script_store.s`): `save()` setzt nur ein Merkwort.
  Der Rahmenhaken schreibt, wenn es gesetzt ist, der Hauptbildschirm offen ist und
  seit dem letzten Schreiben 50 Rahmen vergangen sind: Bild der Einträge
  aktualisieren (unbekannte Einträge anderer Plugins bleiben, neue werden
  angehängt, höchstens 194), Generation erhöhen, CRC rechnen, `f_open` mit
  Neuanlegen, ein `f_write`, `f_close`. Ein Fehlschlag zählt `storeErrors`, kein
  Wiederholen. Das Bild liegt im Blockpuffer `0xC01F8000` (16 KiB).
- Regeln für den Kartenzugriff: `docs/patcher.md`, Abschnitt "Schreibregel für die Karte".

## Prüfungen (gemessen)

| Prüfung | Ergebnis |
|---|---|
| `test/script-store.test.mjs` (Datei, neuere Generation gewinnt, `get`/`set`/`save` in der Referenzlaufzeit, Plätze je Plugin getrennt, Version 2 nur mit Store) | 5 bestanden |
| `tools/patch/test_script_store.py` (Glue, Schreiben in die abwechselnden Dateien Byte für Byte gleich dem Browser Bauer, Pause, Hauptbildschirm, Fehlschlag, Fallback auf die ältere Generation, Einträge fehlender Plugins bleiben, Platz außerhalb) | 7 bestanden |
| Firmware im Emulator, Klicker mit Speicher von der Karte: ohne `save()` keine Datei, drei TAPs in 0,6 s ergeben ein Schreiben und nach der Pause das zweite (Generation 2, Wert 3), nach einem Neustart auf derselben Karte zeigt die Anzeige 3 (gleich dem Browsermodell), mit beschädigter neuerer Datei gilt die ältere | 5 Prüfungen `speicher-*` bestanden |

Damit ist im Emulator belegt, dass ein Zählerstand Aus- und
Einschalten über die Karte überlebt. Am Gerät nicht.

## Grenzen

- FatFs aus der UiTask: im Emulator ohne Folgen, am Gerät nicht geprüft. Ein
  Schreibvorgang auf einer echten Karte kann länger als ein Rahmen dauern;
  gemessen ist das nicht.
- Kein Schutz gegen gleichzeitigen Kartenzugriff der Firmware außer dem offenen
  Hauptbildschirm.
- Mit Karte ohne Plugin-Datei läuft keine Laufzeit und damit auch kein `store`.
