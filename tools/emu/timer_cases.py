"""Emulator cases of the plugin timers (API 11, korg.after, korg.every, korg.afterSteps): a korg.after(1000) fires between
1000 and 1040 ms after the call, also with a pattern change in between; one set in the body of a plugin on the card, before
the samples load, fires at the first frame after the start, and the clock of the plugin has not lost the seconds of the load;
korg.afterSteps(4) fires with the fourth step after the call.

    python3 tools/emu/timer_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402
from splash_cases import Dev  # noqa: E402

# state: 1 once the timer is set, 2 once it ran; armed and fired are the plugin's own clock (korg.millis) at both moments
AFTER = """let state = 0; let armed = 0; let fired = 0;
korg.onEvent("ready", () => {
  armed = korg.millis();
  state = 1;
  korg.after(1000, () => { fired = korg.millis(); state = 2; });
});"""
PROGRAMS = {
    "after": AFTER,
    # the same, with a pattern change three frames after the call
    "pattern": AFTER + """
let frames = 0;
korg.onEvent("frame", () => { frames = frames + 1; if (frames == 3) korg.pattern(5); });""",
    # set in the body: on the card, that runs while the device starts
    "body": """let state = 0; let armed = 0; let fired = 0;
armed = korg.millis();
state = 1;
korg.after(1000, () => { fired = korg.millis(); state = 2; });""",
    # korg.afterSteps(4) from the second step on; `last` is the step of the last step event when the timer runs
    "steps": """let n = 0; let from = -1; let last = -1; let at = -1;
korg.onEvent("ready", () => { korg.play(); });
korg.onEvent("step", (s) => {
  last = s;
  n = n + 1;
  if (n == 2) { from = s; korg.afterSteps(4, () => { at = last; }); }
});""",
}


def compiled():
    """The include of the contract, and the blobs and symbols of PROGRAMS, from the compiler of this checkout."""
    code = """
import { asmInclude } from "./src/script/arm-tables.mjs";
import { compile } from "./src/script/compiler.mjs";
const programs = JSON.parse(process.argv[1]);
const out = { include: asmInclude(), programs: {} };
for (const [name, source] of Object.entries(programs)) {
  const r = compile(source, { name });
  if (!r.ok) { console.error(name, r.errors.map(e => e.message).join("; ")); process.exit(1); }
  out.programs[name] = { blob: Buffer.from(r.blob).toString("hex"), symbols: r.info.symbols };
}
process.stdout.write(JSON.stringify(out));
"""
    result = subprocess.run(["node", "--input-type=module", "-e", code, json.dumps(PROGRAMS)], cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def entry(name, ok, detail):
    return {"id": f"timers:{name}", "ok": bool(ok), "detail": str(detail)}


def signed(value):
    return value - (1 << 32) if value & 0x80000000 else value


class Watch:
    """Reads the globals of the plugin `name` by their names, and notes the device time of each new `state`."""

    def __init__(self, dev, name, program):
        self.dev, self.name, self.symbols, self.times = dev, name.encode(), program["symbols"], {}

    def word(self, at):
        return int.from_bytes(bytes(self.dev.m.uc.mem_read(at, 4)), "little")

    def var(self, name):
        entry = self.word(script_hooks.RUNTIME)
        for _ in range(16):
            if not script_hooks.POOL <= entry < script_hooks.CARD:
                return None
            blob = self.word(entry + 4)
            if script_hooks.POOL <= blob < script_hooks.CARD and bytes(self.dev.m.uc.mem_read(blob + 36, 16)).split(b"\0")[0] == self.name:
                return signed(self.word(self.word(entry + 8) + 4 * self.symbols[name]["slot"]))
            entry = self.word(entry)
        return None

    def run(self, seconds):
        m = self.dev.m
        end = m.time_ns / 1e9 + seconds
        while m.time_ns / 1e9 < end and not m.asserts:
            m.run_until(m.time_ns / 1e9 + 0.001)
            state = self.var("state")
            if state is not None and state not in self.times:
                self.times[state] = m.time_ns / 1e6
            if state == 2:
                break


def one_second(dev, name, program):
    """Device and plugin milliseconds from the call to the callback."""
    w = Watch(dev, name, program)
    w.run(3.0)
    device = round(w.times[2] - w.times[1], 1) if 1 in w.times and 2 in w.times else None
    return device, (w.var("fired") - w.var("armed")) if device is not None else None


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    menu_cases.for_build(payload)
    request = compiled()
    built = script_hooks.build(request["include"], build=identify(payload).build)
    programs = request["programs"]
    out = []

    for name in ("after", "pattern"):
        dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=2.0)
        script_cases.install(dev, built, programs, [name])
        device, plugin = one_second(dev, name, programs[name])
        # polled every millisecond, so the device time may show one more
        out.append(entry(f"after_1000_{name}", device is not None and 1000 <= device <= 1041 and 1000 <= plugin <= 1040 and not dev.m.asserts,
                         f"device {device} ms, plugin clock {plugin} ms"))

    # the plugin on the card, its body runs while the device starts (with samples on the Sampler)
    # marked as probed by the editor, so it runs without the user allowing it in the menu
    block = script_cases.with_flags(bytes.fromhex(programs["body"]["blob"]), 1)
    dev = Dev(payload, flash, 0)
    dev.m.adapter = True
    dev.m.insert_card(menu_cases.early_card(payload, {script_cases.CARD_FILE.lstrip("/"): script_cases.archive([block])}))
    w = Watch(dev, "body", programs["body"])
    w.run(8.0)
    called, ran = w.times.get(1), w.times.get(2)
    device = round(ran - called, 1) if called is not None and ran is not None else None
    plugin = (w.var("fired") - w.var("armed")) if device is not None else None
    out.append(entry("after_1000_from_the_start", device is not None and device >= 1000 and abs(device - plugin) <= 41 and not dev.m.asserts,
                     f"set {called} ms after power-on, ran {device} ms later, plugin clock {plugin} ms"))

    dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=2.0)
    script_cases.install(dev, built, programs, ["steps"])
    w = Watch(dev, "steps", programs["steps"])
    dev.run(2.0)
    start, at = w.var("from") or -1, w.var("at") or -1
    out.append(entry("after_steps_4", start >= 0 and at >= 0 and (at - start) % 16 == 4 and not dev.m.asserts, f"set at step {start}, ran at step {at}"))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--flash", type=Path)
    a = p.parse_args()
    result = cases(a.vsb.read_bytes(), load_flash(a.flash) if a.flash else None)
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(e["ok"] for e in result) else 1)


if __name__ == "__main__":
    main()
