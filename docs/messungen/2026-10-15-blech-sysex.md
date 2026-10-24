# BLECH SysEx: RAM lesen und schreiben in großen Blöcken

Stand 2026-10-15. Kein Gerätezugriff, alles im Emulator gemessen (Hacktribe 2.02 und Korgs Original 2.02, beide mit
BLECH, mit dem eigenen Flash-Abbild), über die emulierte DIN-MIDI wie in [DIN-MIDI und SysEx](2026-10-09-din-sysex.md).
Markierungen: **gemessen** (ausgeführt), **offline** (Code gelesen), **hergeleitet**, **offen**. Der Patch ist
`data/patches/blech-sysex.json`, gebaut von `tools/patch/blech_sysex.py`, die Prüffälle stehen in
`tools/emu/sysex_cases.py`.

## Wozu

Korgs Original kennt Hacktribes Befehle `0x52` bis `0x57` nicht ([Original im Emulator](2026-10-14-stock-emulator.md)),
deshalb konnte die Seite dort nichts live ins RAM schreiben und nichts lesen. BLECH bringt jetzt eigene Befehle mit, die
auch auf Korgs Original gehen, in größeren Blöcken als Hacktribes 256 Byte und mit einer Prüfsumme je Block und
einer Antwort, die sagt, wie es ausgegangen ist. Von Hacktribes Code ist nichts übernommen: die Befehle sind von der
Nachricht bis zur Prüfsumme neu geschrieben, nur Adressen und Namen der Firmware sind dieselben.

## Das Protokoll

Der Rahmen ist Korgs: `F0 42 3n 00 01 24 <Funktion> <Nutzdaten> F7`, n der globale Kanal. Die Nutzdaten sind
32-Bit-Wörter, Little Endian, wie jede Electribe-Nutzlast 7-Bit-gepackt (`src/bytes.mjs`). Die Funktionsbytes liegen
außerhalb dessen, was Korg (`0x0E`, `0x10`, `0x11`, `0x1C`, `0x21` bis `0x26`, `0x30` bis `0x32`, `0x40`, `0x41`,
`0x4C`, `0x50`, `0x51`) und Hacktribe (`0x52` bis `0x58`) belegen.

| Funktion | Anfrage | Antwort | Nutzdaten der Antwort |
|---|---|---|---|
| `0x60` INFO | nichts | `0x68` | Status, Version (1), Flags (1 lesen, 2 schreiben, 4 CRC-32, 8 FLASH READ), größter Block, CRC-32 der Schutztabelle, größter Block von FLASH READ (4096) |
| `0x61` READ | Adresse, Länge | `0x69` | Status, Adresse, Länge, CRC-32, dann die Bytes |
| `0x62` WRITE BEGIN | Adresse, Länge, CRC-32 der Bytes | `0x6A` | Status, Adresse, Länge |
| `0x63` WRITE DATA | die Bytes, so viele wie BEGIN sagte | `0x6B` | Status, Adresse, Länge, CRC-32 des RAM nach dem Kopieren |
| `0x64` FLASH READ | Flash-Adresse, Länge | `0x6C` | Status, Adresse, Länge, CRC-32, dann die Bytes des Flash |

Status: 0 in Ordnung, 1 Prüfsumme stimmt nicht, 2 verweigert, 3 außerhalb des erlaubten Bereichs, 4 die Flash-Funktion der Firmware
meldet keinen Erfolg (nur FLASH READ), 5 das Zurücklesen nach dem Kopieren weicht ab. Die CRC-32 ist die von zlib (Polynom `0xEDB88320`). Der größte Block ist 32768 Byte
(`MAX_BLOCK`), das ist die Größe des eigenen Puffers, nicht eine Grenze der Firmware.

Ein Schreiben sind zwei Nachrichten: BEGIN prüft Adresse und Länge gegen die Schutztabelle, damit eine Ablehnung kommt, bevor
ein Byte gesendet ist, und merkt sich Adresse, Länge und CRC. DATA wird in einen eigenen Puffer dekodiert, gegen die CRC geprüft,
erst dann an die Adresse kopiert, und die Antwort trägt die CRC dessen, was danach im RAM steht. Ein DATA ohne BEGIN wird
nicht angenommen und nicht beantwortet, jedes BEGIN gilt für genau ein DATA.

