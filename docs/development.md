# Entwicklung

Bauen, testen, den Emulator und den Patcher benutzen, die App bauen, ein Release
anlegen. Was der Editor tut und wie er prüft, steht in
[architektur.md](architektur.md).

Voraussetzung ist Node.js 20 oder neuer. Kern, Unit-Tests und Server haben keine
Abhängigkeiten. Die Browsertests brauchen Playwright mit dem installierten Chrome, der
Emulator Python 3.10 oder neuer mit Unicorn. Die Desktop-App verwendet auf macOS und Linux
einen nativen MIDI-Dienst. Beim Start mit `npm start` ist Chrome oder Edge auf einem
Desktopcomputer nötig (Web MIDI mit SysEx, Safari kann das nicht). Unter Windows bleibt
die App vorerst bei Web MIDI.

Agenten arbeiten nach [AGENTS.md](../AGENTS.md), dort stehen die harten Regeln des Repos.

## Befehle

```bash
npm start            # Seite und Emulator zusammen, der Link öffnet den Editor verbunden
npm run serve        # nur die Seite unter http://127.0.0.1:8737/
npm run emu          # nur den Emulator-Dienst starten
npm run setup:emu    # einmalig: Python-Umgebung mit Unicorn für den Emulator
npm run build:site   # dist/ für die App erzeugen
npm run build:codemirror   # site/vendor/codemirror.mjs neu bauen, nur nach einer Änderung an tools/codemirror-entry.mjs
npm run build:blech-patch   # BLECH-Patchdateien für ein Release bauen (siehe unten)
npm run verify:patches -- VSB...   # die Kopien des Patchers einmal prüfen, ihre Prüfsummen nach data/patches/verified.json (siehe unten)

npm test             # alle Tests, die ohne Hardware und ohne Korg-Daten laufen
npm run test:e2e     # die Seite in Chrome gegen das simulierte Gerät
npm run test:emu     # Emulator-Tests, brauchen E2_VSB
npm run test:local   # Werksprüfungen mit eigenen Dateien, brauchen E2_VSB und E2_PATTERNS
npm run test:all     # Unit- und Browsertests nebeneinander, mit E2_VSB auch Emulator
```

## Tests

Es liegen nie Korg-Daten im Repo. Alle Testdaten werden gebaut (`test/helpers.mjs`):
`makeImage()` baut ein leeres Firmware-Abbild in Originalgröße mit Records an den echten
Adressen, `makeRecord()` einen FX-Record mit Füllbytes überall, wo nichts verstanden ist,
damit unberührte Bytes auffallen, dazu Backup-Datei und Pattern-Puffer.

| Ebene | Gegen | Befehl |
|---|---|---|
| Einheit, Karte, Umrechnungen, Regeln, Patcher, Plugin-Compiler | gebaute Testdaten | `npm test` |
| Oberfläche bis zum Senden | statische Seite mit Web-MIDI-Ersatz, Playwright | `npm run test:e2e` |
| Emulator, Patches, virtuelle Karte | eigene Firmware (`E2_VSB`) | `npm run test:emu` |
| Werksprüfungen | eigene Dateien (`E2_VSB`, `E2_PATTERNS`) | `npm run test:local` |
| am Gerät | Anleitungen in [geraetetests/](geraetetests/README.md) | von Hand |

Alles außer den letzten drei Zeilen läuft in CI (`.github/workflows/test.yml`): die Einheitstests
in zwei, die Browsertests in vier Teilen nebeneinander (`--test-shard`), die Prüfungen `unit` und
`browser` fassen die Teile zusammen. Ändert ein Pull Request nur Markdown oder andere
Workflows, laufen nur die Einheitstests, die Dokumente lesen, und keine Browsertests (ausgenommen
`DESIGN.md`, `docs/plugins*.md` und `third_party/`, die die Seite und die Tests lesen).

Bei hoher Rechnerlast die Testdateien einzeln und die Python-Läufe begrenzt starten:

```bash
GELUMPE_JOBS=2 node --test --test-concurrency=1 "test/*.test.mjs"
node --test --test-concurrency=1 --test-timeout=180000 "test/e2e/*.e2e.mjs"
```

Die Befehle nacheinander ausführen. `GELUMPE_JOBS` setzt sowohl die Python-Läufe je
Testdatei als auch die Worker eines Emulator-Pools. Mit `1` laufen sie jeweils einzeln;
ohne gültige positive ganze Zahl nutzt der Node-Teststarter die Hälfte der CPU-Kerne,
mindestens zwei.

