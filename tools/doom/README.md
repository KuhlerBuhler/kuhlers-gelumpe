# Nativer Doom-Start

Stand 15.10.2026: Der Lader ist ein Patch des BLECH-Satzes (`data/patches/doom-loader.json`, gebaut von
`tools/patch/doom_loader.py`), und `doom.bin`, `doom.wad` samt Quellen und Lizenzen liegen in
`third_party/doom/`. Die Seite Patcher erzeugt die Firmware mit dem Lader und bietet beide Dateien
für die Karte an. `build_bootstrap.py` bleibt für die Emulator-Prüfläufe: seine Basis ist der Satz ohne den
Doom-Lader (`currentPatches` lässt ihn weg), das Ergebnis ist dasselbe Abbild.

SHIFT + TAP beim Einschalten wählt Doom innerhalb des BLECH-Abbilds.
EXIT und die bestehenden Rettungs- und Updatewege haben Vorrang.
Ohne Kombination läuft der Sampler. Der Bootloader bleibt unverändert.

Der eigene SD-Lader verwendet den im aktuellen Speicherplan reservierten ROM-Bereich. Er aktiviert nur Startup
und SD, liest `KORG/blechtribe/Doom/doom.bin`, prüft die exakt eingebauten
Dateigrößen und SHA256 und springt erst danach ins geladene Programm.
Die originale, gepinnte doomgeneric-Engine liest ihre Spieldaten als
`KORG/blechtribe/Doom/doom.wad` über die echten FatFs-Funktionen.
Es gibt keinen Host-Dateiaufruf und keine BLECH-VM im nativen Lauf.

## Bauen und im Firmwareemulator prüfen

Benötigt: ein lokales Abbild des aktuellen Integrationsstands, eigener
Flashdump, externe doomgeneric-Quelle mit Revision
`e257a09527062bfb986b6e5e0780839b6cbd5b71`, Arm GNU 14.2.Rel1 und eine
rechtmäßig vorhandene IWAD. Die bisherigen Läufe verwenden Freedoom 0.13.0.
Compiler und alle erzeugten Dateien bleiben außerhalb des Repos; die Engine als
Binärdatei, ihre Quelle und die WAD liegen in `third_party/doom/`. Die beiden neuen Builder verweigern Ausgaben in Git-Verzeichnissen,
auch über symbolische Links.

Die folgenden Variablen benennen eigene lokale Pfade; kein Befehl spricht
MIDI oder ein echtes Gerät an.

```sh
python3 tools/doom/build_runtime.py \
  --source "$doom_source" --toolchain "$doom_toolchain" \
  --output "$doom_output/runtime"

python3 tools/doom/build_bootstrap.py \
  --base "$doom_base" --original "$doom_original" --program "$doom_output/runtime/doom-runtime.bin" \
  --toolchain "$doom_toolchain" --output "$doom_output/bootstrap"

tools/emu/.venv/bin/python tools/doom/run_runtime.py \
  --image "$doom_output/bootstrap/SYSTEM-doom-emulator.VSB" \
  --program "$doom_output/runtime/doom-runtime.bin" \
  --wad "$doom_wad" --flash "$doom_flash" \
  --seconds 200 --card-mib 512 --scenario controls --output "$doom_output/play"
```

Die Basis wird aus dem hashgepinnten Original und dem aktuellen BLECH-Patchsatz
vollständig rekonstruiert. `doom_original` benennt dieses Original. Ein
veraltetes Abbild oder eine Abweichung an beliebiger Stelle wird abgelehnt.
`--extra-patch DATEI` nimmt zusätzliche Patches in denselben Wiederaufbau
und die gemeinsame Speicherprüfung auf. Dazu müssen ihre Haken im aktuellen
Register bekannt sein. Eine unbekannte Kette wird abgelehnt.

`layout.json` reserviert `0xC017CC00..0xC017DC00` für den Lader,
`0xC017DC00..0xC017F000` für seinen Zustand und
`0xC017F000..0xC0180000` für gemeinsame Daten.
Die gemeinsame Patch-Speicherprüfung und die FF-Bytes des konkreten
Basisabbilds müssen beide passen. Eine alte Engine mit anderer gemeinsamer
Adresse wird beim Bau des Laders abgelehnt.

