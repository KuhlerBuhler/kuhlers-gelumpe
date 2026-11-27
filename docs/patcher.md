# Patcher: Aufbau und Regeln

Deutsche Version | [English version](patcher.en.md)

Belege stehen in `docs/messungen/`; was nur hergeleitet ist, steht hier als solches da.

## Inhalt

- [Ziel](#ziel)
- [Der Patch-Satz](#der-patch-satz)
- [Was in der VSB steckt](#was-in-der-vsb-steckt)
- [Patch-Format](#patch-format), [Einhaken](#einhaken) und [Haken-Register](#haken-register)
- [Patch-Datei und bsdiff](#patch-datei-und-bsdiff-release-dateien)
- [Schreibregel für die Karte](#schreibregel-für-die-karte) und [Schalter des BLECH-Menüs](#schalter-des-blech-menüs)
- [Speicherorte](#speicherorte) und [RAM der Patches](#ram-der-patches)
- [Startablauf](#startablauf-und-warum-er-tabu-ist), [Regeln](#regeln) und [Notschalter](#notschalter)
- [Prüfungen vor dem Export](#prüfungen-vor-dem-export-pflicht)
- [Die Seite Patcher](#die-seite-patcher)
- [Was kaputtgehen kann](#was-kaputtgehen-kann) und [Offen](#offen)

## Ziel

Ein Werkzeug, das Änderungen an der eigenen Firmware als Patch auf eine Kopie der [VSB](glossary.md#vsb) legt, sie im Emulator prüft und als Datei zum Flashen ausgibt. Verteilt wird nur der Patch, nie Firmware: jeder wendet ihn auf seine eigene VSB an, wie bei [Hacktribe](glossary.md#hacktribe). Eigene Features kommen als Plugins auf die Karte ([Plugins](plugins.md)). Eigene Patches sollen Nutzer später selbst bauen können (geplant, siehe "Offen").

## Der Patch-Satz

"Gebaut" heißt: der Code liegt im Repository und ist im Emulator oder in Tests geprüft. Der Satz für die rote Electribe ist `data/patches/blech.json`, der für Korgs blaue Synth-Firmware 2.02 `data/patches/blech-synth.json`. Ein Satz listet Patches; jeder Patch trägt `builds` (siehe [Welche Patches passen](#welche-patches-passen)). In den Tabellen steht "rot" für die Builds `hacktribe` und `stock` (Hacktribe und Korgs rote 2.02), "blau" für `synth` (Korgs blaue 2.02). Hacktribe auf der blauen Electribe ist rote Firmware mit blauem Kopf, es gilt der rote Satz.

Am Gerät geprüft sind zwei Dinge: der Weg mit einem Datenpatch (Startbild) hin und mit dem normalen Update zurück ([Rückweg geübt](messungen/2026-10-10-rueckweg-geuebt.md)), und der MFX-2-Patch, der erste Code-Patch am Gerät, samt Notschalter ([MFX 2 am Gerät](messungen/2026-10-13-mfx-umschalter-geraet.md)). Alles andere ist im Emulator oder in Tests geprüft; Release 1.5 enthält Teile ohne Gerätetest (in der Tabelle vermerkt).

### Patches mit eigener Datei in `data/patches/`

| Patch (`id`) | Wirkung | Build | Beleg |
|---|---|---|---|
| `splash-editor`, `splash` | Startbild-Editor (SPLASH IMPORT, DRAW, RESET im BLECH-Menü); das Bild liegt im Flash-Sektor `0x7F0000`, beim Start ab dem ersten Bild; ohne gültigen Satz oder mit EXIT beim Einschalten das Bild der VSB. `splash` ist das BLECHTRIBE-Startbild. Auf blau ohne Gerätetest (1.5) | rot, blau | [Startbild-Editor](hintergrund/startbild-editor.md), [Messung blau](messungen/2026-11-13-startbild-editor-blau.md) |
| `mfx-switch` | MFX 2: ein zweiter Master-Effekt auf TOUCH SCALE, Seite MFX 2 im BLECH-Menü | rot, blau | [Messung](messungen/2026-10-13-mfx-umschalter-geraet.md) |
| `pattern-switch` | Patternwechsel erst nach Bestätigung: beim Spielen blättert das Rad nur, MENU bestätigt, EXIT nimmt zurück; Sync-Gruppen; Seite PATTERN CONFIRM | rot, blau | [Patternwechsel](hintergrund/patternwechsel.md), [Messung](messungen/2026-10-15-patternwechsel.md) |
| `tap-motion` | TAP schaltet die aufgenommene Motion Sequence des Parts an und aus, MASTER FX gehalten plus TAP die der Master-FX-Gesten; das Tap-Tempo entfällt | rot, blau | [Messung](messungen/2026-10-15-tap-motion-patch.md) |
| `note-assistant` | im KEYBOARD-Modus leuchten nach einer Note die Pads der passenden Noten rosa, im CHORD-Modus die passenden nächsten Akkorde | rot, blau | [Messung](messungen/2026-10-15-note-assistant.md) |
| `dice` | SHIFT + PART ERASE schreibt eine neue Melodie in den gewählten Part (Tonart und Tonleiter des Patterns); nur im RAM, ungespeichert bis WRITE | rot, blau | [Messung](messungen/2026-10-16-wuerfeln.md) |
| `pad-colors` | Pad-Farben (Part und Auswahl in Rot, Blau oder Pink), Power Save mit gedimmten LEDs (LED DIMMING), KNOB LEDS OFF, Poly-Steps in Pink | rot, blau | [Messung](messungen/2026-10-17-pad-farben.md) |
| `load-bar` | Ladeanimation (Blechy zieht eine Line, Prozent, "FERTIG") beim Laden der Samples, dazu der Look: mit DISPLAY INVERT ON bekommt jedes Bild der Firmware den Stil des Startbilds | rot | [Ladeanimation](hintergrund/ladeanimation.md), [Messung](messungen/2026-10-15-ladebalken.md) |
| `sample-errors` | der Lader von [`e2sSample.all`](glossary.md#e2ssampleall) überspringt ein Sample, das er nicht nehmen kann, und das Fenster nennt das erste (`Sample 371`, Grund) statt "Unknown Error." | rot | [Messung](messungen/2026-10-15-sample-fehler.md) |
| `sample-swap` | [Sample-Swap](glossary.md#sample-swap): bei großer `e2sSample.all` lädt der Start die Samples des ersten Patterns, weitere folgen von der Karte oder aus dem RAM-Cache; WAV-Import bei STOP hängt den neuen Slot auf der Karte an; der Gesamtexport bleibt bei aktivem Swap gesperrt | rot | [Messung](messungen/2026-10-26-sample-swap-bau.md), [Schutz der Daten](messungen/2026-10-30-sample-swap-schutz.md), [Hintergrund](hintergrund/sample-swap.md) |
| `script-runtime` (erzeugt, nicht im Repository) | die [Plugin-Laufzeit](glossary.md#plugin-laufzeit) mit dem BLECH-Menü und der eingebauten App [Blechy](glossary.md#blechy), siehe [Funktionen der Laufzeit](#funktionen-der-laufzeit-im-blech-menü) | rot, blau | [Plugins](plugins.md), [Skript-Laufzeit](hintergrund/skript-laufzeit.md) |
| `blechtribe` | Kartenordner `KORG/blechtribe/` statt `KORG/hacktribe/` (Hacktribe), `KORG/electribe sampler/` (Korgs rote) oder `KORG/electribe/` (Korgs blaue) | rot, blau | [Messung](messungen/2026-10-14-stock-blech.md) |
| `blech-theme` | eigene Schriften und Symbole fürs Display, reiner Datenpatch, in der Startphase freigegeben | rot, blau | [BLECHTRIBE Theme](hintergrund/blech-theme.md) |
| `preset-tables` | Platz für 128 Insert- und 128 Master-Presets statt 100; der Editor fügt Presets als Kopie hinzu | rot, blau | [Messung](messungen/2026-10-15-preset-tabellen.md) |
| `fx-catalog` (Format `gelumpe-fx-append`) | Effekte aus dem Katalog hängen sich an die Presets an | rot, blau | [Effekt-Katalog](effekt-katalog.md) |
| `synth-filters` | LPF, HPF, BPF laufen durch MS20, MG, P5, OB und Acid wie bei Hacktribe; nur Korgs rotes Build (`notNeededOn` Hacktribe) | rot (stock) | [Messung](messungen/2026-10-15-synth-filter.md) |
| `power-off` | statt "Power Off" winkt Blechy neben einer Zeile, danach geht das Bild wie eine alte Röhre aus | rot, blau | [Messung](messungen/2026-10-15-blechy-power-off.md) |
| `last-pattern` | der Start lädt das Pattern, das zuletzt gewählt war; BLECH > FEATURES > LAST PATTERN OFF | rot, blau | [Messung](messungen/2026-10-28-letztes-pattern.md) |
| `init-pattern` | DATA UTILITY > SET INIT PATTERN legt fest, was INITIALIZE PATTERN kopiert | rot, blau | [Messung](messungen/2026-10-28-init-pattern.md) |
| `stereo-pad` | ein Stereo-Sample belegt nur seinen Part; BLECH > FEATURES > STEREO 1 PAD | rot | [Messung](messungen/2026-10-29-stereo-ein-pad.md) |
| `tube-curve` | Röhrenkurve statt Korgs Soft-Clipper am Ausgang (DSP-Bootstrom); BLECH > FEATURES > TUBE und TUBE DRIVE | rot, blau | [Messung](messungen/2026-11-20-roehrenkurve.md) |
| `ht-osc` | 76 Hacktribe-Oszillatoren (DUAL, OCT, CHIP, RING, X-SAW bis VPM-SINE) auf den freien Plätzen 421 bis 496 (Anzeige 422 bis 497); nur Korgs rotes Build (`notNeededOn` Hacktribe) | rot (stock) | [Messung](messungen/2026-11-08-ht-osc-freie-plaetze.md) |
| `beat-eighth` | die Seite BEAT im Pattern Menü bekommt einen fünften Wert `8` (Achtel) | rot, blau | [Messung](messungen/2026-10-29-beat-achtel.md) |
| `touch-scale-zero` | TOUCH SCALE RANGE geht bis 0: X spielt überall den Grundton | rot, blau | [Messung](messungen/2026-10-30-touch-scale-null.md) |
| `value-popup` | eine Taste, solange nach einem Regler das Werte-Fenster steht, schließt das Fenster und tut, was sie ohne Fenster tut (vorher schluckte Korgs Firmware den Druck, MENU, WRITE und SHIFT + Taste brauchten einen zweiten); LPF, HPF, BPF lassen das Fenster stehen | rot, blau | [Werte-Fenster](hintergrund/display.md#werte-fenster-nach-einem-regler) |
| `import-slots` | der Zielwähler von DATA UTILITY > IMPORT SAMPLE läuft ab der ersten annehmbaren Nummer bis 999 | rot | [Messung](messungen/2026-11-16-import-werks-slots.md) |
| `stage2-memory` | eigener Speicher für Stufe 2 der Insert-Effekte im DSP-Programm (Korgs Stufen überschreiben sich sonst gegenseitig) | rot | [Messung](messungen/2026-11-13-stufe2-speicher.md) |
| `update-guard` | SOFTWARE UPDATE lehnt eine `SYSTEM.VSB` ab, die nicht ganz ist (eine abgebrochene Kopie würde sonst den Flash löschen) | rot, blau | [Messung](messungen/2026-11-13-update-schutz.md) |
| `blech-version` | BLECH > VERSION zeigt die Version und die Firmware, für die das Menü gebaut ist; `node tools/set-version.mjs` baut die Dateien neu | rot, blau | |
| `doom-loader` | Doom vom SD-Lader (SHIFT + TAP beim Einschalten, `KORG/blechtribe/Doom/doom.bin`); Engine und Lizenzen in `third_party/doom/` ([Lizenz](doom-lizenz.md)) | rot | [Messung](messungen/2026-10-15-doom-im-patcher.md) |
| `blech-sysex` | [BLECHTRIBE SysEx](glossary.md#blechtribe-sysex): eigene [SysEx](glossary.md#sysex)-Befehle ab `0x60` zum Lesen und Schreiben von RAM, Flash und Dateien auf der Karte (auf blau nur lesend), dazu [DEV MODE](glossary.md#dev-mode) (nicht auf blau) | rot, blau | [Messung](messungen/2026-10-15-blech-sysex.md), [DEV MODE](messungen/2026-11-14-dev-mode-sperrbereiche.md) |
| `user-samples` | eigene Samples (`Sample/e2sSample.all`) als Oszillatoren in der Gruppe `[User]` auf der blauen, dazu DATA UTILITY > IMPORT SAMPLE (Ordner wie Korgs Browser) und SAMPLE EDIT mit ONE SHOT und REVERSE; 1.5, ohne Gerätetest | blau | [Messung](messungen/2026-11-12-blau-sample-import.md) |

### Patches, die in keinem Satz stehen

| Patch | Wirkung | Build | Beleg |
|---|---|---|---|
| `usb-name` | USB-Gerätename "Electribe 3" für den Namen und die zwei Ports; Häkchen im Patcher, aus per Voreinstellung (DAW-Zuordnungen hängen am Portnamen); am Gerät offen | rot, blau | `tools/patch/usb_name.py`, `test/usb-name.test.mjs` |
| `ifx-idle` | ein Part, der 5 s stumm ist, bekommt den Insert-Effekt Punch; stellt den eigenen nicht zuverlässig zurück, deshalb in keinem Satz | rot, blau | [Messung](messungen/2026-10-18-ifx-ruht.md) |
| `lang-de` (erzeugt) | BLECH-Menü und Korgs Hauptmenüs auf Deutsch, Häkchen im Patcher | rot, blau | [Firmware-Sprache](firmware-sprache.md) |

### Funktionen der Laufzeit im BLECH-Menü

Diese Funktionen haben keinen eigenen Patch, sie sind Code der `script-runtime` (`tools/patch/script_*.s`) und im BLECH-Menü schaltbar. Mit EXIT beim Einschalten ([Notschalter](#notschalter)) sind sie aus.

| Funktion | Wirkung | Beleg |
|---|---|---|
| EXIT-Shortcuts | EXIT gehalten + WRITE speichert das Pattern, EXIT gehalten + Pad setzt den Klang eines Parts auf die Werte der Bank zurück | [Messung](messungen/2026-10-19-exit-shortcuts.md) |
| KEY PADS | KEYBOARD gehalten + Pad setzt den KEY des Patterns (chromatisch, Pads 13 bis 16 transponieren die Oktave) | [Messung](messungen/2026-11-07-key-pads-eingebaut.md) |
| FILTER TOGGLE | SHIFT + LPF, HPF oder BPF schaltet das Filter des Parts aus und mit dem letzten Typ wieder an | [Messung](messungen/2026-11-08-filter-toggle-eingebaut.md) |
| AUTO SAVE | speichert die Global-Werte und die BLECH-Einstellungen beim Verlassen der Seite bzw. des Menüs | [Messung](messungen/2026-11-09-auto-save.md) |
| BPM GLIDE | zwei Seiten (GLIDE CHAIN, GLIDE SWITCH): das Tempo gleitet zum nächsten Pattern; 1.5 | [Messung](messungen/2026-11-15-bpm-glide.md) |
| IDLE SAVE | CUSTOMIZATION > POWER SAVE > IDLE SAVE: ohne Bedienung dimmen Display-Licht und LEDs nach 2, 3 und 4 Minuten, nach 5 gehen sie aus. OFF, ON oder BATTERY ONLY (Vorgabe): mit BATTERY ONLY bleibt das Gerät am Netzteil wach, Einstecken weckt sofort. BATTERY ONLY schreibt die Einstellungen als Version 6, die BLECHTRIBE bis 1.4.8 ablehnt; 1.5 | `tools/emu/idle_save_cases.py`, [Messung](messungen/2026-11-14-energie-befunde.md) |
| ORIG | Schildchen ORIG auf jeder Seite, deren Einstellung vom gespeicherten Stand abweicht | [Messung](messungen/2026-11-11-orig-und-karte-spaeter.md) |
| Anpassung | untere LEDs (METER, COLOR, OFF), Display-Licht, Farbe schon vor dem Startbild | [Messung](messungen/2026-10-14-blech-anpassung.md) |
| Einstellungen im Flash | der Flash ist der Hauptspeicher der BLECH-Einstellungen (zwei Sektoren `0x7FD000`, `0x7FE000` im Wechsel); eine Karte mit gültiger Datei gewinnt, außer sie ist nur veraltet; bei einem Kartenwechsel fragt das Display `SAVE TO FLASH?` | [Messung](messungen/2026-11-13-einstellungen-flash.md) |
| Karte erst nach dem Start | der Wächter der Spielhilfen (`tools/patch/card_gate.py`) liest den Kartenkontakt; wer eine Karte später steckt oder tauscht, bekommt ihre Einstellungsdatei | [Messung](messungen/2026-11-11-orig-und-karte-spaeter.md), [Einstellungen](messungen/2026-11-12-karte-spaeter-einstellungen.md) |
| Ordner übernehmen | fehlt in `KORG/blechtribe` die `Sample/e2sSample.all` oder die Pattern-Sicherung, fragt das Display beim Start, ob der alte Ordner (`KORG/hacktribe`, `KORG/electribe sampler`, auf blau `KORG/electribe`) kopiert werden soll; es wird nichts gelöscht oder überschrieben | [Messung](messungen/2026-10-19-ordner-uebernehmen.md), [blau](messungen/2026-10-29-blau-ordner-uebernehmen.md), [Ordner und Sicherung](messungen/2026-11-09-blechtribe-ordner.md) |
| Patterns-Ordner (rot, 1.5, ohne Gerätetest) | EXPORT/IMPORT PATTERN und ALL PATTERN arbeiten in `KORG/blechtribe/Patterns/`; beim Start gleicht der Card-Haken `electribe_sampler_allpattern.e2sallpat` mit dem RAM ab und schreibt nur geänderte Patterns | `tools/patch/script_patterns.s` |
| Sample-Kategorie (rot) | Seite CATEGORY in SAMPLE EDIT (Kategorie 0 bis 17, gespeichert mit EXPORT ALL SAMPLE) | [Messung](messungen/2026-11-21-sample-kategorie.md) |
| TURN MONO (rot) | Seite TURN MONO in SAMPLE EDIT, nur bei Stereo-Samples: nach Korgs `Are You Sure ?` wird das Sample (L + R) / 2, die Punkte bleiben, mit EXPORT ALL SAMPLE auf die Karte; 1.5, ohne Gerätetest | [Sample-Datei](hintergrund/sample-datei.md#turn-mono-in-sample-edit-rot-und-hacktribe-ab-15) |
| ONE SHOT (rot) | Seite ONE SHOT in SAMPLE EDIT hinter PLAY LEVEL: ON stellt LOOP START auf END POINT, WRITE behält es, EXIT ohne WRITE verwirft; 1.5, ohne Gerätetest | [Sample-Datei](hintergrund/sample-datei.md#one-shot-in-sample-edit-rot-und-hacktribe-ab-15) |
| Presets von der Karte | `KORG/blechtribe/Presets/e2sFx.all` wird beim Start geprüft und in die Preset- und Modulationstabellen geladen, nie in den Flash | [Messung](messungen/2026-10-22-sammeldatei-karte.md) |
| Das Gerät vom Rechner | der Frame-Haken nimmt Befehle, die `KORG.exec` hinterlegt; Tasten, Regler, Pads und Touchpad gehen so ans Gerät, dazu der [Test-Modus](test-modus.md) | [Messung](messungen/2026-10-29-test-modus-fernsteuerung.md) |

Patternwechsel, TAP Motion, Notenassistent und Würfeln brauchen eine Karte, die seit dem Einschalten einmal da war ([Messung](messungen/2026-10-18-karte-gezogen-tap-blinkt.md)); EXIT beim Einschalten schaltet BLECHTRIBE ganz ab.

### Prüfung der Patches im Emulator

Jeder Patch mit Bedienabläufen hat eine Fallsammlung `tools/emu/<name>_cases.py` (zum Beispiel `pswitch_cases.py`, `loadbar_cases.py`, `swap_cases.py`), die `tools/emu/check.py` ausführt, wenn die Kopie den Haken des Patches trägt. Die Plugin-Laufzeit hat ihre Fälle in `tools/emu/script_cases.py`, die `check.py` nicht aufruft.

## Was in der VSB steckt

Die Electribe hat zwei Prozessoren:

- **[ARM](glossary.md#arm)** (TI AM180x): Bedienfeld (Panel-Controller an UART0), Display (SPI0), Sequencer, Menüs, MIDI, SD-Karte, Flash (SPI1).
- **[DSP](glossary.md#dsp)** (Blackfin von Analog Devices, genaues Modell offen): rechnet den Klang, also Samples, Filter, Inserts, Master-Effekt.

Die SYSTEM.VSB ist `0x200100` Byte: 256 Byte Kopf plus das 2-MiB-Abbild des ARM, mit Code, Daten (Presets, Texte, Startbild, Tabellen) und dem eingebetteten DSP-Programm ab `0xC00F9E10` (rund 270 KB), das der ARM beim Start über SPI in den DSP lädt. Zur Laufzeit schickt der ARM dem DSP nur Befehle und Werte über den Host-Port ([Messung](messungen/2026-10-09-mfx-dsp.md)). Mehr zum DSP: [DSP, erster Blick](hintergrund/dsp-erster-blick.md).

Die VSB ist unverschlüsselt. Das Build `hacktribe` setzt auf Korgs 2.02 mit Hacktribe auf; FX-Presets, Menülängen und Startbild darin dürfen vom Original abweichen. Der Editor erkennt die Firmware an Fingerabdrücken (`data/devices.mjs`, `src/firmware.mjs`).

Drei Arten von Patches:

| Art | Beispiele | Prüfbar im Emulator | Schwierigkeit |
|---|---|---|---|
| Daten | Presets, Menülängen, Startbild, Texte und Themes | ja | gering |
| ARM-Code | Tasten, Menüpunkte, LEDs, Touchpad-Routing, Bugfixes, Spiele | ja, der Emulator führt den ARM aus | mittel |
| DSP-Code | `tube-curve`, `stage2-memory`; neue Effekte oder Algorithmen | nur über das DSP-Modell der Prüfung, nicht als Klang | hoch |

## Patch-Format

Gebaut in `src/patch.mjs`, Version 1:

```json
{ "format": "gelumpe-patch", "version": 1, "id": "splash", "name": "Startbild",
  "changes": [
    { "field": "splash", "bytes": "<hex>" },
    { "file": 1712384, "bytes": "<hex>", "expect": "<SHA-256 der ersetzten Bytes>" } ] }
```

- **Feld-Änderung:** ein Feld der [Gerätekarte](geraetekarte.md), das in der Firmware liegt und beschreibbar ist, in genau seiner Breite. Die Prüfung vor dem Export erlaubt, dass es beim Start gelesen wird, denn die Karte kennt sein Format. Beispiel: das Startbild.
- **Rohe Änderung:** Datei-Offset, neue Bytes und die Prüfsumme der Bytes, die sie ersetzt. Ohne Prüfsumme oder mit falscher wird nichts angewendet. Die Original-Bytes stehen nie im Patch.
- **Kopier-Änderung** (`copy`, optional mit `over`): nimmt ihre Bytes beim Anwenden aus der eigenen VSB, die Quelle mit Prüfsumme, und schreibt `over` darüber. So kann ein Patch Firmware-Tabellen wiederverwenden, ohne eine mitzubringen.
- Abgelehnt wird auch: Änderungen im Kopf der VSB oder außerhalb, zwei Änderungen an derselben Stelle, eine Basis, die nicht die gemessene Firmware ist, und eine Kopie, die danach die Firmware-Prüfung nicht besteht.
- `startPhase`: die Spans, die ein Patch im Start ersetzt, mit Begründung (siehe [Prüfungen](#prüfungen-vor-dem-export-pflicht)).
- `ram` und `shares`: der RAM, den der Patch zur Laufzeit belegt (siehe [RAM der Patches](#ram-der-patches)).
- Code als Quelltext, dem der Patcher einen Platz zuteilt, gibt es nicht: jeder Patch setzt seine Adressen fest.

### Welche Patches passen

Jeder Patch trägt `builds`, die Liste der Firmware-Builds, für die er gemacht ist (`hacktribe`, `stock`, `synth`; ohne Angabe nur `hacktribe`). Patches mit derselben `id` sind Fassungen einer Änderung, je eine pro Build; das Build der Basis wählt die Fassung (`selectFor` in `src/patch.mjs`). Hat ein Patch für das Build keine Fassung, wird der ganze Satz abgelehnt, nichts wird halb angewendet; es sei denn, der Patch nennt das Build in `notNeededOn` (er wird dort übersprungen, weil das Build die Änderung schon hat, so bei `synth-filters` und `ht-osc` auf Hacktribe).

`identifyBase` in `src/firmware.mjs` erkennt die Basis. Hacktribes Datei geht durch `identify`. Korgs Build hat die Tabellen nicht, nach denen `identify` sucht; es zählen die Größe, der Lauf, den nur Hacktribe füllt, und das Init-Pattern. Die eigentliche Prüfung sind die Hashes der Bytes, die jeder Patch ersetzt.

## Einhaken

Ein Patch überschreibt nie Original-Code dauerhaft. Er hängt sich ein:

1. **Am Funktionsanfang:** der erste Befehl wird ein Sprung in unseren Code; der verdrängte Befehl läuft dort und danach geht es im Original weiter.
2. **An einer Aufrufstelle:** `rufe F auf` wird `rufe UNSER_CODE auf`, und unser Code ruft am Ende F.
3. **Über einen Zeiger in einer Tabelle:** Funktionszeiger der Firmware, etwa die Bildschirmklassen (vtables), gegen unseren Code tauschen. Reine Datenänderung. Das BLECH-Menü hängt sich so ein, über eine Kopie der Bildschirmtabelle ([Messung](messungen/2026-10-14-blech-menue.md)).

Die gebauten Patches nutzen Aufrufstellen, Befehle und Literale als Haken (`kind` `call`, `instruction`, `literal`). Den Sprung und die erste Abfrage ([Notschalter](#notschalter)) setzt der Code des jeweiligen Patches (`tools/patch/`), der Patcher erzeugt sie nicht.

## Haken-Register

Gebaut in `src/hooks.mjs`, die Ketten stehen in `data/hooks.mjs`. Ein Code-Patch nennt in einer optionalen Liste `hooks` jede Einhängestelle (ein Patch ohne Liste wird nicht erfasst):

```json
{ "site": "0xC00700D8", "kind": "instruction", "chain": "key-dispatch",
  "position": "before", "swallow": true, "note": "..." }
```

- `site`: RAM-Adresse des geänderten Worts. `kind`: `call` (Aufruf ersetzt), `vtable-slot`, `literal`, `instruction`.
- `chain`: die benannte Aufrufkette, die der Haken abfängt (ein Name oder eine Liste), etwa `start`, `key-dispatch`, `pattern-set`, `frame`, `global-screen`. Die Tabelle ordnet jeder Kette ihre Stufen vom Eingang abwärts; eine Stelle, die dort fehlt, wird abgelehnt. Die Kette `start` kennt zwei Stufen für die Karte (`card-mount` und `sample-load`), die Kette `frame` eine für das Senden des Rahmens (`display-flush`).
- `position`: `before`, `after` oder `replace` gegenüber dem Original. `swallow`: ob der Haken das Ereignis davon abhalten kann, das Original und die Stufen dahinter zu erreichen.

`applyPatches` prüft die Haken aller Patches vor dem Schreiben:

| Fall | Folge |
|---|---|
| zwei Patches (oder ein Patch zweimal) auf derselben Stelle | abgelehnt |
| zwei Patches auf derselben Stufe einer Kette, einer ersetzt | abgelehnt |
| Stelle oder Kette unbekannt, Angabe fehlerhaft | abgelehnt |
| bekanntes Paar in `INCOMPATIBLE` | abgelehnt, mit einer Meldung statt einer je Stelle |
| ein Haken, der verschlucken kann, liegt vor dem Haken eines anderen Patches in derselben Kette | angewendet, als Abhängigkeit in `dependencies` gemeldet |

Stufen mit mehreren Stellen prüft die Tabelle bewusst grob: alle Wege einer Patternwahl enden in `set_number`, die drei Einstiege (Rad, Pad, MIDI) sind eine Stufe, `set_number` selbst die nächste.

## Patch-Datei und bsdiff (Release-Dateien)

Zum Release gehören zwei Arten von Dateien, die aus dem Patch-Satz `data/patches/blech.json` und einer VSB gebaut werden. Sie kommen nach `dist-release/` (gitignored) und werden nie eingecheckt. Als Eingabe dient die `SYSTEM.VSB` aus Hacktribes Paket (`hacktribe-es2-sd-package.zip`; sha256 `7cb4825c...`), denn nur an diese passt das [bsdiff](glossary.md#bsdiff):

```bash
E2_VSB="<SYSTEM.VSB aus dem Paket>" npm run build:blech-patch
npm run build:blech-patch -- --vsb <SYSTEM.VSB> --version 1.0.1
```

| Datei | Wofür | Anwenden |
|---|---|---|
| `BLECH.patch` | der ganze Satz in unserem Format: alle Patches mit Haken, Prüfsummen und Startphase-Ausnahmen. Passt mit `--stock` auf Korgs rote 2.02, mit `--synth` auf Korgs blaue 2.02 (eigene Fingerabdrücke, die blaue mit ihrem eigenen Satz `blech-synth.json`) und ohne Schalter auf jede Hacktribe 2.02, deren Code und feste Daten stimmen, auch mit dem Kopf der blauen. Das Release baut sie mit allen drei Dateien | `node tools/patch/apply.mjs --vsb SYSTEM.VSB --patch BLECH.patch --out BLECH.VSB`, oder `applyPatchFile` in `src/patchfile.mjs` |
| `BLECH-for-7cb4825c.bsdiff`, `BLECH-for-2b2e1c2f.bsdiff` (Hacktribe mit blauem Kopf), mit `--stock` `BLECH-for-1d0f0689.bsdiff`, mit `--synth` `BLECH-for-41fc5f1c.bsdiff` | genau diese Datei zu BLECHTRIBE als bsdiff 4 (`BSDIFF40`, wie Hacktribes Patch). Der Name trägt den Anfang des sha256 der Eingabe. Die für `2b2e1c2f` gibt die Kopie mit dem Kopf des Samplers, den Hacktribe auf der blauen beim Update nimmt | `bspatch SYSTEM.VSB BLECH.VSB BLECH-for-7cb4825c.bsdiff`, ohne unsere App, nur mit der Datei mit diesem Hash |

**Welche VSB passt.** Hacktribes Datei und eine bearbeitete VSB unterscheiden sich nur in Daten, die Nutzer ändern: FX-Presets, die Menülängen (14 einzelne Bytes in Code-Literalen) und das Startbild, an einer eigenen Datei gemessen 2317 Byte in 1331 Folgen, kein Code, kein DSP-Programm. `BLECH.patch` prüft deshalb nicht die ganze Datei, sondern einen **Fingerabdruck**: sha256 über alle Bytes außer den `userData`-Bereichen (FX-Tabellen, Groove- und Modulationstabelle, Startbild, Menülängen; aus der Gerätekarte abgeleitet, `userDataRanges()`). Jede Änderung des Patches prüft außerdem einzeln die Bytes, die sie ersetzt (`expect`). Der Fingerabdruck der Ausgabe lässt nur die `userData`-Bytes aus, die der Patch nicht schreibt, prüft also auch, was der Patch geschrieben hat.

**Format von `BLECH.patch`** (Version 2, Zahlen little endian): Kopf mit 128 Byte, dann der Inhalt als JSON.

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

Die `patches` sind dieselben Objekte, die `applyPatches` aus den JSON-Dateien bekommt, in derselben Reihenfolge. Die Datei anwenden heißt: Fingerabdruck der Eingabe prüfen, `applyPatches`, Fingerabdruck der Ausgabe prüfen. Weicht eins ab, wird nichts geschrieben; das Ergebnis ist Byte für Byte das des Satzes (`test/patch-file.test.mjs`). `--patch BLECH.patch` steht allein, nicht zusammen mit JSON-Patches.

Die Fingerabdrücke im Kopf gelten für Hacktribe 2.02. Die der anderen Firmwares stehen in der Nutzlast unter `alternates` (das Format bleibt 2): `stock` für Korgs rote, `hacktribe-blue` für Hacktribe mit dem Kopf der blauen, `synth` für Korgs blaue, dort mit eigener Patchliste. Andere Schlüssel lehnt die Seite ab; eine Datei ohne den passenden Schlüssel lehnt die Firmware mit eigenem Hinweis ab.

**Keine Firmware in der Datei**, nur was die JSON-Patches schon tragen: unseren Code und unsere Daten, die Hashes der Bytes, die sie ersetzen (Hashes nennen Bytes, sie enthalten sie nicht), Quelladressen der `copy`-Änderungen (Adressen, keine Bytes) und an einzelnen Haken das verdrängte Befehlswort (4 Byte), das unser Code nachspielt.

**Keine Firmware in dem bsdiff:** `tools/patch/bsdiff.mjs` sucht die Übereinstimmungen nicht, es kennt die Änderungen. Was die Patches nicht anfassen, ist ein Treffer an gleicher Stelle, eine `copy`-Änderung ein Treffer an der Quelladresse, alles andere steht als Literal im Extra-Block. Klassisches bsdiff würde ein kopiertes Stück als Differenz zur Zielstelle speichern, und das wäre Firmware. Hier ist der Diff-Block nur Nullen. Gemessen an der Paket-VSB: Diff-Block 2.073.917 Byte, alle null; Extra-Block 23.491 Byte, das sind Bytes der Patches; die längste Folge im Extra-Block, die auch in der Original-VSB steht und mehr als drei verschiedene Bytewerte hat, ist 18 Byte lang (zufällig gleiche Befehlsworte). `bspatch` (macOS) liefert dieselben Bytes wie der Satz. Der Steuerblock verrät Quelladressen der Kopien, keine Bytes. Gebaut wird mit dem Programm `bzip2`.

## Schreibregel für die Karte

Gilt für alles, was die Plugin-Laufzeit auf die Karte schreibt (`korg.store`, `tools/patch/script_store.s`). Code eines Patches greift auf die Karte nur über die Datei-Funktionen der Firmware zu (`f_open`, `f_read`, `f_write`, `f_close`, Adressen in [Virtuelle SD](hintergrund/virtuelle-sd.md)), nie über den SD-Controller selbst. [FatFs](glossary.md#fatfs) hat keine Sperre, deshalb:

1. Lesen nur beim Start, hinter dem Laden der `e2sSample.all` und mit EXIT noch nicht gehalten. Schreiben nur im Rahmenhaken (UiTask) bei offenem Hauptbildschirm, also nie während DATA UTILITY, Sample-Laden oder einer anderen Kartenbedienung der Firmware.
2. Geschrieben wird nur auf eine ausdrückliche Anforderung (`korg.store.save()`), mit mindestens 50 Rahmen (2 Sekunden) Pause zwischen zwei Schreibvorgängen.
3. Eine Datei wird ganz in einem Vorgang geschrieben und nie ersetzt: zwei Dateien wechseln sich mit einer Generationsnummer und einer CRC-32 ab, so bleibt bei einem Abbruch (Strom, Karte gezogen) die vorige Generation lesbar.
4. Ein Fehlschlag wird gezählt und nicht wiederholt, die Firmware läuft weiter.
5. Keine Datei wird gelöscht oder umbenannt. Ordner legt nur der Start an: `KORG/blechtribe` und die Unterordner, die BLECHTRIBE darin braucht, soweit sie fehlen ([Messung](messungen/2026-11-09-unterordner-rote-sicherung.md)).

Ausnahmen:

- **Ordner übernehmen** (`tools/patch/script_migrate.s`, [Messung](messungen/2026-10-19-ordner-uebernehmen.md)): nur auf MENU kopiert sie den alten Ordner nach `KORG/blechtribe`, vor dem Sample-Lader und im selben Ablauf, also ohne gleichzeitigen Kartenzugriff der Firmware. Eine Datei, die schon da ist, bleibt; der alte Ordner bleibt.
- **Startbild-Editor** (Flash, siehe [Startbild-Editor](hintergrund/startbild-editor.md)): schreibt in den Flash, nicht auf die Karte.
- **BLECH-Menü** ([Messung](messungen/2026-10-14-blech-menue.md)): schreibt nur auf WRITE des Nutzers (`settings.a/b.bin` nach Regel 3, `e2sPlugin.all` in einem Vorgang) und liest die Dateiliste und `*.blech` beim Öffnen der Liste von MANAGE PLUGINS und die Beschreibung eines Plugins beim Öffnen seiner Seite DESCRIPTION, jeweils im UiTask bei offenem Menübildschirm. Dann ist weder DATA UTILITY noch Sample-Laden offen: die Seiten von BLECHTRIBE, die in DATA UTILITY stehen (EXPORT ALL PLUGINS), sind der Menübildschirm, die Funktionsliste der Firmware ist dabei geschlossen.

Belege und Grenzen: [Messung](messungen/2026-10-14-skript-speicher.md). Am Gerät ist das Schreiben über FatFs noch nicht geprüft.

## Schalter des BLECH-Menüs

Spielhilfen, die an der Karte hängen (Patternwechsel, TAP Motion, Notenassistent, Würfeln), liest der Patch aus einem Einstellungswort im RAM, das das BLECH-Menü schreibt (`PS_SETTING` und so weiter, definiert in den Werkzeugen `tools/patch/pattern_switch.py`, `tap_motion.py`, `note_assist.py`). Der Vertrag:

- Das Wort ist `0xFFFFFFFF` (nie geschrieben) oder 1 für an, 0 für aus. Der Patch liest es bei jedem Haken.
- In der Einstellungsdatei (`settings.a/b.bin`) steht der Schalter als Bit der Flags, **gesetzt heißt aus**. So bleibt jede bestehende Datei "an", und ein älterer Leser ignoriert das Bit.
- Das Menü schreibt das Wort beim Laden der Datei und bei jedem Umschalten. Fehlt die Datei oder ist sie ungültig, schreibt es nichts.
- Wird das Wort zur Laufzeit auf 0 gestellt, nimmt der Patch seine Hinweise sofort zurück (der Notenassistent innerhalb von 0,3 s von den Pads, gemessen).

Der Ladebalken und das eigene Startbild brauchen keinen Schalter: der Balken erscheint nur, wenn eine `e2sSample.all` da ist und EXIT beim Einschalten nicht gehalten wird, das eigene Startbild nur, wenn ein gültiger Satz im Flash steht.

## Speicherorte

Die Datei bleibt immer `0x200100` Byte groß: im Flash liegt die Firmware in `0x020000` bis `0x220000`, dahinter beginnen die Nutzerdaten. Eigener Code und Daten der Patches liegen in den `FF`-Blöcken des Abbilds, die die Firmware nie benutzt; die Karte der freien Läufe, des Flash und der gesperrten Bereiche steht in [Speicherbereiche](speicherbereiche.md). Mehr Platz gibt es nur zur Laufzeit, durch Nachladen aus Flash oder SD in freien RAM.

Code aus dem Flash oder von der SD muss die Firmware laden und anspringen. Für den Rettungsweg bringt ein Ort außerhalb des Abbilds deshalb nichts. Am Gerät ist nur der Code von MFX 2 an einer berechneten Adresse geprüft; der Rest der `FF`-Blöcke ist am Gerät ungeprüft (offen).

## RAM der Patches

Der Patcher prüft Änderungen an der Datei: zwei Patches, die dieselben Bytes schreiben, werden abgelehnt. Was ein Patch zur Laufzeit zusätzlich im RAM belegt (Zustandswörter, Puffer, Dateipuffer, Pool, Menüzustand), steht nicht in der Datei. Deshalb nennt jeder Patch diesen RAM neben `changes` (alle Patches des Satzes tun es, ein Test hält das; die Felder sind in `src/patch.mjs` beschrieben):

- `ram`: Speicher des Patches selbst, je Eintrag `at`, `length`, `what` und `source`. `source` sagt, woher die Größe kommt, `<Datei>:<SYMBOL>` im Werkzeug, das den Patch baut. Die Werkzeuge schreiben die Einträge aus ihren eigenen Konstanten, sie stehen nicht zweimal da. Ein Patch ohne eigenen RAM schreibt `"ram": []`.
- `shares`: ein Wort im Bereich eines anderen Patches, das dieser liest oder schreibt (`with` ist die Id des Besitzers). Es muss ganz in einem Bereich liegen, den der Besitzer in `ram` nennt; fehlt der Besitzer, weil der Patch auch allein angewendet wird, bleibt es nur fern von fremden Bereichen und geschriebenen Bytes. Heute teilen `mfx-switch` (liest die MFX-2-Einstellung) und `load-bar` (liest, ob das BLECH-Menü scharf ist, und DISPLAY INVERT) Wörter aus dem Menüzustand der `script-runtime`.

Der Block von Blechy bei `0xC0184000` steht nicht in `ram`: er gehört zu den geschriebenen Bytes der Datei (`changes`), die Laufzeit liest ihn nur. Nicht angegeben wird, was ein Patch in Objekten der Firmware beschreibt, die ihm nicht gehören (Display-Puffer, Ring zum Bedienfeld, Merkwörter der Firmware): das ist Sache von [Speicherbereiche](speicherbereiche.md). Flash-Orte sind kein RAM.

Die Prüfung steht in `test/patch-ram.test.mjs`, die Regeln in `src/ramspans.mjs`, die freien Läufe des Abbilds in `data/patch-ram.mjs`. Sie schlägt fehl, wenn sich in einem der beiden Builds (Hacktribe, Korgs Original) zwei Patches in geschriebenen Bytes oder angegebenem RAM überschneiden, wenn ein Bereich in einen Patch oder in geschriebene Bytes eines anderen ragt, wenn ein `shares` in keinem Bereich des Besitzers liegt, oder wenn ein Bereich nicht ganz in einem freien `FF`-Lauf des Abbilds liegt; liegt er außerhalb des Abbilds, nennt die Meldung den gesperrten Bereich aus `data/protected.mjs`, den er trifft. `applyPatches` lehnt so einen Satz ebenfalls ab. Mit `E2_VSB` (und `E2_STOCK_VSB`) prüft ein weiterer Test, dass jeder angegebene Bereich im Abbild in der eigenen Firmware `FF` ist.

## Startablauf und warum er tabu ist

Beim Einschalten:

1. ROM-Bootloader im Chip (fest) lädt das Startprogramm aus dem Flash.
2. Startprogramm `0x000000` bis `0x005E74` lädt die Firmware.
3. Firmware startet bei `0xC0000070`.

Die Rettungswege liegen in der Firmware selbst ([Messung](messungen/2026-10-08-emulator-boot.md)):

- Panel-Austausch beim Start, `0xC0028940`; bei falscher oder fehlender Antwort Panel-Update mit Anzeige "00".
- gehaltene Tasten beim Start, `0x91`, Startmodi bei `0xC002882C`.
- Update-Abfrage "SOFTWARE UPDATE / press ENTER", wenn die Kennung bei Flash `0x220000` fehlt, `0xC0029D78`.

Vor allen dreien zeichnet die Firmware schon das Startbild ([Messung](messungen/2026-10-10-startphase.md)). Eine Firmware, die vor diesen Stellen hängt, ist ohne [JTAG](glossary.md#jtag) nicht zu retten, auch ohne dass jemand den Bootloader angefasst hat. Daraus folgen die Regeln.

## Regeln

1. **Keine Patches in der [Startphase](glossary.md#startphase).** Patches richten sich beim ersten Gebrauch ein (erstes MENU, erster Tastendruck einer Kombination), nicht beim Start. Ausnahmen sind Daten, deren Format die Karte kennt und prüft (zum Beispiel das Startbild als 1024 Byte in der VSB), und die Spans, die ein Patch unter `startPhase` mit Begründung nennt (siehe [Prüfungen](#prüfungen-vor-dem-export-pflicht)). Code, der ein anderes Startbild lädt, gehört nicht dazu: er liefe vor allen Rettungswegen.
2. **Gesperrte Bereiche** im Abbild und im Flash, die der Patcher nie ändert: Startprogramm, Startphase der Firmware, Panel-Austausch, Tastenabfrage beim Start, Update-Routine. Gemessen als alle Code-Blöcke, die auf einem der 17 Startwege vor Bildschirm 1 laufen, und alle Bytes des Abbilds, die dabei gelesen werden (`tools/emu/bootmap.py`, rund 153 KiB Code und 47 KiB Daten; Liste in `data/protected.mjs`). Dazu das DSP-Programm (Datei `0xF9F10` bis `0x13C1B0`): der Emulator lädt es nicht, also sieht kein Startweg eine Änderung daran, und ein kaputter Block hält das Gerät vor den Rettungswegen an. `check.py` prüft es als `dsp_stream` Byte für Byte ([DSP, erster Blick](hintergrund/dsp-erster-blick.md)).
3. **Einhaken nur per Sprung oder Zeiger**, mit Notschalter am Eingang.
4. **Patches rufen vorhandene Firmware-Funktionen auf** und schreiben nie selbst in Hardware-Register. LEDs gehen über den LED-Manager der Firmware (Sollwert schreiben, `0xC00875F4` aufrufen), nicht direkt über den LED-Setter `0xC0028600`: nur so stimmt die Kopie des Gesendeten, die die Seite im Gerätemodus liest ([Messung](messungen/2026-10-14-led-zustand-ram.md)).
5. **Patches schreiben nicht in den Flash**, außer über die normalen Speicherwege der Firmware (und den Startbild-Editor, der seinen eigenen Sektor schreibt). Kaputte gespeicherte Daten liest auch die Original-Firmware beim nächsten Start.
6. **DSP-Patches** sind eine eigene Klasse ohne Netz: das DSP-Programm wird beim Start geladen, der Notschalter erreicht es nicht, der Emulator spielt keinen Klang.

## Notschalter

- **Auslösen:** EXIT beim Einschalten halten. EXIT hat keinen eigenen Startmodus; die Firmware legt die gehaltenen Tasten an `*0xC033E6F8 + 0x18` ab und lässt sie dort stehen. Unser Code liest sie beim ersten Gebrauch, ohne die Startphase zu ändern. Im Emulator gemessen; dass EXIT am Gerät Bit 13 ist, ist ebenfalls gemessen ([Messung](messungen/2026-10-10-rueckweg-geuebt.md), `screen_check.py --held` in `tools/device/`).
- **Wirkung:** ein Merker im RAM. Jeder eingehängte Patch fragt ihn als Erstes ab und lässt bei gesetztem Merker nur den Original-Code laufen. Das Gerät verhält sich dann wie die Firmware ohne Patches, und über DATA UTILITY, SOFTWARE UPDATE lässt sich eine andere Firmware aufspielen. Am Gerät gemessen für MFX 2 ([Messung](messungen/2026-10-13-mfx-umschalter-geraet.md)).
- **Nur für diesen Start**, nichts wird gespeichert.
- **Hacktribes Befehle:** Mit BLECHTRIBE antworten Hacktribes SysEx-Befehle `0x52` bis `0x57` nur nach EXIT beim Einschalten; Werkzeuge, die sie brauchen, laufen dann so. `0x56` (Flash schreiben) bleibt immer gesperrt.
- **Grenzen:** hilft nicht gegen kaputte Startdaten, DSP-Patches, kaputte gespeicherte Daten und Patches, die den Panel-Austausch stören (deshalb Regel 2). Gegen Hardwareschaden hilft Regel 4, nicht der Notschalter.

## Prüfungen vor dem Export (Pflicht)

Der Export gibt eine Datei erst heraus, wenn im Emulator:

1. die gepatchte Firmware bis zum Hauptbildschirm bootet,
2. ohne Kennung bei Flash `0x220000` die Update-Abfrage erscheint,
3. die Startmodi mit gehaltenen Tasten erreichbar sind, auch der Notschalter,
4. mit falscher Panel-Version der Panel-Update-Weg kommt,
5. die gepatchten Funktionen in festen Bedienabläufen ohne Assertion laufen,
6. keine Änderung in einem gesperrten Bereich liegt,
7. die Schnittstelle zum DSP hält: der Start lädt jedem Part und dem Master einen Effekt, kein Feld bleibt stumm, kein Part aus, Pad 1 und das Pattern öffnen und schließen Stimmen, jede Übertragung an den DSP ist vollständig.

Die Punkte 1 bis 4 und 6 sind `tools/emu/check.py` (Startphase als Bereiche aus `bootmap.py`, gehaltene Tasten beim Start über `machine.py --held`). Punkt 7 ist `tools/emu/dsp_cases.py` mit dem DSP-Modell (`tools/emu/dsp_model.py`); er läuft bei jeder Kopie mit, auch in der Kurzprüfung, weil er für jede Firmware gilt ([Messung](messungen/2026-11-12-dsp-modell.md)). Punkt 5 hängt am einzelnen Patch: seine Fälle (`tools/emu/*_cases.py`) führt `check.py` aus, wenn die Kopie den Haken trägt (siehe [Prüfung der Patches im Emulator](#prüfung-der-patches-im-emulator)); für einige Patches fehlen sie noch. Der Download kommt erst nach bestandener Prüfung (`allowed` in `src/patcher.mjs`).

**Ausnahme zu Regel 1 (`startPhase`).** Ein Patch nennt unter `startPhase` die Spans, die er im Start ersetzt, mit Begründung. `check.py --allow-code` lässt genau diese zu und führt sie im Ergebnis auf (`start_phase_exceptions`). Trägt die Kopie den Start-Hook dieses Patches, führt `check.py` zusätzlich dessen Speicher- und Notschalterfälle aus. Genutzt wird das vom Startbild-Editor ([Messung](messungen/2026-10-10-startbild-editor.md)) und von der Ladeanimation (Frage nach der Datei, Lader, Rahmen, Karte): ihre Haken laufen alle hinter den Rettungswegen, nur der Rahmenhaken erst vom ersten Rahmen der Oberfläche an. MFX 2 nutzt sie für den Haken am Typ-Setter und am Bildtick ([Messung](messungen/2026-10-10-mfx-umschalter.md)): beide laufen hinter dem Notschalter und tun im Start nur den Notschalter-Test, den Bildschirm-Test und die Abfrage, ob MFX 2 aus ist. Das Theme (`blech-theme`, reine Daten) nutzt sie für die Bitmaps der Schriften und zwei Symbole, die der Hauptbildschirm und die Rettungsbildschirme beim Start lesen ([BLECHTRIBE Theme](hintergrund/blech-theme.md)). Der Patternwechsel braucht keine Ausnahme: kein Haken liegt vor dem Hauptbildschirm.

## Die Seite Patcher

Gebaut in `site/app/patcher.mjs`, die Logik ohne Seite in `src/patcher.mjs`. Wer die Seite benutzt, legt seine eigene `SYSTEM.VSB` ab; ausgeliefert wird nie eine fertige Firmware.

### Ablauf

- **Start:** zwei Fragen vor den vier Schritten. Erst "Welche Electribe hast du?" mit vier Karten: blau, rot, blau mit Hacktribe, rot mit Hacktribe. Dann "Was willst du?": BLECHTRIBE, BLECHTRIBE + Hacktribe oder Nur Update; wer Hacktribe schon hat, bekommt nur BLECHTRIBE und Update. Danach zeigt Schritt 1 nur, was dieser Weg braucht: beim Update das Lesen über USB und das Feld für die Datei von der Karte, sonst Korgs Datei für die passende Electribe (für Hacktribe immer die rote) und das Feld. Ein Gerät am Kabel geht vor. Wer gleich eine Datei ablegt, überspringt die Fragen. Jeder Schritt hat Zurück.
- **Erkennung:** Original Korg 2.02 an der SHA-256 (`1d0f0689...`, derselbe Wert, den Hacktribes Patch-Skript prüft). Eine andere Datei von Korgs Build wird abgelehnt, solange sie nicht schon BLECHTRIBE trägt. Hacktribe 2.02 über `identify`. Ob schon BLECHTRIBE drin ist, sagt `patchesPresent` (über die Patches, die für das Build der Datei gemacht sind): jede Änderung steht byteweise in der Datei (alle: "schon BLECHTRIBE", einige: "teils gepatcht", beides wird nicht noch einmal gepatcht).
- **Anwenden:** die Seite liest das Set `data/patches/blech.json` und die Patches, die es nennt (`loadBlechSet` in `src/patcher.mjs`, keine zweite Liste), und wendet alle im Browser an. Das Ergebnis ist byteweise das von `apply.mjs --set data/patches/blech.json` (`test/patcher.test.mjs` mit `E2_VSB`).
- **Prüfen:** der Emulator prüft die Kopie (`POST /check` mit `allow` und `allowCode`; `allowCode` sind die `startPhase`-Spans aller Patches des Sets). Der Download ist erst nach bestandener Prüfung freigegeben.
- **Gerätename:** ein Häkchen in Schritt 2 legt den Patch `usb-name` dazu (`USB_NAME_URLS`), auch auf eine mitgebrachte `BLECH.patch`. Aus per Voreinstellung. Ein anderes Häkchen macht eine neue Kopie, die alte Prüfung gilt dann nicht mehr.
- **Sprache:** das Häkchen "Gerätemenüs auf Deutsch" legt den Patch `lang-de` dazu (`LANG_DE_URLS`), aus per Voreinstellung. Ein Update behält die Sprache der Datei. Deutsch gibt es nur über die App, die Dateien der Release-Seite sind Englisch ([Firmware-Sprache](firmware-sprache.md)).

### Prüfumfang

Drei Stufen in Schritt 2 (`site/app/patcher.mjs`): **Kurzprüfung** (Vorgabe), **Voller Test** und **Kein Test** (nur mit Häkchen, dass der Nutzer die Folgen kennt).

- **Geprüfte Kopien:** dieselbe Eingabe mit demselben Patch-Satz ergibt dieselbe Datei und dieselben Starts. Steht die SHA-256 von Eingabe und Ergebnis in `data/patches/verified.json` (gebaut mit `tools/verify-patches.mjs`; Korgs rote und blaue 2.02, Hacktribe 2.02 und Hacktribe für die blaue, diese mit `"hardware": "blue"`), entfällt die Prüfung im Emulator (`verifiedReport` in `src/patcher.mjs`).
- **Kurzprüfung:** eine Kopie, die nicht in der Liste steht, prüft der Patcher nur auf Start und Rettungswege (normaler Start, Update-Abfrage, Panel-Update, Startmodi, EXIT, DSP einmal, Startphase), `check.py --quick`, auf dem Mac 14 s. Die Tests der einzelnen Patches laufen nur mit "Voller Test" (mehrere Minuten), denn sie prüfen unseren Code, der in jeder Datei derselbe ist.

### Speichern und danach

- **Speichern:** in der App sucht Schritt 4 alle 2 s die eingesteckte Karte (macOS `/Volumes/*`, Windows die Laufwerksbuchstaben, Linux `/media/$USER/*` und `/run/media/$USER/*`) mit dem KORG-Ordner des Ziels, zeigt den vollen Pfad und schreibt mit "Speichern" nur dorthin, legt `System/` an, wenn es fehlt, und sagt vorher, wenn eine SYSTEM.VSB ersetzt wird; passen mehrere Karten, wählt man eine (`src-tauri/src/save.rs`, `site/app/save-target.mjs`). Daneben bleibt der Speichern-Dialog der App. Im Browser der Speichern-Dialog (`showSaveFilePicker`), wo es ihn gibt, sonst der Download.
- **Nach dem Speichern:** die Anleitung nennt den Kartenordner des laufenden Systems. Hacktribe liest `KORG/hacktribe/System/SYSTEM.VSB` ([Messung](messungen/2026-10-08-firmware-rueckweg.md)), die originale Firmware `KORG/electribe sampler/System/SYSTEM.VSB` (Korg Release Note 2.02, Seite 2). Dazu der Notschalter.
- **Kartenordner:** der Patch `blechtribe` stellt den Ordner um: nach dem Update liest das Gerät `KORG/blechtribe/` statt `KORG/hacktribe/`; Samples und Patterns liegen dort nicht von allein. Die Anleitung sagt deshalb: Karte sichern, vor dem Update `KORG/hacktribe/` (bei der Original-Firmware `KORG/electribe sampler/`) nach `KORG/blechtribe/` **kopieren, nicht umbenennen**, und die `SYSTEM.VSB` in den Ordner der Firmware legen, die jetzt läuft. Läuft bereits BLECH mit dem umgestellten Ordner, liegt der Updatepfad unter `KORG/blechtribe/System/SYSTEM.VSB` (auf dem untersuchten Hacktribe-Gerät durch gelesene Pfadtexte und unveränderten nativen Updatecode belegt, [Vorprüfung](messungen/2026-11-06-sample-ram-vorpruefung.md)).
- **"Ich hab Angst, dass mein Gerät kaputt geht":** `POST /sd/system` legt die Kopie als Update-Datei auf die virtuelle Karte und die Karte ein, die eigene Datei (Hacktribe) läuft im Emulator. Im Emulator zeigt DATA UTILITY, SOFTWARE UPDATE "Next Version 2.02", die Datei wird also gefunden. Die anderen Kartenordner fasst der Dienst nicht an: wer die Dateien von `KORG/hacktribe/` in `KORG/blechtribe/` der virtuellen Karte will, kopiert den Ordner selbst im Dateimanager ("Öffnen" im Feld SD-Karte). Für Korgs rote Datei mit Hacktribe für die blaue gibt es den Knopf nicht: der Probelauf liefe mit Korgs roter Firmware statt mit der blauen.

### Eine Datei, auf der schon BLECHTRIBE ist

Eine Datei mit BLECHTRIBE ab Version 1.3.3 (über USB oder hineingezogen) bekommt den aktuellen Satz direkt darüber, ohne Original, für Korg rot, Korg blau und Hacktribe (roter und blauer Kopf). `data/known-releases.json` (gemacht von `tools/known-releases.mjs`, nur Hashes und Offsets) nennt jede Stelle, die diese Versionen geschrieben haben. Jede Stelle muss die Originalbytes oder die Bytes einer Version halten, sonst gilt die Datei als unbekannt und es wird nichts gepatcht. Freie Bereiche, die der aktuelle Satz nicht mehr nutzt, gehen auf FF zurück, Einhaken-Stellen bleiben und werden neu geschrieben, Effekt-Presets aus dem Katalog werden neu geschrieben (ein eigenes Preset mit gleichem Namen bleibt). Funktionen, deren Einhaken-Stellen in der Datei sind, lassen sich so nicht entfernen (die Optionen Gerätename und Sprache sind gesperrt). `tools/known-releases.mjs` läuft mit dem Tag jeder Version, damit sich ihre Dateien später aktualisieren lassen.

Nur wenn das die Datei ablehnt: bei Korgs Build baut die App das Original aus Korgs System Updater nach (die Bytes, die die Patches schreiben, kommen aus Korgs Datei, genutzt nur bei Treffer auf den Hash). Hacktribe hat diesen Rückfall nicht, seine eigenen Änderungen überschneiden BLECHTRIBEs Stellen, dort braucht es die unveränderte Datei. Eine teils gepatchte Hacktribe-Datei, die keine bekannte Version trägt, nennt deshalb die zwei Wege dahin: die Sicherung der eigenen Hacktribe-Datei (SHA-256 `7cb4825c...`) oder Korgs 2.02 mit `hacktribe-2.patch`. Versionen vor 1.3.3 fehlen in `known-releases.json` mit Absicht: mit ihren Stellen wäre eine Datei von 1.3.7 nicht mehr eindeutig (gemessen an Hacktribe 2.02 mit den Sets von 1.2.0 bis 1.3.7).

### Korgs Firmware laden

Schritt 1 fragt "Welche Basis willst du verwenden?" (bei BLECH und beim Weg zurück): "Original Firmware" ist vorgewählt, "Eigene Firmware" zeigt nur das Feld für die eigene `SYSTEM.VSB` oder ein Zip mit ihr. Bei "Original Firmware" lädt "Weiter" Korgs Firmware gleich, ohne Haken davor: unter den Karten steht, dass "Weiter" Korgs Lizenzvertrag annimmt (Korgs Downloadseite zeigt den Vertrag; der Link im Satz führt dorthin). Eine eigene Datei im Feld wird nie ersetzt. Der Haken für den Lizenzvertrag bleibt nur dort, wo die App Korgs Datei zu einer eigenen Datei laden soll (eine geänderte Korg-Datei oder eine mit BLECHTRIBE darauf, nur in der App).

- **App:** "Weiter" lädt Korgs Zip selbst von Korgs Server (`korg_firmware`, `src-tauri/src/korg.rs`) und legt es ins Feld. Nichts geht über einen Server von uns, nichts wird gespeichert.
- **Browser:** Korgs Server schickt keinen CORS-Kopf (gemessen am 26.10.: keine `Access-Control-Allow-Origin` auf GET, `OPTIONS` mit 403), die Seite kann das Zip also nicht selbst holen. "Weiter" startet den Download von Korgs Zip im Browser und bleibt auf Schritt 1; das Feld für das Zip erscheint, und es nimmt `.zip` an.
- **Zip im Feld:** das Feld nimmt Korgs Zip wie es ist und nimmt `SYSTEM.VSB` heraus (`src/zip.mjs`, mit dem `DecompressionStream` des Browsers); gemessen an beiden Zips von Korg: die herausgenommenen Dateien haben die SHA-256 `1d0f0689...` (rot) und `41fc5f1c...` (blau).

### Eigener Patch in Schritt 2

Schritt 2 fragt "Welchen Patch willst du anwenden?": "Neuste Version" ist vorgewählt (der Satz dieser App), "Eigene blech.patch" zeigt das Feld für eine Patch-Datei (jede Endung, das Format steht am Anfang der Datei). `src/anypatch.mjs` liest eine GELUMPE-`.patch` (`src/patchfile.mjs`), einen Patch im JSON-Format `gelumpe-patch` (einzeln oder als Liste), IPS und IPS32 sowie bsdiff (`BSDIFF40`). BPS, UPS und xdelta erkennt es und lehnt sie mit Namen ab, alles andere mit der Liste der Formate. Das Ergebnis muss die Länge einer `SYSTEM.VSB` haben (`0x200100` Byte). IPS und bsdiff bringen keine Prüfsummen mit, der Patcher weiß also nicht, auf welche Firmware sie passen: die Kontrolle ist der Test im Emulator. Geprüft mit selbstgebauten Patches (`test/anypatch.test.mjs`), offen: Patches aus der Szene.

### BLECHTRIBE mit Hacktribe für die blaue Electribe 2

Hacktribe ist Code des Samplers und läuft auf der roten und der blauen gleich. Für die blaue unterscheidet sich nur der Kopf der Datei (Byte `0x12` und `0x2E`), und der hängt an der Firmware, die beim Update auf dem Gerät läuft (gemessen, [Messung](messungen/2026-10-26-blech-hacktribe-blau.md)):

| Eingabe | Electribe | Kopf des Ergebnisses | Kartenordner |
|---|---|---|---|
| Hacktribe-Datei (roter oder blauer Kopf) | rot oder blau | Sampler (`0x53`, `0x24`): Hacktribes Update nimmt nur ihn | `KORG/hacktribe/System/` |
| Korgs rote 2.02 mit `hacktribe-2.patch` | rot | Sampler | `KORG/electribe sampler/System/` |
| Korgs rote 2.02 mit `hacktribe-2.patch` | blau | blau (`0x00`, `0x23`, wie Hacktribes `-e`): Korgs Firmware der blauen nimmt nur ihn | `KORG/electribe/System/` |
| Korgs blaue 2.02 | blau | blau, Synth-Satz ohne Hacktribe | `KORG/electribe/System/` |

- **Welche Electribe:** bei jeder Kopie mit Hacktribe fragt Schritt 2 "Für welche Electribe ist die Datei?". Vorgewählt ist, was der Kopf der Datei sagt; ist eine Electribe per USB verbunden, gilt sie (`DeviceSession.hardware`: Modell `0x23` ist Korgs blaue, sonst die Kennung im Flash bei `0x220000`). Passt die Wahl nicht zur verbundenen, sagt die Seite es in einer Zeile.
- **Aus Korgs blauer Datei** geht kein Hacktribe: `hacktribe-2.patch` baut nur aus Korgs roter Datei. Die Seite sagt das in Schritt 2 und nennt den Weg über die rote Datei.
- **Kopf:** gesetzt vor dem Patchen (`headFor`, `withHead` in `src/patcher.mjs`), damit Eingabe und Ergebnis denselben Kopf haben.
- **Prüfung:** für die blaue schickt die Seite `hardware=blue` an `POST /check`, der Emulator startet die Kopie auf dem Flash der blauen (Kennung `KORGelec2USR`).
- Gebaut und im Emulator geprüft, am Gerät offen. Was der Emulator nicht zeigt (Hintergrundlicht-Pins, Pad-LEDs, Klang der blauen unter Sampler-Code), steht in der [Messung](messungen/2026-10-26-blech-hacktribe-blau.md).

### BLECHTRIBE direkt auf Korgs Original 2.02

Gebaut und im Emulator geprüft, am Gerät offen. Belege und Zahlen: [BLECHTRIBE auf Korgs Original 2.02](messungen/2026-10-14-stock-blech.md). Zwei Wege beim roten Korg-Original: "BLECHTRIBE direkt (kein Hacktribe-Patch nötig)" ist die Vorgabe und wendet die Patches auf Korgs Datei an; "BLECHTRIBE mit Hacktribe (hacktribe-2.patch selbst mitbringen)" macht daraus erst Hacktribes Datei (nächster Abschnitt). Hacktribe ergänzt Filter für den Synth, zusätzliche Effekte und SysEx zum Lesen und Schreiben im RAM, das der Live-Modus des Editors braucht. Die Wahl lässt sich umstellen, solange nichts läuft.

- **Blaues Original:** die Seite erkennt es an der gemessenen SHA-256 und lädt `data/patches/blech-synth.json`. Der Emulator-Test legt ausschließlich `SYSTEM.VSB` unter `KORG/electribe/System/` ab; weitere VSB-Dateien dort verhindern den Test, sie werden nicht gelöscht. BLECHTRIBE SysEx liest auf dem Synth RAM und Flash, seine Schreibbefehle sind gesperrt. Effekt-Editor und Live-Bearbeitung bleiben beim Sampler.
- **Kartenordner:** die Fassung für Korgs Build ersetzt `electribe sampler` (Fenster von 18 Byte, mit NUL) und `KORG/electribe sampler/` (24 Byte) durch `blechtribe` und `KORG/blechtribe/`, der Rest des Fensters wird zu Nullen (`data/patches/blechtribe-stock.json`, gebaut von `tools/patch/blechtribe.py`, das das Build an der Datei erkennt). Beide Texte liegen in beiden Builds an denselben Adressen (`0xC00A5656`, `0xC00A5678`), und kein 32-Bit-Wort im Abbild zeigt in die Mitte eines Fensters (das Werkzeug prüft es).
- **Patch-Datei:** siehe `alternates` unter [Patch-Datei und bsdiff](#patch-datei-und-bsdiff-release-dateien). Gebaut wird sie mit `npm run build:blech-patch -- --stock <SYSTEM.VSB von Korg>` (oder `E2_STOCK_VSB`), dann liegt dazu `BLECH-for-1d0f0689.bsdiff` im Ordner.
- **Prüfung:** `check.py` läuft mit Korgs Datei als `--base` und der gepatchten Kopie als `--patched`; Besonderheiten unter [Prüfung gegen Korgs Build](#prüfung-gegen-korgs-build).
- **Was fehlt:** alles, was Hacktribe hinzufügt und BLECHTRIBE nicht selbst mitbringt. Der Live-Modus des Editors braucht Hacktribes SysEx `0x52` bis `0x57`; das gibt es in Korgs Build nicht ([Original im Emulator](messungen/2026-10-14-stock-emulator.md)), mit BLECHTRIBE ersetzen es BLECHTRIBEs eigene Befehle, und der Effekt-Editor liest und schreibt Korgs Presets live ([Effekt-Editor auf Korgs Original](messungen/2026-10-15-effekt-editor-original.md)).

### Original Korg 2.02 zu Hacktribe

Gebaut (`convertStock` in `src/patcher.mjs`, `src/bsdiff.mjs`, `src/bzip2.mjs`). Hacktribes Weg ist `scripts/e2-firmware-patch.py` mit `patch/hacktribe-2.patch` (bsdiff4, 17,6 KB, bzip2 darin). Die README von `bangcorrupt/hacktribe` (geprüft 2026-10-14) sagt: "Contents of `patch` directory is not open source and is not covered by the GPL." Alles andere ist AGPL-3.0. Die Patch-Datei liegt deshalb weder in diesem Repository noch auf der Seite. Unter dem Lizenz-Haken steht ein zweiter: "Lade zusätzlich hacktribe-2.patch direkt von Hacktribe". Er ist gesetzt, wenn das Ziel Hacktribe braucht, und lädt die Datei direkt aus Hacktribes Repository (`HACKTRIBE_PATCH_RAW`, raw.githubusercontent.com, das CORS erlaubt) auf den Rechner des Nutzers; das Ergebnis prüft `convertStock` wie bei einer abgelegten Datei. Ohne Netz sagt ein Hinweis das, und das Feld für die eigene Datei bleibt. Ohne Haken lädt die Seite nichts: wer will, holt die Datei bei Hacktribe (die Seite verlinkt sie) und zieht sie auf die Seite.

Ablauf, alles im Browser:

1. Die Datei muss mit `BSDIFF40` beginnen, darf höchstens 1 MiB groß sein (die echte hat rund 18 KB) und muss eine Datei von `0x200100` Byte bauen. Einen Hash der Patch-Datei nennt Hacktribe nicht, geprüft wird deshalb das Ergebnis.
2. bsdiff anwenden (Steuer-, Diff- und Extra-Strom, je bzip2). Den bzip2-Dekoder haben wir selbst geschrieben (`src/bzip2.mjs`, keine neue Abhängigkeit, Blockprüfsummen und Gesamtprüfsumme geprüft), ebenso das Anwenden des Patches.
3. Das Ergebnis muss `7cb4825c...` sein, der Wert in `hash/hacked-SYSTEM.VSB.sha` bei Hacktribe. Gemessen: dieselbe SHA-256 hat eine eigene Hacktribe-2.02-Datei aus Hacktribes Paket. Nicht gemessen ist die echte `hacktribe-2.patch`: sie liegt hier nicht vor. Getestet ist der Weg mit einem eigenen Patch von bsdiff4 vom Original zur Hacktribe-Datei; mit eigener Datei prüfbar über `E2_STOCK_VSB` und `E2_HACKTRIBE_PATCH` in `test/patcher.test.mjs`.

Danach geht es wie bei einer Hacktribe-Datei weiter (BLECHTRIBE, Prüfung, Download). Die Anleitung zeigt den Kartenordner der Original-Firmware, `KORG/electribe sampler/System/`. Die Tests nutzen selbstgebaute Dateien (`test/fixtures/bsdiff/make.py`, Zufallsdaten, nichts von Korg oder Hacktribe).

### Prüfung gegen Korgs Build

`check.py` besteht mit Korgs Original als Basis und der gepatchten Kopie, mit leerem Flash und mit dem eigenen Flash-Abbild ([BLECHTRIBE auf Korgs Original](messungen/2026-10-14-stock-blech.md)). Was bei Korgs Build anders ist und wie die Prüfung damit umgeht:

- **Das Startbild steht länger und trägt einen Ladebalken.** Mit leerem Flash von 0,07 bis 0,40 s (Hacktribe 0,07 bis 0,21 s), mit dem eigenen Flash bis rund 5,9 s. Korgs Build lädt dabei seine Daten und zeichnet einen Balken auf die Seite 7, Spalten 9 bis 119 (er löscht die Pixelzeilen 61 und 62). Die Startbild-Fälle erlauben das, und nur das: `same_image` in `splash_cases.py` nimmt für Korgs Build Abweichungen an genau diesen Bytes an, alles andere am Bild muss gleich sein, und für Hacktribe ändert sich nichts.
- **Die Prüfläufe warten aufs Laden** (`Machine.loading`, `finish_boot`, nur für Korgs Build), mit eigenem Flash rund 6 s statt 0,4 s.
- **Zwei Stellen des Emulators brauchten eine Annahme:** Statusbit 2 am DSP-Port und das einzelne Gleichlaufwort `0x2C` ([Emulator](emulator.md), "DSP-Portmodell"). Beide sind Modellannahmen, nicht an Hardware gemessen.
- **Die Zeitscheibe von `bootmap.py`** ist für Korgs Build 2 ms statt 20 ms, weil das Hauptbild an einer beliebigen Stelle des Bildticks kommt und der Lauf vor dem ersten Tick enden muss.

### Prüfung mit leerem Flash

Die Prüfung muss auch bei einem frischen Dienst ohne Flash-Datei bestehen, denn die meisten, die den Patcher benutzen, haben keinen Flash-Abbild-Dump. Das Startbild steht bei einem leeren Flash nur rund 0,13 s (0,07 bis 0,20 s, mit dem eigenen Flash bis 0,22 s, gemessen mit `splash_cases.py cases`). Feste Stichproben lägen deshalb an der Kante; die Fälle sehen jedes Bild vom ersten gezeichneten Pixel, bis das Display wieder leer ist (mindestens 5 Bilder, alle müssen das erwartete Startbild sein), unabhängig von der Dauer. Dasselbe gilt im Neustart-Schritt von `splash_cases.py run`.

Bei einem leeren Flash schreibt die Firmware beim ersten WRITE selbst eine Marke (`ULEG`, 8 Byte) nach `0x7EF000`, auch die unveränderte Firmware (gemessen); der Schritt "nur dieser Sektor geändert" erlaubt sie, aber nur dort und nur mit genau diesem Inhalt.

## Was kaputtgehen kann

1. Firmware stürzt ab oder hängt im Betrieb: Neustart.
2. Geflashte Firmware startet nicht, das Gerät fragt nach einem Update: Korgs Original-VSB von SD (laut Hacktribe-Doku; selbst nicht durchgespielt, siehe [Rückweg geübt](messungen/2026-10-10-rueckweg-geuebt.md)).
3. Firmware hängt vor der Update-Abfrage: nur JTAG. Dagegen Regeln 1 bis 3 und die Prüfungen vor dem Export.
4. Startprogramm überschrieben: nur JTAG. Der Patcher fasst es nie an.
5. Nutzerdaten im Flash beschädigt: aus Flash-Dump und SD-Backup.
6. Hardwareschaden durch Software: kein Fall bekannt, nicht ausgeschlossen; dagegen Regel 4.

Der Rückweg über den normalen Updateweg ist am Gerät geübt: eine Firmware aus dem Patcher hin, das Original zurück ([Messung](messungen/2026-10-10-rueckweg-geuebt.md)). Offen ist die Rettung, wenn die laufende Firmware nicht mehr startet ([Rettung](rettung.md)).

## Offen

Geplant, nicht gebaut:

- Code als Quelltext, dem der Patcher einen Platz zuteilt (siehe "Patch-Format").
- Sprung und Notschalter-Abfrage vom Patcher erzeugen lassen statt vom Patch (siehe "Einhaken").
- DSP-Patches mit Klangprüfung im Emulator (das DSP-Modell prüft nur die Schnittstelle).
- Boot-Menü und Rückfall-Firmware: ein kleines eigenes Menü statt Korgs erstem Befehl bei `0xC0000070`, eine unveränderte Firmware in freiem Flash; im Repository gibt es dazu keinen Code. Es liefe vor Korgs Initialisierung und bräuchte eigene Treiber für Display, Tasten und Flash, wäre also der kritischste Code des Projekts.
- Punkt 5 der Prüfungen vor dem Export für alle Patches.

Offene Messungen:

- Gerechnete Adressen in den `FF`-Blöcken: am Gerät nur der Code von MFX 2 geprüft.
- Welcher Bildschirm 28 ist, den der SHIFT-Merker beim Start freischaltet ([Messung](messungen/2026-10-10-startphase.md)).
- Freier RAM für nachgeladenen Code.
- Ob die Liste der Menüseiten beim Start oder beim Öffnen gebaut wird.
- DSP: genaues Modell und der Aufbau des Master-Wegs; das Ladeformat (Blackfin-Bootformat, Blöcke mit `0xAD`) ist gemessen ([DSP, erster Blick](hintergrund/dsp-erster-blick.md)).
- Die echte `hacktribe-2.patch` im Patcher: bisher nur mit einem selbstgebauten bsdiff geprüft.
- Am Gerät: Lesen und Schreiben der Karte über FatFs, Schreiben des Startbild-Editors in den Flash, Plugin-Laufzeit und BLECH-Menü.
- Die Rettung bei einer Firmware, die nicht mehr startet, und ob die Datei unter `KORG/electribe sampler/System/` dafür taugt.