Eigene Dateien:

```bash
E2_VSB=/pfad/SYSTEM.VSB E2_PATTERNS=/pfad/backup.e2sallpat npm run test:local
```

Ohne die Variablen werden die Tests mit eigenen Dateien in `npm test` übersprungen.
`npm run test:local` schlägt ohne sie fehl, damit ein Kriterium, das sich darauf stützt,
nicht mit null ausgeführten Tests besteht. `npm run test:emu` braucht nur `E2_VSB`; mit
`E2_STOCK_VSB` (Korgs eigene `SYSTEM.VSB` 2.02) laufen auch die Tests für die Original-Firmware, ohne
sie werden diese übersprungen; ebenso `E2_BLUE_VSB` (die blaue Electribe 2) für `test/emulator-blue.test.mjs`. Für
Tests, die auf einem echten Flash-Abbild aufsetzen, gibt es `E2_FLASH`. In CI stellt
`E2_ARM_REQUIRED` sicher, dass die ARM-Prüfungen laufen.

Zwei Dokumentations-Tests halten das Repo sauber: `test/docs.test.mjs` prüft tote
Links, absolute Benutzerpfade, Namen und Gedankenstriche in `README*`, `AGENTS.md` und
`docs/`. `test/map.test.mjs` prüft die Belege der Gerätekarte, auch dass jede Messung,
auf die ein Eintrag zeigt, als Datei in `docs/messungen/` liegt.

### Prozesse und Ordner eines Testlaufs

Nach einem Testlauf bleibt nichts zurück, auch wenn er abgebrochen wird. Die Tests tragen
jeden Kindprozess und jeden temporären Ordner in `test/support/lifetime.mjs` ein und
räumen beides beim Beenden auf, auch bei SIGINT, SIGTERM, SIGHUP und einem Timeout mitten
im Start. SIGKILL fängt Node nicht ab, deshalb beobachtet die Python-Seite ihren
Elternprozess (`tools/emu/lifetime.py`) und endet innerhalb einer Sekunde nach ihm: der
Dienst über `--parent-pid`, Werkzeuge wie `check.py` über `GELUMPE_PARENT_PID`,
Pool-Worker über den Prozess, der den Pool gestartet hat. Der Ordner, den der Dienst
für einen Test selbst anlegt, läuft mit `--ephemeral` und verschwindet dann ebenfalls.
`test/orphans.test.mjs` hält das fest, ohne Firmware und ohne Unicorn.

### Laufzeit der Tests

Ein kompletter Lauf mit eigener Firmware (`test:local`, rund 420 Tests) dauerte früher
20 bis 35 Minuten, ein kalter Lauf heute rund 6, ein warmer Lauf unter einer Minute. Das ist
gemessen auf einem Rechner mit 10 Kernen, ohne Gerätezugriff. Die Maßnahmen:

- **Boot-Snapshot.** Ein Boot der Firmware bis zum Hauptbild kostet rund 2 CPU-Sekunden und
  kam in den Tests immer wieder vor. `Machine.snapshot` und `from_snapshot`
  (`tools/emu/bootcache.py`) halten CPU-Kontext, nicht leere RAM-Seiten und Modellzustand.
  Der Schlüssel besteht aus Firmware, Flash, gehaltenen Tasten, Gerätezeit und dem Quelltext
  des Emulators. Wiederherstellen kostet 0,06 s statt 2,1 s, das Verhalten ist bit-identisch
  (`test_snapshot.py` vergleicht CPU, die 128 MB RAM, Flash, Tabellen und Display mit einem
  durchgelaufenen Gerät). Mit Karte im Schlitz gibt es keinen Snapshot.
- **Nebeneinander.** `tools/emu/parallel.py` verteilt unabhängige Boots auf Prozesse.
  Standard: Kerne minus einer (mindestens 1), 2 bei einem Lastmittel über der Kernzahl, 1
  bei über der doppelten Kernzahl. `GELUMPE_JOBS` überschreibt das, im eingefrorenen Dienst
  läuft ein Prozess. Die Emulator-Tests starten ihre Python-Läufe über
  `test/support/spawn.mjs`, ohne den Event-Loop zu blockieren.
