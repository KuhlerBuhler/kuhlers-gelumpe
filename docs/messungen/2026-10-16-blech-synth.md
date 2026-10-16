# BLECH auf der blauen Electribe 2, Firmware 2.02

Stand 2026-10-16. Alle Prüfungen laufen offline oder im Emulator. Kein Gerät wurde beschrieben.

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
für die ersetzten 1024 Byte. Der Startbild-Editor aus dem Arbeitsstand gehört
nicht zum freigegebenen Synth-Satz: sein später Start-Haken hat anderen Code.

## Speicher

**Offline gemessen:** Das blaue Original ist von `0xC01217F4` bis `0xC01FFFF0` vollständig FF,
911356 Byte. `SYNTH_FREE_RUNS` in `data/patch-ram.mjs` hält diesen Bereich fest.
Der Platztest prüft den gewählten Synth-Satz auf Überschneidungen und seine deklarierten Bereiche
gegen diesen freien Abschnitt. `tools/emu/synth_ram_probe.py` misst Schreibzugriffe während
Start und Wiedergabe. Bei 8111 ms Gerätezeit war Bildschirm 1 erreicht, ohne Assertion und ohne einen Schreibzugriff in diesem Bereich.

## Entscheidungen zum Port

| Patch | Stand | Grund |
|---|---|---|
| BLECH SysEx | geprüft, 36 von 36 Prüfungen im Satz ohne Theme | Haken werden am Synth erkannt; Lesen, FLASH READ, Schreibsperre, EXIT und Korgs Befehle geprüft |
| Theme | geprüft, 37 von 37 Prüfungen im Satz mit SysEx | Vier Schriften und die vorhandenen Symbole passen |
| Startbild | geprüft, im Satz mit Ausschaltbild 43 von 43 | Eigene Grafik über den gemessenen Bildzeiger |
| Ausschaltbild | geprüft, 43 von 43 Prüfungen im wachsenden Satz | Generator und Ausschaltverhalten geprüft |
| Patternwechsel | geprüft, 73 von 73 im wachsenden Satz | Native Haken, Bestätigung, Abbruch, MIDI und Kartenprüfung |
| TAP Motion | geprüft, 102 von 102 im wachsenden Satz | Part-Motion und Master-FX-Gesten, echte Ausgangsmessung |
| NOTE ASSIST | geprüft, 128 von 128 im wachsenden Satz | Native Part-Auswahl, passende Noten und Kartenprüfung |
| Würfeln | geprüft, 141 von 141 im wachsenden Satz | Synth-Einstieg und Modellzugriff repariert; Flash-Prüfung erfasst alle Bereiche |
| MFX 2 | geprüft, 150 von 150 vor der Menü-Erweiterung, Langtest 56 von 56 | Startmodus, Tasten, Pattern, Speichern und Neustart |
| BLECH-Menü und Plugins | übernommen; 115 Menüprüfungen und die vollständige Plugin-Suite bestehen | Eigener geschützter Einstieg bei `0xC0028170`, Bildschirm 37, native Tabellen und Aufrufe; siehe [Synth-Start-Haken](2026-10-16-synth-start-haken.md) |
| Kartenordner blechtribe | nicht übernommen | Gemeinsamer Ordnerstring würde den Update-Pfad ändern; vorhandene Fenster sind zu kurz, siehe [Ordner-Messung](2026-10-16-blau-ladebalken-ordner.md) |
| Ladebalken | nicht nötig | Der Sample-Lader fehlt; die blaue Firmware hat einen eigenen PCM-Ladebalken, siehe dieselbe Messung |
| sample-errors | nicht nötig | Keine Sample-Slots und kein Sample-Import |
| synth-filters | nicht nötig | Im Synth bereits vorhanden |
| preset-tables | nicht übernommen | Getter gleich, je 100 verschiedene Zeiger im Abbild; die fünfte Knobspeicher-Stelle ist nicht mit gleichem Code bestätigt |
| Doom-Lader | nicht übernommen | Der native Aufruf bei Sampler-Adresse `0xC00005A0` ist nicht bestätigt; auch das nachgeladene Programm enthält Sampler-Adressen und den Ordner blechtribe |

## Prüfumgebung

Der Emulator erkennt die blaue Ladephase an Bildschirm 38. Er wartet dort wie bei Bildschirm 46
des roten Originals auf das Hauptbild; Rettungs- und Update-Modi gelten nicht als Ladephase.
Der Synth-SysEx-Patch wird in `check.py` erkannt und bekommt die lesenden Synth-Protokolltests.
Vorher wurden diese Prüfungen trotz vorhandenem Patch ausgelassen.

Die Patcher-Seite prüft die SHA-256 des blauen Originals und lädt dafür den Synth-Satz.
Der Update-Test verwendet den gemessenen Ordner `KORG/electribe/System/`. Weitere VSB-Dateien
in diesem Ordner werden abgelehnt und bleiben erhalten. Dort darf nur `SYSTEM.VSB` liegen.

