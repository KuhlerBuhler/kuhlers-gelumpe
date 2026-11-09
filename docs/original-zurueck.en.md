# Back to Korg's original

As of 6 November 2026. [Deutsch](original-zurueck.md) (the German page carries the evidence table with all sources). For everyone who
wants BLECHTRIBE (or Hacktribe) off their Electribe, with the blue one in focus. Markers: **measured** (on a device or in the
emulator), **derived**, **open**. The way has not been walked on a real blue device yet, everything for the blue is measured in the emulator.

## Is it possible?

**Yes, on the blue one too.** BLECHTRIBE replaces Korg's firmware like an update from Korg, through SOFTWARE UPDATE from the SD card. Going back
is the same thing again with Korg's unchanged file.

- **Measured (emulator):** the update there and back writes only the firmware area `[0x020000, 0x220000)`. Bootloader, user area (your patterns)
  and PCM bank stay as they are, and after there and back the whole 16 MiB flash is byte for byte the same as before.
- **Measured (emulator):** after the first install BLECHTRIBE on the blue reads `KORG/blechtribe/System/SYSTEM.VSB`. Korg's unchanged blue file from there
  is written back and boots to the main screen.
- **Measured (emulator):** while Hacktribe (also with BLECHTRIBE) runs on the blue, its update takes Korg's blue file only with the Sampler head (byte `0x12`
  to `0x53`, byte `0x2E` to `0x24`). Unchanged it says "Invalid File" and writes nothing.
- **Measured (device, red):** there and back through Korg's update was practised on 10 October.
- **Open:** the same on a real blue device, a power cut in the middle of writing, an update without the power supply.

## Which firmware runs?

The page Rettung in the editor asks for you: `Rettung -> I want to go back to Korg's original`. By hand:

- **Red, BLECHTRIBE:** Korg's red file in `KORG/blechtribe/System/`.
- **Blue, BLECHTRIBE without Hacktribe:** Korg's blue file, **unchanged**, in `KORG/blechtribe/System/`.
- **Blue, Hacktribe or BLECHTRIBE with Hacktribe:** Korg's blue file **with the Sampler head** in `KORG/hacktribe/System/` (Hacktribe runs) or
  `KORG/blechtribe/System/` (BLECHTRIBE runs). The Rettung page makes the file from your own one from Korg.

## Step by step (blue, BLECHTRIBE without Hacktribe)

1. **Back up the card.** Copy everything on the SD card to your computer.
2. **Get Korg's firmware.** Download the System Update 2.02 for the Electribe (blue, not Sampler) from Korg, accept the licence, unzip. You need
   the `SYSTEM.VSB` from it.
3. **Put it on the card.** The name is exactly `SYSTEM.VSB` (not `SYSTEM (1).VSB`), the folder `KORG/blechtribe/System/`, create missing folders. Keep it
   the only file there: Korg's update also looks for `BOOT.VSB`, `USER.VSB` and `PCM.VSB` in that folder, and what happens then is not measured.
   A running BLECHTRIBE does not look in `KORG/electribe/System/`, there you get "Error, No File".
4. **Connect the power supply.** Without it the Electribe says "Battery Low" and writes nothing.
5. **Start the update.** Switch on, `DATA UTILITY`, last page `SOFTWARE UPDATE`, ENTER (the MENU key), confirm "Are You Sure?", wait for "Working..."
   (do not switch off), at "OK. Please Reboot." switch off and on again.
6. **Afterwards.** Korg's firmware reads `KORG/electribe/`, not `KORG/blechtribe/`. Copy what you want to keep from `KORG/blechtribe/` to
   `KORG/electribe/` (on the red `KORG/electribe sampler/`). Patterns in the device stay (emulator, open on a device).

## Blue with Hacktribe

Korg's file is refused ("Invalid File"). The Rettung page takes Korg's `SYSTEM.VSB` for the blue, checks it against Korg's 2.02 (any other file
is refused), changes exactly the two head bytes and saves the result as `SYSTEM.VSB`. The file stays on your computer. Then steps 1 and 3 to 6
above, with the folder of the running firmware. Measured in the emulator, open on a device.

If it sticks, see [Rettung](rettung.md) (German) or the page Rettung in the editor.
