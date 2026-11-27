# Ideen und offene Forschung

Hier steht, was noch nicht gebaut oder noch nicht entschieden ist. Eine Idee hier ist keine Freigabe; was gebaut wird,
steht danach in den Fachseiten ([Übersicht](README.md), [Entscheidungen](entscheidungen.md)). Ideen mit mehr als einem
Satz Beschreibung haben eine eigene Seite in `docs/ideen/`. Aufbau, Start und Bedienung des Emulators stehen in
[Emulator](emulator.md).

Was als Nächstes kommt, steht im [Fahrplan](fahrplan.md); die Liste unten ist breiter und nicht nach Version geordnet.

## Leitplanke

Ein Absturz oder Datenverlust ist akzeptabel. Schäden an Software, Hardware oder SD-Karte sind es nicht. Daraus folgt:
Experimente gehen zuerst über RAM oder gegen ein vollständiges, wiederherstellbares SD-Backup; Firmware und Flash bleiben
gesperrt, bis ein Rückweg belegt ist.

## Samples und Speicher

| Idee | Stand |
|---|---|
| **Sample Swap abschließen:** Der Sample Swap (Dateien größer als der DSP-Speicher, Nachladen von der Karte) ist im Patch-Satz BLECH auf develop, aber nicht veröffentlicht. Offen: den Gesamtexport (EXPORT ALL SAMPLE) durch das dauerhafte Speichern jedes geänderten Slots ersetzen und Gerätetests zu Klang, Stimmen und Aufnahme. | im Emulator geprüft, am Gerät offen ([Patcher](patcher.md), [Bau](messungen/2026-10-26-sample-swap-bau.md), [Speicherdienst](messungen/2026-10-27-sample-store.md)) |
| **Samples über das Kabel rein und raus, ohne Karte umzustecken.** Hinzufügen und Entfernen geht über USB auf der Seite `Gerät -> Samples` (rot). Offen: einzelne Samples als WAV zurückholen, die übrigen Dateien der Karte lesen, Import ganz ohne SD-Karte aus einem RAM-Puffer. | teilweise gebaut ([Sample-Datei](hintergrund/sample-datei.md), [Virtuelle SD-Karte](hintergrund/virtuelle-sd.md), [Import ohne Karte](messungen/2026-10-08-usb-sample-import-offline.md)) |
| **SD-Karte über USB lesen,** ohne sie aus dem Gerät zu nehmen. | Dateifunktionen der Firmware im Emulator aufgerufen, Host-Zugriff am Gerät ungeprüft ([Virtuelle SD-Karte](hintergrund/virtuelle-sd.md)) |
| **Werks-Samples über das Kabel ersetzen:** die dauerhaft gespeicherte Samplebank überschreiben. Am Gerät geht es über das Import-Menü (Patch `import-slots`, Slots ab 19, mit Hacktribe ab 275); offen ist der Schreibweg über Kabel und ob die Bank die Slots ab 501 abdecken kann. | Menüweg im Emulator, Kabelweg offen ([Flash](messungen/2026-10-07-werks-sample-flash.md), [Import](messungen/2026-11-16-import-werks-slots.md)) |
| **Sample-Export als Übertragungsweg:** exportiertes Audio über einen Arbeitspuffer per Kabel abholen. | Exportpfad offline untersucht, am Gerät offen ([DSP-Pfade](messungen/2026-10-08-dsp-audiopfade.md)) |
| **Sample-Metadaten im RAM ändern.** Name und Tune sind auf der Seite Samples editierbar (live ins RAM, durch den Türsteher). Offen: ob eine Änderung einen Neustart überlebt oder mit EXPORT ALL SAMPLE auf die Karte geht, die Skala von Tune, was ein Schreiben der übrigen Felder bewirkt. | teilweise ([Namen](messungen/2026-10-07-sample-name-ram.md), [Metadaten](messungen/2026-10-07-sample-metadaten-ram.md), [Gerätekarte](geraetekarte.md)) |
| **Sample-Editor am Gerät:** ein Sample ins RAM holen, schneiden, normalisieren, umdrehen, ein- und ausblenden, zurückschreiben. | Idee ([Idee 59](ideen/59-sample-editor.md)) |
| **Wellenform beim Schneiden (rot):** beim Einstellen von Start und Ende zeigt das Display Wellenform und Ausschnitt. | untersucht ([Sample-Editor](ideen/59-sample-editor.md#wellenform-beim-schneiden-rot)) |
| **Time-Stretch am Gerät:** Tempo eines Samples ändern, ohne die Tonhöhe zu ändern; offline auf dem ARM machbar, live braucht DSP-Zeit. | untersucht ([Sample-Editor](ideen/59-sample-editor.md#time-stretch-am-gerät), [Time Stretch](messungen/2026-11-17-time-stretch.md)) |
| **Nach dem Resampling auf dem Pad bleiben:** die Auswahl springt danach auf Pad 1. | Ursache offen, im Emulator nicht nachstellbar ([Idee 101](ideen/101-resampling-auf-dem-pad-bleiben.md)) |
| **Samples vor dem Ausschalten exportieren oder automatisch sichern:** das Gerät fragt beim Ausschalten, ob alle Samples exportiert werden sollen. | Wunsch aus der Community |
| **Sample-Wechsel in einem Part per LFO.** | Wunsch aus der Community |
| **OSC Drawer:** einen eigenen Oszillator auf dem Touchpad malen und als User-Sample speichern. | Idee ([Idee 51](ideen/51-osc-drawer.md)) |
| **Synthetische Samples am Rechner:** Kicks, Basslines und mehr im Host rendern und als Sample importieren. | Idee |
| **Noten aus einer MIDI-Datei auf einen Part schreiben.** | Wunsch ([Idee 111](ideen/111-midi-datei-auf-part.md)) |
| **OSCs der EMX auf die E2 laden.** | Wunsch aus der Community, nicht untersucht |
| **Schneller laden, weniger Strom:** Kartentakt, Zeichnen beim Laden, Energiesparen. | recherchiert, am Gerät nichts gemessen ([Idee 56](ideen/56-laden-und-strom.md)) |

## Klang und DSP

Der [DSP](glossary.md#dsp) ist der Blackfin-Prozessor, der den Klang rechnet. Sein Code steckt in der VSB und ist
teilweise gelesen ([DSP, erster Blick](hintergrund/dsp-erster-blick.md)).

| Idee | Stand |
|---|---|
| **Ton im Emulator:** der echte DSP-Code läuft im Emulator (QEMU-Worker), aber ohne Ausgabe und zu langsam für Echtzeit. | offen ([Idee 52](ideen/52-ton-im-emulator.md)) |
| **Zweiter Master-Effekt,** getrennt vom Touchpad. Es ist unbekannt, ob der DSP ihn rechnen kann. | offen ([Idee 53](ideen/53-zweiter-master-effekt.md), [MFX und DSP](messungen/2026-10-09-mfx-dsp.md)) |
| **Eigene Filtertypen,** auch ein echter TB-303-Filter: ein neuer Typ aus vorhandenen DSP-Kernen ist ARM-seitig möglich, ein neuer Kern braucht die DSP-Forschung. | Idee ([DSP, erster Blick](hintergrund/dsp-erster-blick.md)) |
| **Mehrere Insert-Effekte auf einem Pad schichten.** Der Eingriff in die Soundengine wäre groß. | Wunsch aus der Community |
| **Einfacher Effekt-Baukasten** nach dem Touchpad-Modell, der auch ohne Vorwissen funktioniert. | Wunsch aus der Community |
| **Rot bei digitalem Clipping:** das Display-Licht wird rot, wenn der Ausgang clippt, als Menüoption. | Idee, Pegelquelle unbekannt |
| **Lücke beim Patternwechsel:** Stille von etwa 100 ms. | Ursache hergeleitet, am Gerät offen ([Patternwechsel](hintergrund/patternwechsel.md#frage-2-lücke-beim-patternwechsel)) |
| **Klang verzögert auf einer blauen Electribe,** mit Korg, Hacktribe und BLECHTRIBE gleich. | Meldung, Ursache unbekannt ([Idee 80](ideen/80-latenz-blaue-electribe.md)) |
| **Blechy spricht:** eine synthetische Stimme (Formanten, Pulse, Rauschen) statt fester Töne, auch für Ein- und Ausschalten. | Idee, nicht recherchiert |
| **Die ganze Firmware erfassen:** alle Befehle und Funktionen statt einzelner Ausschnitte. | Speicherkarte zusammenhängend, Code nicht vollständig zugeordnet ([Speicherbereiche](speicherbereiche.md)) |

## Bedienung am Gerät

| Idee | Stand |
|---|---|
| **Parameter-Locks im Step-Editor,** bis hin zu einem vollen Motion Edit. | Wunsch aus der Community |
| **Ratchet:** ein Step löst 2 oder 4 Mal aus. | Wunsch aus der Community, ein Pull Request ist willkommen |
| **TAP-Taste frei belegbar.** | untersucht ([Idee 34](ideen/34-tap-shortcut.md)) |
| **Gate Arp: Y wählt den Rhythmus.** | Wunsch ([Idee 102](ideen/102-gate-arp-y-rhythmus.md)) |
| **Gate Arp: Start auf dem Raster** statt im Moment der Berührung. | Meldung ([Idee 79](ideen/79-gate-arp-takt-start.md)) |
| **Aufnahme läuft über eine Kette in einer [Sync Group](glossary.md#sync-group) weiter.** | Wunsch ([Idee 112](ideen/112-aufnahme-ueber-kette.md)) |
| **Zweiter IFX-Parameter:** SHIFT + IFX EDIT steuert einen zweiten Effektparameter, auch als Reglertausch (IFX EDIT wird Resonance). Der Reglertausch wurde verworfen, weil der IFX nur einen Wert hat; mehrere Nutzer wünschen es erneut, und der IFX hat laut Entwickler ein X und ein Y, Korg nutzt nur X. Das ist neu zu prüfen. | offen |
| **Einheitliches, scrollbares Kontextmenü für [Plugins](glossary.md#plugin)** mit MENU und ENTER. | Wunsch aus der Community |
| **MIDI-CC je Regler umlegen** (Plugin), mit Presets für externe Geräte. | aufgeschrieben ([Idee 78](ideen/78-midi-cc-umlegen.md)) |
| **USB-Symbol auf dem Hauptbildschirm,** solange ein Rechner angesteckt ist. | untersucht ([Idee 67](ideen/67-usb-symbol.md)) |
| **Neustart ohne Ausschalten,** auch nach dem Firmware-Update. | Watchdog-Stub und Emulator, Gerät offen ([Idee 77](ideen/77-neustart.md)) |
| **Eigene Schrift** pixeln und beim Patchen einbauen; **UI-Themes** mit eigenen Strings und Bitmaps (Invertieren braucht wohl Code). | untersucht ([Idee 73](ideen/73-schrift-editor.md), [LCD](messungen/2026-10-12-lcd-helligkeit.md)) |
| **Bekannte Firmware-Bugs fixen,** die Korg nicht fixt. | offen, konkrete Bugs sammeln |
| **Vor dem Verwerfen ungespeicherter Änderungen fragen,** auch bei der Pad-Auswahl (MIDI Program Change nicht, dort steuert ein Rechner). | das Rad blättert gestoppt mit ungespeicherten Änderungen schon, statt zu laden ([PATTERN CONFIRM](plugins.md#das-menü-blech-am-gerät)); Pad offen (Idee 57) |

## Firmware-Grundlagen

| Idee | Stand |
|---|---|
| **Objekt-API im Terminal,** etwa `electribe.ram.MFX_Presets[0].parameter.level = 64`, aus der der passende Gerätezugriff entsteht. | Vorschlag, Schreibzugriff nicht gebaut ([Idee 36](ideen/36-terminal.md)) |
| **Eigene Firmware auf Freetribe-Basis** (AGPL: Treiber und Kernel, eigenes Menü obendrauf). Hacktribe ist Patches auf Stock, keine Basis. | Vorschlag, großer Aufwand |
| **Eigene einfache Sound-Engine im Emulator** statt echter Blackfin-Emulation. | Vorschlag |

## Werkzeuge und Doku

| Idee | Stand |
|---|---|
| **Blechy schreibt Plugins:** ein Chat im Editor der Seite Plugins, ein lokales Sprachmodell schreibt den Code. | geplant, nicht gebaut ([Idee 62](ideen/62-blechy-assistent.md)) |
| **News nach dem Update aus den Release Notes erzeugen:** `data/news.mjs` wird von Hand gepflegt, der letzte Eintrag ist 1.3.7. | Idee ([Release](development.md)) |
| **Ein gemeinsames Format für alle Anpassungen,** in einer Datei wie bei der ESX. | später neu zu planen |
| **Video-Tutorial zur Installation:** ein Hinweis für den Wizard und die Startseite. | Wunsch aus der Community |

## Bewusst verworfen

- **Projekte:** Pattern- und Sample-Sätze aus mehreren Projektordnern laden. Samples kommen einzeln in den Sample-Ordner,
  dazu der Sample Swap.
- **Makros für die ganze Bedienung:** TAP MOTION deckt das Nötige ab.
- **Übergangs-Patterns aus zwei Patterns erzeugen:** Generator, Seite und Doku sind wieder entfernt.
- **128 Steps statt 64:** als Patch praktisch ausgeschlossen (Step, Slot und Bank sind fest); gelöst über SYNC GROUP, zwei
  Patterns einer Gruppe spielen wie eines (rot und blau).
- **Leere Sample- und Patternbank laden,** um Unbekanntes im RAM zu erkennen: das Ausblenden in der RAM-Suche geht ohne das
  Gerät zu leeren.
