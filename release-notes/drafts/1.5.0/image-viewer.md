### Entwurf release-notes/1.5.0.md (kommt mit dem Versionssprung)

**Neu**
- Image Viewer zeigt Startbilder und Ladeanimationen von der Karte
  - Was: die App Image Viewer (unter TOOLS) liest jede `.bmp` und jede `.blla` aus `KORG/blechtribe/Media/` direkt, ein eigenes Dateiformat braucht es nicht mehr. Beim Öffnen steht die Liste IMAGES und ANIMATIONS mit der Zahl der Dateien.
  - So geht's: Encoder oder Part wählt, MENU öffnet die Liste und geht wieder zurück. In IMAGES blättern Encoder und Part durch die Bilder, der Name steht zwei Sekunden oben, TAP lässt ihn stehen. In ANIMATIONS wählt der Encoder die Datei, Part geht ein Bild vor und zurück, TAP spielt und hält an; beim Spielen halbiert und verdoppelt Part das Tempo (48 bis 384 ms).
  - Gut zu wissen: weitere Bilder kopierst du selbst nach `KORG/blechtribe/Media/`, 128 x 64 Pixel, 1 Bit, wie bei SPLASH IMPORT. Höchstens 64 Dateien je Art, in der Reihenfolge, in der sie auf die Karte kamen, nicht alphabetisch. Eine andere Datei zeigt `BAD FILE`.

**Geändert**
- Design: die Unterseite Image Viewer fällt weg
  - Was: die App packt keine Bilder mehr in eine `GIFnn.E2G`. Die Seite Startbilder sagt jetzt, dass der Image Viewer jede `.bmp` in `Media/` zeigt.
  - Gut zu wissen: alte `GIFnn.E2G` zeigt der Image Viewer nicht mehr, der GIF Player spielt sie weiter. Eine neue macht `tools/gif/gif2e2g.py`.

**Neu für Entwickler**
- Plugin-API 38: `korg.file.count`, `korg.file.name`, `korg.file.picture` lesen Startbilder (`.bmp`) und Ladeanimationen (`.blla`) aus `KORG/blechtribe/Media/`. Ordner, Reihenfolge, Grenze und Polarität stehen in der Plugin-Doku unter "Karte und Dateiformat".
- Kartenzeit zählt nicht fürs Rahmenbudget: die Zeit in `korg.file.frame`, `read`, `write`, `count`, `name` und `picture` zählt weder für die 5 ms noch für die Warnung bei 0,5 ms, bis 50 ms je Rahmen.

## English

**New**
- Image Viewer shows start images and loading animations from the card
  - What: the Image Viewer app (under TOOLS) reads every `.bmp` and every `.blla` in `KORG/blechtribe/Media/` directly, no file format of its own any more. It opens on the list IMAGES and ANIMATIONS with the number of files.
  - How: the encoder or Part picks, MENU opens the list and goes back. In IMAGES the encoder and Part page through the pictures, the name stays on top for two seconds, TAP keeps it. In ANIMATIONS the encoder picks the file, Part steps one picture on and back, TAP plays and stops; while playing Part halves and doubles the speed (48 to 384 ms).
  - Good to know: copy more pictures to `KORG/blechtribe/Media/` yourself, 128 x 64 pixels, 1 bit, as for SPLASH IMPORT. At most 64 files of a kind, in the order they came onto the card, not alphabetical. Any other file shows `BAD FILE`.

**Changed**
- Design: the Image Viewer sub-page is gone
  - What: the app no longer packs pictures into a `GIFnn.E2G`. The Splash images page now says that the Image Viewer shows every `.bmp` in `Media/`.
  - Good to know: the Image Viewer no longer shows old `GIFnn.E2G` files, the GIF Player still plays them. `tools/gif/gif2e2g.py` makes a new one.

**New for developers**
- Plugin API 38: `korg.file.count`, `korg.file.name`, `korg.file.picture` read start images (`.bmp`) and loading animations (`.blla`) from `KORG/blechtribe/Media/`. Folder, order, limit and polarity are in the plugin docs under "The card and the file format".
- Card time does not count against the frame budget: the time in `korg.file.frame`, `read`, `write`, `count`, `name` and `picture` counts neither for the 5 ms nor for the warning at 0.5 ms, up to 50 ms a frame.
