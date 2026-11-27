# Offene Gerätetests

Geräteschritte, die vorbereitet, aber am Gerät noch nicht gelaufen sind. Jeder Abschnitt nennt, was er klären soll,
woher die Erwartung kommt, und die Schritte. Die Messnotizen, aus denen sie stammen, sind in der Git-Geschichte lesbar
(`git show 03c7827adc7b:docs/messungen/<datei>`).

Für alle gilt [Was für alle Tests gilt](README.md#was-für-alle-tests-gilt): Netzteil, vorher sichern, Ergebnis je
Schritt als "ok", "anders" oder "nicht gelaufen". Schritte, die den RAM schreiben (Abschnitt 2), sind eine Änderung am
laufenden Gerät und brauchen vorher eine ausdrückliche Freigabe.

## 1. MFX 2: GATE ARP, laufende Sequenz, MFX HOLD

Die Schritte 1 bis 6 des MFX-2-Tests liefen am 13.10. am Gerät ([blech-datei.md](blech-datei.md), Abschnitt 8). Diese
drei fehlen. Voraussetzung: Firmware mit dem BLECH-Satz, MFX 2 an (BLECH > FEATURES > MFX 2), ein Pattern mit eigenem
Master-Effekt.

1. GATE ARP drücken, einmal aus Master FX, einmal aus MFX 2, einmal aus Touch Scale. **Erwartet:** nur die
   GATE-ARP-LED leuchtet, TOUCH SCALE und MASTER FX sind dunkel. Ein kurzes Aufblitzen der TOUCH-SCALE-LED beim Druck
   ist ein Befund (der Patch löscht sie im selben Tastenereignis). Bei laufender Sequenz ein Trigger-Pad halten und das
   Touchpad berühren: das Pad wird je Schritt ausgelöst, dazu ein Skalenton, wie bei Gate Arp + Touch Scale der
   Firmware. Noch einmal GATE ARP: nichts ändert sich. MFX 2 geht mit GATE ARP aus, der eigene Effekt kommt zurück.
   SHIFT + TOUCH SCALE: Touch Scale allein (TOUCH-SCALE-LED an), MFX 2 geht dabei aus.
2. Alles aus Schritt 1 und das Umschalten zwischen MASTER FX und TOUCH SCALE bei laufender Sequenz, auf Knackser
   hören. MFX HOLD bei MFX 2 ausprobieren.
3. Wenn etwas hängt: ausschalten, EXIT beim Einschalten halten, Original zurück ([blech-datei.md](blech-datei.md),
   Abschnitt 5).

Im Emulator gemessen: bei GATE ARP unterscheidet sich nur das LED-Byte `0x1b` von der Firmware, die MIDI-Bytes sind
gleich. Ob es knackt, zeigt nur das Gerät.

Quelle: Messung 2026-10-10/mfx-umschalter

## 2. Effekt-Bausteine im DSP (Hörproben)

Alle Schritte setzen einen Effekt-Record im RAM und hören auf einem Part mit Ton. Grundlage sind die gelesenen
DSP-Deskriptoren und der Lader ([Effekt-Katalog](../effekt-katalog.md)). Nach jedem Absturz neu starten, nichts mit
WRITE speichern. Einige dieser Fragen kann ein späterer Sweep schon beantwortet haben (Messung 2026-09-21/stage2-sweep);
das vor dem Test nachsehen.

### 2.1 Lücke in der Insert-Liste ist ein Durchreicher

Hergeleitet: die Nummern `0x0B` bis `0x0E` und `0x17` zeigen im DSP auf denselben Deskriptor wie `0x00` ("[I]
NoFx(Thru)"). Ob der ARM sie annimmt, ist nicht gelesen.

1. Einen Insert-Record im RAM auf `0x0B` setzen, auf einem Part mit Ton hören.

**Erwartet:** klingt wie `0x00`, kein Absturz. Ein Ausfall widerlegt die Herleitung.

### 2.2 Stufe 2: die sechs ungemessenen Bausteine

Gemessen sind 13 von 19 Insert-Bausteinen in Stufe 2. Offen: `0x0F` Distortion, `0x11` Chorus, `0x12` Flanger, `0x13`
Phaser, `0x14` Tremolo, `0x15` Level Mod. Hergeleitet aus dem Lader: Stufe 2 bekommt keinen Platzspeicher, also fallen
`0x11` und `0x12` wahrscheinlich aus.

1. Stufe 1 fest auf Filter `0x0A`.
2. Stufe 2 nacheinander auf `0x0F`, `0x13`, `0x14`, `0x15`, zuletzt `0x11` und `0x12` (die wahrscheinlich hängenden).
3. Je Kette drei Sekunden Rauschen, Pegel aufnehmen.

### 2.3 Decimator mit zweiter Stufe

Gemessen: `0x09 -> 0x0A` und `0x0A -> 0x09` stürzen ab. Der Decimator braucht keinen Platzspeicher, die Ursache ist
offen.

1. `0x09 -> 0x10` und `0x09 -> 0x06` (die beiden Stufe-2-Bausteine, die Korg selbst nutzt).
2. `0x09 -> 0x04` (Punch, im DSP ein Durchreicher).

**Erwartet (Deutung):** läuft Punch nicht, stört die Anwesenheit einer zweiten Stufe, nicht deren Rechnung.

### 2.4 Stufe 1 durchprobieren

Gemessen: `0x15 -> 0x0A` läuft, `0x02 -> 0x10` läuft, `0x15 -> 0x18` hängt, `0x09 -> 0x0A` stürzt ab, `0x16 -> alles`
ist stumm.

1. Stufe 2 fest auf Filter `0x0A`.
2. Stufe 1 nacheinander auf die 19 Bausteine, je drei Sekunden Rauschen, das Gefährliche zuletzt: `0x01` bis `0x08`,
   `0x0F`, `0x10` bis `0x15`, dann `0x16`, `0x18`, `0x09`.

### 2.5 Drei Kompressoren

Hergeleitet: `0x01` mKP2 Comp, `0x02` SR1 Comp und `0x03` Cheap Comp sind drei getrennte Algorithmen mit nicht
vergleichbaren Reglern. Offen ist die Parameterzahl von Cheap Comp (4 oder 6).

1. Ein Loop aus Kick und Hihat.
2. Nacheinander `0x01`, `0x02`, `0x03` mit Vorgaben, Ausgangspegel auf gleiche Lautheit, nach Gehör vergleichen.
3. Bei `0x03` die Regler 5 und 6 (Sens, Output) bewegen.

**Erwartet (Deutung):** reagiert bei Schritt 3 etwas, hat der Baustein 6 Parameter.

### 2.6 `lfo_reset`

Hergeleitet: `lfo_reset` ist im DSP ein Einmal-Auslöser, 1 setzt die Phase auf 0, 2 und 3 lesen Zeiger neben der
Tabelle und verschieben die Phase einmal. Der ARM sendet nur geänderte Parameter.

1. Level Mod `0x15`, Sync an, Note 1/4, ein Part mit gleichmäßigem Ton.
2. `lfo_reset` im RAM nacheinander auf 0, 1, 0, 2, 0, 3 schreiben (jedes Mal zurück auf 0, sonst ist es keine
   Änderung und der ARM sendet nichts).
3. `lfo_speed` verändern.

**Erwartet:** bei 1 springt das Pumpen auf den Beginn, bei 2 und 3 ein einmaliger Sprung auf einen anderen Stand,
danach läuft es durch. Bei Schritt 3 hören, ob das Pumpen aus dem Takt gerät.

### 2.7 Sync-Notenwerte

Hergeleitet: alle LFO-Bausteine teilen eine Tabelle bei DSP `0x97A0`, Index 6 ist 1/4, Index 8 ist 1/16. Offen ist,
ob die Einheit eine ganze Note oder eine Viertel ist (Faktor 4).

1. Tremolo `0x14` oder Level Mod `0x15`, Sync an, Tempo 120.
2. `SyncNote` auf 6, dann auf 8.
3. Tempo mit der Stoppuhr oder per Aufnahme auszählen.

**Erwartet:** bei 6 Viertel (2 Schläge je Sekunde), bei 8 Sechzehntel.

Quelle: Messung 2026-10-14/offene-fragen

## 3. Rote Electribe mit blauer Firmware

Die rote läuft mit Korgs blauer 2.02, um die Firmware der blauen ohne blaues Gerät zu prüfen (Hintergrund:
[Die blaue Electribe](../hintergrund/blau.md)). Getestet werden nur Effekte und Menüs. Im Emulator gemessen
(`red_as_blue_probe.py`), am Gerät nicht gelaufen.

### Go oder No-Go

**Go** nur, wenn alles steht:

- die Sicherungen unten liegen auf dem Rechner, und die Flash-Sicherung hat beide Durchgänge bestanden;
- die blaue Datei trägt das Wort und den Sampler-Kopf und ist vorher mit dem eigenen Flash-Dump durch
  `red_as_blue_probe.py` gelaufen (Ergebnis 0);
- auf der blauen wird nichts gespeichert, was bleiben soll (WRITE, GLOBAL, FACTORY RESET, PCM-Update).

**No-Go** für alles darüber hinaus: die Datei nicht weitergeben (sie enthält Korgs Firmware), kein Knopf im Patcher
daraus, keine Tests, die Patterns auf der blauen speichern müssen.

### Vorher sichern

1. **Ganzer Flash**, solange BLECH läuft:
   `python3 tools/device/blech_flash_dump.py --out ~/electribe-flash-vor-blau.bin` (nur Lesen, außerhalb jedes
   Repositorys). Nur diese Sicherung bringt Patterns und Globals Byte für Byte zurück.
2. **Alle Patterns** als `.e2sallpat`: DATA UTILITY, EXPORT ALL PATTERN, Datei vom Gerät kopieren.
3. **Alle Samples**: `KORG/blechtribe/Sample/e2sSample.all`.
4. **Die ganze Karte**, besonders `KORG/blechtribe/` (Einstellungen, Plugins, `ORIGINAL.BIN`).
5. **Die Dateien für den Rückweg** fertig auf dem Rechner: BLECH auf der eigenen Hacktribe (Prüfsumme der
   `ORIGINAL.BIN` vergleichen), einmal mit Sampler-Kopf und einmal mit blauem Kopf.

### Die blaue Datei bauen

Korgs blaue 2.02, das Wort an `0xC0027114` (Datei `0x27214`) auf `0x059F000C`, dazu der Sampler-Kopf (`0x12 = 0x53`,
`0x2E = 0x24`). `red_as_blue_probe.mark_fix` und `hacktribe_blue_probe.with_head` machen genau das. Vorher mit
`red_as_blue_probe.py` und dem eigenen Flash-Dump im Emulator laufen lassen:

```
node tools/patch/apply.mjs --vsb HACKTRIBE-163d1d8d.VSB --set data/patches/blech.json --out BLECH.VSB
tools/emu/.venv/bin/python tools/emu/red_as_blue_probe.py --blech BLECH.VSB --korg-blue BLAU.VSB --flash FLASH-ROT.bin --shots BILDER/
```

### Hin

1. Netzteil dran. Die blaue Datei als `KORG/blechtribe/System/SYSTEM.VSB`, sonst keine `.VSB` in dem Ordner.
2. DATA UTILITY, SOFTWARE UPDATE, durchlaufen lassen, aus und wieder an.
3. **Erwartet:** Hauptbild der blauen mit "001" und den Pattern-Namen der roten.
4. Testen: Pattern wechseln, spielen, IFX und MFX laden. **Kein WRITE** auf einem Pattern, das bleiben soll (wenn
   nötig auf einem freien Platz), **kein GLOBAL ändern**, **kein FACTORY RESET**, **kein PCM-, USER- oder
   BOOT-Update**.

### Zurück

1. BLECH mit blauem Kopf als `KORG/electribe/System/SYSTEM.VSB`, sonst keine `.VSB` darin.
2. DATA UTILITY, SOFTWARE UPDATE, durchlaufen lassen, aus und wieder an.
3. **Erwartet:** BLECH startet.
4. Patterns zurück: die Datei aus Sicherung 2 nach `KORG/blechtribe/`, DATA UTILITY, IMPORT ALL PATTERN, Datei wählen,
   durchlaufen lassen. Im Emulator stehen danach alle 250 Patterns wie in der Datei.
5. Samples zurück: `e2sSample.all` aus Sicherung 3 nach `KORG/blechtribe/Sample/`, aus und an. BLECH lädt sie beim
   Start.

### Wenn etwas nicht wie erwartet ist

- **"SOFTWARE UPDATE / press ENTER" beim Start der blauen** (Datei ohne das Wort): BLECH mit Sampler-Kopf als
  `KORG/electribe sampler/System/SYSTEM.VSB`, ENTER, durchlaufen lassen, aus und an. Im Emulator gemessen.
- **"Error / Invalid File" auf dem Rückweg:** falscher Kopf. Die blaue nimmt nur den blauen Kopf, der Updater lehnt vor
  dem ersten Schreibbefehl ab, es ist nichts kaputt.
- **Patterns nach dem Import falsch:** Import wiederholen. Globals und alles andere bringt nur die Flash-Sicherung 1
  zurück, und für das Zurückschreiben gibt es im Editor keinen Weg (kein Flash-Schreibbefehl).
- Alles Weitere nach [Rettung](../rettung.md).

### Was der Test klären soll

Ob das DSP-Programm der blauen auf der roten Platine läuft und klingt, wie die Werks-Samples als Oszillatoren klingen
(die blaue nimmt die Werks-Samplebank der roten, ihre 361 PCM-Oszillatoren spielen dann Werks-Samples), ob das
Hintergrundlicht stimmt, und ob die Patterns nach dem Rückweg am Gerät so sind wie im Emulator.

Quelle: Messung 2026-11-08/rot-als-blau

### 3.1 IMPORT SAMPLE und SAMPLE EDIT der blauen auf der roten

Dieselbe Reise wie oben, aber mit BLECHTRIBE der blauen statt Korgs blauer, um IMPORT SAMPLE und SAMPLE EDIT der blauen
ohne blaues Gerät zu prüfen. Am Gerät nicht gelaufen. Jeder Schritt, der schreibt (Datei auf die Karte, SOFTWARE UPDATE),
nur mit OK des Gerätebesitzers.

**Was im Emulator gemessen ist** (BLECHTRIBE blau mit dem Wort, Pascals Flash-Dump vom 9.10., `user_samples_cases.py`
Gruppen 0, 6, 7, 8 mit 14 s Start):

- Die blaue startet mit der Werksbank der roten länger: der Lader der `[User]`-Samples läuft erst nach etwa 10 s
  (Emulator), auf der blauen nach etwa 4 s. gemessen
- Die eigenen Samples kommen hinter die Werksbank der roten ab DSP-Adresse `0x133F5C0`, Fensterende `0x1365AE0`: zusammen
  nur **etwa 157 KB**, rund 1,6 Sekunden mono bei 48 kHz. Für den Test also nur kurze WAV nehmen. gemessen
- Laden beim Start, IMPORT SAMPLE (neu, ersetzen, neue Datei mit Ordner, abgelehnte Nummer und fehlende Datei),
  SAMPLE EDIT (Punkte und TUNE live und gespeichert, REVERSE und PLAY LEVEL über einen Neustart) verhalten sich wie auf
  dem blauen Flash. gemessen
- Ob ein Pad dann das `[User]`-Sample spielt, prüft der Fall nur ab einem neuen Pattern (Oszillator SAW); mit Pattern 001
  der roten trifft er einen anderen Oszillator. Am Gerät einen `[User]`-Oszillator im Part von Hand wählen. hergeleitet

**Die Sample-Datei auf der Karte:** die blaue liest und schreibt dieselbe `KORG/blechtribe/Sample/e2sSample.all` wie
BLECH auf der roten. Mit der eigenen großen Datei lädt sie nur, was in die 157 KB passt, und ein Import hängt an diese
Datei an (hergeleitet, mit der eigenen Datei nicht gemessen). Deshalb die eigene Datei für den Test wegnehmen:

1. Sicherungen 1 bis 5 aus Abschnitt 3, dazu `KORG/blechtribe/Sample/e2sSample.all` ein zweites Mal extra.
2. Den Ordner `KORG/blechtribe/Sample/` auf der Karte umbenennen (zum Beispiel `Sample-rot`). Ein Import legt dann eine
   neue, kleine Datei an (gemessen).
3. Zwei bis drei kurze WAV (unter 1 s, mono oder stereo, 16 oder 24 Bit) in einen neuen Ordner `KORG/blechtribe/Sample/`,
   eine weitere WAV direkt in die Kartenwurzel.

**Die Testdatei bauen:** BLECHTRIBE der blauen auf Korgs blauer 2.02 (`data/patches/blech-synth.json`), dann das Wort und
der Sampler-Kopf wie oben (`red_as_blue_probe.mark_fix`, `hacktribe_blue_probe.with_head`). Die Datei enthält Korgs
Firmware und wird nicht weitergegeben. Vorher im Emulator mit dem eigenen Flash-Dump starten lassen.

**Schritte am Gerät** (nach "Hin" aus Abschnitt 3, mit dieser Datei):

1. DATA UTILITY bis IMPORT SAMPLE, ENTER: die Liste zeigt die Kartenwurzel, erst die Ordner mit Ordner-Icon, dann die WAV aus
   der Wurzel ohne `.wav`. `KORG`, `blechtribe`, `Sample` je mit ENTER öffnen: oben steht Upper Folder mit Pfeil, darunter die
   WAV aus Schritt 3. ENTER auf Upper Folder geht eine Ebene hoch.
2. Eine wählen, ENTER: `[User] 1 (new)`. ENTER: "imported". Im Part den Oszillator auf `[User]` 1 stellen, Pad: das
   Sample klingt, ohne Neustart.
3. Noch eine WAV auf `[User] 2`, dann eine dritte auf `[User] 1` (ersetzt): beide klingen richtig. Die WAV aus der Wurzel auf
   `[User] 3`: klingt, der Name stimmt.
4. DATA UTILITY bis SAMPLE EDIT, ENTER: Seite SELECT SAMPLE zeigt Namen und `[User] 1`. Mit den Seitentasten START POINT,
   LOOP START, END POINT, SAMPLE TUNE ändern, nach jeder Änderung Pad: hörbar ab der nächsten Note.
5. PLAY LEVEL `+12dB`: lauter. REVERSE ON: rückwärts. Wieder OFF: vorwärts.
6. ONE SHOT ON: Pad kurz antippen, das Sample spielt bis zum Ende. Wieder OFF: es endet mit dem Loslassen des Pads.
7. START POINT mitten in die Welle, bis es am Anfang knackt. Seite DECLICK (9/9) ON: das Knacken ist weg oder leiser, START
   POINT zeigt denselben Wert. Wieder OFF: das Knacken ist wieder da.
8. EXIT, aus und wieder an: alle Werte aus 4 bis 7 sind noch da.
9. Ohne Karte starten, dann mit EXIT beim Einschalten: keine `[User]`-Samples, nichts hängt.

**Zurück:** wie in Abschnitt 3, dann den Test-Ordner `KORG/blechtribe/Sample/` löschen und `Sample-rot` wieder
`Sample` nennen (oder die Datei aus Sicherung 3 zurück). BLECH der roten (auf `ORIGINAL.BIN`, Hacktribe `163d1d8d`)
lädt die eigene Datei beim nächsten Start wie vorher.

Quelle: Messung 2026-11-27 (Emulator, `user_samples_cases.py` mit Pascals Flash-Dump)

### 3.2 ONE SHOT in SAMPLE EDIT der roten

BLECHTRIBE der roten (Hacktribe-Basis `ORIGINAL.BIN`), am Gerät nicht gelaufen. Ändert nur RAM bis zu WRITE, auf die Karte
kommt nichts ohne EXPORT ALL SAMPLE. Trotzdem vorher Patterns und Karte sichern (Abschnitt 3).

1. Ein Sample mit Loop wählen (Werksbank), DATA UTILITY > SAMPLE EDIT, ENTER, mit EDIT rechts bis hinter PLAY LEVEL: Seite
   ONE SHOT, Zähler 11/13, Wert OFF.
2. Rad hoch: ON, WRITE: dritte Zeile `saved`. EXIT bis zum Part, Pad kurz antippen: spielt bis zum Ende.
3. Zurück zu ONE SHOT, Rad runter: OFF, EXIT ohne WRITE: der Wert ist wieder ON.
4. OFF, WRITE, EXIT: das Sample endet mit dem Loslassen des Pads, LOOP START steht auf START POINT.
5. Ein Oszillator (Wave bis 49): ONE SHOT zeigt `---`, das Rad ändert nichts.

Quelle: Messung 2026-11-27 (Emulator, `sample_category_cases.py` `case_one_shot`)

### 3.3 TURN MONO in SAMPLE EDIT der roten

BLECHTRIBE der roten (Hacktribe-Basis `ORIGINAL.BIN`), am Gerät nicht gelaufen. Ändert das Sample im DSP-Speicher, auf die Karte
kommt nichts ohne EXPORT ALL SAMPLE, ein Neustart lädt das Stereo-Sample wieder. Trotzdem vorher Patterns und Karte sichern
(Abschnitt 3).

1. Ein Mono-Sample wählen, DATA UTILITY > SAMPLE EDIT, ENTER, mit EDIT links von SELECT SAMPLE: DELETE 13/13, keine Seite TURN
   MONO.
2. Ein eigenes Stereo-Sample wählen: EDIT links zeigt DELETE 14/14, dann TURN MONO 13/14 mit Wert `Stereo`.
3. PLAY starten, ENTER: `stop PLAY`, nichts ändert sich. PLAY stoppen.
4. ENTER: `Are You Sure ?`, EXIT: wieder `Stereo`.
5. ENTER, ENTER: `Mono`. Pad: klingt wie vorher, nur ohne Stereobild, kein Knacken, Start, Loop und Ende an derselben Stelle.
6. EXIT ohne WRITE, Pad: bleibt mono. SAMPLE EDIT wieder öffnen: DELETE 13/13, keine Seite TURN MONO mehr.
7. EXPORT ALL SAMPLE, aus und an: das Sample ist mono, die Datei auf der Karte kleiner.
8. Pad in SAMPLE EDIT gedrückt halten und dabei umwandeln: hört man etwas Fremdes?

Quelle: Messung 2026-11-27 (Emulator, `sample_category_cases.py` `case_turn_mono`)

### 3.4 DECLICK in SAMPLE EDIT der roten

BLECHTRIBE der roten (Hacktribe-Basis `ORIGINAL.BIN`), am Gerät nicht gelaufen. Ändert kein Sample, nur ein Bit, auf die Karte
kommt es erst mit EXPORT ALL SAMPLE. Trotzdem vorher Patterns und Karte sichern (Abschnitt 3).

1. Ein eigenes Sample, das am Anfang oder Ende knackt (START POINT mitten in die Welle), DATA UTILITY > SAMPLE EDIT, ENTER, mit
   EDIT rechts bis hinter ONE SHOT: DECLICK, Zähler 12/13 (stereo 12/14), Wert OFF.
2. Rad hoch: ON, WRITE: `saved`. EXIT bis zum Part, Pad: das Knacken am Anfang ist weg oder leiser, Länge fast gleich.
3. Zurück zu SAMPLE EDIT: START POINT zeigt denselben Wert wie vorher (der Punkt wird nur beim Spielen verschoben).
4. Ein geloopter Klang mit Knacken am Loop: mit ON knackt der Loop weniger.
5. Ein Stereo-Sample mit ON: klingt sauber, kein Aussetzer, kein Doppelanschlag.
6. OFF, WRITE: das Knacken ist wieder da.
7. ON, EXIT ohne WRITE: wieder OFF.
8. ON, WRITE, EXPORT ALL SAMPLE, aus und an: DECLICK steht weiter auf ON.

Quelle: Messung 2026-11-27 (Emulator, `sample_category_cases.py` `case_declick`)

## 4. Gerätename über USB

Der Patch `usb-name` ändert den USB-Gerätenamen auf "Electribe 3" (nicht im BLECH-Satz, ein Häkchen im Patcher). Im
Emulator gibt es kein USB, geprüft sind nur die Bytes (`test/usb-name.test.mjs`). Rot und blau:

1. Den Namen ansehen: unter Linux `amidi -l` und `aconnect -l`, unter macOS im Audio-MIDI-Setup, unter Windows mit dem
   Klassentreiber und mit Korgs Treiber.
2. Die App verbindet sich, SysEx geht in beide Richtungen.
3. Korgs Editoren finden das Gerät.
4. Windows: zeigt es nach dem Umstecken den neuen Namen, oder erst nach dem Entfernen im Geräte-Manager?

Quelle: Idee 69
