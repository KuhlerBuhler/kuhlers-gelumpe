# BLECH auf der blauen Electribe 2, Firmware 2.02

Offline und im Emulator gemessene Adressen und Befunde zum Synth-Satz der blauen Electribe 2 (Firmware 2.02). Der Stand der Patches steht in [Patcher](../patcher.md).

## Ausgangsdateien und Verfahren

Das blaue Original hat SHA-256 `41fc5f1c33209ef381d1c9fef21a72380bcd8d3431c9c1350a964f5c619ab8b8`.
Der Patch-Satz steht in `data/patches/blech-synth.json`. Die Sampler-Sätze bleiben in
`data/patches/blech.json`. Die Dateien mit Firmware und PCM-Bank liegen außerhalb des Repositorys.

Adressen werden mit `tools/patch/fwmap.py` verglichen. `same_code` vergleicht vollständige
Fenster nach der vorhandenen Maskierung von Verzweigungen, PC-relativen Zugriffen und Zeigern.
Ein ausdrücklich gemessener Kandidat kann unabhängig von den automatisch ausgerichteten
Abschnitten verglichen werden. Ein unvollständiges oder ungleiches Fenster gilt nicht als Treffer.

Ein ganzes 16-Wort-Fenster passt nicht an jeder Funktionsgrenze. Der Getter für die Patternnummer
bei `0xC00818D8` und `0xC0072330` besteht zum Beispiel aus zwei gleichen Befehlen; die folgende
Funktion gehört nicht dazu. Die Kartenprüfung und beide Schreiber des Motion-Ausgangs haben
jeweils 16 gleiche Wörter, die Schriftfunktion 30. Die Adresstabellen halten auch die Herkunft
der RAM-Zeiger und die ursprünglichen Aufrufer fest.

**Neu umgesetzt, keine gleichen Funktionen behauptet:** Der Synth-Patternselektor wickelt
die Nummer direkt im eigenen Code auf 0 bis 249 um. Der Patch verwendet einen eigenen kleinen
Umbruch für diesen gemessenen Bereich. Der Würfel-Haken stellt den eigenen Registersatz des
Synth-Einstiegs wieder her und liest den gewählten Part über das native Modell. TAP springt
zum nativen Ende seiner Tastenfunktion mit dessen eigenem Stackrahmen. MFX benutzt den
nativen Touchpad-Handler und wartet beim Start auf dessen Eingabesperre. Hier werden keine
abweichenden Sampler-Funktionen in die blaue Firmware kopiert. Die Haken prüfen die erwarteten
Synth-Anweisungen, die Gesamtläufe prüfen die ausgelösten Abläufe und den ausgeschalteten Patch.

## Schriften und Bilder

**Offline gemessen:** Der Schriftzugriff `0xC003F74C` entspricht `0xC003A384`, über 30 Befehle
nach der Maskierung gleich. Die dritte Anweisung lädt die Schrifttabelle `0xC00AD208`.
Alle vier Schriften haben dieselben Anzahlen und Höhen: 98/8, 95/16, 224/12 und 95/16.
Der Bildzugriff `0xC003F650` entspricht `0xC003A288`, über 16 Befehle nach der Maskierung gleich.
Seine Bildtabelle liegt bei `0xC00AC624` und hat 17 Einträge. Die beiden weiteren Bilder des
Samplers existieren dort nicht. Bild 13 hat 128 mal 64 Pixel; seine Daten beginnen bei
`0xC00DF5FE`, sein Datenzeiger steht bei `0xC00B0438`.

Das Theme ersetzt eigene Schriften und vorhandene Symbole an Ort und Stelle. Es behält Codes,
Vorschübe, Tabellen und Zeiger bei. Das Startbild ist ein eigener Datenpatch mit Prüfsumme
für die ersetzten 1024 Byte. Der Start-Haken des Startbild-Editors hat auf dem Synth anderen Code als auf dem Sampler.

## Speicher

**Offline gemessen:** Das blaue Original ist von `0xC01217F4` bis `0xC01FFFF0` vollständig FF,
911356 Byte. `SYNTH_FREE_RUNS` in `data/patch-ram.mjs` hält diesen Bereich fest.
Der Platztest prüft den gewählten Synth-Satz auf Überschneidungen und seine deklarierten Bereiche
gegen diesen freien Abschnitt. `tools/emu/synth_ram_probe.py` misst Schreibzugriffe während
Start und Wiedergabe. Bei 8111 ms Gerätezeit war Bildschirm 1 erreicht, ohne Assertion und ohne einen Schreibzugriff in diesem Bereich.

## Kartenprüfung der Spielhilfen