- **Gemerkte Ergebnisse.** `check.py`, `mfx_cases.py` und `splash_cases.py` merken sich ihr
  Ergebnis je Eingabedateien und Emulator-Quelltext. **Das ändert, was ein grüner Lauf
  bedeutet:** bei unveränderten Dateien und Quelltext wird die Antwort des letzten echten
  Laufs wiederverwendet. Jede Änderung an einer `.py`-Datei in `tools/emu` oder `tools/patch`
  macht den Schlüssel ungültig. Die Dateien liegen in `~/.cache/gelumpe`
  (`GELUMPE_CACHE_DIR`), sie enthalten Firmware-RAM und nie im Repo. `GELUMPE_CACHE=off`
  lässt alles frisch laufen.
- **Dienst ohne Echtzeit-Bremse** nur für Tests (`server.py --unthrottled`). Die Tests warten
  in Gerätezeit statt in Wanduhrzeit (`settle(ms)` in `test/support/emu.mjs`).
- **Browsertests** laufen als je drei dünne Dateien um dieselbe Suite nebeneinander.

| Lauf (niedrige Last) | vorher | nachher |
|---|---|---|
| `npm run test:local` | 1329 s | 344 s kalt, 37 s warm |
| `npm test` ohne Firmware | 56 s | 22 s |
| `npm run test:e2e` | 142 s | 31 s |

Der kalte Lauf bleibt bei etwa 6 Minuten. Flaschenhälse sind dann die Kette der
Startbild-Fälle (30 Schritte) und die Startwege in `check.py` (Probe-Haken auf jedem
Lesezugriff).

## Emulator

Der optionale ARM-Emulator ist ein eigenes Python-Werkzeug (`tools/emu/`, GPL-2.0, siehe
[NOTICE](../NOTICE)). Installation, Dienst, Karte und Flash stehen in
[emulator.md](emulator.md).

## Patcher

Der Patcher baut aus Patch-Dateien eine geänderte SYSTEM.VSB. Format, Haken, Prüfungen und
Notschalter stehen in [patcher.md](patcher.md). Von der Befehlszeile:

```bash
node tools/patch/apply.mjs --vsb SYSTEM.VSB --patch BLECH.patch --out BLECH.VSB
```

## Werkzeuge nach Ordner

| Ordner | Inhalt |
|---|---|
| `bin/` | Befehlszeile `e2` ([linter.md](linter.md)) |
| `src/` | Kern: Karte, Pattern, Protokoll, Planer, Sender, Sitzung, Linter, Simulation, Patcher; läuft im Browser (außer `node.mjs`) |
| `data/` | Karte (`map/`), Befunde, Gerätefreigabe, Patches, Plugin-Vertrag |
| `site/` | die Seite (`app/`), das Design (`design/`), der gebaute Editor CodeMirror (`vendor/`, [NOTICE](../NOTICE)) |
| `tools/emu/` | Emulator: Maschine, Dienst, virtuelle SD, Prüfläufe |
| `tools/patch/` | Patches (ARM-Code, Haken, Plugin-VM) und ihre Python-Tests |
| `tools/device/` | Werkzeuge am echten Gerät: Flash lesen, LEDs, Bildschirm, FatFs-Sonde |
| `tools/set/` | Befehlszeile für den Übergangs-Generator (`src/transition.mjs`) und die Auswertung von Pattern-Sets ([set/uebergaenge.md](set/uebergaenge.md)) |
| `tools/release*.mjs`, `tools/set-version.mjs` | Release |
| `tools/alsa-sysex.*` | Linux-Sender für große SysEx-Nachrichten ([alsa-sysex.md](../tools/alsa-sysex.md)) |
| `src-tauri/` | die Desktop-App |
| `assets/` | App-Icon, BLECH-Startbild und -Klänge ([README](../assets/blechy/README.md)) |

Browser-Regel: alles in `src/` außer `node.mjs` läuft im Browser. Keine `node:`-Importe
außerhalb von `src/node.mjs`, `bin/`, `tools/` und `test/`.

## Die App

Eine Desktop-App (Tauri v2) um dieselbe Seite. Sie startet den Emulator-Dienst selbst
(freier Port, frischer Token) und beendet ihn beim Schließen. Karte und Flash bleiben in
`~/.gelumpe`. Gebaut wird für macOS (Apple Silicon und Intel), Windows x64 und Linux x64.

Aus den Quellen: einmal `npm run setup:emu` und `cargo install tauri-cli --version "^2" --locked`,
dann `npm run app:dev` (nimmt das Python der venv, kein gebautes Sidecar nötig). Läuft schon ein
Emulator auf `~/.gelumpe/sd`, weigert sich der zweite.

