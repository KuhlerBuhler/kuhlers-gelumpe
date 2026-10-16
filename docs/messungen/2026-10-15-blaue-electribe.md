# Die blaue Electribe 2 (Synth) im Emulator

Stand 2026-10-15. Im Emulator und offline, kein Gerät. Eingabe: die `SYSTEM.VSB` 2.02 der blauen Electribe 2 aus dem
Systemupdate von Korg (sha256 `41fc5f1c...`), zum Vergleich Korgs Sampler-Original 2.02 (`1d0f0689...`) und die
eigene Hacktribe-Datei. Die Dateien liegen nicht im Repository, nur Ergebnisse, Adressen und Hashes. Markierungen:
**gemessen** (ausgeführt, Befehl genannt), **offline** (Bytes oder Code gelesen), **hergeleitet**, **offen**.

## Kurzfassung

1. **Die Firmware der blauen Electribe läuft im Emulator bis zum Hauptbildschirm**, mit leerem Flash nach 0,5 s
   Gerätezeit (Bildschirmnummer 1, wie beim Sampler). Sie nimmt Tasten und Drehgeber, MENU und EXIT führen hin und
   zurück, Ein/Aus schaltet sie aus, die LEDs werden gesetzt, das Display wird gezeichnet. Keine Assertion.
2. **Sie ist derselbe Code wie beim Sampler, nur verschoben.** Sechs der sieben Stellen, die der Emulator braucht,
   haben dieselbe Signatur wie beim Sampler und sitzen 0x2B94 bis 0x46D8 Byte weiter vorn. Nur der
   Bildschirm-Verwalter hat eine eigene Signatur, weil er einen anderen Zeiger lädt; der Code davor und danach ist
   Wort für Wort gleich.
3. **Es fehlten zwei Dinge:** die Stelle `screens` (die Signatur war auf den Zeiger des Sampler-Builds gebaut) und die
   Nutzerdaten-Kennung im Flash. Die blaue Firmware prüft `KORGelec2USR` bei Flash-Adresse `0x220000`, der Sampler
   `KORGele2sUSR`. Mit der Kennung des Samplers zeigt die blaue Firmware SOFTWARE UPDATE statt des Hauptbilds, auch
   mit dem Flash-Abbild eines Sampler-Geräts.
4. **Der Emulator kennt sie jetzt als dritten Build `synth`.** Die Stellen werden wie beim Sampler am Code gefunden,
   der Flash trägt die Kennung des Synths, und der Dienst hält ihre Nutzerdaten in einer eigenen Datei
   (`flash-synth.bin`), damit sie nicht den Flash des Samplers überschreiben.
5. **Offen:** Klang (der Emulator hat keinen), ein benutzter Flash der blauen Electribe (es gibt keinen), Ladezeit
   mit solchem Flash, ob die Firmware die Karte benutzt und in welchem Ordner, Bedienelemente, die es nur am Synth
   gibt (die Bedienfeld-Nummern sind die des Samplers).

## Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| Größe, Kopf und Ladeschema sind wie beim Sampler: `0x200100` Byte, `0x100` Byte Kopf, Nutzlast ab `0xC0000000` | offline | `cmp -l` über die ersten `0x100` Byte beider Dateien: genau zwei Bytes unterscheiden sich, `0x12` (Dateityp `E2` statt `E2S`) und `0x2E` (`0x23` statt `0x24`); was das zweite bedeutet ist offen. Von der Nutzlast sind rund 1,17 Millionen Byte verschieden (alles ist verschoben) |
| Der Lauf bei `0x170000`, den nur Hacktribe füllt, ist bei der blauen Datei 0xFF (`build_of` sagt "stock") | gemessen | `firmware.py`, `build_of`; deshalb prüft die Seite den Kopf zuerst und der Dienst den Code |
| Sechs Signaturen sind dieselben wie beim Sampler, nur an anderen Adressen | gemessen | `firmware.search` über das Abbild: `assert_handler 0xC0026C34`, `flash_read 0xC0019DD4`, `dsp_upload 0xC000DD08`, `tx_full 0xC00205C0`, `panel 0xC00254D0`, `user_check 0xC00270BC` |
| Der Bildschirm-Verwalter ist an `0xC002A1AC` und bis auf das Wort mit dem Zeiger gleich (15 von 16 Wörtern) | offline | Fenster der Sampler-Stelle gegen das ganze blaue Abbild, bester Treffer |
| Die Zeiger: `screens` `0xC03406B0` (Sampler `0xC03404C0`), `panel` `0xC033E8F8` (Sampler `0xC033E6F8`) | offline | `read_value` an den Stellen |
| Mit diesen Stellen und dem Zeiger bootet die Firmware: Bildschirm 38 bei 0,1 s, 0 bei 0,3 s, 1 (Hauptbild) bei 0,5 s | gemessen | Maschine alle 100 ms angesehen, leerer Flash mit Kennung des Synths |
| Ohne Stelle `screens` läuft sie genauso (kein Haken wird dafür gebraucht), der Emulator kennt dann nur die Bildschirmnummer nicht | gemessen | Lauf mit Profil ohne `screens`, 8 s, keine Assertion, Hauptbild gezeichnet |
| Leerer Flash mit der Kennung des Samplers: SOFTWARE UPDATE; mit der Kennung des Synths: Hauptbild | gemessen | `machine.py` mit beiden Kennungen; Strings `elec2USR` und `ele2sUSR` stehen in beiden Abbildern, geprüft wird bei jedem Build nur eine |
| Das eigene Flash-Abbild des Samplers (Hacktribe, 2026-10-09) führt die blaue Firmware ebenfalls zu SOFTWARE UPDATE | gemessen | `machine.py --flash ...`, 8 s, kein Hauptbild |
| Tasten gehen: MENU zeigt das Pattern-Menü (1/28), EXIT führt zum selben Bild wie vorher, ein Drehgeberschritt ändert das Display, Ein/Aus schaltet aus (Display leer) | gemessen | `machine.py --send ...`, Anzeige-Hash verglichen; die Nachrichten sind die des Samplers (`data/panel.mjs`) |
| Der Hauptbildschirm zeigt `Init Pattern`, `Part:01`, `OSC: SAW` | gemessen | Bild der Anzeige (nicht im Repository, es zeigt Korgs Bildschirm) |
| Die blaue Firmware enthält kein `e2sSample.all`, aber die Pfade `KORG/electribe/` und `KORG/electribe sampler/` | offline | `strings` über das Abbild |
| Der Kartenordner der blauen Firmware ist `electribe` | hergeleitet | der Pfad steht im Abbild; ob und wofür die Firmware die Karte öffnet, ist nicht gemessen |
| Der Emulator zeigt für Hacktribe und das Sampler-Original dasselbe wie vorher | gemessen | `npm test` und die Emulator-Tests, siehe unten |

## Frage: Könnte BLECH auf der Synth-Firmware Sample laden und speichern, mit allen Oszillatoren?

**Kurzantwort: nach den Belegen nein, nicht als kleiner Patch.** Die Synth-Firmware hat keinen Sample-Pfad, den man
freischalten könnte. Hacktribe löst es anders: es setzt die Firmware des Samplers auf die Hardware des Synths. Dabei
gehen die Synth-Stimmen und PCM-Klänge verloren. Das ist am Code der Synth-Firmware belegt, was Hacktribe genau tut,
nur aus dessen öffentlicher Beschreibung.

