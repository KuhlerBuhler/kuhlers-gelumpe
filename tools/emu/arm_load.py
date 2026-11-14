# SPDX-License-Identifier: GPL-2.0-only
"""ARM load of a firmware in the emulator, per scene (docs/messungen/2026-11-08-cpu-last-blech.md).

    tools/emu/.venv/bin/python tools/emu/arm_load.py SYSTEM.VSB SPANS.txt|- OUT.json

Load is the model of cpu_profile.py: executed ARM instructions times 5 ns over device time, the rest the firmware sleeps in
wait-for-interrupt. Every scene runs 2 s of device time in 10 ms slices; the result has the mean, the median, the 99th
percentile, the largest slice and the messages to the panel per second (mostly LEDs). SPANS.txt is the output of
tools/patch/apply.mjs; the instructions inside each span are
added up per patch (only code that runs inside a patch, not the firmware work a hook starts). "-" for an unpatched file.
The DSP is a mock in the emulator: these numbers say nothing about the DSP load.
"""
import collections, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tools/emu"), str(ROOT / "tools/patch")]
import unicorn  # noqa: E402
from menu_cases import boot  # noqa: E402

NS = 5
PATPTR = 0xC033E6A4          # the pattern object (tools/patch/dice.py), the block starts 4 bytes in
SLICE = 0.01


def spans_of(path):
    out = []
    if path == "-":
        return out
    for line in Path(path).read_text().splitlines():
        m = re.match(r"\s+([\w.-]+): 0x([0-9a-f]+) \+ (\d+)", line)
        if m:
            start = 0xBFFFFF00 + int(m[2], 16)
            out.append((start, start + int(m[3]), m[1]))
    return out


def main():
    vsb, spans_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    payload = Path(vsb).read_bytes()[256:]
    spans = spans_of(spans_path)
    dev = boot(payload, adapter=True, seconds=3)
    m, uc = dev.m, dev.m.uc
    st = {"on": False, "n": 0, "pages": collections.Counter()}

    def block(_u, at, size, _d):
        if st["on"]:
            st["n"] += size // 4
            st["pages"][(at, size)] += 1
    uc.hook_add(unicorn.UC_HOOK_BLOCK, block)
    results = []

    def measure(scene, seconds=2.0, each=None):
        st["pages"].clear()
        uc.ctl_flush_tb()
        slices = []
        t0, p0 = m.time_ns, m.panel_count
        st["on"] = True
        while m.time_ns - t0 < seconds * 1e9:
            if each:
                each(len(slices))
            n0, s0 = st["n"], m.time_ns
            dev.run(SLICE)
            slices.append((st["n"] - n0) * NS / (m.time_ns - s0) * 100)
        st["on"] = False
        total = sum(size // 4 * c for (_, size), c in st["pages"].items())
        by = collections.Counter()
        for (at, size), c in st["pages"].items():
            for a, b, label in spans:
                if a <= at < b:
                    by[label] += size // 4 * c
                    break
        dt = m.time_ns - t0
        slices.sort()
        row = dict(scene=scene, busy=round(total * NS / dt * 100, 3), p50=round(slices[len(slices) // 2], 2),
                   p99=round(slices[int(len(slices) * .99)], 2), max=round(slices[-1], 2), deviceMs=round(dt / 1e6),
                   panelPerS=round((m.panel_count - p0) / dt * 1e9, 1), asserts=len(m.asserts),
                   byPatch={k: round(v * NS / dt * 100, 3) for k, v in by.most_common()})
        print(json.dumps(row), flush=True)
        results.append(row)

    measure("idle")
    pattern = m.u32(PATPTR) + 4
    uc.mem_write(pattern + 37, bytes([3]))

    def fill(heavy):
        for part in range(16):
            for step in range(64):
                trig = (step % 4 == 0 and part == 0) if not heavy else (step % 2 == part % 2 or part < 4)
                uc.mem_write(pattern + 0x830 + part * 0x330 + step * 12,
                             bytes([1, 96, 96, int(trig), 61 if (part == 0 or heavy) else 0, 0, 0, 0, 0, 0, 0, 0]))
    fill(False)
    dev.press(2, .4)
    measure("playing")
    dev.press(0x17, .3)
    measure("playing-keyboard")
    dev.press(0x17, .3)
    dev.press(1, .3)
    fill(True)
    dev.press(2, .4)
    measure("playing-16-parts")
    dev.press(0x17, .3)
    measure("playing-16-parts-keyboard")
    dev.press(0x17, .3)
    dev.press(1, .3)
    uc.mem_write(pattern + 0x802, bytes([2]))
    fill(False)
    for step in range(64):
        uc.mem_write(pattern + 0x830 + step * 12, bytes([1, 127, 96, int(step == 0), 61, 65, 68, 73, 0, 0, 0, 0]))
    dev.press(0x15, .3)
    dev.press(2, .4)
    measure("sequencer-four-note-long-ties")

    def edit(i):                # a step edit every 100 ms while it plays: the tie cache (tools/patch/pad_colors.py) starts over
        if i % 10 == 0:
            step = 1 + i // 10 % 16
            uc.mem_write(pattern + 0x830 + step * 12 + 1, bytes([126 + i // 10 % 2]))
    measure("sequencer-long-ties-editing", each=edit)
    dev.press(1, .3)
    Path(out).write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
