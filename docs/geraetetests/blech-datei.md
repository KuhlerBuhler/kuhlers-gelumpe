# Gerätetest: BLECH-Firmwaredatei

Stand 2026-10-15. Anleitung für Tester. Die Datei ist gebaut und im Emulator geprüft, am
Gerät ist davon nur das bestätigt, was in Abschnitt 7 so steht. Siehe auch die
[Übersicht](README.md).

## 1. Worum es geht

BLECH ist ein Satz von Patches für die eigene `SYSTEM.VSB` (Sampler 2.02 mit Hacktribe). Er
gibt der Electribe einen Startbild-Editor, MFX 2 auf TOUCH SCALE, eine Laufzeit für Plugins von
der SD-Karte und einen eigenen Menübildschirm "BLECH". Dieser Test spielt die Datei über DATA
UTILITY, SOFTWARE UPDATE auf und geht sie am Gerät durch.

Am Ende ist belegt: die Datei startet am Gerät, der Notschalter (EXIT beim Einschalten) schaltet
BLECH ab, das Menü BLECH, das Laden und Schreiben von Plugin-Dateien, der Import und die
Zustimmung für fremde Plugins laufen so wie im Emulator, und der Weg zurück zur Original-Datei
funktioniert auch mit BLECH.

Der Satz `data/patches/blech.json` besteht aus:

| Patch | Wirkung |
|---|---|
| `splash-editor` | Startbild Editor, Seite 20 im Global Menü |
| `mfx-switch` | MFX 2 auf TOUCH SCALE (liest jetzt den Schalter aus dem BLECH Menü) |
| `script-runtime` | Plugin-VM (API Version 5), Kartenlader, Display (nur für den Besitzer: offene App oder `korg.display.take()`), Apps, Werte, Uhr, Lesen, Handeln, LEDs, Hintergrundlicht, das BLECH Menü (Bildschirm `0x2D`, zwei Ebenen) mit der Anpassung (untere LEDs, Display-Licht) |
| `blechtribe` | Kartenordner `KORG/blechtribe` statt `KORG/hacktribe` |
| `splash` (Blech Startbild) | Datenpatch auf das Startbild |

Im Quelltext heißen Plugins noch `script`. Im Menü und auf der Karte heißen sie Plugin
([Plugins](../plugins.md)).

## 2. Warnung

**Das Gerät wird verändert.** Dieser Test schreibt eine geänderte Firmware in den Flash des
Geräts (SOFTWARE UPDATE schreibt `0x020000` bis `0x220000`, im Emulator so gemessen). Du machst
das auf eigenes Risiko, ohne Gewähr. Was passieren kann:

- Das Gerät hängt oder startet neu. Dann aus- und wieder einschalten, oder mit gehaltenem EXIT
  starten.
- Das Gerät startet mit BLECH nicht normal. Dann musst du die Original-Firmware neu aufspielen
  (Abschnitt 5).
- Hängt die Firmware vor der Update-Abfrage, ist das Gerät ohne JTAG nicht zu retten. Dagegen
  sind die Startwege im Emulator geprüft, am Gerät ist das nicht ausgeschlossen
  ([Patcher](../patcher.md), "Was kaputtgehen kann").
- Ein Hardwareschaden durch Software ist nicht bekannt, aber nicht ausgeschlossen.
- Daten gehen verloren, wenn das Update oder ein späteres Speichern gestört wird: am 13.10. standen
  die Globals nach Arbeit am Gerät auf der Vorgabe, die Ursache ist offen
  ([Messung](../messungen/2026-10-13-globals-zurueckgesetzt.md)). FACTORY RESET löscht Patterns und
  Globals und steht in DATA UTILITY direkt vor SOFTWARE UPDATE.

Korg-Daten werden nie hochgeladen. Die Datei `BLECH.VSB` enthält deine Firmware und bleibt bei dir.
Die Patcher-Seite verarbeitet sie im Browser, ohne Server. Gemeldet werden nur Textausgaben und
Prüfsummen.

## 3. Voraussetzungen

- Electribe 2 Sampler mit Firmware 2.02 und Hacktribe, Netzteil angeschlossen (Update nur am
  Netzteil, stabiler Strom).
- Die eigene `SYSTEM.VSB` (Hacktribe 2.02). Hast du nur Korgs Original 2.02, setzt die Seite Patcher BLECH
  direkt darauf ("BLECH direkt", im Emulator geprüft, am Gerät offen) oder wandelt sie mit Hacktribes
  `hacktribe-2.patch` um, die Datei holst du bei Hacktribe ([Patcher](../patcher.md)).
- SD-Karte im Gerät, Kartenleser am Rechner.
- Rechner mit Node 20 oder die App (die Seite Patcher). Für die Emulator-Prüfung die Python-Umgebung
  des Emulators (`npm run setup:emu`).
- Python 3 mit `mido` und das Gerät per USB für die lesenden Werkzeuge in `tools/device/`.
- Der Kartentest ist am Gerät bestanden: [karte.md](karte.md), alle Schritte.
- Ein Plugin zum Laden: die Beispiel-Plugins der Seite Plugins im Editor (Snake, Tetris und so weiter) und der Klicker aus `test/fixtures/scripts/klicker.js`.

## 4. Vorher sichern

1. **SD-Karte komplett kopieren.**
2. **Global-Block lesen** (nur Lesen, nie ab Adresse `0x1000000`):

   ```bash
   python3 tools/device/flash_dump.py --out <Datei> --start 0x230000 --length 0x4000
   ```

   Die ersten 256 Byte sind der Global-Block ([Speicherbereiche](../speicherbereiche.md),
   [Messung](../messungen/2026-10-13-globals-zurueckgesetzt.md)). Nach dem Update dasselbe in eine
   zweite Datei und die ersten 256 Byte vergleichen.
