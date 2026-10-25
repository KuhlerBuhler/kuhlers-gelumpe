# Sync Group behält unveränderte Samples, Pad X und Y sind keine Änderung, Pad-Druck beim Wechsel (25.10.)

Wünsche vom Gerät, im Emulator gebaut und geprüft (Hacktribe mit eigenem Flash vom 09.10., blau ohne Flash). Am Gerät noch nicht
geprüft.

## Sample nur, wenn es live geändert wurde

Am Gerät: zwei Patterns einer Gruppe sollen nacheinander zwei Vocals spielen, Pattern A auf Part 1, Pattern B mit einem anderen
Sample auf Part 1. Seit dem 22.10. ([Sync Group mit ganzem Stand](2026-10-22-sync-und-menues.md)) geht der Klang der Parts immer
mit, also auch die Sample-Nummer: B spielte das Vocal von A.

Jetzt geht die Sample-Nummer eines Parts (Part-Byte 8, u16) nur mit, wenn sie im Pattern im RAM von dem Bank-Platz abweicht, aus
dem das Pattern geladen wurde (`S_LOADED`), also live geändert wurde. Sonst behält das neue Pattern sein eigenes Sample. Ist kein
Bank-Platz bekannt, geht sie mit wie bisher. Alle anderen Werte gehen weiter immer mit (`sg_sample` in
`tools/patch/pattern_switch.py`).

`pswitch_cases.py`, `case_sync_group`:

- `group_keeps_an_unchanged_sample`: Part 1 hat nach dem Wechsel `0x0200`, das eigene Sample von Pattern B. Mit dem Patch von
  develop rot (`0x0105`, das Sample von A), jetzt grün, Hacktribe und blau.
- `group_carries_the_state`: ein live auf `0x0106` geändertes Sample kommt weiter an.
- `group_carries_back`: zurück auf A hat Part 1 wieder `0x0105`.

## Pad X und Y zählen nicht als ungespeicherte Änderung

Ein Druck aufs MFX-Pad schreibt dessen X und Y (Byte `0x3E` und `0x3F`, [Pattern-Block](2026-09-16-pattern-diff.md)). Damit galt
das Pattern als ungespeichert: gestoppt blätterte das Rad nur noch (VIEW:), statt zu laden. Beide Vergleiche lassen jetzt im Wort
bei `0x3C` alles außer dem MFX-Typ (`0x3D`) aus: `pc_dirty` des Patternwechsels und `sc_unsaved` der WRITE-LED
(`tools/patch/script_shortcuts.s`).

- `pswitch:pad_xy_is_not_an_edit`: X und Y im RAM geändert, ein Klick lädt das nächste Pattern. Mit develop rot (VIEW:), jetzt grün,
  Hacktribe und blau.
- `shortcut:pad_xy_is_not_an_edit`: dieselbe Änderung, die WRITE-LED bleibt dunkel (Hacktribe).
- Nachgestellt durch Schreiben ins RAM, nicht durch einen Druck aufs Pad im Emulator.

## Pad-Druck beim Patternwechsel

Am Gerät: wer genau auf dem Wechsel ein Pad drückt (etwa in PART MUTE die Kick), dem geht der Druck manchmal verloren.

**gemessen** (Emulator, Hacktribe, Flash vom 09.10.): Pad 1 in PART MUTE in 1-ms-Schritten um den Wechsel einer Sync Group gedrückt.
Drücke von 1 ms vor bis 4 ms nach dem Wechsel kamen nicht an, mit dem Patch und mit EXIT beim Einschalten (Firmware allein) gleich.

**offline und gemessen**, warum: der Pad-Handler `0xC0044874` (Pad, gedrückt, Velocity, Quelle) fragt `0xC002D634`, ob der
Befehlsausführer gerade arbeitet (Byte `+0x10` des Objekts hinter `0xC034057C`). Ist er beschäftigt und das Pad gedrückt, verwirft
der Handler es (`bne 0xC004499C`); Loslassen geht durch. Der Ausführer `0xC002D684` setzt das Byte vor jedem Befehl und löscht es
bei `0xC002D81C`. Beim Laden des Patterns stand es im Emulator von 0,8 ms vor bis 3,6 ms nach dem Wechsel. Die Bytes vom Panel kamen
dabei an, nur das Pad-Ereignis (Typ 4) erreichte die Oberfläche nie.

Der Patch (`pad_gate`, `pad_replay` in `tools/patch/pattern_switch.py`): statt zu verwerfen merkt er sich den Druck (bis zu vier,
mit allem, was danach kommt, auch dem Loslassen) und gibt ihn dem Handler, sobald der Ausführer das Byte gelöscht hat, in derselben
Reihenfolge. Blau: dieselben Stellen bei `0xC003EB60` (Handler) und `0xC002A980` (Löschen), je einmal gefunden
(`data/synth-map/pattern-switch.json`).

- Probe nach dem Fix: alle Drücke von 4 ms vor bis 8 ms nach dem Wechsel kommen an.
- `pswitch:pad_during_the_load_is_kept`: ein Tipp (Drücken und Loslassen), gesendet, als der Ausführer beschäftigt wurde. Mit dem
  Patch von develop rot (der Handler sah nur das Loslassen, Part 1 blieb), jetzt grün (Drücken, dann Loslassen; Part 1 umgeschaltet),
  Hacktribe und blau.
- Nicht am Gerät geprüft. Wie lang das Byte dort steht, ist offen.
