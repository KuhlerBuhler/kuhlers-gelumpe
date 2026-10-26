# Patcher: Aufbau und Regeln

Deutsche Version | [English version](patcher.en.md)

Stand 2026-10-16. Zu Idee 17 in [`docs/ideen.md`](ideen.md). Der Patcher ist gebaut,
der Abschnitt "Stand" sagt, was genau und was nicht. Belege stehen in
`docs/messungen/`; was nur hergeleitet ist, steht hier als solches da.

## Ziel

Ein Werkzeug, das Änderungen an der eigenen Firmware als Patch auf eine
Kopie der VSB legt, sie im Emulator prüft und als Datei zum Flashen
ausgibt. Verteilt wird nur der Patch, nie Firmware: jeder wendet ihn auf
seine eigene VSB an, wie bei Hacktribe. Eigene Features kommen als Plugins
auf die Karte ([Plugins](plugins.md)). Eigene Patches sollen Nutzer später
selbst bauen können, zum Beispiel eigene Menüpunkte (geplant, siehe "Offen").

## Stand

Gebaut heißt: der Code liegt im Repository und ist im Emulator oder in
Tests geprüft.

Die blaue Electribe 2 mit Synth-Firmware 2.02 hat einen eigenen Satz
`data/patches/blech-synth.json`. Er enthält lesendes BLECH SysEx, Startbild, Theme,
Ausschaltbild, Patternwechsel mit Bestätigung und Sync-Gruppen, TAP Motion, Notenassistent, Würfeln,
MFX 2, Pad-Farben mit Akkorden in Pink, BLECH-Menü und Plugins mit Blechy
und die EXIT-Shortcuts (EXIT + WRITE, EXIT + Pad). Startbild-Editor, Preset-Erweiterung, Ladeanimation
und Doom gehören nicht dazu.
Die Spielhilfen lassen sich im BLECH-Menü einstellen; EXIT beim Einschalten schaltet BLECH ab.
Patternwechsel, TAP Motion, Notenassistent und Würfeln brauchen eine Karte, die seit dem Einschalten einmal da war; wer sie danach zieht, behält die Funktionen ([Messung](messungen/2026-10-18-karte-gezogen-tap-blinkt.md)).
Warum die übrigen Ports abgelehnt wurden und welche Prüfungen bestehen, steht in der
[Synth-Messung](messungen/2026-10-16-blech-synth.md).

