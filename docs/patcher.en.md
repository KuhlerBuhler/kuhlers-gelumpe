# Patcher: how it works and its rules

[Deutsche Version](patcher.md) | English version

As of 2026-10-14. This page is the English edition of [patcher.md](patcher.md). The German page is the
reference and carries the developer detail: the hook registry, the start sequence, the memory map and
the measurements. This page covers what a user needs and links to the German page for the rest. The
editor is in German, so button labels appear here in German with a translation. Evidence lives in
[`docs/messungen/`](messungen/README.md) (German); what is only derived is marked as such.

## What the patcher does

The patcher puts changes to your own firmware on a copy of your `SYSTEM.VSB`, checks the copy in the
emulator and hands you a file to put on the SD card. **Only the patch is ever distributed, never firmware.**
Everyone applies it to their own VSB, as with Hacktribe. Extra features for the Electribe come as plugins
on the card ([plugins](plugins.en.md)), not as part of the firmware file.

The "Patcher" page in the editor does all of it in the browser. You drop your own `SYSTEM.VSB` on it, choose
what to patch, wait for the check and download the result.

### What is built, and where it was tested

Built means: the code is in the repository and was checked in the emulator or in tests.

- The patch format (version 1) with field, raw and copy changes, the hook registry, and the start-phase
  exceptions (see below).
- The **BLECH set** of six patches (next section) and the page "Patcher" with check, download, the choice
  "BLECH direct" or "with Hacktribe", and the conversion from Korg's original 2.02 to Hacktribe.
- The patch file `BLECH.patch` and a bsdiff file for the release.
- The check in the emulator before the export.
- The write rule for the card, and the customization pages of the BLECH menu.

**What was tested on a real device:** two things. First, the way there with a data patch (a start image) and
back with the normal update ([way back rehearsed](messungen/2026-10-10-rueckweg-geuebt.md), German).
Second, the MFX 2 patch, the first code patch on the device, together with the emergency switch
([MFX 2 on the device](messungen/2026-10-13-mfx-umschalter-geraet.md), German). **The start image editor,
the plugin runtime, the BLECH menu and the card access are tested only in the emulator.** Everything listed
under "Not built yet and still open" is planned or unmeasured.

## What is inside a VSB

The Electribe has two processors:

- **ARM** (TI AM180x): panel controller, display, sequencer, menus, MIDI, SD card, flash.
- **DSP** (an Analog Devices Blackfin, exact model open): computes the sound, that is samples, filters,
  inserts and the master effect.

`SYSTEM.VSB` is `0x200100` bytes: a 256 byte header plus the 2 MiB image of the ARM, with code, data
(presets, texts, start image, tables) and the embedded DSP program (about 270 KB), which the ARM loads into
the DSP at start. At run time the ARM only sends the DSP commands and values. The VSB is not encrypted.

Patches build on Korg's 2.02 with Hacktribe. FX presets, menu lengths and the start image inside it may
differ from the original. The editor recognises the file by fingerprints (`data/devices.mjs`,
`src/firmware.mjs`).

There are three kinds of patch:

| Kind | Examples | Checkable in the emulator | Difficulty |
|---|---|---|---|
| Data | presets, menu lengths, the start image, texts and themes | yes | low, partly built |
| ARM code | keys, menu entries, LEDs, touchpad routing, bug fixes, games | yes, the emulator runs the ARM | medium |
| DSP code | new effect slots, new algorithms, a third effect over everything | no, the DSP is a dummy in the emulator | high |

## The BLECH set and its patches

The set is `data/patches/blech.json` and holds six patches:

