# Glossary

[Deutsche Version](glossary.md) | English version

This page is the English edition of [glossary.md](glossary.md). The anchors are the same in both languages, so a link such as `#hacktribe` works in each. Entries that point at a German page name the section of that page in German.

Terms used in these docs, repo-specific names included (the German ones are names that appear in the app and in the pages). Each doc links a term on its first use. Entries are sorted alphabetically.

## App

In the plugin docs, an app is a plugin that registers itself with `korg.app(name, group)` and has a screen of its own. It is opened from the BLECH menu under GAMES or TOOLS, owns the display while open, and EXIT always closes it.

See: [plugins.md](plugins.md) ("Apps und das Display"), `data/script/contract.mjs` (SCRIPT_APPS)

## ARM

The main processor of the Electribe (TI AM180x). It runs the panel controller link, display, sequencer, menus, MIDI, SD card and flash, and sends commands and values to the DSP at run time.

See: [patcher.md](patcher.md) ("Was in der VSB steckt")

## Baukasten

The editor area (`BLECHTRIBE -> Baukasten`) where effects and modulations are built from DSP units with real units and exported to the card or sent live over USB; it holds the effect catalog.

See: [effekt-katalog.md](effekt-katalog.md), `README.md`

## BLECH

Name of the patch set of this project (product name BLECHTRIBE): the changes built into the Electribe 2 firmware, such as menu, plugin runtime, sample loader and pattern switch. It builds on Hacktribe or on Korg's own firmware.

See: [patcher.md](patcher.md) (Patch-Satz BLECH), `README.md`

## BLECHTRIBE

This project's firmware mod for the Electribe 2, applied as a patch set to a VSB; it has its own SysEx commands 0x60 to 0x67 and 0x6F and a BLECH menu on the device.

See: `src/protocol.mjs` (BLECH command table), [emulator.md](emulator.md)

## BLECHTRIBE SysEx

The extra SysEx commands that the patch `blech-sysex` adds: reading and writing RAM in blocks, reading flash, and reading and writing files on the card. They replace Hacktribe's commands `0x52` to `0x57`, which answer only with EXIT held at power-on. On the blue Electribe they only read.

See: [patcher.md](patcher.md) (patch table), `data/patches/blech-sysex.json`

## Blechy

The BLECHTRIBE mascot. As an app built into the firmware it is the last page of the EDIT ring and waves on power-off; as a page of the editor (`#rescue`) it is the assistant that leads through the way back when a device does not start right.

See: [patcher.md](patcher.md) (patches `power-off`, `load-bar`), [rettung.md](rettung.md)

## Bootloader

The boot program in flash `[0, 0x20000)`. It loads the firmware. The patcher and the editor never touch it.

See: [rettung.md](rettung.md) ("Stoppschild"), [patcher.en.md](patcher.en.md)

## bsdiff

Binary diff format (`BSDIFF40`). The release carries `BLECH-for-<hash>.bsdiff` files that turn exactly one known SYSTEM.VSB into the BLECHTRIBE version without the BLECHTRIBE app; here the diff block is only zeros, so no firmware bytes are in the file.

See: [patcher.md](patcher.md) ("Patch-Datei und bsdiff"), `tools/patch/bsdiff.mjs`

## Build

The firmware build a patch is made for: `hacktribe` (Hacktribe 2.02), `stock` (Korg's red 2.02) and `synth` (Korg's blue 2.02). A patch lists them in `builds`; the base firmware picks the variant.

See: [patcher.md](patcher.md) ("Welche Patches passen"), `src/patch.mjs` (`buildsOf`, `selectFor`)

## Bytecode

The compact block the editor compiles a plugin into: block format 2 with a 52 byte header, signed 32-bit values and a checksum. The device loads this block, never the source text.

See: `data/script/contract.mjs` (FORMAT_VERSION, HEADER)

## DATA UTILITY

The device menu page for card and sample functions (IMPORT SAMPLE, EXPORT SAMPLE, EXPORT ALL PATTERN, CARD FORMAT).

See: [emulator.md](emulator.md) (section "Virtuelle SD-Karte")

## DEV MODE