| Teil | Beleg |
|---|---|
| Patch-Format 1 mit Feld-, Roh- und Kopier-Änderung, `startPhase`, `hooks` | `src/patch.mjs`, `test/patch.test.mjs` |
| Haken-Register | `src/hooks.mjs`, `data/hooks.mjs`, `test/hook-registry.test.mjs` |
| RAM der Patches (`ram`, `shares`): Überdeckungen im Satz und mit Firmware werden gefunden | `src/ramspans.mjs`, `data/patch-ram.mjs`, `test/patch-ram.test.mjs` |
| Patch-Satz BLECH: Startbild-Editor, MFX 2, Patternwechsel mit Bestätigung, TAP Motion, Notenassistent, Ladebalken, Sample-Fehler, Plugin-Laufzeit mit BLECH-Menü und der eingebauten App Blechy, Kartenordner blechtribe, Blech-Startbild, Theme (Schriften und Symbole), Preset-Tabellen für 128 Plätze, Blechy beim Ausschalten, eigene SysEx-Befehle fürs RAM, auf Korgs Original dazu die Synth-Filter | `data/patches/blech.json`, Code in `tools/patch/`, Anwenden mit `tools/patch/apply.mjs` |
| Theme als Datenpatch: eigene Schriften und Symbole fürs Display, in der Startphase freigegeben | `data/patches/blech-theme.json`, `tools/patch/blech_theme.mjs`, [BLECH Theme](hintergrund/blech-theme.md) |
| Patch-Datei `BLECH.patch` und bsdiff für das Release | `src/patchfile.mjs`, `tools/build-blech-patch.mjs`, `tools/patch/bsdiff.mjs`, `test/patch-file.test.mjs`, `test/bsdiff-build.test.mjs` |
| BLECH direkt auf Korgs Original 2.02: Patches mit `builds`, Ordner-Variante für Korgs Build, Patch-Datei mit zweitem Fingerabdruck | `src/patch.mjs` (`selectFor`), `src/firmware.mjs` (`identifyBase`), `data/patches/blechtribe-stock.json`, `src/patchfile.mjs`, `test/patch.test.mjs`, `test/patch-file.test.mjs`, [Messung](messungen/2026-10-14-stock-blech.md) |
| Seite Patcher mit Prüfung, Download, Wahl "BLECH direkt" oder "mit Hacktribe" und Umwandlung Korg 2.02 zu Hacktribe | `site/app/patcher.mjs`, `src/patcher.mjs`, `src/bsdiff.mjs`, `src/bzip2.mjs`, `test/patcher.test.mjs`, `test/bsdiff.test.mjs`, `test/bzip2.test.mjs` |
| Patternwechsel erst nach Bestätigung (Idee 46): beim Spielen blättert das Rad nur, MENU bestätigt, EXIT nimmt zurück | `data/patches/pattern-switch.json`, `tools/patch/pattern_switch.py`, `tools/emu/pswitch_cases.py`, [Messung](messungen/2026-10-15-patternwechsel.md) |
| TAP Motion (Idee 39): TAP schaltet die aufgenommene Motion Sequence des gewählten Parts sofort an und aus, MASTER FX gehalten plus TAP die der Master-FX-Gesten, die TAP-Lampe zeigt den Zustand, das Tap-Tempo entfällt; Menüseite TAP MOTION in der Gruppe FEATURES des Menüs BLECH | `data/patches/tap-motion.json`, `tools/patch/tap_motion.py`, `tools/emu/tap_motion_cases.py`, [Messung](messungen/2026-10-15-tap-motion-patch.md) |
| Notenassistent (Idee 54): im KEYBOARD-Modus leuchten gleich nach einer Note die Pads der passenden Noten rosa (rote und blaue LED zusammen), je besser die Passung desto heller (Prim und Quinte, dann Terzen, Quarte und ein Tonleiterschritt, dann Sexten); gestoppt oder pausiert bleiben sie, beim Spielen blenden sie aus; im CHORD-Modus die passenden nächsten Akkorde ([Helligkeit und Ausblenden](messungen/2026-10-19-notenassistent-helligkeit.md)); das Licht der Firmware gewinnt; beim Spielen bleibt das Pad der zuletzt gespielten Note rot, bis die nächste kommt ([gespielte Note](messungen/2026-10-22-notenassistent-spielende-note.md)); Menüseite NOTE ASSIST in der Gruppe FEATURES des Menüs BLECH, Bit 4 der Flags | `data/patches/note-assistant.json`, `tools/patch/note_assist.py`, `tools/emu/note_assist_cases.py`, [Messung](messungen/2026-10-15-note-assistant.md) |
| Würfeln (Idee 29): SHIFT + PART ERASE schreibt eine neue Melodie in den gewählten Part, Töne aus Tonart und Tonleiter des Patterns (die Tonleitertabelle der Firmware), Pausen und Noten auf der 16tel-Folge, Gates mit gelegentlichem Tie, innerhalb von Pattern-Länge und LAST STEP; nur die Step-Records des Parts im RAM, nichts im Flash, ungespeichert bis WRITE; ein Haken am Eingang der Tastenfunktion der Modustasten (`0xC006FEDC`, Kette `mode-key`), keine Startphase; auf Hacktribe und auf Korgs Original | `data/patches/dice.json`, `tools/patch/dice.py`, `tools/emu/dice_cases.py`, `test/dice-firmware.test.mjs`, [Messung](messungen/2026-10-16-wuerfeln.md) |
| Ruhender IFX (vorerst in keinem Satz, weder rot noch blau: er setzt den IFX auf Punch, stellt den eigenen aber nicht zuverlässig zurück): ein Part, der 5 s stumm ist oder dessen IFX aus ist, bekommt den leichtesten Insert-Effekt Punch; sobald er wieder zu hören ist, lädt die Firmware seinen eigenen Effekt; umgeschaltet wird nur auf dem Hauptbildschirm; ohne Einstellung, an außer mit EXIT beim Einschalten; ein Literal (`0xC0089D90`, Kette `led-timer`); auf Hacktribe und auf Korgs Original | `data/patches/ifx-idle.json`, `tools/patch/ifx_idle.py`, `tools/emu/ifx_idle_cases.py`, [Messung](messungen/2026-10-18-ifx-ruht.md) |
| Pad-Farben: was die Firmware rot zeigt und der gewählte Part in Rot, Blau oder Pink, beides zusammen in der übrigen Farbe; ein Haken am Sprung zum Sender der LED-Nachrichten (`0xC00876A8`), Sollwert und Kopie der Firmware bleiben; Code bei `0xC018B000`, Zustand `0xC018BF00`; Menüseiten PAD COLOR und SELECT COLOR unter CUSTOMIZATION; im Power Save alle LEDs gedimmt um den Wert der Seite POWER SAVE, LED DIMMING (0 bis 100 %, Vorgabe 75 %), ein zweiter Haken am Schalter `0xC0028AB4` schickt sie beim Wechsel neu; im SEQUENCER-Modus zeigt ein Poly-Part Steps mit 2 oder mehr Noten in Pink; auch für die blaue Electribe (`pad-colors-synth.json`) | `data/patches/pad-colors.json`, `tools/patch/pad_colors.py`, `tools/emu/menu_cases.py` (`pad_colour_cases`), [Messung](messungen/2026-10-17-pad-farben.md), [Power Save](messungen/2026-10-18-energiesparen-leds.md), [Poly-Steps](messungen/2026-10-19-poly-pads-pink.md) |
| Ladeanimation (Idee 41, Renderer `tools/art/loading`): solange die Samples laden, zieht Blechy mit geschlossenen Augen eine Line über den Tisch, unten stehen "LADE SAMPLES..." und die Prozent, ab 95 % reißt er die Augen auf, bei 100 % steht "FERTIG"; höchstens 20 Bilder pro Sekunde, das Finale wechselt alle 96 ms (64 ms waren für das LCD zu schnell, die Augen flackerten nur); ist DISPLAY INVERT aus, invertiert der Patch seine Bilder selbst, damit der Schirm dunkel bleibt; die Bilder (`assets/blechy/loading.bin`, 2440 Byte) baut `tools/art/loading/firmware_assets.py` aus dem Renderer der Vorschau. Dazu der Look (Entwurf `restyle_reference below`): mit DISPLAY INVERT ON bekommt jedes Bild der Firmware den Stil des Startbilds, der Seitenreiter eine gestanzte Ecke, Kästen abgeschnittene Ecken und einen geditherten Schatten, gefüllte Kästen (der Patternname, die Wertfenster) werden zu Rahmen, damit der Schirm dunkel bleibt, und unten, links und rechts läuft ein geditherter Rand an langen freien Stücken, rechts bis neben die Symbole der Kopfzeile. Er hängt am Seitenvergleich der Display-Sendung (`0xC0016084`, Kette `display-send`): bei Seite 0 zeichnet der Patch den Look aus dem Bild der Firmware in einen eigenen Puffer und vergleicht und kopiert die Seiten von dort, das Bild der Firmware bleibt unberührt. Ohne Look bleiben die offene App, Blechy beim Ausschalten, der Startbild-Editor, die Ladeanimation, DISPLAY INVERT OFF und EXIT beim Einschalten; `restyle_reference` in `load_bar.py` ist dieselbe Regel in Python, rund 0,3 Mio. Befehle pro gesendetem Bild (gemessen in Unicorn) | `data/patches/load-bar.json`, `tools/patch/load_bar.py`, `tools/emu/loadbar_cases.py`, [Messung](messungen/2026-10-15-ladebalken.md) |
| Sample-Fehler: der Lader von `e2sSample.all` überspringt ein Sample, das er nicht nehmen kann (Format, belegter Platz), und lädt das nächste; das Fenster nennt das erste (`Sample 371`, darunter der Grund) statt "Unknown Error."; elf Haken im Lader, auf beiden Builds | `data/patches/sample-errors.json`, `tools/patch/sample_errors.py`, `tools/emu/sample_error_cases.py`, `test/sample-errors.test.mjs`, [Messung](messungen/2026-10-15-sample-fehler.md) |
| Werksbank im leeren Flash des Emulators (411 Einträge, ohne Korg-Daten), damit Werksplätze Samples aufnehmen | `tools/emu/factorybank.py`, `tools/emu/machine.py` (`blank_flash`), `tools/emu/test_factorybank.py`, [Messung](messungen/2026-10-15-sample-fehler.md) |
| Startbild des Editors im Flash (Sektor `0x7F0000`), ab dem ersten Bild beim Start (Idee 35); vom 15. bis 16.10. lag es auf der Karte | `tools/patch/splash_editor.py`, `tools/emu/splash_cases.py`, [Messung](messungen/2026-10-15-startbild-karte.md) |
| Geprüfte Kopien: dieselbe Eingabe mit demselben Patch-Satz ergibt dieselbe Datei und dieselben Starts, die Prüfung im Emulator entfällt für Kopien, deren SHA-256 von Eingabe und Ergebnis in der Liste stehen (vor dem Release mit Korgs roter und blauer 2.02 und Hacktribe 2.02 gebaut) | `src/patcher.mjs` (`verifiedReport`), `data/patches/verified.json`, `tools/verify-patches.mjs`, `test/patcher.test.mjs` |
| Kurzprüfung: eine Kopie, die nicht in der Liste steht, prüft der Patcher zuerst nur auf Start und Rettungswege (normaler Start, Update-Abfrage, Panel-Update, Startmodi, EXIT, DSP einmal, Startphase), auf dem Mac 14 s statt rund 7 min; die Tests der einzelnen Patches laufen nur mit der Wahl "Voller Test", denn sie prüfen unseren Code, der in jeder Datei derselbe ist. "Kein Test" patcht nur und braucht ein Häkchen, dass der Nutzer die Folgen kennt | `tools/emu/check.py` (`--quick`), `tools/emu/server.py` (`/check?quick=1`), `site/app/patcher.mjs`, `test/patcher.test.mjs` |
| Prüfung vor dem Export im Emulator | `tools/emu/check.py`, `tools/emu/bootmap.py`, `tools/emu/splash_cases.py`, `tools/emu/mfx_cases.py`, `tools/emu/menu_cases.py`, `tools/emu/pswitch_cases.py`, `tools/emu/tap_motion_cases.py`, `tools/emu/note_assist_cases.py`, `tools/emu/dice_cases.py`, `tools/emu/ifx_idle_cases.py`, `tools/emu/shortcut_cases.py`, `tools/emu/remote_cases.py`, `tools/emu/loadbar_cases.py`, `tools/emu/power_off_cases.py`, `tools/emu/synth_filter_cases.py` |
| Schreibregel für die Karte (Plugin-Werte) | `tools/patch/script_store.s`, [Messung](messungen/2026-10-14-skript-speicher.md) |
| Synth-Filter auf Korgs Original (Idee 55): LPF, HPF und BPF laufen durch MS20, MG, P5, OB und Acid wie bei Hacktribe, der Part behält den Typ, auch beim Laden eines Patterns (Korgs Setter faltet ihn sonst auf den electribe-Filter); zwei Stellen (die Auswahl in der Tastenfunktion bei `0xC006FCE8`, der Sprung über das Falten im Setter bei `0xC00495DC`), eigener Code bei `0xC0190000`, mit EXIT beim Einschalten Korgs Verhalten; nur für Korgs Build (`builds: ["stock"]`, `notNeededOn`) | `data/patches/synth-filters.json`, `tools/patch/synth_filters.py`, `tools/emu/synth_filter_cases.py`, `test/synth-filters.test.mjs`, [Messung](messungen/2026-10-15-synth-filter.md) |
| Preset-Tabellen: Platz für 128 Insert- und 128 Master-Presets statt 100 (Korgs Original hat 38 und 32 belegt). Neue Zeigerfelder, Klemme der Getter auf 127, das Reglergedächtnis des Insert-Effekts auf 16 mal 128 Byte; kein Record wird bewegt, die Menülängen bleiben. Der Editor fügt Presets als Kopie hinzu und schreibt sie in eine Kopie der Datei, die der Emulator vorher prüft | `data/patches/preset-tables.json`, `data/patches/preset-tables-stock.json`, `tools/patch/preset_tables.py`, `tools/emu/preset_cases.py`, `src/presets.mjs`, `tools/preset-add.mjs`, `test/presets.test.mjs`, [Messung](messungen/2026-10-15-preset-tabellen.md) |
| Doom vom SD-Lader (SHIFT + TAP beim Einschalten): der Lader ist ein Patch des Satzes, eigener Code (AGPL) bei `0xC017CC00` im freien Lauf hinter der Preset-Reglertabelle, ein Haken am Aufruf von `0xC002A35C` in der Startfunktion (`0xC002ADB0`), der erst die Firmware laufen lässt und nur bei genau SHIFT + TAP die Karte liest: `KORG/blechtribe/Doom/doom.bin`, Länge und SHA-256 geprüft, dann Einsprung. Ohne die Tasten oder mit EXIT beim Einschalten läuft nur der Tastenvergleich. Auf Hacktribe und auf Korgs Original; Engine, Quellen und Lizenzen in `third_party/doom/`, [Lizenz](doom-lizenz.md) | `data/patches/doom-loader.json`, `tools/patch/doom_loader.py`, `tools/doom/bootstrap.*`, `test/doom-layout.test.mjs`, `test/patch-ram.test.mjs`, [Messung](messungen/2026-10-15-doom-im-patcher.md) |
| Blechy beim Ausschalten: das Fenster "Power Off" wird durch Blechy ersetzt, der neben einer Zeile winkt (700 ms), danach blendet das Bild ab und geht wie eine alte Röhre aus (Strich, Punkt, dunkel); Code bei `0xC01A5800`, Bild bei `0xC01A4C00`, ein Wort bei `0xC01A5BF0` sagt dem Look des Ladebalkens, dass er die Bilder in Ruhe lässt; das Speichern der Firmware bleibt unberührt (Haken in der Wartefunktion des Ausschalt-Handlers, ohne Startphase) | `data/patches/power-off.json`, `tools/patch/power_off.py`, `tools/emu/power_off_cases.py`, `test/power-off.test.mjs`, [Messung](messungen/2026-10-15-blechy-power-off.md) |
| BLECH SysEx: eigene Befehle `0x60` bis `0x63` zum Lesen und Schreiben des RAM in Blöcken bis 32 KiB (dazu `0x64` Flash lesen, `0x65`/`0x66` die Update-Datei und `0x67` eine Plugin-Datei in `KORG/blechtribe/Plugin/`), je Block mit CRC-32 und einer Antwort mit Status, auf Hacktribe und auf Korgs Original; die Schutzliste von `data/protected.mjs` prüft die Firmware selbst (Tabelle aus `src/sysex-table.mjs`, nie von Hand), kein Flash-Schreib-Befehl, Ausführen (`0x6F`) nur im Stub-Puffer; Hacktribes `0x52` bis `0x57` verworfen, mit EXIT beim Einschalten gehen sie außer `0x56` wieder; zwei Haken (Funktionsbyte `0xC0026A8C`, Ausführer `0xC0026418`), ohne Startphase, mit EXIT beim Einschalten stumm. Die Seite nimmt sie, wenn das Gerät INFO beantwortet, sonst Hacktribes `0x52` bis `0x57` | `data/patches/blech-sysex.json`, `tools/patch/blech_sysex.py`, `tools/patch/blech_sysex.mjs`, `src/sysex-table.mjs`, `tools/emu/sysex_cases.py`, `test/blech-sysex.test.mjs`, `test/blech-session.test.mjs`, `test/emulator-sysex.test.mjs`, `test/emulator-blech-session.test.mjs`, [Messung](messungen/2026-10-15-blech-sysex.md) |
| Anpassung im BLECH-Menü: untere LEDs (METER, COLOR, OFF, Farbe) und Display-Licht (frei gemischt, Software-PWM), Einstellungen nur auf der Karte | `tools/patch/script_menu.s`, `tools/emu/menu_cases.py` (`look_cases`), [Messung](messungen/2026-10-14-blech-anpassung.md) |
| Ordner übernehmen beim ersten Start: hat `KORG/blechtribe` keine `Sample/e2sSample.all` (oder fehlt ganz), `KORG/hacktribe` oder `KORG/electribe sampler` aber schon, fragt BLECH vor dem Sample-Laden auf dem Display, ob der Ordner kopiert werden soll (Rad, EDIT oder PART wählen zwischen beiden, MENU kopiert, EXIT startet ohne); kopiert werden alle Dateien und Unterordner bis 5 Ebenen, Namen mit Punkt am Anfang nicht, Dateien, die in `KORG/blechtribe` schon liegen, bleiben, wie sie sind; nur Sampler, nicht mit EXIT beim Einschalten | `tools/patch/script_migrate.s`, `tools/emu/migrate_cases.py`, [Messung](messungen/2026-10-19-ordner-uebernehmen.md) |
| EXIT-Shortcuts in der Laufzeit des BLECH-Menüs: EXIT gehalten + WRITE speichert das Pattern an seinen Platz (das Write-Fenster der Firmware bekommt den zweiten WRITE), EXIT gehalten + Pad setzt den Klang eines Parts auf die Werte der Bank zurück (Pattern-Laden der Firmware `0xC004AB84`); die WRITE-LED atmet, solange das Pattern ungespeichert ist; rot und blau ([blau](messungen/2026-10-24-blau-shortcuts-akkorde.md)), nicht mit EXIT beim Einschalten | `tools/patch/script_shortcuts.s`, `tools/emu/shortcut_cases.py`, [Messung](messungen/2026-10-19-exit-shortcuts.md) |
| Tasten vom Rechner: der Frame-Haken nimmt ein Befehlswort, das `KORG.exec` hinterlegt, und drückt die Taste oder dreht das Hauptrad über die Handler der Firmware; damit gehen `KORG.press` und `KORG.turn` auch ans Gerät; nur Sampler | `tools/patch/script_remote.s`, `src/remote.mjs`, `tools/emu/remote_cases.py`, `tools/device/remote_press.py`, [Messung](messungen/2026-10-22-tasten-vom-rechner.md) |
| Presets und Modulationen von der Karte: `KORG/blechtribe/Presets/e2sFx.all` wird beim Start nach den Plugins gelesen, erst ganz geprüft (Kopf, Build, Einträge, Länge, CRC-32), dann gehen die Datensätze ins RAM, wohin die Getter zeigen, und die Modulationen in die Tabelle des Builds; nie in den Flash. Fehlt die Datei, ist sie beschädigt oder ist EXIT beim Einschalten gehalten, bleiben die Presets der Firmware; nur rot | `tools/patch/fx_card.s`, `src/fx-collection.mjs`, `src/fx-v2.mjs`, `tools/emu/fx_card_cases.py`, `test/emulator-fxcard.test.mjs`, [Messung](messungen/2026-10-22-sammeldatei-karte.md) |
| Blechy eingebaut (Seite am Ende des Menü-Rings): sein Block liegt im Abbild bei `0xC0184000` und bleibt dort (der Lader legt nur Eintrag und Variablen in den Pool), BLECH lädt ihn beim Start vor der Karte, auch ohne Karte und Datei, der Rahmenhaken öffnet und schließt ihn mit der Seite (Haken: Event EDIT rechts `0xC0064430`, Pattern EDIT links `0xC0067754`), mit EXIT beim Einschalten ist er nicht da; kein Menüpunkt, nicht exportierbar, nicht abschaltbar | `tools/patch/script_builtin.s`, `data/script/blechy-block.hex` (gebaut von `tools/blechy-build.mjs`), `tools/emu/blechy_cases.py`, `tools/emu/menu_cases.py` (`blechy_ring_cases`), `tools/patch/test_script_hooks.py`, `test/emulator-blechy.test.mjs`, [Messung](messungen/2026-10-15-blechy.md) |

