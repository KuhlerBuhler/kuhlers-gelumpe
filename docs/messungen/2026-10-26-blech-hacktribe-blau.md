# BLECH mit Hacktribe auf der blauen Electribe 2, im Emulator

Stand 2026-10-26. Alles hier lief im Emulator mit den eigenen Dateien des Besitzers (Korg rot `1d0f0689`, Hacktribe
`7cb4825c`, Korg blau `41fc5f1c`), außerhalb des Repositorys. **Am Gerät nichts.** Keine Firmware-Bytes im Repository.
Vorgeschichte und offene Risiken: [Idee 65](../ideen/65-blech-hacktribe-blau.md).

Marker: **gemessen** (ausgeführt, Befehl unten), **hergeleitet** (aus Code geschlossen).

## Belegtabelle

| Behauptung | Marker | Beleg |
|---|---|---|
| Hacktribe mit blauem Kopf (`2b2e1c2f…`) und die BLECH-Kopie davon starten auf dem Flash der blauen (Kennung `KORGelec2USR`) bis zum Hauptbild, ohne Assertion | gemessen | `machine.py --hardware blue`, `test/emulator-blue.test.mjs` (mit `E2_VSB`) |
| Die BLECH-Kopie aus Hacktribe mit blauem Kopf unterscheidet sich von der aus Hacktribe mit Sampler-Kopf nur in Byte `0x12` und `0x2E` | gemessen | beide mit `applyPatches` gebaut, `cmp -l` |
| Kurzprüfung (`check.py --quick --hardware blue`): 22 von 22 bestanden, auch `normal_blank` auf leerem blauem Flash | gemessen | Befehl unten |
| Alle acht Update-Wege auf der blauen verhalten sich wie erwartet (Tabelle unten) | gemessen | `hacktribe_blue_probe.py` |
| Läuft Hacktribe auf der blauen, sagt sein Update zu einer Datei mit blauem Kopf "Error / Invalid File" | gemessen | Bild des Probelaufs (außerhalb des Repositorys) |
| BLECHs Theme zeichnet die Seitentitel von DATA UTILITY anders: SOFTWARE UPDATE wird gezählt (Seite 14 von 14), nicht am Titel erkannt | gemessen | Bilder des Probelaufs; `synth_update_probe.py`, `SAMPLER_SOFTWARE_UPDATE_PAGE` |
| Blauer BLECH-Satz, Karte nur mit `KORG/electribe`: vor der Änderung sagt WRITE im BLECH-Menü "folder missing" (FatFs `FR_NO_PATH`), die Einstellung ist nach dem Neustart weg | gemessen | `menu_cases.settings_cases` mit dieser Karte, vor dem Umbau |
| Nach der Änderung legt die Firmware `KORG/blechtribe` an, WRITE sagt "saved", die Einstellung gilt nach dem Neustart; ein Plugin über BLECH SysEx legt `KORG/blechtribe/Plugin` an | gemessen | `menu:settings_without_folder`, `sysex:file_plugin_makes_folders`, auf blau und Hacktribe |
| `f_mkdir` der blauen liegt bei `0xC008B510` | gemessen | 16 Befehle maskiert wie beim Sampler (`0xC009EB00`), genau ein Treffer (`firmware.py` search); `fwmap` findet dieselbe Stelle |
| Die Ordnerfunktionen der blauen (`0xC0032520`, `0xC003256C`) wählen nach Gerätetyp: `0x123` nimmt das dritte Poolwort (`electribe`), `0x124` das erste (`electribe sampler`) | gemessen | Disassembly; dieselben Funktionen wie Hacktribes `0xC00356D4`, `0xC0035720` |

## Update-Wege auf der blauen

Leerer Flash der blauen, je Weg nur die eine Datei auf der Karte, im Ordner, den die laufende Firmware erfragt (vorher mit
leerer Karte gemessen). DATA UTILITY, SOFTWARE UPDATE, MENU, Netzteil dran.

| Läuft | Datei | Ordner | Lösch-/Schreibbefehle | Ergebnis |
|---|---|---|---|---|
| Korgs blaue | BLECH + Hacktribe, blauer Kopf | `KORG/electribe/System/` | 512 / 8192 | geschrieben, Neustart bis Hauptbild, Rest des Flashs gleich |
| Korgs blaue | BLECH + Hacktribe, Sampler-Kopf | `KORG/electribe/System/` | 0 / 0 | abgelehnt |
| Hacktribe | BLECH + Hacktribe, Sampler-Kopf | `KORG/hacktribe/System/` | 512 / 8192 | geschrieben, Neustart bis Hauptbild, Rest gleich |
| Hacktribe | BLECH + Hacktribe, blauer Kopf | `KORG/hacktribe/System/` | 0 / 0 | abgelehnt ("Invalid File") |
| BLECH + Hacktribe | dieselbe, Sampler-Kopf | `KORG/blechtribe/System/` | 512 / 8192 | geschrieben, Neustart bis Hauptbild, Rest gleich |
| BLECH + Hacktribe | dieselbe, blauer Kopf | `KORG/blechtribe/System/` | 0 / 0 | abgelehnt |
| BLECH + Hacktribe | Korgs blaue, Sampler-Kopf | `KORG/blechtribe/System/` | 512 / 8192 | geschrieben, Neustart bis Hauptbild von Korgs blauer, Rest gleich |
| BLECH + Hacktribe | Korgs blaue, unverändert | `KORG/blechtribe/System/` | 0 / 0 | abgelehnt |