**Bauen** auf dem eigenen Rechner: `npm run app:build -- --bundles <Format>`. Das baut die Seite,
friert den Dienst per PyInstaller zu einem Sidecar ein (`npm run build:sidecar` allein geht auch)
und packt die App nach `src-tauri/target/release/bundle/`. PyInstaller kann nicht quer bauen: jedes
Ziel wird auf seinem eigenen System gebaut, mit der Version aus `npm run release -- prepare`.

Einmalig überall: Node 20+, Rust (`rustup`), `cargo install tauri-cli --version "^2" --locked`,
Python 3.10+ (die venv und PyInstaller legt der Build selbst an).

| System | Zusätzlich einmalig | Befehl | Datei |
|---|---|---|---|
| macOS Apple Silicon | Xcode Command Line Tools | `npm run app:build -- --bundles dmg` | `bundle/dmg/*_aarch64.dmg` |
| macOS Intel (auf Apple Silicon) | siehe unten | `GELUMPE_X64_PYTHON=<x86_64-python> npm run app:build -- --target x86_64-apple-darwin --bundles dmg` | `target/x86_64-apple-darwin/release/bundle/dmg/*_x64.dmg` |
| Windows x64 | siehe unten | `npm run app:build -- --bundles nsis` | `bundle/nsis/*_x64-setup.exe` |
| Linux x64 | `sudo apt install libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev libssl-dev libxdo-dev patchelf python3-venv libasound2-dev` | `npm run app:build -- --bundles appimage,deb` | `bundle/appimage/*.AppImage`, `bundle/deb/*.deb` |

Pfade ab `src-tauri/target/release/`, außer wo `target/<Triple>/` steht. Die fertigen Dateien
kommen alle in den Ordner `dist-release/` im Repo auf dem Rechner, der das Release anlegt (in
`.gitignore`), von den anderen Systemen per Kopie.

Auf GitHub baut der Workflow "Build apps" (von Hand starten, mit der Version) Windows, Linux und,
wenn angehakt, macOS Apple Silicon und Intel (Runner `macos-15-intel`) gleichzeitig, daneben laufen `cargo test` und `cargo clippy` je
System. Die Dateien liegen danach als Artefakte am Lauf; schlägt ein Build oder ein Test fehl, löscht der
letzte Job sie wieder, damit aus einem roten Lauf nichts veröffentlicht wird. Rust-Abhängigkeiten und das eingefrorene
Sidecar kommen aus dem Cache von GitHub, solange sich ihre Quellen nicht geändert haben; ein Cache, der
sieben Tage nicht benutzt wurde, ist weg, dann dauert der nächste Lauf länger.

Für MIDI braucht das Linux-Paket zur Laufzeit ALSA (`libasound.so.2`, auf Debian und Ubuntu
das Paket `libasound2` beziehungsweise `libasound2t64`). Das deb-Paket nennt die Abhängigkeit;
beim AppImage muss sie auf dem Rechner vorhanden sein.

Die nativen MIDI-Tests laufen ohne Gerät und ohne Korg-Daten:

```bash
npm run build:site
npm run build:sidecar
cargo test --manifest-path src-tauri/Cargo.toml
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
```

Die gesonderte Prüfung mit virtuellen MIDI-Ports wird ausdrücklich gestartet:

```bash
cargo test --manifest-path src-tauri/Cargo.toml --lib midi::backend::tests::virtual_ports -- --ignored --nocapture
cargo run --manifest-path src-tauri/Cargo.toml --example midi-smoke
```

Das Beispiel startet eine verborgene echte WebKit-Ansicht mit dem gebauten Editor und
prüft den Adapter, die Tauri-Aufrufe, den Rückkanal und eigene virtuelle Ports zusammen.
Es gehört nicht zur ausgelieferten Oberfläche. Beide Prüfungen verwenden
nur eigens erzeugte Testports, keine angeschlossene Electribe. Native Prüfungen unter Windows
ersetzen keinen Funktionstest; die native Anbindung bleibt dort bis zur Abnahme ausgeschaltet.

Vor einer Freigabe werden die installierten Pakete getrennt geprüft: macOS auf Apple Silicon
und Intel, Linux als deb und AppImage sowie Windows. Zu jedem Ergebnis gehören System,
Paketarchitektur, Senden, Empfangen, Trennen und Neuverbinden über eigene Testports. Ein
Compilerlauf ist kein Nachweis für ein gestartetes Paket.

