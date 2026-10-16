<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/banner-dark.svg">
  <img alt="Kuhler's GELUMPE: Grafischer Electribe-Leser und -Modifizierer plus Emulator" src="assets/readme/banner-light.svg" width="100%">
</picture>

[English version](README.en.md)

Ein grafischer Leser und Modifizierer für die Electribe 2 Sampler, dazu ein Emulator und ein
Patcher für die BLECH-Firmware, die "Blechtribe". BLECH läuft entweder auf Hacktribe oder direkt auf
Korgs Original-Firmware des roten Samplers. Für die blaue Electribe 2 mit Firmware 2.02 gibt es
einen eigenen, im Emulator geprüften Synth-Satz mit Theme, Startbild, Spielhilfen,
BLECH-Menü und Plugins. Umfang und Grenzen stehen in der
[Synth-Messung](docs/messungen/2026-10-16-blech-synth.md).

**Wer ich bin:** Kuhler Buhler aka Pascal, Softwareentwickler und Live-Act. Nachdem ich Hacktribe
installiert hatte, ist mir aufgefallen, dass man die MFX- und IFX-Presets bearbeiten kann. Danach war
ich ein paar Monate in einer Entwicklungspsychose, und das hier ist dabei rausgekommen. Mich nervt,
was Korg mit der Electribe 2 gemacht hat (liegen gelassen), mit BLECH hab ich praktisch die Electribe 3
gebaut.

