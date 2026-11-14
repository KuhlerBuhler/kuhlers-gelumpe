# DEV MODE: was im Firmware-Abbild gesperrt bleibt

Stand 14. November 2026. Hacktribe 2.02 und Korg rot 2.02 im Emulator, blau (Synth) nur als Gegenprobe.
**Am Gerät nicht gemessen.**

DEV MODE ist ein Schalter im BLECH-Menü (Seite `DEV MODE`, nur auf dem Sampler). Ist er an, darf BLECH WRITE das
Firmware-Abbild im RAM (`0xC0000000..0xC0200000`) beschreiben, damit ein Host-Tool geänderte Bereiche eines Patches ohne
SOFTWARE UPDATE einspielen kann. Gesperrt bleiben die Bereiche, die der SysEx-Weg selbst und das Flashen brauchen: wer die
überschreibt, verliert die Verbindung oder bricht ein Update ab.

## Schalter

| Befund | Marker |
|---|---|
| Der Schalter ist das Wort `DEV_FLAG = 0xC01910FC` (`STATE + 0xFC`). An heißt `0x4D564544` ("DEVM"), alles andere aus | gebaut, `tools/patch/blech_sysex.py` |
| Das Abbild hat dort `FF`, kein Patch schreibt das Wort; nach jedem Einschalten ist DEV MODE also aus (gewollt: startet immer aus) | gemessen (`test/dev-mode.test.mjs`, alle drei Patch-Dateien) |
| Die Menüseite schreibt nur dieses Wort (Rad hoch = an, runter = aus), WRITE speichert nichts | gebaut, `tools/patch/script_menu.s` |
| INFO meldet Flag `0x200` (DEV MODE eingebaut) immer auf dem Sampler und `0x400`, solange er an ist; der Synth meldet keins von beiden | gemessen (Emulator, `sysex:dev_*`, `synth_no_dev_mode`) |

## Regel in der Firmware

Die Schutztabelle (`TABLE_AT 0xC0173800`) bekommt Bit 9 (`DEV_OPEN 0x200`) in den Flags einer Region. Nur `firmware-image`
trägt es. `policy_hit` übergeht eine solche Region beim Schreiben, wenn `DEV_FLAG` die Magic hat. Danach folgen in der
Tabelle die gesperrten Bereiche mit Flags 0; die greifen immer. Der Spiegel `0xC4000000..` bleibt gesperrt, Lesen ist
unverändert.

Kopiert WRITE DATA in das Abbild, laufen IRQ und FIQ während der Kopie maskiert, danach Write-Buffer leeren und I-Cache
verwerfen (die MMU ist aus, Daten sind nicht gecacht, `docs/hintergrund/skript-laufzeit.md`). Ziele außerhalb des Abbilds
kopieren wie bisher.

## Gesperrte Bereiche

Quelle sind die Konstanten des SysEx-Patches und drei Spuren aus dem Emulator, erzeugt mit
`tools/emu/sysex_trace.py` (Grundblöcke, die ausgeführt werden):

| Spur | Datei | Ergebnis |
|---|---|---|
| SysEx-Weg: zwei Sitzungen INFO, READ, WRITE, FLASH READ, ohne Leerlauf | `data/traces/sysex-path-ht.json`, `-red.json` | 54 (ht) / 56 (rot) Bereiche |
| Flash-Weg: SOFTWARE UPDATE von der Karte bis zum Ende (512 Löschungen, 8192 Programmierungen) | `data/traces/flash-path-ht.json`, `-red.json` | 278 / 294 Bereiche |
| Schreibzugriffe ins Abbild nach dem Start (nur Info, nicht gesperrt) | `data/traces/image-writes-ht.json`, `-red.json` | 29 Bereiche, 2956 Byte |

