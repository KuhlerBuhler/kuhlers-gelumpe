"""Emulator cases for API 26 plugin popups: a shared firmware-style popup for background plugins only.

The cases cover absolute drawing and clipping, timer and EXIT dismissal, replacement between plugins and the firmware,
and refusal while an app owns the display. They run through the same frame and input hooks as a plugin on the device.

    tools/emu/.venv/bin/python tools/emu/plugin_api26_cases.py --vsb PATCHED.VSB [--flash FLASH.BIN]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from tools.patch import script_hooks  # noqa: E402
import menu_cases  # noqa: E402
import plugin_edit_cases as edit  # noqa: E402
import script_cases  # noqa: E402
from firmware import identify  # noqa: E402
from machine import load_flash  # noqa: E402

PROGRAMS = {
    "geometry": """korg.onEvent("ready", () => {
  korg.display.popup.begin();
  korg.display.pixel(2, 14, 1);
  korg.display.pixel(125, 47, 1);
  korg.display.pixel(127, 63, 1);
  korg.display.popup.timeout(0);
  korg.display.popup.show();
});""",
    "timed": """korg.onEvent("ready", () => {
  korg.display.popup.begin();
  korg.display.pixel(20, 20, 1);
  korg.display.popup.timeout(160);
  korg.display.popup.show();
});""",
    "indefinite": """korg.onEvent("ready", () => {
  korg.display.popup.begin();
  korg.display.pixel(20, 20, 1);
  korg.display.popup.timeout(0);
  korg.display.popup.show();
});""",
    "default": """korg.onEvent("ready", () => {
  korg.display.popup.begin();
  korg.display.pixel(20, 20, 1);
  korg.display.popup.show();
});""",
    "first": """korg.onEvent("ready", () => {
  korg.display.popup.begin();
  korg.display.pixel(17, 25, 1);
  korg.display.popup.timeout(0);
  korg.display.popup.show();
});""",
    "second": """korg.onEvent("ready", () => {
  korg.display.popup.begin();
  korg.display.pixel(29, 25, 1);
  korg.display.popup.timeout(0);
  korg.display.popup.show();
});""",
    "native_to_plugin": """korg.onEvent("ready", () => {
  korg.parts[0].level = 33;
  korg.after(120, () => {
    korg.display.popup.begin();
    korg.display.pixel(20, 20, 1);
    korg.display.popup.timeout(0);
    korg.display.popup.show();
  });
});""",
    "plugin_to_native": """korg.onEvent("ready", () => {
  korg.display.popup.begin();
  korg.display.pixel(20, 20, 1);
  korg.display.popup.timeout(0);
  korg.display.popup.show();
  korg.after(120, () => { korg.parts[0].level = 33; });
});""",
    "app": """korg.app("Popup", "TOOLS");
