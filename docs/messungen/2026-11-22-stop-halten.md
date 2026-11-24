# STOP halten: jeden Klang sofort beenden (22.11.)

Wunsch aus dem Discord: STOP länger halten soll alles beenden, was noch klingt, damit man nicht den AMP EG oder den Level
herunterdrehen muss. Nach dem STOP der Firmware klingen Noten mit langem Release, gehaltene Pads und die Insert-Effekte weiter.

Markierungen: **gemessen** (Emulator mit DSP-Modell, `tools/emu/shortcut_cases.py`, Gruppe `case_stop_hold`),
**hergeleitet** (Disassembly), **offen** (noch nicht am Gerät geprüft).

## Was die Firmware schon kann (Hacktribe 2.02, rot; blau über `data/synth-map/`)

- `0xC009B5D8(0)` springt nach `0xC0098CA8(0)` und schaltet alles still (hergeleitet):
  - für jeden Part 0 bis 15 `0xC0090E28`: Level auf 0 (`+0xb8`) und DSP-Befehl 0x16, Fall 5, Level 0;
  - danach `0xC0091F5C`, das alle Stimmen zurücksetzt;
  - danach `0xC009B0E0(0xffff)`, das je Part `0xC0098AD0` ruft. Das schaltet den Part am DSP aus (`0xC0093A20`), die
    Audio-Schleife löscht dann seinen Ausgang und den Zustand seines Insert-Effekts.
- Dieselbe Funktion mit 0 rufen das Laden eines Patterns (`0xC0079BE0`), der SysEx-Empfang (`0xC0026484`, `0xC0026504`) und
  weitere Stellen (`0xC0031308`, `0xC00381E0`, `0xC00382AC`, `0xC0079648`, `0xC009A84C`) vor dem Klangwechsel (hergeleitet).
  Am Gerät ist der Schnitt beim Patternwechsel hörbar ([Sync-Gruppen](2026-10-25-sync-group-stimmen.md)).
- Die nächste Note schaltet ihren Part wieder an (`0xC0093988`) und schickt den Level neu (gemessen).
- Der Master-Effekt gehört keinem Part, sein Nachhall bleibt (hergeleitet).
- STOP ist die Taste 0x01. Der Sequencer steht schon beim Drücken, nicht erst beim Loslassen (gemessen). SHIFT + STOP tut nichts
  ([Tastenkombinationen](../tastenkombinationen.md)).

## Der Patch (`tools/patch/script_shortcuts.s`, Laufzeit des BLECH-Menüs)

- Der Eingangsfilter merkt sich, ob STOP unten ist (`SH_STATE`, das freie letzte Wort des `KEY_HOLD`-Satzes). Die Nachrichten
  der Taste gehen unverändert an die Firmware, ein kurzer Druck bleibt also das STOP der Firmware.
- Der Takt (UiTask, 25 pro Sekunde) zählt mit. Nach 12 Takten, also einer halben Sekunde, ruft er `0xC009B5D8(0)`, wenn der
  Sequencer steht (`HW_TRANSPORT` 0), sonst gibt er bis zum Loslassen auf. Einmal je Druck.
- Aus der UiTask rufen schon EXIT + Pad und die KEY PADS Funktionen der Firmware, die an den DSP senden. Dass der Aufruf dort
  gleichzeitig mit der Audio-Schleife sicher ist, ist hergeleitet, nicht am Gerät gemessen.
- Wie die anderen EXIT-Shortcuts: nicht mit EXIT beim Einschalten, nicht bei offenem BLECH-Menü. Kein eigener Schalter im Menü.

## Ergebnis im Emulator (gemessen, HT, rot und blau)

| Fall | Ergebnis |
|---|---|
| STOP 150 ms und 300 ms beim Abspielen | kein Aufruf, kein Part aus, gestoppt beim Drücken wie ohne Patch |
| STOP halten beim Abspielen | ein Aufruf mit 0, Part 0 am DSP aus, keine Stimme; Pad 1 danach: Part an, Stimme, Level über 0 |
| STOP halten mit gehaltenem Pad im Stand | Part aus, keine Stimme |
| STOP halten mit EXIT beim Einschalten | kein Aufruf |

## Offen

- Am Gerät hören, dass Release, gehaltene Pads und Insert-Delay wirklich abbrechen und ohne Knacken enden.
- Dass die nächste Note mit dem richtigen Level klingt, auch nach einem Patternwechsel.
