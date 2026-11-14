# Emulator

Stand: 15. Oktober 2026. Für Sampler 2.02, mit dem untersuchten
Hacktribe-Build und mit Korgs Original (siehe
[Original-Firmware und Hacktribe](#original-firmware-und-hacktribe)); die
blaue Electribe 2 läuft ebenfalls ([Synth](#die-blaue-electribe-2-synth)). Code und Werkzeuge
liegen in `tools/emu/`, die Seite dazu in `site/app/`.

**Emuliert** heißt Ausführung von ARM-Code. **Modellannahme** heißt: im
Emulator gesetzter Zustand oder ersetztes Verhalten. Das ist kein Nachweis am
Gerät und keine zusätzliche Schreibfreigabe.

## Zweck und Grenzen

Ein ausdrücklich gewählter Blackfin-Prüfprototyp kann zusätzlich echte
DSP-Instruktionen ausführen und deren Speicher über den Host-Port lesen.
Mit ausdrücklich gesetztem SPORT-Prüftakt erreicht die rote Originalfirmware
ihre native Audioverarbeitung. Aufbau und Grenzen:
[Blackfin: SPORT0 und der native Audiotakt](messungen/2026-11-14-blackfin-sport0.md).
Ein eigener [HOSTDP-FIFO-Prüfpfad](messungen/2026-11-14-blackfin-host-fifo.md)
überträgt Daten über DMA1 und die originalen DSP-Interrupt-Handler.
Die ausdrücklich gewählte [gemeinsame Modellzeit mit GPIO-Kopplung](messungen/2026-11-14-blackfin-modellzeit.md)
verbindet diesen Pfad mit dem ARM-Verkehr. Die bisherige Kompatibilitätsauswahl bleibt Vorgabe.

Der Emulator ist ein eigenständiges Python-Programm. Er führt die Firmware der
Electribe, also eine eigene `SYSTEM.VSB`, mit Unicorn aus und bildet dazu
Display, Panel, MIDI, Flash und SD-Karte nach. Damit lässt sich:

- die Firmware in Gerätezeit starten und das Display live in der Seite sehen,
- die Electribe in der Seite bedienen,
- der Editor mit der laufenden Firmware verbinden wie mit einem echten Gerät,
- eine gepatchte VSB vor dem Export auf ihren Startweg prüfen (`check.py`),
- ohne Hardware testen.

Was er nicht ist:

- **Kein Klang.** Die Firmware läuft ohne Audio. Am Audio-Eingang steckt
  nichts, der Emulator meldet dort 0. Der DSP ist nicht nachgebildet: Der
  Host-Port wird als Briefkasten bedient, nicht modellierte DSP-Wörter lesen
  sich als 0, damit die CPU nicht wartet. Wie das im Einzelnen aussieht, steht
  in [Firmware im Emulator booten](messungen/2026-10-08-emulator-boot.md).
- **Keine Garantie für ARM und DSP am Gerät.** Ein sauberer Lauf im Emulator
  sagt nicht, dass sich Gerät und DSP genauso verhalten. Die Gerätezeit ist
  geschätzt (5 ns je Instruktion). Größenprüfung allein identifiziert keine
  Firmwareversion; abweichende Funktionsergebnisse, Speicherfehler und
  ausbleibende Rückkehr führen zum Fehler. Das ist keine Freigabe für
  Gerätezugriffe.
- **Nicht nachgebildet:** an der SD-Karte Karten über 1 GiB und exFAT (CRC,
  Schreibschutz, Fehlerfälle und SDSC siehe Virtuelle SD-Karte); bei USB ein Kabel;
  der Batteriestand (das Symbol zeigt immer das Netzteil). Der Emulator steckt immer
  am Netzteil (Panel-Nachricht 7); nur beim Ausschalten meldet er Batterie, weil die
  Firmware am Netzteil nicht ausgeht.
- Keine eingebauten Firmwaredaten und keine Hardwareverbindung. Der Emulator
  braucht keine Node-Laufzeit, nur Python. Was einige Fälle aus dem
  JavaScript des Repositorys brauchen (übersetzte Plugins, Feldlisten,
  Presets), steht vorberechnet in `data/emu/node-results.json` und geht mit
  in die App. Nach einer Änderung an Compiler, Vertrag, Presets oder Karte
  die Datei neu schreiben: `tools/emu/.venv/bin/python
  tools/emu/node_results.py`. `test/node-results.test.mjs` schlägt fehl,
  solange sie veraltet ist.

Die Messungen tragen die Marker **gemessen** (am Gerät), **hergeleitet**,
**offen**, **offline** (im Emulator am Originalcode beobachtet) und
**Modellannahme**. Die Tabellen der Messung zum Boot sagen je Teil, was davon
nachgebildet und was nur angenommen ist.

## Installation

Benötigt wird Python 3.10 oder neuer und die offizielle Python-Bindung
`unicorn==2.1.4`. Daneben wird nur die Standardbibliothek verwendet. Die
Version steht fest in `tools/emu/requirements.txt` und wird zur Laufzeit
geprüft.

Vom Repository-Verzeichnis aus, einmalig:

```sh
npm run setup:emu   # legt tools/emu/.venv an, mit unicorn==2.1.4
```

Von Hand ist es dasselbe:

```sh
python3 -m venv tools/emu/.venv
tools/emu/.venv/bin/python -m pip install -r tools/emu/requirements.txt
```

Windows: `py -3 -m venv tools/emu/.venv`, anschließend
`tools/emu/.venv/Scripts/python.exe -m pip install -r tools/emu/requirements.txt`.
In PowerShell `$env:E2_VSB = 'C:\pfad\SYSTEM.VSB'` setzen; das bestehende
npm-Skript verwendet POSIX-Umgebungszuweisungen und benötigt dort eine
entsprechende Shell. Alternativ direkt:
`$env:E2_LOCAL_REQUIRED = '1'; node --test 'test/*.test.mjs'`.

Ein vorhandenes Python mit Unicorn lässt sich über `E2_EMU_PYTHON` wählen.
Ohne lokale venv fällt die Testanbindung auf `python3` zurück; eine fehlende
oder falsche Unicorn-Version lässt einen aktivierten Test scheitern. Fehlt
Unicorn, sagt der Dienst das beim Start und die Seite beim Starten der
Firmware.

## Start

```sh
npm start           # Seite und Emulator zusammen; Strg+C beendet beides
```

Mit `npm start` findet die Seite den Emulator von selbst: einfach
`http://127.0.0.1:8737/` öffnen, der Bereich "Emulator" ist dann verbunden
und vorne. Der Seitenserver gibt Port und Schlüssel dafür unter `/emu.json`
aus, nur an Anfragen für seinen eigenen Host. Andere Ports:
`PORT=9000 EMU_PORT=9001 npm start`.

Einzeln geht es mit `npm run serve` (Seite unter `http://127.0.0.1:8737/`)
und `npm run emu` (Emulator-Dienst).

### Der Dienst

`npm run emu` startet `tools/emu/server.py` mit `E2_EMU_PYTHON`, sonst der
venv in `tools/emu/.venv`, sonst `python3`. Der Dienst hört nur auf
`127.0.0.1:8740` und gibt einen Link wie
`http://127.0.0.1:8737/#emu=8740:<Schlüssel>` aus. Der Link öffnet den
Bereich "Emulator" verbunden; der Schlüssel bleibt nur in diesem Tab. Dort die
VSB wählen und die Electribe einschalten: Die Firmware läuft in Gerätezeit,
nie schneller als das Gerät, und das Display erscheint live. Andere Seite oder
anderer Port: `npm run emu -- --page http://127.0.0.1:9000 --port 8741`.

Der Dienst nimmt nur Anfragen mit dem Schlüssel und von der Editor-Seite an,
denn jede Webseite im Browser kann `127.0.0.1` erreichen. Seine Tests laufen
ohne Firmware und ohne Unicorn (`test_server.py`, auch in `npm test`).

Der Dienst endet mit dem Prozess, der ihn gestartet hat, auch wenn der hart beendet
wird: `--parent-pid <pid>` (mehrfach möglich) wird einmal pro Sekunde geprüft, danach
läuft der normale Weg über SIGTERM, der Karte und Flash speichert. `npm run emu`,
`npm start`, die App und die Tests geben ihre eigene pid mit. Hängt der Weg nach
draußen länger als 10 Sekunden, beendet sich der Dienst hart. `--ephemeral` (nur für
Tests) löscht am Ende Karten- und Flash-Ordner, verlangt `--sd-dir` unterhalb des
temporären Ordners und legt den Flash dann nach `<sd-dir>/flash`.

### Dateien des Dienstes

| Pfad | Inhalt | Anderer Ort |
|---|---|---|
| `~/.gelumpe/flash/flash.bin` | Flash der emulierten Electribe, 16 MiB | `GELUMPE_FLASH_DIR` oder `--flash-dir` |
| `~/.gelumpe/sd/card/` | Ordner der virtuellen SD-Karte | `GELUMPE_SD_DIR` oder `--sd-dir /pfad` (die Karte ist dann `<pfad>/card/`) |
| `~/.cache/gelumpe` | Snapshots und gemerkte Prüfergebnisse | `GELUMPE_CACHE_DIR` |

Alle drei enthalten Nutzerdaten oder Firmware-RAM und gehören nie ins
Repository.

### Bedienung

Unter dem Display liegt die Electribe zum Bedienen: Tasten, Pads und
Ein/Aus mit Maus oder Enter/Leertaste halten, Regler und Drehgeber mit
Mausrad, Ziehen oder Pfeiltasten, das Touchpad mit Ziehen oder Leertaste
plus Pfeiltasten. Jede Eingabe geht als Panel-Nachricht an `POST /input`,
die LEDs kommen über den Ereignisstrom zurück. Welche Nummer zu welchem
Bedienelement gehört, steht in `data/panel.mjs`, gemessen in
[Bedienfeld](messungen/2026-10-08-panel-bedienung.md). Ein/Aus schaltet die
Electribe aus wie am Gerät; ein weiterer Druck startet sie neu.

### Editor und MIDI

Läuft die Firmware, verbindet "Mit Emulator verbinden" im Bereich "Gerät"
den Editor mit ihr wie mit einer echten Electribe: Gerätesuche, RAM lesen
und schreiben, Türsteher und Rücklesen laufen über die emulierte DIN-MIDI
(`POST /midi`, Antworten als Ereignis `midi`). Das braucht kein Web MIDI.
Gemessen in [DIN-MIDI und SysEx](messungen/2026-10-09-din-sysex.md).

MIDI, das ankommt, bevor die Firmware den Hauptbildschirm gezeigt hat, wird
verworfen, nicht aufgehoben: am Gerät kann vor dem Start niemand etwas senden,
und die Firmware bricht darauf mit der Assertion in `MidiHandler.cpp` Zeile 85
ab (gemessen: SysEx bei 40 ms Gerätezeit; der Hauptbildschirm kommt bei rund
0,35 s). "Gestartet" ist `Machine.booted`: Bildschirmnummer 1, alle 100 ms
Gerätezeit und am Ende jedes `run_until` gelesen. Der Dienst meldet es im
Status als `booted`; `POST /midi` antwortet davor mit 200 und dem Status
(`booted: false`), und die Seite sendet erst bei `booted`. Der Bericht von
`machine.py` nennt `booted_ms` und `midi_dropped`.

Ist der Editor so verbunden, zeigt die Leiste "Am Gerät" links im Bereich
"Emulator", welcher Bildschirm, welche Menüseite und welcher Part gerade
offen sind. Steht das Menü Pattern auf MFX TYPE oder ist das Fenster
IFX TYPE offen, öffnet sie diesen Effekt im Effekt-Editor, mit Türsteher,
"Live ins RAM" und Zurücknehmen wie im Bereich "Effekte". Woher sie das
weiß: [Menüzustand](messungen/2026-10-09-menuezustand.md).

Für Tests ohne Seite nimmt `machine.py` Panel-Nachrichten und SysEx mit
Gerätezeit: `--send 0009010000@3 --send 0009000000@3.15` drückt MENU nach
3 s, `--midi f042500000f7@3` schickt die Gerätesuche; die Antworten stehen
im Bericht unter `midi_out`.

## Virtuelle SD-Karte

Der Kartenschacht der Electribe ist nachgebildet: ein SD-Controller (MMC0,
`sdcard.py`) und eine SDHC-Karte, deren Medium eine Abbilddatei ist. Die
Firmware erkennt sie (Kartensymbol), mountet sie, liest und schreibt Dateien.
DATA UTILITY funktioniert damit: IMPORT SAMPLE liest eine WAV von der Karte,
EXPORT SAMPLE schreibt `KORG/hacktribe/Sample/<Slot>_<Name>.wav`, EXPORT ALL
SAMPLE die `e2sSample.all` in denselben Ordner, EXPORT ALL PATTERN die Datei
`KORG/hacktribe/electribe_sampler_allpattern.e2sallpat`. Beim Start lädt die
Firmware nur die `e2sSample.all`, keine einzelnen WAVs. Gemessen in
[virtuelle SD-Karte](hintergrund/virtuelle-sd.md).

**Die Karte ist ein Ordner.** `~/.gelumpe/sd/card/`, nie im Repository, denn
die Karte kann Korg-Samples enthalten. Anderer Ort: `GELUMPE_SD_DIR` oder
`npm run emu -- --sd-dir /pfad` (die Karte ist dann `<pfad>/card/`). Der Ordner
ist frisch leer, aber im Aufbau, den die Firmware erwartet: `KORG/<Ordner>/Sample`
und `KORG/<Ordner>/System`. Den Ordnernamen bestimmt die geladene Firmware: es
ist das Pfadliteral `KORG/.../`, das direkt vor `e2sSample.all` in der VSB steht
(`hacktribe`, nach dem Umbenennen `blechtribe`; `card_folder()` in
`cardstore.py`). Ein leeres Gerüst für eine andere Firmware wird wieder
entfernt, ein Ordner mit Dateien bleibt. `GET /sd` nennt ihn als `korg`. Die
Samples, die beim Start geladen werden, liegen in
`KORG/<Ordner>/Sample/e2sSample.all`.

**Einlegen.** `POST /sd/insert` kopiert den Ordner in ein FAT32-Abbild im
Speicher (1 GiB, so groß, dass CARD FORMAT der Firmware die Karte annimmt) und
schützt den Ordner vor Schreiben (Dateien 0444, Ordner 0555), solange die Karte
drin ist. Das Abbild ist das Medium der Firmware. Was sie darauf ändert, wird
eine Sekunde nach dem letzten Schreiben (spätestens nach einer Minute
Dauerschreiben), beim Anhalten und beim Ziehen in den Ordner übernommen: neue
und geänderte Dateien werden geschrieben, Dateien, die die Firmware gelöscht hat,
verschwinden. Gelöscht wird nur, was beim Einlegen auf der Karte war; versteckte
Dateien, Verknüpfungen und Dateien über 4 GiB werden nicht kopiert und bleiben
unberührt. Unzulässige Zeichen im Namen werden auf der Karte zu `_`, der Ordner
behält den Namen. Passt der Ordner nicht in 1 GiB, wird das Einlegen abgelehnt.
`POST /sd/eject` übernimmt den letzten Stand und gibt den Ordner wieder frei.

**Formatieren** geschieht an der Firmware (DATA UTILITY, CARD FORMAT), nicht in
der Seite. Sie legt FAT16 an; der Dienst liest das (`Fat16Volume` in `fat32.py`,
nur lesen) und leert den Ordner entsprechend. Meldet er, dass er das Abbild
nicht lesen kann, steht der Grund in `GET /sd` unter `error`, und der Ordner
bleibt, wie er war.

**Beim Dienststart ist keine Karte eingelegt.** Ein Dienst, der mit
eingelegter Karte gestorben ist, hinterlässt den Ordner schreibgeschützt; der
nächste Start gibt ihn wieder frei. Was zwischen dem letzten Übernehmen und dem
Absturz geschrieben wurde, ist verloren. Ein zweiter Dienst auf demselben
Ordner wird abgelehnt.

**Einlegen und Ziehen im Betrieb** geht wie am Gerät. Die Firmware liest den
Karten-Eingang (GPIO 4.1, aktiv low) im Polling und bemerkt den Wechsel selbst:
das Kartensymbol links vom Batteriesymbol erscheint und verschwindet, DATA UTILITY
listet die Karte (gemessen, `test/emulator-card.test.mjs`). Der Dienst schaltet den
Eingang und den Controller zwischen zwei Schritten der Maschine um. Beim Ziehen
wird übernommen, was die Firmware bis dahin geschrieben hat; ein halb
geschriebener Stand bleibt so halb, wie er war, wie bei einer gezogenen Karte.

**Öffnen.** `POST /sd/open` zeigt den Ordner im Dateimanager des Rechners
(`open`, `xdg-open`, `explorer`). Das geht nur im Dienst, den die Seite im
Browser nicht ersetzen kann. Dort sieht, ändert und löscht man Dateien; bei
eingelegter Karte geht das nicht, weil der Ordner schreibgeschützt ist (das
hält ein Dateimanager ein, ein Root-Zugriff nicht).

Routen, alle mit Schlüssel und Herkunft wie die übrigen:

| Route | Wirkung |
|---|---|
| `GET /sd` | Ordner, `korg`, eingelegt, läuft sie, schreibt die Firmware gerade, letzter Übernahmefehler |
| `POST /sd/insert`, `POST /sd/eject` | Karte einlegen, ziehen |
| `POST /sd/open` | Ordner im Dateimanager zeigen |
| `POST /sd/system` | Körper: eine VSB. Legt sie als `KORG/<korg>/System/SYSTEM.VSB` in den Ordner und die Karte ein (eine eingelegte wird dafür kurz gezogen); so testet die Seite ein Update |

Der Ereignisstrom meldet `sd` (gelesene und geschriebene Sektoren, schreibt die
Firmware gerade) und in `status` die eingelegte Karte. Die Seite dazu ist
`site/app/sdcard.mjs`: `sdcardPanel(root, emulator)`, ein Schalter "Karte
einlegen", der Knopf "Öffnen" und eine kurze Statuszeile.

Tempo: 64 Byte je Interrupt, rund 0,8 ms Gerätezeit je Sektor (etwa 640 KB/s,
**geschätzt**); eine große `e2sSample.all` verlängert den Start entsprechend.
Karten über 1 GiB und exFAT sind nicht nachgebildet. Was an Fehlerfällen
nachgebildet ist, steht im nächsten Abschnitt.

### Fehlerfälle der Karte

Die Karte verhält sich wie eine echte, auch im Fehlerfall, damit sich das ohne
Gerät testen lässt. Gewählt wird es beim Einlegen (`POST /sd/insert`, Körper
JSON) oder an der eingelegten Karte (`POST /sd/card`, ersetzt `faults` und
schaltet `writeProtect`, die Art bleibt); `GET /sd` nennt unter `card`, was
gilt und wie oft ein Fehler getroffen hat. In Python: `SDCard(medium, kind=...,
write_protect=..., never_ready=...)` und `card.fail(art, cmds=, lbas=, skip=,
count=)`, `card.heal()`.

| Option | Wirkung |
|---|---|
| `kind: "sdsc"` | alte Karte: keine Antwort auf CMD8, kein High-Capacity-Bit, CSD 1.0, Byteadressen |
| `writeProtect` | Schreibschutzschalter, die Firmware liest ihn an GPIO 4.0 (hoch = geschützt) |
| `neverReady` | das Hochfahren der Karte endet nie (ACMD41 bleibt busy) |
| Fehler `no_response` | der Befehl bekommt keine Antwort |
| `response_crc` | die Antwort kommt mit falscher CRC7 |
| `read_timeout`, `read_error` | Antwort ja, Daten kommen nie (`read_error` meldet im nächsten R1 ECC_FAILED) |
| `read_crc` | der Block kommt beschädigt, mit nicht passender CRC16 |
| `write_crc`, `write_error` | die Karte lehnt den Block ab und speichert ihn nicht |

`cmds` (Befehlsnummern) und `lbas` (Blöcke, als Liste oder `{"from","to"}`)
grenzen einen Fehler ein, `skip` lässt die ersten Treffer durch, `count` begrenzt
die Zahl der Treffer. CRC7 für Antworten und CRC16 für jeden Datenblock werden
von der Karte gebildet und vom Controller geprüft; ein Fehler dreht ein Bit auf
dem Weg.

**Was die Firmware tut** (Emulator, Hacktribe, Korgs rot und BLECH darauf;
`tools/emu/card_error_cases.py`, `test/emulator-card-errors.test.mjs`):

| Fall | Firmware | Status |
|---|---|---|
| Lesen der Sampledatei bleibt ohne Antwort oder die Daten kommen nie, nach dem Einhängen | Kasten "Card Error" (Code 4), nach 8 bis 17 s; BLECH macht keine Ordner, schreibt nichts | gemessen |
| Karte gesperrt, Start | kein Schreibbefehl, keine Ordner, das Gerät läuft normal | gemessen |
| Karte gesperrt, EXPORT ALL PATTERN | Kasten "Card Write Protected" (Code 3) sofort, nichts geschrieben; mit Schalter aus schreibt derselbe Export | gemessen |
| SDSC-Karte | hängt ein, liest und schreibt wie die SDHC (Byteadressen aus dem OCR abgeleitet), BLECH macht seine Ordner | gemessen |
| Lesen mit falscher CRC | kein Kartenfehler: die Treiberfunktionen werten die CRC-Bits nie aus (`CRCRD`, `CRCWR`, `TOUTRD`), die Firmware arbeitet mit den beschädigten Bytes; bei der Sampledatei kommt später ihr eigener Fehler (Stock "Format Error", BLECH "bad WAV file") | gemessen, Treiber offline gelesen |
| Schreiben mit falscher CRC oder abgelehnt | nichts im Treiber merkt es, FatFs findet die fehlenden Daten später: "Card Error" | gemessen |
| Schreiben ohne Antwort | "Card Error" nach etwa 15 s | gemessen |

Nur die Laufwerksfunktion der Firmware wertet das Schreibschutz-Pin aus
(`disk_status` `0xC003FEB8` setzt STA_PROTECT, `chk_mounted` macht daraus
FR_WRITE_PROTECTED; **offline gelesen**).

**Modellannahmen** (nicht am Gerät gemessen):

- Die Fehler-Bits stehen so im Controller: `TOUTRD`, `CRCRD` (am Ende des
  Blocks, die Daten kommen trotzdem an), `CRCWR` (bei jedem Status-Token außer
  "ok") und `CRCRS` (statt `RSPDNE`). Ob die echte Karte oder der AM1808 das so
  meldet, ist offen. Die Firmware wertet `CRCRD` und `CRCWR` ohnehin nicht aus.
- Zeitüberschreitungen melden sich sofort, nicht erst nach `MMCTOD`.
- Die CRC16 ist eine über die 512 Byte; ein 4-Bit-Bus hat eine je Datenleitung.
- Eine SDSC-Adresse, die kein ganzer Block ist, gibt ADDRESS_ERROR und keine Daten.
- Ohne Antwort auf einen Lesebefehl **beim Einhängen** bleibt die Firmware im
  Treiber stehen (Startbild). Das deckt sich mit der Rückmeldung vom 18.10.,
  ist aber am Gerät nicht gemessen.

**Offen:** Mit BLECH hängt der Start im Emulator bei einer Karte ohne
Dateisystem (leere Karte ohne FAT) und bei einer Karte, die auf nichts
antwortet; ohne BLECH (Hacktribe, Original) läuft das Gerät mit beiden weiter.
Der erste Lesebefehl kommt, dann steht der Start. Nicht behoben, ein Fall im
Ladebalken-Patch (Mounten wiederholen, `load_bar.py`) ist der erste Verdacht.

Tests: `test_fat32.py` (FAT32-Schreiber und -Leser, mit `fsck_msdos` auf macOS),
`test_sdcard.py` (Controller über die Register, die Fehlerfälle), `test_cardstore.py`
(Einlegen, Schutz, Übernahme in den Ordner, FAT16, Ordnername) und der Teil
`CardServiceTest` in `test_server.py` laufen ohne Firmware in `npm test`.
`test/emulator-card.test.mjs` fährt die ganze Strecke mit der Firmware
(`npm run test:emu`): WAV in den Kartenordner, IMPORT SAMPLE, die Exporte im
Ordner, Ziehen, Neustart des Dienstes.
`test/emulator-sample-full.test.mjs` füllt die Nutzerplätze 501 bis 999 bis an die Grenze des
Samplespeichers (`tools/emu/sampleset.py` baut die `e2sSample.all` aus einer Formel) und prüft, dass die
Firmware nichts in das RAM von BLECHTRIBE schreibt ([Messung](messungen/2026-10-14-sample-speicher-voll.md)).
`test/emulator-sample-meta.test.mjs` liest die drei Sample-Tabellen der Firmware an den Adressen der
Gerätekarte und schreibt an einem unbenutzten Platz Name und Tune über Plan und Türsteher: gelesen,
zurückgelesen, zurückgenommen, kein anderes Byte der Einträge verändert
([Messung](messungen/2026-10-07-sample-metadaten-ram.md)). Ohne Karte trägt ein unbenutzter Platz den Namen
`SampleNNN` und 48000 Hz.

## Flash als Datei

Der Flash der emulierten Electribe ist eine Datei, die den Dienst überlebt, wie der
Chip im Gerät: `~/.gelumpe/flash/flash.bin` (16 MiB, neben dem Kartenordner; anderer
Ort: `GELUMPE_FLASH_DIR` oder `--flash-dir`). Sie enthält Nutzerdaten und gehört nie ins
Repository. Der Emulator bootet immer aus ihr, und jede Änderung der Firmware am Flash
(IMPORT ALL PATTERN, Pattern-WRITE, Globals) wird eine Sekunde später und beim Ausschalten
zurückgeschrieben (temporäre Datei, `fsync`, umbenannt). Ohne Datei startet ein gelöschter
Flash mit der Nutzerdaten-Kennung (`machine.blank_flash`), den die Firmware selbst
einrichtet: leere Patterns, Globals aus ihrer Vorgabe. Samples stehen nicht darin, sie
kommen aus der `e2sSample.all` der Karte. Bei `0x800000` trägt er eine kleine Werksbank
von uns (`tools/emu/factorybank.py`: der Aufbau der echten mit 411 Einträgen, Namen und
Zahlen aus Formeln, kein Audio, keine Korg-Daten), ohne die alle Werksplätze auf denselben
Eintrag zeigten und ein zweites Sample für einen Werksplatz als "Unknown Error." abgelehnt
wurde ([Messung](messungen/2026-10-15-sample-fehler.md)). Die Seite bietet keinen Flash-Import;
`POST /flash` ersetzt den Inhalt der Datei (Tests, Werkzeuge). Eine Datei falscher Größe
wird nicht angefasst, der Start meldet das. Test: `test/emulator-flash.test.mjs`
(`npm run test:emu`) importiert eine selbstgebaute Sicherung, startet den Dienst neu und
findet das Pattern im neuen Export.

## Display

Die Firmware schaltet jeden Bildpunkt nur an oder aus; es gibt keinen Grau-Befehl
und kein Wechseln zwischen zwei Bildern. Was am Gerät gedimmt aussieht (etwa der
Name des wartenden Patterns, den die Firmware alle 280 ms ein- und ausblendet),
ist die Trägheit der Flüssigkristalle. `lcd.py` bildet sie nach, ein Verzögerungsglied
je Bildpunkt, getrennt für das Dunkelwerden (`TAU_ON`, 0,040 s, aus einem Zeitlupenvideo)
und das Hellwerden (`TAU_OFF`, 0,17 s, **geschätzt**: mit bloßem Auge am Gerät am 27.10.,
am 29.10. von 0,30 auf 0,20 s und am 10.11. auf 0,17 s gesenkt, weil es im Emulator zu träge wirkte; keine Messung; die 0,028 s aus dem Video waren zu niedrig, siehe
[LCD-Helligkeit](messungen/2026-10-12-lcd-helligkeit.md)). Die Werte stehen nur in
`lcd.py`.

Überschreiben: `--lcd-tau-on SEKUNDEN` und `--lcd-tau-off SEKUNDEN` am Dienst
(`npm run emu -- --lcd-tau-on 0.12 --lcd-tau-off 0.30`), sonst die Umgebungsvariablen
`E2_LCD_TAU_ON` und `E2_LCD_TAU_OFF` (`E2_LCD_TAU_ON=0.12 E2_LCD_TAU_OFF=0.30 npm start`),
gültig 0 bis 10 s; der Dienst nennt die benutzten Werte beim Start. Wie sich die
Werte aus einem Video des Geräts bestimmen lassen, steht in der Messung.

Der Dienst schickt die 16 Stufen als Ereignis `shade` (ein Byte je Bildpunkt,
Zeile für Zeile, 0 hell bis 15 dunkel). Das Ereignis `display` (1 Bit, `m.fb`)
bleibt unverändert; die Seite zeichnet die Stufen zwischen den Farben
`--cee-lcd-off` und `--cee-lcd-on`. Test: `test_lcd.py`.

### Displaylicht

Die Firmware treibt das Licht über drei GPIO-Pins, GPIO 6.3, 6.4 und 6.5 für
Rot, Grün und Blau (BLECH-Menü BACKLIGHT, Plugins mit `korg.backlight` und
`display.red/green/blue`; alles endet an diesen Pins). Stufe 0 oder 15
ist ein fester Pin, eine Stufe dazwischen eine Software-PWM aus 16 Takten zu
0,5 ms, also 8 ms je Periode (**offline**, 10.11.: Rot auf 5 steigt alle 8000 µs
und bleibt 2500 µs an). Energiesparen lässt Rot und Grün abwechselnd je einmal
in 27 ms aufleuchten. `backlight.py` rechnet je Pin den Anteil der Zeit, die er in
seiner letzten vollen Periode an war (von steigender Flanke zu steigender Flanke),
so wie das Auge den Mittelwert sieht; ein Pin, der sich 100 ms nicht ändert, ist
fest an oder aus. Ausschalten macht das Licht dunkel.

Der Dienst schickt das als Ereignis `backlight`, `[rot, grün, blau]` je 0 bis 255
(Rot auf 5 von 16 ist `[80, 0, 0]`), bei jeder Änderung und beim Verbinden. Bevor
die Firmware einen der Pins zum ersten Mal schreibt, und bei einer Maschine ohne
Licht-Modell, ist es `null`. Die Seite multipliziert beide LCD-Farben je Kanal
mit dem Licht: Weiß (Werkszustand) lässt die Theme-Farben, wie sie sind, ein
gedimmtes Rot färbt die hellen Bildpunkte dunkelrot, Licht aus macht das ganze
Display schwarz. Bei `null`, im Fake-Start ohne Firmware und beim Spiegeln eines
echten Geräts bleiben die Theme-Farben. Ausgeschaltet blendet die Seite das
Display ganz aus, dahinter liegt der dunkle Rahmen. Ob die Farben am Gerät genauso
aussehen (LED-Farbort, Helligkeitskurve), ist **offen**: die Seite nimmt das
Tastverhältnis linear. Tests: `test_backlight.py`, `test_server.py`
(`test_streams_the_display_light_colour`), `test/lcd-shade.test.mjs`, die
Emulator-Seite in `test/e2e/support/emulator-suite.mjs` und der Fall
`look_backlight_colour_reaches_the_page` in `menu_cases.py` an der Firmware.

## LEDs

Die Firmware schickt jede LED als Nachricht `00 LED Wert` über UART0 ans Bedienfeld. Der Emulator schreibt jede Änderung mit ihrer
Gerätezeit mit (`tools/emu/panel_leds.py`, `Machine.panel_leds`): wann das Panel das letzte Byte hatte und wann die LED danach
leuchtet. Eine Nachricht, die nur den alten Wert wiederholt, zählt dort mit, ist aber keine Änderung.

Bis 1.4.5 gingen kurze Wechsel unterwegs verloren (hergeleitet aus dem Code):

- `Machine.leds` hält nur den letzten Wert je LED, `panel_log` die Nachrichten ohne Zeit.
- Der Dienst sah nach jedem Schritt von 20 ms Gerätezeit auf diese Tabelle. Ein Pad, das 14 ms dunkel war, kam nie an.
- Die Seite setzte jede Tabelle sofort, ohne Zeit, und zeigte Pads nur an oder aus.

Jetzt schickt der Dienst nach jedem Schritt das Ereignis `ledtrace` mit allen Änderungen des Schritts, je
`[Gerätezeit µs, leuchtet ab µs, LED, Wert]`. Kommt eine Seite nicht hinterher und verliert ein Ereignis, bekommt sie vor dem
nächsten die ganze Tabelle (`leds`). Die Seite (`site/app/led-trace.mjs`) spielt die Änderungen 60 ms nach ihrer Gerätezeit in
den Abständen des Geräts ab. Jedes gezeichnete Bild zeigt eine LED als Mittel ihrer Werte über das Bild, so wie das Auge eine
PWM-LED sieht: 5 ms dunkel in einem Bild von 17 ms ist ein sichtbar dunkleres Bild.

Das Bedienfeld selbst, nach [Panel-Controller](hintergrund/panel-controller.md):

| Was | Wert | Marker |
|---|---|---|
| 88 LEDs in 11 Zeilen mal 8 PWM-Kanälen | Tabelle `0x8460` im Panel-Code | hergeleitet |
| PWM rund 2 kHz (5000 Schritte bei 10 MHz), Takt des Panels 100 µs | Panel-Code | hergeleitet |
| Helligkeit linear: Wert mal Periode durch 255, auch die Pads | Panel-Code `0x4EBC`; Pulsieren am 18.10. am Gerät flüssig | hergeleitet |
| Eine Nachricht wirkt einen Takt nach ihrem letzten Byte, die Zeilen leuchten reihum je eine PWM-Periode, ein neuer Wert ab der nächsten Runde (5,5 ms) | | Modellannahme |
| Ein Wert, der vor seiner Runde schon ersetzt ist, leuchtet nie | folgt aus der Annahme darüber | Modellannahme |
| Die Seite zeigt den Tastgrad linear als Deckkraft; wie hell das Auge eine Stufe am Gerät sieht | nicht gemessen | Modellannahme |
| `02 b` von der Firmware wirkt auf die LEDs | offen, das Modell übergeht es | offen |

Pads zeigt die Seite jetzt gestuft wie die anderen LEDs; die Messung vom 16.10. (nur an oder aus) ist am 18.10. teils widerlegt
([Pad-LED-Stufen](messungen/2026-10-16-pad-led-stufen.md)). Power Save dimmt in der Firmware, nicht im Panel: BLECH schickt auf
Batterie ein Viertel ([Energiesparen](messungen/2026-10-18-energiesparen-leds.md)), das Modell bekommt also schon die gedimmten Werte.

### Pad-Flackern beim schnellen Drehen

`pswitch:pad_flicker_playing` und `pswitch:pad_flicker_stopped_unsaved` (`tools/emu/pswitch_cases.py`, `case_pad_flicker`): 20
Klicks am Rad im Abstand von 30 ms, abspielend und gestoppt mit ungespeicherter Änderung. Gezählt werden dunkle Lücken eines Pads bis
50 ms, so wie das Bedienfeld sie zeigt. Erlaubt sind die der Firmware (EXIT beim Einschalten) plus die zwei Neuzeichnungen, die
der Fix lässt: die erste sofort und die nach dem Stillstand.

Gemessen im Emulator (Hacktribe 2.02 mit dem BLECH-Satz, 10.11.):

| Stand | abspielend | gestoppt, ungespeichert | Ergebnis |
|---|---|---|---|
| Firmware (EXIT gehalten) | 0 | 1 | |
| vor dem Fix (`c2ba48fd^`) | 20, je Klick einmal | 18 | rot |
| mit dem Fix (`c2ba48fd`) | 2 | 2 | grün |

Jede Neuzeichnung der Vorschau schickt die blaue LED von Pad 1 (`0x2d`) erst 0 und rund 14 ms später wieder 255; am Bedienfeld
sind das 11 bis 16,5 ms dunkel. Die zwei Neuzeichnungen, die der Fix lässt, flackern so noch je einmal (gemessen). Am Gerät nicht
geprüft.

## Zeit und Takt

Der Grundtakt ist 5 ns je Befehl. Eine Scheibe endet vor dem nächsten
Timer-Takt oder UART-Byte (`slice_length`), ein wartender Prozessor springt bis
dorthin (`run_slice`); die Firmware bekommt so 1000 Timer-Interrupts und
25 Bildschirm-Takte je Sekunde Gerätezeit, egal wie lang `SLICE` ist.
`test_timer.py` prüft das (`E2_VSB`, ohne sie übersprungen, mit
`E2_EMU_REQUIRED=1` ein Fehler). Der Karten-Interrupt wird nur einmal je 100 µs
Gerätezeit angesehen (`MMC_IRQ_NS`), und er kommt einmal je 64-Byte-Stück, wie der
FIFO ihn auslöst: kam er für ein Stück, das die Firmware gerade noch abholt, ein
zweites Mal, dann landete er hinter dem nächsten Befehl, und der Handler nahm der
Abfrageschleife die Antwort weg (ST0 löscht beim Lesen, Assertion Zeile 228).
`migrate_cases.py` prüft das mit einem Blick alle 2 µs. Messung:
[Emulator-Takt](messungen/2026-10-12-emulator-takt.md).

### Gerätetakt

Gegen das Gerät verglichen ([Emulator-Zeit gegen Gerätezeit](messungen/2026-10-16-emulator-timing.md),
`tools/device/timing_probe.py`): reine Rechenschleifen laufen am Gerät in 5 ns je Befehl, ein abhängiges
Multiply kostet 6,7 ns mehr, Lesen 0,5 ns je Byte mehr, wenn der Daten-Cache trifft, 6,8 ns je Byte bei
einem Durchlauf über mehr Speicher, als der Cache fasst, und 12,4 ns je Byte über den ungecachten Alias
`0xC4000000`.

Mit diesen Zuschlägen rechnet der Emulator die Zeit jeder Scheibe (`devicetime.Pace`, `Machine.device_rate`).
Er sieht nicht jeden Speicherzugriff an, das wäre zu teuer, sondern nimmt eine Stichprobe: wo eine Scheibe
aufhört, liegt der Code, der gerade läuft. Diese Stelle wird einmal dekodiert, als ganze Schleife, wenn ein
Rücksprung sie umschließt, sonst bis zum Ende des Blocks, und ihr Preis je Befehl gilt für die nächste Scheibe.
So sehen Timer-Interrupts, Bildschirm-Takte, die Echtzeit-Bremse und alle Fälle die Gerätezeit. Ein Ladezugriff,
dessen Basisregister in einer Schleife durch den Speicher läuft, zählt als Cache-Fehlgriff, sobald zwei
Stichproben derselben Schleife kurz nacheinander mehr als 16 KiB auseinander liegen. Die vier Schleifen der
Messung kommen damit auf die Gerätewerte (`test_devicetime.py`). `GELUMPE_PACE=flat` schaltet zurück auf
5 ns für jeden Befehl.

**Modellannahmen**, nicht gemessen:

- Der Daten-Cache fasst 16 KiB (Datenblatt des AM1808). Gemessen ist nur: 4 KiB treffen, 256 KiB nicht.
- Der Zuschlag ist linear in den gelesenen Bytes, auch für einzelne Bytes und Halbwörter.
- Jedes Multiply kostet den Zuschlag, auch eins, dessen Ergebnis nicht gleich gebraucht wird.
- Schreiben, der Befehls-Cache, falsch vorhergesagte und indirekte Sprünge, Lesen von Peripherie und
  Thumb-Code kosten nichts extra.
- Der erste Blick auf einen Durchlauf zählt als Treffer. Eine Kopie, die kürzer als eine Scheibe läuft, rechnet
  der Emulator deshalb zu schnell. Ein Lauf über 256 KiB kommt auf 126 statt 143 ns je Runde.
- Ein Interrupt-Handler läuft im Preis des Codes, den er unterbricht. Seine Scheiben (`ISR_STEP`) enden jedes
  Mal an denselben Stellen und wären keine Stichprobe.

Gegen die Plugin-VM geprüft ([Gerätetakt im Emulator](messungen/2026-11-10-emulator-geraetetakt.md)): am
Gerät 7 bis 8 ns je Emulator-Befehl, mit dem Modell 5,7 bis 6,1, flach 5. Das Modell rechnet also näher am
Gerät, aber noch zu schnell für einen Interpreter.

### Tempo der Prüfungen

Ein Boot bis zum Hauptbild kostet rund zwei CPU-Sekunden; `bootcache.py` bootet je
Firmware, Flash, gehaltene Tasten und Gerätezeit einmal und startet danach aus einem
Snapshot (`Machine.snapshot`, bit-identisch zum durchgelaufenen Gerät, `test_snapshot.py`).
Das gilt auch mit Karte im Schlitz, wenn sie ein Abbild im Speicher ist: der erste Lauf eines
Falls ab dem Einschalten wird samt Karte gemerkt (`bootcache.power_on`, `Dev.run`).
Die Dateien liegen in `~/.cache/gelumpe` (`GELUMPE_CACHE_DIR`), enthalten Firmware-RAM und
gehören nicht ins Repository. `check.py`, `mfx_cases.py` und `splash_cases.py` verteilen
unabhängige Boots auf Prozesse (`GELUMPE_JOBS`, Standard: Kerne minus einer, 2 bei
1-Minuten-Load über der Kernzahl, 1 bei Load über der doppelten Kernzahl). `check.py` merkt
sich das Ergebnis jedes Tasks mit den Dateien, die er benutzt hat (`taskcache.py`), so läuft
nach einer Änderung nur neu, was sie berührt; `mfx_cases.py` und `splash_cases.py` merken sich
ein beendetes Ergebnis je Eingabedateien und Emulator-Quelltext. `GELUMPE_CACHE=off` schaltet
Snapshots und gemerkte Ergebnisse ab, wenn alles frisch laufen soll. `server.py --unthrottled`
(nur für Tests) läuft ohne Echtzeit-Bremse und meldet die Gerätezeit alle 20 ms.
Die Testlaufzeit steht in [development.md](development.md#tests).

## Boot

### Die ganze Firmware starten

`machine.py` startet die ganze Firmware ab dem Reset-Vektor, ohne Klang,
und gibt das Display als Bild aus:

```sh
tools/emu/.venv/bin/python tools/emu/machine.py --vsb /pfad/SYSTEM.VSB \
  --flash /pfad/flash_0M_4M.bin /pfad/flash_4M_8M.bin /pfad/flash_8M_16M.bin \
  --seconds 6 --png display.png
```

`--flash` nimmt den eigenen Flash-Dump, eine Datei oder Teile in
Adressreihenfolge, zusammen 16 MiB. Ohne startet sie aus einem leeren
Flash mit leeren Patterns, ohne Samples und mit der Werksbank von `factorybank.py`. Am Audio-Eingang steckt nichts.
`--hold-power` hält die Ein/Aus-Taste gedrückt. Der JSON-Bericht nennt
Assertions der Firmware, Display-Wechsel, Panel-Nachrichten, LEDs und
Flash-Befehle; geschrieben wird nur in die Flash-Kopie im Speicher.
Für die Boot-Tests in `test:emu` die Flash-Teile in `E2_FLASH` angeben,
getrennt durch `:` (Windows `;`). Was der Emulator nachbildet und was
er nur annimmt: [Firmware im Emulator booten](messungen/2026-10-08-emulator-boot.md).

`--held 0x2000` hält beim Einschalten Tasten gedrückt (Bit n = Panel-Taste
n, hergeleitet). Welche Masken Startmodi wählen:
[Startphase](messungen/2026-10-10-startphase.md).

### Speicheraufbau des Prüflaufs

Der Prüflauf `tools/emu/runner.py` lädt ausschließlich die eigene VSB und
führt die unveränderte Heap-Wachstumsroutine sowie den Arbeitspuffergeber aus.
Fünf Grenzfälle, exakte Ergebnisse, erlaubte Schreibziele und Rückkehr werden
geprüft. Kein RAM-Snapshot, SD-Zugriff, DSP-Modell oder Hardwarepfad ist dafür
erforderlich.

VSB-Größe genau `0x200100`. Die ersten `0x100` Byte sind Dateikopf,
die folgenden `0x200000` Byte werden ab `0xC0000000` geladen:
`Dateioffset = Adresse - 0xC0000000 + 0x100`. SHA256 bezieht sich auf die
gesamte Eingabedatei; sie wird weder verändert noch kopiert.

| Gemapptes Intervall, Ende exklusiv | Inhalt / Berechtigung |
|---|---|
| `[0xC0000000, 0xC0200000)` | VSB-Nutzlast, ARM-Code und statische Daten, Lesen/Ausführen |
| `[0xC0200000, 0xC274F000)` | Unicorn initialisiert mit Null; Lesen/Schreiben, nicht ausführbar |
| `[0x10000000, 0x10010000)` | Künstlicher Emulator-Arbeitsraum, Null, Lesen/Schreiben; nicht auf dem Gerät |

In der zweiten Region liegen Task-Stacks, Kernel-/BSS-Daten, Heap,
Globals, Patterns, Sample-Info-Cache, der Arbeitspuffer und der IRQ-Stack.
Die Grenzen dazu stehen in [speicherbereiche.md](speicherbereiche.md).
Null ist hier **Modellannahme**, kein geladenes Pattern, kein initialisiertes
FILE, keine betriebsbereite Heapverwaltung und kein laufendes Betriebssystem.
Das Mapping ist auf 4-KiB-Seiten aufgerundet; Padding ist keine Gerätezuordnung.

Für jeden Heapfall neue CPU: Cursor bei `0xC03404AC` auf den angegebenen
Anfangswert setzen, R0 auf den Schritt. Rückgabe und Cursor danach prüfen.
Heap `[0xC06A2940, 0xC08A2940)` bleibt Null; die Wachstumsroutine benötigt
keine Nutzdaten oder Freilisten. Beim Puffergeber zeigt R0 auf `0x10000000`.
Emulator-SP `0x10010000`, LR/Stop `0x10001000`, CPSR `0xD3` (ARM, SVC,
IRQs/FIQs gesperrt). Die Stopadresse wird nicht ausgeführt. Schreiben darf
nur auf Cursor bzw. Ausgabegröße und die oberen 4 KiB des künstlichen Stacks
gehen. Firmware und Daten-RAM haben getrennte Ausführ-/Schreibrechte.

**Absichtlich ungemappt:** Flash, DSP-MMIO und Loader bei `0xFFFF0000`.
Unbekannte Zugriffe scheitern statt automatisch weitere Seiten anzulegen.
Dieses Profil kann keine ganze Firmware booten.

### Speicher für die größeren Untersuchungen

Frühere Import-, Export-, Kernel- und Cache-Untersuchungen liefen zusätzlich auf
einem eigenen, zeitlich zusammengesetzten RAM-Abbild. Ihre Stubs und
Aufrufkonventionen sind hier festgehalten; sie sind noch keine aus der VSB
reproduzierbaren Tests. Eine daraus abgeleitete Binärfixture liegt nicht im
Repository.

Dieses Abbild lag in `[0xC0000000, 0xC8000000)`. Die damaligen Skripte legten
Hilfsobjekte oft ab `0xC1000000` an und den Stack bei `0xC2700000` oder
`0xC2740000`. **Diese Adressen liegen im echten Arbeitspuffer und sind keine
freigegebenen Helferadressen.** Für eine Portierung Hilfsobjekte in einen
eigenen, künstlichen Emulatorbereich legen.

- **Tasks:** VSB-Tabelle ab `0xC00A37A8`, zehn Deskriptoren à 32 Byte.
  +4 Startargument, +8 Einstieg, +12 Priorität, +16 Größe, +20 Stackbasis.
  Zehn TCBs ab `0xC06A24E4` zunächst Null; +8 Konfigurationszeiger und
  Prioritätsbyte +13 setzen. 16 Ready-Queue-Köpfe bei `0xC06A28A4+i*8`
  als doppelte Selbstverweise initialisieren. Globals `0xC06A2924=0`,
  `0xC06A2898=0`, `0xC06A2928=1`. Dann `0xC00003D8(TCB*)` aufrufen:
  Ende-4 Einstieg, Ende-8 Startargument, TCB+24 Ende-8. Keine Tasks starten.
- **Boot:** `0xC00296B0` bis `0xC002984C` ausführen, vor Hardwareinitialisierung
  stoppen. Originalcode löscht `[0xC0200000, 0xC08A2940)` und füllt Stacks.
  Das initialisiert nicht automatisch alle späteren Dienste.
- **Heap:** Vollständige New/Delete-Aufrufe benötigen zusätzliche Verwaltung
  ab `0xC00F8D70`/`0xC00F8E60`. Bisher aus Snapshot; der Prüflauf führt
  nur die davon unabhängige Wachstumsroutine aus. Lock-Enable bei
  `0xC03404B0=0` war historisch eine Modellannahme. Für VSB-New/Delete erst
  den ursprünglichen Initialisierungspfad reproduzieren, keine Freilisten
  aus einem Dump als Konstanten übernehmen.
- **Loader:** Für den gesonderten Lauf `[0xFFFF0000, 0x100000000)` als
  64-KiB-Seite mappen und mit selbst erzeugtem `0xAD` füllen. Originalkopie
  `0xC01705DC..0xC01705F8` überträgt `0xD70` Byte von `0xC017127C`.
  Anschließend `0xC0171280..0xC0171304` initialisiert Daten und Modus-SPs;
  Hardwareaufruf davor überspringen. Kein fertiges Loaderabbild speichern.
  Gemessen: Null `[0xFFFF0D70, 0xFFFF1158)`, eigenes Füllwort DEADC0DE
  `[0xFFFF115C, 0xFFFF125C)`. Undefined/Abort/FIQ/IRQ/SVC/System-SP:
  `0xFFFF1258/1250/1248/1240/1200/11C0`.
- **Arbeitspuffer:** `[0xC0D3A940, 0xC273AA40)`, Null plus synthetische
  Transferdaten; Größe `0x01A00100`. Kein PCM-RAM der CPU.
- **IRQ:** Originalroutine bis `0xC00015B0`, vor MMIO stoppen. SVC-SP vor
  Wechsel zu IRQ-CPSR `0xD2` setzen; IRQ-Tiefenzähler `0xC06A2894=0/1`.
  Sonst arbeitet der bankierte SVC-SP uninitialisiert. Nicht in den Scheduler
  oder eine unendliche Wartefunktion laufen lassen.

### Firmware-Einstiege

Die folgenden Aufrufe liefen offline; nur die ersten beiden sind direkt aus der
VSB reproduzierbar (`runner.py`). Pointerargumente benötigen immer die
beschriebenen gültigen Objekte und kontrollierten Zustand.

| Einstieg | Aufgabe / Argumente | Erwartetes Ergebnis | Beleg |
|---|---|---|---|
| `0xC002CEFC` | Heap wachsen, R0 signierter Schritt | alter Cursor oder 0; Cursorprüfung, fünf Fälle | [Systemspeicher](messungen/2026-10-08-systemspeicher-offline.md) |
| `0xC00369F0` | Arbeitspuffer, R0 Kapazitätsausgabe* | R0 `0xC0D3A940`, Ausgabe `0x01A00100` | [Systemspeicher](messungen/2026-10-08-systemspeicher-offline.md) |
| `0xC00003D8` | Taskinitialisierung, R0 TCB* | initialer SP Ende-8, Einreihung | [Systemspeicher](messungen/2026-10-08-systemspeicher-offline.md) |
| `0xC0028DCC` / `0xC0028DD4` | New R0 Bytezahl / Delete R0 Pointer | sechs Größen im Pool, Rückkehr nach Freigabe; Snapshot-Verwaltung | [Systemspeicher](messungen/2026-10-08-systemspeicher-offline.md) |
| `0xC00296B0` | Boot-Speicherinit, bis `0xC002984C`, SVC-SP `0xC274AA40` | Löschbereich und Stackfüllungen | [Boot/Patterns](messungen/2026-10-08-boot-pattern-speicher.md) |
| `0xC0001560` | IRQ-Eintritt, bankierter SVC-SP, Tiefe 0/1; Stop `0xC00015B0` | äußerer IRQ wechselt Stack, verschachtelter nicht | [Boot/Patterns](messungen/2026-10-08-boot-pattern-speicher.md) |
| `0xC004A350` | Patternresolver, R1 Index | 0..249: `0xC08A2940+(Index+4)*0x4000`; ungültig: 0 | [Boot/Patterns](messungen/2026-10-08-boot-pattern-speicher.md) |
| `0xC01705DC` | Loaderkopie, Stop `0xC01705F8` | 0xD70 Byte zur hohen Seite | [Boot/Patterns](messungen/2026-10-08-boot-pattern-speicher.md) |
| `0xC0171280` | Loaderinitialisierung, Stop `0xC0171304` | Datenfüllungen und sechs Modus-SPs | [Boot/Patterns](messungen/2026-10-08-boot-pattern-speicher.md) |
| `0xC004F340` | Sample-Info-Cache bauen/restore; Cachekennung und Live-Tabellen als Zustand | sechs Tabellen exakt gesichert/wiederhergestellt | [Boot/Patterns](messungen/2026-10-08-boot-pattern-speicher.md) |
| `0xC004EDDC` | DSP lesen, R0 Ziel*, R1 Byteoffset, R2 count16 | synthetische PCM-Wörter exakt | [DSP](messungen/2026-10-08-dsp-audiopfade.md) |
| `0xC004EF28` | DSP schreiben, R0 Quelle*, R1 Byteoffset, R2 count16 | PCM und unveränderte Nachbarbytes | [DSP](messungen/2026-10-08-dsp-audiopfade.md) |
| `0xC0035B10` | WAV importieren, R0 FILE*, R1 Metadaten*, R2 Slot, R3 Pfad* | Status 0 / 0x21 / 4 wie unten | [Import](messungen/2026-10-08-usb-sample-import-offline.md) |
| `0xC0039B2C` | WAV schreiben, R0 Dateiobjekt*, R1 zusätzlicher Kontext*, R2 ESLI*, R3 DSP-Offset, fünftes Argument Bytezahl auf Stack | RIFF/PCM exakt, 64-KiB-Blöcke | [DSP](messungen/2026-10-08-dsp-audiopfade.md) |
| `0xC0027D84` | SysEx-Leseantwort, R0 Antwortkontext*, R1 Kanal, R2 Funktion, R3 CPU-Daten*; Stack: Länge, 2, 0x52 | gepackte Antwort exakt, Quellbuffer unverändert | [DSP](messungen/2026-10-08-dsp-audiopfade.md) |

Nachverfolgte Aufrufketten, keine zusätzliche direkte Einstiegsschnittstelle:
New → `0xC0008F30` → `0xC0008F70`; Delete → `0xC0008F50` → `0xC000EE6C`;
Wachstum über `0xC000A3B0`; DSP-Lesen über `0xC00141F8`, `0xC0014AFC`,
`0xC001488C`; Schreiben über `0xC0014284`, `0xC0014C34`, `0xC00146B4`.
Einzel-/Gesamtexport `0xC0039CC4`/`0xC0039E68` wurden als Aufrufer des
WAV-Schreibers identifiziert; ohne vollständig initialisierte Objektzustände
nicht als VSB-Test-Einstiege anbieten. Die interne Bedeutung des zweiten
WAV-Schreiber-Kontextes ist nicht abschließend benannt.

### Stubs für SD und DSP: WAV ohne Karte

Für den Importtest entstehen WAVs zur Laufzeit mit `wave`/`io.BytesIO`:
PCM etwa `37*i-400` als 16-Bit-LE-Werte, Mono/Stereo und 44.100/48.000 Hz.
Die Testdaten sind eigene Formeln, keine Ausschnitte eines echten Samples.
Geprüft werden mindestens sechs Audio-Byte und ein Transfer über 65.536 Byte.

Das synthetische FILE-Objekt ist kein Betriebssystem-Dateihandle:
vier u32-Wörter, +8 Position, +12 WAV-Größe. Namenspfad NUL-terminiert;
Metadatenpuffer `0x494` Byte. Speicherfile, Puffer und Pfad im künstlichen
Emulatorbereich. R0-R3 des Importers: FILE*, Metadaten*, Zielindex, Pfad*.
Der historische Testindex 742 beweist keinen freien Geräteslot.

`UC_HOOK_CODE` setzt am Eintritt expliziter Stubs R0 auf Status und PC auf LR:

| Adresse | ABI und Ersatz |
|---|---|
| `0xC009DD74` Lesen | R0 FILE*, R1 Ziel*, R2 Bytezahl, R3 Istzahl*. WAV ab FILE+8 kopieren, Istzahl und Position aktualisieren, R0=0. Fehlerfall beim PCM-Start ab Byte 44: R0=1, ohne Kopie. Grenzen aller Pointer prüfen. |
| `0xC009E404` Seek | R0 FILE*, R1 absoluter Byteoffset. Offset gegen WAV-Länge prüfen, FILE+8 setzen, R0=0. |
| `0xC0035AD8` Managerbezug | Künstlichen Managerzeiger zurückgeben; kein Gerätedienst. |
| `0xC007DE7C` Kapazität | `0x01C65EC0 - initialer DSP-Cursor` oder absichtlich 0 zurückgeben. |
| `0xC007E990` Managerabfrage | Historischer Stub R0=`0xFFFFFFFF`; Bedeutung dieses Rückgabewertes nicht als Gerätebeobachtung behaupten. |
| `0xC0014284` DSP-Schreiben, API-Modell | R0 DSP-Byteoffset, R1 CPU-Quelle*, R2 Anzahl 16-Bit-Wörter. In separate synthetische DSP-Byteablage kopieren, R0=0. |
| `0xC00141F8` DSP-Lesen, API-Modell | R0 Offset, R1 CPU-Ziel*, R2 count16, R3=2. Aus DSP-Ablage lesen, fehlende eigene Testbytes mit 0xA5 modellieren, R0=0. |

`0xC004EDF0` nur beobachten: Originalreservierung weiter ausführen,
Metadatenlänge bei +60 protokollieren. DSP-Cursor `0xC00F9C80` und
Live-Sampletabellen davor/danach prüfen. Der historische Importtest setzte
die Aktivmarkierung `0xC036AD88 + 742*1116 + 11` auf 0. Das ist kontrollierter
Testzustand, kein Backup oder sichere Slotreservierung am Gerät.

Im Importtest sofort abbrechen bei unerwartetem Schreiben `0xC009DFB8`, Löschen
`0xC009E9B8`, Assertion `0xC00298BC` und Schedulerpfad `0xC0001D14`. Beim Export
darf einzig der ausdrücklich installierte Schreibstub
`0xC009DFB8(FILE*, Quelle*, Länge, Istzahl*)` Daten in ein Python-bytearray
übernehmen und Status 0 liefern. Niemals Hostdateien aus Firmwarepfaden öffnen.

**Erwartete Ergebnisse:** fünf positive Importfälle liefern Status 0,
PCM exakt, Name, Länge, Rate und aktive Markierung korrekt. Platzmangel
liefert `0x21` vor Reservierung. PCM-Lesefehler liefert 4 nach Reservierung,
aber aktive Markierung und erhöhter Cursor bleiben zurück: fehlender Rollback
ist ein erwarteter Befund, kein bestandener sicherer Import.

### DSP-Portmodell und Haken

Der Test für den originalen ARM-Transfer läuft getrennt von den beiden
DSP-API-Stubs: Page `[0x60000000, 0x60001000)` mappen, zunächst Null. Eigene
DSP-Bytes außerhalb des CPU-RAM in einer Python-Ablage halten; Nachbarbytes
0xA5. `UC_HOOK_MEM_READ`/`WRITE` am Datenport `0x60000000` und Steuer-/Statusport
`0x60000002`, ausschließlich 16-Bit-Zugriffe akzeptieren.

- Statuslesen: vor der Instruktion `0x85` bereitstellen (**Modellannahme**). Bit 7 und Bit 0 waren es schon,
  Bit 2 kam dazu: Korgs Build wartet darauf, bevor es mit einem benutzten Flash seine Daten lädt, und blieb mit `0x81`
  für immer in der Warteschleife (`0xC0014E0C`). Hacktribes Boot ändert sich damit nicht (gemessen: Anzeige und
  Bildschirmnummer alle 50 ms gleich, mit und ohne eigenen Flash).
- Ein Steuerwort `0x2C` allein, wo kein Transfer beginnen kann (Steuerwort 1 eines Rahmens ist immer `A9` oder
  `AB`), ist ein Gleichlaufwort und gehört zu keinem Rahmen. Korgs Build schreibt es einmal früh im Start; ohne
  diese Regel lagen alle späteren Rahmen um ein Wort verschoben, und die Abfragen der Pegel erschienen im Protokoll
  der MFX-Fälle als andere Adressen. Hacktribe schreibt es nicht, die Regel greift dort nie (gemessen: 9051 Steuerwörter in 8 s mit eigenem Flash,
  das sind genau 1293 Rahmen zu 7 Wörtern).
- Sieben Steuerwörter sammeln: `[A9 oder AB, offset_low, offset_high,
  count16, 2, 0, 0]`. Offset in Byte, Länge in 16-Bit-Wörtern. Unvollständige
  Frames, falsche Breite und Transfers außerhalb der Testablage scheitern.
- A9: Datenlesen stellt vor jedem Zugriff das nächste LE-Wort bereit.
  AB: Datenschreiben übernimmt genau das nächste LE-Wort.
- Freie Sperre/normalen Task modellieren: `0xC06A2894=0`,
  `0xC06A2928=1`, `0xC06A2480=1`. Am Hook `0xC00145F0` historisch R0=1
  für LR `0xC0014814`/`0xC0014A34`, sonst 0. GPIO-Verhalten ist simuliert.
- Originalcode von `0xC004EF28` bzw. `0xC004EDDC` bis zur LR-Stopadresse
  ausführen; Assertions/Scheduler nicht als erfolgreiche Rückkehr ersetzen.

Prüfen: 3, 16, 17, 32, 33 Wörter, PCM bytegenau, sämtliche benachbarten
Bytes unverändert, Semaphore wieder frei. Kurze Schreibvorgänge nutzen
Read/Modify/Write von 16 Wörtern; bei 17 sind zwei überlappende Transfers
ab Offset und Offset+2 Byte erwartet. Das Modell beweist weder reales
DSP-Timing noch Klang, Cachekohärenz oder parallele Aufnahme/Wiedergabe.
API-Modell und Portmodell getrennt benennen; kein ungetesteter Gesamtpfad.

### Reihenfolge für die vollständige Portierung

1. Originale Kernel-/Allocatorinitialisierung aus VSB reproduzieren;
   unerwartete MMIO-Zugriffe stoppen. Keine Snapshot-Pointer konservieren.
2. Synthetische Sampletabellen und Objekte initialisieren, Besitzer und
   zulässige Schreibziele protokollieren; Import mit Speicherfile und DSP-API.
3. Die sieben Importfälle inklusive des fehlenden Fehler-Rollbacks prüfen.
4. DSP-Portmodell separat mit fünf Wortlängen prüfen, erst dann kombinieren.
5. Export mit synthetischen Metadaten, Schreibstub und mehreren Blöcken;
   Fehler-/IRQ-/Semaphorefälle ergänzen.

Die fehlende VSB-Initialisierung bleibt sichtbar; sie wird nicht durch erfundene,
als gemessen ausgegebene Daten ersetzt. Gerätepfade, Execute, Flashschreiben und
Türsteherintegration sind eigene Aufgaben.

## Original-Firmware und Hacktribe

Der Emulator führt Korgs eigene `SYSTEM.VSB` 2.02 ("Original", im Code `stock`) aus wie die von
Hacktribe. Beide sind Sampler 2.02 und teilen fast allen Code; Hacktribe ist ein Satz kleiner Umbauten im
Code plus neuer Code und neue Tabellen in sonst gelöschten Bereichen. Messungen und Belege:
[Korgs Original-Firmware 2.02 im Emulator](messungen/2026-10-14-stock-emulator.md).

**Gemessen:** das Original bootet ohne Änderung am Emulator bis zum Hauptbild, auf allen Startwegen
wie Hacktribe, mit Tasten, LEDs, Display, MIDI nach dem Start und virtueller Karte. **Nicht übertragbar**
ist, was Hacktribe hinzufügt.

### Profil: wo die Stellen sitzen

Die Adressen der Stellen, die der Emulator ersetzt oder liest, sind kein Wissen des Emulators, sondern
Tatsachen eines Builds. `tools/emu/firmware.py` schlägt sie beim Laden nach (`identify`, Ergebnis `Profile`):

| Stelle | Adresse (beide Builds) | Was das Modell damit tut |
|---|---|---|
| `assert_handler` | `0xC00298BC` | der Lauf endet davor, die Meldung (Datei, Zeile) wird gemerkt |
| `flash_read` | `0xC001E4AC` | Treiberlesen, die Bytes werden in einem Zug kopiert |
| `dsp_upload` | `0xC0011AB8` | der DSP ist ein Platzhalter, das Programm geht nirgends hin |
| `tx_full` | `0xC0024CB4` | UART-Sendeschleife: das Byte passte nicht, die Scheibe endet |
| `screens` | Zeiger `0xC03404C0` | Bildschirm-Verwaltung, `+0x2C` ist die Nummer des Bildschirms |
| `panel` | Zeiger `0xC033E6F8` | Bedienfeld-Objekt, `+0x18` gehaltene Tasten, `+0x20` Startmodus (nur `bootmap.py`) |
| `user_check` | `0xC0029D78` | Prüfung der Nutzerdaten-Kennung (nur `bootmap.py`) |

Die Panel-Version `0x96` gehört dagegen nicht zum Profil: das Bedienfeld ist Hardware und meldet sie unabhängig davon, was die zu prüfende Firmware erwartet (sonst fände die Startprüfung eine geänderte Versionsprüfung nie).

Gefunden wird eine Stelle an ihrem Code, nicht an einer Tabelle von Dateihashes. Verglichen werden 16
Befehlswörter, wobei alles, was vom Ort abhängt (Sprungziele, pc-relative Ladeoffsets), ausgeblendet
ist. Im Repository steht je Stelle nur ein Hash dieser Wörter, nichts von der Firmware. Dadurch zählt
auch eine Hacktribe-Datei mit geänderten Presets, Menülängen oder Startbild, oder mit Patches im
übrigen Code, als dasselbe Build. Stimmt die Stelle an der üblichen Adresse, kostet das nichts; sonst
wird das ganze Abbild durchsucht (rund 2 s) und die verschobene Stelle in `Profile.moved` gemeldet.
Fehlt eine nötige Stelle, verweigert der Emulator die Datei mit ihrem Namen ("Das ist keine
Sampler-2.02-Fassung, die der Emulator kennt: flash_read fehlt."), statt an einer falschen Adresse zu
haken. `python tools/emu/firmware.py SYSTEM.VSB` zeigt das Profil, `--sign ADDR` erzeugt die Signatur
einer neuen Stelle.

Welches Build es ist, sagt ein Lauf, den nur Hacktribe füllt: Ab Nutzlast `0x170000` steht bei Hacktribe
Code, bei Korg 0xFF. Preset-, Menü- und Startbildänderungen berühren ihn nicht. Dieselbe Regel steht in
`src/firmware.mjs` (`buildOf`), damit die Seite vor dem Hochladen weiß, was sie vor sich hat. Der Dienst
meldet sie zusätzlich im Status (`firmware.build`, `firmware.folder`).

### Was nur Hacktribe hat

| Funktion | Original | Auf der Seite |
|---|---|---|
| SysEx `0x52` bis `0x57`: RAM lesen und schreiben, FX-Presets, Flash lesen | wird nicht beantwortet (die Gerätesuche schon); mit BLECHTRIBE gibt es dafür BLECHTRIBEs eigene Befehle `0x60` bis `0x63` ([Messung](messungen/2026-10-15-blech-sysex.md)), die auch hier gehen, aber weder Flash lesen noch Code ausführen | eine Zeile im Bereich Emulator sagt, was fehlt; ohne BLECHTRIBE zeigt die Seitenleiste den Grund und der Probe-Dienst und das Terminal lehnen ab, mit BLECHTRIBE gehen sie |
| Effekt-Presets an den Stellen der Gerätekarte | die Tabellen sind leer, Korg legt die Presets verstreut ab und findet sie über zwei Zeigerfelder ([Preset-Tabellen](messungen/2026-10-15-preset-tabellen.md)) | der Effekt-Editor liest sie über die Zeiger, mit dem Hinweis "Original-Firmware", schreibt in die Datei und, mit BLECHTRIBE, live ins RAM des Emulators ([Messung](messungen/2026-10-15-effekt-editor-original.md)) |
| Gruppen-Grooves bei `0x143C00` | fehlen | die Datei gilt nicht als bekannt (`known: false`) |
| BLECHTRIBE-Patches, Plugins | die Patches gehen auch auf das Original (Patcher: "BLECHTRIBE direkt"), mit eigener Fassung des Kartenordners; Plugins brauchen das BLECH-Menü ([BLECHTRIBE auf Korgs Original](messungen/2026-10-14-stock-blech.md)) | Plugin-Bereich zeigt einen Hinweis, Schreiben und Simulieren gehen weiter |
| Kartenordner | `KORG/electribe sampler/`, mit Leerzeichen | der Dienst liest den Ordner aus der Firmware (`card_folder`) |

`identify` in `src/firmware.mjs` kennt das Original als Datei (`build: "stock"`, `known: false` mit dem
Grund) und erkennt von Hacktribe nur die vermessene Fassung als `known`. Die Karte der Gerätewerte
(`data/map/`) beschreibt Hacktribes Tabellen und hat für das Original nichts.

### Grenzen

- Die Prüffälle der Patches (`splash_cases.py`, `mfx_cases.py`, `menu_cases.py`, `pswitch_cases.py`, `loadbar_cases.py`, `script_cases.py`) rechnen mit
  Adressen für Pattern, Sequenzer, Menü und Skripte, die an Hacktribe gemessen sind; ihre Konstanten sind keine
  Stellen des Profils. Auf einer mit BLECHTRIBE gepatchten Kopie von Korgs Original bestehen die Fälle von `check.py`
  (Zahlen in [BLECHTRIBE auf Korgs Original](messungen/2026-10-14-stock-blech.md)), `script_cases.py` ist dort nicht
  gelaufen.
- `check.py` prüft das Original unverändert (`--base` und `--patched` dieselbe Datei) mit allen Startwegen und
  eine gepatchte Kopie des Originals gegen das Original.
- Das Original braucht beim Hochfahren mehr Gerätezeit als Hacktribe: 600 gegen 400 ms bis zum Hauptbild mit
  leerem Flash, mit dem eigenen Flash rund 6 s, weil es dann seine Daten lädt und dabei einen Ladebalken über das
  Startbild zeichnet. Die Prüfläufe warten darauf (`Machine.loading`, `finish_boot`).

## Die blaue Electribe 2 (Synth)

Die `SYSTEM.VSB` 2.02 der blauen Electribe 2 läuft im Emulator, im Code `synth`, bis zum Hauptbild, mit Tasten,
Drehgeber, Display und LEDs (kein Klang, wie bei jeder Firmware). Sie ist derselbe Code wie der Sampler, jede Stelle
ist nur verschoben. Messung und Belege:
[Die blaue Electribe 2 im Emulator](messungen/2026-10-15-blaue-electribe.md).

- `firmware.py` hat für sie eine zweite Stellentabelle (`SYNTH_SITES`) und probiert sie, wenn die des Samplers nicht
  passt. `Profile.user_mark` ist die Kennung, die die Firmware im Flash bei `0x220000` prüft (`KORGelec2USR`, beim
  Sampler `KORGele2sUSR`); der leere Flash trägt sie.
- Der Dienst hält die Nutzerdaten des Synths in `flash-synth.bin` neben `flash.bin`. Der Kartenordner ist
  `electribe` (hergeleitet).
- Die Seite erkennt die Datei am Kopf und sagt das in einer Zeile. Editor, Effekt-Editor, Patches, Plugins und
  Samples sind für den Sampler und werden für diese Firmware nicht angeboten.
- `check.py` und die Prüffälle des Synth-Satzes laufen gegen Korgs blaue 2.02 (Workflow "Verify patches", Job `blue`). Nicht geprüft: ein benutzter Flash, die Karte.
- Wie der Synth seine PCM-Wellen lädt, wie die Oszillator-Tabelle auf sie zeigt und ob BLECHTRIBE dort Samples von der Karte
  zu Oszillatoren machen könnte, steht in [Samples auf der blauen Electribe 2](messungen/2026-10-15-synth-samples.md). Ein Flash mit der PCM-Bank aus den WAV-Dateien der blauen Electribe baut `tools/emu/synth_pcm_flash.py` (lokal, nie ins Repository; [Messung](messungen/2026-10-15-synth-pcm-flash.md)).
  `tools/emu/synth_probe.py` ist das Werkzeug dazu (Bank lesen, Oszillator-Tabelle, Start mit einer selbstgebauten Bank,
  Stimmennachrichten, Kartenfunktionen); seine Tests laufen mit `E2_BLUE_VSB` in `npm run test:emu`.

### Hacktribe auf der blauen

Hacktribe für die blaue ist Sampler-Code auf der blauen Hardware ([Idee 65](ideen/65-blech-hacktribe-blau.md)). Welche
Hardware der Emulator spielt, steht in der Kennung im Flash: die blaue `KORGelec2USR`, die rote `KORGele2sUSR`
(`firmware.HARDWARE_MARKS`).

- `machine.py --hardware blue` und `check.py --hardware blue` starten ohne `--flash` von einem leeren Flash der blauen,
  mit ihrer Kennung und ohne Sample-Bank. Der Fall `normal_blank` von `check.py` nimmt die Hardware des gegebenen Flashs.
- Der Dienst liest die Hardware aus dem Kopf der VSB (`E2` statt `E2S`): auch Hacktribe mit blauem Kopf läuft auf
  `flash-synth.bin` und, solange die fehlt, auf einem leeren Flash der blauen. Eine Prüfung (`POST /check`) nimmt den Flash
  der Hardware des Originals; `?hardware=blue` sagt es für eine Datei mit Sampler-Kopf, die auf der blauen laufen soll.
- `tools/emu/hacktribe_blue_probe.py` geht jeden Update-Weg auf der blauen durch (Korgs blaue, Hacktribe, BLECHTRIBE mit
  Hacktribe, der Weg zurück), mit beiden Köpfen; Messung:
  [BLECHTRIBE mit Hacktribe auf der blauen](messungen/2026-10-26-blech-hacktribe-blau.md).

## Check und Tests

### Prüflauf

`runner.py` gibt nur JSON auf stdout aus, Fehler auf stderr, Exitcode 0
ausschließlich bei erfolgreichen Prüfergebnissen:

```sh
tools/emu/.venv/bin/python tools/emu/runner.py --vsb /pfad/SYSTEM.VSB
```

Der Bericht enthält Firmware-SHA256, Version, Initialisierung, fünf
Heap-Grenzfälle und Arbeitspuffer-Kapazität. Er enthält keine Firmwarebytes und
keine Speicherinhalte. Im ARM-Lauf gelten 200.000 Instruktionen und zwei
Sekunden Unicorn-Zeitlimit pro Aufruf. Nach jedem Lauf muss PC die
Rückkehradresse erreicht haben; ein Limit allein ist kein erfolgreicher Test.
Node startet das Werkzeug mit `spawnSync`, Argumentliste ohne Shell und
20 Sekunden Prozesslimit. Ein Lauf liefert einen JSON-Bericht oder Exitcode 1
mit Fehlertext.

### Startphase und Prüfung vor dem Export

`bootmap.py` bootet eine VSB auf 17 Startwegen (normal, Update-Abfrage,
Panel-Update, jeder Startmodus, Notschalter) und listet den Code, der bis
zum ersten Hauptbildschirm läuft, und die Bytes des Abbilds, die dabei
gelesen werden. Die Startphase endet genau dort, wo die Firmware den
Hauptbildschirm setzt, nicht erst am Ende der 20-ms-Zeitscheibe, in der das
passiert: Code, der erst auf dem Hauptbildschirm läuft (etwa der Bildhaken der
Skript-Laufzeit hinter seinem Tor), zählt nicht mit, egal wie der Bildtakt zum
Hauptbildschirm liegt. `check.py` macht daraus die Prüfung für eine gepatchte
Kopie: alle Startwege müssen ankommen, und kein geändertes Byte darf in
Code oder Daten der Startphase liegen, außer Daten, die die Karte kennt
(`--allow`, etwa das Startbild). Ein Lauf dauert rund anderthalb Minuten.

```sh
tools/emu/.venv/bin/python tools/emu/check.py --base SYSTEM.VSB --patched NEU.VSB --allow 0xF9954:1024
```

Der Dienst bietet dasselbe als `POST /check` (Original und Kopie
hintereinander im Körper, `?allow=Stelle:Länge,...`, dazu `allowCode` für
Startphasen-Code, den ein Patch begründet ersetzt, wie `--allow-code`); die
Seite ruft es vor dem Download auf. Während es läuft, liefert `GET /check/progress`
den Stand (`state`, `total`, `done`, `ok`, `fail` und je Gruppe Name, Zustand und Zähler;
`progress.py`); `check.py` schreibt dieselben Schnappschüsse als JSON-Zeilen nach stderr.
Die Seite zeigt daraus Balken und Gruppenliste. Ein gemerktes Ergebnis (Cache) meldet keinen
Fortschritt.

Unterstützter Untersuchungsstand: Sampler 2.02 mit dem dokumentierten
Hacktribe-Build. Größenprüfung allein identifiziert keine Firmwareversion;
abweichende Funktionsergebnisse, Speicherfehler und ausbleibende Rückkehr
führen zum Fehler. Das ist keine Freigabe für Gerätezugriffe.

### Fälle von Hand starten

Drei Stolpersteine, die wie ein Fehler im Code aussehen:

- **Die Fälle laufen auf einem leeren Flash.** `check.py` führt die Fälle der Patches auf einem leeren Flash aus
  (wie CI, `--hardware blue` für einen blauen), nicht auf dem eines Nutzers: sie erwarten die Init-Patterns eines leeren
  Flashs (ein Takt, keine Kette). Ein Flash mit gespeicherten Patterns lässt Fälle scheitern (gesehen bei
  `tap_motion_cases` Gruppe 5 mit `KeyError (0, 28)`, `pswitch_cases` Gruppe 14 und `dice_cases` Gruppe 3). Der eigene Flash
  eines Nutzers geht nur mit `--boot-flash` an die Startszenarien (die App macht es so, `server.py`). Ändert sich der eigene Flash, läuft wegen des Task-Caches
  jeder Task neu, nicht nur die Starts ([Entwicklung](development.md)).
- **Jedes Fallmodul mit eigenem `Dev` ruft `menu_cases.for_build(payload)`** (oder `menu_cases.boot`). Die Vorgaben von
  `menu_cases` sind die der Hacktribe (MENU 45, BASE_RING 29); ein Modul, das sein Gerät selbst baut und das nicht tut,
  steuert die blaue mit den Bildschirmnummern der roten an und stürzt ab (`UC_ERR_READ_UNMAPPED`). Früher fiel das nicht
  auf, weil ein vorheriger Task im selben Prozess den Build schon gesetzt hatte; seit jeder Task einen eigenen Prozess
  bekommt, schon. Beispiel: `power_off_cases.for_build`.
- **Eine Test-VSB, die vor einer Änderung gepatcht wurde, trägt die alte Laufzeit.** Ein Fallmodul, das man von Hand mit
  `cases --patched Datei.VSB` startet, nimmt genau diese Datei. Nach einer Änderung an `tools/patch/script_*.s` und
  `node tools/patch/script_runtime.mjs --build ...` bricht das Laden eines Plugins dann mit Fehlercode 19 ab, oder die Fälle
  stürzen ab. Die Datei neu patchen, dann stimmt es wieder. `tools/verify-patches.mjs` patcht immer frisch.

### Tests

`npm test` überspringt den Prüflauf auch mit gesetztem `E2_VSB` und braucht
keine Python-Installation (ohne Python werden die Python-Tests übersprungen);
keine Firmware wird für CI geladen oder hochgeladen.
`npm run test:emu` führt nur die Emulator-Tests aus und braucht nur `E2_VSB`;
ohne sie scheitert er:

```sh
E2_VSB=/pfad/SYSTEM.VSB npm run test:emu
```

Mit `E2_STOCK_VSB` (Korgs eigene `SYSTEM.VSB` 2.02) laufen zusätzlich die Tests für das Original:
Boot bis zum Hauptbild, alle Startwege, Bedienfeld, MIDI nach dem Start und die Karten-Tests mit
`KORG/electribe sampler/`. Ohne die Variable werden sie übersprungen, sie sind nie Pflicht.
Dasselbe gilt für `E2_BLUE_VSB` (die `SYSTEM.VSB` der blauen Electribe 2): Build, Stellen, Boot bis zum Hauptbild
und Bedienfeld.

`npm run test:local` führt sie mit den übrigen Prüfungen aus und braucht `E2_VSB`
und `E2_PATTERNS`. Für die Boot-Tests die Flash-Teile in `E2_FLASH` angeben
(siehe "Die ganze Firmware starten"). Die Python-Tests ohne Firmware
(`test_server.py`, `test_fat32.py`, `test_sdcard.py`, `test_cardstore.py`,
`test_lcd.py` und weitere) laufen in `npm test`; `test_timer.py` und
`test_snapshot.py` brauchen die Firmware.

Emulatorergebnisse sind keine Messung am Gerät. Als Beleg für die Gerätekarte
taugt allenfalls `derived:` mit dokumentierter Herleitung, sichtbar als
Emulatorbefund benannt; Gerätetests bleiben `measure:`.

## Lizenz

Das Python-Programm in `tools/emu/` steht unter GPL-2.0-only, der vollständige
Text liegt in [tools/emu/LICENSE](../tools/emu/LICENSE). Node-Testanbindung und
Editor bleiben AGPL-3.0-only. Beide sprechen über Dateipfad und einen kleinen
Ergebnisbericht miteinander, ohne gemeinsam genutzte Laufzeitobjekte. Unicorn
wird nicht mitgeliefert, die Abhängigkeit wird selbst installiert; ein
Browserbundle enthält kein Unicorn. Version, Herkunft und Lizenzgrenze stehen
in [NOTICE](../NOTICE).
