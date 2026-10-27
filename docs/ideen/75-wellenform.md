# 75. Wellenform beim Schneiden (rot)

Wunsch (27.10.): wenn man auf der roten Start und Ende eines Samples einstellt, zeigt das Display die Wellenform und den
gerade eingestellten Ausschnitt. Auf dem Hauptbildschirm und im Menü SAMPLE EDIT.

Geplant für 1.5, "The sample update" ([Fahrplan](../fahrplan.md)).

Stand 2026-10-27: **nur untersucht, nichts gebaut, kein Emulator- oder Gerätelauf.** Marker: **gemessen**, **hergeleitet**,
**ungeprüft**.

## Befund

- Hauptbildschirm: der Regler OSC EDIT (Regler 9) schreibt das Part-Byte `0xC06B2F9C + 0x330*part + 0x0B`, 0 bis 127
  (`data/map/pattern.mjs`). Dass es auf der roten START POINT ist, steht so im Korg-Handbuch. (gemessen / ungeprüft)
- SAMPLE EDIT ist Bildschirm 37, mit den Seiten 1/10 bis 10/10, darunter START POINT (`docs/messungen/2026-10-09-menuezustand.md`,
  `2026-10-22-sync-und-menues.md`). Welches Feld die offene Seite meldet, ist noch nicht gefunden. (gemessen / ungeprüft)
- Start, Loop und Ende je Sample stehen in der Abspieltabelle `0xC0362EE8 + i*0x10` (+0, +4, +8), die Länge in der
  Metadatentabelle `0xC036AD88 + i*0x45C` +4, Stereo +9 (`2026-10-07-sample-metadaten-ram.md`). Die Einheit ist nicht
  gemessen. (gemessen)
- **Das PCM liegt nach dem Laden nur im DSP.** Der Loader liest 64-KiB-Blöcke in einen Arbeitspuffer und schreibt sie per
  `0xC004EF28` in den DSP. Zurücklesen geht (rund 6 MiB/s), aber der Host-Port hat schon gehangen und es muss im
  Kommando-Task laufen (Messungen zu Sample Swap). (hergeleitet / gemessen)
- Zeichnen geht wie bei der Ladeanimation am Display-Hook `0xC008370C` in den Bildpuffer `0xC031B310`, vor dem Look.
  (gebaut für andere Patches)

## Vorschlag

- **Übersicht beim Laden:** am DSP-Schreibaufruf des Loaders (`0xC003631C`, `0xC00363E0`) je Sample 128 Spitzenwerte aus dem
  Block berechnen, solange er im ARM-RAM liegt. 1000 Samples x 128 Byte = 128 KB im freien RAM. Kein Extra-Lesen von Karte
  oder DSP. Sample Swap lädt über denselben Weg, ist also mit abgedeckt.
- **Hauptbildschirm:** dreht man START POINT, kommt für etwa 1,5 s ein Fenster mit der Wellenform (gespiegelte Spitzen), einer
  Linie am Startpunkt und dem abgeschnittenen Teil ausgegraut.
- **SAMPLE EDIT:** auf den Seiten START, LOOP und END bleibt die Wellenform stehen, mit drei Markern; der Text der Firmware
  bleibt oben. Kein Zoom in der ersten Fassung.
- Nur rot (Sampler, Korg und Hacktribe).

## Plan

1. Emulator: Seitenfeld von SAMPLE EDIT finden, Einheit von Start und Ende und die Abbildung 0 bis 127 auf das Sample messen.
2. Übersicht am Loader, Prüffall gegen die Kartendatei.
3. Zeichenroutine am Display-Hook, passend zum Look.
4. Auslöser Hauptbildschirm, dann SAMPLE EDIT.
5. `check.py` für die roten Builds mit neuen Fällen.

## Risiken

- Codeplatz ist knapp, neuer Code in den dritten Bereich ab `0xC0188A00`.
- Der 128-KB-Puffer darf sich nicht mit den Puffern von Sample Swap ab `0xC274F000` überschneiden.
- Der Start wird durch die Spitzenberechnung etwas langsamer.
- 24-Bit-WAVs werden im Puffer vor dem Schreiben auf 16 Bit gewandelt, die Spitzen erst danach nehmen.

## Am Gerät zu testen

- Startzeit mit und ohne Patch.
- Wellenform gegen die Datei für 3 Samples, mono und stereo.
- START POINT drehen, während das Pattern spielt: Knackser? Geht das Fenster wieder weg?
- SAMPLE-EDIT-Seiten, Laden über Sample Swap, zusammen mit Blechy und dem Look.