3. **Patterns und Samples sichern.** Die Samples liegen auf der Karte (`e2sSample.all`, also in
   der Kartenkopie). Die Patterns am Gerät mit EXPORT ALL PATTERN in DATA UTILITY, das legt eine
   `.e2sallpat`-Datei im Kartenordner ab.
4. **Die Original-Firmwaredatei** sichern, die jetzt läuft, und ihre Prüfsumme notieren
   (`shasum -a 256`). Das ist die Rückkehr-Datei aus Abschnitt 5. Nach dem Kopieren die Prüfsumme der
   Kopie auf der Karte nachlesen.
5. **Optional: den ganzen Flash** in einem Stand lesen
   (`python3 tools/device/flash_dump.py --out <Datei>`, zwei Durchgänge, rund 108 s je Durchgang). Der
   Dump enthält Korg-Daten und bleibt bei dir. Er dient auch der Emulator-Prüfung in Schritt 2.

## 5. Der Weg zurück

**Notschalter.** Beim Einschalten EXIT halten. EXIT hat keinen eigenen Startmodus, die Firmware
startet normal und legt die gehaltenen Tasten ab (Bit 13, `0x2000`, am Gerät bestätigt). Jeder
Haken von BLECH fragt das ab und gibt dann nur an die Original-Firmware weiter: kein Menü BLECH (der
Ring der Firmware läuft von Global direkt zu Data Util), keine Plugins, MFX 2 wie im Original. Das gilt
nur für diesen Start, nichts wird gespeichert. Datenpatches wirken weiter, auch das Blech Startbild
(es wird vor der Tastenabfrage gezeichnet). Der Notschalter hilft nicht gegen kaputte Startdaten,
DSP-Patches, kaputte gespeicherte Daten und Patches, die den Panel-Austausch stören
([Patcher](../patcher.md), "Notschalter", "Regeln"). Am Gerät bestätigt ist er für den MFX-2-Code-Patch
(13.10.), für den ganzen Satz nicht (offen).

**Original-Firmware zurückspielen**, wenn das Gerät noch startet (auch mit gehaltenem EXIT). So wurde
der Weg am 10.10. geübt: hin mit einer Datei aus dem eigenen Patcher, zurück mit der gesicherten
Datei, beides über SOFTWARE UPDATE ([Messung](../messungen/2026-10-10-rueckweg-geuebt.md)):

1. Die Original-`SYSTEM.VSB` (Rückkehr-Datei aus Abschnitt 4) auf die Karte legen: als
   `KORG/hacktribe/System/SYSTEM.VSB`. Das liest die laufende Hacktribe-Firmware. Eine laufende BLECH
   liest ihre Update-Datei aus `KORG/blechtribe/System/SYSTEM.VSB`: im Emulator gemessen
   ([Hintergrund](../hintergrund/virtuelle-sd.md), "Passt ein Datenpatch an derselben Stelle?"), am
   15.10. am Gerät gesehen. Die Datei gehört in den Ordner der Firmware, die gerade läuft.
2. Prüfsumme der Datei auf der Karte nachlesen, sie muss der notierten gleichen.
3. Karte ins ausgeschaltete Gerät, Netzteil, einschalten. DATA UTILITY, SOFTWARE UPDATE, die
   Versionsanzeige ansehen, bestätigen, den Abschluss abwarten, ausschalten. Gemessen wurde die
   Anzeige "Now 2.02, Next 2.02" im Emulator.
4. Das Gerät startet wieder mit dem alten Startbild (so am 10.10. am Gerät beobachtet).

Das Aufspielen läuft über Korgs eigenen Update-Weg, der eine laufende Anwendung voraussetzt. Er
beweist keine Wiederherstellung nach jedem Firmwarefehler
([Quellenprüfung](../messungen/2026-10-08-firmware-rueckweg.md)).

**Wenn das Gerät nicht mehr startet:**

- Es fragt beim Start nach einem Update ("SOFTWARE UPDATE, press ENTER"): laut Hacktribe-Doku kann
  eine passende Werksfirmware auf der Karte die Wiederherstellung ermöglichen, für den Sampler unter
  `KORG/electribe sampler/System/SYSTEM.VSB`. Dieser Weg ist am Gerät nicht geübt (offen). Im Emulator
  suchte die Abfrage `System/SYSTEM.VSB` an der Kartenwurzel ohne `KORG` und meldete "Error, Invalid
  File", der Grund ist offen ([Hintergrund](../hintergrund/virtuelle-sd.md), "Update beim Start").
- Es hängt ohne diese Abfrage: nach Hacktribes Anleitung nur JTAG/OpenOCD. Nichts weiter
  ausprobieren ([Quellenprüfung](../messungen/2026-10-08-firmware-rueckweg.md)).

**Kleinere Fälle:**

- Das Menü hängt oder zeigt Unsinn: EXIT, notfalls aus und mit gehaltenem EXIT wieder an (dann ist
  das Menü ganz aus).
- Ein Plugin macht Ärger: `Plugin/e2sPlugin.all` von der Karte nehmen, oder beim Start EXIT halten,
  oder im Menü auf der Seite PLUGINS OFF und WRITE.
- Globals weichen ab: nicht ausschalten, nicht WRITE. Den gesicherten Block als Global-Dump (`0x51`)
  senden, das speichert sofort. Den globalen MIDI-Kanal danach von Hand setzen, der Dump setzt ihn
  nicht. Ein fertiges Werkzeug dafür liegt nicht bei (offen).

## 6. Die Schritte

Alle Schritte zeigen "Erwartet" und eine Zeile "Melden". Markiert ist, was im Emulator gemessen und
was am Gerät noch offen ist. Hält ein Schritt nicht, was er erwartet: aufhören, nichts weiter
probieren, Ausgabe und Display notieren.

