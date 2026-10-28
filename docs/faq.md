# Häufige Fragen

Stand: 28. Oktober 2026. Kurze Antworten auf Fragen, die Neue stellen. Jede Antwort sagt dazu, was
belegt ist und was offen bleibt. Marker wie überall in den Docs: **gemessen**, **offline**,
**hergeleitet**, **offen**.

## Geht mein Gerät kaputt, wenn ich BLECH aufspiele?

Kurz: Ein Fall, in dem ein Gerät durch die Software dauerhaft beschädigt wurde, ist nicht bekannt, ganz
ausschließen kann ihn niemand. Der übliche Weg zurück ist am Gerät geübt. Ein Versprechen, dass nie etwas
schiefgeht, geben diese Docs nicht.

- **BLECH kommt wie ein Update von Korg**, über SOFTWARE UPDATE von der SD-Karte. Der Rückweg über denselben
  Weg ist am Gerät geübt: eine Firmware aus dem Patcher hin, das Original zurück (**gemessen**, 10. Oktober,
  [Rückweg geübt](messungen/2026-10-10-rueckweg-geuebt.md)).
- **Das Startprogramm (Bootloader) wird nie angefasst.** Der Patcher fasst es nicht an, und der Editor sperrt
  den Bereich (Flash `[0, 0x20000)`, [Sperrliste](speicherbereiche.md#die-sperrliste-als-maschinenregel)).
- **Was trotzdem passieren kann**, aus [Was kaputtgehen kann](patcher.md#was-kaputtgehen-kann):
  - Die Firmware stürzt ab oder hängt im Betrieb: Neustart.
  - Die geflashte Firmware startet nicht und das Gerät fragt nach einem Update: Korgs Original-VSB von der
    SD-Karte (laut Hacktribe-Doku, selbst nicht durchgespielt).
  - Die Firmware hängt, bevor die Update-Abfrage kommt: nur JTAG, auch wenn niemand den Bootloader angefasst
    hat. Dagegen helfen die Regeln (zum Beispiel: keine Patches in der Startphase) und die Prüfungen vor dem
    Export.
  - Das Startprogramm ist überschrieben: nur JTAG. Der Patcher fasst es nie an.
  - Hardwareschaden durch Software: kein Fall bekannt, nicht ausgeschlossen.
  - **offen:** die Rettung, wenn die laufende Firmware nicht mehr startet, siehe [Rettung](rettung.md).
- **Vorher lesen:** Jede Anleitung für den Gerätetest beginnt mit einer Warnung und beschreibt den Weg
  zurück, bevor die Schritte kommen ([Gerätetests](geraetetests/README.md)). Wer es macht, macht es auf
  eigenes Risiko und ohne Gewähr.

## Die Electribe sagt "Error, No File". Was ist falsch?

Kurz: Name, Ordner oder der Ordner einer anderen Firmware. Die Seite [Rettung](rettung.md) im Editor geht es mit dir durch.

- **Der Name ist genau `SYSTEM.VSB`.** Lädst du die Datei ein zweites Mal herunter, nennt der Browser sie oft
  `SYSTEM (1).VSB`. Umbenennen. Blendet der Rechner Endungen aus, wird daraus leicht `SYSTEM.VSB.VSB`.
- **Sie liegt im Unterordner `System`**, also `KORG/<Ordner>/System/SYSTEM.VSB`. Fehlt `System`, leg ihn an.
- **Der Ordner der Firmware, die jetzt läuft:** `electribe sampler` (Korgs rote), `electribe` (Korgs blaue),
  `hacktribe` oder `blechtribe`. Benenn keinen Ordner um: `blechtribe` nimmt die Firmware erst, wenn BLECH läuft.
- **Im Patcher die richtige Electribe gewählt?** Für die rote und die blaue nennt er verschiedene Ordner. Der Patcher
  sagt am Ende, wohin die Datei gehört.

Die Fälle stammen aus dem Discord (**gemessen**, Chat und Fotos). Welche Datei wohin gehört:
[Rettung, Welche Datei in welchen Ordner](rettung.md#welche-datei-in-welchen-ordner).

## Die Electribe sagt "Error, Invalid File"

Die Firmware hat eine Datei gefunden, die nicht zu ihr passt, und schreibt nichts (**offline**, Emulator).

- **Aus dem Patcher:** meist für die andere Electribe gepatcht. Neu patchen und die Farbe des Geräts wählen.
- **Beim Einschalten auf einer blauen, auf der früher Hacktribe war:** Sie kann sich beim Start noch für einen Sampler
  halten und nimmt dann nur eine Sampler-Datei unter `KORG/electribe sampler/System/` (**hergeleitet**, ein Gerätefall
  im Discord, welcher Weg dort half, ist **offen**).
- **Zurück zu Korgs blauer Firmware, während Hacktribe läuft:** Die Datei braucht zwei geänderte Kopf-Bytes, siehe
  [Rettung](rettung.md#welche-datei-in-welchen-ordner). Die App macht das noch nicht.

## Die App findet meine Electribe nicht

- **Oben "Echtes Gerät" gewählt?** Nur in diesem Modus verbindet die App, auch automatisch (**offline**, Code).
- **Ports, die auf `PAD/KNOB` oder `SOUND` enden** (Einstellungen, MIDI-Bericht): Das ist Korgs eigener
  USB-MIDI-Treiber. Unter Windows kommen über ihn die Antworten der Electribe nicht an, entfern ihn im Geräte-Manager
  (**gemessen**, Windows, 28.10.). Am Mac ist das **offen**: dann den MIDI-Bericht ins Discord posten.
- **Gar keine Electribe im Bericht:** eingeschaltet, Datenkabel statt Ladekabel, anderer USB-Anschluss
  (**hergeleitet**).

Die Rettung liest den MIDI-Bericht selbst und sagt, welcher Fall es ist.

## Mein Pattern-Export zeigt alte Patterns, oder es kommt nichts Neues auf die Karte

Kein Fehler in BLECH ([Messung](messungen/2026-10-28-pattern-export.md), **gemessen** im Emulator):

- **Erst WRITE, dann EXPORT PATTERN.** Der Export schreibt das gespeicherte Pattern, Änderungen ohne WRITE sind nicht
  in der Datei. Korgs und Hacktribes Firmware machen es genauso.
- **Exporte liegen in `KORG/blechtribe/`.** Die Übernahme beim ersten Start kopiert den alten Ordner dorthin und lässt
  ihn stehen. Importier nur aus `KORG/blechtribe/`.
- **Auf der blauen** gibt es die Übernahme nicht: Exporte liegen in `KORG/blechtribe/`, die alten Patterns bleiben in
  `KORG/electribe/`.
- **Das Datum ist immer der 01.01.2014**, die Electribe hat keine Uhr. Ein Export mit demselben Namen ersetzt die Datei,
  am Rechner sieht der Ordner gleich aus.

## Die volle Prüfung im Patcher wird rot

Auf dein Gerät kommt dann nichts. Vor App 1.3.7 scheitert die volle Prüfung, wenn im Emulator Patterns gespeichert
sind (**gemessen**, `test/emulator-check-flash.test.mjs`). Mit einer älteren App: `~/.gelumpe/flash/flash.bin`
umbenennen (unter Windows liegt `.gelumpe` im Benutzerordner) und die Prüfung neu starten, oder die App aktualisieren.
Bleibt sie rot, schick `~/.gelumpe/emu.log` mit.
