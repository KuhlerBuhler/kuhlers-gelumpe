# Die Sample-Datei `e2sSample.all` und die Seite Samples

Die Datei [`e2sSample.all`](../glossary.md#e2ssampleall) sammelt alle Samples der Karte. Das Format ist aus dem Export der Firmware und aus eigenen Dateien im Emulator belegt
([virtuelle-sd.md](virtuelle-sd.md), [Sample-Fehler](../messungen/2026-10-15-sample-fehler.md),
[Metadaten](../messungen/2026-10-07-sample-metadaten-ram.md)). Die Samples in den Tests sind eine Formel, kein Korg-Sample.
Der Code dazu steht in `src/sample-file.mjs`, die Seite in `site/app/sampleset.mjs` (`BLECHTRIBE -> Samples`).

## Das Format (gemessen)

| Teil | Inhalt |
|---|---|
| Kopf, 4096 Byte | 16 Byte `e2s sample all`, `0x1A`, `0`; danach 1020 Offsets (32 Bit, little endian), einer je Platz, 0 heißt leer |
| Plätze | 0 bis 499 sind die Werks-Samples und stehen nicht in der Datei. Die Firmware lädt 500 bis 998, am Gerät 501 bis 999 |
| Eintrag | eine RIFF/WAVE-Datei je Sample: `fmt `, `data` und `korg` |
| `korg` | `esli` und der 1172 Byte lange Satz der Firmware: Platz (Byte 0 und 78), Name (Byte 2, 16 Byte), Kategorie, Loop, Ende, One-Shot, Rate (Byte 72), Slices |

Die Länge eines Eintrags steht nicht im Kopf, sie ist die RIFF-Größe plus 8. Ein Eintrag, den der Lader nicht nehmen kann (kein PCM, nicht 16
oder 24 Bit, mehr als zwei Kanäle, Platz belegt), wird übersprungen, wenn BLECHTRIBE den Patch `sample-errors` hat.

## Was die Seite tut

- Liest die Datei, zeigt Platz, Name, Format, Länge und Größe je Sample. Ein Eintrag, den sie nicht lesen kann, steht mit dem
  Grund da und lässt sich entfernen.
- **Hinzufügen** nimmt eine WAV (PCM, 16 oder 24 Bit, ein oder zwei Kanäle) und legt sie auf den ersten freien Platz ab 501.
  Hat die WAV einen eigenen `esli`-Satz, bleibt er und bekommt nur Platz und Name. Sonst baut die Seite den Satz, den
  `tools/emu/sampleset.py` baut. 24 Bit und Stereo lädt der Lader im Emulator, am Gerät ist das **nicht geprüft**.
- **Entfernen** lässt keine Lücke: die Einträge dahinter rücken auf, der Kopf bekommt die neuen Offsets, die Datei endet beim
  letzten Eintrag. Es gibt keinen Knopf zum Aufräumen. Ein neuer Eintrag kommt ans Ende.
- Änderungen stehen erst als Vorschlag da (`wird entfernt`, `neu`) und lassen sich zurücknehmen. **Speichern** schreibt alles
  auf einmal.
- Die Electribe liest `e2sSample.all` nur beim Start. Die Seite sagt es vor dem Speichern und im Hinweis danach.
- **Als Datei speichern** holt die ganze Datei der Karte über USB auf den Rechner, mit Audio, als Sicherung oder zum Bearbeiten
  ohne Gerät. Jeder Block kommt mit seinem CRC-32, die Größe wird am Ende nochmal gefragt, und die Bytes müssen sich als Sample-Datei
  lesen lassen. Abbrechen geht zwischen zwei Stücken von 256 KiB. Eine volle Datei (26,8 MB) dauert rund zwei Minuten
  ([Messung](../messungen/2026-10-26-sample-datei-sysex.md#am-gerät-lesegeschwindigkeit)).

## Für die blaue Electribe 2

Mit dem Patch `user-samples-synth.json` (im BLECHTRIBE-Satz der blauen) lädt die blaue dieselbe Datei aus ihrem Ordner
(`KORG/blechtribe/Sample/` mit dem Satz) bei jedem Start als Oszillatoren der Gruppe `[User]`
([Messung](../messungen/2026-11-12-blau-sample-import.md)). Ihr Lader nimmt weniger als der der roten, deshalb hat die Seite oben
einen Schalter rot/blau. Er stellt sich auf das angeschlossene Gerät (Modellbyte `0x23` der blauen) und bleibt sonst gespeichert.

- **Hinzufügen** für die blaue macht aus der WAV 16 Bit mono bei ihrer Rate: von 24 Bit bleiben die oberen 16, Stereo wird
  gemittelt und abgerundet wie im Lader (`toMono16`). Ein `esli`-Satz der WAV bleibt, nur das Stereo-Bit geht weg. Eine schon
  hinzugefügte WAV wird beim Umschalten neu gebaut.
- Die Liste sagt, was die blaue beim nächsten Start nicht lädt (`blueLoad`, derselbe Gang wie der Lader: Plätze aufsteigend):
  kein 16 Bit oder anders aufgebaut als `fmt`, `data`, `korg`; kein Platz mehr hinter den Werkswellen; mehr als 64.
- Die Zusammenfassung zeigt den freien Platz in MB und in Sekunden mono bei 48 kHz. Der Platz ist **geschätzt**: Fensterende
  `0x1365AE0` minus `0xE03E60`, wo die Werkswellen im Emulator enden (5 643 392 Byte). Am Gerät rechnet der Lader ihn aus den
  eigenen Tabellen. Ein Sample braucht seine Werte, 64 Byte Nullen und das auf 32 Byte aufgerundet.
- Samples aus der App spielt die blaue erst nach einem Neustart, wie die rote. Ein Import am Gerät (unten) spielt sofort.

### IMPORT SAMPLE und SAMPLE EDIT am Gerät (blau, ab 1.5)

Die Laufzeit des Patches liegt an `0xC013A000` mit einem festen Sprungvektor, den das BLECH-Menü ruft: `+0` `us_import(Pfad, k)`,
`+4` `us_set(k, Feld, Wert)`, `+8` `us_store(k)`, `+12` die Marke `BLUS`, `+16` `us_info(k)`, `+20` die Adresse des Ordners,
den der Browser von IMPORT SAMPLE zeigt (`0xC013FA00`: 0x80 Bytes Ordner, dahinter 0x80 Bytes Pfad der gewählten Zeile). Fehlt die Marke, zeigt DATA UTILITY
die beiden Seiten nicht. Die Seiten zeigt nur das Profil synth; rot und Hacktribe bauen sich byte-gleich wie vorher.

- **IMPORT SAMPLE** zeigt die Karte wie Korgs Dateibrowser: beim ersten Mal die Kartenwurzel (`SD:`), oben Upper Folder (nicht in
  der Wurzel), dann die Ordner, dann die `.wav` ohne Endung, jeweils in der Reihenfolge des Ordners. Andere Dateien, versteckte
  Ordner und Namen über 31 Zeichen fehlen. ENTER auf einem Ordner öffnet ihn mit dem Cursor auf Upper Folder, ENTER auf Upper
  Folder geht eine Ebene hoch. Der Ordner bleibt bis zum Ausschalten; lässt er sich nicht mehr öffnen (andere Karte), zeigt der
  Browser die Wurzel. Ein Ordner mit mehr als 95 Zeichen Pfad öffnet nicht. Die Icons sind die Glyphen der Firmware wie in Korgs
  Liste: 7 Upper Folder (Pfeil), 9 Ordner (ein Pixel tiefer als die Datei), 8 Datei (Quelle: Messung, Korgs Liste der roten bei
  `0xC0085BB4` gelesen und im Emulator gezeichnet, `tools/emu/user_samples_cases.py` `import_folders_*`). ENTER auf einer WAV,
  dann wählt das Rad `[User]` 1 bis eins hinter dem letzten. Ein vorhandenes Sample wird ersetzt, sonst kommt ein neues dazu. Die WAV wird wie in der App 16 Bit
  mono (`fmt` darf hinter `LIST` stehen, 24 Bit behält die oberen 16, Stereo gemittelt), der Eintrag kommt mit einem frischen
  `esli`-Satz ans Ende der Datei, der Kopf bekommt den Offset. Der alte Eintrag bleibt als toter Platz, bis die App die Datei das
  nächste Mal schreibt. Die Datei wird nur mit Lesen/Schreiben geöffnet, nie mit `FA_CREATE_ALWAYS` (das kürzt auf 0); fehlt sie,
  legt der Import Datei und Ordner an. Danach gehen PCM und Tabellen sofort in den DSP und den RAM.
- **SAMPLE EDIT** hat 9 Seiten: SELECT SAMPLE, START POINT, LOOP START, END POINT, SAMPLE TUNE (-63 bis 63), PLAY LEVEL
  (`+0dB`/`+12dB`), ONE SHOT (OFF/ON), REVERSE (OFF/ON), DECLICK (OFF/ON, Abschnitt "DECLICK auf der blauen"). Punkte stehen in Werten (Byte / 2) wie auf der roten. Punkte und TUNE gehen in die
  RAM-Tabellen und wirken ab der nächsten Note; in den `esli`-Satz kommen sie mit EXIT oder beim Wechsel auf ein anderes Sample.
  PLAY LEVEL und REVERSE schreiben den Satz sofort und laden das Sample an seinem Platz neu.
- **REVERSE** ist `esli[54]` Bit 0. Die Punkte bleiben vorwärts gespeichert; der Lader schreibt die PCM umgedreht in den DSP, die
  Punkte spiegelt er nicht: sie zählen auf der umgedrehten PCM. Die rote liest Byte 54 nicht und spielt vorwärts; ihr EXPORT ALL SAMPLE schreibt das Byte als 0 (gemessen
  im Emulator). Byte 76 wäre frei gewesen, die rote schickt es aber bei jeder Note an den DSP, deshalb nicht.
- **ONE SHOT** ist `esli[52]` wie auf der roten. Die blaue behält den gespeicherten LOOP START und setzt nur im DSP-Satz den Loop
  auf das Ende (Flag `0x10000`), OFF gibt den alten Loop zurück. Die Seite schreibt den Satz sofort, der Lader liest das Byte beim
  Start (gemessen im Emulator, `tools/emu/user_samples_cases.py` `edit_menu_one_shot`).
- **TUNE** ist eine Stufe pro Halbton auf dem Pitch-Wort der Stimme (hergeleitet, nicht am Gerät gehört).
- **REVERSE auf der roten** hat ein eigenes Bit (Byte 53 Bit 1, siehe unten). Die rote schreibt die PCM umgedreht in die Datei, die
  blaue spielt so ein Sample also auch rückwärts (ihre Seite REVERSE zeigt OFF). Ein Sample mit REVERSE von der blauen spielt die
  rote vorwärts, dort liegt die PCM vorwärts in der Datei (hergeleitet aus beiden Ladern).
- Die App behält den ganzen `esli`-Satz, also auch REVERSE, PLAY LEVEL und TUNE, wenn sie die Datei neu schreibt
  (`test/sample-file.test.mjs`).

### ONE SHOT in SAMPLE EDIT (rot und Hacktribe, ab 1.5)

SAMPLE EDIT hat hinter PLAY LEVEL eine Seite ONE SHOT, dazu die Seite CATEGORY hinter RENAME, REVERSE und DECLICK hinter ONE SHOT,
also 14 Seiten (ONE SHOT 11/14). Quelle: Messung im
Emulator (`tools/emu/sample_category_cases.py` `case_one_shot`).

- Korgs One-Shot ist kein eigenes Feld, das man setzt: die Firmware nennt ein Sample one-shot, wenn sein LOOP START auf dem END
  POINT steht (Spieltabelle `0xC0362EE8` + Index × 16, Byte 14; Getter `0xC004EA38`). Im `esli` ist es Byte 52, Loop und Ende
  stehen dann gleich (Byte 44 und 48, in Byte, also Frames × 2 bei mono).
- ON stellt LOOP START über Korgs eigene Funktion (`0xC007F630`) auf END POINT, OFF auf START POINT. Den Loop von vorher merkt
  sich die rote nicht, anders als die blaue.
- Wie bei Korgs eigenen Seiten ist das erst eine Vorschau. WRITE gibt Kommando `0x25` aus (nicht, solange `0xC0345EC4` belegt
  ist), die dritte Zeile zeigt `saved`. EXIT ohne WRITE holt die alten Werte aus der Sicherung `0xC0345A2C` zurück. Für 1 bis 3 s
  nach WRITE nimmt die Firmware keine Tasten.
- Das Gate (Note hält, solange das Pad gedrückt ist) folgt der Änderung erst, wenn SAMPLE EDIT verlassen ist. Innerhalb von SAMPLE
  EDIT verhält sich Korgs eigener LOOP START genauso.
- Oszillatoren und leere Plätze zeigen `---`. Auf die Karte kommt ONE SHOT wie die Punkte mit EXPORT ALL SAMPLE.

### TURN MONO in SAMPLE EDIT (rot und Hacktribe, ab 1.5)

Ein Stereo-Sample hat hinter DECLICK eine Seite TURN MONO (Zähler 14/15, DELETE 15/15), ein Mono-Sample hat sie
nicht. Quelle: Messung im Emulator (`tools/emu/sample_category_cases.py` `case_turn_mono`, rot und Hacktribe).

- Der Wert zeigt `Stereo` oder `Mono` (Korgs eigene Texte `0xC00A733C` und `0xC00A7337`). ENTER oder WRITE fragt mit Korgs
  `Are You Sure ?` (`0xC00A5A8B`), ein zweites ENTER oder WRITE wandelt um, EXIT nimmt die Frage zurück.
- Die Wandlung läuft im DSP-Speicher: Blöcke bis `0x10000` Byte lesen (`0xC004EDDC`), je Frame (L + R) / 2 abgerundet, ohne
  Clipping, in die erste Hälfte des Samples zurückschreiben (`0xC004EF28`). Puffer ist Korgs Arbeitspuffer (`0xC00369F0`, frei
  mit `0xC0036A08`). 20000 Frames: 0 von 20000 weichen von (L + R) / 2 ab.
- Danach Metadaten (`0xC036AD88` + Zeile × `0x45C`): Byte 4 halbe Länge, Byte 9 = 0 (mono). Die Spieltabelle (`0xC0362EE8` +
  Zeile × 16) bekommt Start, Loop und Ende in Byte halbiert, die Punkte bleiben auf demselben Frame.
- Liegt das Sample als letztes im DSP-Speicher (Ende = Zeiger `0xC00F9C80`), rückt der Zeiger um die halbe Länge zurück, so wie
  DELETE ihn zurücksetzt. Sonst bleibt die zweite Hälfte bis zum nächsten Start ungenutzt.
- Danach wird der Schnappschuss neu genommen (`0xC0039514`), sonst holte EXIT ohne WRITE die alten Stereo-Werte zurück. Mono
  bleibt also auch ohne WRITE. Der Seitenring zählt danach wieder 14.
- Solange der Sequencer läuft (`0xC06BC318` ungleich 0), wandelt ENTER nicht und die Seite zeigt `stop PLAY`. Solange
  `0xC0345EC4` belegt ist, auch nicht.
- Auf die Karte kommt es wie die Punkte mit EXPORT ALL SAMPLE: ein Mono-WAV mit halber Datenlänge. Korgs Export schneidet jedes
  Sample auf START POINT bis END POINT zu, START steht im Satz dann auf 0, Loop und Ende relativ dazu. Ohne Export lädt der nächste
  Start wieder das Stereo-Sample von der Karte.
- Grenze: eine Stimme, die das Sample gerade spielt (Pad in SAMPLE EDIT gedrückt), wird nicht vorher beendet. Sie kann für die
  Dauer der Wandlung Fremdes spielen. Nur im Emulator geprüft, am Gerät offen (`docs/geraetetests/offene-geraetetests.md` 3.3).
- Die blaue braucht die Seite nicht: ihr IMPORT SAMPLE und die App (`src/sample-file.mjs` `entryFromWav` mit `blue`) schreiben
  mono, und Stereo-Daten in der Datei mittelt ihr Lader beim Start. Im DSP liegt dort jedes Sample schon mono.

### DECLICK in SAMPLE EDIT (rot und Hacktribe, ab 1.5)

SAMPLE EDIT hat hinter REVERSE eine Seite DECLICK (13/14 mono, 13/15 stereo), Wert OFF oder ON. Mit ON spielt das Sample von
START POINT, LOOP START und END POINT, die zur nächsten ruhigen Stelle verschoben sind. Nichts am Sample wird geändert. Quelle:
Messung im Emulator (`tools/emu/sample_category_cases.py` `case_declick`, rot und Hacktribe).

- Gespeichert wird ein Bit: Bit 0 von Byte 15 der Spieltabelle (`0xC0362EE8` + Zeile × 16), im `esli` Byte 53. Korg kopiert das
  Byte nur durch (Import `0xC004EDF0`, Export `0xC004EBD4`, Sicherung von SAMPLE EDIT `+0x35` bei `0xC004EFF4`), Werksdaten haben
  0. Die Aufnahme (`0xC004F128`) schreibt es nicht. Die Seite wirkt wie ONE SHOT: WRITE gibt `0x25` aus (`saved`), EXIT ohne WRITE
  holt den alten Wert zurück. Dazu setzt die Seite bei jeder Änderung Korgs Byte `0xC0345A20` ("geändert"). Korgs EXIT auf den
  eigenen SAMPLE-EDIT-Seiten ruft `0xC0039420`, das bei gesetztem Byte aus der Sicherung zurückholt (`0xC004EFF4`); EXIT auf den
  BLECH-Seiten (CATEGORY, ONE SHOT, DECLICK, TURN MONO) ruft es jetzt genauso, vorher sprang es nur auf Bildschirm 37 und ließ
  ungeschriebene Änderungen stehen. CATEGORY bleibt dabei wie bisher auch ohne WRITE stehen (sie wird mit den Einstellungen
  gespeichert). `0xC0039420` gibt außerdem Part 1 seinen eigenen Oszillator zurück, über den SAMPLE EDIT das Sample abspielt.
  Auf die Karte kommt es mit EXPORT ALL SAMPLE.
- Ruhige Stelle: im Fenster von 128 Frames vor und hinter dem Punkt der nächste Frame, an dem alle Kanäle die Null kreuzen (Wert
  0 oder Vorzeichenwechsel zum Frame davor). Haben links und rechts dort keinen gemeinsamen Nulldurchgang, der Frame mit dem
  kleinsten |L| + |R|, bei Gleichstand der nähere. Keine Blende, auch bei Stereo nicht.
- START bleibt zwischen Samplebeginn und END, END zwischen neuem START und Samplende, LOOP zwischen beiden. Steht LOOP auf START
  oder END (Korgs One-Shot), folgt er dem verschobenen Punkt, damit ONE SHOT bleibt.
- Die verschobenen Punkte rechnet der UI-Takt (`declick_frame` im Frame-Haken, bis 256 Zeilen je Frame, ein Sample je Frame) über
  Korgs DSP-Lesen (`0xC004EDDC`, mit Sperre wie das Schreiben der Note) in einen eigenen Puffer, nicht in Korgs Arbeitspuffer. Sie
  stehen in einer Tabelle für 64 Samples in der Laufzeitreserve `0xC018E9D0` (3104 Byte, nur Sampler-Builds). Ein Eintrag gilt,
  solange Start, Loop, Ende und PCM-Länge noch passen. Wer einen Punkt auf Korgs Seiten verschiebt, TURN MONO oder ein anderes
  Sample in den Platz lädt, hört bis zur neuen Rechnung die gespeicherten Punkte. REVERSE löscht den Eintrag des Samples, die
  nächste Rechnung nimmt die umgedrehte PCM.
- Gespielt wird über einen Haken im Stimmenstart (`0xC0099A40`, Stelle `0xC0099BC8`): Start, Loop und Ende aus der Spieltabelle
  werden für diese Note durch die verschobenen ersetzt. Korgs Seiten zeigen und exportieren weiter die gespeicherten Punkte, OFF
  spielt sie wieder. Slices (Modus 1 und 2) verschiebt DECLICK nicht.
- Grenze: mehr als 64 Samples mit ON spielen ab dem 65. die gespeicherten Punkte. Oszillatoren und leere Plätze zeigen `---`.
- Nur im Emulator geprüft, am Gerät offen (`docs/geraetetests/offene-geraetetests.md` 3.4).

### DECLICK auf der blauen (ab 1.5)

Dieselbe Regel wie auf der roten, in der Laufzeit des Patches `user-samples` (`tools/patch/user_samples.py`). Die blaue hat
nur Mono im DSP, also zählt der eine Kanal. Quelle: Messung im Emulator (`tools/emu/user_samples_cases.py` `case_declick`, mit
dem DSP-Modell; die Punkte gegen eine Rechnung in Python aus der PCM im DSP).

- Gespeichert wird `esli[53]` Bit 0 wie auf der roten, im RAM das Byte `+0x30` des Satzes je `[User]`-Sample (`0xC013E000` +
  (k - 1) × 64). Die Seite DECLICK ist Seite 9 von SAMPLE EDIT und schreibt den Satz sofort, wie ONE SHOT (`us_set` Feld 7).
- Die verschobenen Punkte kommen nur in den SMPR-Satz, den die Stimme spielt (`smpr_put`); der Satz je Sample, die Anzeige und
  die Datei behalten die eingestellten. Gerechnet wird beim Laden (nach dem Schreiben der PCM, über Korgs DSP-Lesen am Port des
  Laders, `0xC00103B8`), bei jeder Änderung eines Punkts und beim Umschalten (zur Laufzeit unter Korgs Sperre, `0xC000FAB4`,
  dem Gegenstück der roten `0xC00141F8`). REVERSE und PLAY LEVEL laden das Sample neu, die Punkte werden dann auf den neuen
  Werten gerechnet. Fenster im RAM: `0xC013FB00`, 0x300 Bytes.
- Ohne Nulldurchgang im Fenster der Frame mit dem kleinsten |Wert|, bei Gleichstand der nähere (gemessen mit einer Welle, die nie
  die Null kreuzt).
- Keine Grenze bei 64 wie auf der roten: jedes `[User]`-Sample hat seinen Satz.
- Nur im Emulator geprüft, am Gerät offen (`docs/geraetetests/offene-geraetetests.md` 3.1, Schritt 7).

### REVERSE in SAMPLE EDIT (rot und Hacktribe, ab 1.5)

SAMPLE EDIT hat hinter ONE SHOT eine Seite REVERSE (12/14 mono, 12/15 stereo), Wert OFF oder ON. ON dreht die PCM des Samples im
DSP-Speicher um, OFF dreht sie zurück. Quelle: Messung im Emulator (`tools/emu/sample_category_cases.py` `case_reverse`, rot und
Hacktribe).

- Gespeichert wird Bit 1 von Byte 15 der Spieltabelle (`0xC0362EE8` + Zeile × 16), im `esli` Byte 53, dasselbe Byte wie DECLICK
  (Bit 0). Das Bit heißt: die PCM liegt umgedreht. Korgs Lader liest die PCM so, wie sie in der Datei steht, ein Neustart spielt
  also weiter rückwärts, ohne eigenen Code im Lader.
- Die Umkehr läuft wie TURN MONO im DSP-Speicher über Korgs Lesen (`0xC004EDDC`) und Schreiben (`0xC004EF28`) mit Korgs
  Arbeitspuffer (`0xC00369F0`), in Blöcken bis `0x10000` Byte: je ein Block vom Anfang und vom Ende werden gelesen, frameweise
  umgedreht und vertauscht zurückgeschrieben, der Rest in der Mitte in einem Stück. Ein Stereo-Frame behält L vor R. OFF ergibt
  die PCM Bit für Bit wie vorher (70001 Frames mono, 40001 Frames stereo).
- Die Punkte bleiben stehen und zählen auf der umgedrehten PCM, wie auf der blauen. Wer genau den alten Abschnitt rückwärts hören
  will, stellt die Punkte danach neu.
- Die Seite wirkt sofort, auch ohne WRITE: Korgs Sicherung von SAMPLE EDIT (`0xC0345A2C`, Byte 15 bei `0xC0345A61`) bekommt das
  neue Bit mit, sonst holte EXIT ohne WRITE das alte Bit zur umgedrehten PCM zurück. Auf die Karte kommt es mit EXPORT ALL SAMPLE:
  die umgedrehte PCM und das Bit.
- Solange `0xC0345EC4` belegt ist, dreht die Seite nicht. Oszillatoren und leere Plätze zeigen `---`.
- Grenze wie bei TURN MONO: eine Stimme, die das Sample gerade spielt, wird nicht vorher beendet. Nur im Emulator geprüft, am Gerät
  offen (`docs/geraetetests/offene-geraetetests.md` 3.5).

## Der Plan einer Änderung

`planChange` gibt zurück, was die Datei ändert, so wenig wie nötig: den neuen Kopf, die Einträge, die bleiben und wohin sie
rücken (aufsteigend, jeder nur nach unten, also liest ein einfaches Kopieren nie schon überschriebene Bytes), und die neuen Einträge
am Ende. Übertragen werden müssen nur der Kopf und die neuen Samples, das Verschieben macht der Besitzer der Datei. Aus dem
Kartenleser läuft der Plan im Speicher (`applyPlan`).

## Der Weg übers Kabel (SysEx)

**gemessen im Emulator** ([Messung](../messungen/2026-10-26-sample-datei-sysex.md)), am Gerät **nicht** gemessen. Die Seite erreicht
die Datei über BLECHs [SysEx](../glossary.md#sysex)-Befehle (`tools/patch/blech_sysex.py`). `0x65` FILE READ und `0x66` FILE BEGIN
erreichen `SYSTEM.VSB` und `ORIGINAL.BIN` im Ordner der Firmware (Bit 31 des Offsets wählt), `0x67` PLUGIN BEGIN eine
Plugin-Datei, mit Offset plus Länge bis `0x200100`. Für die Sample-Datei gelten diese Erweiterungen:

| Befehl | Was er tut |
|---|---|
| Bit 30 im Offset von FILE READ und FILE BEGIN | `KORG/<Ordner>/Sample/e2sSample.all`; mit Bit 31 dazu die Tauschdatei `e2sSample.tmp` daneben. Der Ordner ist der, den das Update nimmt (die eigene Funktion der Firmware), Offset plus Länge bis 256 MiB |
| Bit 29 im Offset von FILE READ und FILE BEGIN | Doom-Dateien: `KORG/blechtribe/Doom/doom.bin`; mit Bit 31 dazu `doom.wad`. Die Pfade sind die aus `tools/doom/runtime_abi.h`, die der [Doom-Lader](../glossary.md#doom-lader) liest. Grenze 256 MiB, ein Block bei Offset 0 macht die Datei neu, fehlt der Ordner, legt die Firmware ihn an. Bits 30 und 29 zusammen nennen keine Datei: Status 3 (READ liest damit `e2sFx.all`) |
| `0x71` FILE COPY, Antwort `0x79` | Quelle, Ziel (je Selektor und Offset, die zwei Sample-Dateien, nicht dieselbe) und Länge 1 bis 256 KiB: kopiert auf der Karte in Stücken von 16 KiB, beide Dateien offen. Antwort: Status, kopierte Bytes, CRC-32 davon. Ist die Quelle kürzer als verlangt, wird abgelehnt, bevor das Ziel angelegt wird |
| `0x72` FILE DELETE, Antwort `0x7A` | löscht eine der beiden Sample-Dateien mit `f_unlink` der Firmware. SYSTEM.VSB, ORIGINAL.BIN und Plugins sind abgelehnt |
| `0x73` FILE CRC, Antwort `0x7B` | liest bis 256 KiB einer Sample-Datei von der Karte und schickt nur Status, Offset, Länge und CRC-32 |

Ein Block bei Offset 0 schneidet `e2sSample.all` nicht ab (er schreibt den Kopf an Ort und Stelle, `FA_OPEN_ALWAYS`), bei der Tauschdatei
macht er sie neu. INFO meldet Bit 7 der Flags, wenn die Befehle da sind, und Bit 8 (`FLAGS` `0x1ff`) für die Doom-Dateien. Die blaue Electribe 2 hat keinen Doom-Lader, ihr Build meldet Bit 8 nicht und die App schreibt dort nichts; ob sie Bit 29 trotzdem annimmt, ist nicht geprüft. Auf der blauen Electribe 2 fehlt `f_unlink` im Abbild, dort
macht DELETE die Datei neu und schließt sie, sie bleibt also leer (Größe 0, die die Seite wie eine fehlende liest); der Tausch unten
läuft so auch auf der blauen, nur bleibt eine leere `e2sSample.tmp` liegen. Der Code liegt in einem zweiten Abschnitt bei `0xC017B950` (1116 Byte), weil der
erste bis `0xC0173000` reicht, wo der Puffer der Sync Group anfängt.

### Warum die Datei über eine Tauschdatei kleiner wird

Das FatFs in der Firmware hat kein `f_truncate` und kein `f_rename` (**offline** gelesen: `f_getfree` `0xC009E85C` steht direkt vor
`f_unlink` `0xC009E9B8`, `follow_path` `0xC009CF2C` wird nur von `f_open`, `f_opendir`, `f_stat`, `f_unlink` und `f_mkdir` gerufen). Eine
Datei lässt sich also nicht kürzen und nicht umbenennen. Eigene Eingriffe in die FAT-Kette kommen nicht in Frage: ein Absturz darf Daten
kosten, die Karte darf er nicht beschädigen. Entfernen geht deshalb so, und die Seite macht es von selbst:

1. Kopf und neue Samples der neuen Datei kommen als Tauschdatei auf die Karte; was bleibt, kopiert die Electribe auf der Karte
   (FILE COPY, aneinanderliegende Samples in einem Zug).
2. Die Seite prüft die Tauschdatei: Größe und CRC-32, den das Gerät selbst von der Karte liest (FILE CRC), gegen die Teil-CRCs der
   Antworten (`src/crc-combine.mjs`).
3. Erst dann wird die alte Datei gelöscht, die Tauschdatei zurückkopiert, wieder geprüft und die Tauschdatei gelöscht.

Bis zum Löschen der alten Datei ist an ihr nichts verändert, ein Fehler davor löscht nur die Tauschdatei. Bricht es danach ab (Kabel
gezogen, Strom aus), liegt die fertige Tauschdatei auf der Karte; beim nächsten Lesen über USB bietet die Seite an, sie fertigzustellen,
oder sie zu löschen, wenn ihr Kopf nicht zu ihrer Größe passt. Fehlt `e2sSample.all` dazwischen, lädt die Electribe beim Start keine
Samples, die Karte ist heil. Eine Wiederherstellung beim Einschalten, ohne die App, gibt es **nicht**.

Nur Hinzufügen braucht das nicht: die neuen Samples kommen hinter die alten, der Kopf zuletzt, ein Abbruch dazwischen lässt Samples
zurück, die niemand listet, nie einen Kopf ohne seine Samples.

### Wie die Seite listet

Sie liest den Kopf und von jedem Sample die ersten 44 Byte und den Namen im Satz hinter dem Audio, nicht das Audio. Ein Eintrag mit
anderem Aufbau als fmt, data, korg steht mit seiner Länge aus dem RIFF-Kopf und dem Vermerk `Aufbau nicht erkannt` da und lässt sich
entfernen. Fehlt die Datei, ist die Liste leer, und ein erstes Sample legt sie an.

Doom über das Kabel (offline gelesen, Fälle `doom_*` in `tools/emu/sysex_cases.py` im Emulator grün auf Hacktribe und Korgs Original):
Der Code der Doom-Befehle liegt im zweiten Bereich bei den Sample-Befehlen (Hauptbereich `0xd5c` von `0xf00` Byte, zweiter Bereich
`0x68c` von `0x840`). Ohne Karte antwortet READ und DATA mit Status 6, ohne `doom.bin` auf der Karte ebenfalls. Die echte `doom.bin`
(453.380 Byte, 14 Blöcke) liegt nach dem Schreiben gleich der in `third_party/doom/`. **Offen** am Gerät: die Zeit für die 28 MB `doom.wad`
(geschätzt aus 150 bis 200 KiB/s beim Lesen: 2,5 bis 3 Minuten, Schreiben nicht gemessen). Quelle: Messung 2026-11-11/doom-usb.

Mehr zu Speicher, Schreibwegen, Dateibesitz und Journal der Sample-Datei auf der Karte: [sample-speicher.md](sample-speicher.md).
