# 93. Bild-Betrachter für mehrere BMPs

Wunsch aus der Community (Oktober 2026). Stand 2026-11-16: **mit 1.5 neu gebaut, das Katalog-Plugin Image Viewer liest
`.bmp` und `.blla` direkt aus `KORG/blechtribe/Media/` (API 38), im Simulator und im Emulator geprüft, am Gerät offen.**
Marker: **gemessen**, **hergeleitet**, **ungeprüft**.

## Wunsch

Mehrere Bilder von der Karte nacheinander am Display ansehen, etwa BMPs, und mit einer Taste weiterblättern.

## Wie es gebaut ist (ab 1.5)

- Drei Aufrufe ab API 38: `korg.file.count` liest den Ordner `KORG/blechtribe/Media/`, `korg.file.name` gibt den Namen,
  `korg.file.picture` ein Bild einer `.bmp` oder `.blla`. Ordner, Reihenfolge, Grenze von 64 Dateien je Art und Polarität
  stehen in [Plugins, Karte und Dateiformat](../plugins.md#karte-und-dateiformat). Ein eigenes Format braucht es nicht mehr:
  es sind dieselben Dateien wie Startbild (SPLASH IMPORT) und [Ladeanimation](../hintergrund/ladeanimation.md).
- Das Plugin Image Viewer (TOOLS) zeigt beim Öffnen die Liste `IMAGES n` und `ANIMATIONS n`. In IMAGES blättern Encoder
  und Part im Kreis durch die `.bmp`, Name und Platz stehen zwei Sekunden oben. In ANIMATIONS wählt der Encoder die
  `.blla`, Part geht ein Bild vor und zurück, TAP spielt ein Bild alle 96 ms (Part halbiert und verdoppelt das, 48 bis
  384 ms), nach dem letzten Bild kommt wieder das erste. `NO IMAGES`, `NO ANIMATIONS`, `NO CARD` und `BAD FILE` sagen,
  was fehlt.
- Die App packt keine Bilder mehr für den Viewer: weitere `.bmp` kopiert man selbst nach `KORG/blechtribe/Media/`, die
  Seite Startbilder sagt das. `GIFnn.E2G` bleibt für den GIF Player, `tools/gif/gif2e2g.py` macht so eine Datei.
- Tests: `test/media.test.mjs` (Referenz), `test/script-file.test.mjs` (Plugin im Simulator), `tools/patch/test_script_file.py`
  (Firmware-Code in Unicorn), `tools/emu/plugin_api38_cases.py` (jeder Schritt gegen den Simulator, 40 von 40 auf Hacktribe,
  Korg rot und blau). (gemessen, Emulator)
- Zeiten im Emulator in [Messung](../messungen/2026-11-16-image-viewer-timing.md): ein `.bmp` 9,2 bis 9,4 ms Kartenzeit,
  langsamster Handler ohne Kartenzeit 0,37 bis 0,44 ms. (gemessen, Emulator)

## Bis 1.4.6

Der Viewer las Bilder über `korg.file.frame` aus `KORG/blechtribe/Gif/GIF00.E2G` bis `GIF99.E2G`, die App packte mehrere
Bilder in so eine Datei (Design, Unterseite Image Viewer). Diese Unterseite gibt es ab 1.5 nicht mehr.

## Offen

- Am Gerät nicht ausprobiert, die Lesezeit am Gerät ist nicht gemessen. (**ungeprüft** am Gerät)
- Nur 1-Bit-BMPs mit 128 x 64 Pixeln wie bei SPLASH IMPORT; andere BMPs zeigen `BAD FILE`.
