"""Emulator cases of the object tree (API 10, data/script/objects.mjs): a plugin sets the INTENSITY of the display light
through its path to 0 and back, the backlight pins go dark and light again; a value outside the range is clamped and
counted; a stored value outside the range is repaired at start.

    python3 tools/emu/objects_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
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

INTENSITY = "korg.menu.blech.customizations.display.intensity"
PROGRAMS = {
    # frame 5: light off, frame 40: back to full
    "light": f"""let n = 0;
korg.onEvent("frame", () => {{
  n = n + 1;
  if (n == 5) {INTENSITY} = 0;
  if (n == 40) {INTENSITY} = 15;
}});""",
    # a value that only shows at run time: 99 is clamped to 15 and counted
    "clamp": f"""let v = 99;
korg.onEvent("ready", () => {{
  {INTENSITY} = v;
}});""",
}


def compiled():
    """The include of the contract and the blobs of PROGRAMS, from the compiler of this checkout."""
    code = """
import { asmInclude } from "./src/script/arm-tables.mjs";
import { compile } from "./src/script/compiler.mjs";
const programs = JSON.parse(process.argv[1]);
const out = { include: asmInclude(), programs: {} };
for (const [name, source] of Object.entries(programs)) {
  const r = compile(source, { name });
  if (!r.ok) { console.error(name, r.errors.map(e => e.message).join("; ")); process.exit(1); }
  out.programs[name] = { blob: Buffer.from(r.blob).toString("hex") };
}
process.stdout.write(JSON.stringify(out));
"""
    result = subprocess.run(["node", "--input-type=module", "-e", code, json.dumps(PROGRAMS)], cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def entry(name, ok, detail):
    return {"id": f"objects:{name}", "ok": bool(ok), "detail": str(detail)}


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    menu_cases.for_build(payload)
    request = compiled()
    built = script_hooks.build(request["include"], build=identify(payload).build)
    at = (script_hooks.MENU_STATE + built.symbols["MX_INTENS"]) & 0xFFFFFFFF
    out = []

    dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=2.0)
    menu_cases.watch_pins(dev)
    script_cases.install(dev, built, request["programs"], ["light"])
    before = menu_cases.duty(dev, 0.1)[0]
    dev.run(0.3)
    dark = menu_cases.duty(dev, 0.8)[0], dev.read(at, 1)[0]
    dev.run(0.6)
    light = menu_cases.duty(dev, 0.5)[0], dev.read(at, 1)[0]
    out.append(entry("light_off_and_on", dark[1] == 0 and max(dark[0].values()) == 0 and light[1] == 15 and min(light[0].values()) == 1.0
                     and not dev.m.asserts, f"before {before}, off {dark}, on {light}"))

    dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=2.0)
    script_cases.install(dev, built, request["programs"], ["clamp"])
    dev.run(0.3)
    repairs = dev.u32(built.symbols["objects_repairs"])
    out.append(entry("clamped_and_counted", dev.read(at, 1)[0] == 15 and repairs == 1 and not dev.m.asserts, f"INTENSITY {dev.read(at, 1)[0]}, repairs {repairs}"))

    dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=2.0)
    dev.m.uc.mem_write(at, bytes([200]))
    dev.call(built.symbols["objects_repair"])
    out.append(entry("repaired_at_start", dev.read(at, 1)[0] == 15 and dev.u32(built.symbols["objects_repairs"]) == 1 and not dev.m.asserts,
                     f"INTENSITY {dev.read(at, 1)[0]}, repairs {dev.u32(built.symbols['objects_repairs'])}"))
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