Ein nativer Funktionstest unter Windows braucht einen vorher eingerichteten Loopback-Provider
mit ausdrücklich benannten virtuellen Ports. Provider, Version und Einrichtung gehören ins
Prüfprotokoll. Diese Testvoraussetzung wird nicht mit der App ausgeliefert. Ohne diesen Nachweis
bleibt die native Windows-Anbindung ausgeschaltet.

**macOS Intel** baut ein Apple-Silicon-Mac unter Rosetta: `rustup target add x86_64-apple-darwin`
und ein x86_64-Python 3.10+ (zum Beispiel `uv python install cpython-3.12-macos-x86_64`, Pfad mit
`uv python find cpython-3.12-macos-x86_64`). Das Sidecar wird mit diesem Python in einer eigenen
venv (`tools/emu/.venv-x64`) eingefroren und unter Rosetta ausgeführt.

**Windows in einer VM auf Apple Silicon** (nicht getestet): die VM ist ARM, die App soll x64
werden und läuft dort emuliert. Alles x64 installieren: Node, Python (python.org "Windows installer
(64-bit)"), Visual Studio Build Tools mit "Desktop development with C++" und den x64-Tools, Rust mit
`rustup default stable-x86_64-pc-windows-msvc`. WebView2 ist in Windows 11 dabei, NSIS lädt Tauri
selbst. Die `-setup.exe` enthält den Offline-Installer von WebView2 (`webviewInstallMode` in
`src-tauri/tauri.conf.json`, etwa 130 MB mehr): ohne ihn blieb das Fenster unter Windows 10 ohne
WebView2 weiß, wenn das Nachladen beim Installieren scheiterte. Bleibt der Rust-Host ARM, `--target x86_64-pc-windows-msvc` anhängen, die Datei liegt dann
unter `target/x86_64-pc-windows-msvc/release/bundle/nsis/`.

Die App prüft beim Start und alle paar Stunden das neueste Release und zeigt oben "Neue Version
verfügbar", ein Klick öffnet die Release-Seite. Solange das Repo nicht öffentlich ist, bleibt der
Knopf weg. Ein Selbst-Update bräuchte den Tauri-Updater mit eigenem Signaturschlüssel.

## Release

**Der normale Weg läuft in GitHub** (Workflow "Release", `.github/workflows/release.yml`):

1. Auf `develop` per Pull Request: `node tools/set-version.mjs X.Y.Z` (schreibt die vier Versionsdateien) und die
   Notizen als `release-notes/X.Y.Z.md`. Sie sind das, was im Release und im Discord steht.
2. Pull Request `develop` -> `main` mergen.
3. Der Merge startet den Workflow. Steht in `package.json` eine Version ohne Tag und gibt es ihre Notizen, baut er die
   Apps auf allen Systemen (`build-apps.yml`), prüft den BLECH-Satz im Emulator auf Hacktribes, Korgs roter und blauer
   2.02 (`npm run verify:patches`, je ein Job), baut `BLECH.patch` und die `.bsdiff`, veröffentlicht das Release mit
   `tools/release.mjs --ci` (älteres Release gelöscht, Tags bleiben) und postet es im Discord. Jeder andere Push auf
   `main` endet nach dem ersten Schritt.

Korgs drei 2.02 kommen nie ins Repo. Der Workflow lädt sie über die Links in den Secrets `E2_VSB_URL` (Hacktribe),
`E2_VSB_STOCK_URL` (rot) und `E2_VSB_SYNTH_URL` (blau) und bricht ab, wenn eine Datei nicht die erwartete SHA-256 hat.
Fehlt in `data/patches/verified.json` das Paar einer der drei, warnt der Lauf: die App prüft diese Datei dann vor dem
Patchen selbst im Emulator.

**Von Hand** geht es weiter so, etwa wenn GitHubs Runner ausfallen:

`npm run release` (`tools/release.mjs`). Auf jedem System vor dem Bauen setzt
`npm run release -- prepare` (oder `node tools/set-version.mjs <Version>` mit der Version vom
Release-Rechner) die nächste Version in `package.json`, `tauri.conf.json`, `Cargo.toml` und
`Cargo.lock`: erste Version 1.0.0, danach der letzte Tag `vX.Y.Z` mit Patch plus eins, `--minor` oder
`--major` hebt stattdessen den Teil (bei `prepare` und beim Release gleich angeben). `prepare`
verlangt, dass `HEAD` auf `origin/develop` steht, und committet nichts.

Wenn alle fünf Dateien (zwei `.dmg` für Apple Silicon und Intel, Setup-`.exe`, `.AppImage`, `.deb`) in `dist-release/` liegen:

```bash
npm run release              # Trockenlauf: prüft alles, zeigt die Schritte
npm run release -- --yes     # wirklich
```

Mit `--yes` passiert der Reihe nach: Version in die Dateien schreiben, die vier Dateien als "Release
vX.Y.Z" committen (nur diese), den Commit nach `origin/develop` pushen, das Release anlegen (der Tag liegt
auf diesem Commit, das Release wird als neuestes markiert) mit den fünf Dateien, dann alle älteren
Releases samt Dateien löschen, die Tags bleiben. Steht die Version schon in `HEAD`, entfallen Commit und
Push. Nur das neueste Release liegt also auf GitHub.

