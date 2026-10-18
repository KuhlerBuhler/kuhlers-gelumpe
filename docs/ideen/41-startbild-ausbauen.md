# Idee 41: Startbild ausbauen

Stand: das statische Bild ist gebaut und am Gerät gesehen; Ladebalken, wandernde Augen und die kleinen Gesichter am Rand sind gebaut und im Emulator geprüft, am Gerät nicht. Zurück zu den [Ideen](../ideen.md).

## Das Bild

Das Startbild „splash“: der Schriftzug „BLECH“ mittig als fettes Graffiti (Impact), darüber die aufgerissenen Terror-Augen (dieselben wie bei Blechy, Idee 40), dazu ein ganz blasses „Kuhler's“ als Hintergrund hinter den Augen.

Als statisches 1-Bit-Bild liegt es in `assets/blechy/` (`splash.png`, `splash.bin`, der fertige Patch `splash.json`, gegen `src/patch.mjs` per Round-Trip geprüft, `test/blech-splash.test.mjs`). Es gehört zum Patch-Satz BLECH (`data/patches/blech.json`). Am Gerät erscheint es als Datenpatch ([MFX 2 am Gerät](../messungen/2026-10-13-mfx-umschalter-geraet.md)). Ein reiner Datenpatch wie Idee 20, im Emulator sofort prüfbar.

Graustufen gibt es nicht, das Display ist hart 1-Bit. „Schwach“ geht nur über Dithering (dünnes Bayer-Punktmuster), so entsteht das blasse „Kuhler's“, und so wären spätere Verläufe möglich.

## Animierter Ladescreen (gebaut)

Der Unterstrich unter BLECH ist der Fortschrittsbalken, während die `e2sSample`-Datei beim Start lädt, und die Augen wandern dabei hin und her (Patch `data/patches/load-bar.json`, [Messung](../messungen/2026-10-15-ladebalken.md)). Dazu blenden kleine Gesichter (8 mal 9 Pixel, eigene Zeichnung) kurz am linken und rechten Rand ein und wieder aus, eins nach dem anderen, jedes Mal an einem anderen der vier Plätze; das Einblenden ist ein geordnetes 4-mal-4-Raster (vier Stufen hoch und zurück), es gibt kein Grau. Nur beim BLECH-Bild, nur während des Ladens, nie auf den Rettungswegen und nie mit EXIT beim Einschalten ([Bild](../images/blech-ladebalken-gesicht.png)). Dasselbe Augen- und Gesichter-Motiv kann auf anderen Screens vorkommen (das hängt mit Blechys zufälligem Vorbeikommen zusammen, Idee 40).

Weitere Möglichkeiten: invertiert, mehrere Bilder als Animation, Farbe über das RGB-Licht pro Bild (Idee 37). Eine Animation, die zusätzlich Zeit kostet, verlängert den Start; die gebaute läuft nach den Rettungswegen, wie bei Idee 35, und kostet nach der Messung keine Zeit (mit den Gesichtern: Lader 1160,6 gegen 1157,1 ms mit EXIT, ohne Gesichter 1160,2 ms).

## Ladebalken statt „Loading nnn%“ (gebaut)

Das Startbild bleibt stehen, solange beim Start die Samples geladen werden, und der Balken ersetzt die Anzeige „Loading nnn%“. Vier Haken: die Frage der Firmware nach der `e2sSample.all` (merkt, dass ein Laden kommt, nur auf dem normalen Weg nach den Rettungswegen), der Lade-Fortschritt im Lader `0xC00364F0` (er läuft in einer eigenen Task neben der Oberfläche), das Ende des Laders und das Senden des Rahmens, in dem Bild, Balken und Augen direkt in den Bildspeicher der Firmware gelegt werden.

Die erste Fassung hat das Bild je Rahmen mit der Zeichenroutine der Firmware gezeichnet (2,5 Millionen Befehle) und den Start um 59 Prozent verlängert; die gebaute Fassung braucht rund 6300 Befehle je Rahmen und lässt den Start so lang wie ohne den Patch (1518,5 gegen 1518,6 ms im Emulator). Ohne Karte, ohne `e2sSample.all` und mit EXIT beim Einschalten läuft nichts davon. Ein anderes Startbild, etwa ein gezeichnetes, ist vom Einschalten bis zum Beginn des Ladens zu sehen; während die Samples laden, zeigt der Patch sein eigenes BLECH-Bild mit Balken und Augen (Gerät 18.10.: vorher erkannte er das BLECH-Bild an der CRC, und schon ein geändertes Pixel ließ die Augen stehen). Die Augen fahren schnell los und bremsen am Ende ab (Ease-out).