`manifest.json` hält jeweils Hash, Länge und RAM-Grenzen fest.
`result.json` hält Spielticks, Tasten, Blickrichtung, SD-Zugriffe, drei
Randwächter und den höchsten beobachteten Stackverbrauch fest.
`frame.png` zeigt die tatsächlichen über SPI gesendeten Displaybytes.
Die 512-MiB-Testkarte hat 4-KiB-Cluster; die 64-MiB-Fehlerkarte hat
512-Byte-Cluster. Ladezeiten sind ausdrücklich von dieser Geometrie abhängig.
Der Bedientest wartet auf laufende Spielticks nach der Übergangsanimation
und prüft Drehung, Bewegung, Munitionsverbrauch, Benutzen, E2M1, Quit und
Ausschalten. `game-frame.png` hält die tatsächliche Spielausgabe vor dem
Ausschalten fest. Ohne `--scenario controls` prüft der kürzere Lauf nur
die Drehung.

Die Pflichtprüfung für den lokalen Port läuft mit
`E2_DOOM_REQUIRED=1 node --test test/doom-native.test.mjs`.
Dazu `E2_EMU_PYTHON`, `E2_DOOM_BUILD`, `E2_VSB`, `E2_DOOM_IMAGE`,
`E2_DOOM_PROGRAM`, `E2_DOOM_WAD` und `E2_FLASH` auf die eigenen lokalen
Artefakte setzen. Sie verlangt zusätzlich den positiven Spiellauf,
Startregression, Fehlerwege und Ausschalten. Ohne diese lokalen Dateien
werden die entsprechenden Tests ausdrücklich übersprungen.

## Tasten und Grenzen

| Electribe | Doom |
|---|---|
| PART ab / auf | vorwärts / rückwärts |
| EDIT links / rechts | links / rechts drehen |
| PLAY | schießen |
| TAP | benutzen |
| REC | bestätigen |
| MENU oder EXIT | Menü / abbrechen |
| Ein/Aus halten | native Selbsthaltung ausschalten |

Doom rendert intern 320 mal 200 Pixel. Der Port verkleinert und dithert auf
128 mal 64 Pixel: gewichtete Flächenmittelung, Spreizung zwischen dem zweiten
und 98. Helligkeitsperzentil und Atkinson-Fehlerverteilung. Bei weniger als
16 Helligkeitsstufen Unterschied bleibt der Kontrast unverändert. Jede
Quellzeile wird nur einmal in einen Ring aus vier Zeilen eingelesen. Der
Port sendet beide Displayhälften. Gegner sind aktiv;
Ton und Speichern sind abgeschaltet. SD-Dateien werden nur gelesen.
Quit zeigt `DOOM STOP`, Fehler zeigen `DOOM ERROR` mit Code. Ein/Aus bleibt
in diesen Zuständen bedienbar. Nach erneutem Einschalten ohne SHIFT + TAP
ist der normale Sampler der Rückweg. Das ist im Emulator geprüft;
Bildrate, Cachewirkung, Tasten und Ausschalten am Gerät bleiben ungeprüft.

Der Bereich `0xC1000000..0xC1800000` liegt im Arbeitspuffer des normalerweise
laufenden Samplers. Seine Verfügbarkeit im Doom-Zweig ist aus den beobachteten
Tasks und dem ausgelassenen Samplerstart hergeleitet, keine allgemeine
RAM-Reservierung. Drei Randwächter prüfen Überläufe an diesen Grenzen;
sie beweisen keine vollständige Schreibisolation.

## Frühere getrennte Machbarkeitsproben

Die separate Firmware-Treiberprobe startet nur im Emulator SD, Display und
Panel ohne Sampleranwendung. Sie verwendet weder MIDI noch ein echtes Gerät:

```sh
tools/emu/.venv/bin/python tools/doom/boot_probe.py \
  --base "$HOME/Desktop/SYSTEM.VSB" \
  --flash "$HOME/Desktop/electribe-flash/flash_full_2026-10-09.bin"
```

Erwartet: 25 Prüfungen bestanden. Ohne `--frame` entsteht ein eigenes
Testbild. `--frame DATEI` liest genau 1024 Byte im nativen Displayformat
von einer schreibgeschützten virtuellen Karte und sendet sie über den
Firmwaretreiber. Die Probe lädt ihren Diagnosecode vor dem Boot direkt
ins emulierte RAM. Sie ist noch kein SD-Lader für Doom. Als Basis werden
nur die dokumentierte SYSTEM.VSB und BLECH v8 akzeptiert. Bei fehlender
Karte oder Datei hält die Diagnose mit Fehlerstatus; das ist kein
auslieferbarer Rückweg in die Sampleranwendung.

Der Firmwaretest im Node-Testlauf ist ausdrücklich einzuschalten:

```sh
E2_EMU_REQUIRED=1 E2_VSB="$HOME/Desktop/SYSTEM.VSB" \
  E2_FLASH="$HOME/Desktop/electribe-flash/flash_full_2026-10-09.bin" \
  node --test test/doom-boot.test.mjs
```

