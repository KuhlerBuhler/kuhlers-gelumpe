# Documentation

[Deutsche Version](README.md) | English version

Entry point for everything in `docs/`. Start with the [glossary](glossary.en.md) if a term is new to you: every page
links the terms it uses on first use. Users start with the [README](../README.en.md) ([German](../README.md)).

Language: most pages are written in German and are linked as they are, German is the reference. English
editions exist for [plugins](plugins.en.md), [patcher](patcher.en.md), [original-zurueck](original-zurueck.en.md)
this index and the [glossary](glossary.en.md); the plugins page also exists in [French](plugins.fr.md). The
page names in the links are German, the descriptions here are English.

Everything measured holds for the Korg Electribe 2 Sampler with firmware 2.02 and Hacktribe, unless a page says otherwise. Facts carry a marker: **gemessen** (measured), **offline** (code or a dump
was read), **hergeleitet** (derived), **offen** (open). Code in `tools/` has short READMEs of its own:
[tools/emu/README.md](../tools/emu/README.md) and [tools/alsa-sysex.md](../tools/alsa-sysex.md). The origin of bundled
parts is in [NOTICE](../NOTICE), the rules for agents and contributors in [AGENTS.md](../AGENTS.md).

## Use the firmware and the app

| Page | Content |
|---|---|
| [faq.md](faq.md) | Frequent questions, from "will it break my device" to "Error, No File" |
| [tastenkombinationen.md](tastenkombinationen.md) | Key combinations of the firmware: SHIFT, hold and power-on |
| [test-modus.md](test-modus.md) | Test mode (the device looks switched off) and operating the device over USB |
| [plugins.en.md](plugins.en.md) | Plugins: language, events, functions, card format, the BLECH menu, the editor page ([German](plugins.md), [French](plugins.fr.md)) |
| [effekt-katalog.md](effekt-katalog.md) | The effects and modulations of the Baukasten catalog and what an effect cannot do |
| [original-zurueck.en.md](original-zurueck.en.md) | Going back to Korg's original firmware, red and blue ([German](original-zurueck.md)) |
| [rettung.md](rettung.md) | The Blechy page: the documented way back when a device does not start |
| [doom-lizenz.md](doom-lizenz.md) | Doom on the card: parts, licences and what is missing for redistribution |
| [geraetetests/](geraetetests/README.md) | Step-by-step guides to test BLECHTRIBE and the card functions on your own device |

## How it is built

| Page | Content |
|---|---|
| [development.md](development.md) | Build, test, build the desktop app, release |
| [architektur.md](architektur.md) | Gatekeeper, send path, rehearsal, terminal, error catalog, design |
| [patcher.en.md](patcher.en.md) | Patching the firmware: patch format, hooks, rules, emergency switch, patch table ([German](patcher.md)) |
| [emulator.md](emulator.md) | The emulator: installation, service, card and flash, boot, check runs |
| [geraetekarte.md](geraetekarte.md) | The device map: format, evidence, conversions, expert mode |
| [linter.md](linter.md) | The linter, its knowledge about effects, the simulated device, open points |
| [speicherbereiche.md](speicherbereiche.md) | Measured memory areas, write limits, areas still open |
| [firmware-sprache.md](firmware-sprache.md) | Device menus in German: language files, shortening rule, umlauts |
| [barrierefreiheit.md](barrierefreiheit.md) | Accessibility: what is tested against WCAG 2.2 AA and what is open |
| [entscheidungen.md](entscheidungen.md) | Decisions that are settled |
| [fahrplan.md](fahrplan.md) | Roadmap: what is released, what 1.5 brings, what comes after |

## Background

Deeper explanations of how the firmware works, used by the pages above.

| Page | Content |
|---|---|
| [hintergrund/skript-laufzeit.md](hintergrund/skript-laufzeit.md) | Firmware tasks, hooks and memory as the base of the plugin runtime |
| [hintergrund/virtuelle-sd.md](hintergrund/virtuelle-sd.md) | File functions of the firmware, FatFs, the sample loader, the virtual card |
| [hintergrund/sample-datei.md](hintergrund/sample-datei.md) | The `e2sSample.all` format and the transfer over USB with a swap file |
| [hintergrund/startbild-editor.md](hintergrund/startbild-editor.md) | The start image in flash and its editor |
| [hintergrund/ladeanimation.md](hintergrund/ladeanimation.md) | The file format of the loading animation and the GIF import |
| [hintergrund/blech-theme.md](hintergrund/blech-theme.md) | Own fonts and symbols for the display |
| [hintergrund/dsp-erster-blick.md](hintergrund/dsp-erster-blick.md) | The DSP: program, effect switching, filters |
| [hintergrund/panel-controller.md](hintergrund/panel-controller.md) | The microcontroller behind keys, knobs and LEDs |
| [hintergrund/sequencer-timing.md](hintergrund/sequencer-timing.md) | Sequencer resolution, MIDI clock, tempo |
| [hintergrund/patternwechsel.md](hintergrund/patternwechsel.md) | Confirming a pattern change and the gap that a change has |
| [hintergrund/sample-swap.md](hintergrund/sample-swap.md) | Sample Swap: voices, DSP requests, eviction, waits, checks |
| [hintergrund/sample-speicher.md](hintergrund/sample-speicher.md) | Sample memory: upper RAM, import, PCM write paths and protection, file ownership, journal |
| [hintergrund/doom.md](hintergrund/doom.md) | Doom on the device: start, picture, pads, sound, runtime |
| [hintergrund/usb.md](hintergrund/usb.md) | USB: descriptor, endpoints, drivers, SysEx bottleneck |
| [hintergrund/blackfin.md](hintergrund/blackfin.md) | The Blackfin DSP: boot, memory access, DMA, RTOS, QEMU and simulator |
| [hintergrund/effekte.md](hintergrund/effekte.md) | Effects: effect file, levels, tube curve, TAP Motion, glide, synth start |
| [hintergrund/firmware-extras.md](hintergrund/firmware-extras.md) | Hacktribe extras on red: grooves, scales, chords, Easter egg |
| [hintergrund/blau.md](hintergrund/blau.md) | The blue Electribe: ID, update, effect port, red as blue |
| [hintergrund/display.md](hintergrund/display.md) | Display and LEDs: calibration, brightness, meter, power saving, device name |
| [hintergrund/patch-effizienz.md](hintergrund/patch-effizienz.md) | Patch efficiency: plugin check, decoder, work areas, SysEx buffer |

## Measurements and ideas

| Page | Content |
|---|---|
| [messungen/README.md](messungen/README.md) | All measurements by topic. They are the evidence for the device map, so their paths never change |
| [ideen.md](ideen.md) | Ideas that are still open, with their detail pages in [ideen/](ideen/) |
| [glossary.en.md](glossary.en.md) | Terms and repo-specific names |
