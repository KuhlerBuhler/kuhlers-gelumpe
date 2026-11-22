# Debrick with a Raspberry Pi 4 (13.11.2026)

The scripts that brought back a red electribe after a partial SYSTEM.VSB went into flash. Symptom: white screen at
power on, later "00". They run on the Pi from this folder (`sudo`, OpenOCD 0.12 with `bcm2835gpio`, `pinctrl`), with
`../am1802.cfg` found through `openocd -s ..`. No firmware image is included.

Like the scripts one level up, nothing here writes to flash. Power off and on undoes everything; the flash only changes
when you run SOFTWARE UPDATE on the device.

## Files

| File | What |
|---|---|
| `pi4.cfg` | Adapter: Pi 4, pins TCK 11, TMS 5, TDI 6, TDO 13, TRST 26 (jumper wires plugged onto J9, not soldered) |
| `late.sh <image.bin>` | Holds TRST low, waits for a power cycle, gives ROM and boot loader 45 s, then runs `rescue.sh` at 500 kHz. This is what worked |
| `rescue.sh <image.bin> [kHz]` | Halts the running firmware, checks the boot loader set up the MMU (TTB `0x8001C000`), loads the image to `0xC0000000` and jumps in with the MMU state the boot loader leaves |
| `catch.sh <image.bin>` + `catch.tcl` | Tries to catch the CPU in the boot loader at power on and start the image at the entry. Did not work on 13.11. |
| `oc.py` | Sends commands to OpenOCD's TCL port 6666 |
| `jt.py` | Memory read/write over that port; `python3 jt.py disp` prints the LCD buffer as text |
| `press2.py` | Presses panel keys from JTAG: `python3 press2.py install menu left show`. Writes a stub at `0xC1000100` that queues a key message in a task context and returns to the interrupted PC |

`image.bin` is SYSTEM.VSB without its first 0x100 bytes (exactly 0x200000 bytes). Take the firmware the device had
before it broke, or a fresh build on the owner's ORIGINAL.BIN.

## Steps

1. Wires onto J9 (silk print GND TMS TCK TRST TDI TDO, see `../photos/`), device off.
2. `./late.sh image.bin`, then switch the device on. Expect `TTB 0x8001c000` and the image's first words.
3. Read the display: `python3 jt.py disp`. If it shows "00", the firmware waits for the panel MCU: check the
   C272 cable to the panel board (on 13.11. it sat crooked).
4. On the device, or with `press2.py`: MENU, EDIT left to DATA UTILITY, MENU, EDIT right to SOFTWARE UPDATE
   (FACTORY RESET comes just before it), then MENU three times. The SD card needs a good SYSTEM.VSB.

## Pitfalls

- BLECH 1.4.6 switches the device off when power is held 5 s at start. For that image the rescue patched it in RAM:
  `PATCH="0xc0181338=0xe12fff1e 0xc01539f4=0xea0000af" ./late.sh SYSTEM-146c.bin`. Other builds have these
  places elsewhere or not at all; leave `PATCH` empty for a firmware without BLECH.
- Never call firmware functions from the debugger with IRQs on (that crashed the device). `press2.py` goes through the
  stub for this reason.
- The addresses in `jt.py` and `press2.py` (LCD buffer `0xC031B310`, panel queue, queue and event functions) were
  read on the Hacktribe-based build of 13.11. A build on Korg's stock firmware needs them checked first.
- About ten quick SSH connections to the Pi block port 22 for some minutes; keep one session open.
