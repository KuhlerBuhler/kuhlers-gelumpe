# SPDX-License-Identifier: GPL-2.0-only
"""Writes data/emu/node-results.json: every answer the case modules ask Node for (node_json.py), from this checkout.

Each module in tools/emu that asks Node has a node_requests() that makes all of its calls; this script runs them with
Node and writes what came back. Run it after a change to the compiler, the plugin contract, the presets or the map the
cases read; test/node-results.test.mjs runs it with --check and fails while the file is stale.

    tools/emu/.venv/bin/python tools/emu/node_results.py [--check]
"""
import argparse
import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tools" / "patch"), str(HERE)]

import node_json  # noqa: E402

ABOUT = "written by tools/emu/node_results.py, do not edit: what the emulator cases ask Node for, keyed by node_json.key"


def modules():
    """The modules of tools/emu with a node_requests()."""
    return sorted(p.stem for p in HERE.glob("*.py") if "\ndef node_requests(" in p.read_text(encoding="utf-8"))


def generate():
    node_json.recording = {}
    try:
        for name in modules():
            importlib.import_module(name).node_requests()
        results = node_json.recording
    finally:
        node_json.recording = None
    lines = [f"  {json.dumps(k)}: {json.dumps(results[k], ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"
             for k in sorted(results)]
    return "{\n  \"about\": " + json.dumps(ABOUT) + ",\n  \"results\": {\n" + ",\n".join("  " + line for line in lines) + "\n  }\n}\n"


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true", help="only compare with the file, write nothing; exit 1 when it differs")
    a = p.parse_args()
    text = generate()
    old = node_json.FILE.read_text(encoding="utf-8") if node_json.FILE.exists() else ""
    if a.check:
        # compared as data, so a checkout with other line ends is not stale
        fresh = json.loads(text)["results"]
        kept = json.loads(old)["results"] if old else {}
        if fresh != kept:
            print(f"{node_json.FILE.relative_to(ROOT).as_posix()} is stale: {len(fresh.keys() - kept.keys())} missing, "
                  f"{len(kept.keys() - fresh.keys())} unused, {sum(1 for k in fresh.keys() & kept.keys() if fresh[k] != kept[k])} changed; "
                  f"write it again with `{node_json.REGENERATE}`", file=sys.stderr)
            return 1
        return 0
    node_json.FILE.parent.mkdir(parents=True, exist_ok=True)
    node_json.FILE.write_text(text, encoding="utf-8", newline="\n")
    print(f"{node_json.FILE.relative_to(ROOT).as_posix()}: {len(json.loads(text)['results'])} results")
    return 0


if __name__ == "__main__":
    sys.exit(main())