`main` ist geschützt, deshalb geht der Versions-Commit nach `develop` und erreicht `main` mit dem einen
Pull Request `develop` -> `main`, den du danach öffnest (`gh pr create --base main --head develop`). Ein
eigener Bump-PR ist nicht nötig. Der Workflow "Sync develop" holt den Merge-Commit danach nach `develop`
zurück.

`--notes=Datei.md` nimmt die Release-Notizen aus der Datei statt GitHubs erzeugter Liste der PRs. Sobald
das Release veröffentlicht ist, postet der Workflow "Discord release" es über den Webhook im Secret
`DISCORD_WEBHOOK` (`tools/discord-release.mjs`): Titel "BLECHTRIBE X.Y.Z ist da" mit Link, darunter die
Notizen, lange in mehreren Nachrichten, zum Schluss eine Nachricht nur mit dem Link zum Release. Notizen erst danach geändert: den Workflow von Hand mit dem Tag
starten, er postet das Release noch einmal.

Geprüft wird vorher: alle fünf Ziele da, genau eine Datei je Ziel, alle mit der fälligen Version, `gh`
angemeldet, das Release gibt es noch nicht, `HEAD` ist `origin/develop`. Scheitert der Push, liegt der
Commit lokal: beheben und `git push origin HEAD:develop`, dann `npm run release -- --yes` erneut, es läuft
nur noch das Release.

**BLECH-Patch zum Release** (optional): `E2_VSB=<SYSTEM.VSB aus Hacktribes Paket> npm run
build:blech-patch` baut zwei Dateien nach `dist-release/`. `BLECH.patch` ist der ganze Patch-Satz im
eigenen Format (`node tools/patch/apply.mjs --vsb SYSTEM.VSB --patch BLECH.patch --out BLECH.VSB`) und
passt auf jede Hacktribe 2.02 mit unverändertem Code, auch mit eigenen FX-Presets, Menülängen oder
Startbild. `BLECH-for-7cb4825c.bsdiff` (`bspatch SYSTEM.VSB BLECH.VSB BLECH-for-7cb4825c.bsdiff`, ohne die
App) passt nur auf genau die Hacktribe-Datei mit diesem sha256-Anfang. Liegen sie im Ordner, lädt
`npm run release` sie mit hoch, `BLECH.patch` muss für die fällige Version gebaut sein
(`-- --version X.Y.Z`). Beide enthalten keine Firmware, nur eigenen Code und Prüfsummen. Format, Beleg
und Grenzen: [patcher.md](patcher.md), "Patch-Datei und bsdiff".

**Geprüfte Kopien** (vor jedem Release mit geändertem Patch-Satz): `npm run verify:patches -- <Korgs rote 2.02>
<Korgs blaue 2.02> <Hacktribe 2.02>` patcht jede Datei wie die Seite, lässt `tools/emu/check.py` laufen und schreibt die
SHA-256 von Eingabe und Ergebnis nach `data/patches/verified.json`, nur wenn alle bestehen. Der Patcher überspringt die
Prüfung im Emulator für genau diese Kopien, auf langsamen Rechnern dauert sie über eine Stunde. Jede andere Datei wird
weiter ganz geprüft; eine Liste von einem alten Patch-Satz trifft nichts mehr und kostet nur die Zeit.

## Keine öffentliche Seite

Der Editor wird nur als App verteilt. Es gibt bewusst keinen Workflow, der die Seite auf GitHub Pages
veröffentlicht, und es soll auch keinen geben.