1. **Datei bauen.** Aus der eigenen `SYSTEM.VSB`, entweder aus dem Quelltext

   ```bash
   node tools/patch/apply.mjs --vsb <eigene SYSTEM.VSB> --set data/patches/blech.json --out BLECH.VSB
   ```

   oder mit der Patch-Datei des Releases

   ```bash
   node tools/patch/apply.mjs --vsb <eigene SYSTEM.VSB> --patch BLECH.patch --out BLECH.VSB
   ```

   oder mit der Seite Patcher (baut aus demselben Satz dieselbe Datei, byteweise gleich `apply.mjs
   --set`, gemessen an der eigenen Datei und an Hacktribes 2.02-Datei). Die Original-Datei wird nie
   verändert.
   Erwartet: "wrote BLECH.VSB (2097408 bytes)" mit einer SHA-256, die du notierst. Die Prüfsumme hängt
   von deiner Ausgangsdatei ab (hergeleitet: die Ausgabe trägt deren Daten, etwa die FX-Presets),
   sie gleicht darum nicht der Prüfsumme anderer Dateien.
   Melden: ok mit den ersten 8 Zeichen der SHA-256, sonst die Ausgabe.

2. **Im Emulator prüfen.** `apply.mjs` druckt am Ende die Zeile für die Prüfung mit allen
   `--allow` und `--allow-code` Angaben. Ausführen (mit Flash-Dump als `--flash`, wenn vorhanden). Die
   Seite Patcher macht diese Prüfung selbst und gibt den Download erst danach frei, sie dauert einige
   Minuten.
   Erwartet: alle Prüfungen bestanden: 191 von 191 mit Flash-Dump (am 15.10. mit der Datei v18b so gemessen), darunter alle
   Startwege, die Menüfälle mit der Anpassung und der Seite von Blechy, die Fälle des Startbild Editors und von MFX 2.
   Melden: ok mit der Zahl, sonst die fehlgeschlagenen Prüfungen. Bei einer Abweichung nicht weiter.

3. **Kartenordner kopieren, nicht umbenennen.** `KORG/hacktribe/` nach `KORG/blechtribe/` kopieren
   (mit `Sample/`, `System/` und so weiter, der alte Ordner bleibt für die Original-Firmware). Nach
   dem Update liest BLECH nur noch `KORG/blechtribe/`, sonst sind die Samples weg: im Emulator
   sah der Slot leer aus, die Karte blieb unverändert. Darin `KORG/blechtribe/Plugin/` anlegen, falls
   er nicht schon aus dem Kartentest da ist (die Testdateien `FSTEST.*` dort entfernen). Im
   Emulator kopierst du den Ordner selbst (Feld SD-Karte, "Öffnen").
   Erwartet: `KORG/blechtribe/` mit demselben Inhalt wie `KORG/hacktribe/` und dem Ordner `Plugin/`.
   Melden: ok.

4. **Datei auf die Karte.** `BLECH.VSB` als `KORG/hacktribe/System/SYSTEM.VSB` auf die Karte (die
   laufende Hacktribe-Firmware liest noch den alten Ordner; bei der originalen Korg-Firmware ist es
   `KORG/electribe sampler/System/SYSTEM.VSB`, Original-Datei vorher gesichert, Abschnitt 4). Karte in
   das ausgeschaltete Gerät, Netzteil. Die Prüfsumme der Datei auf der Karte nachlesen.
   Erwartet: Prüfsumme gleich der aus Schritt 1.
   Melden: ok.

5. **Update.** DATA UTILITY, SOFTWARE UPDATE (in der Liste steht direkt davor FACTORY RESET,
   das nicht bestätigen), Version ansehen, bestätigen, Abschluss abwarten ("OK. Please Reboot."), ausschalten.
   Erwartet: das Update läuft durch, wie am 10.10. beim Hin und Zurück. Im Emulator reagierte die
   Ein/Aus-Taste auf diesem Bildschirm nicht; ob das Gerät sich ebenso verhält, ist offen.
   Melden: ok, sonst was das Display zeigt.

6. **Start ohne Plugins.** Einschalten. Danach `python3 tools/device/led_inventory.py --identify`
   (nur Lesen) und denselben Aufruf mit `--emu BLECH.VSB` im Emulator, beide Ausgaben vergleichen.
   Den Global-Block erneut lesen und mit der Sicherung vergleichen.
   Erwartet: Blech Startbild, Hauptbildschirm, MFX 2 wie in der [MFX-2-Messung](../messungen/2026-10-13-mfx-umschalter-geraet.md)
   (MASTER FX gibt die MFX des Patterns, TOUCH SCALE schaltet auf MFX 2), die Samples sind da. Die
   Fingerabdrücke gleichen sich (hergeleitet: bei MFX 2 allein haben sie am Gerät der Datei
   gleich gesehen, welche Werte für den ganzen Satz gelten, ist offen). Globals unverändert.
   Melden: ok, sonst beide Fingerabdruck-Ausgaben und was abweicht.

7. **Notschalter.** Neustart mit gehaltenem EXIT.
   Erwartet: normaler Start, im Edit Ring kommt nach Global direkt Data Util ("28/29"), kein Menü BLECH.
   Das Blech Startbild erscheint trotzdem. Im Emulator gemessen, am Gerät offen für den ganzen Satz.
   Melden: ok, sonst was das Display zeigt.

