# Sample-Swap: Schutzcode und Dateibesitz verbunden

Stand: 04.11.2026. **Gemessen im ARM-Modell und Emulator**, ohne Gerät,
Klang oder DMA. Alle Testdaten werden erzeugt. Eigene Firmwaredateien und
ausführliche Prüfprotokolle bleiben außerhalb des Repos.

## Hergeleitet: Herkunft und Umfang

Der Schutzstand aus PR 309 ist seit der
[Schutzprüfung](2026-10-31-sample-swap-schutz-review.md) unverändert.
Die relevante Quelländerung nach dessen Develop-Merge wurde mit dem
[gemeinsamen Dateibesitz](2026-10-31-sample-dateibesitz.md) verbunden.
Generierte Patchblöcke und die fremde Verifikationsdatei wurden nicht übernommen.
Ein weiterer Develop-Merge war dafür nicht nötig.

Der gemeinsame Stand enthält die Export-Sperre bei aktivem oder fehlerhaftem
Swap, die ursprünglichen Zeilensignaturen, die eingegrenzten nativen
DSP-Wartepfade und die Journal-Unterscheidung beim Öffnen. Die vorhandenen
Funktionen `catalogue_begin/end` und die exklusive Dateisperre bleiben erhalten.

## Gemessen: Bau und lokale Prüfung

Beide roten Originale erzeugen dieselbe Patchdatei. Das gesamte BLECH-Patchset
lässt sich mit den Hook- und RAM-Prüfungen auf beide Originale anwenden.
Die gezielte Modellprüfung von Swap, Dateibesitz und Snapshot besteht;
Firmwarefälle ohne gesetzte Eingabedatei wurden dabei ausgelassen und zählen
nicht als native Prüfung.

`npm test` besteht mit 1365 erfolgreichen und 161 ausgelassenen Tests, ohne
Fehler. Die ausgelassenen Tests zählen nicht als Firmwareprüfung.
Die gezielten nativen Prüfungen bestehen auf beiden roten Builds:

| Prüfung | Stock | Hacktribe |
|---|---:|---:|
| Startprüfung des gesamten Patchsets | 21 | 21 |
| Start, Export, Speicherdienste und Leserabschluss | 24 | 24 |
| Mono-/Stereo-Snapshot einschließlich neu belegter physischer Zeile | 8 | 8 |

Keiner dieser nativen Fälle wurde ausgelassen. Eine zusätzliche Prüfung des
Integrationsdiffs findet keinen neuen Fehler durch die Zusammenführung.
`npm run test:e2e` besteht mit 285 erfolgreichen und einem ausgelassenen
Test, ohne Fehler. Die vollständige native Release-Prüfung aller drei
Originale bleibt offen; `verified.json` wurde
nicht als Nachweis für den geänderten Stand übernommen oder erneuert.

Folgende Aufrufe gehören zu dieser Prüfung; die Firmwarevariablen bezeichnen
ausschließlich externe eigene Dateien:

```sh
python3 tools/patch/sample_swap.py --vsb "$E2_STOCK_VSB" --out "$SWAP_STOCK_JSON"
python3 tools/patch/sample_swap.py --vsb "$E2_HACKTRIBE_VSB" --out "$SWAP_HACKTRIBE_JSON"
cmp "$SWAP_STOCK_JSON" "$SWAP_HACKTRIBE_JSON"
node --test test/sample-swap.test.mjs test/sample-owner.test.mjs test/sample-snapshot.test.mjs
npm test
npm run test:e2e
tools/emu/.venv/bin/python tools/emu/swap_cases.py cases --patched "$SWAP_PATCHED" --group 0 --group 10 --group 19 --group 20
tools/emu/.venv/bin/python tools/emu/sample_snapshot_cases.py --patched "$SWAP_PATCHED"
```

Die nativen Aufrufe werden für beide roten Builds ausgeführt. Gruppe 0 prüft
kleine Sammlung, bedarfsgesteuerten Start und EXIT. Gruppe 10 prüft den
Cache-Besitz beim Gesamtexport. Gruppe 19 prüft die Speicherdienste mit nativer
FatFs, Gruppe 20 den Leserabschluss. Die Speicherdienste sind weiterhin nicht
mit allen normalen Sample-Menüs verbunden. Zusätzlich läuft `check.py --quick`
mit den aus dem gesamten Patchset erzeugten erlaubten Startbereichen.

## Gemessen: Gegenproben am verbundenen Code

Die bisherigen hohen Verdrängungsbefunde bestehen weiterhin:

| Gegenprobe | Ergebnis |
|---|---|
| `PLAYBACK + 600 * 16 + 4` von 0 auf 256 | Signatur unverändert; Slot 600 bleibt verdrängbar |
| Slots 600 und 601 auf physischer Zeile 600, Name von 601 geändert | 601 gilt als geändert; über 600 bleibt dieselbe Zeile verdrängbar |

Die Gegenproben verwenden eigene Tabellen im ARM-Modell. Sie sind ausdrücklich
keine bestandenen Schutzprüfungen und keine Messung am Gerät.

## Offen: Schutzkorrekturen und Gerätefreigabe

Die Verbindung behebt die bereits gemessenen Schutzlücken noch nicht:
Wiedergabepunkte fehlen in der Signatur, ein sauberer Alias kann eine geänderte
gemeinsame Belegung freigeben, und nicht alle Journalfehler verhindern das
erneute Laden. Die Zuordnung der DSP-Frist nach wartendem Ressourcenerwerb
und der Übergang einer kleinen Sammlung zu aktivem Swap bleiben ebenfalls offen.

Vor einem Geräteprototyp müssen diese Fehler geschlossen und die RAM-Nutzung
in allen vorgesehenen Modi einschließlich realer DMA-Zugriffe belegt sein.
Es erfolgten weder Gerätezugriff noch Installation, Push oder Merge.
