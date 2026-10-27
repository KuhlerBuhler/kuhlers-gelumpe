# 70. Plugin Reglertausch

Wunsch: IFX EDIT wird zu Resonance, SHIFT + IFX EDIT zu EG Int, Resonance und EG Int werden zu
Effektreglern. Als Plugin.

Stand 2026-10-27: **nur untersucht, nichts gebaut, am Gerät nichts.** Marker: **gemessen**, **hergeleitet**, **ungeprüft**.

## Befund

- Plugins bekommen jeden Reglerdreh als `knob(index, wert)` im nächsten 40-ms-Bild (`data/script/describe.mjs`). SHIFT kommt
  als Tastenereignis (Taste 10), das Plugin merkt sich selbst, ob SHIFT gehalten ist. (gemessen, Code gelesen)
- Abfangen geht heute nicht: die Firmware wendet den Dreh an (`0xC00423A0`), bevor das Plugin ihn sieht. Die Laufzeit hat
  eine Abfangmaske je Ereignistyp (`SCRIPT_CONTROL_CAPTURE_MASK`), aber keine API dafür und keine je Regler. (gemessen)
- Regler: LEVEL 0, PAN 1, PITCH 2, RESONANCE 3, EG INT 4, MOD DEPTH 5, ATTACK 6, IFX EDIT 7, DECAY 8, OSC EDIT 9,
  MOD SPEED 10 (`data/panel.mjs`). CUTOFF ist ein Drehgeber, kein Regler. (gemessen)
- Einen Dreh auslösen: Firmware-Funktion `0xC0040A50(index, wert)`, im Emulator 55 von 55 gleich wie ein Dreh am Panel
  (Messung TAP Motion). Blau: `0xC003B688`, noch nicht gemessen.
- SHIFT + Regler macht in der Firmware nichts anderes als der Regler allein. (gemessen)
- Der IFX hat pro Part genau einen Wert, `ifxEdit` (0 bis 127). Einen zweiten IFX-Parameter gibt es nicht. (gemessen)
- Resonance und EG Int sind Potis mit fester Stellung: ein umgelegter Regler springt beim ersten Dreh. Abhilfe im Plugin:
  erst übernehmen, wenn der Regler den gespeicherten Wert überfahren hat. (hergeleitet)

## Fehlt in der Laufzeit (zusammen mit Idee 72, eine Plugin-API, API 10)

- `korg.captureKnobs(maske)`: einzelne Regler abfangen, 0 gibt frei, beim Beenden automatisch frei. Neue Maske je Regler
  im Eingangsfilter (`tools/patch/script_hooks.s`).
- `korg.knob(index, wert)`: Dreh auf einem Regler auslösen, aus dem Bild-Hook.
- Der Ring meldet weiter den Original-Regler, damit das Plugin weiß, was gedreht wurde.

## Offen: was steuert der EG-Int-Regler danach?

- (a) Master FX Y: unklar, ob sich das so auslösen lässt, und es gilt für das ganze Pattern.
- (b) Zweiter IFX-Parameter: gibt es nicht.
- (c) Bleibt EG Int: dann gibt es EG Int zweimal. Einfachster Weg, Vorschlag.

## Plan

1. Maske je Regler im Eingangsfilter (erst Sampler, dann Synth).
2. `captureKnobs` und `knob` in Vertrag, Beschreibung, Compiler und Simulation, API-Version hoch.
3. Emulator-Fall: Regler 7 abfangen, 3 und 4 auslösen, gegen einen Lauf ohne Abfangen vergleichen.
4. Plugin mit SHIFT-Merker und Übernahme beim Überfahren.

## Am Gerät zu testen

- Maske 0 verhält sich wie ohne Plugin.
- Werte von IFX EDIT und EG INT nach Abfangen und Auslösen.
- SHIFT während eines Drehs, Freigabe bei EXIT.
- Blau: nimmt `0xC003B688` denselben Aufruf?
