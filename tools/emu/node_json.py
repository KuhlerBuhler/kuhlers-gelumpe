# SPDX-License-Identifier: GPL-2.0-only
"""What the case modules need from the JavaScript of this repository (compiled plugins, field lists), without Node.

The app ships the emulator frozen (build-sidecar.mjs), and its users have no Node. So every answer a case module once got
from `node --input-type=module -e CODE ARGS...` is kept in data/emu/node-results.json, keyed by the sha256 of the code and
its arguments; tools/emu/node_results.py writes that file and test/node-results.test.mjs fails when it is stale.

run() looks the answer up there first. Only from a checkout with Node on PATH does a missing answer run Node, so a new
case still works while it is written; frozen, or without Node, a missing answer is an error that names the file and the
command that writes it. GELUMPE_NODE_RESULTS=strict makes a missing answer an error with Node too (the CI check uses it,
so a case whose answer the file lacks fails there and not in the app).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = Path(getattr(sys, "_MEIPASS", "") or REPO)     # the app's frozen service unpacks its data files here
FILE = DATA / "data" / "emu" / "node-results.json"
REGENERATE = "tools/emu/.venv/bin/python tools/emu/node_results.py"

# node_results.py sets this: every call runs Node and is noted here, the file is not read
recording = None
_results = None


def key(code, args):
    return hashlib.sha256(json.dumps([code, *args], ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _known():
    global _results
    if _results is None:
        _results = json.loads(FILE.read_text(encoding="utf-8"))["results"] if FILE.exists() else {}
    return _results


def _node(code, args):
    done = subprocess.run(["node", "--input-type=module", "-e", code, *args], cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8")
    if done.returncode != 0:
        raise RuntimeError(f"node ended with {done.returncode}: {done.stderr.strip()}")
    return json.loads(done.stdout)


def run(code, *args):
    """The JSON that `node --input-type=module -e code args...` prints in the repository root."""
    args = [str(a) for a in args]
    k = key(code, args)
    if recording is not None:
        recording[k] = _node(code, args)
        return recording[k]
    known = _known()
    if k in known:
        return known[k]
    frozen = getattr(sys, "frozen", False)
    if frozen or os.environ.get("GELUMPE_NODE_RESULTS") == "strict" or not shutil.which("node"):
        why = "the app's emulator runs without Node" if frozen else "strict" if shutil.which("node") else "Node is not on PATH"
        raise RuntimeError(f"{FILE.relative_to(DATA).as_posix()} has no result {k[:12]} ({why}); "
                           f"write the file again with `{REGENERATE}` and commit it")
    return _node(code, args)


INCLUDE = """
import { asmInclude } from "./src/script/arm-tables.mjs";
process.stdout.write(JSON.stringify(asmInclude()));
"""

PROGRAM = """
import { compile } from "./src/script/compiler.mjs";
import { markProbed } from "./src/script/blob.mjs";
const [name, source, probed] = process.argv.slice(1);
const r = compile(source, { name });
process.stdout.write(JSON.stringify(r.ok
  ? { blob: Buffer.from(probed ? markProbed(r.blob) : r.blob).toString("hex"), symbols: r.info.symbols }
  : { errors: r.errors.map(e => e.message).join("; ") }));
"""


def include():
    """The assembler include of the plugin contract (src/script/arm-tables.mjs)."""
    return run(INCLUDE)


def program(name, source, probed=False):
    """One plugin from the compiler of this checkout: {blob (hex), symbols}, or {errors} when it does not compile.
    `probed` marks the block as probed by the editor (src/script/blob.mjs)."""
    return run(PROGRAM, name, source, "probed" if probed else "")


def compiled(programs, probed=False):
    """The include and the blobs and symbols of the programs ({name: source}); a program that does not compile is an error."""
    out = {"include": include(), "programs": {}}
    for name, source in programs.items():
        r = program(name, source, probed)
        if "errors" in r:
            raise RuntimeError(f"{name}: {r['errors']}")
        out["programs"][name] = r
    return out