| Behauptung | Status | Beleg |
|---|---|---|
| Beide Firmwares bestehen aus denselben 24 Quelldateien (gleiche Liste von `.cpp`-Namen in den Assertion-Texten, darunter `DspIf.cpp`, `VoiceTask.cpp`, `Timbre.cpp`) | gemessen | `strings` über beide Abbilder, Listen verglichen: kein Name nur auf einer Seite |
| Im Sampler stehen 31 Zeilen mit "sample" (IMPORT SAMPLE, EXPORT SAMPLE, EXPORT ALL SAMPLE, SAMPLE EDIT, TIME SLICE, CLEAR SLICE, DELETE SAMPLE, SELECT SAMPLE, `e2sSample.all`, `Sample/`), im Synth 4, und keine davon ist ein Sample-Menü (Ableton-Export `SampleRef`, Ordnername `electribe sampler`, `/PCM.VSB`, `elec2PCM`) | gemessen | `strings -a \| grep -ic sample`: 31 gegen 4, die Treffer einzeln gelesen |
| Der Synth hat statt Samples ein PCM-Update: `PCM Update`, `User/PCM`, `/PCM.VSB`, `PCM :%2d.%02d.%02d`; seine Oszillatoren heißen u. a. `WaveDrum1` bis `WaveDrum8`, `Wavestation`, `GamelanWave`. Der Sampler hat dagegen `/SLICE.VSB` | offline | Strings; was in `PCM.VSB` steht, ist nicht gelesen (die Datei liegt nicht vor) |
| Der Synth kann Audio als WAV schreiben (`EXPORT AUDIO`, `EXPORT CHAIN AUDIO`, `RIFFWAVEfmt `), hat aber keinen Import von WAV und keine Sample-Tabelle in den Strings | offline | Strings; ein fehlender Text ist kein Beweis, dass der Code fehlt (hergeleitet) |
| Das DSP-Programm ist ein anderes: 269428 Byte (Sampler 271008), bei gleicher Lage in nur 36678 Byte gleich; beide werden einmal beim Start über SPI1 geladen | gemessen | Abbild bei `dsp_upload` aus dem Speicher gelesen (R1, R2), beide Dateien |
| Ob das DSP-Programm der blauen Firmware eine Sample-Stimme enthält | offen | Das DSP-Programm ist nicht disassembliert; die Strings des Hauptprozessors sagen darüber nichts |
| Hacktribe ist "based on sampler firmware version 2.02" und unterstützt Synth- und Sampler-Hardware | öffentliche Beschreibung des Projekts (GitHub-Seite von Hacktribe) | nicht selbst geprüft |
| Auf der Synth-Hardware entfernt Hacktribe die Synth-Stimmen und PCM-Instrumente und bringt Sampling, zwei Synth-Engines und Effekte | öffentliche Beschreibung (Presse- und Forenberichte), nicht selbst geprüft | |

Folgerungen (**hergeleitet**):

- Ein BLECH-Patch auf der Synth-Firmware müsste Sample-Speicher, Tabellen, Import und Export, die Sample-Stimme im
  DSP und die Menüs neu bauen. Der Code dafür steht in der Synth-Firmware nicht, und der Teil im DSP wäre ein
  Eingriff in ein Programm, das wir nicht lesen. Das ist kein Patch in der Größe von BLECH.
- Alle Patches und Adressen von BLECH gelten für den Sampler (Hacktribe oder Korgs Original); auf der Synth-Firmware
  stimmen weder Adressen noch erwartete Bytes.
- Der Weg, der existiert, ist umgekehrt: die Sampler-Firmware auf der Synth-Hardware. Sie kommt mit dem Sampler-Teil
  des DSP-Programms, aber ohne die Synth-Stimmen. Ob die Oszillatoren der Synth-Firmware als Samples in diese
  Firmware gelegt werden können ("Oszillatoren als Samples"), ist eine eigene Frage: PCM-Wellen der Synth-Firmware
  ließen sich vielleicht als Samples ablegen, die Stimmen, die sie aus den Reglern formen (Filter, Modulation,
  Oszillator-Parameter), blieben aber im DSP-Programm der Synth-Firmware. Das ist offen und nicht gemessen.
- Prüfbar wäre es im Emulator nur halb: er hat keinen DSP und keinen Klang.

## Was am Emulator allgemein ist und was am Sampler hängt