8. **Das Menü ansehen.** Hauptbildschirm, MENU, mit EDIT rechts nach Global ("27/31"), EDIT rechts:
   eine einzige Seite "BLECH 28/31" mit dem Titel BLECH und der Zeile "press  [ Enter ]", so wie danach Data Util
   ("29/31"). Zurück mit EDIT links. ENTER (die Taste MENU) öffnet die Liste der Gruppen: "BLECH 1/3" FEATURES, dann mit
   EDIT rechts CUSTOMIZATION, PLUGINS (GAMES und TOOLS kommen dazu, wenn eine App der Gruppe geladen ist, die Zähler zählen dann
   bis 5; eine Gruppe ABOUT gibt es nicht),
   jede mit "press  [ Enter ]". ENTER auf FEATURES zeigt die vier Schalter MFX 2, PATTERN CONFIRM, TAP MOTION und NOTE ASSIST
   mit Wert (ON) statt "press  [ Enter ]" (Schild "Feature"). ENTER auf einer Gruppe zeigt ihre Seiten: das Schild oben links nennt sie ("Plugins 1/5"),
   der Zähler zählt nur ihre Seiten, EDIT blättert im Kreis. EXIT geht immer eine Ebene zurück (Seiten, Liste, Ring,
   Hauptbildschirm), MENU auf dem Hauptbildschirm kommt wieder auf die zuletzt benutzte Seite. WRITE auf einer Seite
   darf kein Fenster "Pattern schreiben" öffnen. Auf jeder Seite stehen Titel, Wert und Schild klar lesbar, nichts liegt
   übereinander und kein Schild ist abgeschnitten ("Custom 1/8" mit ganzem m, der Fehler von v13).
   Erwartet: wie beschrieben, im Emulator gemessen (Ring, ENTER, EXIT, WRITE, MENU, alle 48 Tasten ohne
   Assertion, kein Text über einem anderen, jedes Schild vor seinem Zähler ganz). Der Seitenzähler am Gerät ist offen
   (siehe Abschnitt 7). Bilder aus dem Emulator: `docs/images/blech-menue-v14/00-all.png` (nur lokal, nicht im Repo).
   Melden: ok, sonst Seitenzähler und Anzeige der Seiten, am besten mit Foto.

9. **Einstellungen.** Gruppe FEATURES, Seite MFX 2: Hauptrad auf OFF, der Wert zeigt "OFF, RESTART". WRITE:
   "saved". Ausschalten, die Karte am Rechner ansehen: `KORG/blechtribe/settings.b.bin` ist 24 Byte
   groß. Wieder einschalten. Danach wieder ON und WRITE.
   Erwartet: nach dem Neustart ist MFX 2 aus, TOUCH SCALE verhält sich wie im Original.
   Melden: ok, sonst die Anzeige und die Dateigröße.

10. **Anpassung: untere LEDs.** Netzteil angeschlossen. Gruppe CUSTOMIZATION (ENTER), Seite BOTTOM LEDS: Hauptrad auf
    COLOR, dann auf den Seiten LED HUE, SAT, BRIGHT die Farbe verstellen (HUE einmal rundum, SAT und BRIGHT 0 bis 15), auch ganz hoch und
    ganz niedrig, dann die Seite BOTTOM LEDS auf OFF und auf METER. Dabei Musik laufen lassen. WRITE.
    Erwartet: jede Änderung sieht man sofort an den vier unteren LEDs. COLOR leuchtet fest in der
    Farbe, OFF dunkel, METER mit Farbe wird mit dem Pegel heller und dunkler, ohne Farbe (STOCK) ist
    es die Pegelanzeige wie vorher. Sieht man Zwischenstufen bei den Pegeln, nehmen die LEDs Helligkeit an;
    sieht man nur an und aus, ist das so zu melden (offen, siehe Abschnitt 7). Nach dem Neustart ist die Wahl
    noch da. Im Global-Menü Power Save auf "Always": die LEDs gehen aus, auch bei COLOR.
    Melden: ok, sonst was zu sehen ist, besonders die Stufen und die Farben.

11. **Anpassung: Display-Licht.** Gruppe CUSTOMIZATION, Seiten BACKLIGHT HUE, SAT, BRIGHT. Erst HUE einmal rundum bei voller
    SAT und BRIGHT, dann Mischungen mit niedriger SAT und BRIGHT, auch sehr niedrige (1 bis 3). WRITE.
    Erwartet: die Farbe ändert sich sofort. Pegel 0 und 15 sind feste Farben ohne Software-PWM. Bei Pegeln
    dazwischen steuert die Firmware das Licht mit einer PWM (8 ms): am Gerät darauf achten, ob es flimmert
    (mit dem Auge, mit der Handykamera, beim Bewegen der Augen) und ob alle Kanäle gleich hell stufen.
    Alle drei auf 0 ist das Weiß der Firmware, die Anzeige ist lesbar. Nach dem Neustart ist die Wahl noch da.
    Power Save "Always" dimmt das Licht wie ohne BLECH. Flimmert es, kommen nur die Pegel 0 und 15 (acht
    Farben, keine PWM) in den Patch.
    Melden: ok, sonst was zu sehen ist (Flimmern ja oder nein, Stufen, Lesbarkeit).

11b. **Display umkehren.** Gruppe CUSTOMIZATION, Seite DISPLAY INVERT ("Custom 8/9"): Hauptrad auf ON, dann auf OFF, dann
    wieder ON, WRITE, MENU verlassen (EXIT), Hauptbildschirm ansehen, ausschalten und neu starten.
    Erwartet: bei ON werden helle Punkte dunkel und dunkle hell, sofort, am Menü und am Hauptbildschirm, bei OFF ist alles
    wie vorher; nach dem Neustart ist es noch an. Neustart mit gehaltenem EXIT: Display normal. **Das ist ein Test, ob der
    Display-Baustein den Befehl `0xA7` annimmt** (Annahme, Baustein nicht geprüft): bleibt das Display bei ON unverändert,
    sagt das hier, dann bekommt die Seite eine Umkehrung in Software.
    Melden: ok, sonst was das Display bei ON zeigt (unverändert, Müll, umgekehrt nur teilweise).

