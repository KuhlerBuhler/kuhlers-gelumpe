# 78. Plugin: MIDI-CC je Regler umlegen

Wunsch aus der Community: `korg.setMidiCC("Cutoff", 37, range)`, besser je Part. Jeder Regler hat einen MIDI-CC. Roland-Geräte
nehmen für Cutoff CC 60, die Electribe sendet 37 (Angabe des Nutzers), er will, dass ein Regler den CC des externen Geräts
schickt. Zusatz: der Novation Circuit Tracks könnte MIDI-Presets laden.

Status: offen, nichts gebaut. Marker: **gemessen**, **hergeleitet**, **ungeprüft**. Zurück zu den [Ideen](../ideen.md).

## Was es schon gibt

- Die CC-Tabelle der Electribe liegt als Messung vor ([CC-Map](../messungen/2026-09-16-cc-map.md)) und steckt als
  Beleg `measure:2026-09-16/cc-map` in `data/map/pattern.mjs` (Cutoff, Resonance, Level, IFX Edit und weitere). (gemessen)
- Widerspruch zur Meldung: die Messung nennt für Cutoff **CC 74**, nicht 37. Was der Nutzer meint (andere Firmware, anderes
  Gerät, Verwechslung mit einer anderen Nummer), ist **ungeprüft**.
- Plugins bekommen Regler als Ereignis `knob`. Seit Plugin-API 30 gibt es `korg.midi.cc`, `.noteOn`, `.noteOff` und
  `.program`, mit denen ein Plugin selbst MIDI sendet (`data/script/contract.mjs`); ein Umlegen des CC, den die Firmware
  für einen Regler sendet, ist das nicht.
- Noten gehen über `0xC005AD44` und senden "zugleich MIDI auf DIN und USB" (`docs/hintergrund/skript-laufzeit.md`). Ob es
  eine entsprechende Routine für CC gibt, ist **ungeprüft**.

## Offen

- Wo die Firmware beim Drehen eines Reglers den CC sendet, und ob sich Nummer und Bereich dort umbiegen lassen (global oder je
  Part). (ungeprüft)
- Ob der Regler dabei weiter den internen Klang ändern soll, oder nur den CC schickt (Regler "entkoppeln": Eingaben verschlucken, API 13).
- Ob die Tabelle für alle Regler gelten soll oder nur für eine Auswahl.
- Presets (Circuit Tracks und andere): eine Datei auf der Karte mit Name, Regler, CC, Bereich. Format offen.

## Plan (grob, hergeleitet)

1. Suchen, wo die Firmware den Regler-CC ausgibt (Emulator, MIDI-Ausgang des Emulators mitschneiden).
2. `korg.setMidiCC(regler, cc, min, max)` je Part, mit Liste erlaubter Regler. Beim Beenden alles zurückgeben (wie `ledHold`).
3. Plugin mit Preset-Auswahl, Presets als Dateien unter `KORG/blechtribe/`.
4. Rot und blau prüfen.