Allgemein, ohne Änderung für die blaue Firmware: CPU und Speicherabbild (Unicorn, ARM926), Zeit und Takt, Interrupts,
der Flash als SPI-Baustein (Lesen, Schreiben, Löschen), das Bedienfeld-Protokoll (UART, Version, gehaltene Tasten,
LEDs), das Display (SPI, 128 mal 64) mit der LCD-Trägheit, die SD-Karte (der Controller; die Firmware fragt den
Karten-Eingang), der DSP als Briefkasten, MIDI (UART). Dazu die vier Einsprünge im Code (Assertion, Flash-Lesen,
DSP-Upload, volle Sendeschleife): sie sitzen an anderen Adressen, der Code dort ist gleich.

Am Sampler hängt dagegen:

- **Die Adressen und der Zeiger** der Stellen (`firmware.py`), jetzt in einer zweiten Tabelle für den Synth.
- **Die Nutzerdaten-Kennung** im Flash (`Profile.user_mark`).
- **Der Kartenordner** (`KORG/hacktribe/`, `KORG/electribe sampler/`): beim Synth `electribe`, hergeleitet.
- **Alles auf der Seite, was Hacktribe oder BLECH braucht:** SysEx `0x52` bis `0x57`, die Tabellen der Gerätekarte,
  der Effekt-Editor, die Patches und Plugins, die Samples und ihre Pfade. Die blaue Firmware hat weder Hacktribes
  Code noch die Tabellen der Karte, und die Patches sind für Adressen des Samplers gebaut.
- **Die Prüffälle** in `check.py`, `splash_cases.py`, `mfx_cases.py`, `menu_cases.py`, `script_cases.py`: ihre
  Konstanten sind Adressen des Samplers. `check.py` gegen die blaue Firmware ist nicht gelaufen und ist keine
  Aufgabe dieser Messung.

## Was der Emulator tut

- `tools/emu/firmware.py` nimmt die blaue Firmware als dritten Build `synth` (`SYNTH_SITES`): erst die Tabelle des
  Samplers, wenn die nicht passt die des Synths. Der Sampler-Weg ist unverändert.
- `Machine` legt den Flash mit der Kennung des Build an (`Profile.user_mark`).
- Der Dienst hält den Flash des Synths in `flash-synth.bin` neben `flash.bin` und meldet den Build `synth` im Status.
- Die Seite erkennt die Datei am Kopf (`buildOf`), sagt das in einer Zeile und bietet Editor, Patches und Plugins für
  diese Firmware nicht an (`FEATURES.synth`). Eine eigene Übersicht dessen, was fehlt, gibt es nicht.

Tests: `test/emulator-blue.test.mjs` (nur mit `E2_BLUE_VSB`), `test/firmware.test.mjs`, `tools/emu/test_firmware.py`,
`tools/emu/test_flashstore.py`.

## Entscheidungen, die ohne Rückfrage fielen

1. Der Build heißt `synth`, nicht `blue`: Farbe ist ein Handelsname, der Unterschied ist, dass es der Synth ist.
2. Eigene Flash-Datei für den Synth, statt `flash.bin` zu teilen: die Nutzerdaten beider Geräte sind verschieden,
   und eine geteilte Datei würde bei jedem Wechsel der Firmware die Daten des anderen überschreiben.
3. Kartenordner `electribe`, weil dieser Pfad im Abbild steht. Eine Messung, welchen Ordner die Firmware beim
   Update oder bei DATA UTILITY tatsächlich liest, fehlt.
4. Die Seite erkennt den Synth am Kopf der Datei, nicht am Code, weil die Seite keinen Python-Dienst braucht, um eine
   Datei zu beschriften. Der Dienst prüft zusätzlich den Code, und nur er entscheidet, ob die Firmware startet.
5. Der Bereich "Gerät" und die Seitenleiste "Am Gerät" bleiben für den Synth leer: beide brauchen SysEx von
   Hacktribe. Ob die Seite sie auch dann versucht, ist im Browser nicht geprüft.

## BLECH auf der blauen Electribe 2: Plan für nach dem Release

Übertragen ist nur der SysEx-Patch ([BLECH SysEx, Abschnitt Synth](2026-10-15-blech-sysex.md)). Der Rest von BLECH ist nicht begonnen. Was dafür
gemessen ist und was fehlt:

