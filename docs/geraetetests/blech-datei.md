# Gerätetest: BLECH-Firmwaredatei

Anleitung für Tester. Die Datei ist gebaut und im Emulator geprüft, am Gerät ist nur bestätigt,
was in Abschnitt 6 so steht. Siehe auch die [Übersicht](README.md).

## 1. Worum es geht

BLECH ist ein Satz von Patches für die eigene `SYSTEM.VSB` (Sampler 2.02, Korgs Original oder
[Hacktribe](../glossary.md#hacktribe)). Er gibt der Electribe das Menü BLECH, Plugins von der SD-Karte, den
Startbild-Editor, MFX 2 und mehr ([Plugins](../plugins.md), [Patcher](../patcher.md)). Dieser Test spielt die Datei
über DATA UTILITY, SOFTWARE UPDATE auf, prüft den Notschalter und geht die Geräteschritte durch, die der Emulator
nicht beantworten kann.

Der Satz steht in `data/patches/blech.json` (rot) und `data/patches/blech-synth.json` (blau). Die Seite Patcher baut
daraus dieselbe Datei wie `tools/patch/apply.mjs`.

## 2. Warnung

**Das Gerät wird verändert.** SOFTWARE UPDATE schreibt eine geänderte Firmware in den Flash
(`0x020000` bis `0x220000`). Du machst das auf eigenes Risiko, ohne Gewähr. Was passieren kann:

- Das Gerät hängt oder startet neu: aus- und wieder einschalten, oder mit gehaltenem EXIT starten.
- Das Gerät startet mit BLECH nicht normal: die Original-Firmware neu aufspielen (Abschnitt 5).
- Hängt die Firmware vor der Update-Abfrage, ist das Gerät ohne JTAG nicht zu retten. Die Startwege sind im
  Emulator geprüft, am Gerät ist das nicht ausgeschlossen ([Patcher](../patcher.md), "Was kaputtgehen kann").
- Daten gehen verloren, wenn das Update oder ein späteres Speichern gestört wird. Am 13.10. standen die Globals
  nach Arbeit am Gerät auf der Vorgabe, die Ursache ist **offen**
  ([Messung](../messungen/2026-10-13-globals-zurueckgesetzt.md)). FACTORY RESET löscht Patterns und Globals und
  steht in DATA UTILITY direkt vor SOFTWARE UPDATE.

Korg-Daten werden nie hochgeladen. `BLECH.VSB` enthält deine Firmware und bleibt bei dir, die Seite Patcher
verarbeitet sie im Browser. Gemeldet werden nur Textausgaben und Prüfsummen.

## 3. Voraussetzungen

- Electribe 2 mit Firmware 2.02, Netzteil angeschlossen (kein Batteriebetrieb beim Update).
- Die eigene `SYSTEM.VSB` oder `ORIGINAL.BIN` (Korg oder Hacktribe).
- SD-Karte im Gerät, Kartenleser am Rechner.
- Die App (Seite Patcher) oder Node 20. Für die Emulator-Prüfung die Python-Umgebung (`npm run setup:emu`).
- Für die Schritte in Abschnitt 7: Python 3 mit `mido` und das Gerät per USB. Es muss genau ein MIDI-Port mit
  "electribe" und "SOUND" im Namen da sein.

## 4. Vorher sichern

1. **SD-Karte komplett kopieren.**
2. **Global-Block lesen** (nur Lesen, nie ab Adresse `0x1000000`):

   ```bash
   python3 tools/device/flash_dump.py --out <Datei> --start 0x230000 --length 0x4000
   ```

   Die ersten 256 Byte sind der Global-Block ([Speicherbereiche](../speicherbereiche.md)). Nach dem Update dasselbe
   in eine zweite Datei schreiben und die ersten 256 Byte vergleichen.
3. **Patterns sichern:** am Gerät EXPORT ALL PATTERN in DATA UTILITY, das legt eine `.e2sallpat`-Datei im
   Kartenordner ab. Die Samples liegen als `e2sSample.all` auf der Karte, also in der Kartenkopie.
4. **Die laufende Firmwaredatei** sichern und ihre Prüfsumme notieren (`shasum -a 256`). Das ist die
   Rückkehr-Datei aus Abschnitt 5.

## 5. Der Weg zurück

Welche Datei in welchen Ordner gehört, steht in der [Rettung](../rettung.md), "Welche Datei in welchen Ordner".
Kurz:

- **Notschalter:** beim Einschalten EXIT halten. Dann läuft die Firmware ohne BLECH-Menü, Plugins und MFX 2, nur für
  diesen Start, es wird nichts gespeichert. Datenpatches wie das Blech-Startbild wirken weiter. Gegen kaputte
  Startdaten, DSP-Patches und kaputte gespeicherte Daten hilft er nicht ([Patcher](../patcher.md), "Notschalter").
- **Gerät startet noch:** die gesicherte Original-Datei als `SYSTEM.VSB` in den Ordner der laufenden Firmware legen,
  Prüfsumme der Kopie nachlesen, DATA UTILITY, SOFTWARE UPDATE. Am 10.10. so hin und zurück geübt
  ([Messung](../messungen/2026-10-10-rueckweg-geuebt.md)).
- **Gerät startet nicht:** [Rettung](../rettung.md). Hängt die Firmware vor der Update-Abfrage, hilft nur JTAG, nichts
  weiter ausprobieren.
- **Ein Plugin macht Ärger:** `Plugin/e2sPlugin.all` von der Karte nehmen oder mit gehaltenem EXIT starten.
- **Globals weichen ab:** nicht ausschalten und nicht WRITE drücken (das speichert, was im RAM steht). Den
  gesicherten Block als Global-Dump (`0x51`) senden, das speichert sofort. Den globalen MIDI-Kanal danach von Hand
  setzen. Ein fertiges Werkzeug dafür liegt nicht bei (**offen**).

## 6. Installieren und Notschalter

Je Schritt "ok", "anders" oder "nicht gelaufen" melden. Hält ein Schritt nicht, was er erwartet: aufhören, Ausgabe
und Display notieren.

| # | Schritt | Erwartet |
|---|---|---|
| 1 | Datei bauen: Seite Patcher, oder `node tools/patch/apply.mjs --vsb <eigene SYSTEM.VSB> --set data/patches/blech.json --out BLECH.VSB` | `wrote BLECH.VSB`, SHA-256 notieren (sie hängt von deiner Ausgangsdatei ab) |
| 2 | Im Emulator prüfen: die Seite Patcher macht es selbst und gibt den Download erst danach frei, `apply.mjs` druckt den Befehl für `tools/emu/check.py` | alle Prüfungen bestanden, das dauert einige Minuten |
| 3 | `BLECH.VSB` als `SYSTEM.VSB` in den Ordner der laufenden Firmware auf der Karte, Prüfsumme der Kopie nachlesen | gleich der aus Schritt 1 |
| 4 | Karte ins ausgeschaltete Gerät, Netzteil, DATA UTILITY, SOFTWARE UPDATE (davor steht FACTORY RESET, das nicht bestätigen), Version ansehen, bestätigen, "OK. Please Reboot." abwarten, ausschalten | das Update läuft durch |
| 5 | Einschalten, dann Global-Block erneut lesen und mit der Sicherung vergleichen | Blech-Startbild, Hauptbildschirm, Samples da, Globals unverändert |
| 6 | Neustart mit gehaltenem EXIT | normaler Start ohne Menü BLECH (der Ring läuft von Global direkt zu Data Util), das Blech-Startbild erscheint trotzdem |

Der Notschalter ist am Gerät für den MFX-2-Code-Patch bestätigt (13.10.), für den ganzen Satz ist er **offen**.

## 7. Geräteschritte

Das Menü BLECH und die Plugin-Laufzeit sind im Emulator mit Fällen in `tools/emu/` geprüft (`menu_cases.py`,
`script_cases.py`, `blechy_cases.py`). Die folgenden Schritte brauchen das Gerät.

### 7.1 BLECH SysEx: RAM lesen, Durchsatz messen

Der Patch `blech-sysex` gibt dem Gerät eigene [SysEx](../glossary.md#sysex)-Befehle `0x60` bis `0x63`
([Messung](../messungen/2026-10-15-blech-sysex.md)). Gerät per USB, kein Editor im Browser offen:

```bash
python3 tools/device/blech_sysex_probe.py --repeat 5
```

Das Werkzeug fragt INFO, liest `0xC0000100` in Blöcken von 256 bis 32768 Byte, prüft jeden Block gegen die CRC-32 des
Geräts und druckt Millisekunden und KiB/s je Größe. Es schreibt nichts. Bricht es bei einer Größe ab, ist die Größe
darunter der größte sichere Block.

Erwartet: INFO mit Version 1, Flags `0xF`, größter Block 32768, alle Blöcke mit passender CRC. Im Emulator über DIN
schafft ein Block 2,6 KiB/s (die Leitung ist die Grenze), über USB wird deutlich mehr erwartet (geschätzt). Mit EXIT
beim Einschalten bleibt die Abfrage ohne Antwort. Melden: die Ausgabe, bei einem Abbruch die Größe und die Meldung.

### 7.2 BLECH FLASH READ: den Flash lesen (besonders blaue Electribe)

Der Befehl `0x64` liest den Flash nur, es gibt keinen, der ihn schreibt oder löscht. Gedacht für die blaue
Electribe 2 (Synth), von der es bisher keine Sicherung des Flash gibt. Voraussetzung: eine Firmware mit dem
SysEx-Patch (Synth: `data/patches/blech-synth.json`), Netzteil, nichts am Gerät bedienen, solange das Werkzeug läuft.

1. Die Original-`SYSTEM.VSB` der blauen (Version 2.02) und die Karte sichern, das ist der Weg zurück.
2. Die BLECH-Synth-Datei als `SYSTEM.VSB` in den Ordner legen, der in der [Rettung](../rettung.md) für die blaue
   steht, dort **keine andere Datei** (besonders kein `BOOT.VSB`, `USER.VSB`, `PCM.VSB`: was die Firmware damit tut,
   ist nicht gemessen). SOFTWARE UPDATE wie in Abschnitt 6, mit Netzteil (mit Batterie lehnt das Gerät ab).
3. Lesen:

   ```bash
   python3 tools/device/blech_sysex_probe.py --repeat 2
   python3 tools/device/blech_flash_dump.py --out <Datei> --start 0x220000 --length 0x8000   # ein kleiner Anfang
   python3 tools/device/blech_flash_dump.py --out <Datei>                                      # der ganze Flash
   ```

   Das Werkzeug liest in Blöcken zu 4096 Byte, prüft jede CRC-32, liest alles zweimal und schreibt die Datei nur,
   wenn beide Läufe gleich sind. Es lehnt einen Pfad in einem Git-Arbeitsverzeichnis ab, denn die Datei enthält
   Korg-Daten.
4. Zurück: die gesicherte Original-Datei in denselben Ordner, dieselben Schritte. Dann antworten INFO und FLASH READ
   nicht mehr.

Erwartet: der kleine Lauf zeigt am Anfang die Kennung der Nutzerdaten (Synth `KORGelec2USR`, Sampler `KORGele2sUSR`),
der volle Lauf endet mit "written", beide Läufe haben dieselbe SHA-256, die Datei hat 16.777.216 Byte. Die Datei nicht
weitergeben. Melden: SHA-256 und Dauer, sonst die Meldung und die Adresse.

### 7.3 HT OSC: Hacktribes Oszillatoren auf der roten Firmware (nur rot)

Voraussetzung: der BLECH-Satz auf Korgs roter 2.02, Karte mit der eigenen `e2sSample.all`. Im Emulator gemessen ist,
dass die Einträge stehen, der Regler sie erreicht, die Datei lädt und ein Pattern sie behält
([Messung](../messungen/2026-11-08-ht-osc-freie-plaetze.md)). Wie sie klingen, zeigt nur das Gerät.

1. Part 1 wählen, OSC-Regler bis 420 (letztes Werks-Sample), eine Raste weiter. Erwartet: 422 DUAL-SAW. Weiter bis
   497 VPM-SINE 32, die nächste Raste springt auf 501. Jeden Oszillator kurz anspielen.
2. Mit einer Hacktribe vergleichen, wenn eine da ist (DUAL-SAW, CHIP-NOISE, X-SAW 0, X-SAW +12, VPM-SINE 4).
   Erwartet: gleicher Klang.
3. Osc Edit auf DUAL-SAW und X-SAW 0 drehen. Erwartet: der Klang ändert sich wie unter Hacktribe.
4. Part 1 auf 431 (CHIP-TRI 2), WRITE, aus- und einschalten. Erwartet: Part 1 steht auf 431 und klingt gleich.
5. BLECH > FEATURES ansehen. Erwartet: keine Seite HT OSC, die Oszillatoren sind immer an.
6. Mit EXIT beim Einschalten: wie die Firmware, 422 heißt `Sample422`.

Melden: ok je Schritt, sonst welcher Oszillator anders klingt oder stumm ist (mit Platznummer).

### 7.4 CATEGORY in SAMPLE EDIT (rot und Hacktribe, nicht blau)

Voraussetzung: der BLECH-Satz, Karte mit mindestens einem eigenen Sample. Im Emulator gemessen sind Seiten, Zähler,
Rad, Export und ein Sample mit Slices ([Messung](../messungen/2026-11-21-sample-kategorie.md)).

1. DATA UTILITY > SAMPLE EDIT, ein eigenes Sample wählen, EDIT rechts. Erwartet: Seite 3/11 heißt CATEGORY, der Wert ist
   "[User]" (Hacktribe "[Wave]").
2. Rad auf "[Kick]", EXIT. Erwartet: das Part-Bild zeigt beim Sample "[Kick]".
3. SHIFT + OSC-Rad auf einem Part mit diesem Sample. Erwartet: es springt auf das Sample als eigene Kick-Folge, nicht zu
   den Werks-Kicks.
4. RENAME, START POINT, DELETE SAMPLE durchgehen. Erwartet: wie vorher, der Zähler zählt bis 11/11 und läuft auf 1/11 um.
5. EXPORT ALL SAMPLE, aus- und einschalten. Erwartet: das Sample steht weiter auf "[Kick]", und ein Sample-Werkzeug am
   Rechner zeigt die Kategorie Kick.
6. Ohne EXPORT ALL SAMPLE umstellen, aus- und einschalten. Erwartet (hergeleitet): die alte Kategorie ist zurück.
7. Mit EXIT beim Einschalten: SAMPLE EDIT hat Korgs 10 Seiten, keine CATEGORY.

Melden: ok je Schritt, sonst die Seite und was das Display zeigt.

### 7.5 korg.menu.add

Im Editor ein Plugin mit diesem Text anlegen, proben, exportieren, laden:

```js
korg.app("Speed", "TOOLS");
let speed = 5;
const page = korg.menu.add("Speed", 1, 10, 5);

korg.onEvent("menu", (id, value) => {
  if (id == page) { speed = value; }
});

korg.onEvent("frame", () => {
  korg.display.clear();
  korg.display.number(speed, 0, 16);
});
```

Erwartet: im Menü, Gruppe PLUGINS, steht eine Seite "Speed" mit 5, das Hauptrad ändert die Zahl (1 bis 10).
TOOLS > Speed, ENTER öffnet die App, sie zeigt die geänderte Zahl (hergeleitet, im Emulator gemessen ist nur, dass das
Plugin das Ereignis bekommt). Melden: ok, sonst was die Seite und das Display zeigen.

### 7.6 Display nehmen

Im Editor ein Plugin mit diesem Text anlegen, proben, exportieren, laden:

```js
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.PLAY && korg.display.take()) korg.display.text("PLAY aktiv", 0, 0);
});
```

Erwartet: nach dem Laden bleibt das Display das der Firmware. PLAY zeigt "PLAY aktiv", EXIT bringt den normalen
Hauptbildschirm zurück, auch wenn das Plugin die Taste nicht abfragt. Melden: ok, sonst was angezeigt wird.

### 7.7 Das Menü ansehen

Hauptbildschirm, MENU, mit EDIT rechts bis Event ("30/32"), EDIT rechts:
eine einzige Seite "BLECH 31/32" mit dem Titel BLECH und der Zeile "press  [ Enter ]", so wie Data Util,
EDIT rechts: Blechy (32/32), EDIT rechts: die erste Seite des Pattern Menüs. Im Pattern Menü bis CHAIN REPEAT ("15/32"),
EDIT rechts: SYNC GROUP ("Pattern 16/32"), EDIT rechts: die erste Seite des Part Menüs ("17/32"), und zurück.
Auf der blauen: SYNC GROUP 16/31, BLECH 30/31, Blechy 31/31.
In Global (MENU auf "Global") auf der ersten Seite EDIT links: PLUGIN RUNTIME ("Global 21/21"), EDIT rechts wieder die
erste Seite (TRIGGER MODE, "1/21"). In Data Util (MENU auf "Data Util") auf der ersten Funktion EDIT links:
SET INIT PATTERN ("Data Util 18/18", auf der blauen 14/14), mit EDIT links weiter EXPORT ALL EFFECTS (17/18 auf der roten, auch auf der blauen),
EXPORT ALL PLUGINS (16/18), EXPORT ALL CUSTOM (15/18), dann SOFTWARE UPDATE (14/18). EXPORT ALL CUSTOM schreibt
`KORG/blechtribe/e2sCustom.all`, EXPORT ALL EFFECTS schreibt `KORG/blechtribe/Presets/e2sFx.all` neu (der Editor liest
sie danach mit allen Einträgen und Texten). EXIT auf diesen Seiten geht auf "Global" bzw. "Data Util" zurück.
Zurück auf BLECH: ENTER (die Taste MENU) öffnet die Liste der Gruppen: "BLECH 1/4" FEATURES, dann mit
EDIT rechts PLUGINS, CUSTOMIZATION (GAMES und TOOLS kommen dazu, wenn eine App der Gruppe geladen ist, die Zähler zählen dann
bis 6), zuletzt VERSION,
jede mit "press  [ Enter ]". ENTER auf FEATURES zeigt die vier Schalter MFX 2, PATTERN CONFIRM, TAP MOTION und NOTE ASSIST
mit Wert (ON) statt "press  [ Enter ]" (Schild "Feature"). ENTER auf einer Gruppe zeigt ihre Seiten: das Schild oben links nennt sie ("Plugins 1/5"),
der Zähler zählt nur ihre Seiten, EDIT blättert im Kreis. EXIT geht immer eine Ebene zurück (Seiten, Liste, Ring,
Hauptbildschirm), MENU auf dem Hauptbildschirm kommt wieder auf die zuletzt benutzte Seite. WRITE auf einer Seite
darf kein Fenster "Pattern schreiben" öffnen. Auf jeder Seite stehen Titel, Wert und Schild klar lesbar, nichts liegt
übereinander und kein Schild ist abgeschnitten ("Custom 1/8" mit ganzem m).
Erwartet: wie beschrieben, im Emulator gemessen (Ring, ENTER, EXIT, WRITE, MENU, alle 48 Tasten ohne
Assertion, kein Text über einem anderen, jedes Schild vor seinem Zähler ganz). Der Seitenzähler am Gerät ist offen
(siehe Abschnitt 8). Bilder aus dem Emulator: `docs/images/blech-menue-v14/00-all.png` (nur lokal, nicht im Repo).
Melden: ok, sonst Seitenzähler und Anzeige der Seiten, am besten mit Foto.

### 7.8 Einstellungen

Gruppe FEATURES, Seite MFX 2: Hauptrad auf OFF, der Wert zeigt "OFF, RESTART". WRITE:
"saved". Ausschalten, die Karte am Rechner ansehen: `KORG/blechtribe/settings.b.bin` ist 24 Byte
groß. Wieder einschalten. Danach wieder ON und WRITE.
Erwartet: nach dem Neustart ist MFX 2 aus, TOUCH SCALE verhält sich wie im Original.
Melden: ok, sonst die Anzeige und die Dateigröße.

### 7.9 Anpassung: untere LEDs

Netzteil angeschlossen. Gruppe CUSTOMIZATION (ENTER), Seite BOTTOM LEDS: Hauptrad auf
COLOR, dann auf den Seiten LED HUE, SAT, BRIGHT die Farbe verstellen (HUE einmal rundum, SAT und BRIGHT 0 bis 15), auch ganz hoch und
ganz niedrig, dann die Seite BOTTOM LEDS auf OFF und auf METER. Dabei Musik laufen lassen. WRITE.
Erwartet: jede Änderung sieht man sofort an den vier unteren LEDs. COLOR leuchtet fest in der
Farbe, OFF dunkel, METER mit Farbe wird mit dem Pegel heller und dunkler, ohne Farbe (STOCK) ist
es die Pegelanzeige wie vorher. Sieht man Zwischenstufen bei den Pegeln, nehmen die LEDs Helligkeit an;
sieht man nur an und aus, ist das so zu melden (offen, siehe Abschnitt 8). Nach dem Neustart ist die Wahl
noch da. Im Global-Menü Power Save auf "Always": die LEDs gehen aus, auch bei COLOR.
Melden: ok, sonst was zu sehen ist, besonders die Stufen und die Farben.

### 7.10 Anpassung: Display-Licht

Gruppe CUSTOMIZATION, Seiten BACKLIGHT HUE, SAT, BRIGHT. Erst HUE einmal rundum bei voller
SAT und BRIGHT, dann Mischungen mit niedriger SAT und BRIGHT, auch sehr niedrige (1 bis 3). WRITE.
Erwartet: die Farbe ändert sich sofort. Pegel 0 und 15 sind feste Farben ohne Software-PWM. Bei Pegeln
dazwischen steuert die Firmware das Licht mit einer PWM (8 ms): am Gerät darauf achten, ob es flimmert
(mit dem Auge, mit der Handykamera, beim Bewegen der Augen) und ob alle Kanäle gleich hell stufen.
Alle drei auf 0 ist das Weiß der Firmware, die Anzeige ist lesbar. Nach dem Neustart ist die Wahl noch da.
Power Save "Always" dimmt das Licht wie ohne BLECH. Flimmert es, kommen nur die Pegel 0 und 15 (acht
Farben, keine PWM) in den Patch.
Melden: ok, sonst was zu sehen ist (Flimmern ja oder nein, Stufen, Lesbarkeit).

### 7.11 Display umkehren

Gruppe CUSTOMIZATION, Seite DISPLAY INVERT ("Custom 8/9"): Hauptrad auf ON, dann auf OFF, dann
wieder ON, WRITE, MENU verlassen (EXIT), Hauptbildschirm ansehen, ausschalten und neu starten.
Erwartet: bei ON werden helle Punkte dunkel und dunkle hell, sofort, am Menü und am Hauptbildschirm, bei OFF ist alles
wie vorher; nach dem Neustart ist es noch an. Neustart mit gehaltenem EXIT: Display normal. **Das ist ein Test, ob der
Display-Baustein den Befehl `0xA7` annimmt** (Annahme, Baustein nicht geprüft): bleibt das Display bei ON unverändert,
sagt das hier, dann bekommt die Seite eine Umkehrung in Software.
Melden: ok, sonst was das Display bei ON zeigt (unverändert, Müll, umgekehrt nur teilweise).

### 7.12 Plugin laden

Im Editor auf der Seite Plugins den Quelltext von `test/fixtures/scripts/klicker.js` als eigenes Plugin "klicker" einfügen, proben, "Alle
speichern (e2sPlugin.all)", die Datei nach `KORG/blechtribe/Plugin/` auf die Karte, neu starten.
Erwartet: der Hauptbildschirm bleibt unverändert, die Patterns sind zu sehen (das Laden zeichnet nichts).
Der Klicker ist eine App: im Menü steht unter TOOLS > "Klicker" ("ENTER=OPEN"), unter PLUGINS eine Seite
"klicker" (ON, mit dem Hauptrad OFF und wieder ON), kein Blechy darunter. TOOLS, ENTER: der Bildschirm der App
zeigt "Klicks 0", TAP zählt und leuchtet. EXIT: der normale Hauptbildschirm ist zurück, mit den Patterns.
TAP zählt auch bei geschlossener App (die LED), ENTER öffnet sie wieder mit dem Stand.
Melden: ok, sonst was passiert und was das Display zeigt.

### 7.13 Snake

Dasselbe mit Snake, dabei Musik laufen lassen. Snake ist eine App unter GAMES: nach dem Laden zeigt
das Gerät wie vorher seinen Hauptbildschirm, GAMES, ENTER öffnet das Spiel (neues Spiel bei jedem Öffnen),
gesteuert mit ◄ Part und Part ►, EXIT beendet es und der normale Bildschirm ist zurück. Solange Snake offen ist,
ändern ◄ Part und Part ► die gewählte Part der Firmware nicht (im Emulator gemessen, `snake-part-tasten-aendern-die-part-nicht`);
nach EXIT ändern sie die Part wieder (`part-tasten-nach-exit-wieder-der-firmware`).
PLAY, STOP und REC erreichen die Firmware auch bei offener App: PLAY startet das Pattern, STOP hält es an
(`app-offen-play-stop-erreichen-die-firmware`), die App sieht beide Tasten ebenfalls.
Erwartet: kein Knacken und kein Stocken des Sequencers, nach Gehör; EXIT geht jederzeit.
Melden: ok, sonst was zu hören ist und bei welcher Tätigkeit.

### 7.14 EXPORT ALL PLUGINS

Data Util, auf der ersten Funktion zweimal EDIT links (auf der blauen ebenso): Seite
EXPORT ALL PLUGINS (sieht aus wie IMPORT SAMPLE: Titel, "press  [ Enter ]"), ENTER oder WRITE.
Erwartet: "1 exported" (oder die Zahl der Plugins) als Wert der Seite. Auf der Karte am Rechner ist `e2sPlugin.all`
gleich groß und gleich dem, was vorher drauf war.
Melden: ok, sonst die Meldung des Geräts und die Größen.

### 7.15 Plugin laden

Ein `.blech` aus dem Editor ("Als .blech speichern") nach
`KORG/blechtribe/Plugin/` legen (auf einem Mac liegen dort oft auch `._Name.blech` Dateien), am Gerät im Menü auf
PLUGINS ENTER drücken (die Liste öffnet direkt, ohne die Seite MANAGE PLUGINS dazwischen). EDIT blättert durch die Liste, je Plugin eine Seite: oben der Name, darunter
der Stand. Ein nicht geladenes zeigt OFF; das Hauptrad nach oben lädt es, WRITE behält den Stand. ENTER auf einem
Plugin öffnet seine Seiten: ACTIVE, DESCRIPTION, seine eigenen Seiten, REMOVE; EXIT führt zurück auf das Plugin in der Liste.
Erwartet: nur echte Plugin Dateien stehen in der Liste (keine mit Punkt am Anfang), ein Plugin kommt nur einmal vor,
DESCRIPTION zeigt die Beschreibung (das Hauptrad scrollt sie), unter dem Namen steht nach dem Laden ON, das Plugin läuft
sofort, es hat nun mehr Seiten hinter ENTER (hat es eine App, steht sie unter GAMES oder TOOLS). Das Hauptrad nach unten auf
ACTIVE nimmt es aus `e2sPlugin.all` (Seite bleibt offen, zeigt OFF), die Datei bleibt und das Plugin steht als OFF in
der Liste; nach Neustart läuft es nicht. Nach oben lädt es wieder, nach Neustart läuft es. REMOVE fragt
("Enter = remove"), ein zweites ENTER nimmt es heraus und löscht seine `.blech` ("removed"); es steht nicht mehr in der
Liste, am Rechner fehlt die Datei. Auf der blauen bleibt die Datei ("file stays on card").
Melden: ok, sonst Meldung und Anzeige.

### 7.16 Viele Plugins

70 `.blech` (mit verschiedenen Namen im Kopf) nach `KORG/blechtribe/Plugin/` legen, im Menü auf
PLUGINS ENTER.
Erwartet: die Liste zählt 65 Seiten, die letzte heißt LIST FULL mit "64 files shown"; das Öffnen dauert nicht so lange,
dass das Gerät hängt (im Emulator 0,9 s). Ein Plugin weit hinten lässt sich mit dem Hauptrad laden.
Melden: ok, sonst Zahl der Seiten und wie lange das Öffnen dauert.

### 7.17 Fremdes Plugin

Das Flag "geprobt" entfernen:
`node tools/patch/probe-flag.mjs --clear eingabe.blech ausgabe.blech`, die Ausgabe nach
`KORG/blechtribe/Plugin/` legen und importieren.
Erwartet: das Plugin steht als Seite mit "WRITE=ALLOW" da und läuft nicht. WRITE: es läuft, die
Zustimmung steht in der Einstellungsdatei, und beim nächsten Start fragt es nicht mehr.
Melden: ok, sonst was angezeigt wird.

### 7.18 Fehlerfälle

(a) Karte ziehen und im Menü WRITE. (b) Eine beschädigte `e2sPlugin.all`
(letztes Byte ändern) auf die Karte legen und starten.
Erwartet: (a) "no card". (b) das Gerät startet normal, kein Plugin der Karte läuft (Blechy ist trotzdem da, 7.19).
Melden: ok je Fall, sonst Anzeige oder Verhalten.

### 7.19 Blechy, die letzte Seite des Rings

Mit der Karte aus 7.12 und ohne Karte (der Schritt gilt für beide).
Hauptbildschirm, MENU, EDIT bis Event (30/31), EDIT rechts: Blechy steht da, ohne Titel, ohne "press  [ Enter ]", der Seitenzähler
ist nicht zu sehen. Etwa eine Sekunde nach der Landung winkt er einmal (die Hand schwingt hin und her, gut anderthalb Sekunden),
dann steht er und zuckt ab und zu. EDIT rechts: das Pattern Menü (erste Seite); dort EDIT links: wieder Blechy, er winkt wieder.
EDIT links: Event. Wieder auf seine Seite, EXIT: der Hauptbildschirm. Auf der Seite: das Touchpad nahe an ihm antippen (wütend),
darüber wischen (froh), PLAY (er tanzt nach rund 12 Sekunden, mit den Achteln), STOP (die Sprechblase "wat machst'n du da atze?",
dann Spielzeit und Lieblingstempo). Er steht nicht unter GAMES oder PLUGINS, EXPORT ALL schreibt ihn nicht, und die
Einstellung RUNTIME auf OFF nimmt ihn nicht weg. Neustart mit gehaltenem EXIT: der Ring geht von Event direkt ins Pattern Menü,
die Zähler enden bei 29, er ist nicht da.
Erwartet: wie beschrieben, im Emulator gemessen (`tools/emu/blechy_cases.py`, `menu:blechy_*`), am Gerät offen. Dazu, nur Lesen:
im Terminal des Editors (`KORG.ram`, nur Lesen) `0xC0184000` bis `0xC01866D4` (9940 Byte) lesen und mit `data/script/blechy-block.hex`
vergleichen: der Block muss unverändert im Speicher stehen, auch nach Musik, Samples und Menü.
Melden: ok, sonst was die Seite zeigt, wie lange das Winken dauert und ob der Block im RAM abweicht.

## 8. Am Gerät bestätigt

| Punkt | Stand |
|---|---|
| Update mit einer Datei aus dem eigenen Patcher, danach zurück mit der gesicherten Datei | am Gerät bestätigt, 10.10. ([Messung](../messungen/2026-10-10-rueckweg-geuebt.md)) |
| EXIT beim Einschalten ist Bit 13 (`0x2000`), Startmodus 0 | am Gerät bestätigt, 10.10. |
| MFX 2 als erster Code-Patch: Update lief, Fingerabdrücke im RAM gleich der Datei, kein Knacken nach Gehör | am Gerät bestätigt, 13.10. ([Messung](../messungen/2026-10-13-mfx-umschalter-geraet.md)) |
| Eine laufende BLECH nimmt ihr Update aus `KORG/blechtribe/System/SYSTEM.VSB` | am Gerät bestätigt, 15.10. |
| Notschalter für den ganzen Satz, SysEx-Durchsatz über USB, Klang der HT-OSC-Oszillatoren, CATEGORY am Gerät | offen |
| Seitenzähler des Rings (Global, BLECH, Data Util, Event), der Gruppenliste ("BLECH 1/4") und das Schild mit dem Gruppennamen (7.7) | offen |
| Zeigen die unteren LEDs Helligkeitsstufen (die Firmware sendet Verläufe, ob die LEDs sie umsetzen, ist nicht geprüft, 7.9) | offen |
| Flimmern der Software-PWM des Display-Lichts (125 Hz, 7.10); ob am Prozessor ein PWM-Baustein an diese Pins führt, ist nicht nachgeschlagen | offen |
| Nimmt der Display-Baustein den Befehl `0xA7` an (DISPLAY INVERT, 7.11) | offen |
| Darstellung langer Dateinamen und Zeit der Dateiliste bei vielen Dateien (höchstens 8 Namen werden gemerkt) | offen |
| FatFs Lesen, Schreiben und Verzeichnis lesen in eigenem Code | offen ([karte.md](karte.md)) |
| Zeit je Rahmen am Gerät, Hörtest, Hintergrundlicht auf Batterie, LED-Sperre, das Menü in der Hand | offen |
| Blechy (7.19) und ob sein Block bei `0xC0184000` im RAM unverändert bleibt | offen |
| Schalter für das Startbild | gibt es nicht: das Startbild wird rund 290 ms vor dem Kartenzugriff gezeichnet |
| Ein/Aus auf dem Bildschirm "OK. Please Reboot." | offen |
| Verhalten der Firmware bei einem fehlerhaften oder abgebrochenen Update | offen |
| Ursache für die zurückgesetzten Globals vom 13.10. | offen |