Es gibt keinen Befehl, der den Flash schreibt oder löscht. EXEC (`0x6F`, Antwort `0x70`: Status, Adresse, r0) führt Code aus, aber nur an einem Wort des Stub-Puffers (`0xC1000000` bis `0xC1000400`, `data/exec.mjs`) und nur, wo die Schutztabelle dem Editor das Schreiben erlaubt (auf der blauen also nie); vorher leert es den Schreibpuffer und den Befehls-Cache, das Argument kommt in r0. Hacktribes Befehle `0x52` bis `0x57` verwerfen beide Haken, mit EXIT beim Einschalten gehen sie wieder, außer dem Flash-Schreiben `0x56` ([Messung vom 24.10.](2026-10-24-hacktribe-flash.md)). FLASH READ liest nur (siehe unten). Die Schutztabelle (`src/sysex-table.mjs`,
412 Byte) wird aus `data/protected.mjs` und den erklärten Bereichen des Editors geschnitten und beim Bau in den Patch
geschrieben, nie von Hand: das RAM-Fenster von 128 MiB, jede geschützte RAM-Region (Schreiben), die zwei Regionen, die auch
Lesen sperren (Lader, DSP-Ports), die Ausnahmefenster der drei Regionen mit `except` (Tabellen und Menülängen,
Display, Sample-Name und -Tune, Stub-Puffer; die 998 Namen und Tunes sind je ein Lauf mit Abstand) und beim Schreiben der Spiegel in
der anderen Fensterhälfte ohne Ausnahme. Das Abbild des Patches selbst liegt in der Region `firmware-image`, ist also für
Schreiben gesperrt.

## Wo es in der Firmware hängt

| Was | Wert | Art |
|---|---|---|
| Der Zustandsautomat der SysEx-Bytes entscheidet beim Funktionsbyte über Länge und Ziel der Nutzdaten | Funktion `0xC0026A8C`, Rückgabe der Folgezustand, `0x1E` heißt "Daten in den Puffer lesen" | offline gelesen, am Verhalten gemessen |
| Die Daten dekodiert der Automat selbst in einen Puffer: Beschreibung bei `0xC033E6CC` (Zeiger, Rest, Zähler, Packungszustand), Merker `0xC033E6C9` für "vollständig, das F7 gibt die Nachricht weiter" | | offline gelesen |
| Hacktribes Haken sitzt bei `0xC0026B00` und bei `0xC00265B0`, nicht am Funktionsanfang | beide Builds haben den Funktionsanfang `0xC0026A8C` und den Ausführer `0xC0026418` unverändert | gemessen (Bytevergleich, beide Hashes gleich) |
| Der Ausführer läuft in CommandTask, ein Aufruf aus zwei Warteschlangen | `0xC0026418`, Hacktribes Umweg `0xC01707F0` endet dort | offline gelesen |
| Antworten gehen über die Sperre `0xC0027D54` bis `0xC0027D6C`, die den Parser ruhig hält, und `0xC0027834` (Puffer, Länge, Port); den Port, aus dem die Anfrage kam, liefert `0xC0026260` | | offline gelesen |
| Der globale Kanal steht bei `0xC00F930F` | | offline gelesen |

Zwei Haken, beide ein Sprung auf den ersten Befehl, der verdrängte Befehl läuft im Patch. Für jedes andere Funktionsbyte geht
der Haken zum Original weiter. Mit EXIT beim Einschalten tut keiner der beiden etwas: die vier Funktionsbytes werden nicht
genommen, das Gerät schweigt dazu wie Korgs Original. Kein Haken in der Startphase.

Der Code (1760 Byte) liegt bei `0xC0172100`, die Tabelle bei `0xC0173800`, der Zustand bei `0xC0191000` und der Puffer
bei `0xC0191100` bis `0xC01A0000` (61184 Byte, genug für einen Block von 32768 Byte, dessen Antwort 37 KiB packt: die
Antwort wird von hinten im selben Puffer gepackt, ohne zweite Kopie). Das ist der freie Lauf hinter dem Code der
Synth-Filter, in beiden Builds `FF`. Zuerst lagen Zustand und Puffer bei `0xC0174000` bis `0xC0180000`; dort liegen
seit den Preset-Tabellen deren Plätze für weitere Presets (`0xC0174000` bis `0xC017CC00`), also zogen Zustand und Puffer um.

