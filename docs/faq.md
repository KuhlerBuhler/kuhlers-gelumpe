# Häufige Fragen

Stand: 26. Oktober 2026. Kurze Antworten auf Fragen, die Neue stellen. Jede Antwort sagt dazu, was
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