BLECH menu page that lets BLECH WRITE write into the firmware image in RAM (except locked areas). It is OFF after every power-on, is not saved, and does not exist on the blue Electribe.

See: [patcher.md](patcher.md) (patch `blech-sysex`), `data/dev-closed.mjs`

## Doom loader

The `doom-loader` patch: on SHIFT + TAP at power-on it reads `KORG/blechtribe/Doom/doom.bin` from the card, checks length and SHA-256 and jumps into it.

See: `tools/patch/doom_loader.py`

## DSP

The second processor (an Analog Devices Blackfin, exact model open). It computes the sound: samples, filters, insert effects, master effect. Its program is embedded in the VSB and loaded by the ARM at start.

See: [patcher.md](patcher.md) ("Was in der VSB steckt"), [hintergrund/dsp-erster-blick.md](hintergrund/dsp-erster-blick.md)

## e2sallpat

The backup file of all 250 patterns (file ending .e2sallpat), made by the device's EXPORT ALL PATTERN and importable with IMPORT ALL PATTERN.

See: [emulator.md](emulator.md), `src/map/address.mjs` (PATTERN_FILE)

## e2sSample.all

The sample collection file on the SD card (`Sample/e2sSample.all` in the card folder). The firmware loads it at start; the loader patches (`sample-errors`, `sample-swap`, `user-samples`) work on it.

See: [patcher.md](patcher.md) (patch table), [hintergrund/sample-datei.md](hintergrund/sample-datei.md)

## Eingangsfilter

The code that BLECH puts in front of the panel messages (touch, buttons) so that plugins or patches can change what the firmware sees, for example the locked touch X and Y.

See: [messungen/2026-11-12-plugin-touch-lock-y.md](messungen/2026-11-12-plugin-touch-lock-y.md), `tools/patch/script_hw.s` (touch_lock_input)

## Emulator

The ARM emulator in `tools/emu/` that runs a copy of the firmware, so the patcher can check it before export. It plays no sound and models the DSP only at its interface.

See: [patcher.md](patcher.md) ("Prüfungen vor dem Export"), [emulator.md](emulator.md)

## Evidence markers

Labels on facts in the docs that say how a statement is backed: **gemessen** (measured on the device or in the emulator), **offline** (code or a dump was read, nothing was run), **hergeleitet** (derived from other facts) and **offen** (not checked yet).

See: [messungen/README.md](messungen/README.md)

## Execute

Hacktribe's SysEx command 0x57, which makes the device jump to a given address, used to run a small stub from RAM (for example to set LEDs).

See: `src/protocol.mjs` (EXECUTE), [messungen/2026-10-08-led-execute.md](messungen/2026-10-08-led-execute.md)

## Execute stub

A small piece of ARM code uploaded over SysEx (0x53/0x54) into RAM and run once with Hacktribe's command 0x57; it must end with r0 = 1 to get an answer.

See: [hintergrund/virtuelle-sd.md](hintergrund/virtuelle-sd.md) (section 6)

## Expertenmodus

Expert mode: unknown fields can be edited as raw numbers behind a switch; changes go the most volatile way first (RAM or pattern buffer) and need a second confirmation to become permanent.

See: [geraetekarte.md](geraetekarte.md) (section "Expertenmodus")

## FatFs

The FAT file system library inside the firmware. It has no lock, so patches use only its file functions (`f_open`, `f_read`, `f_write`, `f_close`) and follow the card write rule.

See: [patcher.md](patcher.md) ("Schreibregel für die Karte")

## Fingerabdruck

Fingerprint: the sha256 over all bytes of a VSB except the `userData` areas (FX tables, groove and modulation tables, start image, menu lengths). `BLECH.patch` checks it for input and output instead of the whole file.

See: [patcher.md](patcher.md) ("Patch-Datei und bsdiff")

## Firmware

The software running on the Electribe 2's ARM CPU (SYSTEM.VSB 2.02: Korg's original or Hacktribe), which BLECH patches.

See: `AGENTS.md`

## Frame hook

The hook at 0xC00836FC in the UiTask that runs every 40 ms (25 Hz) after the firmware drew its widgets; plugin code drains the input ring and draws into the display buffer there.

