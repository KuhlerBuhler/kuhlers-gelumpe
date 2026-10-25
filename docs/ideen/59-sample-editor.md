# 59. Sample-Editor am Gerät

Wunsch vom 24.10.: Ein Sample am Gerät bearbeiten, ohne Rechner. Das Sample kommt ins RAM, dort wird es geschnitten,
normalisiert, umgedreht, ein- und ausgeblendet, danach geht es zurück auf seinen Platz.

## Was wir wissen

| Aussage | Status |
|---|---|
| Über `0xC1010000` bis `0xC4000000` (rund 47 MiB) hat die Firmware beim Spielen nur einen 4-KiB-Block angefasst, einen Task-Stack bei `0xC274E000` | gemessen am Gerät ([RAM frei](../messungen/2026-10-22-ram-frei.md)) |
| Import und Export nutzen einen Arbeitspuffer von 26 MiB, `0xC0D3A940` bis `0xC273AA40`. Er liegt zum großen Teil im gemessenen Bereich, Import und Export liefen bei der Messung nicht | gemessen im Emulator ([Systemspeicher](../messungen/2026-10-08-systemspeicher-offline.md)) |
| Darüber, von `0xC273AA40` bis `0xC4000000`, bleiben rund 24,8 MiB, die auch Import und Export nicht als Puffer nutzen (bis auf den Stack bei `0xC274E000`) | hergeleitet |
| Die Samples spielt der DSP aus seinem eigenen Speicher; wie sie beim Start dorthin kommen, ist nicht gemessen | hergeleitet ([DSP, erster Blick](../hintergrund/dsp-erster-blick.md)) |
| Name und Tune eines Samples lassen sich im RAM ändern | gebaut ([Idee 6](../ideen.md)) |

## Wege

| Weg | Aufwand |
|---|---|
| **Über die Karte:** das Sample als Datei von der Karte ins RAM lesen (Dateifunktionen der Firmware, siehe [Idee 38](38-samples-ueber-kabel.md)), bearbeiten, als neue Datei schreiben und über den Importweg der Firmware auf einen Platz laden | mittel: Lesen, Schreiben und Import sind einzeln im Emulator gemessen, die Kette nicht |
| **Direkt aus dem DSP:** die PCM-Daten über den Host-Port aus dem DSP holen und wieder hineinschreiben | groß: wo und wie der DSP ein Sample ablegt, ist nicht gemessen ([Idee 26](26-dsp-erfassen.md)) |

Bearbeiten lässt sich im RAM ohne Eile: ein Sample in voller Länge passt mehrfach in den freien Bereich, ein Rückgängig
ist damit eine Kopie.

## Offen

- Wohin der Editor im Menü gehört: zu SAMPLE EDIT der Firmware oder als eigener Punkt in BLECH.
- Die Bedienung am Display: Wellenform auf 128 x 64 Pixeln, Start und Ende auf den Reglern.
- Ob der Arbeitspuffer frei ist, solange kein Import läuft. Dann reichen auch die 26 MiB darin, sonst nur der Bereich darüber.
- Die offenen Punkte der [RAM-Messung](../messungen/2026-10-22-ram-frei.md): der Stack bei `0xC274E000` und ein langer Lauf.
