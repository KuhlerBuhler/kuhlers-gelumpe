# 81. Filter schnell an und aus mit SHIFT + Filtertaste

Wunsch (Community, 30.10.): SHIFT + Filtertaste schaltet das Filter schnell an und aus und holt beim Wiedereinschalten denselben
Filtertyp zurück, statt wie bei Hacktribe durch alle Modi zu wechseln. Je Taste ein eigener Speicher: von LPF Acid auf HPF
wechseln gibt den zuletzt benutzten HPF-Typ (zum Beispiel OB HPF). Stand 2026-11-03: **als Plugin Filter Toggle im Katalog
gebaut (API 14), im Simulator geprüft, am Gerät nichts.** Marker: **gemessen**, **hergeleitet**, **ungeprüft**.

## Was es schon gibt

- [Idee 55](../ideen.md): LPF, HPF und BPF laufen durch MS20, MG, P5, OB und Acid, im Emulator gebaut, am Gerät offen
  ([Messung](../messungen/2026-10-15-synth-filter.md)). Die Taste wählt heute den Typ reihum. (gemessen im Emulator)
- Filtertyp liegt im Part an Offset 12, Werte 0 bis 16 (`data/map/pattern.mjs`, Beleg `measure:2026-09-17/filter-types`).
  0 ist OFF ([Messung](../messungen/2026-09-17-filter-types.md)), 1 bis 6 die LPF-Familie, 7 bis 11 HPF, 12 bis 16 BPF.
  (gemessen)
- SHIFT + LPF, HPF, BPF tun heute dasselbe wie ohne SHIFT (Filtertyp wechseln), `docs/tastenkombinationen.md`. Die
  Kombination ist also frei. (gemessen, Tabelle dort)
- Plugins setzen Part-Werte mit `korg.parts[i].filterType = x` und lassen bei offener App mit `korg.passKeys` einzelne
  Tasten an die Firmware durch (beides API 14, [Plugins](../plugins.md)).

## Gebaut: das Plugin Filter Toggle

Eine App unter TOOLS im Katalog (`data/script/presets.mjs`, Beschreibung in [Plugins](../plugins.md#die-beispiel-plugins)).

- SHIFT + Taste der Familie, die der Part gerade hat: Filter aus (Typ 0). Noch einmal: der Typ, den die Taste zuletzt hatte.
- SHIFT + Taste einer anderen Familie: deren letzter Typ, ohne Speicher deren electribe-Filter.
- Die Taste allein bleibt bei der Firmware. Das Plugin merkt sich nur, welchen Typ sie hinterlässt.
- Der Speicher gilt je Part und Taste, in Variablen des Plugins, bis zum Ausschalten. Nicht auf der Karte, nicht im Pattern.
- Bei offener App gehen alle Tasten an die Firmware, nur die drei Filtertasten nicht, solange SHIFT gedrückt ist. Bei
  geschlossener App dreht die Firmware den Typ zuerst weiter, das Plugin setzt im nächsten Rahmen den richtigen.
  (hergeleitet, im Simulator mit der gemessenen Reihe von Hacktribe nachgestellt)
- Tests: `test/script-plugins.test.mjs` (aus, zurück zum alten Typ, Speicher je Taste und Part, Taste allein unverändert,
  geschlossene App).

## Was der Plugin-API fehlt

- **Tasten ohne offene App zurückhalten.** `korg.passKeys` gilt nur bei offener App. Geschlossen sieht die Firmware SHIFT +
  Filtertaste und dreht den Typ weiter, bevor das Plugin ihn setzt; am Display springt kurz der Zwischentyp auf. Gebraucht
  wird ein `korg.keyHold(taste, an)` wie `korg.knobHold`, das auch ohne App gilt.
- **Kombination im Eingangsfilter.** Das Plugin hält die Filtertasten erst im Rahmen nach SHIFT zurück. Kommt die Filtertaste
  weniger als 40 ms nach SHIFT, geht sie noch an die Firmware. Sauber wäre ein Halten "nur mit SHIFT" im Eingangsfilter.
- **Blaue Electribe.** `korg.seq.setPartValue` schreibt dort nichts, das Plugin wirkt also nur auf der roten.

## Offen

- Was "aus" am Klang bedeutet (Filter umgangen oder Cutoff voll offen). Am Gerät hören.
- Alles am Gerät: Reihenfolge Firmware vor Plugin bei geschlossener App, das Parameterfenster beim Setzen, Patternwechsel.
- Ob auch ein Wechsel der Taste ohne SHIFT den Speicher benutzen soll (LPF Acid, dann HPF gibt den letzten HPF-Typ). Das
  Plugin lässt die Taste allein heute bei der Firmware.
- Ein Patch in der Firmware (Plan unten) bleibt der Weg ohne die Grenzen oben.

## Plan für einen Firmware-Patch (grob, hergeleitet)

1. Tastenauswahl aus Idee 55 lesen (`tools/patch/`), die Stelle finden, an der der Typ gesetzt wird.
2. Je Taste ein Byte "letzter Typ", beim Tastendruck befüllt.
3. SHIFT + Taste: Filter aus, beim zweiten Druck den gemerkten Typ setzen.
4. Menüpunkt im BLECH-Menü (aus, an), Standard aus. Rot und blau prüfen.