See: [hintergrund/skript-laufzeit.md](hintergrund/skript-laufzeit.md) (section 1.3)

## FX-Katalog

The set of ready-made effects (49 insert and master effects, 6 modulations) in `data/fx/catalog.mjs`; the patch `fx-catalog` appends them to the presets in the firmware.

See: [effekt-katalog.md](effekt-katalog.md), `data/fx/catalog.mjs`

## Geraetekarte

The device map: every editable field of the Electribe described once as data (id, label, where, type, transport, source, evidence). The UI, the linter and the docs are generated from it.

See: [geraetekarte.md](geraetekarte.md), data/map/

## Globals

The 256-byte block of device settings behind GLOBAL PARAMETERS (MIDI channel, clock mode, contrast, battery type and more). It lives in flash at 0x230000, begins with `GLST`, ends with `GLED`, and is saved on power-off and on WRITE.

See: `data/map/global.mjs`, [messungen/2026-10-13-globals-zurueckgesetzt.md](messungen/2026-10-13-globals-zurueckgesetzt.md)

## GSCR

The four-byte tag at the start of a compiled plugin block (format 2, with its own size and CRC-32). A plugin file `e2sPlugin.all` is a header (`GSAL`) followed by such blocks.

See: `data/script/contract.mjs`

## Hacktribe

Third-party open-source firmware mod for the Electribe 2 sampler. It is built from Korg's 2.02 with Hacktribe's `hacktribe-2.patch` (not in this repository) and reads its own card folder `KORG/hacktribe/`. BLECHTRIBE builds on Hacktribe 2.02 or on Korg's original.

See: [patcher.md](patcher.md) ("Original Korg 2.02 zu Hacktribe")

## Haken

Hook: a place where a patch redirects the firmware (a function start, a call site, or a table pointer), registered with its chain, position and swallow flag in the patch's `hooks` list.

See: [patcher.md](patcher.md) ("Einhaken", "Haken-Register"), `src/hooks.mjs`

## Host-Port

The memory port through which the ARM processor reads and writes the DSP's memory, for example to load sample audio into the DSP or to read it back. In the emulator it is modelled as a mailbox with control words such as 0xA9 and 0xAB.

See: [ideen/52-ton-im-emulator.md](ideen/52-ton-im-emulator.md), [ideen/59-sample-editor.md](ideen/59-sample-editor.md), [hintergrund/dsp-erster-blick.md](hintergrund/dsp-erster-blick.md)

## JTAG

Hardware debug interface. When the firmware hangs before its rescue paths, or the boot program is damaged, only a JTAG probe can recover the device.

See: [patcher.md](patcher.md) ("Startablauf", "Was kaputtgehen kann"), [rettung.md](rettung.md)

## Kurzprüfung

The default emulator check of the patcher page: only start and rescue paths (`check.py --quick`), not the cases of the individual patches. "Voller Test" runs those too, "Kein Test" skips the check.

See: [patcher.md](patcher.md) ("Prüfumfang"), `tools/emu/check.py`

## lang-de

Optional generated patch that shows the BLECH menu and Korg's main menus in German. Off by default, available only through the app.

See: [firmware-sprache.md](firmware-sprache.md), `src/patcher.mjs` (`LANG_DE_URLS`)

## Linter

The rule set (src/rules.mjs, data/findings.mjs) that checks effect presets and other fields against everything that has gone wrong before; severities fatal, silent, error, warn, note.

See: [linter.md](linter.md)

## Loading animation

The file KORG/blechtribe/Media/loading.blla (format BLLA) that the firmware plays while it loads the samples; without a valid file Blechy plays.

See: [hintergrund/ladeanimation.md](hintergrund/ladeanimation.md)

## Mailbox

The command channel from ARM to DSP: 64 word frames sent alternately to two mailbox addresses (0xFF900018, 0xFF900098); the ARM waits until the DSP clears bit 31 before the next frame.

See: [hintergrund/patternwechsel.md](hintergrund/patternwechsel.md) (section 2.4)

## MFX

Master effect: the one effect on the whole mix, chosen per pattern (page MFX TYPE). The MFX 2 patch makes TOUCH SCALE a second MASTER FX button with a second effect type per pattern slot.