Am Gerät geprüft sind zwei Dinge: der Weg mit einem Datenpatch (Startbild) hin
und mit dem normalen Update zurück ([Rückweg geübt](messungen/2026-10-10-rueckweg-geuebt.md))
und der MFX-2-Patch, der erste Code-Patch am Gerät, samt Notschalter
([MFX 2 am Gerät](messungen/2026-10-13-mfx-umschalter-geraet.md)). Startbild-Editor,
Patternwechsel, Ladebalken, Plugin-Laufzeit, BLECH-Menü und der Kartenzugriff sind nur im Emulator geprüft.
Geplant und nicht gebaut ist alles, was unter "Offen" steht.

## Was in der VSB steckt

Die Electribe hat zwei Prozessoren:

- **ARM** (TI AM180x): Bedienfeld (Panel-Controller an UART0), Display
  (SPI0), Sequencer, Menüs, MIDI, SD-Karte, Flash (SPI1).
- **DSP** (Blackfin von Analog Devices, genaues Modell offen): rechnet den
  Klang, also Samples, Filter, Inserts, Master-Effekt.

Die SYSTEM.VSB ist `0x200100` Byte: 256 Byte Kopf plus das 2-MiB-Abbild
des ARM, mit Code, Daten (Presets, Texte, Startbild, Tabellen) und dem
eingebetteten DSP-Programm ab `0xC00F9E10` (rund 270 KB), das der ARM beim
Start über SPI in den DSP lädt. Zur Laufzeit schickt der ARM dem DSP nur
Befehle und Werte über den Host-Port
(`docs/messungen/2026-10-09-mfx-dsp.md`). Mehr zum DSP:
[DSP, erster Blick](hintergrund/dsp-erster-blick.md).

Die VSB ist unverschlüsselt. Patches setzen auf Korgs 2.02 mit Hacktribe auf;
FX-Presets, Menülängen und Startbild darin dürfen vom Original abweichen. Der
Editor erkennt diesen Stand an Fingerabdrücken (`data/devices.mjs`,
`src/firmware.mjs`).

## Drei Arten von Patches

| Art | Beispiele | Prüfbar im Emulator | Schwierigkeit |
|---|---|---|---|
| Daten | Presets, Menülängen, Startbild (Idee 20), Texte und Themes (27) | ja | gering, teils gebaut (Export, Startbild) |
| ARM-Code | Tasten, Menüpunkte, LEDs, Touchpad-Routing, Bugfixes, Spiele | ja, der Emulator führt den ARM aus | mittel |
| DSP-Code | neue Effektplätze, neue Algorithmen, ein dritter Effekt über alles (Idee 53) | nein, der DSP ist im Emulator eine Attrappe | hoch |

## Patch-Format

Gebaut in `src/patch.mjs`, Version 1:

```json
{ "format": "gelumpe-patch", "version": 1, "id": "splash", "name": "Startbild",
  "changes": [
    { "field": "splash", "bytes": "<hex>" },
    { "file": 1712384, "bytes": "<hex>", "expect": "<SHA-256 der ersetzten Bytes>" } ] }
```

- **Feld-Änderung:** ein Feld der Gerätekarte, das in der Firmware liegt
  und beschreibbar ist, in genau seiner Breite. Die Prüfung vor dem Export
  erlaubt, dass es beim Start gelesen wird, denn die Karte kennt sein
  Format. Erstes Beispiel: das Startbild.
- **Rohe Änderung:** Datei-Offset, neue Bytes und die Prüfsumme der Bytes,
  die sie ersetzt. Ohne Prüfsumme oder mit falscher wird nichts angewendet.
  Die Original-Bytes stehen nie im Patch.
- **Kopier-Änderung** (`copy`, optional mit `over`): nimmt ihre Bytes beim
  Anwenden aus der eigenen VSB, die Quelle mit Prüfsumme, und schreibt `over`
  darüber. So kann ein Patch Firmware-Tabellen wiederverwenden, ohne eine
  mitzubringen.
- Abgelehnt wird auch: Änderungen im Kopf der VSB oder außerhalb, zwei
  Änderungen an derselben Stelle, eine Basis, die nicht die gemessene
  Firmware ist, und eine Kopie, die danach die Firmware-Prüfung nicht
  besteht.
- Später: Code als Quelltext, dem der Patcher einen Platz zuteilt, damit
  sich zwei Patches nicht überschreiben (geplant). Heute setzt jeder Patch seine
  Adressen fest.

## Einhaken

Ein Patch überschreibt nie Original-Code dauerhaft. Er hängt sich ein:

1. **Am Funktionsanfang:** der erste Befehl wird ein Sprung in unseren Code;
   der verdrängte Befehl läuft dort und danach geht es im Original weiter.
2. **An einer Aufrufstelle:** `rufe F auf` wird `rufe UNSER_CODE auf`, und
   unser Code ruft am Ende F.
3. **Über einen Zeiger in einer Tabelle:** Funktionszeiger der Firmware,
   etwa die Bildschirmklassen (vtables, `0xC00E36E8` Menü Pattern), gegen
   unseren Code tauschen. Reine Datenänderung. Das BLECH-Menü hängt sich so
   ein, über eine Kopie der Bildschirmtabelle
   (`docs/messungen/2026-10-14-blech-menue.md`).

Die gebauten Patches nutzen Aufrufstellen, Befehle und Literale als Haken
(`kind` `call`, `instruction`, `literal` in den Listen unter `data/patches/`).

**Geplant:** Den Sprung und die erste Abfrage (Notschalter) erzeugt immer der
Patcher, nicht der Autor eines Patches. Heute steht beides im Code des
jeweiligen Patches (`tools/patch/`), der Patcher erzeugt es nicht.

## Haken-Register

Gebaut in `src/hooks.mjs`, die Ketten stehen in `data/hooks.mjs`. Ein
Code-Patch nennt in einer optionalen Liste `hooks` (Format bleibt Version 1,
ein Patch ohne Liste wird nicht erfasst) jede Einhängestelle:

```json
{ "site": "0xC00700D8", "kind": "instruction", "chain": "key-dispatch",
  "position": "before", "swallow": true, "note": "..." }
```

- `site`: RAM-Adresse des geänderten Worts. `kind`: `call` (Aufruf ersetzt),
  `vtable-slot`, `literal`, `instruction`.
- `chain`: die benannte Aufrufkette, die der Haken abfängt (ein Name oder eine
  Liste), etwa `start`, `key-dispatch`, `pattern-set`, `frame`,
  `global-screen`. Die Tabelle ordnet jeder Kette ihre Stufen vom Eingang
  abwärts; eine Stelle, die dort fehlt, wird abgelehnt.
- `position`: `before`, `after` oder `replace` gegenüber dem Original.
  `swallow`: ob der Haken das Ereignis davon abhalten kann, das Original und
  die Stufen dahinter zu erreichen.

`applyPatches` prüft die Haken aller Patches vor dem Schreiben:

| Fall | Folge |
|---|---|
| zwei Patches (oder ein Patch zweimal) auf derselben Stelle | abgelehnt |
| zwei Patches auf derselben Stufe einer Kette, einer ersetzt | abgelehnt (Patternwechsel gegen `patternChange` an `0xC0081F50`) |
| Stelle oder Kette unbekannt, Angabe fehlerhaft | abgelehnt |
| bekanntes Paar in `INCOMPATIBLE` (alter Startbild-Editor und Laufzeit, beide besitzen `0xC002ADAC` und `0xC0064D3C`) | abgelehnt, mit einer Meldung statt einer je Stelle |
| ein Haken, der verschlucken kann, liegt vor dem Haken eines anderen Patches in derselben Kette (Eingangsfilter vor MFX 2) | angewendet, als Abhängigkeit in `dependencies` gemeldet |

Startbild-Editor und MFX 2 liegen auf verschiedenen Ketten und gehen
zusammen. Der Patternwechsel (Idee 46) ist gebaut (`data/patches/pattern-switch.json`); seine Haken
standen vorher nur als Beschreibung in `test/fixtures/hooks-planned.json`, damit die Kollisionen vor dem Bau
getestet waren. Dort steht noch die Beschreibung der Plugin-Laufzeit aus der Planung (Idee 50); gebaut ist sie in
`data/patches/script-runtime.json`. Stufen mit mehreren Stellen (alle Wege einer Patternwahl enden in
`set_number`) prüft die Tabelle bewusst grob: die drei Einstiege (Rad, Pad, MIDI) sind eine Stufe, `set_number`
selbst die nächste, denn der Haken am Rad ruft `set_number` weiter und nimmt der Plugin-Laufzeit (`patternChange` an
`0xC0081F50`) die Nummer nicht. Die Kette `start` kennt zwei Stufen für die Karte (`card-mount`: die Frage der Firmware
nach der `e2sSample.all`, die die Karte mountet, und der Startbild-Editor dahinter; `sample-load`: der Lader und sein
Textupdate), die Kette `frame` eine für das Senden des Rahmens (`display-flush`, der Ladebalken).

## Patch-Datei und bsdiff (Release-Dateien)

Zum Release gehören zwei Dateien, die aus dem Patch-Satz `data/patches/blech.json`
und einer VSB gebaut werden. Beide kommen nach `dist-release/` (gitignored) und
werden nie eingecheckt. Als Eingabe dient die `SYSTEM.VSB` aus Hacktribes Paket
(`hacktribe-es2-sd-package.zip`; die Datei hat sha256 `7cb4825c...`), denn nur an
diese passt das bsdiff:

```bash
E2_VSB="<SYSTEM.VSB aus dem Paket>" npm run build:blech-patch
npm run build:blech-patch -- --vsb <SYSTEM.VSB> --version 1.0.1
```