## Vollständige Firmware-Prüfungen

Alle folgenden Läufe von `tools/emu/check.py` sind grün. Jede Synth-Stufe enthält die vorherigen
Patches sowie SysEx, Startbild und Theme. Nach jeder angenommenen Stufe wurden auch die beiden
Sampler-Sätze erneut geprüft. Die letzte Stufe enthält auf Rot zusätzlich
die oben beschriebene MUTE-Korrektur. Identische Dateien und Quelltexte können dabei
den an ihre Prüfsummen gebundenen Emulator-Cache verwenden.

| Synth-Stufe | Bestanden | Fehler |
|---|---:|---:|
| Ausschaltbild | 43 von 43 | 0 |
| dazu Patternwechsel | 73 von 73 | 0 |
| dazu TAP Motion | 102 von 102 | 0 |
| dazu NOTE ASSIST | 128 von 128 | 0 |
| dazu Würfeln | 141 von 141 | 0 |
| dazu MFX 2, vor der Menü-Erweiterung | 150 von 150 | 0 |
| dazu BLECH-Menü und Plugins, vollständiger Synth-Satz | 269 von 269 | 0 |

| Firmware | Satz | Bestanden | Fehler |
|---|---|---:|---:|
| Korg blau, Synth 2.02 | `blech-synth.json` | 269 von 269 | 0 |
| Hacktribe 2.02 | `blech.json` | 334 von 334 | 0 |
| Korg rot, Sampler 2.02 | `blech.json` | 359 von 359 | 0 |

Die gebaute `SYSTEM-blech-v26-blau.VSB` hat 2097408 Byte und ist bytegleich mit dem Exemplar
des grünen Gesamtlaufs und des virtuellen Update-Tests. Ihre SHA-256 ist
`bea2ed650cf20006424e2a6c51d77c41e71ba4572dc292306b3c743865bf82c8`.
Startseite und README nennen den geprüften Synth-Satz mit seinen Grenzen. Eine Prüfung am
Gerät wurde nicht ausgeführt.

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
[Start-Messung](2026-10-16-synth-start-haken.md) erklärt die Ablehnung des
früheren Einstiegs bei `0xC0028084` nach der LED-Gegenprobe.

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

## Virtuelle Update-Karte

**Mit dem echten Emulator-Dienst geprüft:** Blaues Original geladen, Synth-Kandidat über
`Emulator.put_system` auf die virtuelle Karte gelegt. Der Dienst meldete Build `synth` und
Ordner `electribe`. Unter `KORG/electribe/System/` lag ausschließlich `SYSTEM.VSB`.
Die gespeicherte Datei entsprach Byte für Byte dem Kandidaten. Die Karte war danach eingelegt.
Ein Browsertest bestätigt denselben Ablauf von Dateiauswahl über Prüfung und Download bis
zum Update-Test. Die Übertragung auf einen echten Speicherchip wurde nicht ausgeführt.

**SOFTWARE UPDATE im Emulator ausgeführt:** Das blaue Original aktualisiert auf den
vollständigen Synth-Kandidaten, danach wird der Kandidat gestartet. Anschließend läuft der
gleiche Weg zum Original zurück. Beide Updates schreiben ausschließlich `[0x020000, 0x220000)`,
mit je 512 Löschungen zu 4096 Byte und 8192 Programmierschritten zu 256 Byte. Unterhalb des
Firmware-Bereichs, in den Benutzerdaten und in der PCM-Bank ändern sie nichts. Beide Neustarts
erreichen das Hauptbild, laden PCM erfolgreich und haben keine Assertion. Nach dem Rückweg
ist das gesamte Flash-Abbild wieder gleich dem Zustand nach dem ersten Originalstart.

## Browser, Tests und Paketierung

`npm test`: 1060 Tests, davon 917 bestanden und 143 übersprungen, keine Fehler.
`npm run test:e2e`: 162 Tests, davon 161 bestanden und einer übersprungen, keine Fehler.
Die gesonderte Patcher-Suite besteht alle zwölf Fälle, darunter die blaue Auswahl, der
Synth-Satz, der Download und der virtuelle Update-Pfad. Die Python-Suiten laufen zusätzlich
mit Unicorn: Emulator 206 Tests, davon 187 bestanden und 19 übersprungen; Patch-Werkzeuge
123 Tests, davon 122 bestanden und einer übersprungen. Der Capstone-Vergleich besteht
mit der zusätzlichen Bibliothek. Der ausgelassene Test benötigt eine eigens angegebene
Firmware-Datei. Alle Suiten haben null Fehler.

Die Adresstabellen werden mit dem Sidecar gebündelt. Ein Test mit simuliertem Entpackordner
bestätigt, dass `synthaddr.py` sie dort liest. Ein nativer Sidecar-Build wurde nicht ausgeführt.
Die Seite wurde im Browser aus den Projektquellen geprüft.