12. **Plugin laden.** Im Editor auf der Seite Plugins den Quelltext von `test/fixtures/scripts/klicker.js` als eigenes Plugin "klicker" einfügen, proben, "Alle
    speichern (e2sPlugin.all)", die Datei nach `KORG/blechtribe/Plugin/` auf die Karte, neu starten.
    Erwartet: der Hauptbildschirm bleibt unverändert, die Patterns sind zu sehen (das Laden zeichnet nichts).
    Der Klicker ist eine App: im Menü steht unter TOOLS > "Klicker" ("ENTER=OPEN"), unter PLUGINS eine Seite
    "klicker" (ON, mit dem Hauptrad OFF und wieder ON), kein Blechy darunter. TOOLS, ENTER: der Bildschirm der App
    zeigt "Klicks 0", TAP zählt und leuchtet. EXIT: der normale Hauptbildschirm ist zurück, mit den Patterns.
    TAP zählt auch bei geschlossener App (die LED), ENTER öffnet sie wieder mit dem Stand.
    Melden: ok, sonst was passiert und was das Display zeigt.

13. **Snake.** Dasselbe mit Snake, dabei Musik laufen lassen. Snake ist eine App unter GAMES: nach dem Laden zeigt
    das Gerät wie vorher seinen Hauptbildschirm, GAMES, ENTER öffnet das Spiel (neues Spiel bei jedem Öffnen),
    gesteuert mit ◄ Part und Part ►, EXIT beendet es und der normale Bildschirm ist zurück. Solange Snake offen ist,
    ändern ◄ Part und Part ► die gewählte Part der Firmware nicht (im Emulator gemessen, `snake-part-tasten-aendern-die-part-nicht`);
    nach EXIT ändern sie die Part wieder (`part-tasten-nach-exit-wieder-der-firmware`).
    PLAY, STOP und REC erreichen die Firmware auch bei offener App: PLAY startet das Pattern, STOP hält es an
    (`app-offen-play-stop-erreichen-die-firmware`), die App sieht beide Tasten ebenfalls.
    Erwartet: kein Knacken und kein Stocken des Sequencers, nach Gehör; EXIT geht jederzeit.
    Melden: ok, sonst was zu hören ist und bei welcher Tätigkeit.

14. **EXPORT ALL.** Menü, Gruppe PLUGINS, Seite EXPORT ALL (sieht aus wie IMPORT SAMPLE: Titel, "press  [ Enter ]"), ENTER oder WRITE.
    Erwartet: "1 exported" (oder die Zahl der Plugins) als Wert der Seite. Auf der Karte am Rechner ist `e2sPlugin.all`
    gleich groß und gleich dem, was vorher drauf war.
    Melden: ok, sonst die Meldung des Geräts und die Größen.

15. **IMPORT PLUGIN.** Ein `.blech` aus dem Editor ("Als .blech speichern") nach
    `KORG/blechtribe/Plugin/` legen (auf einem Mac liegen dort oft auch `._Name.blech` Dateien), am Gerät im Menü, Gruppe
    PLUGINS, die Seite IMPORT PLUGIN öffnen (sie sieht aus wie IMPORT SAMPLE). ENTER zeigt den ersten Dateinamen, das
    Hauptrad oder EDIT blättert Datei für Datei, ENTER oder WRITE lädt die gezeigte, EXIT geht zurück auf die Seite.
    Erwartet: nur echte Plugin Dateien stehen in der Liste (keine mit Punkt am Anfang, kein "Upper Folder"), die gezeigte
    Datei zeigt "imported", das Plugin läuft sofort, eine neue Seite für das Plugin ist da (hat es eine App, steht sie
    unter GAMES oder TOOLS). IMPORT PLUGIN steht nicht unter DATA UTILITY, siehe [Plugins](../plugins.md), "Stand".
    Melden: ok, sonst Meldung und Anzeige.

16. **Fremdes Plugin.** Das Flag "geprobt" entfernen:
    `node tools/patch/probe-flag.mjs --clear eingabe.blech ausgabe.blech`, die Ausgabe nach
    `KORG/blechtribe/Plugin/` legen und importieren.
    Erwartet: das Plugin steht als Seite mit "WRITE=ALLOW" da und läuft nicht. WRITE: es läuft, die
    Zustimmung steht in der Einstellungsdatei, und beim nächsten Start fragt es nicht mehr.
    Melden: ok, sonst was angezeigt wird.

17. **korg.menu.add.** Im Editor ein Plugin mit diesem Text anlegen, proben, exportieren, laden:

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

    Erwartet: im Menü, Gruppe PLUGINS, steht eine Seite "Speed" mit 5, das Hauptrad ändert die Zahl (zwischen 1 und
    10); TOOLS > Speed, ENTER öffnet die App, sie zeigt die geänderte Zahl (hergeleitet aus dem
    Beispiel, im Emulator gemessen ist nur, dass das Plugin das Ereignis bekommt).
    Melden: ok, sonst was die Seite und das Display zeigen.

18. **Fehlerfälle.** (a) Karte ziehen und im Menü WRITE. (b) Eine beschädigte `e2sPlugin.all`
    (letztes Byte ändern) auf die Karte legen und starten.
    Erwartet: (a) "no card". (b) das Gerät startet normal, kein Plugin der Karte läuft (Blechy ist trotzdem da, Schritt 20).
    Melden: ok je Fall, sonst Anzeige oder Verhalten.

