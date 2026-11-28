# DSP program in the GNU Blackfin simulator

Research scripts from the attempt to run the firmware's real DSP program in the Blackfin simulator of gdb and feed it
the host-port traffic the emulator records. Results and the point where it stopped:
[Echter DSP-Code im Simulator](../../../docs/messungen/2026-11-12-dsp-im-simulator.md). The working model for checks is
the [DSP model](../../emu/dsp_model.py).

The scripts are kept as they were left on 2026-11-12. They are not maintained and not covered by tests; scripts that
import emulator case modules may need adjusting to the current `tools/emu`.

## What is not in the repository

| Input | Where it comes from |
|---|---|
| Region directory (`map.json`, `blocks.txt`, `r_<addr>.bin`) | The DSP boot stream of a SYSTEM.VSB, extracted with `dsp_extract.py SYSTEM.VSB OUTDIR` (tools/dsp on the sample swap branch). Korg code: keep OUTDIR outside the repository |
| Simulator `run` | gdb 15.2 with the `SIGNEXTEND` fix in `sim/bfin/bfin-sim.c` (see [Ton im Emulator](../../../docs/ideen/52-ton-im-emulator.md)), built with `make all-sim`. The extra tracing and the MDMA model used in the measurement were local simulator changes and are lost |
| Blackfin binutils (`as-new`, `objcopy`) | binutils 2.42 configured for `bfin-elf`. `BFIN_BINUTILS` points at the build directory, default `../binutils-build2` next to this folder |
| Recordings (`*.pkl`) | Made by the `record*.py` scripts from a VSB in the emulator |

## Scripts

| Script | What |
|---|---|
| `mkelf.py` | Writes an ELF32 Blackfin executable from (address, bytes) segments |
| `boot.py REGIONDIR RUN` | Runs the extracted DSP program from `0xFFA00000` in the simulator |
| `harness.py REGIONDIR RUN ASMFILE` | Assembles a harness (`h1.s`, `h2.s`, `h3.s`, `t1.s`) to `0x03000000` and runs it with the DSP regions and the MMR area as RAM |
| `replay.py REGIONDIR RUN REC.pkl` | Replays recorded host-port writes into the DSP program (`replay.s` is the generated harness) and prints the output peak every ms |
| `record.py`, `record2.py` ... `record11.py` | Record host-port transfers from the emulator with the DSP model (variants: sequencer run, user sample on part 1, peripheral write counts) |
| `knobs*.py`, `allknobs*.py`, `sweep*.py`, `notes.py`, `midinotes.py`, `padmap.py`, `ifxmap.py`, `fx*.py`, `cutin.py`, `bluefilt.py`, `ftype*.py`, `who*.py` | Emulator probes: which DSP parameters and mailbox commands change for knobs, notes, pads and effects |
| `cdis.py VSB FROM TO [thumb]` | ARM disassembly of a firmware range with capstone |
| `callers.py`, `dr.py`, `p2walk.py` | Helpers over disassembly text files |

Run the emulator-based scripts from the repository root with the emulator venv (`tools/emu/.venv`), for example
`python3 tools/dsp/sim/record2.py SYSTEM.VSB out.pkl`.

## Device side

`tools/device/dsp_peek.py`, `region_peek.py`, `l1_dump.py` and `heap_head.py` read DSP memory on the device through the
firmware's own host-port read (`0xC00141F8`). They compare the device code with a reference VSB first, then place a small
stub at `0xC1000000`, run it with BLECH EXEC and restore the buffer afterwards. EXEC changes device state: only run them
on purpose. Some reads hang the device (bank A, the L1 scratchpad, the voice loop code, any read while a voice sounds), see
[Hänger nach EXEC](../../../docs/messungen/2026-11-15-remote-exec-haenger.md#dsp-lesen-per-exec-14-und-1511). `dsp_peek.py --emu VSB` runs the same read in the emulator.