| Datei | Wofür | Anwenden |
|---|---|---|
| `BLECH.patch` | der ganze Satz in unserem Format: alle Patches mit Haken, Prüfsummen und Startphase-Ausnahmen. Passt auf jede Hacktribe 2.02, deren Code und feste Daten stimmen, und mit `--stock` auch auf Korgs Original 2.02 (zweiter Fingerabdruck, Ordner-Variante für Korgs Build) | `node tools/patch/apply.mjs --vsb SYSTEM.VSB --patch BLECH.patch --out BLECH.VSB`, oder in `src/patchfile.mjs` (`applyPatchFile`) |
| `BLECH-for-7cb4825c.bsdiff`, mit `--stock` auch `BLECH-for-1d0f0689.bsdiff` | genau diese Datei zu BLECH als bsdiff 4 (`BSDIFF40`, wie Hacktribes Patch). Der Name trägt den Anfang des sha256 der Eingabe | `bspatch SYSTEM.VSB BLECH.VSB BLECH-for-7cb4825c.bsdiff`, ohne unsere App, nur mit der Datei mit diesem Hash |

**Welche VSB passt.** Hacktribes Datei und eine bearbeitete VSB unterscheiden
sich nur in Daten, die Nutzer ändern. An einer eigenen SYSTEM.VSB gemessen, gegen
die aus dem Paket: 2317 Byte in 1331 Folgen, nämlich FX-Presets (Master-Slot 10 und
33 bis 49, Insert-Slot 50 bis 59, zusammen 1662 Byte), die Menülängen (14 einzelne
Bytes in Code-Literalen, Master 32 auf 49, Insert 49 auf 59) und das Startbild
(641 Byte ab `0xF9954`). Kein Code, kein DSP-Programm.

`BLECH.patch` prüft deshalb nicht die ganze Datei, sondern einen
**Fingerabdruck**: sha256 über alle Bytes außer den `userData`-Bereichen (FX-Tabellen,
Groove- und Modulationstabelle, Startbild, Menülängen; aus der Gerätekarte
abgeleitet, `userDataRanges()`). Beide VSBs bestehen ihn. Jede Änderung des
Patches prüft außerdem weiter einzeln die Bytes, die sie ersetzt (`expect`), auch
an den Haken. Der Fingerabdruck der Ausgabe lässt nur die `userData`-Bytes aus,
die der Patch nicht schreibt (das Startbild schreibt er), prüft also auch, was
der Patch geschrieben hat.

Gemessen: der Satz lässt sich auf beide VSBs anwenden, und die Datei gibt jeweils
dieselben Bytes wie der Satz. Von `tools/emu/check.py` besteht die Paket-VSB
alle Prüfungen bis auf `splash:valid`; der schlägt bei der eigenen VSB und beim
Startbild-Patch allein ebenso fehl, liegt also nicht an der Datei.

**Format von `BLECH.patch`** (Version 2, Zahlen little endian): Kopf mit 128 Byte,
dann der Inhalt als JSON.

| Offset | Größe | Inhalt |
|---|---|---|
| 0 | 8 | Kennung `GLMPPAT\0` |
| 8 | 2 | Formatversion, 2 |
| 10 | 2 | Merkmale, 0 |
| 12 | 4 | Länge des Inhalts |
| 16 | 16 | BLECH-Version als Text, mit 0 aufgefüllt (die aus `package.json`, also die des Releases) |
| 32 | 32 | Fingerabdruck der erwarteten Eingabe (sha256 ohne `userData`) |
| 64 | 32 | Fingerabdruck der erwarteten Ausgabe (sha256 ohne die `userData`-Bytes, die der Patch nicht schreibt) |
| 96 | 32 | sha256 des Inhalts |
| 128 | n | `{ "format": "gelumpe-patch-file", id, name, userData: [[Datei, Länge], ...], patches: [...] }` |

Die `patches` sind dieselben Objekte, die `applyPatches` aus den JSON-Dateien
bekommt, in derselben Reihenfolge. Die Datei anwenden heißt also: Fingerabdruck der
Eingabe prüfen, `applyPatches`, Fingerabdruck der Ausgabe prüfen. Weicht eins ab,
wird nichts geschrieben; das Ergebnis ist Byte für Byte das des Satzes
(`test/patch-file.test.mjs`). `--patch BLECH.patch` steht allein, nicht zusammen
mit JSON-Patches. Version 1 (ein Hash über die ganze Datei) wurde nie
veröffentlicht und wird nicht gelesen.

**Keine Firmware in der Datei**, nur was die JSON-Patches schon tragen:
unseren Code und unsere Daten, die Hashes der Bytes, die sie ersetzen (Hashes
nennen Bytes, sie enthalten sie nicht), Quelladressen der `copy`-Änderungen
(Adressen, keine Bytes) und an einzelnen Haken das verdrängte Befehlswort
(4 Byte), das unser Code nachspielt.

**Keine Firmware in dem bsdiff:** `tools/patch/bsdiff.mjs` sucht die
Übereinstimmungen nicht, es kennt die Änderungen. Was die Patches nicht
anfassen, ist ein Treffer an gleicher Stelle, eine `copy`-Änderung ein Treffer
an der Quelladresse, alles andere steht als Literal im Extra-Block. Klassisches
bsdiff würde ein kopiertes Stück als Differenz zur Zielstelle speichern, und
das wäre Firmware. Hier ist der Diff-Block nur Nullen. Gemessen an der
Paket-VSB: Diff-Block 2.073.917 Byte, alle null; Extra-Block 23.491 Byte, das
sind Bytes der Patches. Die längste Folge im Extra-Block, die auch in der
Original-VSB steht und mehr als drei verschiedene Bytewerte hat, ist 18 Byte
lang (9 Folgen, zusammen 151 Byte, zufällig gleiche Befehlsworte); alles
Längere sind Nullen und Einsen (Tabellen). `bspatch` (macOS) liefert damit
dieselben Bytes wie der Satz. Der Steuerblock verrät Quelladressen der Kopien,
keine Bytes. Gebaut wird mit dem Programm `bzip2`.

## Schreibregel für die Karte

Gebaut für die Plugin-Werte (`korg.store`, `tools/patch/script_store.s`), im
Emulator geprüft. Code eines Patches greift auf die Karte nur über die
Datei-Funktionen der Firmware zu (`f_open`, `f_read`, `f_write`, `f_close`,
Adressen in [Virtuelle SD](hintergrund/virtuelle-sd.md)), nie über den
SD-Controller selbst. FatFs hat keine Sperre, deshalb gilt für alles, was
`korg.store` und die Laufzeit schreiben:

1. Lesen nur beim Start, hinter dem Laden der `e2sSample.all` und mit EXIT
   noch nicht gehalten. Schreiben nur im Rahmenhaken (UiTask) bei offenem
   Hauptbildschirm, also nie während DATA UTILITY, Sample-Laden oder einer anderen
   Kartenbedienung der Firmware.
2. Geschrieben wird nur auf eine ausdrückliche Anforderung (`korg.store.save()`),
   mit mindestens 50 Rahmen (2 Sekunden) Pause zwischen zwei Schreibvorgängen.
3. Eine Datei wird ganz in einem Vorgang geschrieben und nie ersetzt: zwei Dateien
   wechseln sich mit einer Generationsnummer und einer CRC-32 ab, so bleibt bei
   einem Abbruch (Strom, Karte gezogen) die vorige Generation lesbar.
4. Ein Fehlschlag wird gezählt und nicht wiederholt, die Firmware läuft weiter.
5. Keine Datei wird gelöscht oder umbenannt, kein Ordner angelegt; `KORG/blechtribe/Plugin/`
   legt der Nutzer an.

Eine Ausnahme ist die Übernahme des alten Ordners beim ersten Start (`tools/patch/script_migrate.s`,
[Messung](messungen/2026-10-19-ordner-uebernehmen.md)): nur auf MENU legt sie `KORG/blechtribe` mit Unterordnern an, soweit sie fehlen, und
kopiert hinein, vor dem Sample-Lader und im selben Ablauf, also ohne gleichzeitigen Kartenzugriff der Firmware. Gelöscht
oder überschrieben wird nichts: eine Datei, die schon da ist, bleibt (`f_open` mit "neu anlegen"), der alte Ordner bleibt.

Das Startbild des Editors (`splash.a.bin`, `splash.b.bin` in `KORG/blechtribe/`, Satz mit Generation und CRC-32,
[Messung](messungen/2026-10-15-startbild-karte.md)) folgt der Regel 3 ebenso: WRITE schreibt Generation plus eins in die Datei, in der
die höchste nicht steht. Gelesen wird beim Start, und zwar direkt hinter der Frage der Firmware nach der `e2sSample.all` (sie
mountet die Karte), nicht davor; ohne gemountete Karte (`FatFs[0]->fs_type == 0`) wird nicht gefragt.

Das BLECH Menü (`docs/messungen/2026-10-14-blech-menue.md`) ist die Ausnahme zu 1: es
schreibt nur auf WRITE des Nutzers (`settings.a/b.bin` nach Regel 3, `e2sPlugin.all` in einem
Vorgang) und liest die Dateiliste und `*.blech` beim Öffnen der Seite IMPORT PLUGIN, jeweils
im UiTask bei offenem Menübildschirm. Dann ist weder DATA UTILITY noch Sample-Laden offen.

Belege und Grenzen: `docs/messungen/2026-10-14-skript-speicher.md`. Am Gerät
ist das Schreiben über FatFs noch nicht geprüft (Schritte in
`docs/geraetetests/karte.md`).

## Schalter, die das Menü ergänzen muss

Der Patternwechsel ist beim Start an, sobald seit dem Einschalten eine Karte gemountet war. Im Stand blättert das Rad nur, wenn das Pattern ungespeicherte Änderungen hat: `VIEW:` zeigt die Nummer, MENU lädt, EXIT bleibt ([Messung](messungen/2026-10-18-ungespeichert-blaettern.md)). Das Menü BLECH schaltet ihn ab, ohne dass der Patch
dafür umgebaut wird: Seite PATTERN CONFIRM in der Gruppe FEATURES des Menüs BLECH (gebaut am 15.10. in der Gruppe CUSTOMIZATION, dann eine Seite der Liste selbst, seit der Neuordnung in FEATURES, `menu:confirm_*`). Der Vertrag
und wie das Menü ihn erfüllt:

- Das Wort `PS_SETTING` bei `0xC0180F10` (RAM, vom Patch nie beschrieben): `0xFFFFFFFF` (nie geschrieben) oder 1 heißt an,
  0 heißt aus. Der Patch liest es bei jedem Haken.
- In der Einstellungsdatei (`settings.a/b.bin`, Version 2) die Flags bei `+12`: **Bit 2 gesetzt heißt aus**. Die Bedeutung
  ist umgekehrt, damit jede bestehende Datei (Bit 2 ist dort 0) weiter "an" heißt. Die Datei bleibt Version 2 und die Prüfsumme
  gilt wie bisher; ein älterer Leser ignoriert das Bit.