korg.onEvent("open", () => {
  korg.display.popup.begin();
  korg.display.pixel(20, 20, 1);
  korg.display.popup.show();
});""",
}


def node_requests():
    """Every answer this module asks Node for (node_json.py); tools/emu/node_results.py keeps them in its file."""
    edit.compiled(PROGRAMS)


def entry(name, ok, detail):
    return {"id": f"plugin_api26:{name}", "ok": bool(ok), "detail": str(detail)}


def pixel(frame, x, y):
    return frame[(y >> 3) * 128 + x] >> (y & 7) & 1


def popup_active(dev, built):
    return dev.u32(built.symbols["popup_active"])


def native_window(dev):
    return dev.screen()["window"] or 0


def boot(payload, flash, built, programs, names):
    dev = menu_cases.boot(payload, flash, files=menu_cases.CARD_FOLDER, adapter=True, seconds=2.0)
    entries = script_cases.install(dev, built, programs, names)
    return dev, entries


def cases(vsb, flash=None):
    payload = vsb[0x100:]
    menu_cases.for_build(payload)
    request = edit.compiled(PROGRAMS)
    built = script_hooks.build(request["include"], build=identify(payload).build)
    programs = request["programs"]
    out = []

    dev, _ = boot(payload, flash, built, programs, ["geometry"])
    dev.run(0.25)
    frame = dev.fb()
    geometry = (popup_active(dev, built) == 1 and native_window(dev) == 0 and dev.screen()["number"] == 1
                and pixel(frame, 2, 14) == 1 and pixel(frame, 125, 47) == 1
                and pixel(frame, 1, 14) == 1 and pixel(frame, 126, 14) == 1
                and pixel(frame, 30, 13) == 1 and pixel(frame, 30, 48) == 1)
    out.append(entry("absolute_content_and_native_outline", geometry,
                     f"active {popup_active(dev, built)}, screen {dev.screen()}, native window {native_window(dev)}, "
                     f"content {pixel(frame, 2, 14), pixel(frame, 125, 47)}, "
                     f"outline {pixel(frame, 1, 14), pixel(frame, 126, 14), pixel(frame, 30, 13), pixel(frame, 30, 48)}"))

    dev, _ = boot(payload, flash, built, programs, ["timed"])
    dev.run(0.08)
    early = popup_active(dev, built)
    dev.run(0.24)
    late = popup_active(dev, built)
    out.append(entry("custom_timeout", early == 1 and late == 0, f"active at 80 ms: {early}, at 320 ms: {late}"))

    dev, _ = boot(payload, flash, built, programs, ["default"])
    dev.run(1.8)
    before_default = popup_active(dev, built)
    dev.run(0.4)
    after_default = popup_active(dev, built)
    out.append(entry("default_timeout", before_default == 1 and after_default == 0,
                     f"active at 1.8 s: {before_default}, at 2.2 s: {after_default}"))

    dev, _ = boot(payload, flash, built, programs, ["indefinite"])
    dev.run(0.2)
    before_exit = popup_active(dev, built)
    menu_cases.press(dev, "exit", wait=0.2)
    after_exit = popup_active(dev, built)
    out.append(entry("exit_closes_plugin_popup", before_exit == 1 and after_exit == 0 and dev.screen()["number"] == 1,
                     f"active before EXIT: {before_exit}, after: {after_exit}, screen {dev.screen()}"))

    dev, _ = boot(payload, flash, built, programs, ["first", "second"])
    dev.run(0.25)
    frame = dev.fb()
    replaced = popup_active(dev, built) == 1 and pixel(frame, 17, 25) == 0 and pixel(frame, 29, 25) == 1
    out.append(entry("plugin_replaces_plugin", replaced,
                     f"active {popup_active(dev, built)}, first pixel {pixel(frame, 17, 25)}, second pixel {pixel(frame, 29, 25)}"))

    dev, _ = boot(payload, flash, built, programs, ["native_to_plugin"])
    dev.run(0.7)
    native_to_plugin = popup_active(dev, built) == 1 and native_window(dev) == 0 and pixel(dev.fb(), 20, 20) == 1
    out.append(entry("plugin_replaces_firmware_popup", native_to_plugin,
                     f"active {popup_active(dev, built)}, native window {native_window(dev)}, marker {pixel(dev.fb(), 20, 20)}"))

    dev, _ = boot(payload, flash, built, programs, ["plugin_to_native"])
    dev.run(0.7)
    plugin_to_native = popup_active(dev, built) == 0 and native_window(dev) != 0
    out.append(entry("firmware_replaces_plugin_popup", plugin_to_native,
                     f"active {popup_active(dev, built)}, native window {native_window(dev)}"))

    dev, app_entries = boot(payload, flash, built, programs, ["app"])
    dev.run(0.2)
    script_cases.open_app(dev, menu_cases.GROUP_TOOLS)
    dev.run(0.2)
    app_refused = popup_active(dev, built) == 0 and dev.screen()["number"] == 1
    out.append(entry("app_cannot_open_plugin_popup", app_refused,
                     f"active {popup_active(dev, built)}, screen {dev.screen()}, app state {dev.u32(app_entries['app'] + 12)}"))
    return out


def main():
    import lifetime
    lifetime.load_gate()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vsb", required=True, type=Path)
    parser.add_argument("--flash", type=Path)
    args = parser.parse_args()
    result = cases(args.vsb.read_bytes(), load_flash(args.flash) if args.flash else None)
    print(json.dumps(result, indent=1))
    sys.exit(0 if all(case["ok"] for case in result) else 1)


if __name__ == "__main__":
    main()
