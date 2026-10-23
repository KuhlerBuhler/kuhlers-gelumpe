# Doom für die Karte

Hier liegt, was Doom auf der Electribe braucht, mit allen Quellen und Lizenzen. Nichts davon ist
Korg-Material. Warum die Teile nebeneinander liegen dürfen und was noch offen ist, steht in
[docs/doom-lizenz.md](../../docs/doom-lizenz.md). Der Aufbau und die Messungen stehen in
[tools/doom/README.md](../../tools/doom/README.md).

## Was ist was

| Datei | Was | Lizenz |
|---|---|---|
| `doom.bin` | die Engine, gebaut für den ARM926 der Electribe: doomgeneric (Revision `e257a09527062bfb986b6e5e0780839b6cbd5b71`) mit unserem Adapter, gegen newlib und libgcc gelinkt | engine: GPL-2.0-or-later, `sha1.c`: GPL-3.0-or-later, unser Adapter: AGPL-3.0-or-later; als Ganzes also unter GPL-3.0 weiterzugeben, siehe docs/doom-lizenz.md |
| `doom-sources.tar.gz` | die vollständige zugehörige Quelle: die ausgecheckte Engine, unsere Adapter und Skripte, die Compilerkonfiguration, `REBUILD.md`, `build.json` | wie oben, je Datei |
| `sources.json` | SHA-256 jeder Datei des Archivs und der Binärdatei | keine Lizenz nötig, Prüfliste |
| `manifest.json` | Länge, SHA-256, Einsprung und Speichergrenzen von `doom.bin`; der Lader prüft gegen diese Werte | unser Code, AGPL-3.0-or-later |
| `doom.wad` | Freedoom 0.13.0, Phase 1 (`freedoom1.wad` unverändert, nur umbenannt) | BSD, drei Klauseln, `licenses/Freedoom-COPYING.txt` |
| `linked-objects.txt` | welche Objekte von newlib und libgcc im Binär stecken (aus der Link-Map des Builds) | Liste, keine Lizenz nötig |
| `licenses/` | die Lizenztexte und Hinweise, siehe unten | jeweils die Datei selbst |
| `BUILD.md` | der Bauweg, mit dem `doom.bin` bytegleich neu entsteht | AGPL-3.0-or-later |
| `distribution-review.json` | der Stand der Weitergabeprüfung, Punkt für Punkt | |

SHA-256: `doom.bin` `5222c195cb7b8507f4b3391d8bb190f82ce27c86a122532d25b90497431695d8`,
`doom.wad` `7323bcc168c5a45ff10749b339960e98314740a734c30d4b9f3337001f9e703d`,
`doom-sources.tar.gz` `ca0ac8269392fbcabb39bfcdefcaa4cfe536830590e0e80557625ba85ef76c9a`.

## Lizenztexte in `licenses/`

| Datei | Inhalt |
|---|---|
| `GPL-2.0-doomgeneric-LICENSE.txt` | der Lizenztext, den doomgeneric im Repository mitbringt (GPL Version 2) |
| `GPL-3.0.txt` | GNU GPL Version 3, der Text der Free Software Foundation |
| `GPL-3.0-gcc-Copying.html` | derselbe GPL-3.0-Text, wie ihn die Dokumentation der Arm-Toolchain mitliefert |
| `Freedoom-COPYING.txt` | die Freedoom-Lizenz (BSD, drei Klauseln) |
| `Freedoom-CREDITS.txt`, `Freedoom-CREDITS-MUSIC.txt` | die Urheber der Spieldaten und der Musik, beizulegen, wenn die Spieldaten weitergegeben werden |
| `GCC-Runtime-Library-Exception-3.1.txt` | die Ausnahme für libgcc (`COPYING.RUNTIME` aus GCC 14) |
| `newlib-4.4.0-COPYING.NEWLIB.txt` | die Lizenzhinweise von newlib 4.4.0, gesammelt für alle Quelldateien |

Der AGPL-3.0-Text für unseren Code ist `LICENSE` im Wurzelverzeichnis des Repositories.

## Was bewusst so bleibt

`dummy.c` und `doomgeneric.c` der Engine sind zwei kleine Glue-Dateien (53 und 27 Zeilen) ohne
Lizenzkopf. Wären sie GPL-2.0-only, passten sie nicht mit `sha1.c` (GPL-3.0-or-later) in einer
Binärdatei. Der Maintainer hat am 2026-10-16 entschieden, so auszuliefern. Meldet sich der Autor,
ersetzen wir beide durch eigenen Glue-Code im Adapter. Sonst ist nichts offen,
`redistribution_ready` in `distribution-review.json` steht auf `true`.