- Beim Laden der Datei (`menu_settings_load`) und bei jedem Umschalten das Wort schreiben, `1` oder `0`. Fehlt die Datei oder
  ist sie ungültig, nichts schreiben. Das Menü hält den Zustand in `MENU_STATE + 0x158` (1 an, 0 aus; die Lücke zwischen den
  beiden Dateipuffern), `menu_arm` setzt 1, `menu_settings_load` und die Seite schreiben das Wort, `menu_settings_save` setzt
  Bit 2 der Flags, wenn der Zustand 0 ist. Die Bits 0 und 1 (Laufzeit, MFX 2) und das Look-Wort bei `+16` bleiben unberührt. Das Menü kennt für TAP Motion einen dritten Wert ONCE (Einstellungswort 2, Bit 5 der Flags, Bit 3 gewinnt); was der Patch damit tut, legt der Patch fest.

Der Notenassistent ist beim Start an, ebenfalls sobald seit dem Einschalten eine Karte gemountet war, und das Menü BLECH bekommt dafür eine eigene Seite NOTE ASSISTANT
in der Gruppe FEATURES des Menüs BLECH (gebaut, `menu:note_assist_*`). Der Vertrag, wie bei TAP MOTION:

- Das Wort `NA_SETTING` bei `0xC0189F00` (RAM, im Zustand des Patches): `0xFFFFFFFF` (nie geschrieben) oder 1 heißt an, 0 heißt aus. Der Patch liest es bei jedem Haken.
- In der Einstellungsdatei die Flags bei `+12`: **Bit 4 gesetzt heißt aus** (Bit 0 Skripte, 1 MFX 2, 2 Patternwechsel aus, 3 TAP Motion aus). Eine Datei ohne das Bit
  oder keine Datei heißt an, ältere Leser ignorieren das Bit. `FLAG_OFF_BIT` steht in `tools/patch/note_assist.py`. Beim Laden der Datei und bei jedem Umschalten das Wort schreiben, `1` oder `0`.
- Wird das Wort zur Laufzeit auf 0 gestellt, nimmt der Patch seine Hinweise innerhalb von 0,3 s von den Pads (gemessen, `setting_off_gives_the_leds_back`).

Der Ladebalken und das eigene Startbild brauchen keinen Schalter: der Balken erscheint nur, wenn eine
`e2sSample.all` da ist und EXIT beim Einschalten nicht gehalten wird, das eigene Startbild nur, wenn ein gültiger Satz im Flash steht.

## Speicherorte

| Ort | Größe | Stand |
|---|---|---|
| `FF`-Blöcke im Abbild, größter `0xC01A2100` bis `0xC0200000` | 736 KiB in 6 Blöcken, 375 KiB am Stück | keine Zeiger darauf, im Emulator beim Bedienen unverändert; am Gerät läuft Code von MFX 2 ab `0xC01A5000` (`docs/messungen/2026-10-13-mfx-umschalter-geraet.md`), die Bilder der Ladeanimation liegen bei `0xC01A3D00` bis `0xC01A4A00` (in Rot, Blau und Hacktribe `FF`); der Rest des Blocks und die gerechneten Adressen sind am Gerät ungeprüft |
| `FF` im Abbild davor, `0xC01720B0` bis `0xC01A0000` | 188 KiB | BLECH SysEx (Code `0xC0172100` bis `0xC0173800`, Tabelle `0xC0173800`; Zustand und Puffer weiter hinten, siehe die Tabelle unten), die Preset-Tabellen (Plätze `0xC0174000` bis `0xC017CC00`, Code `0xC017C000`), Patternwechsel (Code `0xC0180000`, Zustand `0xC0180F00`) und Ladeanimation (Code `0xC0181000` bis `0xC0181F00`, Zustand `0xC0181F00`; ihre Bilder liegen bei `0xC01A3D00`, der Rest des Looks bei `0xC0183900` bis `0xC0184000`, seine Puffer bei `0xC018C400` bis `0xC018CE80`), dahinter Zustand und Puffer des Startbild-Editors (`0xC0182000` bis `0xC0183000`, nur RAM), der Sample-Fehler-Patch (Code `0xC0183000` bis `0xC0183700`, Zustand `0xC0183800`), der Block von Blechy (`0xC0184000`, 15476 Byte, nur gelesen, Platz bis `0xC0188000`; sie lagen zuerst bei `0xC01A4000` und kollidierten mit dem Power-Off-Bild bei `0xC01A4A00`); gemessen an der unveränderten Firmware im Emulator: nach dem Start mit Karte und einigen Tastendrücken ist dort kein Byte beschrieben (beschrieben werden nur `0xC00F9268`, `0xC00F930F` und ab `0xC013C200` 794 Byte in anderen `FF`-Blöcken), am Gerät ungeprüft; dahinter liegt TAP Motion (Code `0xC0188000` bis `0xC0188800`, Zustand `0xC0188F00`) |
| Flash `0x660017` bis `0x6B0000` | 319 KiB | `FF`, in allen Flash-Ständen gleich (`docs/messungen/2026-10-09-flash-dump.md`) |
| Flash `0x7C0002` bis `0x7DFFFE` | 127 KiB | ebenso |
| Flash `0xE5F013` bis `0x1000000` | 1,6 MiB | ebenso, hinter der Werks-Samplebank |
| SD-Karte | groß | eigene Samples liegen dort (`e2sSample.all`), die Firmware liest beim Start von dort |

Die Datei bleibt immer `0x200100` Byte groß: im Flash liegt die Firmware
in `0x020000` bis `0x220000`, dahinter beginnen die Nutzerdaten. Mehr geht
nur zur Laufzeit, durch Nachladen aus Flash oder SD in freien RAM. Wie viel
RAM frei ist, ist noch nicht gemessen.

Code aus dem Flash oder von der SD muss die Firmware laden und anspringen.
Für den Rettungsweg bringt ein Ort außerhalb des Abbilds deshalb nichts.

## RAM der Patches

Der Patcher prüft Änderungen an der Datei: zwei Patches, die dieselben Bytes schreiben, werden abgelehnt. Was ein
Patch zur Laufzeit zusätzlich im RAM belegt (Zustandswörter, Puffer, Dateipuffer, Pool, Menüzustand), steht nicht
in der Datei und blieb deshalb unbemerkt: der Startbild-Editor hatte seinen Zustand und die Puffer bei
`0xC01A4000` bis `0xC01A5000`, über dem Code und dem Bild des Power-Off-Patches bei `0xC01A4A00`. Aufgefallen
ist es beim Vergleich der Adressen, bei keinem Test.

Jeder Patch nennt deshalb diesen RAM neben `changes` (alle Patches des Satzes tun es, ein Test hält das; die Felder
sind in `src/patch.mjs` beschrieben):

- `ram`: Speicher des Patches selbst, je Eintrag `at`, `length`, `what` und `source`. `source` sagt, woher die Größe
  kommt, `<Datei>:<SYMBOL>` im Werkzeug, das den Patch baut. Die Werkzeuge schreiben die Einträge aus ihren eigenen
  Konstanten, sie stehen nicht zweimal da. Ein Patch ohne eigenen RAM schreibt `"ram": []`.
- `shares`: ein Wort im Bereich eines anderen Patches, das dieser liest oder schreibt (`with` ist die Id des
  Besitzers). Es muss ganz in einem Bereich liegen, den der Besitzer in `ram` nennt; fehlt der Besitzer, weil der Patch
  auch allein angewendet wird, bleibt es nur fern von fremden Bereichen und geschriebenen Bytes. Drei gibt es: `PS_SETTING`
  (`0xC0180F10`, das BLECH-Menü schreibt es in den Zustand des Patternwechsels), `TM_SETTING` (`0xC0188F00`, das BLECH-Menü schreibt
  es in den Zustand von TAP Motion) und `BLECH_MFX` (`0xC01D6E1C`, MFX 2 liest die Einstellung aus dem Menüzustand der Plugin-Laufzeit).

Der Block von Blechy bei `0xC0184000` steht nicht in `ram`: er gehört zu den geschriebenen Bytes der Datei (`changes`), die Laufzeit liest ihn nur.

Nicht angegeben wird, was ein Patch in Objekten der Firmware beschreibt, die ihm nicht gehören: der Display-Puffer,
der Ring zum Bedienfeld, Merkwörter der Firmware. Das ist Sache von [Speicherbereiche](speicherbereiche.md). Flash-Orte
sind kein RAM und stehen auch nicht hier.

| Bereich | Patch | Inhalt | Größe aus |
|---|---|---|---|
| `0xC0174000` + 0x3950, `0xC0178000` + 0x3950 | preset-tables | Platz für je 28 weitere Preset-Records (Insert, Master), vom Editor beschrieben | `preset_tables.py:RES_IFX`, `RES_MFX` |
| `0xC017C400` + 0x800 | preset-tables | Reglergedächtnis des Insert-Effekts, 16 Parts zu 128 Byte, die Firmware füllt es beim Start | `preset_tables.py:EDIT_TABLE` |
| `0xC0180F00` + 0x40 | pattern-switch | Zustand, darin `PS_SETTING` bei +0x10 | `pattern_switch.py:STATE` |
| `0xC0173000` + 762 | pattern-switch | Puffer der Sync Group: die Werte, die ein Patternwechsel in der Gruppe mitnimmt | `pattern_switch.py:SG_BUF` |
| `0xC0173400` + 0x4C | pattern-switch | die Ansicht: Kopie des Zugriffsobjekts, dessen Pattern der Block der Bank ist, die angezeigte Nummer, der Index der Info-Zeile und der Bank-Platz, den die Sync Group ins Pattern gebracht hat | `pattern_switch.py:VIEW_W` |
| `0xC0181F00` + 0x40 | load-bar | Zustand | `load_bar.py:STATE` |
| `0xC0182000` bis `0xC0183000` | splash-editor | Zustand 0x100, Datensatz 0x420, zwei Bilder zu 0x400, FatFs-Datei 0x2E0 | `splash_editor.py`, fünf Einträge |
| `0xC0183800` + 0x100 | sample-errors | Zustand (Zähler, erstes übersprungenes Sample, Grund) und die zwei Zeilen des Fensters bei +0x40 und +0x60 (der Code liegt bei `0xC0183000`, 852 Byte, als geänderte Bytes) | `sample_errors.py:STATE` |
| `0xC0188F00` + 0x40 | tap-motion | Zustand, darin `TM_SETTING` bei +0, die Lampe, die Patternnummer, der gemerkte Modus je Part und für Master FX (der Code liegt bei `0xC0188000`, 0x2B0 Byte, als geänderte Bytes) | `tap_motion.py:STATE` |
| `0xC0189F00` + 0x40 | note-assistant | Zustand, darin `NA_SETTING` bei +0, die Takte seit der letzten Note, Note und Pad, die Pads der zuletzt gespielten Note bei +0x1C (der Code liegt bei `0xC0189000`, 0x754 Byte, als geänderte Bytes) | `note_assist.py:STATE` |
| `0xC018AF00` + 0x40 | dice | Zustand, darin `DC_SETTING` bei +0, der Zustand des Zufallszahlengebers, die Töne der Tonleiter (der Code liegt bei `0xC018A000`, 0x4A4 Byte, als geänderte Bytes) | `dice.py:STATE` |
| `0xC018C400` + 0x400, `0xC018C800` + 0x400, `0xC018CC00` + 0x280 | load-bar | der Look: das Bild der Firmware, das Bild mit Look, aus dem die Display-Sendung ihre Seiten nimmt, Reiter, bis zu 12 Kästen und die Quelle der Sendung (der Code liegt bei `0xC0183900`, als geänderte Bytes) | `load_bar.py:LOOK_BACK`, `LOOK_OUT`, `LOOK_NBOX` |
| `0xC018CF00` + 0x40 | ifx-idle | Zustand: je Part die stummen Takte und ob er Punch vom Patch hat (der Code liegt bei `0xC018C000`, 0x1E4 Byte, als geänderte Bytes) | `ifx_idle.py:STATE` |
| `0xC0191000` + 0x100 | blech-sysex | Zustand: das erklärte Schreiben, die decodierte Anfrage, Antworten, die kurz sind | `blech_sysex.py:STATE` |
| `0xC0191100` bis `0xC01A0000` | blech-sysex | Puffer für Nachrichten und Antworten, bis 32768 Byte Nutzdaten, die Antwort wird von hinten im selben Puffer gepackt | `blech_sysex.py:BUF` |
| `0xC01A5C00` + 0x40, `0xC01A5D00` + 0x120 | mfx-switch | Zustand, Datensatz der Tabelle | `mfx_switch.py:STATE`, `RECBUF` |
| `0xC01AE000` + 166864 | script-runtime | Laufzeit: Kontrollblock, Ring, LED, Display, Regler, Apps | `script_hooks.py:RUNTIME`, `SCRIPT_RUNTIME_SIZE` |
| `0xC01D6C00` + 480, `0xC01D6E00` + 0x200 | script-runtime | Menüeinträge, Menüzustand mit den Einstellungspuffern | `script_hooks.py:MENU_ITEMS`, `MENU_STATE` |
| `0xC01D7000` + 131072 | script-runtime | Plugin-Pool | `script_hooks.py:POOL` |
| `0xC01F7000` + 0x1000 | script-runtime | Arbeitsbereich des Kartenladers, benutzt bis +0x500 | `script_hooks.py:CARD` |
| `0xC01F8000` + 0x7FF0 | script-runtime | Blockpuffer, die beiden Bilder des Stores liegen darin | `script_hooks.py:INPUT` |

