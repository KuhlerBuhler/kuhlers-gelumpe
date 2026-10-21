[Deutsche Version](README.md)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/banner-dark.svg">
  <img alt="Kuhler's GELUMPE: graphical Electribe reader and modifier plus emulator" src="assets/readme/banner-light.svg" width="100%">
</picture>


A graphical Electribe 2 reader and modifier, plus an emulator and a patcher for the BLECH firmware,
the "Blechtribe". BLECH runs either on top of Hacktribe or directly on Korg's original firmware of the
red sampler. The blue Electribe 2 with firmware 2.02 has a separate Synth set tested in the
emulator, including the theme, start image, playing aids, BLECH menu and plugins. Its scope and
remaining limits are recorded in the [Synth measurement](docs/messungen/2026-10-16-blech-synth.md).

**Who I am:** Kuhler Buhler aka Pascal, software developer and live act. After installing Hacktribe I
noticed you can edit the MFX and IFX presets. Then I spent a few months in a "Entwicklungspsychose"
(a development frenzy), and this is what came out of it. Korg's treatment of the Electribe 2 annoys me
(they abandoned it), and with BLECH I practically built the Electribe 3.

If this is useful to you: [donate via PayPal](https://www.paypal.me/kuhlerbuhler).

An editor and emulator for the Korg Electribe 2 Sampler with firmware 2.02, Korg's original or
[Hacktribe](https://github.com/bangcorrupt/hacktribe). It runs as an app or in the browser. With it
you can

- start and operate your Electribe's firmware in an **emulator**, with display, keys, knobs and LEDs,
  without anything touching your device,
- **patch** your `SYSTEM.VSB` and export a new firmware file for the SD card (the BLECH patch set,
  a start image editor, a second master effect and more),
- write **plugins** that run on the Electribe: a running light, a game on the display, a menu page of
  your own,
- edit effects and patterns in plain words and real units instead of bytes, and send them to the
  device over Web MIDI.

Before anything is sent, a linter whose rules were cross-checked against the physical device and a
simulated device check whether the Electribe would accept it. The emulator, the patcher and plugins
work with Korg's original 2.02 and with Hacktribe 2.02. On the red sampler, the effect editor and RAM writes over MIDI
use Hacktribe or BLECH with its own USB commands. A different build moves the addresses, so a device or firmware file it does not
recognise is only read from.

**No firmware ships with this.** You load your own `SYSTEM.VSB`. The file never leaves your
computer, nothing is uploaded to a server.

## Hacktribe or the original firmware?

BLECH adds its own features to either base. Hacktribe additionally provides its extended oscillator
bank, MFX/IFX, grooves and scales, FX/groove import and export, a custom INIT pattern and MIDI
extensions. Those features require Hacktribe; applying BLECH to a Korg original does not add them.

The trade-off: the factory sample bank gives way to oscillators. User samples occupy slots 501 to
999, and factory samples need conversion for that bank. Existing patterns can sound different when
oscillator or effect assignments change, so check them after switching. Staying on Korg's original
with BLECH avoids that extra firmware conversion. The blue Synth set keeps Korg's synth firmware;
Hacktribe itself supports both hardware types.

See the [Hacktribe project](https://github.com/bangcorrupt/hacktribe),
[oscillators](https://github.com/bangcorrupt/hacktribe/wiki/Features#oscillators) and
[factory samples](https://github.com/bangcorrupt/hacktribe/wiki/How-To#factory-samples).

## Preview

The app in dark mode. The emulator is shown without firmware, so its display stays black.

| | |
|---|---|
| ![Start page](docs/images/preview/start.png) | ![Patcher](docs/images/preview/patcher.png) |
| Start | Patcher |
| ![Start screen](docs/images/preview/splash.png) | ![Plugin catalog](docs/images/preview/plugin-catalog.png) |
| Draw your own start screen | Plugin catalog |
| ![Plugin editor](docs/images/preview/plugin-editor.png) | ![Emulator](docs/images/preview/emulator.png) |
| Plugin editor | Emulator |

## Get the app

The Releases page of this repository has the app for macOS (Apple Silicon, `.dmg`), Windows
(`.exe`) and Linux (`.AppImage`, `.deb`). The app starts the emulator service itself and stops it when
you close it. The emulator's card and flash live in `~/.gelumpe`. On start and every few hours the app
checks for a newer release and shows "Neue Version verfügbar" at the top; a click opens the release page.

**The app is not signed.** On macOS the system blocks the downloaded app. Release it once:

```bash
xattr -dr com.apple.quarantine "/Applications/Kuhlers GELUMPE.app"
```

On Windows, SmartScreen shows a warning: "More info", then "Run anyway".

## Quick start from source

**In the browser.** You need Node.js 20 or later, and for the emulator Python 3.10 or later.

```bash
npm ci
npm run setup:emu   # once: Python environment with Unicorn for the emulator
npm start           # page and emulator together
```

`npm start` prints the address (by default `http://127.0.0.1:8737/`), open it in your browser. Without
the emulator `npm run serve` is enough and `setup:emu` is not needed. To talk to the device you need
Chrome or Edge on a desktop computer: the page uses Web MIDI with SysEx, which Safari does not have.

**Build the app yourself** (Tauri v2). Once: Node 20+, Python 3.10+, Rust via `rustup` and
`cargo install tauri-cli --version "^2" --locked`. Plus per system: on macOS the Xcode Command Line
Tools, on Windows the Visual Studio Build Tools with "Desktop development with C++", on Linux
`libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev libssl-dev libxdo-dev
patchelf python3-venv`.

```bash
npm ci
npm run app:build -- --bundles dmg            # macOS
npm run app:build -- --bundles nsis           # Windows
npm run app:build -- --bundles appimage,deb   # Linux
```

The build compiles the page, freezes the emulator service into a sidecar with PyInstaller
(`npm run build:sidecar` does just that) and packs the app. The result lands in
`src-tauri/target/release/bundle/`: `dmg/*.dmg` (macOS), `nsis/*-setup.exe` (Windows),
`appimage/*.AppImage` and `deb/*.deb` (Linux). Each system builds its own, cross-building does not
work. More (Intel Mac, Windows on ARM): [development](docs/development.md) (German).

## Patch the firmware

On the "Patcher" page you load your own `SYSTEM.VSB` (Korg's original 2.02 or Hacktribe 2.02), choose the patches and
get a new file. The emulator boots it first and checks it (main screen, update prompt, start modes,
emergency switch). The page only releases the file once the check has passed, which takes a few
minutes. It then shows the steps for putting it on the card. The patches, their format and their
limits are described in [docs/patcher.en.md](docs/patcher.en.md). If you want to patch without the app,
take `BLECH.patch` or the matching `.bsdiff` file from the release, described there as well.

Among other things the BLECH set brings: its own BLECH menu with plugins, colours for display and LEDs,
pattern changes with confirmation, TAP Motion, the note assistant in KEYBOARD mode, a melody generator
(SHIFT + PART ERASE), Blechy the pet, a splash screen with a loading bar, clear messages instead of
"Unknown Error" when loading samples, and Doom (SHIFT + TAP at power-on, licence in
[docs/doom-lizenz.md](docs/doom-lizenz.md), German).


## Plugins

A plugin gives the Electribe a new function. You put it on the device through the SD card, in the folder
`KORG/blechtribe/Plugin/`. The code is a subset of JavaScript, the editor compiles it to bytecode for a
small VM in the firmware, and an error switches the plugin off without disturbing the Electribe.
Language, events and functions: [docs/plugins.en.md](docs/plugins.en.md).
The catalog has ready plugins: Set-Timer, BLECH Clicker, Snake, Tetris, Game of Life, Pong, Simon and
Mandelbrot.

## The emulator

The emulator runs the real firmware as a local service, and the page shows an operable device with a
virtual SD card. It produces no sound and does not replace listening, but you can try everything before a
device sees it. More: [docs/emulator.md](docs/emulator.md) (German). The firmware's key combinations are in
[docs/tastenkombinationen.md](docs/tastenkombinationen.md).

## Safety: before you put anything on the device

A wrong write or a faulty firmware can hang the device. So:

- **Emergency switch:** hold EXIT while powering on. The firmware then runs without patches, and DATA
  UTILITY, SOFTWARE UPDATE lets you install a different firmware. This only applies to that one start.
- **Back up before you change anything:** the SD card (samples, patterns, the original `SYSTEM.VSB`) and
  the global settings. Powering off and WRITE save whatever is in RAM, so do not power off if something
  looks wrong.
- **Way back:** put the saved original `SYSTEM.VSB` back. How that was rehearsed is in
  [docs/messungen/2026-10-10-rueckweg-geuebt.md](docs/messungen/2026-10-10-rueckweg-geuebt.md).
- **If the device no longer starts:** the "Rettung" page in the editor (German) walks through the
  documented recovery and marks each step as measured on the device or not. The bootloader is never
  touched, beyond it only JTAG helps ([docs/rettung.md](docs/rettung.md)).
- **Test it yourself:** the [device tests](docs/geraetetests/README.md) describe how to repeat BLECH and
  the card functions on your own device, with a warning, prerequisites, a backup and the way back.

The linter checks known memory regions, message format and documented failure cases. The emulator runs
the firmware's real ARM code, but the DSP only as a stand-in: it makes no sound, and it only imitates the
panel and the timing. Whether something sounds good, only your ears can say. Much is so far checked in
the emulator only, not yet on a real device. Details: [docs/linter.md](docs/linter.md),
[docs/emulator.md](docs/emulator.md) (German).

## Documentation

[docs/README.md](docs/README.md) is the index: plugins, patcher, emulator, the device map, the
measurements on the device, ideas and background. For working on the code:
[docs/development.md](docs/development.md). The docs are in German, except the pages on
[plugins](docs/plugins.en.md) and the [patcher](docs/patcher.en.md), which also exist in English.

AI agents also work on this project. The rules for them are in [AGENTS.md](AGENTS.md).

## Contributing

Pull requests go to `develop`, not to `main`. The rules are in [CONTRIBUTING.md](CONTRIBUTING.md); the most important
one: no Korg data in the repository, ever. A check closes a pull request that carries any. If you find something that
can damage a device, report it privately ([SECURITY.md](SECURITY.md)).

## Licence

AGPL-3.0, see [`LICENSE`](LICENSE). Where the parts come from is in [`NOTICE`](NOTICE).