**Im Emulator gemessen:** Beide Firmwares lesen den Kartenkontakt an GPIO 4.1 aus
`0x01E26070`, mit Bitmaske 2. Der Lesezugriff läuft im Sampler bei `0xC001C9F0`,
im Synth bei `0xC0018318`; `fwmap --target` bestätigt dort 16 gleiche maskierte Wörter.
Ohne Karte ist das Bit gesetzt. Die Synth-Firmware mountet FatFs erst beim ersten Zugriff.
Ein gemountetes Dateisystem als Voraussetzung würde die Spielhilfen trotz eingelegter Karte
abschalten. `tools/patch/card_gate.py` verwendet deshalb auf dem Synth den vorhandenen
Kartenkontakt und auf den beiden Sampler-Builds die bisherige Prüfung des gemounteten Volumes.
Die Spielhilfen bleiben ohne Karte aus. Zwei native Tests prüfen beide Regeln und bestätigen,
dass die Prüfung selbst nichts in den Speicher schreibt.

Die Synth-Prüfung für NOTE ASSIST enthält den Fall ohne Karte wieder. Der Kombinationstest
Patternwechsel plus MFX 2 wird ausgeführt; die vorherige feste Erfolgsmeldung ohne Test entfällt.
Die Würfelprüfung misst die Tastaturbelegung über die MIDI-Noten der Original-Firmware und
liest ausgewählte Parts über das Sequencer-Modell. Laufzeitzeiger werden dabei unverändert
verwendet. Ein unerreichbarer Part bricht die Prüfung mit einem Fehler ab.

## Motion und Flash-Prüfungen

**Mit gleichem Code und im Emulator gemessen:** Die Motion-Schreiber `0xC0059300` und
`0xC0059394` entsprechen `0xC004FF30` und `0xC004FFC4`, jeweils 16 maskierte Wörter gleich.
Ihr Schreibziel `r7-0x10` liegt im Sampler bei `0xC068DB1C`, im Synth bei `0xC0567E14`.
Die Prüfung übersetzt die Basis dieses Arrays vor dem Lane-Offset. Eine fehlende Zuordnung
bricht ab. Vor dem Aufnehmen einer Master-FX-Geste wählt die Prüfung den nativen Modus
MASTER FX, da das blaue Original mit TOUCH SCALE startet. Alle 29 direkten TAP-Prüfungen
bestehen damit. Die App-Capture-Prüfung wird nur bei vorhandenem Plugin-Laufzeithaken ausgeführt.

Schon das blaue Original löscht und beschreibt beim ersten Start den 4096-Byte-Sektor bei
`0x7EF000`. Das Dirty-Flag allein belegt deshalb keinen Schreibzugriff eines späteren
Würfelaufrufs. Vor und nach sechs Würfelaktionen waren das vollständige 16-MiB-Flash-Abbild
und die Zähler aller schreibenden SPI-Befehle gleich. Die Prüfung vergleicht beide Werte nach
dem Start. Ein Negativtest erkennt auch eine Änderung im Firmware-Bereich; ein weiterer
erkennt zusätzliche Schreibbefehle bei unverändertem Inhalt.

Der lange MFX-Vergleich verwendet den MFX-Patch allein gegen das Original. Ein Satz mit
Theme und Startbild würde die dort verlangte Bildgleichheit durch eigene Grafiken ändern.
Die Flash-Prüfung beginnt mit dem gestarteten Zustand und erfasst anschließend jede Änderung
beim Umschalten und Speichern. Der vollständige BLECH-Satz läuft zusätzlich durch `check.py`.
Der MIDI-Programmwechsel verwendet den von der Firmware gemeldeten Kanal. Bei ausbleibender
Antwort bricht die Prüfung ab. Vor dem Tastenvergleich werden die Geräteuhren angeglichen,
damit blinkende LEDs nicht zu unterschiedlichen Zeitpunkten verglichen werden.
Der lange MFX-Test besteht damit alle 56 Vergleiche, einschließlich eigener MFX-Typen pro
Pattern, WRITE, Neustart, beschädigter Speichersätze und anderer Tasten.

## DSP-Programm und Builder

**Im Emulator gemessen:** Die Argumente des DSP-Uploads sind auf der blauen Firmware
`0xC00DFB80` und 269428 Byte, Ende `0xC01217F4`. Das sind die Dateistellen `0xDFC80`
bis `0x1218F4`. Beim Sampler bleiben es `0xC00F9E10` und 271008 Byte, Ende
`0xC013C0B0`. `check.py` vergleicht den vollständigen zum Build gehörenden Bereich.
Ein Negativtest verändert den vorderen Teil des blauen DSP-Programms, den die Sampler-Grenzen
nicht erfasst hatten, und bestätigt die Ablehnung.