Die Prüfung steht in `test/patch-ram.test.mjs`, die Regeln in `src/ramspans.mjs`, die freien Läufe des Abbilds in
`data/patch-ram.mjs`. Sie schlägt fehl, wenn sich in einem der beiden Builds (Hacktribe, Korgs Original) zwei Patches
in geschriebenen Bytes oder angegebenem RAM überschneiden, wenn ein Bereich in einen Patch oder in geschriebene
Bytes eines anderen ragt, wenn ein `shares` in keinem Bereich des Besitzers liegt, oder wenn ein Bereich nicht ganz
in einem freien `FF`-Lauf des Abbilds liegt (die Karte der Läufe steht oben und in
[Speicherbereiche](speicherbereiche.md)); liegt er außerhalb des Abbilds, nennt die Meldung den gesperrten Bereich
aus `data/protected.mjs`, den er trifft. Der Fall von oben ist ein eigener Test: mit den alten Adressen des
Startbild-Editors meldet die Prüfung die Überdeckung mit dem Power-Off-Bild. `applyPatches` lehnt so einen Satz
ebenfalls ab. Mit `E2_VSB` (und `E2_STOCK_VSB`) prüft ein weiterer Test, dass jeder angegebene Bereich im Abbild in
der eigenen Firmware `FF` ist; gegen Korgs Original ist das hier nicht gelaufen.

Beim Zusammentragen fiel eine zweite Überdeckung auf: die beiden Bilder des Stores (`script_store.s`) lasen bis
0x4000 Byte je Bild, das zweite lag bei `0xC01FC000` und reichte damit 16 Byte über das Ende des Blockpuffers
(`0xC01FFFF0`) in die letzten Bytes des Abbilds, die nicht uns gehören. Nur eine Datei über 0x3FF0 Byte löst das aus,
eine selbst geschriebene hat höchstens 16 + 194 * 84 Byte. Die Lesegröße ist jetzt 0x3FF0, und der Bau der
Plugin-Laufzeit bricht ab, wenn die Bilder über den Blockpuffer hinausreichen. Im Emulator ist die Änderung nicht
gelaufen (nur das Literal der Lesegröße ändert sich, zwei Bytes im Patch).

## Startablauf und warum er tabu ist

Beim Einschalten:

1. ROM-Bootloader im Chip (fest) lädt das Startprogramm aus dem Flash.
2. Startprogramm `0x000000` bis `0x005E74` lädt die Firmware.
3. Firmware startet bei `0xC0000070`.

Die Rettungswege liegen in der Firmware selbst
(`docs/messungen/2026-10-08-emulator-boot.md`):

- Panel-Austausch beim Start, `0xC0028940`; bei falscher oder fehlender
  Antwort Panel-Update mit Anzeige „00“.
- gehaltene Tasten beim Start, `0x91`, Startmodi bei `0xC002882C`.
- Update-Abfrage „SOFTWARE UPDATE / press ENTER“, wenn die Kennung bei
  Flash `0x220000` fehlt, `0xC0029D78`.

Vor allen dreien zeichnet die Firmware schon das Startbild
(`docs/messungen/2026-10-10-startphase.md`).

Eine Firmware, die vor diesen Stellen hängt, ist ohne JTAG nicht zu
retten, auch ohne dass jemand den Bootloader angefasst hat. Daraus folgen
die Regeln.

## Regeln

1. **Keine Patches in der Startphase.** Patches richten sich beim ersten
   Gebrauch ein (erstes MENU, erster Tastendruck einer Kombination), nicht
   beim Start. Ausnahmen sind nur Daten, deren Format die Karte kennt und
   prüft (zum Beispiel das Startbild als 1024 Byte in der VSB). Code, der
   ein anderes Startbild lädt, gehört nicht dazu: er liefe vor allen
   Rettungswegen.
2. **Gesperrte Bereiche** im Abbild und im Flash, die der Patcher nie
   ändert: Startprogramm, Startphase der Firmware, Panel-Austausch,
   Tastenabfrage beim Start, Update-Routine. Gemessen als alle
   Code-Blöcke, die auf einem der 17 Startwege vor Bildschirm 1 laufen,
   und alle Bytes des Abbilds, die dabei gelesen werden
   (`tools/emu/bootmap.py`, rund 153 KiB Code und 47 KiB Daten).
   Dazu das DSP-Programm (Datei `0xF9F10` bis `0x13C1B0`): der Emulator
   lädt es nicht, also sieht kein Startweg eine Änderung daran, und ein
   kaputter Block hält das Gerät vor den Rettungswegen an. `check.py`
   prüft es als `dsp_stream` Byte für Byte
   ([DSP, erster Blick](hintergrund/dsp-erster-blick.md)).
3. **Einhaken nur per Sprung oder Zeiger**, mit Notschalter am Eingang.
4. **Patches rufen vorhandene Firmware-Funktionen auf** und schreiben nie
   selbst in Hardware-Register. LEDs gehen über den LED-Manager der Firmware
   (Sollwert schreiben, `0xC00875F4` aufrufen), nicht direkt über den
   LED-Setter `0xC0028600`: nur so stimmt die Kopie des Gesendeten, die die
   Seite im Gerätemodus liest (`docs/messungen/2026-10-14-led-zustand-ram.md`).
   Ausnahme wäre nur ein späteres Boot-Menü, siehe unten.
5. **Patches schreiben nicht in den Flash**, außer über die normalen
   Speicherwege der Firmware. Kaputte gespeicherte Daten liest auch die
   Original-Firmware beim nächsten Start.
6. **DSP-Patches** sind eine eigene Klasse ohne Netz: das DSP-Programm wird
   beim Start geladen, der Notschalter erreicht es nicht, der Emulator
   prüft es nicht.

## Notschalter

- **Auslösen:** EXIT beim Einschalten halten. EXIT hat keinen eigenen
  Startmodus; die Firmware legt die gehaltenen Tasten an
  `*0xC033E6F8 + 0x18` ab und lässt sie dort stehen. Unser Code liest sie
  beim ersten Gebrauch, ohne die Startphase zu ändern. Im Emulator gemessen;
  dass EXIT am Gerät Bit 13 ist, ist ebenfalls gemessen
  (`docs/messungen/2026-10-10-rueckweg-geuebt.md`, `screen_check.py --held`
  in `tools/device/`).
- **Wirkung:** ein Merker im RAM. Jeder eingehängte Patch fragt ihn als
  Erstes ab und lässt bei gesetztem Merker nur den Original-Code laufen.
  Das Gerät verhält sich dann wie die Firmware ohne Patches, und über
  DATA UTILITY → SOFTWARE UPDATE lässt sich eine andere Firmware aufspielen.
  Am Gerät gemessen für MFX 2: der Notschalter schaltet den Code-Patch ab
  (`docs/messungen/2026-10-13-mfx-umschalter-geraet.md`).
- **Nur für diesen Start**, nichts wird gespeichert.
- **Hacktribes Befehle:** Mit BLECH antworten Hacktribes SysEx-Befehle `0x52` bis `0x57` nur nach
  EXIT beim Einschalten; Werkzeuge, die sie brauchen, laufen dann so. `0x56` (Flash schreiben)
  bleibt immer gesperrt.
- **Grenzen:** hilft nicht gegen kaputte Startdaten, DSP-Patches, kaputte
  gespeicherte Daten und Patches, die den Panel-Austausch stören (deshalb
  Regel 2). Gegen Hardwareschaden hilft Regel 4, nicht der Notschalter.

## Prüfungen vor dem Export (Pflicht)

Der Export gibt eine Datei erst heraus, wenn im Emulator:

1. die gepatchte Firmware bis zum Hauptbildschirm bootet,
2. ohne Kennung bei Flash `0x220000` die Update-Abfrage erscheint,
3. die Startmodi mit gehaltenen Tasten erreichbar sind, auch der
   Notschalter,
4. mit falscher Panel-Version der Panel-Update-Weg kommt,
5. die gepatchten Funktionen in festen Bedienabläufen ohne Assertion laufen,
6. keine Änderung in einem gesperrten Bereich liegt.

Gebaut ist davon heute: Export mit Firmware-Erkennung und Booten der Kopie
im Emulator, Bedienabläufe per Panel-Nachricht und Prüfung von
Display und RAM, gehaltene Tasten beim Start (`machine.py --held`), die
Startphase als Bereiche (`bootmap.py`) und die Punkte 1 bis 4 und 6 als
`tools/emu/check.py`, auf der Seite Patcher (siehe unten). Der Download
kommt erst nach bestandener Prüfung (`allowed` in `src/patcher.mjs`). Punkt 5
hängt am einzelnen Patch und ist teils gebaut: für den Startbild-Editor
(`splash_cases.py`), MFX 2 (`mfx_cases.py`), das BLECH-Menü (`menu_cases.py`), den Patternwechsel (`pswitch_cases.py`), den Ladebalken (`loadbar_cases.py`), die Sample-Fehler (`sample_error_cases.py`) und das Power-Off-Bild (`power_off_cases.py`),
deren Fälle `check.py` ausführt, wenn die Kopie den jeweiligen Haken trägt. Für die
Plugin-Laufzeit liegen die Fälle in `tools/emu/script_cases.py`, das `check.py`
nicht aufruft.

