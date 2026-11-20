# JTAG on the electribe 2 (AM1802)

OpenOCD files and scripts for the last way back when a firmware hangs before every rescue path of the firmware itself
(see [Rettung](../../docs/rettung.md)): halt the ARM over JTAG, load a firmware image into RAM, run it from there and use
DATA UTILITY > SOFTWARE UPDATE to write it back to flash.

No script here writes to flash or RAM. Power off and on undoes everything. No firmware is included.

## Files

| File | What |
|---|---|
| `am1802.cfg` | OpenOCD target (ICEPick, ARM926), based on OpenOCD's `omapl138.cfg` |
| `e2-xpack.cfg` | Adapter CH347 (xpack-openocd 0.12, 500 kHz, TRST only). This is the setup that was used |
| `e2-raspberrypi.cfg` | The same with a Raspberry Pi as the adapter (bcm2835gpio, pins as in Hacktribe's openocd.cfg). Not tested |
| `ocd.sh` | `./ocd.sh <adapter.cfg> <script.tcl>` (on a Pi with sudo). `OPENOCD=/path/to/openocd` picks another binary |
| `probe.tcl` | Read only: connect, halt, print PC, CPSR, CP15 and a few words, resume |
| `pc-stichprobe.tcl` | Read only: halt 12 times and print PC/LR (where does the CPU hang?) |
| `halt-now.tcl` | Halt right now and say where the CPU is (manual timing trick) |
| `halt-at-entry.tcl` | Catch the factory boot loader at power-on, run to the firmware entry `0xC0000000` and halt there |
| `photos/` | The board with header J9 (`j9-markiert.jpg` marks CPU, J9 and the DSP header) |

## Wiring

Header J9, next to the AM1802, 6 pins with silk print GND TMS TCK TRST TDI TDO. J10 right beside it belongs to the DSP
(BF523), not that one. The Raspberry Pi pins are listed in `e2-raspberrypi.cfg`.

## Procedure (manual, as used for two debricks in September 2026 with a CH347)

1. Start OpenOCD in the moment you switch the device on: `./ocd.sh e2-xpack.cfg halt-now.tcl`.
   PC `0x8...` means still in the factory boot loader (good), PC `0xC...` means too late: power off and try again.
   A reset over JTAG does not work on this board, hence the timing trick.
2. `telnet localhost 4444`, then `bp 0xc0000000 4 hw` and `resume`. The CPU halts at the firmware entry.
3. There: `load_image system.bin 0xc0000000 bin`, `reg pc 0xc0000000`, `resume`.
   `system.bin` is SYSTEM.VSB without its first 0x100 bytes (exactly 0x200000 bytes).
4. The firmware now runs from RAM. Run DATA UTILITY > SOFTWARE UPDATE from the SD card to put it back into flash.

`halt-at-entry.tcl` tries steps 1 and 2 automatically (start it before switching on). Its polling loop did not catch the
boot loader reliably on the test device (mostly "too late"); the manual trick worked.

## Not known

- Whether the factory boot loader still jumps to `0xC0000000` when the SYSTEM region in flash is empty. Both debricks
  had a valid firmware in flash. If the breakpoint never hits, `halt-at-entry.tcl` reports `RESULT NO_BP` and where the
  CPU is.
- The Raspberry Pi file is untested (command names for OpenOCD 0.12, older ones are in comments).