## Belegtabelle

| Behauptung | Status | Beleg |
|---|---|---|
| Der Code des Patches ist für beide Builds derselbe, die ersetzten Bytes haben dieselben Prüfsummen; die Schutztabelle ist je Build eigen (`blech-sysex.json`, `blech-sysex-stock.json`), weil Hacktribes Presets in zwei Tabellen liegen und Korgs verstreut, siehe [Effekt-Editor auf Korgs Original](2026-10-15-effekt-editor-original.md) | gemessen | `blech_sysex.mjs --vsb` gegen beide Dateien gibt dieselben Dateien, `test/blech-sysex.test.mjs` |
| INFO wird beantwortet: Version 1, Flags 15 (mit FLASH READ, vorher 7), größter Block 32768, Tabellen-CRC `0x662EEC2A` gleich der CRC der Tabelle im Abbild, größter Flash-Block 4096 | gemessen | `sysex:info`, beide Builds |
| READ von 1, 4, 7, 8, 13, 524, 4096, 16384 und 32768 Byte kommt vollständig, mit CRC und den Bytes des RAM | gemessen | `sysex:read_sizes`, beide Builds |
| 48 zufällige Blöcke von 1 bis 32768 Byte (277032 Byte) werden geschrieben, die CRC aus der Antwort ist die gesendete, die Bytes im RAM stimmen, jeder sechste wird noch einmal gelesen | gemessen | `sysex:write_random`, beide Builds |
| Eine falsche CRC beim DATA ergibt Status 1 mit der CRC des Angekommenen, nichts wird geschrieben, der nächste Block geht | gemessen | `sysex:bad_crc`, `sysex:after_bad_crc` |
| Ein DATA ohne BEGIN und ein zweites DATA nach einem BEGIN bleiben ohne Antwort, ein zu kurzes DATA bekommt Korgs eigene Fehlerantwort `0x26` und kein `0x6B`, danach geht alles | gemessen | `sysex:data_without_begin`, `sysex:one_data_per_begin`, `sysex:short_data` |
| Länge 0, ein Byte über dem größten Block, unter, über und über das Fenster hinaus, ein umlaufender Bereich: Status 3 | gemessen | `sysex:ranges` |
| Schreiben in Firmware-Code, den eigenen Code, Puffer und Tabelle, Task-Stacks, Heap, Sample-Cache, Arbeitspuffer, Startstack und in den Spiegel von Abbild und Heap: Status 2 schon bei BEGIN, das RAM bleibt | gemessen | `sysex:refuses_writes` |
| Display, Stub-Puffer, Sample-Name, Sample-Tune, ein Insert- und ein Master-Record gehen durch, ein Schreiben über die Kante zweier Records nicht | gemessen | `sysex:allows_declared`, `sysex:window_edges` |
| Lesen geht überall im Fenster (Firmware, Heap, Stacks, der eigene Code) | gemessen | `sysex:reads_everywhere_in_the_window` |
| Die Firmware sagt zu 209 Bereichen (128 ja, 74 verweigert, 7 außerhalb) dasselbe wie `src/protect.mjs` (Ränder jeder Region, erklärte Fenster, Zufallsstellen), mit einer Ausnahme der Benennung: was außerhalb des Fensters liegt, ist bei der Firmware "außerhalb" (3), auch Lader und DSP-Ports | gemessen | `sysex:same_rule_as_the_editor`, `test/emulator-sysex.test.mjs` |
| Mit EXIT beim Einschalten bleiben INFO, READ, BEGIN, FLASH READ und EXEC ohne Antwort, Korgs Musterabfrage wird beantwortet (18733 Byte), Hacktribes `0x52` antwortet wieder | gemessen | `sysex:kill_switch_silent`, `sysex:kill_switch_korg_still_answers`, `sysex:kill_switch_hacktribe` |
| Die Gerätesuche, Korgs Pattern- und Global-Abfrage gehen wie vorher, MIDI-Noten laufen, kein Assert | gemessen | `sysex:search`, `sysex:pattern_request`, `sysex:global_request`, `sysex:notes` |
| Hacktribes `0x52` bleibt stumm; `0x53` und `0x54` schreiben nichts, auch nicht in den Stub-Puffer, `0x57` führt nichts aus (24.10.) | gemessen | `sysex:hacktribe_read_dropped`, `sysex:hacktribe_write_run_dropped` |
| EXEC führt einen über WRITE geschriebenen Stub mit seinem Argument aus und antwortet mit dem, was er in r0 zurückgibt; an `0xC1000002`, `0xC1000400`, `0xC0FFFFFC`, `0xC3000000`, im Abbild und bei 0 lehnt es ab (Status 2) und führt nichts aus; INFO meldet Bit 6; auf der blauen lehnt es auch im Puffer ab; Hacktribe und Korgs Original (24.10.) | gemessen | `sysex:exec_runs`, `sysex:exec_refused`, `sysex:exec_info_after`, `sysex:synth_exec_refused` |
| Die Firmware stößt in keinem dieser Läufe auf eine Assertion | gemessen | `sysex:no_asserts` |
| Die Signaturen, die die Seite für Korgs Original mit BLECH nimmt (`0xC0000040`, `0xC0026430`, `0xC0170000`), stimmen im laufenden Emulator mit denen der Datei überein | gemessen | Lesen über BLECH, `data/devices.mjs` |

