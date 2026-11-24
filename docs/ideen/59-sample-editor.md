# 59. Sample-Editor am Gerät

Status: offen, nichts gebaut. Zurück zu den [Ideen](../ideen.md).

Wunsch: Ein Sample am Gerät bearbeiten, ohne Rechner. Das Sample kommt ins RAM, dort wird es geschnitten,
normalisiert, umgedreht, ein- und ausgeblendet, danach geht es zurück auf seinen Platz.

## Was wir wissen

| Aussage | Status |
|---|---|
| Über `0xC1010000` bis `0xC4000000` (rund 47 MiB) hat die Firmware beim Spielen nur einen 4-KiB-Block angefasst, einen Task-Stack bei `0xC274E000` | gemessen am Gerät ([RAM frei](../messungen/2026-10-22-ram-frei.md)) |
| Import und Export nutzen einen Arbeitspuffer von 26 MiB, `0xC0D3A940` bis `0xC273AA40`. Er liegt zum großen Teil im gemessenen Bereich, Import und Export liefen bei der Messung nicht | gemessen im Emulator ([Systemspeicher](../messungen/2026-10-08-systemspeicher-offline.md)) |
| Darüber, von `0xC273AA40` bis `0xC4000000`, bleiben rund 24,8 MiB, die auch Import und Export nicht als Puffer nutzen (bis auf den Stack bei `0xC274E000`) | hergeleitet |
| Die Samples spielt der [DSP](../glossary.md#dsp) aus seinem eigenen Speicher; wie sie beim Start dorthin kommen, ist nicht gemessen | hergeleitet ([DSP, erster Blick](../hintergrund/dsp-erster-blick.md)) |
| Name und Tune eines Samples lassen sich im RAM ändern | gebaut (Seite Samples im Editor, [Gerätekarte](../geraetekarte.md)) |

## Wege

| Weg | Aufwand |
|---|---|
| **Über die Karte:** das Sample als Datei von der Karte ins RAM lesen (Dateifunktionen der Firmware, siehe [Virtuelle SD-Karte](../hintergrund/virtuelle-sd.md)), bearbeiten, als neue Datei schreiben und über den Importweg der Firmware auf einen Platz laden | mittel: Lesen, Schreiben und Import sind einzeln im Emulator gemessen, die Kette nicht |
| **Direkt aus dem DSP:** die PCM-Daten über den [Host-Port](../glossary.md#host-port) aus dem DSP holen und wieder hineinschreiben | groß: wo und wie der DSP ein Sample ablegt, ist nicht gemessen ([DSP, erster Blick](../hintergrund/dsp-erster-blick.md)) |

Bearbeiten lässt sich im RAM ohne Eile: ein Sample in voller Länge passt mehrfach in den freien Bereich, ein Rückgängig
ist damit eine Kopie.

## Offen

- Wohin der Editor im Menü gehört: zu SAMPLE EDIT der Firmware oder als eigener Punkt in BLECH.
- Die Bedienung am Display: Wellenform auf 128 x 64 Pixeln, Start und Ende auf den Reglern.
- Ob der Arbeitspuffer frei ist, solange kein Import läuft. Dann reichen auch die 26 MiB darin, sonst nur der Bereich darüber.
- Die offenen Punkte der [RAM-Messung](../messungen/2026-10-22-ram-frei.md): der Stack bei `0xC274E000` und ein langer Lauf.

## Wellenform beim Schneiden (rot)

Wunsch: beim Einstellen von Start und Ende eines Samples zeigt das Display die Wellenform und den eingestellten Ausschnitt, auf dem Hauptbildschirm und in SAMPLE EDIT. Nur untersucht, nichts gebaut. Marker: **gemessen**, **hergeleitet**, **ungeprüft**.

### Befund

- Hauptbildschirm: der Regler OSC EDIT (Regler 9) schreibt das Part-Byte `0xC06B2F9C + 0x330*part + 0x0B`, 0 bis 127
  (`data/map/pattern.mjs`). Dass es auf der roten START POINT ist, steht so im Korg-Handbuch. (gemessen / ungeprüft)
- SAMPLE EDIT ist Bildschirm 37, mit den Seiten 1/10 bis 10/10, darunter START POINT (`docs/messungen/2026-10-09-menuezustand.md`,
  `2026-10-22-sync-und-menues.md`). Welches Feld die offene Seite meldet, ist noch nicht gefunden. (gemessen / ungeprüft)
- Start, Loop und Ende je Sample stehen in der Abspieltabelle `0xC0362EE8 + i*0x10` (+0, +4, +8), die Länge in der
  Metadatentabelle `0xC036AD88 + i*0x45C` +4, Stereo +9 (`2026-10-07-sample-metadaten-ram.md`). Die Einheit ist nicht
  gemessen. (gemessen)
- **Das PCM liegt nach dem Laden nur im [DSP](../glossary.md#dsp).** Der Loader liest 64-KiB-Blöcke in einen Arbeitspuffer und schreibt sie per
  `0xC004EF28` in den DSP. Zurücklesen geht (rund 6 MiB/s), aber der [Host-Port](../glossary.md#host-port) hat schon gehangen und es muss im
  Kommando-Task laufen (Sample Swap). (hergeleitet / gemessen)
- Zeichnen geht wie bei der Ladeanimation am Display-Hook `0xC008370C` in den Bildpuffer `0xC031B310`, vor dem Look.
  (gebaut für andere Patches)

### Vorschlag

- **Übersicht beim Laden:** am DSP-Schreibaufruf des Loaders (`0xC003631C`, `0xC00363E0`) je Sample 128 Spitzenwerte aus dem
  Block berechnen, solange er im ARM-RAM liegt. 1000 Samples x 128 Byte = 128 KB im freien RAM. Kein Extra-Lesen von Karte
  oder DSP. Sample Swap lädt über denselben Weg, ist also mit abgedeckt.
- **Hauptbildschirm:** dreht man START POINT, kommt für etwa 1,5 s ein Fenster mit der Wellenform (gespiegelte Spitzen), einer
  Linie am Startpunkt und dem abgeschnittenen Teil ausgegraut.
- **SAMPLE EDIT:** auf den Seiten START, LOOP und END bleibt die Wellenform stehen, mit drei Markern; der Text der Firmware
  bleibt oben. Kein Zoom in der ersten Fassung.
- Nur rot (Sampler, Korg und Hacktribe).

## Time-Stretch am Gerät

Das Tempo eines Samples ändern, ohne dass sich die Tonhöhe ändert (etwa ein 128-BPM-Loop auf 145 BPM). Pitch ändert heute
die Abspielgeschwindigkeit, Tonhöhe und Länge ändern sich dabei gemeinsam. Ob ein Regler oder das BPM den Faktor vorgibt:
Tempo ohne Tonhöhe ist der eigentliche Time-Stretch (Urteil).

Gedacht ist eine manuelle Bedienung: SHIFT + EDIT-Regler streckt oder staucht das Sample im Pattern, bedient wie Pitch.
Am Regler drehen und sofort hören heißt Stretch in Echtzeit im [DSP](../glossary.md#dsp), die schwerste Stufe.

### Reihenfolge

1. **Offline mit manuellem Faktor:** SHIFT + Regler stellt den Faktor ein (etwa 85 bis 115 %), das Gerät rechnet das Sample
   einmal neu und spielt die neue Fassung.
2. **Offline mit BPM:** Ausgangs- und Zieltempo statt Faktor, im Sample-Editor (dem Sample-Editor).
3. **Live:** der Loop folgt beim Spielen dem Tempo oder dem Regler, wie die Stretch-Parts der Electribe SX. Braucht
   Rechenzeit im DSP.

Stand der Untersuchung ([Time Stretch](../messungen/2026-11-17-time-stretch.md)): offline auf dem ARM ist ein
WSOLA-Verfahren in Festkomma machbar, live ohne DSP-Patch nicht in brauchbarer Qualität, live mit DSP-Patch unklar, weil
offen ist, ob bei vollem Pattern Rechenzeit frei ist. Ob Stufe 1 und 3 auf dem Gerät gehen (Qualität, Rechenzeit,
Speicher), ist nicht geprüft.
