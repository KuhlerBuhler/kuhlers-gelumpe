# Gerätetests: Anleitungen für Tester

Das meiste, was dieses Projekt an der Electribe tut, ist im Emulator gemessen. Diese Anleitungen sind für Leute, die
es an ihrer eigenen Electribe nachvollziehen und das Ergebnis melden. Jede Anleitung sagt vorher, was am Ende belegt
sein soll, und trennt "am Gerät bestätigt" von "nur im Emulator gemessen" und "offen".

**Das Gerät wird dabei verändert.** Der Kartentest schreibt Code in den RAM und eine Datei auf die SD-Karte, die
übrigen Anleitungen spielen eine geänderte Firmware auf oder setzen sie voraus. Jede beginnt mit einer Warnung und
beschreibt den Weg zurück, bevor die Schritte kommen. Lies beides, bevor du anfängst. Machst du es, dann auf eigenes
Risiko und ohne Gewähr.

## Die Anleitungen

Reihenfolge einhalten: erst die Karte, dann die BLECH-Datei, dann die übrigen.

| Anleitung | Was sie prüft | Gerät wird verändert |
|---|---|---|
| [karte.md](karte.md) | Die Dateifunktionen der Firmware lesen und schreiben eine kleine Datei auf der SD-Karte. | RAM (einmaliger Probe-Code) und eine Datei auf der Karte, keine Firmware |
| [blech-datei.md](blech-datei.md) | Die Firmware mit dem BLECH-Satz über SOFTWARE UPDATE aufspielen, den Notschalter prüfen, dazu SysEx, FLASH READ, HT OSC, CATEGORY, das Menü BLECH, Anpassung, Plugins und Blechy am Gerät. | Firmware im Flash, Karte |
| [live.md](live.md) | Ladebalken, eigenes Startbild, Patternwechsel mit Bestätigung, TAP Motion und Notenassistent, an der Firmware mit dem BLECH-Satz. | nichts, nur Karte und Bedienen |
| [blech-1.3.md](blech-1.3.md) | Bedien- und Displaytest von BLECHTRIBE 1.3: Start, Blechy, PATTERN CONFIRM, Synth-Filter, SPLASH DRAW, CALIBRATE DISPLAY, Doom. | Einstellungen, nur mit Sicherung |
| [doom-v21.md](doom-v21.md) | BLECH v21 mit Doom-Lader aufspielen, Doom mit SHIFT + TAP starten, spielen, beenden. | Firmware im Flash, Karte |
| [firmware-sprache.md](firmware-sprache.md) | Gerätemenüs auf Deutsch (Patch `lang-de`): alle Seiten, Dialoge und Meldungen am Display, ein Update behält die Sprache. | Firmware im Flash |
| [offene-geraetetests.md](offene-geraetetests.md) | Vorbereitete, noch nicht gelaufene Tests: MFX 2 mit GATE ARP, Effekt-Bausteine im DSP, die rote mit blauer Firmware, Gerätename über USB. | je nach Test RAM oder Firmware im Flash |

Die Messung der MIDI-Clock am Gerät steht in [Sequencer-Timing](../hintergrund/sequencer-timing.md#5-am-gerät-messen-offen).

## Was für alle Tests gilt

- **Gerät:** Electribe 2 Sampler mit Firmware 2.02 und
  [Hacktribe](../glossary.md#hacktribe) ([Quelle](https://github.com/bangcorrupt/hacktribe)). Die Werkzeuge sind nur an
  diesem Stand gemessen, die Adressen verschieben sich bei einem anderen Stand. Die
  Werkzeuge prüfen die Firmware vorab und brechen bei einer Abweichung ab, ohne zu
  schreiben.
- **Eigene Firmwaredatei:** Die [`SYSTEM.VSB`](../glossary.md#vsb) kommt von dir. Es wird keine Firmware
  mitgeliefert und nichts davon hochgeladen. Auch Flash-Dumps, Pattern-Sicherungen
  und Samples bleiben bei dir. Gemeldet werden nur Textausgaben und Prüfsummen.
- **Netzteil**, kein Batteriebetrieb, bei jedem Test. Beim Update ist stabiler Strom
  Pflicht ([Quellenprüfung](../messungen/2026-10-08-firmware-rueckweg.md)).
- **Vorher sichern:** SD-Karte komplett kopieren, den Global-Block lesen (Befehl in
  den Anleitungen), bei Firmware-Tests die eigene Original-`SYSTEM.VSB` samt Prüfsumme.
  Am 13.10. fielen am Gerät die Globals auf die Vorgabe zurück, die Ursache ist offen
  ([Messung](../messungen/2026-10-13-globals-zurueckgesetzt.md)). Deshalb wird
  vor jedem Test gesichert, nicht danach.
- **Nach einer Abweichung** im Global-Menü nicht ausschalten und nicht WRITE drücken,
  solange der RAM nicht stimmt: Ausschalten und WRITE speichern, was gerade im RAM steht.
- **FACTORY RESET** steht in DATA UTILITY direkt vor SOFTWARE UPDATE. Beim Blättern auf
  das Display sehen, nicht über zwei Seiten scrollen. Nach dem Bestätigen sind Patterns
  und Globals weg.
- **Python-Werkzeuge** (`tools/device/`): Python 3 mit `mido`, das Gerät per USB am
  Rechner. Es muss genau ein MIDI-Port mit "electribe" und "SOUND" im Namen da sein.
  Gelesen wird nur mit den Lesebefehlen der Firmware, nie ab Flash-Adresse `0x1000000`
  (dort antwortet das Gerät nicht mehr, [Speicherbereiche](../speicherbereiche.md)).

## Markierungen

- **am Gerät bestätigt:** an einem echten Gerät beobachtet oder gelesen.
- **im Emulator gemessen:** mit der echten Firmware im Emulator ausgeführt, am Gerät
  nicht geprüft.
- **hergeleitet:** aus Code oder Messungen geschlossen, nicht beobachtet.
- **offen:** nicht geprüft oder unklar. Steht so auch in den Ergebnistabellen.

## Ergebnisse melden

Je Schritt eine Zeile: Nummer, "ok", "anders" oder "nicht gelaufen", bei "anders" die
Ausgabe des Werkzeugs oder was das Display zeigt (Text, Seitenzähler, Fehlerzeile). Bei
Abweichungen die vollständige Ausgabe aufheben. Wohin die Meldung geht, steht
im Projekt (offen: derzeit kein festgelegter Meldeweg).

## Verwandte Dokumente

- [Plugins](../plugins.md): Sprache, Ereignisse, Dateien für die Karte, Menü BLECH
- [Patcher](../patcher.md): wie die Firmwaredatei gebaut und geprüft wird, Notschalter
- [Rettung](../rettung.md): welche Datei in welchen Ordner gehört, wenn das Gerät nicht startet
- [Speicherbereiche](../speicherbereiche.md): was am Gerät wie geschützt ist
- [Tastenkombinationen](../tastenkombinationen.md): Startmodi und gehaltene Tasten
