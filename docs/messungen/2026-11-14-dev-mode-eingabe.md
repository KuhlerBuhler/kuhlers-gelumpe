# DEV MODE: Eingaben über USB ohne EXEC

Stand 14. November 2026. Hacktribe 2.02 und Korg rot 2.02 im Emulator, blau (Synth) nur als Gegenprobe.
**Am Gerät nicht gemessen.**

Mit DEV MODE an bedient ein Rechner die Electribe über USB wie ein Mensch: Tasten, Hauptrad, Encoder, Regler, Pads,
Touchpad, Testmodus, und liest das Display. Dafür läuft kein Code vom Rechner, es gibt kein EXEC. `remote_press.py`
schreibt per BLECH WRITE nur Daten in das Postfach der Laufzeit, der Frame-Hook der Firmware holt sie dort ab.

## Postfach

| Befund | Marker |
|---|---|
| Das Postfach liegt im Kartenbereich der Laufzeit: `CARD = 0xC01F7000` (`tools/patch/script_hooks.py`), Nachricht `+0xFA0` (8 Byte wie vom Panel), Befehlswort `+0xFC0`, gehaltene Taste `+0xFC4`, Zähler fertiger Befehle `+0xFC8` (`tools/patch/script_remote.s`) | gebaut |
| Ganzer Bereich `0xC01F7FA0..0xC01F7FCC`, steht als `remoteMailbox` in `data/protected.mjs` | gebaut, `test/dev-mode.test.mjs` prüft gegen `CARD` und die `.equ` |
| Der Bereich liegt im Firmware-Abbild `0xC0000000..0xC0200000` und in keinem der gesperrten Bereiche (`data/dev-closed.mjs`). WRITE geht also nur mit DEV MODE an, ohne ihn ist er als `firmware-image` gesperrt, auf dem Synth immer | gemessen (Emulator, `sysex:dev_input_*`), `test/dev-mode.test.mjs` |
| Deshalb braucht es keine Firmware-Änderung: der Schalter von DEV MODE ist auch der Schalter für die Eingabe | hergeleitet aus den zwei Zeilen darüber |
| Der Frame-Hook prüft das Befehlswort jeden Frame (Marke `0xA5` im oberen Byte; Arten Taste 1, Encoder 2, Nachricht 3, Test 4, Loslassen 5), führt es aus, setzt es auf 0 und zählt den Zähler hoch | gebaut seit 1.3.8, unverändert |

## Ablauf in `remote_press.py`

| Befund | Marker |
|---|---|
| Der Weg über das Postfach gilt, wenn INFO Flag `0x400` (DEV MODE an) und `WRITE` meldet und die Laufzeit mit Signatur `REMT`/`RMT2` gefunden ist; `--exec` erzwingt den alten EXEC-Weg | gebaut, `test/remote.test.mjs` |
| Je Schritt: Zähler lesen, bei Pad, Regler und Touch erst die 8 Byte Nachricht schreiben, dann das Befehlswort, dann den Zähler lesen bis er um 1 steigt (höchstens 1 s) | gebaut |
| WRITE DATA kopiert ins Abbild mit maskiertem IRQ und FIQ (`2026-11-14-dev-mode-sperrbereiche.md`). Der Frame-Hook sieht Nachricht und Befehlswort also nie halb geschrieben | hergeleitet |
| Der Hook kann das Befehlswort zwischen Kopie und Rücklesen schon abholen und auf 0 setzen. Die Firmware antwortet dann Status 5 (Rücklesen anders). Für das Befehlswort zählt das als angekommen, der Zähler entscheidet | gebaut, Wettlauf hergeleitet |
| Holt niemand das Wort ab (Laufzeit hängt, Hook aus), nimmt das Tool es zurück (schreibt 0), damit es nicht später unerwartet wirkt | gebaut, `test/remote.test.mjs` |
| Kein EXEC, kein Schreiben in den EXEC-Puffer `0xC1000000`, nichts auf der Karte, nichts im Flash | gebaut, `test/remote.test.mjs` zählt die Aufrufe |

## Emulator

| Fall (`tools/emu/sysex_cases.py`, `dev_input_cases`) | Hacktribe | rot |
|---|---|---|
| `dev_input_keys_like_the_panel`: Tasten und Hauptrad über das Postfach landen auf derselben Seite wie dieselben Tasten am Panel | grün | grün |
| `dev_input_messages_reach_the_dispatcher`: Regler, Encoder, Pad, Touch, SHIFT halten und loslassen kommen als Panel-Nachrichten an | grün | grün |
| `dev_input_off_refused`: ohne DEV MODE lehnt die Firmware schon WRITE BEGIN ab, der Zähler bleibt stehen, das Tool wählt den EXEC-Weg | grün | grün |

Die Gruppe `case_dev_mode` (Regel gleich wie im Editor, mit dem Postfach in den Testvektoren) ist danach auf beiden
Builds wieder 7/7 grün. Blau nicht eigens gelaufen: der Synth lehnt das Schreiben ab, `synth_no_dev_mode` deckt das.

## Offen

- Gerätetest: Schritte 10 bis 12 in `2026-11-14-dev-mode-geraet.md`, jeder Schreibschritt braucht eine Freigabe.
- `src/remote.mjs` (`KORG.press` in der Editor-Konsole) nutzt weiter den EXEC-Weg.
