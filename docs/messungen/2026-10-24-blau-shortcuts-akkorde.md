# EXIT-Shortcuts und Akkorde in Pink auf der blauen Electribe (24.10.)

Beide gab es bisher nur auf der roten, weil die Stellen in der Firmware der blauen nicht gemessen waren. Gemessen im Emulator mit
Korgs Synth-Firmware 2.02 und dem BLECH-Satz für Blau. **Am Gerät nicht geprüft.**

## Die Stellen

- Die meisten Stellen hatten schon Einträge in `data/synth-map/`: LED-Manager, Player, Pattern im RAM, Pattern-Bank,
  LED-Sender, Sequencer-Modell.
- Neu ist das Pattern-Laden der Firmware für EXIT + Pad: rot `0xC004AB84`, blau `0xC0044C64`, dieselbe Funktion, 16 Wörter
  gleich (`tools/patch/fwmap.py` gegen Hacktribe 2.02), eingetragen in `data/synth-map/shortcuts.json`.
- Ein Part liegt auf der blauen wie auf der roten: ab Byte `0x800` der Datei, alle `0x330` Byte, die Steps ab `0x30`, 12 Byte
  je Step.
- **Voice Assign ist auch auf der blauen Byte 2 des Parts.** Gemessen auf der Seite VOICE ASSIGN im MENU (Edit ► bis Seite 18):
  Byte 2 des ersten Parts im RAM einmal auf 0 und einmal auf 2 gesetzt, die Seite neu gezeichnet: nur diese Seite ändert sich,
  mit 2 zeigt sie "Poly1".

## Ergebnis (Emulator, blau)

| Fall (`tools/emu/shortcut_cases.py`) | Ergebnis |
|---|---|
| EXIT + WRITE speichert an den eigenen Platz, andere Plätze bleiben | ja |
| WRITE allein öffnet das Write-Fenster wie immer | ja |
| EXIT + Pad setzt den Klang des Parts zurück, Steps und andere Parts bleiben (TRIGGER, SEQUENCER, beim Abspielen) | ja |
| WRITE-LED atmet bei ungespeichertem Pattern, dunkel nach dem Speichern | ja |
| EXIT beim Einschalten: alles wie bei Korg | ja |

| Fall (`tools/emu/menu_cases.py`, `chord_cases`, `tie_cases`) | Ergebnis |
|---|---|
| Poly 1: Steps mit 2 Noten pink, mit einer Note rot | ja |
| Mono 1 und EXIT beim Einschalten: alle rot | ja |
| gebundene Noten: Nachklang wird dunkler, folgt einer Änderung, überlappende addieren sich | ja |

Der Fall mit voller UART-Warteschlange (`tie_unseen_edit_during_full_queue`) läuft nur auf der roten, er steuert deren
Warteschlange direkt. Der Code der Farben, den er prüft, ist auf beiden derselbe.

Knopf 1 auf 200 ändert im Init-Pattern der blauen nichts, dort steht der Wert schon. Die Fälle drehen ihn deshalb, bis sich das
Pattern ändert.
