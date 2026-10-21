# Blechy-Samples

Eigene Aufnahmen (Schnüffel-Geräusche), kein Korg-Material.
Quelle: `source-original.mp3` (17 s, mehrere Takes hintereinander), daraus
geschnitten und normalisiert (`loudnorm=I=-16:TP=-1.5`).

| Datei | Rolle | Schnitt aus Quelle |
|---|---|---|
| `blechy-happy.mp3` | glücklich (Streicheln/Wischen übers Touchpad) | 4,55-5,55 s |
| `blechy-angry.mp3` | wütend (normales Antippen, Maul auf) | 9,70-11,35 s (Anfang weg) |
| `blechy-sad.mp3` | traurig (beim Ausschalten) | 6,25-7,85 s |
| `blechy-key.mp3` | Tastatur-Ton (wenn ein Keyboard-Menü offen ist) | 15,38-16,15 s |

Fürs Web direkt nutzbar. Fürs Gerät später ins passende Sample-Format wandeln.
Zuordnung und Verhalten: Idee 40 in `docs/ideen.md`.

## Startbild A auf ein Gerät bringen

`splash.json` ist ein Datenpatch (Feld `splash`) und lässt sich mit jedem Code-Patch
zusammen anwenden, `apply.mjs` nimmt mehrere `--patch`. Im Patch-Set
`data/patches/blech.json` ist es schon enthalten.

```bash
node tools/patch/apply.mjs --vsb SYSTEM.VSB --patch data/patches/mfx-switch.json --patch assets/blechy/splash.json --out NEU.VSB
# mit Startbild-Editor: Blech ist dann das VSB-Bild, das der Editor ohne gespeicherten Datensatz zeigt
node tools/patch/apply.mjs --vsb SYSTEM.VSB --patch data/patches/splash-editor.json --patch data/patches/mfx-switch.json --patch assets/blechy/splash.json --out NEU.VSB
```

Die ausgegebene `check.py`-Zeile (mit `--allow 0xf9954:1024` für das Bild) ausführen,
bevor die Datei aufs Gerät kommt.

## Startbild und Ladeanimation

`splash.bin` (Blechy kippt das Röhrchen) und `loading.bin` (die Bilder der Ladeanimation für
`data/patches/load-bar.json`) kommen aus dem Renderer in `tools/art/loading/anim.py`:

```bash
python3 tools/art/loading/firmware_assets.py
```

Danach `tools/patch/load_bar.py --vsb SYSTEM.VSB --out data/patches/load-bar.json` und die Patch-Sätze neu bauen.

## Theme

`theme-preview.png` zeigt die wichtigsten Bildschirme und alle druckbaren Zeichen mit dem BLECH Theme (Patch
`data/patches/blech-theme.json`, eigene Schriften und Symbole). Erzeugt mit `tools/patch/blech_theme_preview.mjs`
aus dem Emulator, nur die Seite mit Theme. Aufbau und Regeln: [BLECH Theme](../../docs/hintergrund/blech-theme.md).
