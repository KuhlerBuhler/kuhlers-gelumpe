[English version](README.en.md)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/banner-dark.svg">
  <img alt="Kuhler's GELUMPE: Grafischer Electribe-Leser und -Modifizierer plus Emulator" src="assets/readme/banner-light.svg" width="100%">
</picture>

<h3 align="center">BLECHTRIBE: neue Firmware für deine Electribe 2. Kostenlos.</h3>

<p align="center">
  <a href="https://github.com/KuhlerBuhler/kuhlers-gelumpe/releases/latest"><img alt="App herunterladen" src="https://img.shields.io/badge/%E2%AC%87%20App%20herunterladen-Mac%20%7C%20Windows%20%7C%20Linux-2d6579?style=for-the-badge" height="56"></a>
</p>

<p align="center">Du musst hier nichts suchen und keinen Code anfassen. Klick auf den Knopf, lade die App für deinen Rechner, fertig.</p>

## Inhalt

- [Häufige Fragen](#häufige-fragen)
- [So kommt BLECHTRIBE auf deine Electribe](#so-kommt-blechtribe-auf-deine-electribe)
- [Was kann was?](#was-kann-was)
- [Vorher und nachher](#vorher-und-nachher)
- [Die Firmware patchen](#die-firmware-patchen)
- [Die App laden](#die-app-laden)
- [Plugins](#plugins)
- [Der Emulator](#der-emulator)
- [Sicherheit](#sicherheit-bevor-du-etwas-aufs-gerät-spielst)
- [Mitmachen](#mitmachen)

## Häufige Fragen

- **Kostet das was?** Nein. Wenn du magst, freu ich mich über eine [Spende](https://www.paypal.me/kuhlerbuhler).
- **Ist das sicher?** Die App prüft die neue Firmware zuerst im Emulator. Das fängt viele Fehler ab, garantiert aber nicht das Verhalten jedes echten Geräts. Sichere vorher deine Original-Firmware und deine Daten.
  Der Notschalter: **EXIT beim Einschalten halten**, dann startet die Electribe ohne BLECHTRIBE, und du spielst dein Original wieder auf.
- **Brauch ich einen PC?** Ja, einmal zum Umbauen der Datei. Danach nicht mehr.
- **Sind Samples dabei?** Nein. BLECHTRIBE bringt keine Samples mit, deine eigenen Samples bleiben erhalten. Beim ersten Start bietet die Electribe an, deinen Sample-Ordner zu übernehmen.
- **Geht das mit der blauen Electribe?** Ja, mit etwas weniger Funktionen, siehe Tabelle.
- **Hab ich mit BLECHTRIBE noch Hacktribe?** Ja, wenn du eine Hacktribe-Datei reinziehst. BLECHTRIBE kommt dann obendrauf. Auf Korgs Original schaltet es die Hacktribe-Funktionen nicht frei.
- **Wie kann ich eigene Effekte machen?** In der App im **Baukasten**. Da nimmst du einen fertigen Effekt oder baust einen aus Bausteinen, mit Namen und echten Einheiten. Über den Export kommen sie auf die SD-Karte, einzelne auch live per USB. Das geht auf der roten Electribe mit BLECHTRIBE.
- **Windows: Die App findet meine Electribe nicht, obwohl die MIDI-Ports da sind.** Dann ist wohl Korgs eigener USB-MIDI-Treiber drauf, über den kommen die Antworten der Electribe nicht an. Nimm ihn im Geräte-Manager raus (die Electribe, "Gerät deinstallieren", mit Treiber) und starte Windows neu, Windows' eigener Treiber reicht. Will das KORG Driver Setup Utility ihn danach wieder installieren, mach es einfach zu. Der MIDI-Bericht in den Einstellungen sagt das auch.
- **Ich hab eine Idee für die App oder die Firmware.** Immer her damit: [Idee aufschreiben](https://github.com/KuhlerBuhler/kuhlers-gelumpe/issues/new?template=idea.yml). Dafür brauchst du ein GitHub-Konto.

## So kommt BLECHTRIBE auf deine Electribe

Du brauchst einen Rechner (Mac, Windows oder Linux) und einen SD-Kartenleser. Einmal, für ein paar Minuten.

1. **App laden** über den Knopf oben. Auf der Seite ganz unten bei "Assets": `.dmg` für Mac, `.exe` für Windows.
   Auf dem Mac blockiert das System die App beim ersten Öffnen, weil sie nicht von Apple signiert ist. Wie du sie freigibst, steht unter [Die App laden](#die-app-laden).
2. **SD-Karte** aus der Electribe in den Rechner stecken.
3. **App öffnen**, links auf **Firmware Patcher**, dann die Datei `SYSTEM.VSB` von deiner Karte reinziehen.
   Du findest sie im Ordner `KORG/electribe sampler/System/` (Original) oder `KORG/hacktribe/System/` (Hacktribe) oder `KORG/electribe/System/` (blaue Electribe).
4. **Warten**, bis die App fertig geprüft hat (ein paar Minuten), dann die neue Datei speichern.
   Die App sagt dir, wohin sie auf der Karte muss.
5. **Karte zurück in die Electribe**, einschalten und am Gerät das Update starten. Die App zeigt dir die Tasten dazu.

Klappt etwas nicht? Die App sagt dir, was los ist. Wenn du trotzdem nicht weiterkommst, schreib mir, mit einem Foto der Meldung.

## Was kann was?

| | Sampler (rot) Original | Synth (blau) Original | Sampler mit Hacktribe | **BLECHTRIBE** rot | **BLECHTRIBE** blau | **BLECHTRIBE** mit Hacktribe |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Eigene Samples aufnehmen und laden | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ |
| Erweiterte Hacktribe-Oszillatorbank (Dual, Oct, Chip, ...) | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| Zusätzliche Hacktribe-MFX, IFX, Grooves und Skalen | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| FX und Grooves über die Hacktribe-Menüs importieren/exportieren | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| Eigenes INIT-Pattern über Hacktribe | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| Hacktribe-MIDI-Erweiterungen | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| Unveränderte Werks-Samplebank der roten Electribe nutzen | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Anpassbare Oberfläche (Startbild, Schrift, Ausschaltbild) | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Ladeanimation mit Fortschritt | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ |
| Startbild selbst malen | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ |
| Synth-Filter (MS20, Acid, ...) | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Effekte frei bearbeiten (App) | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ |
| 128 Plätze für eigene Effekte | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ |
| Zweiter Master-Effekt (MFX 2) | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Plugins und Spiele (Snake, Tetris, ...) | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Pad-Farben und LED-Farben | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Patternwechsel erst nach Bestätigung | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Sync-Gruppen (Patterns spielen wie eins) | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Schnell speichern (EXIT + WRITE), Part zurücksetzen (EXIT + Pad) | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Akkorde in Pink | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| TAP Motion | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Notenassistent | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Würfeln (Zufallsmelodie) | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Klare Meldung bei kaputten Samples | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ |
| Doom | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ |
| Update über USB aus der App | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ |

Hacktribe ist eine eigene Firmwarebasis. BLECHTRIBE ergänzt sie; es schaltet diese
Hacktribe-Funktionen auf einem Korg-Original nicht automatisch frei. Die blaue BLECHTRIBE-Spalte
meint den Synth-Satz auf Korg 2.02. Hacktribe selbst unterstützt laut Projekt beide Hardwaretypen.

**Was du bei Hacktribe abwägen musst:**

| Nachteil | Was das für dich heißt |
|---|---|
| Die Werks-Samplebank wird durch Oszillatoren ersetzt | Die eigenen Samples liegen auf 501 bis 999. Werks-Samples müssen für Hacktribe umgewandelt und in die eigene Bank geladen werden. |
| Alte Patterns können anders klingen | Oszillator- und Effektzuordnungen ändern sich. Nach dem Umstieg die eigenen Patterns durchhören und bei Bedarf neu zuordnen. |
| Zusätzlicher Firmwarewechsel | Wer Korgs Original nutzt, braucht zuerst eine passende Hacktribe-Datei. BLECHTRIBE kann auch direkt auf dem Original bleiben. |

Funktionen und Umstieg: [Hacktribe](https://github.com/bangcorrupt/hacktribe),
[Oszillatorbank](https://github.com/bangcorrupt/hacktribe/wiki/Features#oscillators),
[Werks-Samples](https://github.com/bangcorrupt/hacktribe/wiki/How-To#factory-samples) und
[FAQ](https://github.com/bangcorrupt/hacktribe/wiki/FAQ).

## Vorher und nachher

Links die normale Electribe, rechts mit BLECHTRIBE. Die Animationen verwenden die eigenen
Firmwaregrafiken; der Ladeabschluss bleibt hier länger sichtbar. Das normale Ausschalten ist
schematisch mit unserer eigenen Schrift dargestellt.

| Normal | BLECHTRIBE |
|:-:|:-:|
| ![Normales Startbild](docs/images/readme/start-hacktribe.png) | ![BLECHTRIBE beim Starten](docs/images/readme/blechtribe-start.gif) |
| ![Normaler Hauptbildschirm](docs/images/readme/haupt-hacktribe.png) | ![BLECHTRIBE Hauptbildschirm](docs/images/readme/haupt-blechtribe.png) |
| ![Normales Menü](docs/images/readme/menu-hacktribe.png) | ![BLECHTRIBE Menü](docs/images/readme/menu-blechtribe.png) |
| ![Normales Ausschalten, schematisch](docs/images/readme/ausschalten-normal.svg) | ![BLECHTRIBE beim Ausschalten](docs/images/readme/blechtribe-aus.gif) |

---

## Die Firmware patchen

Auf der Seite "Firmware Patcher" ziehst du deine eigene `SYSTEM.VSB` rein (Korgs Original 2.02 für Sampler oder
Synth, oder Hacktribe 2.02), wählst die Patches aus und bekommst eine neue Datei. Bevor du die
runterladen kannst, bootet der Emulator sie und prüft, ob alles läuft: Hauptbildschirm, Update-Abfrage,
Startmodi, Notschalter. Das dauert ein paar Minuten, du siehst dabei, welche Gruppe gerade dran ist.
Danach zeigt dir die Seite, wie du die Datei aufs Gerät bekommst. Alle Patches und ihre Grenzen stehen in
[docs/patcher.md](docs/patcher.md). Wer ohne App patchen will, nimmt `BLECH.patch` oder die passende
`.bsdiff`-Datei aus dem Release, das steht da auch.

Was BLECH auf dem Sampler so mitbringt: ein eigenes Menü BLECH mit Plugins, Farben für Display und
LEDs, Patternwechsel erst nach Bestätigung, Sync-Gruppen, TAP Motion, den Notenassistenten im KEYBOARD-Modus, einen
Melodie-Generator (SHIFT + PART ERASE), EXIT + WRITE zum Speichern (die WRITE-LED atmet, solange etwas ungespeichert ist), EXIT + Pad setzt den Klang eines Parts
zurück, Akkord-Steps von Poly-Parts in Pink, beim ersten Start die Übernahme deines
hacktribe- oder electribe-sampler-Ordners, Blechy als kleines Haustier, ein Startbild mit Ladebalken,
verständliche Meldungen statt "Unknown Error" beim Sample-Laden und Doom (SHIFT + TAP beim Einschalten,
zur Lizenz siehe [docs/doom-lizenz.md](docs/doom-lizenz.md)).

## Für Bastler

GELUMPE ist das Programm dahinter: deine Electribe 2 auslesen und umbauen, mit einem Emulator (eine Electribe im Rechner) und dem Patcher für BLECHTRIBE. Was auf der blauen Electribe genau geht, steht in der
[Synth-Messung](docs/messungen/2026-10-16-blech-synth.md).

## Wer ich bin

Ich bin Kuhler Buhler, aka Pascal, arbeite als Softwareentwickler und bin ein Live Act. Als ich Hacktribe installiert hab,
ist mir aufgefallen, dass man die MFX- und IFX-Presets ja selbst bearbeiten kann. Tja, und dann war ich
ein paar Monate in einer Entwicklungspsychose, und das hier ist dabei rausgekommen.

Warum das Ganze? Mich nervt, was Korg aus der Electribe 2 gemacht hat, nämlich nix. Da ist so viel mehr
drin, als Korg jemals rausgeholt hat. Mit BLECH hab ich mir praktisch die Electribe 3 gebaut, die es
nie gab.

Wenn dir das was bringt, freu ich mich über eine [Spende per PayPal](https://www.paypal.me/kuhlerbuhler).

## Was du damit machen kannst

GELUMPE läuft als App oder im Browser und funktioniert mit der Electribe 2 mit Firmware 2.02, dem
roten Sampler (Korgs Original oder [Hacktribe](https://github.com/bangcorrupt/hacktribe)) und der
blauen Synth (Korgs Original). Du kannst

- die Firmware deiner Electribe im **Emulator** starten und bedienen, mit Display, Tasten, Reglern
  und LEDs, ohne dass irgendwas an dein Gerät geht,
- deine `SYSTEM.VSB` **patchen** und daraus eine neue Firmware-Datei für die SD-Karte machen
  (BLECH, eigenes Startbild, zweiter Master-Effekt und einiges mehr),
- **Plugins** schreiben, die direkt auf der Electribe laufen, zum Beispiel ein Lauflicht, ein Spiel
  auf dem Display oder eine eigene Menüseite, oder fertige aus dem Katalog nehmen. Sie liegen auf der
  Karte im Ordner `KORG/blechtribe/Plugin/` (Einzahl, nicht "Plugins"), bei der roten wie bei der blauen
  Electribe. Mit verbundenem Gerät schickt sie der Knopf "Aufs Gerät" per USB dorthin,
- im **Baukasten** eigene Effekte und Modulationen bauen, mit echten Einheiten statt Bytes, und sie
  als `.e2fx`-Datei weitergeben oder als eine Datei für die Karte exportieren. Eine `.e2fx` öffnest du
  unter BLECHTRIBE -> Baukasten -> Meine Effekte -> ".e2fx-Datei öffnen", mit geladener Firmware auch unter
  BLECHTRIBE -> Presets -> "Preset-Datei laden",
- Patterns bearbeiten und per Web MIDI ans Gerät schicken.

Bevor irgendwas ans Gerät geht, schauen ein Linter mit Regeln, die ich am echten Gerät abgeglichen hab,
und der Emulator drüber, ob die Electribe das voraussichtlich schluckt. Emulator, Patcher und Plugins
laufen mit Korgs Original 2.02 und mit Hacktribe 2.02. Der Effekt-Editor und das Schreiben ins RAM über MIDI brauchen auf dem roten Sampler
Hacktribe oder BLECHTRIBE mit seinen eigenen USB-Befehlen. Bei anderen Firmware-Ständen liegen die Adressen woanders, deshalb wird
ein unbekanntes Gerät oder eine unbekannte Datei nur gelesen und nie beschrieben.

**Firmware ist nicht dabei.** Du lädst deine eigene `SYSTEM.VSB`, und die bleibt auf deinem Rechner.
Nichts davon landet auf irgendeinem Server.

## Vorschau

Die App im Dunkelmodus. Der Emulator ist hier ohne Firmware zu sehen, das Display bleibt schwarz.

| | |
|---|---|
| ![Startseite](docs/images/preview/start.png) | ![Patcher mit laufender Prüfung](docs/images/preview/patcher.png) |
| Start | Patcher |
| ![Startbildschirm](docs/images/preview/splash.png) | ![Plugin-Katalog](docs/images/preview/plugin-catalog.png) |
| Startbildschirm selbst malen | Plugin-Katalog |
| ![Plugin-Editor](docs/images/preview/plugin-editor.png) | ![Emulator](docs/images/preview/emulator.png) |
| Plugin-Editor | Emulator |

## Die App laden

Auf der Releases-Seite dieses Repositories liegt die App für macOS (Apple Silicon und Intel, je eine `.dmg`), Windows (`.exe`) und Linux (`.AppImage`, `.deb`). Die App startet den
Emulator-Dienst selbst und beendet ihn beim Schließen. Karte und Flash des Emulators liegen
in `~/.gelumpe`. Beim Start und alle paar Stunden prüft die App, ob es ein neueres Release
gibt, und zeigt dann oben "Neue Version verfügbar". Ein Klick lädt die passende Datei in den Downloads-Ordner und startet die Installation (klappt das nicht, öffnet sich die Release-Seite).

**Die App ist nicht signiert.** Unter macOS blockiert das System die geladene App. Einmal
freigeben:

```bash
xattr -dr com.apple.quarantine "/Applications/Kuhlers GELUMPE.app"
```

Unter Windows zeigt SmartScreen eine Warnung: "Weitere Informationen", dann "Trotzdem
ausführen". Die `-setup.exe` bringt WebView2 mit und installiert es, wenn es fehlt (etwa unter
Windows 10), auch ohne Internet.

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

Die Desktop-App spricht auf macOS und Linux nativ mit den MIDI-Ports. Dafür braucht sie
keinen zusätzlichen Browser und keinen separat installierten MIDI-Helfer. Unter Windows
bleibt die App vorerst bei Web MIDI.

**Die App selbst bauen** (Tauri v2). Einmalig: Node 20+, Python 3.10+, Rust über `rustup` und
`cargo install tauri-cli --version "^2" --locked`. Dazu je nach System: unter macOS die Xcode Command
Line Tools, unter Windows die Visual Studio Build Tools mit "Desktop development with C++", unter Linux
`libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev libssl-dev libxdo-dev
patchelf python3-venv libasound2-dev`.

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

## Plugins

Mit einem Plugin bringst du der Electribe was Neues bei. Es kommt über die SD-Karte in den Ordner
`KORG/blechtribe/Plugin/`. Der Ordner heißt `Plugin`, Einzahl, nicht "Plugins", und er ist bei der roten
und der blauen Electribe derselbe. Die Firmware legt ihn nicht selbst an, du erstellst ihn. Ist das Gerät
verbunden, geht es auch ohne Karte: im Bereich Plugins schreibt der Knopf "Aufs Gerät" das Plugin per USB
dorthin, danach am Gerät Menü -> BLECH -> PLUGINS -> MANAGE PLUGINS. Geschrieben wird in einer abgespeckten Form von JavaScript, der Editor
übersetzt das in Bytecode für eine kleine VM in der Firmware. Wenn ein Plugin einen Fehler hat, wird
nur das Plugin abgeschaltet, die Electribe läuft normal weiter. Sprache, Ereignisse und Funktionen:
[docs/plugins.md](docs/plugins.md). Im Katalog liegen schon fertige Plugins: Set-Timer, BLECH Clicker,
Snake, Tetris, Game of Life, Pong, Simon, Mandelbrot, GIF Player, Lauflicht und Pulsieren.

## Der Emulator

Der Emulator lässt die echte Firmware auf deinem Rechner laufen, und die Seite zeigt dir dazu eine
bedienbare Electribe mit virtueller SD-Karte. Ton gibt es keinen, den Hörtest am Gerät ersetzt er also
nicht, aber du kannst alles ausprobieren, bevor es überhaupt in die Nähe deines Geräts kommt. Mehr dazu
in [docs/emulator.md](docs/emulator.md), die Tastenkombinationen der Firmware stehen in
[docs/tastenkombinationen.md](docs/tastenkombinationen.md).

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
- **Wenn das Gerät nicht mehr startet:** die Seite "Rettung" im Editor fragt, was du siehst, und führt
  dich den dokumentierten Weg zurück. Der Bootloader bleibt tabu, dahinter
  hilft nur JTAG ([docs/rettung.md](docs/rettung.md)).
- **Selbst testen:** die [Gerätetests](docs/geraetetests/README.md) beschreiben, wie du BLECH und die
  Kartenfunktionen an deinem Gerät nachvollziehst, mit Warnung, Voraussetzungen, Sicherung und
  Rückweg.

Der Linter prüft bekannte Speicherbereiche, das Nachrichtenformat und dokumentierte Fehlerfälle. Der
Emulator führt den echten ARM-Code der Firmware aus, den DSP aber nur als Attrappe: er erzeugt keinen Ton,
und das Bedienfeld und das Timing bildet er nur nach. Ob etwas gut klingt, sagt nur das Gehör. Vieles ist
bisher nur im Emulator geprüft und am echten Gerät noch nicht. Details: [docs/linter.md](docs/linter.md),
[docs/emulator.md](docs/emulator.md).

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