Die sechs Builder für Ausschaltbild, Patternwechsel, TAP Motion, NOTE ASSIST, Würfeln und MFX 2
wählen ihren Build im Funktionsaufruf selbst. Im selben Prozess wurde jeweils
`hacktribe`, dann `synth`, dann erneut `hacktribe` gebaut. Die beiden Sampler-Ergebnisse waren
identisch; die Synth-Ergebnisse entsprachen den erzeugten Dateien. Die neuen Kartenprüfungen
ändern keine Sampler-Patchbytes. Die NOTE-ASSIST-Ausgabe unterscheidet sich dort nur in ihrer
bereits zuvor abweichenden RAM-Beschreibung.

## Menü und Plugins auf dem Synth

**Im Emulator gemessen:** Der Synth-Wrapper bei `0xC0028170` initialisiert Menü,
Einstellungen, Blechy und Karten-Plugins nach der nativen Modell- und
Bildschirm-Initialisierung. EXIT, Panel-Update, besondere Startmodi und ungültige
Panel-Zeiger umgehen sämtliche eigenen Lader. Register und Flags bleiben
bis auf den Effekt des verdrängten nativen Befehls erhalten. Die
Ablehnung des früheren Einstiegs bei `0xC0028084` folgt aus der LED-Gegenprobe: dort weichen die LEDs LPF und MFX SEND vom Original ab.

Die native Bildschirmtabelle bei `0xC00DFA68` enthält 37 Einträge und 148 Byte.
BLECH ergänzt Bildschirm 37. Die Klassentabelle bei `0xC00C9BD8` hat 72 Byte.
Beide Tabellen werden erst beim Anwenden aus der geprüften eigenen Firmware
kopiert; das Repository enthält ihre Prüfsummen und eigene Überschreibungen.
Der Synth-Menüring hat ursprünglich 28 Einträge; BLECH und Blechy ergänzen zwei.
Der Zähler benutzt die native Vtable bei `0xC00CB660`.

Der Synth-Haken für die Spitzenebene bei `0xC0061DDC` ist ein eigener Wrapper
für die gemessenen Register r4 und r5. Der andere Sampler-Code wird nicht als
gleich eingetragen. Dasselbe gilt für die Eingangs-Funktion bei `0xC003D158`
und die Part-Auswahl bei `0xC0072338`: Ihre Aufrufverträge wurden gesondert
geprüft. Im Eingangs-Funktionskörper ab `0xC003D168` passen 100 maskierte
Befehle zum Sampler-Körper ab `0xC0042C18`; die Einstiege unterscheiden sich.
Global EDIT rechts hat ein vollständiges gemeinsames Fenster von sechs
Befehlen. WRITE hat acht gemeinsame Befehle bis zur aktuellen Bildschirmabfrage;
die folgenden abweichenden Zweige bleiben nativ.

Die RAM-Adressen kommen aus beobachteten Zeigern und nativen Zugriffen:
Sequenzermodell `0xC0582F78`, aktuelles Pattern `0xC0583FF0`, Transport
`0xC0583C98`, Bildschirm-Tick-Argument `0xC0593370` und dessen Redraw-Byte
bei `+0x4C`. Das native MUTE-Pad übergibt Objekt `0xC0596DF8`.
Der UART-Schreiber benutzt den Semaphor-5-Zähler bei `0xC057387C`.
Die zunächst über einen Heap-Abstand vermutete Adresse `0xC05740D0` enthält
FF und wurde abgelehnt. Herkunft und begrenzte Codefenster stehen in
`data/synth-map/script-runtime.json`.

Die Plugin-Suite prüft Kartenlader, leere und beschädigte Dateien, Zustimmung
zu fremden Plugins, Import und Export, Menüeinträge, Skriptfehler und Budget,
Displayübernahme und EXIT, Blechy, Snake sowie den Vergleich der App-Bilder
mit dem Browser. Dazu kommen Tempo, Pattern, Part, MUTE, PLAY und STOP,
Sequenzereignisse, LEDs, Hintergrundlicht und gespeicherte Plugin-Werte.
Statusantworten werden auf dem Synth mit Modellkennung `0x23` über den
lesenden BLECH-Befehl geprüft. Schreibbefehle bleiben gesperrt.

**Korrektur im roten Sampler-Build:** Die Gegenprobe deckte eine bereits zuvor
falsche gemeinsame MUTE-Objektadresse auf. Korg rot übergibt nativ
`0xC06CA798`, Hacktribe `0xC06CA760`. Die bisherige Adresse führt auf Rot
beim MUTE-Aufruf zu einer ungültigen Anweisung. Die rote Laufzeit hat deshalb
mit `script-runtime-stock.json` eine eigene Build-Variante; die gesamte
Plugin-Suite besteht damit auch auf Rot. Hacktribes Patchbytes sind bytegleich
zum vorherigen Satz. Die Build-Auswahl bleibt auf den einzelnen Aufruf begrenzt.

