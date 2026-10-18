"""Where Doom stands on the own Electribe, read over USB-MIDI with BLECH's READ while the device hangs on the start image.

The loader and the engine keep their progress at 0xC017F000 (tools/doom/runtime_abi.h, struct doom_shared): stage 1 the keys
said Doom and the loader runs the firmware's start calls, 2 the card is mounted, 3 doom.bin is read and its SHA-256 checked,
4 the engine runs, 5 a level plays, 6 stopped, 0x80000000 an error (with its code). Read only: one READ of 0x844 bytes; nothing
is written, nothing executed. Whether the device answers at all while the loader holds the start task is part of the answer.

    python3 doom_probe.py               # device on USB, hanging after SHIFT + TAP at power-on
    python3 doom_probe.py --watch 10    # ten reads, one a second, to see whether the numbers move
"""
import argparse
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from blue_report import midi_ask, search, talk  # noqa: E402

SHARED = 0xC017F000
READ, R_READ = 0x61, 0x69
STAGES = {0: "nothing (the loader never ran, or the RAM was cleared)", 1: "selected: the loader runs the firmware's start calls",
          2: "mounted: the card is there, doom.bin is being read", 3: "verified: doom.bin read and checked, jumping into the engine",
          4: "engine: Doom initialises", 5: "playing", 6: "stopped"}
FIELDS = ("magic", "version", "stage", "error", "frames", "gametic", "gamestate", "viewangle", "file_reads", "bytes_read",
          "heap_used", "key_events", "last_key", "last_down", "console_head", "exit_status", "clock_millis")


def read_shared(ask, dev):
    f, body = talk(ask, dev, READ, struct.pack("<II", SHARED, 0x44 + 2048))
    if f != R_READ:
        raise SystemExit(f"READ got function {f:#x}")
    status = struct.unpack_from("<I", body)[0]
    if status:
        raise SystemExit(f"READ refused with status {status}")
    data = body[16:]
    values = dict(zip(FIELDS, struct.unpack_from("<17I", data)))
    console = data[0x44:].split(b"\0")[0].decode("ascii", "replace")
    return values, console


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--port", default=None)
    p.add_argument("--watch", type=int, default=1)
    a = p.parse_args()
    ask, port = midi_ask(a.port)
    dev = search(ask)
    print(f"device answered the search: model {dev['model']:#04x}, version {dev['version']} (so its MIDI still runs)")
    for i in range(a.watch):
        values, console = read_shared(ask, dev)
        stage = values["stage"]
        text = f"error {values['error']:#x}" if stage & 0x80000000 else STAGES.get(stage, "unknown")
        print(f"\nstage {stage:#x}: {text}")
        print("  " + ", ".join(f"{k} {v:#x}" for k, v in values.items()))
        if console:
            print("  console:", console[-600:])
        if i + 1 < a.watch:
            time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
