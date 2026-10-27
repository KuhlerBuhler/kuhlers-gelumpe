# 74. Plugin-API für 1.4: Feedback aus der Community

Feedback (27.10.), gesammelt für 1.4 (neben Sample Swap). Stand 2026-10-27: **aufgeschrieben, nichts gebaut.**
Heute ist die Plugin-API bei Version 9 (`data/script/contract.mjs`).

## Wünsche und heutiger Stand

| Wunsch | Heute | Notiz |
|---|---|---|
| Parameter lesen und schreiben: `korg.param(part, id, wert)`, `korg.read.param(part, id)` | einzelne Werte gibt es (`korg.read.part()`, `korg.knobs`, Pattern-Werte wie `level`, `mfxType`), eine allgemeine Parameter-Funktion nicht | Part-Werte liegen ab `0xC06B2F9C + 0x330*part` (rot), die Gerätekarte (`data/map/`) kennt viele Felder; Schreiben braucht eine Liste erlaubter Felder mit Bereichen, rot und blau |
| Ereignis verschlucken: Handler gibt einen Wert zurück, die Firmware verarbeitet das Ereignis dann nicht, für Tasten, Touchpad, Pads, Regler und Drehgeber, auch bei geschlossener App | nur bei offener App gehören ihr die Tasten (außer PLAY, STOP, REC); Regler, Drehgeber, Pads und Touchpad gehen immer an die Firmware; `korg.remapKey` legt Tasten um | Der Eingangsfilter hat eine Maske je Ereignistyp (`SCRIPT_CONTROL_CAPTURE_MASK`), ohne API. Haken: der Handler läuft erst im nächsten 40-ms-Bild, die Firmware hat das Ereignis dann schon. Ein Rückgabewert geht deshalb nur, wenn der Filter das Ereignis zurückhält, bis der Handler entschieden hat, oder wenn das Plugin vorher sagt, was es haben will (Maske je Bedienelement, siehe Idee 70/72) |
| Mehr Speicher pro Plugin, oder `korg.file.read` / `korg.file.write` mit 1 bis 4 KB | `korg.store`: 16 Plätze zu 32 Bit, auf die Karte mit `korg.store.save()`; lesen von der Karte nur `korg.file.frame` (GIF) | Datei je Plugin unter `KORG/blechtribe/`, Schreiben nur, wenn die Firmware die Karte nicht braucht (wie heute beim Speichern) |
| Doku: Tabelle Index zu Bedienelement für Regler und Drehgeber | fehlt in `docs/plugins.md` (nur `korg.knobs.LEVEL` als Beispiel) | Regler: LEVEL 0, PAN 1, PITCH 2, RESONANCE 3, EG INT 4, MOD DEPTH 5, ATTACK 6, IFX EDIT 7, DECAY 8, OSC EDIT 9, MOD SPEED 10. Drehgeber: 0 Hauptrad, 1 SAMPLE/OSC, 2 CUTOFF, 3 MOD TYPE, 4 IFX TYPE (`data/panel.mjs`). Klein, kann schon in 1.3.6 |
| Doku: vollständige Liste der `korg.key`-Namen | steht in `docs/plugins.md` ("Namen für Tasten und LEDs"), aus `data/panel.mjs` erzeugt | prüfen, ob sie vollständig und gut auffindbar ist |

## Offen

- Welche Parameter `korg.param` zuerst können soll.
- Verschlucken per Rückgabewert oder per vorher gesetzter Maske (oder beides).
- Größe und Ort der Plugin-Datei, und ob sie zwischen Plugins geteilt wird.