See: `tools/patch/mfx_switch.py`, [messungen/2026-10-10-mfx-umschalter.md](messungen/2026-10-10-mfx-umschalter.md)

## Motion Sequence

The Electribe's recorded knob movement per part. A part's mode is off (0), smooth (1) or trigger hold (2), set by the page MOTION SEQ of the Part menu or `korg.parts[i].motionMode`.

See: `data/script/contract.mjs` (PATTERN_MOTION, PART_FIELDS motionMode)

## Notschalter

Emergency switch: holding EXIT while powering on makes every hooked-in patch skip its code, so the device runs like the unpatched firmware for this start only. Nothing is stored.

See: [patcher.md](patcher.md) ("Notschalter")

## Panel controller

The separate microcontroller (ARM Cortex-M3, FM3 family) behind keys, knobs, pads and LEDs, talking to the main ARM over UART0 in 5 byte messages; its firmware is stored in every VSB.

See: [hintergrund/panel-controller.md](hintergrund/panel-controller.md)

## Patch

A set of byte changes applied to the user's own SYSTEM.VSB (JSON under data/patches/, built by tools/patch/); code patches hook into firmware functions, data patches only replace bytes.

See: [hintergrund/blech-theme.md](hintergrund/blech-theme.md), data/patches/

## Patcher

The tool that builds a changed SYSTEM.VSB from patch files (ARM code and hooks); available in the app and as tools/patch/apply.mjs.

See: [development.md](development.md) (section "Patcher"), `tools/patch/apply.mjs`

## Pattern confirm

BLECH feature (menu BLECH > FEATURES > PATTERN CONFIRM, patch pattern-switch): turning the wheel while playing only browses (VIEW:), MENU confirms (NEXT:) and the change happens at the end of the sequence.

See: [hintergrund/patternwechsel.md](hintergrund/patternwechsel.md)

## Plugin

A small program in the repo's own script language that runs on the Electribe inside the BLECHTRIBE runtime (apps, games, tools, helpers), written in the editor on the Plugins page and tested in a simulator before it is sent.

See: [plugins.en.md](plugins.en.md)

## Plugin-Laufzeit

The runtime (patch `script-runtime`, generated, not in the repository) that runs plugins from the card and adds the BLECH menu and the built-in app Blechy to the device.

See: [patcher.en.md](patcher.en.md), [plugins.en.md](plugins.en.md)

## Pool

The shared 128 KiB memory area (0xC01D7000 to 0xC01F7000) in which the plugin blocks, their variables and their plugin entries live. A block that does not fit is rejected with POOL_BUDGET.

See: `tools/patch/script_hooks.py` (POOL), `data/script/contract.mjs` (SCRIPT_POOL_BYTES, ERROR_LIST)

## Probelauf

Rehearsal: the simulated device is given exactly the byte stream that would go to the device and plays it through on a copy. Catches wrong channel, missing address messages and encoding errors.

See: [architektur.md](architektur.md)

## Rahmenhaken

The routine hooked into the firmware's UI task that runs once per frame (every 40 ms, 25 times a second). It compares the firmware's state to create sequencer events, delivers the event ring, timers and frame events to the plugins, sends LED packets and copies the plugin display.

See: `tools/patch/script_hooks.s`, [plugins.md](plugins.md) ("Ereignisse")

## Sample-Swap

Patch `sample-swap`: with a large `e2sSample.all`, start loads only the samples of the first pattern; further samples are loaded from the card or the RAM cache when a pattern needs them. Red Sampler only.

See: [patcher.md](patcher.md) (patch table), `data/patches/sample-swap.json`

## SeqTask

The firmware task (priority 2) that runs the sequencer; it is woken every 2 ms and turns the timer ticks into sequencer steps, notes and MIDI.

See: [hintergrund/sequencer-timing.md](hintergrund/sequencer-timing.md), [hintergrund/skript-laufzeit.md](hintergrund/skript-laufzeit.md) (section 1.1)

## Sidecar

The frozen (PyInstaller) emulator service that the desktop app starts next to the page.

See: [development.md](development.md) (section "Die App"), `tools/emu/build-sidecar.mjs`

## Splash screen

