# 80. Meldung: Klang verzögert auf einer blauen Electribe

Meldung (Community, 30.10., derselbe Nutzer wie Idee 79): Auf seiner blauen Electribe kommt der Klang verzögert, auch am
Kopfhörer direkt am Gerät. Die rote hatte das nicht. Gleich mit Korgs Firmware, mit Hacktribe und mit BLECH, er vermutet die
Hardware. Stand 2026-10-30: **nur Meldung, nichts gemessen, nichts untersucht.** Marker: **gemessen**, **hergeleitet**,
**ungeprüft**.

## Was wir wissen

- Die Angabe "gleich mit allen drei Firmwares" spricht gegen BLECH als Ursache. (hergeleitet, aus der Meldung)
- Wie groß die Verzögerung ist und wie sie gemessen wurde (Gehör, Aufnahme), ist **unbekannt**.
- Ob sie bei allen Klangquellen auftritt (Synth, Sample, Pad, Sequencer, MIDI) oder nur bei einer, ist **unbekannt**.
- Zum Audiopfad der blauen Einheit steht in den Docs nichts über Codec oder Ausgabepuffer. Es gibt nur die DSP-Pfade für
  Sample-Export ([DSP-Audiopfade](../messungen/2026-10-08-dsp-audiopfade.md)). Der Emulator macht keinen Ton in echter Zeit
  (Idee 52), eine Latenz lässt sich dort nicht messen. (aus der Suche in `docs/`, nicht jede Datei gelesen)
- Die eigene Verzögerung der Plugin-Ereignisse (bis 40 ms) betrifft nur Plugins und war hier nicht im Spiel.

## Rückfragen an den Nutzer

- Seriennummer oder Baujahr der blauen Einheit, Firmwarestand (Korg 2.02?).
- Verzögerung bei Pad, Tastatur, externem MIDI-Eingang, laufendem Sequencer? Auf der Schlagseite oder beim Drehen von Reglern?
- Aufnahme mit Handy oder Interface: Pad drücken gegen Ton, Abstand in ms.
- Gibt es eine zweite blaue Einheit zum Vergleich?

## Mögliche Ursachen (ungeprüft)

- Defekt oder Bauteiltoleranz an dieser Einheit (Vermutung des Nutzers).
- Abweichende Hardwarerevision der blauen Reihe.
- Eine Einstellung, die bei der roten fehlt (Quantize, Audio-Puffer, Effekt in der Kette).

## Plan

Nichts bauen, bis eine Messung vorliegt. Danach: gleiche Messung an einer roten und einer anderen blauen Einheit, wenn eine
verfügbar ist.
