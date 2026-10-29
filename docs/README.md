# Dokumentation

Die Docs sind auf Deutsch. Den Einstieg für Nutzer gibt es in der [README](../README.md) (auch
[auf Englisch](../README.en.md)). Alles Gemessene gilt für die Korg Electribe 2 Sampler mit
Firmware 2.02 und Hacktribe. Marker in den Texten: **gemessen**, **offline** (Code oder Dump
gelesen), **hergeleitet**, **offen**.

## Benutzen

| Seite | Inhalt |
|---|---|
| [fahrplan.md](fahrplan.md) | Welche Version was bekommen soll: 1.3.6, 1.4, 1.5 "The sample update" |
| [tastenkombinationen.md](tastenkombinationen.md) | SHIFT-, Halte- und Einschalt-Kombinationen der Firmware |
| [plugins.md](plugins.md) | Plugins: Sprache, Ereignisse, Funktionen, Kartenformat, das Menü BLECH, die Seite im Editor ([English](plugins.en.md)) |
| [doom-lizenz.md](doom-lizenz.md) | Doom auf der Karte: Teile, Lizenzen, warum AGPL und GPL zusammenpassen, was noch zur Weitergabe fehlt |
| [rettung.md](rettung.md) | Die Seite Rettung: der dokumentierte Weg zurück, Ordner je Firmware, das Stoppschild |
| [patcher.md](patcher.md) | Die Firmware patchen: Patchformat, Haken, Regeln, Notschalter, BLECH-Patchdatei ([English](patcher.en.md)) |
| [emulator.md](emulator.md) | Der Emulator: Installation, Dienst, Karte und Flash, Boot, Prüfläufe |
| [set/pattern-aufspielen.md](set/pattern-aufspielen.md) | Einzelne Patterns von der Karte auf die Electribe bringen |
| [set/uebergaenge.md](set/uebergaenge.md) | Übergangs-Patterns für ein Set erzeugen |
| [set/pattern-werkzeuge.md](set/pattern-werkzeuge.md) | Die Seite Pattern-Werkzeuge: Übergänge bauen und Parts würfeln, Ausgabe als Datei, Sicherung oder ans Gerät |
| [geraetetests/](geraetetests/README.md) | Anleitungen, um BLECH und die Kartenfunktionen an einem eigenen Gerät zu testen |

## Wie es gebaut ist

| Seite | Inhalt |
|---|---|
| [architektur.md](architektur.md) | Türsteher, Sendeweg, Probelauf, Terminal, Fehlerkatalog, Design |
| [geraetekarte.md](geraetekarte.md) | Das Format der Karte, Belege, Umrechnungen, Expertenmodus |
| [linter.md](linter.md) | Der Linter, sein Wissen über Effekte, das simulierte Gerät, offene Punkte |
| [speicherbereiche.md](speicherbereiche.md) | Vermessene Speicherbereiche, Schreibgrenzen, noch offene Bereiche |
| [development.md](development.md) | Bauen, testen, die App bauen, Release |
| [barrierefreiheit.md](barrierefreiheit.md) | Prüfung gegen WCAG 2.2 AA: Funde, Fixes, offene Entscheidungen |
| [entscheidungen.md](entscheidungen.md) | Was entschieden ist |

## Messungen und Hintergrund

| Seite | Inhalt |
|---|---|
| [messungen/README.md](messungen/README.md) | Alle Messungen nach Thema, die Belege der Gerätekarte |
| [ideen.md](ideen.md) | Ideen, ihr Stand und ihre Detailseiten |
| [hintergrund/skript-laufzeit.md](hintergrund/skript-laufzeit.md) | Firmware-Tasks, Haken und Speicher als Grundlage der Plugin-Laufzeit |
| [hintergrund/virtuelle-sd.md](hintergrund/virtuelle-sd.md) | Datei-Funktionen der Firmware, FatFs, Sample-Lader, die virtuelle Karte |
| [hintergrund/sample-datei.md](hintergrund/sample-datei.md) | Das Format der `e2sSample.all`, die Seite Samples, der Weg über USB mit Tauschdatei |
| [hintergrund/startbild-editor.md](hintergrund/startbild-editor.md) | Das Startbild im Flash und der Editor dafür |
| [hintergrund/ladeanimation.md](hintergrund/ladeanimation.md) | Das Dateiformat der eigenen Ladeanimation, der GIF-Import |
| [hintergrund/blech-theme.md](hintergrund/blech-theme.md) | Eigene Schriften und Symbole fürs Display, der Patch `blech-theme` |
| [hintergrund/dsp-erster-blick.md](hintergrund/dsp-erster-blick.md) | Der DSP (Blackfin): Strom, Filter, Effekt-Einheiten |
| [hintergrund/panel-controller.md](hintergrund/panel-controller.md) | Der Mikrocontroller im Bedienfeld: Abbild, Update, Auflösung von Reglern und Touchpad, LEDs |
| [hintergrund/sequencer-timing.md](hintergrund/sequencer-timing.md) | Sequencer-Auflösung, MIDI-Clock ein und aus, Tempo |
| [hintergrund/patternwechsel.md](hintergrund/patternwechsel.md) | Warum ein Patternwechsel eine Lücke hat und wo man einhaken kann |

Die Tools in `tools/` haben je eine kurze Erklärung in [development.md](development.md), der
Emulator zusätzlich in [../tools/emu/README.md](../tools/emu/README.md) und der Linux-Sender in
[../tools/alsa-sysex.md](../tools/alsa-sysex.md). Die Herkunft der Bestandteile steht in
[../NOTICE](../NOTICE).
