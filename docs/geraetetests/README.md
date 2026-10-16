# Gerätetests: Anleitungen für Tester

Stand 2026-10-14. Alles, was in diesem Projekt bisher an der Electribe läuft, ist
zum größten Teil im Emulator gemessen. Diese Anleitungen sind für Leute, die es an
ihrer eigenen Electribe nachvollziehen und das Ergebnis melden. Jede Anleitung sagt
vorher, was am Ende belegt sein soll, und trennt "am Gerät bestätigt" von "nur im
Emulator gemessen" und "offen".

**Das Gerät wird dabei verändert.** Der Kartentest schreibt Code in den RAM und eine
Datei auf die SD-Karte, der Test der BLECH-Datei spielt eine geänderte Firmware auf.
Jede Anleitung beginnt mit einer Warnung und beschreibt den Weg zurück, bevor die
Schritte kommen. Lies beides, bevor du anfängst. Machst du es, dann auf eigenes
Risiko und ohne Gewähr.

## Die Anleitungen

Reihenfolge einhalten: erst die Karte, dann die BLECH-Datei.

| Anleitung | Was sie prüft | Gerät wird verändert |
|---|---|---|
| [karte.md](karte.md) | Die Dateifunktionen der Firmware lesen und schreiben eine kleine Datei auf der SD-Karte. Gehört vor alles, was Plugins von der Karte lädt. | RAM (einmaliger Probe-Code) und eine Datei auf der Karte, keine Firmware |
| [live.md](live.md) | Patternwechsel mit Bestätigung, Ladebalken und eigenes Startbild, an der Firmware mit dem BLECH-Satz (nach der BLECH-Datei). | nichts, nur Karte und Bedienen |
| [blech-datei.md](blech-datei.md) | Die Firmware mit dem BLECH-Satz (Startbild-Editor, MFX 2, Plugins von der Karte, Menü BLECH) wird über SOFTWARE UPDATE aufgespielt und durchgespielt. | Firmware im Flash, Karte |

Wer nur den Kartentest macht, ändert keine Firmware. Die BLECH-Datei setzt voraus,
dass der Kartentest am Gerät bestanden ist.

## Was für alle Tests gilt

- **Gerät:** Electribe 2 Sampler mit Firmware 2.02 und
  [Hacktribe](https://github.com/bangcorrupt/hacktribe). Die Werkzeuge sind nur an
  diesem Stand gemessen, die Adressen verschieben sich bei einem anderen Stand. Die
  Werkzeuge prüfen die Firmware vorab und brechen bei einer Abweichung ab, ohne zu
  schreiben.
- **Eigene Firmwaredatei:** Die `SYSTEM.VSB` kommt von dir. Es wird keine Firmware
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
- [Speicherbereiche](../speicherbereiche.md): was am Gerät wie geschützt ist
- [Tastenkombinationen](../tastenkombinationen.md): Startmodi und gehaltene Tasten

- [Doom auf BLECH v21: manueller Gerätetest](doom-v21.md)
