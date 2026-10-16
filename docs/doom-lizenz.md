# Doom: Lizenzen und Weitergabe

Stand 15. Oktober 2026. Die Dateien liegen in [`third_party/doom/`](../third_party/doom/README.md). Das ist
meine Lesung der Lizenztexte und keine Rechtsberatung. Marker: **gemessen** (nachgezählt oder
nachgebaut), **hergeleitet** (aus den Texten gefolgert), **offen**.

## Was ausgeliefert wird

| Teil | Wo | Lizenz | Marker |
|---|---|---|---|
| Lader (SD-Lader, Tastenprüfung, SHA-256-Prüfung) | als Bytes in `data/patches/doom-loader.json`, Quelle `tools/doom/bootstrap.*`, `sha256.c` | AGPL-3.0-or-later, unser Code | gemessen: Quelle baut zu genau diesen Bytes |
| Adapter (Anzeige, Tasten, Datei, Uhr, Ausschalten) | in `doom.bin`, Quelle `tools/doom/runtime.c` und Header | AGPL-3.0-or-later, unser Code | gemessen |
| Engine doomgeneric, Revision `e257a095...` | in `doom.bin`, Quelle im Archiv | je Datei GPL-2.0-or-later, `sha1.c` GPL-3.0-or-later | gemessen: 77 von 80 gewählten Dateien nennen Version 2 oder später, `sha1.c` Version 3 oder später |
| newlib 4.4.0 (126 Objekte) und libgcc (24 Objekte) | in `doom.bin` | newlib: gemischt, meist BSD; libgcc: GPL-3.0-or-later mit GCC Runtime Library Exception | gemessen: die Objektliste steht in `third_party/doom/linked-objects.txt`; hergeleitet: die Lizenz je Objekt |
| Spieldaten Freedoom 0.13.0, Phase 1 | `doom.wad` | BSD, drei Klauseln | gemessen: `doom.wad` ist `freedoom1.wad` ohne Änderung (gleiche SHA-256) |
| Korg-Daten | nirgends | | gemessen: Der Lader ruft Firmware-Funktionen über feste Adressen auf, er enthält keinen Korg-Code und keine Korg-Daten; `test/release-audit.test.mjs` lässt in `third_party/doom/` nur die drei Dateien mit ihrem Hash durch |

## Wie die Lizenzen zusammenpassen

**Engine gegen Engine.** Eine Datei, `sha1.c`, verlangt GPL Version 3 oder später, die übrigen
Engine-Dateien erlauben Version 3 ausdrücklich (2 oder später). Die verlinkte Engine kann also als Ganzes nur
unter GPL-3.0 weitergegeben werden, nicht unter "GPL-2.0-only". Das ist hergeleitet. Die zwei
Dateien ohne Lizenzkopf stehen unter "offen".

**Unser Code gegen die Engine.** AGPL-3.0 Abschnitt 13 erlaubt ausdrücklich, ein AGPL-Werk mit einem
GPL-3.0-Werk zu einem Werk zu verbinden; die Bedingungen der GPL gelten für deren Teil, die der AGPL
für unseren. GPL-3.0 Abschnitt 13 sagt es von der anderen Seite. Beide Lizenzen verlangen dasselbe,
was wir tun: den Quelltext aller Teile mitliefern, die Lizenztexte und Hinweise erhalten,
nichts weiter einschränken. Der Zusatz der AGPL (Quelltext auch bei Nutzung über ein Netz) greift bei einem
Gerät ohne Netzdienst nicht, schadet aber nicht. Das ist hergeleitet.

**Ein Werk oder getrennte Werke.** Der Lader sitzt im Flash der Firmware, den jeder Nutzer selbst
patcht. `doom.bin` liegt als Datei auf der Karte. Der Lader liest die Datei, prüft sie und springt
hinein, beide teilen eine Struktur im RAM. Ob das noch "getrennte Programme" (bloße Zusammenstellung) oder
ein verbundenes Programm ist, ist eine Auslegungsfrage, und wir müssen sie nicht entscheiden: Die
Antwort ist in beiden Fällen "weitergeben unter den Bedingungen beider Lizenzen", und die sind
miteinander verträglich (siehe oben). Das gilt auch für den Zusammenschluss in einem Repository:
Das Repository bleibt AGPL-3.0 für unsere Teile, `third_party/doom/` trägt die Lizenzen der Teile darin,
und `NOTICE` sagt es.

**Die Spieldaten.** Freedoom ist ein eigenes Werk unter BSD, das die Engine als Datei liest. Die BSD
Lizenz verlangt Lizenztext und Urheberhinweise bei der Weitergabe (liegen bei, `licenses/Freedoom-*`),
sie ist mit GPL und AGPL verträglich, und Engine und Daten sind getrennte Werke.

**Die Firmware.** Wir geben nie eine Firmware weiter, nur Patches, die der Nutzer auf seine eigene
Datei anwendet. Der Lader und die Engine bringen keinen Korg-Code mit.

## Was zur Weitergabe der Binärdatei gehört

Mit `doom.bin` zusammen, am selben Ort: die vollständige Quelle (`doom-sources.tar.gz`, baut bytegleich neu,
[BUILD.md](../third_party/doom/BUILD.md)), die Lizenztexte (`licenses/`), die Urheberhinweise
(Freedoom-Credits, die Kopfzeilen im Quellarchiv) und der Hinweis, welche Lizenz auf welchem Teil liegt
(`third_party/doom/README.md`). Die Seite Patcher bietet `doom.bin` und `doom.wad` an und verweist
auf diese Datei; der Ordner wird mit der Seite ausgeliefert, also liegt die Quelle am selben Ort.

## Stand der Prüfung: freigegeben

`third_party/doom/distribution-review.json` hält jeden Punkt fest. Erfüllt: GPL-Text, vollständige
Quelle, Bauweg, Zusammenspiel AGPL und GPL, Freedoom samt Credits, die GCC Runtime Library Exception
(`licenses/GCC-Runtime-Library-Exception-3.1.txt`, aus dem GCC-14-Zweig) und die newlib-Hinweise
(`licenses/newlib-4.4.0-COPYING.NEWLIB.txt`, aus dem Tag `newlib-4.4.0`; die Datei sammelt die
Hinweise der einzelnen Quelldateien).

Bewusst in Kauf genommen: **`dummy.c` und `doomgeneric.c`** haben keinen Lizenzkopf und keine Klausel
"oder später". Nur der Text der GPL Version 2 steht im Repository der Engine. Wären sie GPL-2.0-only,
passten sie nicht mit `sha1.c` (3 oder später) in einer Binärdatei. Es sind zwei winzige Glue-Dateien,
der Rest der Engine erlaubt "oder später". Entscheidung des Maintainers am 2026-10-16: so ausliefern.
Meldet sich der Autor, ersetzen wir beide durch eigenen Code im Adapter (neuer Build, neuer Hash, neuer
Lader).

Frühere Befunde: [Doom: Quellen und Lizenzbefund](messungen/2026-10-15-doom-lizenzen.md).
