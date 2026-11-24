# Dokumentation

Deutsche Version | [English version](README.en.md)

Einstieg in alles unter `docs/`. Fang mit dem [Glossar](glossary.md) an, wenn dir ein Begriff neu ist: Jede Seite verlinkt die Begriffe, die sie benutzt, bei der ersten Verwendung. Nutzer starten mit der [README](../README.md) ([English](../README.en.md)).

Sprache: Die meisten Seiten sind auf Deutsch, das Deutsche ist die Referenz. Englische Fassungen gibt es für [plugins](plugins.en.md), [patcher](patcher.en.md), [original-zurueck](original-zurueck.en.md), diesen Index ([README.en.md](README.en.md)) und das [Glossar](glossary.en.md). Die Plugins-Seite gibt es außerdem auf [Französisch](plugins.fr.md).

Alles Gemessene gilt für den Korg Electribe 2 Sampler mit Firmware 2.02 und Hacktribe, sofern eine Seite nichts anderes sagt. Fakten tragen einen Marker: **gemessen**, **offline** (Code oder ein Dump wurde gelesen), **hergeleitet**, **offen**. Der Code in `tools/` hat eigene kurze READMEs: [tools/emu/README.md](../tools/emu/README.md) und [tools/alsa-sysex.md](../tools/alsa-sysex.md). Woher die mitgelieferten Teile stammen, steht in [NOTICE](../NOTICE), die Regeln für Agents und Mitwirkende in [AGENTS.md](../AGENTS.md).

## Firmware und App benutzen

| Seite | Inhalt |
|---|---|
| [faq.md](faq.md) | Häufige Fragen, von "geht mein Gerät dabei kaputt" bis "Error, No File" |
| [tastenkombinationen.md](tastenkombinationen.md) | Tastenkombinationen der Firmware: SHIFT, Halten und Einschalten |
| [test-modus.md](test-modus.md) | Test-Modus (das Gerät sieht ausgeschaltet aus) und Bedienung des Geräts über USB |
| [plugins.md](plugins.md) | Plugins: Sprache, Ereignisse, Funktionen, Kartenformat, das BLECH-Menü, die Editor-Seite ([English](plugins.en.md), [Französisch](plugins.fr.md)) |
| [effekt-katalog.md](effekt-katalog.md) | Die Effekte und Modulationen des Baukasten-Katalogs und was ein Effekt nicht kann |
| [original-zurueck.md](original-zurueck.md) | Zurück zu Korgs Original-Firmware, rot und blau ([English](original-zurueck.en.md)) |
| [rettung.md](rettung.md) | Die Blechy-Seite: der dokumentierte Rückweg, wenn ein Gerät nicht startet |
| [doom-lizenz.md](doom-lizenz.md) | Doom auf der Karte: Teile, Lizenzen und was für eine Weitergabe fehlt |
| [geraetetests/](geraetetests/README.md) | Schritt-für-Schritt-Anleitungen, um BLECHTRIBE und die Kartenfunktionen am eigenen Gerät zu testen |

## Wie es gebaut ist

| Seite | Inhalt |
|---|---|
| [development.md](development.md) | Bauen, Testen, die Desktop-App bauen, Release |
| [architektur.md](architektur.md) | Türsteher, Sendeweg, Probelauf, Terminal, Fehlerkatalog, Design |
| [patcher.md](patcher.md) | Die Firmware patchen: Patch-Format, Haken, Regeln, Notschalter, Patch-Tabelle ([English](patcher.en.md)) |
| [emulator.md](emulator.md) | Der Emulator: Installation, Dienst, Karte und Flash, Start, Prüfläufe |
| [geraetekarte.md](geraetekarte.md) | Die Gerätekarte: Format, Belege, Umrechnungen, Expertenmodus |
| [linter.md](linter.md) | Der Linter, sein Wissen über Effekte, das simulierte Gerät, offene Punkte |
| [speicherbereiche.md](speicherbereiche.md) | Gemessene Speicherbereiche, Schreibgrenzen, noch offene Bereiche |
| [firmware-sprache.md](firmware-sprache.md) | Gerätemenüs auf Deutsch: Sprachdateien, Kürzungsregel, Umlaute |
| [barrierefreiheit.md](barrierefreiheit.md) | Barrierefreiheit: was gegen WCAG 2.2 AA getestet ist und was offen ist |
| [entscheidungen.md](entscheidungen.md) | Entscheidungen, die feststehen |
| [fahrplan.md](fahrplan.md) | Fahrplan: was veröffentlicht ist, was 1.5 bringt, was danach kommt |

## Hintergrund

Tiefere Erklärungen dazu, wie die Firmware arbeitet. Die Seiten oben stützen sich darauf.

| Seite | Inhalt |
|---|---|
| [hintergrund/skript-laufzeit.md](hintergrund/skript-laufzeit.md) | Firmware-Tasks, Haken und Speicher als Grundlage der Plugin-Laufzeit |
| [hintergrund/virtuelle-sd.md](hintergrund/virtuelle-sd.md) | Dateifunktionen der Firmware, FatFs, der Sample-Lader, die virtuelle Karte |
| [hintergrund/sample-datei.md](hintergrund/sample-datei.md) | Das Format `e2sSample.all` und die Übertragung über USB mit einer Swap-Datei |
| [hintergrund/startbild-editor.md](hintergrund/startbild-editor.md) | Das Startbild im Flash und sein Editor |
| [hintergrund/ladeanimation.md](hintergrund/ladeanimation.md) | Das Dateiformat der Ladeanimation und der GIF-Import |
| [hintergrund/blech-theme.md](hintergrund/blech-theme.md) | Eigene Schriften und Symbole für das Display |
| [hintergrund/dsp-erster-blick.md](hintergrund/dsp-erster-blick.md) | Der DSP: Programm, Effekt-Umschaltung, Filter |
| [hintergrund/panel-controller.md](hintergrund/panel-controller.md) | Der Mikrocontroller hinter Tasten, Reglern und LEDs |
| [hintergrund/sequencer-timing.md](hintergrund/sequencer-timing.md) | Sequencer-Auflösung, MIDI-Clock, Tempo |
| [hintergrund/patternwechsel.md](hintergrund/patternwechsel.md) | Einen Pattern-Wechsel bestätigen und die Lücke, die ein Wechsel hat |

## Messungen und Ideen

| Seite | Inhalt |
|---|---|
| [messungen/README.md](messungen/README.md) | Alle Messungen nach Thema. Sie sind der Beleg für die Gerätekarte, darum ändern sich ihre Pfade nie |
| [ideen.md](ideen.md) | Ideen, die noch offen sind, mit ihren Detailseiten in [ideen/](ideen/) |
| [glossary.md](glossary.md) | Begriffe und Namen aus diesem Repo ([English](glossary.en.md)) |