| Patch | What it does |
|---|---|
| Start image editor | edit the start image and store it in the flash (the storage place is derived; whether it works on the device is open) |
| MFX 2 | a second master effect on TOUCH SCALE, switched on or off on the BLECH menu page MFX 2 (applies from the next start) |
| Plugin runtime with BLECH menu | runs plugins from the card and adds the "BLECH" screen to the EDIT ring ([plugins](plugins.en.md)); also carries Blechy, the app built into BLECH, as the last page of the ring: his block lies in the image at `0xC0184000` and is loaded at start before the card, with or without a card, and with EXIT held at power-on he is absent |
| Card folder `blechtribe` | the device reads `KORG/blechtribe/` instead of `KORG/hacktribe/` (or `KORG/electribe sampler/` on Korg's original) |
| BLECH start image | the BLECH splash screen |
| Theme | own fonts and symbols for the display ([background, German](hintergrund/blech-theme.md)); a data-only patch |

All six apply together. The page applies them in the browser, and the result is byte for byte the one that
`tools/patch/apply.mjs --set data/patches/blech.json` produces (measured on our own files).

### Which firmware you can start from

- **Hacktribe 2.02** (the file from Hacktribe's package, sha256 `7cb4825c...`): the normal case.
- **Korg's original 2.02** (sha256 `1d0f0689...`, the value Hacktribe's own patch script checks): the page
  offers two ways.
  - **"BLECH direkt (kein Hacktribe-Patch nötig)"**, BLECH direct, the default: the patches go straight onto
    Korg's file. Built and checked in the emulator, **open on the device**
    ([measurement](messungen/2026-10-14-stock-blech.md), German).
  - **"BLECH mit Hacktribe (hacktribe-2.patch selbst mitbringen)"**, BLECH with Hacktribe: the page first
    turns Korg's file into Hacktribe's file and then adds BLECH. You bring Hacktribe's `hacktribe-2.patch`
    yourself.
- Any other file is rejected.

**Why you bring `hacktribe-2.patch` yourself.** Hacktribe's README says that the contents of its `patch`
directory are not open source and not covered by the GPL (checked 2026-10-14). The file is therefore neither
in this repository nor on the page, and the page does not fetch it. You download it from Hacktribe (the page
links it) and drop it on the page. Everything happens in the browser, nothing is uploaded. The page checks
that the file starts with `BSDIFF40`, is at most 1 MiB and builds a file of the right size, and then that the
result has the sha256 `7cb4825c...`. Honest limit: the real `hacktribe-2.patch` is not in the repository, so
this path was tested only with a self-made bsdiff (same tool, random data, nothing from Korg or Hacktribe).
You can test it with your own file through `E2_STOCK_VSB` and `E2_HACKTRIBE_PATCH` in
`test/patcher.test.mjs`.

**What you miss on Korg's original without Hacktribe.** Whatever Hacktribe adds that BLECH does not bring
itself: filters for the synth, extra effects, and the SysEx commands `0x52` to `0x57` for reading and writing
RAM. The editor's live mode needs those SysEx commands, and the effect editor needs the preset tables on the
card. Korg's build has neither ([original in the emulator](messungen/2026-10-14-stock-emulator.md), German).
The BLECH menu, plugins, MFX 2 and the start image editor run on it in the emulator.

## The rules a patch must follow

These rules exist because a firmware that hangs before its rescue paths is only recoverable with a JTAG
probe, even if nobody touched the bootloader.

1. **No patches in the start phase.** Patches set themselves up on first use (first MENU, first key
   combination), not at start. The exceptions are data whose format the card knows and checks (the start
   image) and the few spans a patch lists under `startPhase` with a reason; the check allows exactly those
   and reports them. The theme uses this for the bitmaps of the fonts.
2. **Locked areas** that the patcher never changes: the boot program, the firmware's start phase, the panel
   exchange, the key query at start, the update routine, and the DSP program. They were measured as every
   code block that runs on one of the 17 start paths before screen 1, plus every byte read there (about
   153 KiB of code and 47 KiB of data).
3. **Hooking only by jump or pointer**, with an emergency switch at the entry. A patch never overwrites
   original code for good, it hooks in: at the start of a function, at a call site, or by swapping a
   function pointer in a table.
4. **Patches call existing firmware functions** and never write to hardware registers themselves. LEDs go
   through the firmware's LED manager.
5. **Patches do not write to the flash**, except through the firmware's normal storage paths.
6. **DSP patches** are a class of their own without a safety net: the DSP program is loaded at start, the
   emergency switch cannot reach it and the emulator does not check it. None is built.

### The emergency switch

Hold **EXIT while powering on**. The firmware then runs without patches: every hooked-in patch asks one flag
first and runs only the original code if it is set. The device behaves like the firmware without patches,
and DATA UTILITY, SOFTWARE UPDATE lets you install a different firmware. It applies **for this start only**,
nothing is stored. Measured on the device for MFX 2 (the switch turns the code patch off), and measured in
the emulator for the rest.

**Limits:** it does not help against broken start data, DSP patches, broken stored data, or patches that
disturb the panel exchange (that is what rule 2 is for). Against hardware damage rule 4 helps, not the
switch.

### How the card is written

Code from a patch touches the card only through the firmware's file functions, never through the SD
controller. FatFs has no lock, so everything the runtime writes follows these rules:

1. Read only at start, after `e2sSample.all` has loaded and with EXIT not held. Write only in the frame hook
   with the main screen open, so never during DATA UTILITY or sample loading. The BLECH menu is the exception:
   it writes only on the user's WRITE and reads the file list when the page PLUGIN EDIT opens and the description of a plugin when its page DESCRIPTION opens, always with
   the menu screen open.
2. Write only on an explicit request (`korg.store.save()`), with at least 50 frames (2 seconds) between two
   writes.
3. A file is written whole in one go and never replaced in place: two files take turns with a generation
   number and a CRC-32, so after an abort (power loss, card pulled) the previous generation stays readable.
4. A failure is counted and not repeated, and the firmware keeps running.
5. No file is deleted or renamed and no folder is created; you create `KORG/blechtribe/Plugin/` yourself.

Writing through FatFs is **not yet tested on the device** (steps in [geraetetests/karte.md](geraetetests/karte.md),
German).

### RAM of the patches

The patcher checks changes to the file: two patches that write the same bytes are refused. What a patch keeps in RAM
at run time on top of that (state words, buffers, file buffers, a pool, the menu state) is not in the file, so it
went unnoticed once: the start image editor kept its state and buffers at `0xC01A4000` to `0xC01A5000`, over the
code and the picture of the power-off patch at `0xC01A4A00`. It was found by comparing addresses, not by a test.

Every patch now names that RAM next to `changes` (fields in `src/patch.mjs`):

- `ram`: memory of the patch itself, each entry `at`, `length`, `what` and `source`. `source` says where the size comes
  from, `<file>:<SYMBOL>` in the tool that builds the patch; the tools write the entries from their own constants.
  A patch without RAM of its own says `"ram": []`.
- `shares`: a word inside another patch's area that this one reads or writes (`with` is the owner's id). It has to lie
  wholly in an area the owner lists in `ram`; without the owner (the patch is applied alone) it only has to stay clear of
  other areas and written bytes. There are two: `PS_SETTING` (`0xC0180F10`, the BLECH menu writes it into
  the pattern switch's state) and `BLECH_MFX` (`0xC01D6E1C`, MFX 2 reads the setting from the plugin runtime's menu
  state).