## Durchsatz

Gemessen über die emulierte DIN-Leitung (31250 Baud, 0,32 ms je Byte), Korgs Original mit BLECH, eigenes Flash. Gerätezeit,
von der Anfrage bis zum Ende der Antwort; die Zeit läuft in Schritten von 50 ms, die kleinen Blöcke sind darum nur grob.

| Block | Lesen | Schreiben (BEGIN und DATA) | KiB/s lesen | KiB/s schreiben |
|---:|---:|---:|---:|---:|
| 256 Byte | 150 ms | 200 ms | 1,67 | 1,25 |
| 1024 Byte | 400 ms | 450 ms | 2,50 | 2,22 |
| 4096 Byte | 1550 ms | 1600 ms | 2,58 | 2,50 |
| 16384 Byte | 6050 ms | 6100 ms | 2,64 | 2,62 |
| 32768 Byte | 12050 ms | 12050 ms | 2,66 | 2,66 |

Die Leitung ist die Grenze: 31250 Baud sind 3125 Byte je Sekunde, gepackt 2,67 KiB Nutzdaten je Sekunde, und 32768 Byte
erreichen 2,66. Die Prüfsumme, das Packen und das Kopieren kosten gegen die Leitung nichts, das Rechnen der Firmware
ist in der Gerätezeit nicht zu sehen. Hacktribes Weg mit 256-Byte-Stücken braucht je Stück zwei Nachrichten und eine
Bestätigung und wurde hier nicht gegengemessen. Über USB ist die Leitung nicht die Grenze,
dort gibt der Gerätetest in [BLECH-Datei, Schritt "BLECH SysEx"](../geraetetests/blech-datei.md) die Messung vor. **Offen:** Durchsatz
und größter sicherer Block am Gerät, und ob die Warteschlange des USB-Eingangs einen Block von 32 KiB ohne Verlust nimmt (bleibt
etwas liegen, meldet die CRC es).

## Was die Seite damit tut

- `DeviceSession.connect()` fragt nach der Gerätesuche INFO. Antwortet das Gerät, laufen Lesen und Schreiben über BLECH
  (`ram: "blech"`), sonst über Hacktribe (`ram: "hacktribe"`), sonst bleibt das Gerät lesend. Das Gerät wird an Signaturen seines
  Codes erkannt (`data/devices.mjs`: Hacktribe und Korgs Original mit BLECH), nicht an der Antwort.