The 128 x 64 pixel start image; BLECH stores a user image in flash sector 0x7F0000 and mirrors it as KORG/blechtribe/Media/splash.bmp.

See: [hintergrund/startbild-editor.md](hintergrund/startbild-editor.md)

## Sprachbereich

The 16 KiB at `0xC016C000` to `0xC0170000` (top of the code area MORE3) where `lang-de` writes its texts, tables and glyphs.

See: [firmware-sprache.md](firmware-sprache.md), `tools/patch/script_hooks.py` (`LANG`)

## Startphase

The firmware's start sequence before the main screen: boot program, panel exchange, key query at start, update prompt. Patches may not change code that runs there, because the rescue paths live there; listed exceptions are declared in a patch's `startPhase`.

See: [patcher.md](patcher.md) ("Regeln", "Prüfungen vor dem Export")

## Swap file

The temporary file e2sSample.tmp on the card used to shrink e2sSample.all, because the firmware's FatFs cannot truncate or rename.

See: [hintergrund/sample-datei.md](hintergrund/sample-datei.md)

## Sync Group

A per-pattern setting (OFF or 1 to 999) added by BLECHTRIBE. Patterns of the same group switch at the end of the sequence without MENU confirmation, and live changes (pitch, modulation) carry over to the next pattern in RAM, so there is no jump.

See: [messungen/2026-10-19-sync-groups.md](messungen/2026-10-19-sync-groups.md)

## SysEx

System Exclusive, the MIDI message type used over USB to talk to the device (reading and writing memory and files, remote control).

See: [test-modus.md](test-modus.md), [patcher.en.md](patcher.en.md)

## Test-Modus

State in which the device looks switched off (display, light and LEDs dark, Auto Power Off held) but keeps running. Only over USB, only in RAM; on a real device it is blocked after it froze one.

See: [test-modus.md](test-modus.md)

## Timer3

The hardware timer that counts at 150 MHz and that the firmware runs with a period of one second. The plugin clock (`korg.millis`) and the timers are built on it.

See: `data/script/contract.mjs` (TIMER3)

## Touch Scale

One of the three touchpad modes (Touch Scale alone, Gate Arp + Touch Scale, Gate Arp alone) selected by the TOUCH SCALE, GATE ARP and MASTER FX buttons; X on the pad plays the note of the scale.

See: [tastenkombinationen.md](tastenkombinationen.md), [ideen/102-gate-arp-y-rhythmus.md](ideen/102-gate-arp-y-rhythmus.md)

## Tuersteher

The gatekeeper: every change passes the linter and a rehearsal in the simulated device before it is sent to the device. Errors block sending, warnings need confirmation.

See: [architektur.md](architektur.md) (section "Der Türsteher"), `src/gate.mjs`

## UiTask

The firmware task that dispatches keys, draws the screens every 40 ms and is the only context where plugin handlers run.

See: [hintergrund/skript-laufzeit.md](hintergrund/skript-laufzeit.md) (section 1.1)

## Unicorn

The CPU emulation library the emulator tools use to execute ARM code, also for single routines without the whole firmware (for example to count the instructions of a display call).

See: [plugins.md](plugins.md) ("Im Emulator"), `tools/patch/test_script_display.py`

## VM

The bytecode virtual machine of the plugin runtime (tools/patch/script_vm.s): a stack machine with bounds-checked variables, a fuel counter that stops endless loops and a fixed API table instead of firmware addresses.

See: [hintergrund/skript-laufzeit.md](hintergrund/skript-laufzeit.md) (sections 2.2, 2.3)

## VSB

The firmware file `SYSTEM.VSB` of the Electribe 2: 0x200100 bytes, a 256 byte header plus the 2 MiB image of the ARM processor (code, data, and the embedded DSP program). It is not encrypted. The device installs it from the SD card through DATA UTILITY, SOFTWARE UPDATE.

See: [patcher.md](patcher.md) ("Was in der VSB steckt")

## WFI

The ARM instruction "wait for interrupt". A quiet firmware waits in it about 3000 times a second, one stuck in a loop never does, which the emulator uses to tell idle from hung.

See: `tools/emu/machine.py` (idle_waits), `tools/emu/server.py` (alive)
