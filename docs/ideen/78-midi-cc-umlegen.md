# 78. Plugin: MIDI-CC je Regler umlegen

Wunsch (Community, 30.10.): `korg.setMidiCC("Cutoff", 37, range)`, besser je Part. Jeder Regler hat einen MIDI-CC. Roland-Geräte
nehmen für Cutoff CC 60, die Electribe sendet 37 (Angabe des Nutzers), er will, dass ein Regler den CC des externen Geräts
schickt. Zusatz: der Novation Circuit Tracks könnte MIDI-Presets laden. Stand 2026-10-30: **aufgeschrieben, nichts gebaut, am
Gerät nichts.** Marker: **gemessen**, **hergeleitet**, **ungeprüft**.

## Was es schon gibt

- Die CC-Tabelle der Electribe liegt als Messung vor ([CC-Map](../messungen/2026-09-16-cc-map.md)) und steckt als
  Beleg `measure:2026-09-16/cc-map` in `data/map/pattern.mjs` (Cutoff, Resonance, Level, IFX Edit und weitere). (gemessen)
- Widerspruch zur Meldung: die Messung nennt für Cutoff **CC 74**, nicht 37. Was der Nutzer meint (andere Firmware, anderes
  Gerät, Verwechslung mit einer anderen Nummer), ist **ungeprüft**.
- Plugins bekommen Regler als `korg.knobs` (Ereignis `knob`, Index siehe Idee 74). Eine API für MIDI-Ausgang gibt es in
  `data/script/contract.mjs` (API 12) nicht, die Suche nach MIDI-Funktionen dort fand nichts. (ungeprüft im Detail, nur gegrept)
- Noten gehen über `0xC005AD44` und senden "zugleich MIDI auf DIN und USB" (`docs/hintergrund/skript-laufzeit.md`). Ob es
  eine entsprechende Routine für CC gibt, ist **ungeprüft**.

## Offen

- Wo die Firmware beim Drehen eines Reglers den CC sendet, und ob sich Nummer und Bereich dort umbiegen lassen (global oder je
  Part). (ungeprüft)
- Ob der Regler dabei weiter den internen Klang ändern soll, oder nur den CC schickt (Regler "entkoppeln", vgl. Idee 74,
  Ereignisse verschlucken).
- Ob die Tabelle für alle Regler gelten soll oder nur für eine Auswahl.
- Presets (Circuit Tracks und andere): eine Datei auf der Karte mit Name, Regler, CC, Bereich. Format offen.

## Plan (grob, hergeleitet)

1. Suchen, wo die Firmware den Regler-CC ausgibt (Emulator, MIDI-Ausgang des Emulators mitschneiden).
2. `korg.setMidiCC(regler, cc, min, max)` je Part, mit Liste erlaubter Regler. Beim Beenden alles zurückgeben (wie `ledHold`).
3. Plugin mit Preset-Auswahl, Presets als Dateien unter `KORG/blechtribe/`.
4. Rot und blau prüfen.