19. **Display nehmen.** Im Editor ein Plugin mit diesem Text anlegen, proben, exportieren, laden:

    ```js
    korg.onEvent("buttonPress", (key) => {
      if (key == korg.key.PLAY && korg.display.take()) korg.display.text("PLAY aktiv", 0, 0);
    });
    ```

    Erwartet: nach dem Laden bleibt das Display das der Firmware. PLAY zeigt "PLAY aktiv" auf dem Display, EXIT
    bringt den normalen Hauptbildschirm zurück, auch wenn das Plugin die Taste gar nicht abfragt.
    Melden: ok, sonst was angezeigt wird.

20. **Blechy, die letzte Seite des Rings.** Mit der Karte aus dem Schritt 12 und ohne Karte (der Schritt gilt für beide).
    Hauptbildschirm, MENU, EDIT bis Event (30/31), EDIT rechts: Blechy steht da, ohne Titel, ohne "press  [ Enter ]", der Seitenzähler
    ist nicht zu sehen. Etwa eine Sekunde nach der Landung winkt er einmal (die Hand schwingt hin und her, gut anderthalb Sekunden),
    dann steht er und zuckt ab und zu. EDIT rechts: das Pattern Menü (erste Seite); dort EDIT links: wieder Blechy, er winkt wieder.
    EDIT links: Event. Wieder auf seine Seite, EXIT: der Hauptbildschirm. Auf der Seite: das Touchpad nahe an ihm antippen (wütend),
    darüber wischen (froh), PLAY (er tanzt nach rund 12 Sekunden, mit den Achteln), STOP (die Sprechblase "wat machst'n du da atze?",
    dann Spielzeit und Lieblingstempo). Er steht nicht unter GAMES oder PLUGINS, EXPORT ALL schreibt ihn nicht, und die
    Einstellung RUNTIME auf OFF nimmt ihn nicht weg. Neustart mit gehaltenem EXIT: der Ring geht von Event direkt ins Pattern Menü,
    die Zähler enden bei 29, er ist nicht da.
    Erwartet: wie beschrieben, im Emulator gemessen (`tools/emu/blechy_cases.py`, `menu:blechy_*`), am Gerät offen. Dazu, nur Lesen:
    im Terminal des Editors (`KORG.ram`, nur Lesen) `0xC0184000` bis `0xC0186F7C` (12668 Byte) lesen und mit `data/script/blechy-block.hex`
    vergleichen: der Block muss unverändert im Speicher stehen, auch nach Musik, Samples und Menü.
    Melden: ok, sonst was die Seite zeigt, wie lange das Winken dauert und ob der Block im RAM abweicht.

21. **BLECH SysEx: RAM lesen und schreiben in Blöcken, Durchsatz messen.** Der Patch `blech-sysex` gibt dem Gerät eigene Befehle
    `0x60` bis `0x63` ([Messung](../messungen/2026-10-15-blech-sysex.md)). Am Rechner, Gerät per USB, ohne dass der Editor im Browser
    dieselbe Schnittstelle offen hat:

    ```bash
    python3 tools/device/blech_sysex_probe.py --repeat 5
    ```

    Das Werkzeug fragt INFO und liest `0xC0000100` in Blöcken von 256 bis 32768 Byte, prüft jeden Block gegen die CRC-32 des Geräts und
    druckt Millisekunden und KiB/s je Größe. Es schreibt nichts. Bricht es bei einer Größe ab, ist die Größe darunter der größte sichere Block.
    Danach in der Seite "Mit Electribe verbinden": im Bereich Gerät steht "RAM über MIDI: BLECH, Blöcke bis 32768 Byte".
    Mit EXIT beim Einschalten bleibt dieselbe Abfrage ohne Antwort, die Seite fällt auf Hacktribes Befehle zurück (steht dort
    "Hacktribe") oder bleibt lesend.
    Erwartet: INFO mit Version 1, Flags `0xF`, größter Block 32768, Tabellen-CRC `0x662EEC2A`; alle Blöcke mit passender CRC. Im
    Emulator über DIN schafft ein Block 2,6 KiB/s, das ist die Leitung; über USB wird deutlich mehr erwartet (geschätzt, bei Hacktribe
    waren es 200 KiB/s für Blöcke von 16384 Byte). Ob die Warteschlange des USB-Eingangs 32 KiB ohne Verlust nimmt, ist offen.
    Melden: ok mit der Ausgabe des Werkzeugs, sonst die Größe, bei der es abbricht, und die Meldung.