- Die Pläne bleiben Hacktribe-förmig (Adresse, dann Daten), der Sender macht daraus einen BLECH-Block, schreibt mit Blöcken
  bis 4096 Byte statt 256 und prüft jeden Block gegen die CRC. Eine falsche CRC wiederholt den Block, dreimal im Ganzen,
  danach bricht der Lauf mit der Meldung ab (ein Schweigen wird nie wiederholt; ein Zurücklesen, das abweicht, auch nicht). Eine
  Aufzeichnung läuft damit auf beiden Wegen gleich ab.
- Das Gerät lehnt von sich aus ab, was die Schutzliste sperrt. Die Erlaubnisliste des Editors (`allowedRegions()`) bleibt
  zusätzlich seine Sache, die Firmware kennt sie nicht.
- Auf Korgs Original mit BLECH gehen Lesen, das Terminal, der Display-Spiegel und das Schreiben des Displays und der
  Sample-Namen. **Nicht** gehen der Effekt-Editor, weil Korgs Build seine Presets anders ablegt als die Karte der Seite
  beschreibt ([Original im Emulator](2026-10-14-stock-emulator.md)), und Code ausführen, das BLECH nicht kann.

## FLASH READ: den Flash lesen (nur lesen)

Gebaut für beide Sampler-Builds (Hacktribe und Korgs Original) und für die blaue Electribe 2. Gemessen im Emulator (`tools/emu/sysex_cases.py`,
Gruppe `case_flash`, mit leerem Flash), Gerätetest in [BLECH-Datei, Schritt 22](../geraetetests/blech-datei.md).

- **Anfrage** `0x64`: Flash-Adresse und Länge, zwei Wörter. **Antwort** `0x6C`: Status, Adresse, Länge, CRC-32 der Bytes, dann die Bytes
  (Aufbau wie bei READ). Der größte Block ist 4096 Byte (`FLASH_MAX`, INFO nennt ihn im letzten Wort): die Sektorgröße, und nach der Schreibseite der
  Firmware (`0xC0029AB8` arbeitet in Stücken zu `0x1000`) die Größe, mit der ihr Flash-Code selbst umgeht. Größere Blöcke sind nicht gemessen.
- **Wie gelesen wird:** über die Lesefunktion der Firmware, dieselbe, mit der der MFX-2-Patch seine Tabelle liest (`0xC0029A74`, ein Wrapper, der
  die Sperre der Firmware nimmt und den Flash-Treiber `0xC001E4AC` ruft). Der Patch spricht den Flash-Chip nie selbst an.
- **Grenze, in der Firmware geprüft:** Länge 1 bis 4096, Adresse plus Länge ohne Überlauf und höchstens `0x1000000` (das Ende des 16-MiB-Flash). Ein Lesen ab
  `0x1000000` hat das Gerät hängen lassen ([Speicherbereiche](../speicherbereiche.md)); die Firmware antwortet dort mit Status 3 und ohne Daten, und das
  Werkzeug fragt es nie an.
- **Es gibt keinen Befehl, der den Flash schreibt oder löscht,** auch keinen versteckten: der Patch hat nur diesen einen Aufruf in den Flash-Code, die Lesefunktion.
- **Bootloader:** `[0, 0x5E74)` ist lesbar, die Entscheidung ist: ja. Lesen verändert nichts, die Regel der Sperrliste sperrt Lesen nur, wo schon der Zugriff
  das Risiko ist (DSP-Ports, Lader im RAM, alles hinter dem Flash), und der Gerätedump vom 9.10. hat diesen Bereich mit Hacktribes Lesebefehl `0x55` schon
  gelesen ([Flash-Dump](2026-10-09-flash-dump.md)). Für ein vollständiges Abbild gehört er dazu. Geschrieben wird er nie (kein Schreibbefehl).
- **EXIT beim Einschalten:** wie bei den anderen Befehlen keine Antwort (gemessen).
- **Werkzeug:** `tools/device/blech_flash_dump.py` liest zweimal und schreibt die Datei nur, wenn beide Läufe gleich sind; jeder Block wird gegen seine
  CRC-32 geprüft (bei einem Fehler dreimal), das erste Schweigen beendet den Lauf, und es lehnt einen Pfad in einem Git-Arbeitsverzeichnis ab (Korg-Daten).
  Im Emulator geprüft: `--emu VSB --start 0x220000 --length 0x8000`.

