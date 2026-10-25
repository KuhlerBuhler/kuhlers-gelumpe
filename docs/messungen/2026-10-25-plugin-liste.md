# Eine Plugin-Liste in PLUGIN EDIT, IMPORT PLUGIN entfällt (25.10.)

Wunsch: eine Liste für alle Plugins. Gebaut und im Emulator geprüft (Hacktribe, `tools/emu/script_cases.py`, `import_cases`). Am Gerät
noch nicht geprüft.

## Was jetzt gilt

PLUGINS hat drei Seiten: RUNTIME, PLUGIN EDIT und EXPORT ALL. IMPORT PLUGIN gibt es nicht mehr.

- **ENTER auf PLUGIN EDIT** liest den Ordner `KORG/blechtribe/Plugin/` (bis 16 `*.blech` mit Plugin-Kopf, die Regeln der alten
  Importliste: keine Dateien mit Punkt am Anfang, keine versteckten oder Systemdateien, keine Unterordner) und öffnet die Liste. Gibt es
  weder eine Datei noch ein geladenes Plugin, sagt die Seite "No Plugin" und bleibt.
- **Die Liste:** zuerst die geladenen Plugins in der Reihenfolge der Laufzeit, dann die Plugins der Dateien, die nicht geladen sind, in
  der Reihenfolge der Dateien. Ein Plugin steht einmal da: der Name im Kopf der Datei gleicht dem Namen im geladenen Block. Ein gelöschtes
  Plugin (DELETE PLUGIN) gilt als nicht geladen, seine Datei steht wieder in der Liste und lässt sich laden.
- **Die Seiten eines Plugins:** SELECT PLUGIN, STATE, DESCRIPTION, danach die Seiten, die das Plugin mit `korg.menu.add` angelegt hat,
  zuletzt DELETE PLUGIN. Ein Plugin, das nicht geladen ist, hat nur die ersten drei.
- **STATE eines Plugins, das nicht geladen ist:** OFF. Das Hauptrad nach oben oder ENTER lädt es aus der Datei und startet es (der
  Weg des alten Imports, auch das Speicherbild von `korg.store` wird danach neu gelesen); das Plugin steht dann bei den geladenen und
  SELECT PLUGIN folgt ihm. Ein fremdes Plugin wartet auf WRITE=ALLOW, ein kaputter Block meldet "rejected", bei ausgeschalteter Laufzeit
  "runtime off". Das Hauptrad nach unten tut nichts.
- **DESCRIPTION:** das Bild mit dem Namen oben, der Beschreibung (das Hauptrad scrollt, `^` und `v` zeigen, dass es weitergeht) und
  dem Stand unten, wie bisher unter IMPORT PLUGIN. ENTER tut hier nichts. Die Beschreibung wird beim Öffnen der Seite aus der Datei hinter
  dem Block gelesen.

## Entschieden

| Frage | Entscheidung | Grund |
|---|---|---|
| Plugins nur in `e2sPlugin.all`, ohne `.blech` | stehen als geladene Plugins in der Liste, DESCRIPTION sagt "no description" | `e2sPlugin.all` enthält Blöcke ohne den Anhang `GDSC` und `GSRC` (siehe [Plugins](../plugins.md), "Dateien für die Karte"); sie auszulassen würde sie vor dem Nutzer verstecken, sie läuft aber |
| "geladen und aus" gegen "nicht geladen" | beide zeigen OFF; der Unterschied ist die Seitenzahl im Zähler: ein Plugin, das nicht geladen ist, hat 3 Seiten, ein geladenes seine eigenen und DELETE PLUGIN dazu | der Wunsch war OFF für nicht geladen; ein eigenes Wort (etwa "NOT LOADED") passt nicht in die rund 14 Zeichen des Werts neben die anderen Zustände |
| Ordnung der Liste | geladene zuerst, dann die Dateien | `M_PSEL` zählt wie bisher durch die geladenen Plugins; ein geladenes Plugin behält seinen Platz, ein frisch geladenes rückt an das Ende der geladenen |
| Teile der Firmware (Blechy, Funktionen von BLECH) | nie in der Liste | Blechy hat keinen Block im Pool der Plugins und zählt nicht ([Menü](../plugins.md)); ihre Schalter stehen unter FEATURES |
| Laden bleibt über einen Neustart | nicht von selbst | wie beim alten Import: ein geladenes Plugin läuft bis zum Ausschalten, `e2sPlugin.all` entsteht nur mit EXPORT ALL |
| Mehr als 16 Dateien | die ersten 16 des Ordners | wie bisher (`LIST_MAX`) |

## Wo es steht

`tools/patch/script_menu.s`: `menu_psel_total`, `menu_psel_file` und `menu_psel_name` bilden die eine Liste aus den geladenen Plugins
und den Dateien (`menu_file_entry` findet das geladene Plugin zu einer Datei); `menu_load_psel` lädt über `menu_import`;
`menu_desc_load` und `menu_desc_open` lesen die Beschreibung; `menu_text_pdesc` und `menu_desc_frame` zeigen sie (Seitenart 39).
`menu_import` übergeht den Block eines gelöschten Plugins beim Prüfen auf einen gleichen Namen.

`tools/emu/script_cases.py`, `import_cases`: Liste aus den Dateien (ohne die Dateien, die keine Plugins sind), STATE OFF vor dem Laden,
Beschreibung als Seite und ihr Scrollen, Laden mit dem Hauptrad nach oben, Speicherbild nach dem Laden gleich der Datei, aus und
wieder an, fremdes Plugin wartet und wird erlaubt, kaputter Block wird abgelehnt, Verlassen zeichnet neu, geladene zuerst und nichts
doppelt, Plugin nur in `e2sPlugin.all`, gelöschtes Plugin lädt wieder, keine Dateien, Laufzeit ausgeschaltet.