| Befund | Marker |
|---|---|
| Konstanten: SysEx-Code `0xC0172100..0xC0173000`, Sample-Code, Tabelle, `STATE..BUF_END` (`0xC0191000..0xC019A400`, mit `DEV_FLAG`), Dateibereich `0xC019F000..`, die zwei Hook-Wörter | gebaut |
| Die Spuren werden mit wachsendem Abstand (ab `0x40`, verdoppelt) zusammengefasst, bis alles in 100 Tabellenplätze passt; erreicht bei `0x400` | gemessen (`sysex_trace.py closed`) |
| Danach sind es je 95 Bereiche, ht 160780 Byte, rot 165052 Byte; liegt eine Konstante in einem Spurbereich, werden beide ein Eintrag | gemessen |
| Keiner der gesperrten Bereiche überdeckt ein Schreibziel, das der Editor erklärt (`src/plan.mjs allowedRegions`); die werden vorher herausgeschnitten | gemessen (`test/dev-mode.test.mjs`) |
| USB-MIDI wird nicht emuliert; der USB-Treiber steckt nicht in der Spur. Der Teil des SysEx-Wegs, der über BLECH läuft, ist über die Konstanten und die Spur gesperrt, Korgs USB-Code selbst nicht | offen, hergeleitet |
| `data/dev-closed.mjs` ist generiert; `sysex_trace.py closed --check` prüft, dass die Datei zu Konstanten und Spuren passt | gemessen (Test) |

Die Liste geht als `devClosed` in `data/protected.mjs`, der Editor nutzt dieselbe Regel (`src/protect.mjs refusal(…, {devMode})`),
und die Vektoren in `test/support/sysex-vectors.mjs` prüfen sie im Emulator gegen die Firmware (`sysex_cases.py --only 11`).

## Host-Tool `tools/device/hot_patch.py`

Vergleicht das laufende Abbild (Basis) mit einem neuen und schreibt nur, was ohne SOFTWARE UPDATE geht.

| Befund | Marker |
|---|---|
| Das neue Abbild braucht einen Prüfbericht (`tools/emu/check.py --report`) mit passendem sha256, sonst läuft der volle Check; `--allow-quick` nur mit Hinweis in der Ausgabe | gebaut, `test_hot_patch.py` |
| Basis: SYSTEM.VSB von der Karte (FILE READ), `--base` oder `--chain <Journal>`; vor dem Schreiben per READ gegen das laufende Abbild geprüft (`--proof full` ganzes Abbild, `near` 4-KiB-Blöcke um die Änderungen) | gebaut |
| Nach dem Start schreibt die Firmware rund 186 KB im Abbild selbst (ht und rot, Emulator 5 s), darunter etwa 450 Byte `.data` bei `0xC00F8EA0..0xC00F94F1`, `0xC00F9D8C`, `0xC0162894`, `0xC0163134`, die nicht in der Spur nach dem Start stehen. Das Tool bootet Basis und neues Abbild im Emulator und zählt diese Bytes zu den Daten | gemessen |
| Einteilung je Bereich: gesperrt, DSP-Programm, Startphase (`bootmap.py`), Daten (RAM-Bereiche der Patches, Schreibspur, Startwerte) und abweichende Live-Bytes = volles Update; schon geschrieben = übersprungen; sonst hot | gebaut, `test_hot_patch.py` |
| Gruppen: zeigt ein neues Wort (B/BL oder Zeiger) in einen anderen geänderten Bereich, sind beide eine Gruppe; Reihenfolge Code über FF zuerst, einzelne Wörter zuletzt; über einem Block (1 KiB) Warnung "nicht atomar" | gebaut |
| Läuft der Sequencer (`0xC06BC318` != 0), schreibt das Tool nicht | gebaut |
| Journal `out/hot-patch/hot-patch-<sha8>.json` mit Basis-Bytes; `--revert` schreibt sie zurück, letzte Gruppe zuerst | gebaut, Emulator `sysex_cases.py hotpatch` |
| Kein Kartenschreiben, kein EXEC, keine Tasten; `--dry-run` liest nur | gebaut |

Tasten, Regler, Pads und Touch über USB mit DEV MODE (`tools/device/remote_press.py`, ohne EXEC): `2026-11-14-dev-mode-eingabe.md`.

## Offen

- Gerätetest (Plan Phase 4, Schritte in `2026-11-14-dev-mode-geraet.md`): Schalter, Schreiben ins Abbild, gesperrte Bereiche, Ausschalten.
- USB-Treiber von Korg in die Sperrliste, falls ein Gerätetest zeigt, dass ein Hot-Patch dort die Verbindung trennt.
