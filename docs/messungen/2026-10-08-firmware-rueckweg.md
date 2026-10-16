# Firmware-Rückweg: geprüfte Quellen und getrennte Verfahren

Stand: 8. Oktober 2026. **Quellen geprüft**, keine Firmware aufgespielt.

## Normaler Updateweg bei laufender Firmware

**Korg-Dokumentation:** Das offizielle Sampler-2.02-Paket enthält auf Seite 2
der englischen Release Notes die Updateanleitung. Eine vom Gerät formatierte
SD-Karte trägt SYSTEM.VSB im System-Unterordner des Sampler-Verzeichnisses.
Nach Einsetzen bei ausgeschaltetem Gerät: starten, DATA UTILITY → SOFTWARE
UPDATE, Versionsanzeige prüfen, Update bestätigen, Abschluss abwarten und
ausschalten. Stabile Stromversorgung ist erforderlich.
[Offizielles Paket samt Anleitung](https://www.korg.com/us/support/download/software/0/368/2579/).

**Hacktribe-Dokumentation:** Die laufende Hacktribe-Anwendung verwendet
`KORG/hacktribe/System/SYSTEM.VSB`.
[Installationsanleitung](https://github.com/bangcorrupt/hacktribe/wiki/How-To).
Der Dateipfad gehört zur laufenden Firmware, nicht allgemein zur Hardwarefarbe.

**Folgerung:** Der normale Menüweg setzt eine funktionierende Anwendung
voraus. Er beweist keine Wiederherstellung nach jedem Firmwarefehler.

## Wiederherstellung, wenn die Startabfrage erscheint

**Hacktribe-Dokumentation:** Wenn das Gerät beim Start nach einem Update
fragt, kann eine passende Werksfirmware auf SD die Wiederherstellung
ermöglichen. Für einen ursprünglich als Sampler verkauften Electribe liegt
sie unter `KORG/electribe sampler/System/SYSTEM.VSB`; für den ursprünglichen
Synth gilt `KORG/electribe/System/SYSTEM.VSB`.
Das ist vom Hacktribe-Menüpfad zu unterscheiden.

**Hacktribe-Dokumentation:** Bleibt das Gerät ohne passende Updateabfrage
beim Start hängen, beschreibt der Hersteller von Hacktribe JTAG/OpenOCD als
Reparaturweg. Ein defekter Secondary Bootloader benötigt dessen separate
Wiederherstellung. Die Anleitung nennt keinen universellen USB-/SD-Modus,
der ohne weitere Voraussetzung jede fehlerhafte Anwendung repariert.
[Debrick-Anleitung](https://github.com/bangcorrupt/hacktribe/wiki/Debrick).

## Prüffolge am eigenen Gerät

**Schutzvorschlag:** Zuerst Gerätetyp und Ausgangsfirmware eindeutig
zuordnen, vollständige Sicherungen und passende Wiederherstellungsdatei
bereitstellen. Dann am funktionierenden Gerät die Update-Menüanzeige und
Dateierkennung prüfen und vor dem Schreiben abbrechen. Ein echter
Hin-/Rück-Updateversuch schreibt Flash und ist ein eigener Versuch; er wurde
bei dieser Untersuchung nicht ausgeführt. Eine absichtlich defekte Firmware
ist kein notwendiger Schritt dieser Quellenprüfung.

Die Quellenprüfung erfüllt den ersten Schritt der Vorbedingung im Konzept, den
Rückweg vor dem Firmware-Schreiben zu erproben.
Sie ersetzt weder einen tatsächlich durchgeführten Hin-/Rück-Updateversuch
noch eine Bestätigung des Reparaturwegs durch eine zweite Person.
