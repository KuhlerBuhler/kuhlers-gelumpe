# Eigene Ladeanimation: das Dateiformat

Stand 28.10.2026, [Idee 71](../ideen/71-ladeanimation-karte.md). Gebaut sind Kodieren, Dekodieren, Prüfen
(`src/loading-anim.mjs`), der Dekoder in Python für die Emulator-Fälle (`tools/patch/loading_anim.py`), ein GIF-Dekoder für
den Import (`src/gif.mjs`) und das Abspielen in der Firmware (`tools/patch/load_bar.py`, Hacktribe und rot). Die App
macht die Datei im Bereich Design und schreibt sie beim Patchen in den Slot (siehe unten), am Gerät ist nichts geprüft.

## Bilder

Ein Bild ist der Frame-Buffer, wie ihn der Ladebalken heute zeichnet (`tools/patch/load_bar.py`): 8 Seiten zu 128 Byte,
Bit 0 ist die oberste Zeile einer Seite, ein gesetztes Bit leuchtet auf dem invertierten Display (DISPLAY INVERT ON).
Ist DISPLAY INVERT aus, invertiert der Patch das Bild selbst, wie heute.

`pixelsToFrame` wandelt Pixel in der Form des Startbilds (Zeile für Zeile, 1 = gezeichnet, also dunkel, wie `toMono`
sie liefert) in so ein Bild: Bits gespiegelt und invertiert gegenüber `pixelsToSplash`.

## Aufbau

Alle Zahlen little endian.

| Offset | Größe | Inhalt |
|---|---|---|
| 0 | 4 | `BLLA` |
| 4 | 1 | Version, 1 |
| 5 | 1 | Schleife ab Prozent: 0 heißt, sie spielt, wenn der Fortschritt steht; 1 bis 100 heißt, ab diesem Prozent |
| 6 | 2 | N, Fortschritts-Bilder (mindestens 1, Bild 0 mitgezählt) |
| 8 | 2 | M, Schleifen-Bilder |
| 10 | 2 | Offset der Listentabelle (heute 1040) |
| 12 | 4 | Größe der Datei |
| 16 | 1024 | Bild 0, voll |
| Tabelle | 2 je Liste | N - 1 + M Offsets ab Dateianfang: erst Fortschritt 1 bis N - 1, dann Schleife 0 bis M - 1 |

Eine Liste ist ein u16 mit der Anzahl Läufe, danach die Läufe. Ein Lauf ist ein u16-Kopf (Bits 0 bis 9 Offset im Bild,
Bits 10 bis 15 Länge minus 1, also 1 bis 64 Byte), danach die neuen Bytes. Läufe und Listen liegen ohne Ausrichtung,
gelesen wird byteweise (`ldrb`).

## Was die Listen bedeuten

- Fortschritts-Bild k ist Bild k - 1 mit Liste k darübergeschrieben. Die Firmware geht nur vorwärts: vom zuletzt
  gezeigten Bild bis zum Ziel wendet sie die Listen nacheinander an.
- Schleifen-Bild j ist das gerade gezeigte Fortschritts-Bild mit Schleifen-Liste j darübergeschrieben. Schleifen-Listen
  sind gegen Bild 0 gerechnet (bei Schleife ab Prozent P gegen das Fortschritts-Bild von P) und bauen nicht aufeinander auf. Die Firmware kopiert in jedem Rahmen ihren
  Fortschritts-Puffer ins Display und schreibt die Schleifen-Liste darüber; der Puffer selbst bleibt unberührt. So
  braucht die Schleife keinen zweiten Puffer, kann an jedem Fortschritts-Bild beginnen und zurück zum Fortschritt geht
  ohne Rest. Folge: Bytes, die im Schleifen-Bild gleich Bild 0 sind, zeigen das aktuelle Fortschritts-Bild.

## Warum Läufe statt Paaren

Ein Paar (Offset u16, Wert u8) kostet 3 Byte je geändertem Byte. Animationen ändern meist zusammenhängende Spalten einer
Seite, ein Lauf kostet dort 2 Byte Kopf plus 1 Byte je Wert. Ein einzelnes gleiches Byte zwischen zwei Änderungen
schreibt der Encoder mit (1 Byte statt 2 für einen neuen Kopf). Ein voll invertiertes Bild kostet so 16 Läufe zu
66 Byte, 1058 Byte mit Zähler, statt 3074. Das Dekodieren in ARM bleibt kurz: zwei `ldrb`, `orr`, Länge per `lsr #10`,
Offset per `bic`, dann eine Kopierschleife. 10 Bit Offset heißt: ein Offset über 1023 lässt sich gar nicht schreiben,
geprüft wird nur, dass der Lauf nicht über Byte 1023 hinaus schreibt.

## Welches Bild wann

Der Fortschritt läuft in Promille p (0 bis 999, 1000 erst wenn der Loader fertig ist). Gezeigt wird Fortschritts-Bild
p * (N - 1) / 1000, abgerundet (`progressIndex`, `loading_anim.progress_index`): das letzte Bild also erst am Ende. Die
Schleife spielt nach Zeit, ein Bild alle 96 ms: mit Byte 5 = P ab P Prozent und beim Fertig, mit Byte 5 = 0 wenn der
Fortschritt 500 ms stand (`load_bar.STALL_MS`).

## Prüfung vor dem ersten Bild

Was die Firmware prüft (`validateAnimation`, `loading_anim.validate`), jede Abweichung heißt Standard-Blechy:

1. Magic `BLLA`.
2. Version 1, Schleife ab höchstens 100 Prozent.
3. Größe höchstens 16384 Byte (`MAX_BYTES`, Vorschlag, nicht gemessen).
4. N mindestens 1, die Tabelle liegt hinter Bild 0 und innerhalb der Datei.
5. Jede Liste und jeder Lauf liegt innerhalb der Datei, kein Lauf schreibt über Byte 1023 hinaus.