| Befund | Status | Beleg |
|---|---|---|
| Die Abbilder lassen sich ausrichten: 2036 Läufe gleicher Wörter, 85,0 Prozent des Abbilds, 6803 Zeiger, jeder Ort des SysEx-Patches (Haken, Funktionen, Sprungziele) wurde damit gefunden und trug dieselben 16 Wörter | gemessen | `tools/patch/fwmap.py --ref SAMPLER.VSB --vsb SYNTH.VSB ADRESSE...` |
| RAM-Variablen werden über die Literalpools gefunden (Bedienfeld `0xC033E6F8` zu `0xC033E8F8`, Bildschirm-Verwalter `0xC03404C0` zu `0xC03406B0`), nicht alle: der Parser-Zustand des SysEx liegt unverschoben, Felder mitten in Arrays (Display-Puffer, Tick-Zähler) haben keinen eigenen Zeiger und müssen einzeln hergeleitet werden | gemessen | `fwmap.py`, Ladebefehle beider Abbilder |
| Der freie Lauf des Synths (`0xC01217F4` bis `0xC0200000`) enthält den des Samplers (`0xC013C0B0` bis `0xC0200000`): Code und RAM der Patches behalten ihre Adressen | gemessen | Läufe aus `FF` in beiden Abbildern |
| Das Modellbyte des Rahmens ist beim Synth `0x23`, beim Sampler `0x24` | gemessen | Gerätesuche im Emulator |
| Zahl der Firmware-Adressen, die ein Builder festlegt (verschiedene `0xC0...`-Werte im Quelltext): Startbild-Editor 49, MFX 2 31, Pattern-Schalter 28, TAP-Motion 26, Notenassistent 17, Ladebalken 19, Power-off 10, Laufzeit (Haken 39, Menü 54, Hardware 17, LED 8, Karte 6) | gemessen | Suche im Quelltext von `tools/patch/` |

Vorgehen, wenn es soweit ist, je Patch: Builder bekommen wie `blech_sysex.py` ein `--build synth --ref` und übersetzen ihre Adressen über `fwmap.py`
(Code mit Prüfung der 16 Wörter, RAM-Variablen mit Prüfung am Lader); die Haken-Tabelle `data/hooks.mjs` bekommt je Kette die Stellen des Synths; die
Prüffälle (`menu_cases`, `mfx_cases`, `splash_cases` und die anderen, die Adressen des Samplers fest tragen) werden auf dieselbe Übersetzung umgestellt, sonst prüfen sie
am Synth nichts; die Schutzzeit der Startphase (`bootmap.py`) und die gesperrten Bereiche werden für den Synth neu gemessen; die Schutztabelle des SysEx bekommt die
RAM-Karte des Synths (Heap, Stacks, Patternbank), bis dahin verweigert sie jedes Schreiben. Reihenfolge nach Nutzen und Risiko: Theme und Startbild (Daten), Power-off-Bild,
MFX 2, Notenassistent, TAP-Motion, Pattern-Schalter, dann Menü und Laufzeit (die größte Zahl von Adressen und ein Menü, das auf den Bildschirm-Klassen des Synths sitzen muss).

Nicht übertragen, mit Grund: Samplepfade, Ladebalken beim Laden der Samples und Kartenordner `electribe sampler` (der Synth hat keine Samples; sein Ordner heißt `electribe`, und
ob ein Umbenennen etwas bringt, ist nicht gemessen), Synth-Filter (sie setzen die Sampler-Hardware voraus, die der Synth nicht hat) und Preset-Tabellen (die Tabellen von Hacktribe gibt es im Synth nicht).
Alle Oszillator- und PCM-Dinge bleiben unberührt, das PCM-Update der Firmware schreibt den Bereich ab `0x800000`; **offen:** ob SOFTWARE UPDATE auf dem Synth nur `0x020000` bis `0x220000` schreibt
(beim Sampler gemessen), das ist am Synth noch nicht gemessen und gehört vor jeden Gerätetest einer Firmware für den Synth.

## SOFTWARE UPDATE der blauen Electribe 2: Ordner, Schreibbereich, Hin und Zurück