| Behauptung | Status | Beleg |
|---|---|---|
| FLASH READ von 1 bis 4096 Byte am Anfang, an der Nutzerdaten-Kennung, in der Firmware, in der PCM-Bank und am letzten Byte kommt vollständig, mit CRC und den Bytes des Flash | gemessen | `sysex:flash_read`, Hacktribe und Korg |
| Länge 0, ein Byte über dem größten Block, Start ab `0x1000000`, über das Ende, umlaufend und weit weg: Status 3 ohne Daten | gemessen | `sysex:flash_limits` |
| Währenddessen sieht der Flash-Chip kein Programmieren und kein Löschen, sein Inhalt gilt als unverändert | gemessen | `sysex:flash_untouched` (Zähler der Befehle des emulierten Chips) |
| Mit EXIT beim Einschalten bleibt FLASH READ ohne Antwort | gemessen | `sysex:kill_switch_silent` |
| Der Durchsatz und ob der Treiber am Gerät 4096 Byte am Stück ohne Fehler liefert | offen | Gerätetest |

## Die blaue Electribe 2 (Synth)

Nur dieser Patch ist auf den Synth übertragen, der Rest von BLECH nicht (Plan: [blaue Electribe](2026-10-15-blaue-electribe.md)). Gebaut mit
`tools/patch/fwmap.py`, das die Adressen des Samplers in das Abbild des Synths übersetzt (Datei `data/patches/blech-sysex-synth.json`, Menge
`data/patches/blech-synth.json`).

| Behauptung | Status | Beleg |
|---|---|---|
| Der Code des Patches ist derselbe, die Orte der Firmware (Haken, Parser-Zustand, Sendeweg, Flash-Wrapper, Kanal, Bedienfeld) sind übersetzt: Haken `0xC002240C` und `0xC0021D70`, die Wörter dort sind die des Samplers | gemessen | `fwmap.py` (gleiche 16 Wörter, maskiert), Patch gebaut und angewendet |
| Der Parser-Zustand (`0xC033E6CC`, `0xC033E6C9`) liegt im Synth an denselben Adressen, nur das Bedienfeld ist verschoben (`0xC033E8F8`) | gemessen | die Ladebefehle beider Abbilder gelesen |
| Die Firmware des Synths meldet im Gerätesuchen-Antwort das Modellbyte `0x23`, der Sampler `0x24`; der Rahmen des Patches (Antworten) trägt das Byte des Builds | gemessen | Antwort auf `F0 42 50 00 00 F7` im Emulator |
| Die Schutztabelle ist 20 Byte: ein Bereich, das ganze RAM-Fenster, ohne Ausnahme. Jedes Schreiben wird schon bei BEGIN verweigert, Lesen geht. Grund: die RAM-Karte des Synths (Heap, Stacks, Patternbank) ist nicht vermessen, eine übernommene Tabelle des Samplers würde falsche Grenzen schützen | Entscheidung | `src/sysex-table.mjs` |
| Mit dem Patch bootet die Firmware zum Hauptbild, INFO (Flags 15, Flash-Block 4096), READ, FLASH READ mit allen Grenzen, die Verweigerung von Schreiben, EXIT beim Einschalten, Korgs Gerätesuche, Pattern- und Global-Abfrage, MIDI-Noten und kein Assert | gemessen | `sysex_cases.py synth`, 16 Einträge ok |

Am Gerät ungeprüft. Der Editor erkennt den Synth nicht als BLECH-Gerät (`hasBlechSysex` kennt nur die Stellen des Samplers); gebaut ist die Seite des Geräts, die
Werkzeuge (`blech_flash_dump.py`) sprechen das Protokoll direkt.

## Offen

- Der Gerätetest am echten Gerät (Durchsatz, größter Block über USB, Verhalten des Eingangspuffers).
- Ob die Adressen der Sample-Tabellen und des Displays im Original dieselben sind wie bei Hacktribe: im Emulator gleich
  (derselbe Code), am Gerät ungeprüft.
- Der Effekt-Editor auf Korgs Original: braucht das Format der Presets des Originals.
