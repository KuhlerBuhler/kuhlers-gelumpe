# Ordner KORG/blechtribe beim ersten Start, Frage der blauen nach der Pattern-Sicherung (9.11.)

Stand 2026-11-09. Alles im Emulator mit Korgs blauer 2.02 (`41fc5f1c`), Korgs roter (`1d0f0689`) und Hacktribe
(`7cb4825c`), die Dateien außerhalb des Repositorys. **Am Gerät nichts.** Vorgeschichte: [rote Fassung](2026-10-19-ordner-uebernehmen.md),
[blaue Fassung](2026-10-29-blau-ordner-uebernehmen.md).

Marker: **gemessen** (ausgeführt), **hergeleitet** (aus Code geschlossen).

## Belegtabelle

| Behauptung | Marker | Beleg |
|---|---|---|
| Korgs blaue schreibt EXPORT ALL PATTERN als `KORG/electribe/electribe_allpattern.e2allpat` (4161792 Byte), direkt in den Ordner, nicht nach `PatternSet` | gemessen | unveränderte blaue 2.02 im Emulator, DATA UTILITY Seite 2, MENU, MENU, "OK"; danach `fat32.Volume.walk()` der Karte: nur `KORG`, `KORG/electribe` und diese Datei |
| Vorher (Stand develop): die blaue fragt, wenn `SD:KORG/blechtribe` fehlt und `SD:KORG/electribe` da ist, egal was darin liegt | hergeleitet | `mg_blue` in `tools/patch/script_migrate.s` vor dieser Änderung (`mg_dir_exists` beider Ordner); Fall `blue_update_file_only_asks_and_copies` fragte mit nur `System/SYSTEM.VSB` |
| Vorher: rot und Hacktribe fragen, wenn `KORG/blechtribe/Sample/e2sSample.all` fehlt und eine `e2sSample.all` in `KORG/hacktribe` oder `KORG/electribe sampler` liegt | hergeleitet | `migrate_start`, unverändert; Fälle `menu_copies_the_folder`, `old_folder_without_samples_no_question` |
| BLECH liest und schreibt in `KORG/blechtribe` die Ordner `Plugin` (Plugins, `store.*.bin`), `Presets` (`e2sFx.all`, nur rot), `Gif` (`GIFnn.E2G`), `Doom` (`doom.bin`, nur rot), `Sample` (`e2sSample.all`, nur rot) und `System` (`SYSTEM.VSB` für das Update) | hergeleitet | Pfade in `script_card.s`, `script_menu.s`, `script_store.s`, `fx_card.s`, `script_file.s`, `doom_loader.py`, `blech_sysex.py`; `fx_card.s` und die Doom-Patches kommen nur in die roten Sätze (`script_hooks.py`, `data/patches/doom-loader.json`) |

## Der Patch

- `mg_folders` läuft in `migrate_start` nach den Prüfungen von Panel und EXIT, vor der Frage. Lässt sich `SD:KORG/blechtribe`
  nicht öffnen, macht es `f_mkdir` für `SD:KORG`, `SD:KORG/blechtribe` und jeden Ordner der Liste des Builds. Ist der Ordner
  da, bleibt er, wie er ist, auch wenn Unterordner fehlen. Mit EXIT beim Einschalten legt der Start nichts an.
- Warum nur dann: jedes `f_mkdir` eines vorhandenen Ordners kostet im Emulator etwa 4 ms. Bei jedem Start alle acht
  geprüft, kam der Sample-Lader der roten 34 ms später (384 statt 350 ms, Fall `menu:early_look_loader_starts_at_the_same_time`,
  Grenze 15 ms), beim ersten Anlegen 79 ms (CI). Mit nur dem `f_opendir`: 363 statt 351 ms (Hacktribe), 358 statt 346 ms (rot).
- Rot und Hacktribe: `Plugin`, `Presets`, `Gif`, `Doom`, `Sample`, `System`. Blau: `Plugin`, `Gif`, `System`. Die Ordner der
  Firmware selbst (`PatternSet`, `Audio`, ` Project`) legt die Firmware beim Export an, BLECH nicht.
- Die blaue fragt jetzt, wenn direkt in `KORG/electribe` eine Datei auf `.e2allpat` endet (Groß und klein egal, Namen mit
  Punkt am Anfang nicht) und in `KORG/blechtribe` keine (`mg_allpat`). Nach einer Sample-Datei sucht sie nicht. Nach dem
  Kopieren liegt die Sicherung in `KORG/blechtribe`, die Frage kommt nicht mehr; nach EXIT kommt sie beim nächsten Start
  wieder, wie auf der roten.
- Rot und Hacktribe behalten die Sample-Regel. Hacktribe auf einer blauen ist die Firmware des Samplers und läuft mit
  derselben Regel.

## Emulator (`tools/emu/migrate_cases.py`)

| Firmware | Ergebnis |
|---|---|
| Korg rot + `blech.json` | 14 von 14, darunter leere Karte: alle sechs Ordner; `KORG/blechtribe` mit nur `Plugin`: bleibt so, eigene Datei bleibt; EXIT beim Einschalten: kein Ordner; `KORG/hacktribe` mit `.e2sallpat` und `.e2allpat`, ohne `e2sSample.all`: keine Frage |
| Hacktribe + `blech.json` | 14 von 14, dieselben Fälle |
| Korg blau + `blech-synth.json` | 15 von 15, darunter leere Karte: `Plugin`, `Gif`, `System`; nur die Sicherung in `KORG/electribe`: Frage, MENU kopiert sie; Update-Datei, Audio, eine Punktdatei `._x.e2allpat` und eine `Sample/e2sSample.all` ohne Sicherung: keine Frage; `KORG/blechtribe` mit Plugin, ohne Sicherung: Frage; mit Sicherung: keine Frage |

`check.py --quick` mit den drei Sätzen: je 22 von 22. `menu_cases.early_look_cases` rot und Hacktribe: alle grün.

## Offen, für den Gerätetest

- Auf der blauen läuft `f_mkdir` im Starthaken vor dem Scheduler. Lesen geht dort (gemessen am 29.10.), Schreiben im
  Emulator auch; ob der Kartentreiber am Gerät dort schreibt, ist nicht gemessen.
- Ob die Frage am Gerät nur mit einer `.e2allpat` in `KORG/electribe` kommt.
- Zum Testen der Ordner braucht die Karte kein `KORG/blechtribe` (umbenennen), sonst legt der Start nichts an.