Ausnahme zu Regel 1, gebaut für den Startbild-Editor (Idee 35,
`docs/messungen/2026-10-10-startbild-editor.md`): ein Patch nennt unter
`startPhase` die Spans, die er im Start ersetzt, mit Begründung, und
`check.py --allow-code` lässt genau diese zu und führt sie im Ergebnis auf
(`start_phase_exceptions`). Trägt die Kopie den Start-Hook dieses Patches,
führt `check.py` zusätzlich dessen Speicher- und Notschalterfälle aus
(`tools/emu/splash_cases.py`). Punkt 5 ist für diesen einen Patch als
Bedienlauf gebaut (`splash_cases.py run`).
Ladebalken (`load-bar`) und Startbild-Editor nutzen sie für ihre Haken in der Startphase (Frage nach der Datei, Lader, Rahmen,
Karte): sie laufen alle hinter den Rettungswegen, nur der Rahmenhaken erst vom ersten Rahmen der Oberfläche an. Der
Patternwechsel braucht keine Ausnahme, kein Haken liegt vor dem Hauptbildschirm.
Dieselbe Ausnahme nutzt der MFX-2-Patch (`docs/messungen/2026-10-10-mfx-umschalter.md`) für
seinen Haken am Typ-Setter und am Bildtick: beide laufen nach den Rettungswegen, hinter dem
Notschalter, und tun im Start nur den Notschalter-Test, den Bildschirm-Test und die Abfrage, ob MFX 2 aus ist
(erst im Hauptbildschirm setzt der Tick-Haken den Touch-Pad-Startmodus Master FX); seine Fälle führt `check.py` über
`mfx_cases.py` aus.
Das Theme (`blech-theme`, reine Daten) nutzt sie für die Bitmaps der Schriften und zwei Symbole, die der Hauptbildschirm und die
Rettungsbildschirme beim Start lesen ([BLECH Theme](hintergrund/blech-theme.md)); der Notschalter hält es nicht ab, es ändert
keinen Ablauf.

## Die Seite Patcher

Gebaut in `site/app/patcher.mjs`, die Logik ohne Seite in `src/patcher.mjs`. Wer die Seite
benutzt, legt seine eigene `SYSTEM.VSB` ab; ausgeliefert wird nie eine fertige Firmware.

- **Erkennung:** Original Korg 2.02 an der SHA-256 (`1d0f0689…`, derselbe Wert, den Hacktribes
  Patch-Skript prüft; gemessen an der eigenen Datei). Eine andere Datei von Korgs Build wird abgelehnt, solange sie
  nicht schon BLECH trägt. Hacktribe 2.02 über `identify`. Ob schon BLECH drin ist, sagt `patchesPresent`
  (über die Patches, die für das Build der Datei gemacht sind): jede Änderung steht byteweise in der
  Datei (alle: "schon BLECH", einige: "teils gepatcht", beides wird nicht noch einmal gepatcht).
- **Zwei Wege beim roten Korg-Original:** die Seite bietet "BLECH direkt (kein Hacktribe-Patch nötig)" als Vorgabe an und
  "BLECH mit Hacktribe (hacktribe-2.patch selbst mitbringen)" als zweiten Weg, dazu einen Satz, was Hacktribe
  ergänzt: Filter für den Synth, zusätzliche Effekte und SysEx zum Lesen und Schreiben im RAM, das der Live-Modus des
  Editors braucht. Der erste Weg wendet die Patches auf Korgs Datei an, der zweite macht daraus erst Hacktribes
  Datei (nächster Abschnitt). Die Wahl lässt sich umstellen, solange nichts läuft.
- **Ablauf:** Die Seite liest das Set `data/patches/blech.json` und die Patches, die es nennt
  (`loadBlechSet` in `src/patcher.mjs`, keine zweite Liste), und wendet alle im Browser an: Startbild-Editor,
  MFX 2, Patternwechsel, Ladebalken, Plugin-Laufzeit, Kartenordner blechtribe, Blech-Startbild und Theme und das Power-Off-Bild. Das Ergebnis ist byteweise das von
  `apply.mjs --set data/patches/blech.json` (gemessen an der eigenen Datei und an Hacktribes 2.02-Datei,
  `test/patcher.test.mjs` mit `E2_VSB`). Dann prüft der Emulator die Kopie (`POST /check` mit `allow` und `allowCode`,
  sonst fiele jeder Patch mit Code in der Startphase durch; `allowCode` sind die `startPhase`-Spans aller Patches
  des Sets). Der Download ist erst nach
  bestandener Prüfung freigegeben; die Prüfung dauert einige Minuten.
- **Nach dem Download:** Anleitung mit dem Kartenordner des laufenden Systems. Hacktribe liest
  `KORG/hacktribe/System/SYSTEM.VSB` (gemessen, `docs/messungen/2026-10-08-firmware-rueckweg.md`),
  die originale Firmware `KORG/electribe sampler/System/SYSTEM.VSB` (Korg Release Note 2.02,
  Seite 2: Ordner [System] unter [KORG][electribe sampler]). Dazu der Notausgang EXIT beim Einschalten.
  **Kartenordner:** der Patch `blechtribe` stellt den Ordner um, nach dem Update liest das Gerät
  `KORG/blechtribe/` statt `KORG/hacktribe/`, Samples und Patterns liegen dort nicht von allein. Die Anleitung
  sagt deshalb: Karte sichern, vor dem Update `KORG/hacktribe/` (bei der Original-Firmware `KORG/electribe sampler/`)
  nach `KORG/blechtribe/` **kopieren, nicht umbenennen**, und die `SYSTEM.VSB` in den Ordner der Firmware legen, die
  jetzt läuft, nicht nach blechtribe.
- **"Ich hab angst ...":** `POST /sd/system` legt die Kopie als Update-Datei auf die virtuelle Karte
  und die Karte ein, die eigene Datei (Hacktribe) läuft im Emulator. Gemessen im Emulator:
  DATA UTILITY, SOFTWARE UPDATE zeigt "Next Version 2.02", die Datei wird also gefunden. Die anderen Kartenordner
  fasst der Dienst nicht an: wer die Dateien von `KORG/hacktribe/` in `KORG/blechtribe/` der virtuellen Karte will,
  kopiert den Ordner selbst im Dateimanager ("Öffnen" im Feld SD-Karte). Früher kopierte der Dienst selbst und bot
  einen Knopf "Ordner für BLECH übernehmen" an; beides ist entfernt.

### BLECH direkt auf Korgs Original 2.02

Gebaut und im Emulator geprüft, am Gerät offen. Belege und Zahlen: [BLECH auf Korgs Original 2.02](messungen/2026-10-14-stock-blech.md).

- **Blaues Original:** Die Seite erkennt es an der gemessenen SHA-256 und lädt
  `data/patches/blech-synth.json`. Sie bietet dafür den Synth-Satz an. Der Emulator-Test legt
  ausschließlich `SYSTEM.VSB` unter `KORG/electribe/System/` ab. Weitere VSB-Dateien dort
  verhindern den Test; sie werden nicht gelöscht. BLECH SysEx liest auf dem Synth RAM und
  Flash, seine Schreibbefehle sind gesperrt. Effekt-Editor und Live-Bearbeitung bleiben
  beim Sampler. Die vorhandenen Release-Dateien `BLECH.patch` und die Sampler-bsdiff-Dateien
  enthalten den Synth-Satz nicht.
- **Welche Patches passen:** jeder Patch trägt `builds`, die Liste der Firmware-Builds, für die er gemacht ist
  (`hacktribe`, `stock`, `synth`; ohne Angabe nur `hacktribe`). Patches mit derselben `id` sind Fassungen einer Änderung,
  je eine pro Build, und das Build der Basis wählt die Fassung (`selectFor` in `src/patch.mjs`). Hat ein Patch für das
  Build keine Fassung, wird der ganze Satz abgelehnt, nichts wird halb angewendet; es sei denn, der Patch nennt das
  Build in `notNeededOn` (es hat die Änderung schon, die Synth-Filter auf Hacktribes Build): dann wird er dort übersprungen. Startbild-Editor, MFX 2,
  Blech-Startbild und das Power-Off-Bild sind für beide Sampler-Builds markiert; ihre erwarteten Bytes stimmen in Korgs Datei
  (gemessen). Kartenordner, Preset-Tabellen, BLECH SysEx und Plugin-Laufzeit haben je eine
  Fassung pro Sampler-Build. Die Laufzeit unterscheidet das native MUTE-Objekt. Die Synth-Filter
  gibt es nur für Korgs Sampler-Build.
- **Basis erkennen:** `identifyBase` in `src/firmware.mjs`. Hacktribes Datei geht durch `identify`. Korgs Build hat die
  Tabellen nicht, nach denen `identify` sucht, es zählen die Größe, der Lauf, den nur Hacktribe füllt, und das
  Init-Pattern; die eigentliche Prüfung sind die Hashes der Bytes, die jeder Patch ersetzt. `applyPatches` fragt nicht
  mehr `identify`, sondern `identifyBase`; alles, was nicht als `stock` markiert ist, lehnt Korgs Datei weiter ab.
- **Kartenordner:** die Fassung für Korgs Build ersetzt `electribe sampler` (Fenster von 18 Byte, mit NUL) und
  `KORG/electribe sampler/` (24 Byte) durch `blechtribe` und `KORG/blechtribe/`, der Rest des Fensters wird zu
  Nullen (`data/patches/blechtribe-stock.json`, gebaut von `tools/patch/blechtribe.py`, das das Build an der Datei
  erkennt). Beide Texte liegen in beiden Builds an denselben Adressen (`0xC00A5656`, `0xC00A5678`), und kein
  32-Bit-Wort im Abbild zeigt in die Mitte eines Fensters (das Werkzeug prüft es, gemessen an beiden Dateien).
  Die Karte braucht danach `KORG/blechtribe/`, wie bei Hacktribe.
- **Patch-Datei:** der Kopf von `BLECH.patch` trägt die Fingerabdrücke für Hacktribe 2.02 wie bisher, die für Korgs
  Original stehen in der Nutzlast unter `alternates.stock` (Format bleibt 2). Gebaut wird sie mit
  `npm run build:blech-patch -- --stock <SYSTEM.VSB von Korg>` (oder `E2_STOCK_VSB`), dann liegt dazu
  `BLECH-for-1d0f0689.bsdiff` im Ordner. Eine Datei ohne `alternates` lehnt Korgs Original mit eigenem Hinweis ab.
- **Prüfung:** `check.py` läuft mit Korgs Datei als `--base` und der gepatchten Kopie als `--patched`. Was dort anders
  ist (Ladebalken über dem Startbild, Ladezeit, Statusbit am DSP-Port), steht unter "Prüfung gegen Korgs Build".
- **Was fehlt:** alles, was Hacktribe hinzufügt und BLECH nicht selbst mitbringt. Der Live-Modus des Editors braucht
  Hacktribes SysEx `0x52` bis `0x57`; das gibt es in Korgs Build nicht ([Original im Emulator](messungen/2026-10-14-stock-emulator.md)),
  mit BLECH ersetzen es BLECHs eigene Befehle, und der Effekt-Editor liest und schreibt Korgs Presets live
  ([Effekt-Editor auf Korgs Original](messungen/2026-10-15-effekt-editor-original.md)). BLECH-Menü, Plugins, MFX 2 und
  Startbild-Editor laufen im Emulator (Prüfung bestanden), am Gerät ist das offen.

### Original Korg 2.02 zu Hacktribe