Die Prüfung läuft einmal über alle Listen, ihre Kosten wachsen höchstens mit der Dateigröße.

## In der Firmware

Der Bereich `0xC01A6000` bis `0xC01ADF00` war bis 1.3.7 die erste Code-Fläche der Plugin-Laufzeit und ist seitdem frei
(`FF` in allen drei Abbildern, Sample Swap nutzt ihn nicht). Auf Hacktribe und rot gehört er jetzt dem Ladebalken, auf
blau bleibt er Reserve der Laufzeit:

| Bereich | Inhalt |
|---|---|
| `0xC01A6000` bis `0xC01AA000` | eigene Animation, 16384 Byte, von der App geschrieben; `FF` ohne |
| `0xC01AA000` bis `0xC01AC000` | Standard-Blechy `assets/blechy/loading.blla` (7918 Byte), vom Patch geschrieben |
| `0xC01AC000` bis `0xC01AC800` | Code: Prüfen, Abspielen, Zählen der Lesevorgänge |
| `0xC01AC800` + 0x40 | RAM: welche Animation, gezeigtes Bild, gelesene Bytes, Rate, gezeigter Fortschritt |
| `0xC01ACC00` + 0x400 | RAM: das Fortschritts-Bild auf dem Schirm |
| `0xC01AD000` bis `0xC01ADF00` | frei |

Geprüft wird einmal, wenn der Start fragt, ob `e2sSample.all` da ist (`lb_stat`), vor dem ersten Bild. Der Fortschritt
kommt aus den Lesevorgängen des Sample-Parsers (`0xC00362FC` und `0xC003635C`, je bis 64 KiB): Position und Größe der
Datei stehen im Dateiobjekt von FatFs (+8, +12). Während ein Lesevorgang läuft, rechnet die Firmware mit der Rate der
bisherigen Lesevorgänge dieses Ladens hoch, nie über das Ende dieses Lesevorgangs hinaus und nie rückwärts. Die Zeit dafür
ist der Tick des Betriebssystems; im Emulator zählt er beim Lesen von einer Karte mit 32-KiB-Clustern nur rund 10 Prozent
(gemessen 28.10.), dort ist die Hochrechnung zu schnell und hält am Ende des Lesevorgangs an.

Standard-Blechy ist ein Fortschritts-Bild je Prozent 0 bis 99 mit der Zahl darin, dazu das Bild beim Fertig (N = 101), und
das Finale als Schleife ab 95 Prozent (8 Bilder). `tools/art/loading/firmware_assets.py` baut die Datei aus den Teilen in
`assets/blechy/loading.bin` und vergleicht jedes Bild mit dem Renderer.

## Größe

Bild 0 kostet 1024 Byte, der Kopf 16, jedes weitere Bild 2 Byte Tabelle, 2 Byte Zähler und seine Läufe.
`costPerFrame` nennt die Kosten je Bild, damit die App die teuersten zeigen kann. `thinAnimation` lässt jedes zweite
Fortschritts-Bild weg (0, 2, 4 ... bleiben, das letzte immer), die Schleife bleibt. Bei Bildern, deren Änderungen sich
nicht überdecken, halbiert das die Listen ungefähr (Test: 41 Bilder, Faktor 0,45 bis 0,65 der Datei).

## GIF-Import

`decodeGif` in `src/gif.mjs` liest GIF87a und GIF89a: globale und lokale Farbtabellen, LZW, Interlace, Transparenz,
Disposal 0 bis 3, Verzögerung in ms. Jedes Bild kommt fertig zusammengesetzt in Leinwandgröße als RGBA, die Leinwand
beginnt transparent (wie im Browser). Geprüft gegen das bekannte 10 x 10 Beispielbild und eine mit ffmpeg erzeugte Datei
(`test/fixtures/gif/ffmpeg-moving.gif`), dazu im Test gebaute Dateien für Transparenz, Disposal und Interlace.

## Tests

`test/loading-anim.test.mjs`, `test/gif.test.mjs`, `tools/patch/test_loading_anim.py` (Python gegen eine Datei aus dem
JS-Encoder, braucht node; dazu Standard-Blechy Bild für Bild gegen `load_bar.compose_reference`). Die Emulator-Fälle
stehen in `tools/emu/loadbar_cases.py` (`case_smooth`, `case_custom`).

## In der App

`Gerät -> Design`, Abschnitt Ladeanimation: ein GIF oder mehrere Einzelbilder (sortiert nach Namen), gewandelt wie das
Startbild (`pixelsOf` in `site/app/splash.mjs`, gleiche Schwelle). Je Bild die Rolle Fortschritt oder Warte-Schleife,
dazu "Schleife bei Stillstand" oder "ab Prozent". Die Größe steht als "x von 16 KB"; zu groß heißt abgelehnt, mit den
drei teuersten Bildern im Hinweis und dem Knopf Ausdünnen. Übernommen wird die Datei im Browser gespeichert.

Der Firmware Patcher schreibt sie als Patch `loading-anim` in das Kartenfeld `loadingAnim` (der Slot ab `0xC01A6000`,
Rest `FF`), in einem eigenen Durchgang nach dem Set und nur, wenn `load-bar` mit drauf ging: `load-bar` meldet den Slot
als seinen RAM, in einer Liste mit ihm würde der Patch abgelehnt. Vorher prüft `loadingAnimPatch` die Datei mit
`validateAnimation`. "Standard wiederherstellen" löscht die gespeicherte Datei, dann bleibt der Slot `FF` und die Firmware
zeigt Blechy. Tests: `test/loading-anim-patch.test.mjs`, `test/e2e/loading-anim.e2e.mjs`.
