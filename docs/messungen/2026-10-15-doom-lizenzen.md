# Doom: Quellen und Lizenzbefund

Stand 15.10.2026. Gelesener Lizenzbefund und lokale Paketprüfung,
keine Veröffentlichung oder Geräteaktion.

## Gepinnte Engine

Gelesen am doomgeneric-Stand
`e257a09527062bfb986b6e5e0780839b6cbd5b71`: `LICENSE` enthält den GPLv2-Text.
Das allein bedeutet nicht GPL-2.0-only. Von 80 tatsächlich gewählten
Engine-C-Dateien nennen 77 ausdrücklich GPL Version 2 mit späteren
Versionen als Wahlmöglichkeit. `sha1.c` nennt ausdrücklich
GPL Version 3 mit späteren Versionen als Wahlmöglichkeit. Primärbelege:
[am_map.c](https://github.com/ozkl/doomgeneric/blob/e257a09527062bfb986b6e5e0780839b6cbd5b71/doomgeneric/am_map.c),
[sha1.c](https://github.com/ozkl/doomgeneric/blob/e257a09527062bfb986b6e5e0780839b6cbd5b71/doomgeneric/sha1.c)
und [Repo-Lizenz](https://github.com/ozkl/doomgeneric/blob/e257a09527062bfb986b6e5e0780839b6cbd5b71/LICENSE).
`dummy.c` und `doomgeneric.c` haben keinen eigenen Lizenzheader.
Die zwei Dateien benötigen bei einer Distributionsfreigabe eine
ausdrückliche Bewertung der Repo-Lizenz und ihrer Anwendbarkeit.
Ihre Repo-Hinweise bleiben im vollständigen Quellenarchiv erhalten;
eine eigenständige ausdrückliche spätere Lizenzklausel steht dort nicht.

Hergeleitet: Der passende gemeinsame Versionszweig der ausdrücklich
lizenzierten Engineanteile ist GPLv3. GPL-2.0-only wäre für die ganze
verlinkte Engine bereits wegen `sha1.c` die falsche Beschreibung.
Unser Adapter trägt AGPL-3.0-or-later. Abschnitt 13 der
[lokalen AGPL-Lizenz](../../LICENSE) erlaubt Kombination mit GPLv3 und
belässt die jeweiligen Lizenzbedingungen auf den jeweiligen Anteilen.
Das ist keine automatische Freigabe der gesamten Binärdistribution.

## Buildquellen sichern

`build_runtime.py` erzeugt automatisch `doom-sources.tar.gz`, `sources.json`
und `build.json` neben der Engine. Gesichert werden die vollständige
gepinnt ausgecheckte Engine, unser Adapter, seine ABI- und Layoutheader,
Linkerskript, Buildskripte, Repo-Lizenz, Toolchainmanifest und die genaue
Compilerkonfiguration. Dateihashes verbinden diesen Stand mit `doom.bin`.
Quelländerungen während des Builds führen zum Abbruch.

Gemessen: `node --test test/doom-sources.test.mjs` besteht. Der Test
verlangt die Ablehnung eines nachträglich veränderten Adapters,
einer veränderten Binärdatei und eines veränderten Quellarchivs.
Ein tatsächlicher ARM926-Build mit dem vorhandenen Arm GNU 14.2.Rel1
hat das Quellenarchiv außerhalb des Repos erzeugt. Ein kompletter
Weitergabebundle wurde nicht erzeugt.

## Offene Distributionsprüfung

`source_package.py` vergleicht den aktuellen Stand, Binärhash und das
archivierte Hashinventar. Das Ergebnis bleibt ausdrücklich
`redistribution_ready: false`. Ein bloßer Upstreamlink ist kein Ersatz
für die exakt zu dieser Binärdatei gehörenden Quellen und Bauanweisungen.
Korg-Firmware und WAD-Daten sind nicht Teil des Quellarchivs.

Offen bleiben die zu dieser Toolchain passenden Lizenztexte und die
einzelnen Anforderungen der eingebundenen Newlib-Dateien sowie die Prüfung der GCC-Laufzeitausnahme. Newlib hat unterschiedliche
Dateilizenzen; daraus folgt keine pauschale Quellpflicht für die Toolchain.
Die [offizielle Newlib-Lizenzsammlung](https://sourceware.org/newlib/COPYING.NEWLIB)
verlangt die Betrachtung der jeweiligen Datei und ihrer Hinweise.
Die [offizielle GCC-Beschreibung](https://gcc.gnu.org/onlinedocs/libstdc++/manual/license.html)
veröffentlicht die Runtime Library Exception und ihre Bedingungen;
sie belegt keine automatische Ausnahme für beliebige fremde Laufzeiten.
Der lokale Compilerlieferumfang enthält hier ein Toolchainmanifest,
aber keine vollständige separat geprüfte Newlib-Lizenzsammlung.

Vor einer Weitergabe müssen GPLv3-Text, AGPL-Text, erhaltene Urheberhinweise,
passende Laufzeitlizenzen und vollständige korrespondierende Quellen
beziehungsweise eine konkret geprüfte Ausnahme zusammen bereitstehen.
Bei beigepacktem Freedoom kommen dessen Lizenz und Credits dazu.
Dieser Stand erlaubt lokale Tests; die Binärweitergabe bleibt offen.