22. **BLECH FLASH READ: den Flash lesen (blaue Electribe 2, Sampler mit BLECH).** Für alle, die eine Electribe mit BLECH SysEx haben, besonders für die blaue Electribe 2
    (Synth), von der es bisher keine Sicherung des Flash gibt. Der Befehl `0x64` liest den Flash nur, es gibt keinen, der ihn schreibt oder löscht
    ([Messung](../messungen/2026-10-15-blech-sysex.md), "FLASH READ"). Voraussetzung: eine Firmware mit dem SysEx-Patch (Sampler: der BLECH-Satz; Synth: `data/patches/blech-synth.json`,
    `node tools/patch/apply.mjs --vsb SYSTEM.VSB --set data/patches/blech-synth.json --out BLECH-SYNTH.VSB`), Gerät per USB, kein Editor im Browser offen, Netzteil dran,
    nichts am Gerät bedienen, solange das Werkzeug läuft.

    **Die Firmware der blauen aufspielen** (im Emulator so gemessen, [Messung](../messungen/2026-10-15-blaue-electribe.md), "SOFTWARE UPDATE der blauen Electribe 2"):

    1. Vorher die Original-`SYSTEM.VSB` der blauen (Version 2.02) auf den Rechner sichern, sie ist der Weg zurück. Karte sichern.
    2. Auf der Karte den Ordner **`KORG/electribe/System/`** anlegen (so sucht die Firmware, nicht `hacktribe` und nicht `blechtribe`) und `BLECH-SYNTH.VSB` dort als
       **`SYSTEM.VSB`** ablegen. In diesem Ordner darf **keine andere Datei** liegen, besonders kein `BOOT.VSB`, `USER.VSB` oder `PCM.VSB`: die Firmware fragt nach allen vieren,
       und was sie damit tut, ist nicht gemessen.
    3. Netzteil anschließen (mit Batterie lehnt das Gerät ab), Karte einlegen, einschalten.
    4. MENU, zweimal EDIT-Regler nach links, MENU: "Data Util". Den Regler zehnmal nach rechts: letzte Seite, "SOFTWARE UPDATE".
    5. MENU: "Now Version 2.02, Next Version 2.02". MENU: "Are You Sure ?". MENU: "Working...". Warten, bis "OK. Please Reboot." steht, währenddessen nichts drücken
       und den Strom nicht trennen. Dann aus- und wieder einschalten. Erwartet: das Gerät startet zum Hauptbildschirm.
    6. Danach der Test unten. Es werden nur `[0x020000, 0x220000)` beschrieben, die PCM-Bank und die Nutzerdaten bleiben (im Emulator Byte für Byte gleich).
    7. **Zurück:** die gesicherte Original-`SYSTEM.VSB` in denselben Ordner (`KORG/electribe/System/SYSTEM.VSB`, die laufende v22-synth liest denselben Ordner), dieselben Schritte 3 bis 5.
       Erwartet: das Original startet zum Hauptbildschirm, INFO und FLASH READ antworten nicht mehr. Hängt das Gerät oder startet nicht: mit gehaltenem EXIT einschalten
       und das Update mit der Original-Datei wiederholen.

    ```bash
    python3 tools/device/blech_sysex_probe.py --repeat 2                                        # INFO: Flags 0xF, Flash-Block 4096
    python3 tools/device/blech_flash_dump.py --out ~/blaue-electribe-flash.bin --start 0x220000 --length 0x8000   # ein kleiner Anfang
    python3 tools/device/blech_flash_dump.py --out ~/blaue-electribe-flash-voll.bin             # der ganze Flash, zwei Läufe
    ```

    Das Werkzeug liest in Blöcken zu 4096 Byte von 0 bis höchstens `0x1000000`, prüft jeden Block gegen seine CRC-32, liest alles zweimal und schreibt die Datei nur, wenn
    beide Läufe gleich sind. Es lehnt einen Pfad in einem Git-Arbeitsverzeichnis ab (die Datei enthält Korg-Daten und gehört nirgends in ein Repository). Der ganze Flash dauert
    einige Minuten. Bricht es ab, meldet es die Adresse und den Grund; ein Schweigen des Geräts wird nicht wiederholt, dann das Gerät aus- und einschalten.
    Erwartet: der kleine Lauf (ab `0x220000`) zeigt am Anfang die Kennung der Nutzerdaten, beim Synth `KORGelec2USR`, beim Sampler `KORGele2sUSR`; der volle Lauf endet mit "written"
    und einer SHA-256 je Lauf, die gleich sind; die Datei hat genau 16.777.216 Byte. Mit EXIT beim Einschalten bleibt das Werkzeug beim INFO stehen ("no BLECH SysEx").
    Melden: ok mit der SHA-256 und der Dauer, sonst die Meldung und die Adresse. Die Datei **nicht** weitergeben ohne Rücksprache, sie enthält Korgs Firmware und Daten;
    bei der blauen Electribe brauchen wir daraus nur, ob der Bereich ab `0x800000` die PCM-Bank im erwarteten Aufbau trägt (`tools/emu/synth_probe.py bank DATEI` auf dem eigenen Rechner).

Nach dem Test das Ergebnis je Schritt notieren: ok, anders, nicht gelaufen.

## 7. Ergebnisse und Messungen

Alle Angaben ohne Gerät sind im Emulator gemessen, mit der echten Firmware und einer virtuellen Karte.