Wenn dir das was bringt: [Spende per PayPal](https://www.paypal.me/kuhlerbuhler).

Ein Editor und Emulator für den Korg Electribe 2 Sampler mit Firmware 2.02, Korgs
Original oder [Hacktribe](https://github.com/bangcorrupt/hacktribe). Er läuft als App oder
im Browser. Mit ihm kannst du

- die Firmware deiner Electribe in einem **Emulator** starten und bedienen, mit Display,
  Tasten, Reglern und LEDs, ohne dass etwas an dein Gerät geht,
- deine `SYSTEM.VSB` **patchen** und als neue Firmware-Datei für die SD-Karte ausgeben
  (BLECH-Patchsatz, Startbild-Editor, zweiter Master-Effekt und mehr),
- **Plugins** schreiben, die auf der Electribe laufen: ein Lauflicht, ein Spiel auf dem
  Display, eine eigene Menüseite,
- Effekte und Patterns in Klartext und echten Einheiten bearbeiten statt in Bytes und per
  Web MIDI ans Gerät schicken.

Bevor Daten gesendet werden, prüfen ein Linter mit Regeln, die am echten Gerät abgeglichen
wurden, und ein simuliertes Gerät, ob die Electribe sie voraussichtlich annimmt. Emulator,
Patcher und Plugins laufen mit Korgs Original 2.02 und mit Hacktribe 2.02. Für die blaue
Electribe 2 mit Original 2.02 ist ein eigener Patch-Satz im Emulator geprüft. Der Effekt-Editor
und das Schreiben ins RAM über MIDI brauchen Hacktribe. Bei anderen Ständen verschieben sich
die Adressen, ein unbekanntes Gerät oder eine unbekannte Firmware-Datei wird deshalb nur
gelesen.

**Es wird keine Firmware mitgeliefert.** Du lädst deine eigene `SYSTEM.VSB`. Die Datei
verlässt deinen Rechner nicht, nichts wird auf einen Server geladen.

## Vorschau

Der Dunkelmodus der App. Der Emulator ist hier ohne Firmware zu sehen, das Display bleibt schwarz.

| | |
|---|---|
| ![Startseite](docs/images/preview/start.png) | ![Patcher mit laufender Prüfung](docs/images/preview/patcher.png) |
| Start | Patcher, die Prüfung im Emulator läuft |
| ![Preset-Editor](docs/images/preview/presets.png) | ![Plugin-Katalog](docs/images/preview/plugin-catalog.png) |
| Preset-Editor | Plugin-Katalog |
| ![Plugin-Editor](docs/images/preview/plugin-editor.png) | ![Emulator](docs/images/preview/emulator.png) |
| Plugin-Editor | Emulator |

## Die App laden

Auf der Releases-Seite dieses Repositories liegt die App für macOS (Apple Silicon, `.dmg`), Windows (`.exe`) und Linux (`.AppImage`, `.deb`). Die App startet den
Emulator-Dienst selbst und beendet ihn beim Schließen. Karte und Flash des Emulators liegen
in `~/.gelumpe`. Beim Start und alle paar Stunden prüft die App, ob es ein neueres Release
gibt, und zeigt dann oben "Neue Version verfügbar". Ein Klick öffnet die Release-Seite.

**Die App ist nicht signiert.** Unter macOS blockiert das System die geladene App. Einmal
freigeben:

```bash
xattr -dr com.apple.quarantine "/Applications/Kuhlers GELUMPE.app"
```

Unter Windows zeigt SmartScreen eine Warnung: "Weitere Informationen", dann "Trotzdem
ausführen".

## Schnellstart aus den Quellen

**Im Browser.** Du brauchst Node.js 20 oder neuer, für den Emulator Python 3.10 oder neuer.

```bash
npm ci
npm run setup:emu   # einmalig: Python-Umgebung mit Unicorn für den Emulator
npm start           # Seite und Emulator zusammen
```

`npm start` zeigt die Adresse an (standardmäßig `http://127.0.0.1:8737/`), die öffnest du im Browser.
Ohne Emulator reicht `npm run serve`, dann entfällt `setup:emu`. Für die Kommunikation mit dem Gerät
brauchst du Chrome oder Edge auf einem Desktopcomputer, die Seite nutzt Web MIDI mit SysEx, das Safari
nicht kann.

**Die App selbst bauen** (Tauri v2). Einmalig: Node 20+, Python 3.10+, Rust über `rustup` und
`cargo install tauri-cli --version "^2" --locked`. Dazu je nach System: unter macOS die Xcode Command
Line Tools, unter Windows die Visual Studio Build Tools mit "Desktop development with C++", unter Linux
`libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev libssl-dev libxdo-dev
patchelf python3-venv`.

```bash
npm ci
npm run app:build -- --bundles dmg            # macOS
npm run app:build -- --bundles nsis           # Windows
npm run app:build -- --bundles appimage,deb   # Linux
```

Der Build baut die Seite, friert den Emulator-Dienst per PyInstaller zu einem Sidecar ein
(`npm run build:sidecar` macht nur das) und packt die App. Das Ergebnis liegt unter
`src-tauri/target/release/bundle/`: `dmg/*.dmg` (macOS), `nsis/*-setup.exe` (Windows),
`appimage/*.AppImage` und `deb/*.deb` (Linux). Gebaut wird auf dem jeweiligen System, quer geht
nicht. Mehr dazu (Intel-Mac, Windows auf ARM): [Entwicklung](docs/development.md).

## Die Firmware patchen

Auf der Seite "Patcher" lädst du deine eigene `SYSTEM.VSB` (Korgs Original 2.02 für Sampler oder Synth, oder Hacktribe 2.02), wählst die
Patches und bekommst eine neue Datei. Der Emulator bootet sie vorher und prüft sie
(Hauptbildschirm, Update-Abfrage, Startmodi, Notschalter). Erst nach bestandener Prüfung gibt die
Seite die Datei frei, das dauert einige Minuten. Die Anleitung zum Aufspielen zeigt die Seite
danach an. Alle Patches, ihr Format und die Grenzen stehen in [docs/patcher.md](docs/patcher.md).
Wer ohne App patchen will, nimmt `BLECH.patch` oder die passende `.bsdiff`-Datei aus dem Release,
ebenfalls dort beschrieben.

Der BLECH-Satz für den Sampler bringt unter anderem: ein eigenes Menü BLECH mit Plugins, Farben für Display und
LEDs, Patternwechsel mit Bestätigung, TAP Motion, den Notenassistenten im KEYBOARD-Modus, einen
Melodie-Generator (SHIFT + PART ERASE), Blechy als Haustier, ein Startbild mit Ladebalken, klare
Meldungen statt "Unknown Error" beim Sample-Laden und Doom (SHIFT + TAP beim Einschalten, Lizenz in
[docs/doom-lizenz.md](docs/doom-lizenz.md)).

So sieht die Electribe mit dem BLECH-Theme aus (im Emulator):

<img alt="Die wichtigsten Bildschirme mit dem BLECH-Theme und alle Zeichen der vier eigenen Schriften" src="assets/blechy/theme-preview.png" width="480">

## Plugins

Ein Plugin gibt der Electribe eine neue Funktion. Du lädst es über die SD-Karte aufs Gerät, in den
Ordner `KORG/blechtribe/Plugin/`. Der Code ist eine Teilmenge von JavaScript, der Editor übersetzt
ihn in Bytecode für eine kleine VM in der Firmware, und ein Fehler schaltet das Plugin ab, ohne die
Electribe zu stören. Sprache, Ereignisse und Funktionen: [docs/plugins.md](docs/plugins.md).
Im Katalog liegen fertige Plugins: Set-Timer, BLECH Clicker, Snake, Tetris, Game of Life, Pong,
Simon und Mandelbrot.

## Der Emulator

Der Emulator führt die echte Firmware als lokaler Dienst aus, die Seite zeigt ein bedienbares
Gerät mit virtueller SD-Karte. Er erzeugt keinen Ton und ersetzt keinen Hörtest, aber du kannst alles
probieren, bevor es ein Gerät sieht. Mehr: [docs/emulator.md](docs/emulator.md). Die
Tastenkombinationen der Firmware stehen in [docs/tastenkombinationen.md](docs/tastenkombinationen.md).

## Sicherheit: bevor du etwas aufs Gerät spielst

Ein falscher Schreibzugriff oder eine fehlerhafte Firmware kann das Gerät hängen lassen. Darum:

- **Notschalter:** EXIT beim Einschalten halten. Dann läuft die Firmware ohne Patches, und über
  DATA UTILITY, SOFTWARE UPDATE lässt sich eine andere Firmware aufspielen. Das gilt nur für diesen
  Start.
- **Sichern, bevor du etwas änderst:** die SD-Karte (Samples, Patterns, die originale `SYSTEM.VSB`)
  und die Global-Einstellungen. Ausschalten und WRITE speichern, was gerade im RAM steht, schalte
  also bei einer Abweichung nicht aus.
- **Zurück:** die gesicherte Original-`SYSTEM.VSB` wieder aufspielen. Wie das geübt wurde, steht in
  [docs/messungen/2026-10-10-rueckweg-geuebt.md](docs/messungen/2026-10-10-rueckweg-geuebt.md).
- **Wenn das Gerät nicht mehr startet:** die Seite "Rettung" im Editor führt durch den dokumentierten
  Weg und sagt bei jedem Schritt, ob er am Gerät gemessen ist. Der Bootloader bleibt tabu, dahinter
  hilft nur JTAG ([docs/rettung.md](docs/rettung.md)).
- **Selbst testen:** die [Gerätetests](docs/geraetetests/README.md) beschreiben, wie du BLECH und die
  Kartenfunktionen an deinem Gerät nachvollziehst, mit Warnung, Voraussetzungen, Sicherung und
  Rückweg.

Der Linter und das simulierte Gerät prüfen bekannte Speicherbereiche, das Nachrichtenformat und
dokumentierte Fehlerfälle. Sie führen keinen ARM- oder DSP-Code aus und erzeugen keinen Ton. Ob etwas
gut klingt, sagt nur das Gehör. Details: [docs/linter.md](docs/linter.md).

## Dokumentation

[docs/README.md](docs/README.md) ist der Index: Plugins, Patcher, Emulator, Gerätekarte, die Messungen
am Gerät, Ideen und Hintergrund. Für die Arbeit am Code: [docs/development.md](docs/development.md).

An diesem Projekt arbeiten auch KI-Agenten mit. Die Regeln für sie stehen in [AGENTS.md](AGENTS.md).

## Mitmachen

Pull Requests gehen gegen `develop`, nicht gegen `main`. Die Regeln stehen in [CONTRIBUTING.md](CONTRIBUTING.md); die
wichtigste: keine Korg-Daten ins Repository, nie. Ein Check schließt einen Pull Request, der welche enthält. Wer etwas
findet, das ein Gerät beschädigen kann, meldet es privat ([SECURITY.md](SECURITY.md)).

## Lizenz

AGPL-3.0, siehe [`LICENSE`](LICENSE). Die Herkunft der Bestandteile steht in [`NOTICE`](NOTICE).
