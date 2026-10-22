# Tasten vom Rechner (KORG.press und KORG.turn)

Stand 22. Oktober 2026. Gemessen im Emulator (`tools/emu/remote_cases.py`, `tools/device/remote_press.py --emu`) mit der
eigenen Hacktribe-2.02-Datei und Korgs Original 2.02 (rot), jeweils mit dem BLECH-Satz. **Am Gerät nicht geprüft.**

## Was gebaut ist

- `tools/patch/script_remote.s`: der Frame-Haken der Plugin-Laufzeit (UiTask, 25 Mal je Sekunde) schaut nach den
  EXIT-Kurzbefehlen in ein Befehlswort bei `0xC01F7FC0`, eine freie Lücke im Arbeitsbereich des Kartenladers zwischen der
  Beschreibung der Importliste (endet `+0xF00`) und dem Zustand von `fx_card.s` (`+0xFE0`). Eine Taste geht durch den
  Tasten-Handler der Firmware (`0xC0042BB8(taste, 1)`, im nächsten Frame `(taste, 0)`), das Rad durch den Drehgeber-Handler
  (`0xC00419B4(index, delta)`), dieselben Wege, die das Panel nimmt (docs/hintergrund/skript-laufzeit.md) und die
  `korg.play` schon aus der UiTask nimmt. Nach jedem Befehl zählt `+8` eins hoch.
- Nur ein Wort mit `0xA5` im obersten Byte gilt: der Bereich ist nach dem Einschalten FF.
- `src/remote.mjs`: der Stub für `KORG.exec` (76 Byte im Stub-Puffer, CommandTask). Er schreibt das Wort und schläft dann
  zehnmal 10 ms, bis der Zähler sich bewegt hat, höchstens 500 ms. So überschreibt ein zweiter Druck nie einen ersten, und
  nach `exec` ist die Taste schon verarbeitet. Die Konsole findet das Befehlswort über eine Kennung im Code der VSB
  (`REMT`, dann die Adresse).
- Ohne BLECH-Satz drückt `KORG.press` wie bisher die Taste des Emulators, und so ein Skript bleibt nicht sendbar.

## Ergebnis (gemessen im Emulator)

| Fall | Hacktribe | Korg rot |
|---|---|---|
| MENU, Edit ►, Rad +1, +1, -1, EXIT über das Befehlswort: Bildschirm, Seitenzähler und Display Byte für Byte wie mit dem Panel | ja | ja |
| Jeder Befehl genau einmal gezählt, das Wort danach 0 | ja | ja |
| Wort ohne Kennung und FFFFFFFF: nichts passiert | ja | ja |
| Der ganze Weg über SysEx (`0x53` Stub schreiben, `0x57` ausführen, `0x52` lesen): Menü, Seite SWING, Rad, EXIT, Menü wieder auf SWING | ja | nicht gelaufen |

Der letzte Fall lief mit `tools/device/remote_press.py --emu` gegen die Hacktribe-Kopie; Korgs Original hat das
Execute-Kommando `0x57` von Hacktribe nicht.

## Offen am Gerät

- Ob der Stub am Gerät in 500 ms fertig wird: im Emulator nach einem bis zwei Frames.
- Ob der Drehgeber-Handler aus der UiTask am Gerät so wirkt wie im Emulator (gemessen ist am Gerät nur die Taste,
  über `korg.play`).

```bash
python3 tools/device/remote_press.py --dry-run menu
python3 tools/device/remote_press.py menu edit_next +1 exit --screen
```