Folgen für den Patcher: eine Hacktribe-Datei bekommt den Sampler-Kopf (Hacktribe läuft schon), Korgs rote mit
`hacktribe-2.patch` für die blaue den blauen (Korgs blaue läuft). Der Weg zurück zu Korgs blauer: ihre Datei mit
Sampler-Kopf in `KORG/blechtribe/System/` ([Rettung](../rettung.md)).

## Ein Flash mit den Daten der blauen

Läuft die Kopie auf einem Flash, den Korgs blaue Firmware vorher benutzt hat (Patterns und Einstellungen im Format der
blauen, wie auf einer echten blauen nach dem Wechsel zu Hacktribe), kommt das erste Bild nach dem Hauptbildschirm
40 ms später als in derselben Kopie ohne die Aufrufe des Ladebalkens: ohne Karte sind dort 9 statt 5 Bilder leer
(gemessen, `loadbar_cases.case_off` mit dem `flash-synth.bin` des Dienstes; auf leerem Flash der blauen und auf dem
benutzten Flash der roten kein Unterschied). Der Ladebalken zeichnet dabei nichts: jedes Bild ist eines der Kopie ohne
ihn, das letzte dasselbe. `loadbar:no_card_draws_nothing` prüft genau das, statt Bild für Bild an derselben Stelle.

## Der Kartenordner der blauen

Korgs blaue Firmware liest und schreibt `KORG/electribe/`. Der BLECH-Synth-Satz zieht wie der rote nach `KORG/blechtribe/`
um (`data/patches/blechtribe-synth.json`): `blechtribe` passt nicht in die Fenster von `electribe` (10 und 16 Byte), aber
in die von `electribe sampler` (18 und 24 Byte), die die blaue nie erfragt (Typ `0x124`). Der Patch schreibt dort
`blechtribe` hinein und lässt die zwei Poolwörter von Typ `0x123` (`0xC0032568`, `0xC00325B4`) darauf zeigen. Die
erste Installation geht weiter über `KORG/electribe/System/` (Korgs blaue läuft dann), jedes spätere Update über
`KORG/blechtribe/System/`. Die Seite sagt, `KORG/electribe/` nach `KORG/blechtribe/` zu kopieren; beim ersten Start bietet BLECH die Kopie auch
selbst an ([Messung](2026-10-29-blau-ordner-uebernehmen.md)).

Gemessen mit dem BLECH-Synth-Satz samt Umbenennung (`synth_update_probe.py`, leerer Flash der blauen): Kurzprüfung 21 von 21;
Korgs blaue schreibt ihn aus `KORG/electribe/System/` (512 Lösch-, 8192 Schreibbefehle), Neustart bis Hauptbild; danach
erfragt er `SD:KORG/blechtribe/System/SYSTEM.VSB`; Korgs blaue unverändert von dort zurück, Neustart bis Hauptbild.

Wo die Firmware schreibt und ein Ordner fehlt, legt sie die Ordner des Pfads an und versucht es einmal neu
(`card_create` in `tools/patch/script_card.s`, `make_folders` in `tools/patch/blech_sysex.py`): die Einstellungen, der
Plugin-Export, der Plugin-Speicher und die Dateien über BLECH SysEx. Auf der roten ist der Ordner nach der Umbenennung da,
dort greift das nicht.

## Wie gemessen

```
tools/emu/.venv/bin/python tools/emu/machine.py --vsb HACKTRIBE-BLAU.VSB --hardware blue --seconds 12
tools/emu/.venv/bin/python tools/emu/check.py --base HACKTRIBE-BLAU.VSB --patched BLECH.VSB --hardware blue --quick --allow … --allow-code …
tools/emu/.venv/bin/python tools/emu/hacktribe_blue_probe.py --korg-blue KORG-BLAU.VSB --hacktribe HACKTRIBE-BLAU.VSB --blech BLECH.VSB --shots DIR
npm run verify:patches -- KORG-ROT.VSB KORG-BLAU.VSB HACKTRIBE.VSB HACKTRIBE-BLAU.VSB
```

`HACKTRIBE-BLAU.VSB` ist Hacktribe 2.02 mit Byte `0x12 = 0x00` und `0x2E = 0x23`; die `--allow`-Spannen gibt
`applyPatches` aus (`tools/verify-patches.mjs` macht beides selbst). Die Bilder bleiben außerhalb des Repositorys.