Im Emulator gemessen (2026-10-15), Netzteil eingesteckt, mit `tools/emu/synth_update_probe.py`; die Bilder der Anzeige je Schritt liegen nur lokal (Korg-Schirme). Eingabe: die
Original-Firmware 2.02 der blauen, `SYSTEM-blech-v22-synth.VSB` (nur der SysEx-Patch mit FLASH READ), ein Flash mit der PCM-Bank aus den WAVs
([PCM-Bank](2026-10-15-synth-pcm-flash.md)), nach einem ersten Start (dabei schreibt die Firmware einmal 4 KiB bei `0x7EF000`, ihre Marke; auf einem benutzten Gerät ist sie da).

| Befund | Status | Beleg |
|---|---|---|
| **Ordner:** die Firmware sucht `SD:KORG/electribe/System/`, und zwar der Reihe nach `BOOT.VSB`, `USER.VSB`, `PCM.VSB`, `SYSTEM.VSB`. Bei ENTER ohne Datei steht "Error / No File". Das gilt für die Original-Firmware und für v22-synth (derselbe Ordner) | gemessen | Haken auf `f_open`, Pfade gelesen |
| **Bedienung:** DATA UTILITY hat 11 Seiten, SOFTWARE UPDATE ist die letzte (11/11): MENU, zweimal EDIT links, MENU, zehnmal EDIT rechts, dann dreimal MENU. Die Anzeige: "Now Version 2.02, Next Version 2.02, press [Enter]", dann "Are You Sure ?", dann "Working...", dann "OK. Please Reboot." (Bildschirm 29) | gemessen | Bilder je Schritt |
| **Hin** (Original zu v22-synth): 512 Löschbefehle zu 4 KiB und 8192 Seitenprogrammierungen zu 256 Byte (2.097.152 Byte), alle in `[0x020000, 0x220000)`. Im ganzen 16-MiB-Flash unterscheiden sich danach nur Bytes in `0x041D70` bis `0x193814` (26 Folgen: die Haken und der Code des Patches), `[0x220000, 0x800000)` (Nutzerbereich) und `[0x800000, 0x1000000)` (PCM-Bank) sind byteweise gleich, unterhalb `0x020000` ebenso, der Bereich `0x020000` bis `0x220000` ist genau die Nutzlast der Datei | gemessen | Befehlsprotokoll des Flash-Chips, Vergleich vorher und nachher |
| **Neustart** aus dem aktualisierten Flash: v22-synth erreicht das Hauptbild, die PCM-Ladung meldet Erfolg (`r6` 1), keine Assertion; INFO antwortet mit Flags `0xF` und Flash-Block 4096, FLASH READ liefert an `0x020000`, `0x220000`, `0x800000` und `0xFFFFFF` die Bytes des Flash | gemessen | `sysex_cases.Link` gegen die Maschine |
| **Zurück** (aus der laufenden v22-synth mit der Original-VSB im selben Ordner): derselbe Schreibbereich (512 Löschbefehle, 8192 Programmierungen, nur `[0x020000, 0x220000)`), Bank und Nutzerbereich gleich, der Bereich ist wieder die Original-Nutzlast, die Original-Firmware startet zum Hauptbild, PCM-Ladung ok | gemessen | dasselbe |
| Nach Hin und Zurück ist der ganze 16-MiB-Flash byteweise gleich dem Stand davor | gemessen | Vergleich |

Wichtig für die Karte: die Firmware fragt auch nach `BOOT.VSB`, `USER.VSB` und `PCM.VSB` im selben Ordner. Liegt dort eine davon, ist nicht gemessen, was passiert (`PCM.VSB` würde nach der
Prüfung des Aufbaus den Bereich ab `0x800000` neu schreiben, siehe [Samples](2026-10-15-synth-samples.md)). Für diesen Test darf in `KORG/electribe/System/` **nur** `SYSTEM.VSB` liegen.
Nicht gemessen: ein Stromausfall mitten im Schreiben, die Batterie ("Battery Low" ohne Netzteil) und das Verhalten am echten Gerät.