Der folgende Engineversuch ist davon getrennt.

Diese lokale Machbarkeitsprobe baut die unveränderte `doomgeneric` Engine
und führt ihren ARM-Code in Unicorn aus. Sie verbindet keine Firmware und
keine Hardware. Der Testadapter ersetzt Dateizugriff, Zeit und Tasten.
`probe.ld` verwendet eine künstliche Adresse, keine freigegebene Geräteadresse.

Die Engine bleibt außerhalb des Repos. Erwarteter Commit:
`e257a09527062bfb986b6e5e0780839b6cbd5b71` aus
[ozkl/doomgeneric](https://github.com/ozkl/doomgeneric/tree/e257a09527062bfb986b6e5e0780839b6cbd5b71).
Der Builder lehnt andere Commits und lokal veränderte Enginequellen ab.
Die Engine enthält GPL-2.0-or-later und GPL-3.0-or-later;
Details und offene Prüfung stehen unten bei Quellen und Weitergabe.
Die eigenen Adapter folgen der AGPL des Projekts.

## Voraussetzungen

- Arm GNU Toolchain 14.2.Rel1, `arm-none-eabi`, mit Newlib.
- Python mit Unicorn 2.1.4, beispielsweise `tools/emu/.venv/bin/python`.
- Ein separat bereitgestelltes IWAD. Die Probe erwartet den Namen
  `freedoom1.wad` in ihrem virtuellen Dateisystem.
- Ein Ausgabeverzeichnis außerhalb des Repos.

Geprüfte portable Werkzeugkette für diesen Mac:
[Arm GNU 14.2.Rel1, Darwin ARM64](https://developer.arm.com/-/media/Files/downloads/gnu/14.2.rel1/binrel/arm-gnu-toolchain-14.2.rel1-darwin-arm64-arm-none-eabi.tar.xz).
Andere Hosts brauchen das entsprechende Arm-Paket. Die Werkzeuge werden
nicht automatisch installiert oder heruntergeladen.

Geprüfte freie Spieldaten:
[Freedoom 0.13.0](https://github.com/freedoom/freedoom/releases/tag/v0.13.0).
Dessen mitgelieferte `COPYING` Datei nennt die Bedingungen der BSD Lizenz
mit drei Klauseln. Engine und Spieldaten sind unterschiedliche Projekte.
Die Probe belegt die Originalengine mit Freedoom-Inhalten.

## Reproduzieren

Die Variablen zeigen auf lokal vorhandene, entpackte Verzeichnisse.
WAD, fremde Quellen, Werkzeugkette und erzeugte Dateien bleiben außerhalb
des Repos. Der `--output` Pfad wird bei Bedarf angelegt. Standardmäßig werden Gegner
und Ton abgeschaltet. `--monsters` beim Build aktiviert die normalen Gegner;
der Ton bleibt ausgeschaltet.

```sh
python3 tools/doom/build_probe.py \
  --source "$doom_source" \
  --toolchain "$doom_toolchain" \
  --output "$doom_output/build" \
  --zone-mib 6

tools/emu/.venv/bin/python tools/doom/run_probe.py \
  --build "$doom_output/build" \
  --wad "$doom_wad" \
  --output "$doom_output/run"

tools/emu/.venv/bin/python tools/doom/run_probe.py \
  --build "$doom_output/build" \
  --wad "$doom_wad" \
  --output "$doom_output/input" \
  --input
```

Für den zusätzlichen Gegnerlauf beim Build `--monsters` ergänzen und ein
eigenes Buildverzeichnis wählen, beispielsweise `"$doom_output/monsters"`.
Danach dieselbe `run_probe.py` mit diesem Build und `--input` ausführen.
`build.json` hält fest, ob Gegner aktiviert sind. Die Argumentanzahl im
C Startadapter folgt automatisch dem erzeugten Argumentarray.

Erwarteter Exitcode je Lauf: 0. `build.json` nennt Compiler und Optionen;
`architecture.txt`, `size.txt`, `symbols.txt` und `undefined.txt` dokumentieren
den Build. `result.json` enthält RAM-Anforderung, WAD-Lesezugriffe, Spielticks,
Blickrichtung und Bildhashes. Ein auf 1 MiB unterhalb des anfänglichen SP
begrenzter Schreibzugriffshaken misst außerdem den niedrigsten beschriebenen
Stackwert und den niedrigsten bei Schreibzugriffen beobachteten SP. `console.log` enthält die Meldungen der Engine.
Die beiden PBM Dateien zeigen Beginn und Ende in 128 mal 64 Pixeln.

Ein Lauf gilt nur bei echten Spielticks und gesetzten Bildpixeln als Erfolg.
Die ersten Bilder können wegen des Doom Übergangseffekts schwarz sein.
`--input` drückt nach Spielbeginn die rechte Richtungstaste und lässt sie
wieder los; am Ende muss die Blickrichtung verändert sein.

## Grenzen

Die Engine rendert weiterhin 320 mal 200 Pixel. Der eigene Adapter verkleinert
das Bild auf 128 mal 64 und wandelt es mit einem geordneten Ditherraster in
1024 Byte um. Nur die Ausgabeschicht wurde ergänzt. Ein direktes Setzen der
Engineauflösung auf 128 mal 64 genügt bei dieser Engine nicht, weil deren
bestehende Bildausgabe nur ganzzahlig vergrößert.

Das IWAD liegt im Python-Prozess. Der emulierte ARM liest Ausschnitte über
seine Dateischnittstelle. Dies belegt Dateiverhalten und Enginepuffer,
jedoch keinen FatFs Aufruf oder SD-Durchsatz. Zeit und Eingabe sind synthetisch.
Unicorn-Ausführungszeit ist kein Beleg für die Bildrate auf echter Hardware.
Ton, Speichern, weitere Karten, Startauswahl und Samplerfreiheit bleiben offen.

## Quellen und Weitergabe

Jeder vollständige Runtimebuild erzeugt `doom-sources.tar.gz` und
`sources.json` außerhalb des Repos. Das Archiv enthält die gesamte
gepinnt ausgecheckte Engine, unseren tatsächlich gebauten Adapter,
Header, Linkerskript, Buildskripte, Repo-Lizenz, Compilerkonfiguration und
Toolchainmanifest. `build.json` bindet Quellhashes an den Binärhash.
Änderungen während des Builds werden abgelehnt.

```sh
python3 tools/doom/source_package.py \
  --build "$doom_output/runtime" --output "$doom_output/distribution-review"
```

Dieser Prüflauf lehnt veränderte Quellen, Binärdateien oder Archive ab.
Er erzeugt keine Weitergabefreigabe: `redistribution_ready` bleibt `false`.
Die passende Lizenzsammlung der eingebundenen Newlib-Dateien und die
Anwendbarkeit der GCC-Laufzeitausnahme bleiben zu prüfen. Es gibt daraus
keine pauschale Pflicht zur Weitergabe aller Toolchainquellen. Ein Link
auf irgendeinen aktuellen Upstreamstand ersetzt das Quellenpaket nicht.
Auch die WAD-Lizenz und deren Urheberhinweise sind getrennt beizulegen,
wenn Spieldaten weitergegeben werden.

Die Engine ist kein reines GPL-2.0-only-Werk: Die meisten verlinkten
Dateien nennen GPL-2.0-or-later, `sha1.c` nennt GPL-3.0-or-later.
Unser Adapter bleibt AGPL-3.0-or-later. Grundlage und offene Prüfungen:
[die Lizenzmessung](../../docs/messungen/2026-10-15-doom-lizenzen.md).
Das alte BLECH-v8-Paket `SYSTEM-blech-doom-v1.VSB` ist kein aktueller
Gerätekandidat und darf für die aktuelle Integration nicht verwendet werden.

## Verträglichkeit des aktuellen Stands

`test/doom-compatibility.test.mjs` prüft im normalen Start der neuen
Doom-Firmware TAP-Motion, SHIFT+TAP und die Tastenerfassung einer App.
Mit `E2_DOOM_SYSEX_CASES` auf die passende SysEx-Prüfquelle kommen
Protokoll-, Notschalter- und übrige MIDI-Fälle hinzu.
`E2_DOOM_COMPAT_REPORT` benennt die externe JSON-Ergebnisdatei.
Der Lauf setzt `E2_DOOM_REQUIRED=1`, `E2_DOOM_IMAGE`, `E2_FLASH` und
`E2_EMU_PYTHON` voraus. Fehlende echte Haken werden als Fehler behandelt.

Die frühere v8-Datei und das Paket `SYSTEM-blech-doom-v1.VSB` sind
historische Prototypen. Sie enthalten weder den aktuellen Funktionsumfang
noch die neue Speicherbelegung und sind kein aktueller Gerätetest.

Der geprüfte v21-Stand und die gegenüber dem Zwischenstand geänderte
Speicherreserve sind in [Doom auf BLECH v21](../../docs/messungen/2026-10-15-doom-v21.md)
belegt. Code belegt höchstens 4 KiB, Zustand höchstens 5 KiB, gemeinsame
Daten belegen eine 4-KiB-Reserve. SysEx und Preset-Tabellen bleiben
unverändert Teil der vollständig rekonstruierten Basis.
