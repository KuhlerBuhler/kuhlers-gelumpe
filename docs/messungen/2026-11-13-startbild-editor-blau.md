# Startbild-Editor auf der blauen, im Emulator

Stand 13.11.2026 auf `develop` (`65b94ded`), nur Emulator (Korgs Original 2.02 blau), am Gerät nichts
geprüft. Ziel für 1.5: SPLASH IMPORT, SPLASH DRAW und SPLASH RESET im BLECH-Menü auch auf der blauen,
das Bild im Flash, damit es wie auf der roten ab dem ersten Bild beim Start steht.

## Was neu ist

Der Editor für die blaue war schon gebaut (`tools/patch/splash_editor.py --build synth`,
`data/patches/splash-editor-synth.json`), aber nicht im Satz. Neu:

| Änderung | Datei |
| --- | --- |
| Der Editor ist im blauen Satz | `data/patches/blech-synth.json` |
| Die Startbild-Fälle laufen auf der blauen: Bild der VSB an der Adresse der blauen, leerer Flash der blauen Hardware, deren Ladebalken, Bootgrenze wie bei Korgs roter | `tools/emu/splash_cases.py` |
| Der Vergleich des Dateibrowsers mit IMPORT SAMPLE entfällt auf der blauen (ihr DATA UTILITY hat kein IMPORT SAMPLE) | `tools/emu/menu_cases.py` |

**Gelesen:** `splash-editor-synth.json` ist das, was der Generator heute aus der blauen 2.02 baut
(`cmp` gleich). Mit dem Satz zusammen meldet `checkHooks` keinen doppelt beanspruchten Haken.

## Flash

**Gelesen** ([Einstellungen im Flash](2026-11-13-einstellungen-flash.md)): auf der blauen schreiben
alle Aufrufer der Schreibfunktion `0xC0026E24` nur `0x230000`, `0x240000 + n * 0x4000`, `0x7EF000`,
`0x7FF000`, die Update-Bereiche unter `0x7E0000` und ab `0x800000`. Sektor `0x7F0000`, den der Editor
nimmt, schreibt nichts davon. `0x7FD000` und `0x7FE000` (BLECH-Einstellungen ohne Karte) bleiben frei.

**Hergeleitet:** Was auf einer echten blauen in `0x7F0000` steht, ist nicht gemessen (kein Dump einer
blauen). Der Editor nimmt den Satz nur mit Kennung, Version, Länge und CRC32; alles andere zeichnet das
Bild der VSB.

## Der Ladebalken der blauen

**Gemessen:** Korgs blaue löscht über dem Startbild die Zeilen 54 und 55 (Bits 6 und 7 in Seite 6),
ab Spalte 9 nach rechts wachsend. Die rote löscht 61 und 62 in Seite 7. Ohne diese Ausnahme sah der
Fall jedes Bild der VSB nach drei Bildern als "anderes Bild". Über einem gespeicherten Bild, das dort
schon dunkel ist, ändert er nichts.

## Hintergrundfarbe beim Start

**Gemessen** (Emulator, ganzer blauer Satz): Korgs blaue zeichnet ihr Startbild, bevor der Flash antwortet, die
gespeicherte Farbe kam deshalb erst, während das Bild schon stand. Mit dem Editor zeichnet dessen Start-Haken das
Bild hinter dem Lesen des Flash: Rot ab 56,15 ms, Bild bei 56,39 ms. Die blaue verhält sich damit wie die rote,
`menu_cases.boot_light_cases` prüft auf der blauen mit Editor jetzt "Farbe vor dem Startbild".
`splash_cases.has_start_hook` erkennt den Haken auf der blauen jetzt an ihrer Adresse; vorher lief `check.py`
die Startbild-Fälle auf der blauen gar nicht.

## Fälle

`tools/emu/splash_cases.py` `cases` und `run` liefen auf Korgs blauer 2.02 mit dem Editor allein und mit
dem ganzen blauen Satz, `menu_cases.splash_menu_cases` mit dem ganzen blauen Satz. Mit dem ganzen Satz
ist in `run` alles zum Editor grün; nur die Schritte, die die Global-Seiten Bild für Bild mit Korgs
Original vergleichen, weichen ab, weil andere Patches des Satzes diese Seiten ändern (mit dem Editor
allein sind auch sie grün). Gegenprobe mit dem geänderten `splash_cases.py`: Hacktribe 2.02 und Korgs
rote 2.02, je mit dem Editor allein, `cases` und `run` grün. Auf der roten sah der Neustart nach WRITE
einmal als erstes Bild ein halb gezeichnetes; die Neustart-Schritte überspringen jetzt wie die Startfälle
bis zu zwei solche Bilder am Anfang.

| Fall | blau |
| --- | --- |
| Start: leer, gültig, Bit gekippt, halb geschrieben, falsche Kennung, Version, Länge | alle grün, Hauptbildschirm erreicht, DSP einmal gebootet |
| EXIT beim Einschalten: Bild der VSB, Patch aus, Global ohne Seite 20 | grün |
| Editor: Cursor, VALUE, SHIFT, MENU kippt und malt, WRITE | grün |
| WRITE ändert nur `0x7F0000` und was die Firmware selbst schreibt (`0x230000`, auf frischem Flash `0x7EF000`) | grün |
| Neustart zeigt das gemalte Bild | grün |
| Import: von unten, von oben mit Schwarz als Index 1, Kopf 124 Byte | grün, Bild gespeichert und nach Neustart zu sehen |
| Import: 100 Pixel breit, 4 Bit, keine Datei | 2, 2, 1 wie erwartet |
| BLECH-Menü: SPLASH als eigene Gruppe, IMPORT mit Liste und langen Namen, ohne Datei, DRAW öffnet den Editor, RESET bringt das Bild der VSB zurück, auch nach Neustart | grün |

```bash
PYTHONPATH=tools/patch tools/emu/.venv/bin/python tools/emu/splash_cases.py cases --base korg-blue-2.02.VSB --patched BLECH-blau.VSB
PYTHONPATH=tools/patch tools/emu/.venv/bin/python tools/emu/splash_cases.py run --base korg-blue-2.02.VSB --patched BLECH-blau.VSB
```

## Offen

- **Gerätetest auf einer blauen:** keiner. Vor allem das Löschen und Schreiben von `0x7F0000` und
  dass das Bild beim nächsten Start ab dem ersten Bild steht.
- **Inhalt von `0x7F0000` auf echten blauen:** nicht gemessen, siehe oben.