Gebaut (`convertStock` in `src/patcher.mjs`, `src/bsdiff.mjs`, `src/bzip2.mjs`). Hacktribes Weg ist
`scripts/e2-firmware-patch.py` mit `patch/hacktribe-2.patch` (bsdiff4, 17,6 KB, bzip2 darin). Die README
von `bangcorrupt/hacktribe` (geprüft 2026-10-14) sagt: "Contents of `patch` directory is not open source
and is not covered by the GPL." Alles andere ist AGPL-3.0. Die Patch-Datei liegt deshalb weder in diesem
Repository noch auf der Seite, und die Seite lädt sie auch nicht selbst: wer die Seite benutzt, holt sie bei Hacktribe
(die Seite verlinkt die Datei direkt) und zieht sie auf die Seite.

Ablauf: die originale Korg 2.02 wird abgelegt, die Seite erkennt sie am Hash. Wer "BLECH mit Hacktribe" wählt,
wird nach `hacktribe-2.patch` gefragt (mit Link und dem Grund, warum sie fehlt). Dann, alles im Browser:

1. Die Datei muss mit `BSDIFF40` beginnen, darf höchstens 1 MiB groß sein (die echte hat rund 18 KB) und
   muss eine Datei von `0x200100` Byte bauen. Einen Hash der Patch-Datei nennt Hacktribe nicht, geprüft
   wird deshalb das Ergebnis.
2. bsdiff anwenden (Steuer-, Diff- und Extra-Strom, je bzip2). Den bzip2-Dekoder haben wir selbst
   geschrieben (`src/bzip2.mjs`, keine neue Abhängigkeit, Blockprüfsummen und Gesamtprüfsumme geprüft),
   ebenso das Anwenden des Patches.
3. Das Ergebnis muss `7cb4825c…` sein, der Wert in `hash/hacked-SYSTEM.VSB.sha` bei Hacktribe. Gemessen:
   dieselbe SHA-256 hat eine eigene Hacktribe-2.02-Datei aus Hacktribes Paket. Nicht gemessen
   ist die echte `hacktribe-2.patch`: sie liegt hier nicht vor. Getestet ist der Weg mit einem eigenen
   Patch von bsdiff4 (demselben Werkzeug) vom Original zur Hacktribe-Datei, lokal, 31 ms, Ergebnis-Hash
   gleich; mit eigener Datei prüfbar über `E2_STOCK_VSB` und `E2_HACKTRIBE_PATCH` in `test/patcher.test.mjs`.

Danach geht es wie bei einer Hacktribe-Datei weiter (BLECH, Prüfung, Download). Die Anleitung zeigt für
diesen Weg den Kartenordner der Original-Firmware, `KORG/electribe sampler/System/`. Die Tests nutzen
selbstgebaute Dateien (`test/fixtures/bsdiff/make.py`, Zufallsdaten, nichts von Korg oder Hacktribe).

### Prüfung gegen Korgs Build

`check.py` besteht mit Korgs Original als Basis und der gepatchten Kopie, mit leerem Flash (88 von 88) und mit dem
eigenen Flash-Abbild (89 von 89), Zahlen und Wege in [BLECH auf Korgs Original](messungen/2026-10-14-stock-blech.md).
Was bei Korgs Build anders ist und wie die Prüfung damit umgeht:

- **Das Startbild steht länger und trägt einen Ladebalken.** Mit leerem Flash von 0,07 bis 0,40 s (Hacktribe 0,07 bis
  0,21 s), mit dem eigenen Flash bis rund 5,9 s. Korgs Build lädt dabei seine Daten und zeichnet einen Balken auf die
  Seite 7, Spalten 9 bis 119 (er löscht die Pixelzeilen 61 und 62). Die Startbild-Fälle erlauben das, und nur das:
  `same_image` in `splash_cases.py` nimmt für Korgs Build Abweichungen an genau diesen Bytes an, alles andere am Bild
  muss gleich sein, und für Hacktribe ändert sich nichts. Das Bild ist also zu sehen und bleibt lange genug stehen, die
  mindestens fünf Bilder sind mit 32 und mehr Bildern weit überschritten. Ein Problem des Patches ist das nicht.
- **Die Prüfläufe warten aufs Laden** (`Machine.loading`, `finish_boot`, nur für Korgs Build), mit eigenem Flash
  rund 6 s statt 0,4 s.
- **Zwei Stellen des Emulators brauchten eine Annahme:** Statusbit 2 am DSP-Port und das einzelne Gleichlaufwort
  `0x2C` ([Emulator](emulator.md), "DSP-Portmodell"). Beide sind Modellannahmen, nicht an Hardware gemessen.
- **Die Zeitscheibe von `bootmap.py`** ist für Korgs Build 2 ms statt 20 ms, weil das Hauptbild an einer beliebigen
  Stelle des Bildticks kommt und der Lauf vor dem ersten Tick enden muss.

### Prüfung mit leerem Flash

Die Prüfung muss auch bei einem frischen Dienst ohne Flash-Datei bestehen, denn die meisten, die den
Patcher benutzen, haben keinen Flash-Abbild-Dump. Das Startbild steht nur rund 0,13 s, von 0,07 bis 0,20 s
bei einem leeren Flash und bis 0,22 s mit dem eigenen Flash (gemessen mit `splash_cases.py cases`, Bild für
Bild alle 10 ms). Feste Stichproben (0,12, 0,16 und 0,2 s) lägen bei einem leeren Flash an der Kante, das
dritte Bild wäre schon leer. Darum sehen die Fälle jedes Bild vom ersten gezeichneten Pixel bis das Display
wieder leer ist (mindestens 5 Bilder, alle müssen das erwartete Startbild sein). Das ist strenger als drei
Stichproben und hängt nicht an der Dauer. Dasselbe gilt im Neustart-Schritt von `splash_cases.py run`.

Dort kommt beim leeren Flash ein zweiter Befund dazu: die Firmware schreibt beim ersten WRITE auf einem leeren
Flash selbst eine Marke (`ULEG`, 8 Byte) nach `0x7EF000`, auch die unveränderte Firmware (gemessen); der
Schritt "nur dieser Sektor geändert" erlaubt sie, aber nur dort und nur mit genau diesem Inhalt.
Gemessen: `cases` und `run` bestehen mit leerem Flash und mit dem eigenen Flash-Abbild.

## Später möglich: Boot-Menü und Rückfall-Firmware

Geplant, nicht gebaut (im Repository gibt es dazu keinen Code). Statt Korgs erstem Befehl bei `0xC0000070`
läuft ein kleines eigenes Menü
(normal starten, Original starten, Testmodus). Eine unveränderte Firmware
liegt in einem freien Flash-Bereich und wird bei Bedarf in den RAM geladen.
Ohne Bedienung ginge es als Startzähler: drei Starts ohne Hauptbildschirm,
dann von selbst die Original-Kopie.

Preis: das Menü läuft vor Korgs Initialisierung und braucht eigene kleine
Treiber für Display, Tasten und Flash (Freetribe hat solche, AGPL). Es wird
damit der kritischste Code im Projekt: klein halten, einmal bauen, nie von
Patches ändern. Der Emulator bildet genau diese drei Schnittstellen nach.

## Was kaputtgehen kann

1. Firmware stürzt ab oder hängt im Betrieb: Neustart.
2. Geflashte Firmware startet nicht, das Gerät fragt nach einem Update:
   Korgs Original-VSB von SD (laut Hacktribe-Doku; selbst nicht
   durchgespielt, siehe [Rückweg geübt](messungen/2026-10-10-rueckweg-geuebt.md)).
3. Firmware hängt vor der Update-Abfrage: nur JTAG. Dagegen Regeln 1 bis 3
   und die Prüfungen vor dem Export.
4. Startprogramm überschrieben: nur JTAG. Der Patcher fasst es nie an.
5. Nutzerdaten im Flash beschädigt: aus Flash-Dump und SD-Backup.
6. Hardwareschaden durch Software: kein Fall bekannt, nicht
   ausgeschlossen; dagegen Regel 4.

Der Rückweg über den normalen Updateweg ist am Gerät geübt: eine Firmware aus dem Patcher
hin, das Original zurück (`docs/messungen/2026-10-10-rueckweg-geuebt.md`). Offen ist die
Rettung, wenn die laufende Firmware nicht mehr startet.

## Erste Projekte

1. **Startbild als Patch** (Idee 20): reiner Datenpatch, an ihm entstand
   das Patch-Format. Gebaut; am Gerät geflasht und gesehen
   (`docs/messungen/2026-10-10-rueckweg-geuebt.md`).
2. **SHIFT + MASTER FX** (Idee 53): Taste abfangen, LED blinken lassen,
   Touchpad-Zuordnung umschalten. Erster Code-Patch, Notschalter und
   Einhaken entstanden dabei. Gebaut (MFX 2, `data/patches/mfx-switch.json`) und
   am Gerät gemessen (`docs/messungen/2026-10-13-mfx-umschalter-geraet.md`).
3. **Dritter Effekt über alles** (Idee 53): erst DSP-Forschung, nur lesend.
   Disassembler und Ausführung einzelner DSP-Funktionen stehen, der DSP-Strom ist aus
   der VSB gezogen ([DSP, erster Blick](hintergrund/dsp-erster-blick.md)). Gemessen ist: die
   Firmware schickt von einem Master-Preset nur die Master-Stufe an den DSP. Ein
   DSP-Patch ist nicht gebaut.

## Offen

Geplant, nicht gebaut:

- Code als Quelltext, dem der Patcher einen Platz zuteilt (siehe "Patch-Format").
- Sprung und Notschalter-Abfrage vom Patcher erzeugen lassen statt vom Patch
  (siehe "Einhaken").
- DSP-Patches und eine DSP-Prüfung im Emulator.
- Boot-Menü und Rückfall-Firmware (siehe oben).
- Punkt 5 der Prüfungen vor dem Export für alle Patches, nicht nur für Startbild-Editor,
  MFX 2, BLECH-Menü, Patternwechsel und Ladebalken.

Offene Messungen:

- Gerechnete Adressen in die `FF`-Blöcke: am Gerät nur der Code von MFX 2 geprüft, der
  Rest des Blocks und mehr Bedienabläufe nicht.
- Welcher Bildschirm 28 ist, den der SHIFT-Merker beim Start freischaltet
  (`docs/messungen/2026-10-10-startphase.md`).
- Der Startbild-Editor speichert seit dem 16.10. wieder in den Flash (Sektor `0x7F0000`), nicht mehr auf die Karte; das
  Schreiben in den Flash ist am Gerät ungeprüft.
- Freier RAM für nachgeladenen Code.
- Ob die Liste der Menüseiten beim Start oder beim Öffnen gebaut wird.
- DSP: genaues Modell und der Aufbau des Master-Wegs. Das Ladeformat (Blackfin-Bootformat,
  Blöcke mit `0xAD`) ist gemessen ([DSP, erster Blick](hintergrund/dsp-erster-blick.md)).
- Die echte `hacktribe-2.patch` im Patcher: bisher nur mit einem selbstgebauten bsdiff geprüft.
- Das Lesen und Schreiben der Karte über FatFs am Gerät, ebenso Startbild-Editor,
  Plugin-Laufzeit und BLECH-Menü am Gerät.
- Die Rettung bei einer Firmware, die nicht mehr startet, und ob die Datei unter
  `KORG/electribe sampler/System/` dafür taugt.