The block of Blechy at `0xC0184000` is not in `ram`: it is among the bytes the file writes (`changes`), and the runtime only reads it.

What a patch writes into firmware objects it does not own (the display buffer, the ring to the panel) is not
declared. Flash locations are not RAM either.

`test/patch-ram.test.mjs` fails when two patches of the set overlap in written bytes or declared RAM on either build
(Hacktribe, Korg's own), when an area reaches into the bytes another patch writes, when a `shares` lies in no area of
its owner, or when an area does not lie wholly in a free `FF` run of the image (`data/patch-ram.mjs`); outside the
image the message names the protected region of `data/protected.mjs` it hits. The start image editor at its old
address is a test of its own, and `applyPatches` refuses such a set too. With `E2_VSB` (and `E2_STOCK_VSB`) another
test checks that every declared area in the image is `FF` in your firmware; the Korg case has not been run here.

Collecting the areas turned up a second overlap: the plugin store's two images (`script_store.s`) read up to 0x4000
bytes each, so the second one, at `0xC01FC000`, ran 16 bytes past the end of the block buffer (`0xC01FFFF0`) into the
last bytes of the image, which are not ours. Only a file over 0x3FF0 bytes does that; one we wrote is at most
16 + 194 * 84. The read size is now 0x3FF0 and the build of the plugin runtime fails when the images leave the block
buffer. The change has not been run in the emulator (only the literal of the read size changes, two bytes).

## The check in the emulator

The page releases the download only after the emulator has checked your patched copy. The check takes a few
minutes. It requires that

1. the patched firmware boots to the main screen,
2. without the marker at flash `0x220000` the update prompt appears,
3. the start modes with held keys are reachable, the emergency switch included,
4. with a wrong panel version the panel update path appears,
5. the patched functions run through fixed operating sequences without an assertion,
6. no change lies in a locked area.

Built today: points 1 to 4 and 6 as `tools/emu/check.py` on the page Patcher; point 5 is built for the start
image editor, MFX 2 and the BLECH menu (their cases run when the copy carries the matching hook). The
plugin runtime has its own cases in `tools/emu/script_cases.py`, which `check.py` does not call. The check
also passes with an empty flash, which is what most users have, and with a full flash image of your own
device. Korg's original needs a few allowances (it shows a loading bar over the start image and takes longer
to start), which the check handles without weakening it for Hacktribe's file
([details, German](patcher.md#prüfung-gegen-korgs-build)). With Korg's original as the base and the patched
copy, `check.py` passed 88 of 88 checks with an empty flash and 89 of 89 with the own flash image.

The emulator runs ARM code but does not play sound, and it does not run the DSP. Whether something sounds
good, only your ears can say.

## Putting the file on the card, and the way back

**Back up first:** the SD card (samples, patterns, the original `SYSTEM.VSB`) and the global settings.

After the download the page shows a guide with the card folder of your running system:

- Hacktribe reads `KORG/hacktribe/System/SYSTEM.VSB` (measured, [firmware way back](messungen/2026-10-08-firmware-rueckweg.md), German).
- Korg's original reads `KORG/electribe sampler/System/SYSTEM.VSB` (Korg's release note for 2.02, page 2).
- **Card folder:** the `blechtribe` patch changes the folder the firmware uses. After the update the device
  reads `KORG/blechtribe/` instead of `KORG/hacktribe/`, so your samples and patterns are not there on their
  own. Before the update, **copy** `KORG/hacktribe/` (on Korg's original `KORG/electribe sampler/`) to
  `KORG/blechtribe/`, **do not rename it**. Then put the `SYSTEM.VSB` into the folder of the firmware that is
  running now, not into `blechtribe`.

Then update through DATA UTILITY, SOFTWARE UPDATE. If something goes wrong, the emergency switch (EXIT at
power-on) is your first resort.

**Trying it first in the emulator.** The button "Ich hab angst dass mein Gerät kaputt geht" ("I am afraid my device will break") puts your copy on the
virtual card as the update file and inserts the card; your own file (Hacktribe) runs in the emulator. In
the emulator, DATA UTILITY, SOFTWARE UPDATE shows "Next Version 2.02", so the file is found. The service
never touches the other card folders: whoever wants the files of `KORG/hacktribe/` in `KORG/blechtribe/` on the
virtual card copies the folder in the file manager ("Öffnen" in the card field), like on a real card.

**The way back.** Put your saved original `SYSTEM.VSB` back and update again through the normal update path.
This was rehearsed on a device: a firmware from the patcher on, the original back
([way back rehearsed](messungen/2026-10-10-rueckweg-geuebt.md), German).

What can break, and what helps:

1. The firmware crashes or hangs while running: restart.
2. A flashed firmware does not start and the device asks for an update: the original VSB from the SD card
   (per Hacktribe's documentation; not played through ourselves).
3. The firmware hangs before the update prompt: only a JTAG probe helps. Rules 1 to 3 and the checks before the
   export exist for this.
4. The boot program is overwritten: only JTAG. The patcher never touches it.
5. User data in the flash is damaged: restore from a flash dump and the SD backup.
6. Hardware damage caused by software: no case is known, but it is not ruled out; rule 4 guards against it.

**Open:** the rescue when the running firmware no longer starts, and whether the file under
`KORG/electribe sampler/System/` is good for that. The "Rettung" page in the editor walks through the
documented recovery and marks each step as measured on the device or not ([rettung.md](rettung.md), German).
If you want to repeat BLECH on your own device, the [device tests](geraetetests/README.md) (German) give a
warning, prerequisites, a backup and the way back.

## Patch file formats

### The JSON patch (format version 1)

Built in `src/patch.mjs`:

```json
{ "format": "gelumpe-patch", "version": 1, "id": "splash", "name": "Startbild",
  "changes": [
    { "field": "splash", "bytes": "<hex>" },
    { "file": 1712384, "bytes": "<hex>", "expect": "<SHA-256 der ersetzten Bytes>" } ] }
```

- **Field change:** a field of the device map that lies in the firmware and is writable, in exactly its width.
  The check before the export allows it to be read at start, because the map knows its format. First example:
  the start image.
- **Raw change:** a file offset, the new bytes and the checksum of the bytes it replaces. Without a checksum,
  or with a wrong one, nothing is applied. The original bytes are never in the patch.
- **Copy change** (`copy`, optionally with `over`): takes its bytes from your own VSB when it is applied, the
  source with a checksum, and writes `over` on top. This lets a patch reuse firmware tables without carrying
  one.
- Also rejected: changes in the header of the VSB or outside it, two changes at the same place, a base that is
  not the measured firmware, and a copy that fails the firmware check afterwards.

A code patch also lists its hook sites in an optional `hooks` list (site, kind, chain, position, whether it can
swallow the event). `applyPatches` checks the hooks of all patches before writing. Two patches on the same site,
two patches on the same stage of a chain where one replaces, an unknown site or chain, and known incompatible
pairs are rejected. A hook that can swallow an event and lies in front of another patch's hook on the same
chain is applied and reported as a dependency. Detail: [German page](patcher.md#haken-register).

### `BLECH.patch` and the bsdiff files (release files)

The release carries two kinds of file, built from `data/patches/blech.json` and a VSB. They go to
`dist-release/` (gitignored) and are never checked in. The input is the `SYSTEM.VSB` from Hacktribe's package
(`hacktribe-es2-sd-package.zip`, sha256 `7cb4825c...`), because only that file fits the bsdiff:

```bash
E2_VSB="<SYSTEM.VSB from the package>" npm run build:blech-patch
npm run build:blech-patch -- --vsb <SYSTEM.VSB> --version 1.0.1
```

| File | What for | How to apply |
|---|---|---|
| `BLECH.patch` | the whole set in our format: all patches with hooks, checksums and start-phase exceptions. Fits any Hacktribe 2.02 whose code and fixed data match, and with `--stock` Korg's original 2.02 too (a second fingerprint, the folder variant for Korg's build) | `node tools/patch/apply.mjs --vsb SYSTEM.VSB --patch BLECH.patch --out BLECH.VSB`, or `applyPatchFile` in `src/patchfile.mjs` |
| `BLECH-for-7cb4825c.bsdiff`, with `--stock` also `BLECH-for-1d0f0689.bsdiff` | exactly this file to BLECH as a bsdiff 4 (`BSDIFF40`, like Hacktribe's patch). The name carries the start of the sha256 of the input | `bspatch SYSTEM.VSB BLECH.VSB BLECH-for-7cb4825c.bsdiff`, without our app, only with the file that has this hash |

**Which VSB fits.** Hacktribe's file and an edited VSB differ only in data that users change. Measured on one
of our own `SYSTEM.VSB` files against the one from the package: 2317 bytes in 1331 runs, namely FX presets,
the menu lengths (14 single bytes in code literals) and the start image (641 bytes). No code, no DSP
program. `BLECH.patch` therefore does not check the whole file but a **fingerprint**: the sha256 over all
bytes except the `userData` areas (FX tables, groove and modulation table, start image, menu lengths).
Both VSBs pass it. Each change of a patch also still checks the bytes it replaces (`expect`). The
fingerprint of the output leaves out only the `userData` bytes that the patch does not write, so it checks
what the patch wrote too.

**Layout of `BLECH.patch`** (version 2, numbers little endian): a 128 byte header, then the content as JSON.

| Offset | Size | Content |
|---|---|---|
| 0 | 8 | tag `GLMPPAT\0` |
| 8 | 2 | format version, 2 |
| 10 | 2 | features, 0 |
| 12 | 4 | length of the content |
| 16 | 16 | BLECH version as text, padded with 0 (the one from `package.json`, so the release's) |
| 32 | 32 | fingerprint of the expected input (sha256 without `userData`) |
| 64 | 32 | fingerprint of the expected output (sha256 without the `userData` bytes the patch does not write) |
| 96 | 32 | sha256 of the content |
| 128 | n | `{ "format": "gelumpe-patch-file", id, name, userData: [[file, length], ...], patches: [...] }` |

The `patches` are the same objects that `applyPatches` gets from the JSON files, in the same order. Applying
the file therefore means: check the input fingerprint, run `applyPatches`, check the output fingerprint. If
either differs, nothing is written; the result is byte for byte that of the set
(`test/patch-file.test.mjs`). `--patch BLECH.patch` stands alone, not together with JSON patches. For Korg's
original, the fingerprints stand in the payload under `alternates.stock` (the format stays 2), and a file
without `alternates` rejects Korg's original with a note of its own. Version 1 (one hash over the whole
file) was never published and is not read.

**No firmware in the file.** `BLECH.patch` carries only what the JSON patches already carry: our code and
our data, the hashes of the bytes they replace (a hash names bytes, it does not contain them), source
addresses of `copy` changes (addresses, not bytes), and at single hooks the displaced instruction word
(4 bytes) that our code replays.

**No firmware in the bsdiff either.** `tools/patch/bsdiff.mjs` does not search for matches, it knows the
changes. What the patches do not touch is a match at the same place, a `copy` change is a match at its
source address, and everything else is a literal in the extra block. Classic bsdiff would store a copied
piece as a difference to its target, and that would be firmware. Here the diff block is only zeros. Measured
on the package VSB: diff block 2,073,917 bytes, all zero; extra block 23,491 bytes, all of them bytes of the
patches. The longest run in the extra block that also occurs in the original VSB and has more than three
different byte values is 18 bytes (9 runs, 151 bytes in total, coincidentally equal instruction words); all
longer runs are zeros and ones (tables). `bspatch` on macOS gives the same bytes as the set. The control
block reveals source addresses of copies, not bytes. The build uses the `bzip2` program.

## Not built yet and still open

Planned and not built:

- Code as source text, to which the patcher assigns a place so that two patches cannot overwrite each other.
  Today every patch fixes its own addresses.
- The jump and the emergency-switch query generated by the patcher instead of by each patch.
- Pattern change only after confirmation; so far only a hook description in `test/fixtures/hooks-planned.json`.
- DSP patches and a DSP check in the emulator.
- A boot menu and a fallback firmware (a small menu of our own before Korg's first instruction, with an
  unchanged firmware in free flash). Not built, and no code for it exists in the repository.
- Point 5 of the checks before the export for all patches, not only for the start image editor, MFX 2 and the
  BLECH menu.

Open measurements:

- The calculated addresses in the `FF` blocks: on the device only the code of MFX 2 is checked, not the rest
  of the block and not more operating sequences.
- Reading and writing the card through FatFs on the device, and the start image editor, the plugin runtime
  and the BLECH menu on the device.
- Whether the start image editor can save to flash `0x7F0000` on the device (the place is derived).
- Free RAM for code loaded later.
- The real `hacktribe-2.patch` in the patcher: so far tested only with a self-made bsdiff.
- The rescue for a firmware that no longer starts.
- DSP: the exact model and the layout of the master path (the load format is measured, see
  [DSP, first look](hintergrund/dsp-erster-blick.md), German).

For the full list, the memory map and the start sequence, see [patcher.md](patcher.md).
