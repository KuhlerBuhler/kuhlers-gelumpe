# 81. Filter schnell an und aus mit SHIFT + Filtertaste

Wunsch (Community, 30.10.): SHIFT + Filtertaste schaltet das Filter schnell an und aus und holt beim Wiedereinschalten denselben
Filtertyp zurück, statt wie bei Hacktribe durch alle Modi zu wechseln. Je Taste ein eigener Speicher: von LPF Acid auf HPF
wechseln gibt den zuletzt benutzten HPF-Typ (zum Beispiel OB HPF). Stand 2026-10-30: **aufgeschrieben, nichts gebaut, am Gerät
nichts.** Marker: **gemessen**, **hergeleitet**, **ungeprüft**.

## Was es schon gibt

- [Idee 55](../ideen.md): LPF, HPF und BPF laufen durch MS20, MG, P5, OB und Acid, im Emulator gebaut, am Gerät offen
  ([Messung](../messungen/2026-10-15-synth-filter.md)). Die Taste wählt heute den Typ reihum. (gemessen im Emulator)
- Filtertyp liegt im Part an Offset 12, Werte 0 bis 16 (`data/map/pattern.mjs`, Beleg `measure:2026-09-17/filter-types`).
  Ob "Filter aus" ein eigener Wert in diesem Bereich ist, ist **ungeprüft**.
- SHIFT + LPF, HPF, BPF tun heute dasselbe wie ohne SHIFT (Filtertyp wechseln), `docs/tastenkombinationen.md`. Die
  Kombination ist also frei. (gemessen, Tabelle dort)
- Plugins können Tasten umlegen (`korg.remapKey`), aber nur bei offener App; Filtertasten gehen sonst an die Firmware
  (`docs/hintergrund/skript-laufzeit.md`, Idee 74).

## Offen

- Was "aus" am Klang bedeutet (Filter umgangen, Cutoff voll offen, oder ein eigener Typ).
- Der Speicher je Taste (LPF, HPF, BPF): im RAM, pro Part, und ob er mit dem Pattern gespeichert oder beim Ausschalten
  verworfen wird. Auf der Karte (`KORG/blechtribe/`) wäre es dauerhaft.
- Verhalten beim Patternwechsel und beim Laden (Typ kommt aus dem Pattern, Speicher gilt nur für die laufende Sitzung?).
- Ob auch ein Wechsel der Taste ohne SHIFT den Speicher benutzen soll (LPF Acid, dann HPF gibt den letzten HPF-Typ), oder nur
  SHIFT + Taste.

## Plan (grob, hergeleitet)

1. Tastenauswahl aus Idee 55 lesen (`tools/patch/`), die Stelle finden, an der der Typ gesetzt wird.
2. Je Taste ein Byte "letzter Typ", beim Tastendruck befüllt.
3. SHIFT + Taste: Filter aus, beim zweiten Druck den gemerkten Typ setzen.
4. Menüpunkt im BLECH-Menü (aus, an), Standard aus. Rot und blau prüfen.