| Punkt | Stand | Datum, Beleg |
|---|---|---|
| Update über Karte und SOFTWARE UPDATE mit einer Datei aus dem eigenen Patcher (Startbild als Datenpatch), danach zurück mit der gesicherten Datei | am Gerät bestätigt | 10.10., [Messung](../messungen/2026-10-10-rueckweg-geuebt.md) |
| EXIT beim Einschalten ist Bit 13 (`0x2000`), Startmodus 0 | am Gerät bestätigt | 10.10., ebenda |
| Hintergrundlicht-Pins per Execute schaltbar (Grundlage von `korg.backlight`) | am Gerät bestätigt | 10.10., [Startphase](../messungen/2026-10-10-startphase.md) |
| MFX 2 als erster Code-Patch am Gerät: Update lief, Fingerabdrücke im RAM gleich der Datei, MFX 2 je Pattern, Patternwechsel, WRITE ändert die MFX des Patterns nicht, kein Knacken nach Gehör | am Gerät bestätigt | 13.10., [Messung](../messungen/2026-10-13-mfx-umschalter-geraet.md) |
| Notschalter (EXIT) schaltet den MFX-2-Code-Patch ab, das Blech Startbild erscheint trotzdem | am Gerät bestätigt | 13.10., ebenda |
| Prüfungen im Emulator: 191 von 191 mit Flash-Dump, alle Startwege, Menüfälle mit der Anpassung und der Seite von Blechy, Startbild Editor, MFX 2, Power-Off-Bild auch von seiner Seite aus (Datei v18b, SHA-256 beginnt mit b0f1f5f0) | im Emulator gemessen, am Gerät offen | 15.10., [Menü](../messungen/2026-10-14-blech-menue.md), `tools/emu/check.py` |
| Menü BLECH mit drei Ebenen (Ring, Gruppen ohne ABOUT, Seiten, Optik von Data Util, Schilder ganz, versteckte Dateien fehlen in der Importliste): Ring und Zähler, ENTER, EXIT, WRITE, MENU, 48 Tasten, EXIT beim Einschalten, Einstellungen, Plugin-Seiten, EXPORT ALL, IMPORT PLUGIN, fremde Plugins, `korg.menu.add`; keine Seite zeichnet Text über Text | im Emulator gemessen, am Gerät offen | 15.10., [Menü](../messungen/2026-10-14-blech-menue.md) |
| Apps: Laden zeichnet nichts, öffnen aus dem Menü, EXIT, der Hauptbildschirm kommt Pixel für Pixel zurück, EXIT lässt sich nicht abfangen, `korg.display.take()` | im Emulator gemessen, am Gerät offen | 15.10., [Apps](../messungen/2026-10-14-plugin-apps.md) |
| IMPORT PLUGIN und EXPORT ALL unter DATA UTILITY | nicht gebaut | [Plugins](../plugins.md), "Stand" |
| Kartenlader für `e2sPlugin.all` (Datei, Block mit falscher Prüfsumme, falsche Kennung, halbierte Datei, EXIT) | im Emulator gemessen, am Gerät offen | 14.10., [Messung](../messungen/2026-10-14-skript-karte.md) |
| Update-Datei der laufenden BLECH unter `KORG/blechtribe/System/SYSTEM.VSB`, unter dem alten Pfad "Error, No File" | im Emulator gemessen; die Datei im Ordner `blechtribe` nahm eine laufende BLECH am 15.10. am Gerät als Update | [Hintergrund](../hintergrund/virtuelle-sd.md) |
| Karte ohne `KORG/blechtribe/`: Slot leer, Karte bleibt unverändert, Samples sind weg bis der Ordner kopiert ist | im Emulator gemessen, am Gerät offen | [Hintergrund](../hintergrund/virtuelle-sd.md) |
| FatFs Lesen, Schreiben und Verzeichnis lesen in unserem Code | offen | [karte.md](karte.md) |
| Zeit je Rahmen am Gerät, Hörtest, Hintergrundlicht auf Batterie, LED-Sperre, das Menü in der Hand | offen | |
| Darstellung langer Dateinamen und Zeit der Dateiliste bei vielen Dateien (höchstens 8 Namen werden gemerkt) | offen | [Menü](../messungen/2026-10-14-blech-menue.md) |
| Seitenzähler des Rings (Global "27/31", BLECH "28/31", Data Util "29/31", Event "30/31"), der Gruppenliste ("BLECH 1/3") und das Schild mit dem Gruppennamen am Gerät | offen | |
| Blechy in BLECH eingebaut, letzte Seite des Rings: ohne Karte geladen, Block im Abbild bei `0xC0184000` außerhalb des Pools, winkt nach etwa einer Sekunde einmal je Landung, antippen, streicheln, Tanz, Sprechblase, EDIT und EXIT blättern weg, mit EXIT beim Einschalten nicht da, kein Plugin der Karte (nicht in den Listen, nicht exportiert) | im Emulator gemessen, am Gerät offen (auch ob der Platz bei `0xC0184000` frei bleibt) | 15.10., [Messung](../messungen/2026-10-15-blechy.md) |
| BLECH SysEx (`0x60` bis `0x63`): INFO, Lesen und Schreiben bis 32768 Byte mit CRC-32, Verweigerung geschützter Bereiche, stumm mit EXIT beim Einschalten, auf Hacktribe und auf Korgs Original | im Emulator gemessen über DIN (2,6 KiB/s, die Leitung ist die Grenze), am Gerät offen (Durchsatz über USB, größter sicherer Block) | 15.10., [Messung](../messungen/2026-10-15-blech-sysex.md), Schritt 21 |
| Anpassung: untere LEDs (METER, COLOR, OFF, Farbe) und Display-Licht (Pegel 0 bis 15, Software-PWM) samt Datei, Power Save, EXIT beim Einschalten | im Emulator gemessen, am Gerät offen | 14.10., [Anpassung](../messungen/2026-10-14-blech-anpassung.md) |
| Zeigen die unteren LEDs am Gerät Helligkeitsstufen (die Firmware sendet Verläufe, ob die LEDs sie umsetzen, ist nicht geprüft) | offen | [Anpassung](../messungen/2026-10-14-blech-anpassung.md) |
| Flimmern der Software-PWM des Display-Lichts (125 Hz) am Gerät; ob am Prozessor ein PWM-Baustein an diese Pins führt, ist nicht nachgeschlagen | offen | [Anpassung](../messungen/2026-10-14-blech-anpassung.md) |
| Schalter für das Startbild | gibt es nicht (das Startbild wird rund 290 ms vor dem Kartenzugriff gezeichnet) | [Menü](../messungen/2026-10-14-blech-menue.md) |
| Ein/Aus auf dem Bildschirm "OK. Please Reboot." am Gerät | offen | [Messung](../messungen/2026-10-13-globals-zurueckgesetzt.md) |
| Rettung, wenn die laufende Firmware nicht mehr startet; ob die Datei unter `KORG/electribe sampler/System/` dafür taugt | offen | [Messung](../messungen/2026-10-10-rueckweg-geuebt.md), [Quellenprüfung](../messungen/2026-10-08-firmware-rueckweg.md) |
| Verhalten der Firmware bei einem fehlerhaften oder abgebrochenen Update | offen | [Hintergrund](../hintergrund/virtuelle-sd.md) |
| Ursache für die zurückgesetzten Globals vom 13.10. | offen | [Messung](../messungen/2026-10-13-globals-zurueckgesetzt.md) |
