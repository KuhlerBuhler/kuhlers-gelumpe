"""Run every node snippet the full check's cases need and write the results for the frozen app (node_json.py).

    python record_node_json.py OUT.json

build-sidecar.mjs runs this before PyInstaller. CALLS holds, per case module, each call of a function that runs a snippet,
written as in the module and evaluated in its namespace, so the app finds every result by the same key.
test/node-json.test.mjs holds that every such call of a case is listed here. Snippets at module level run on import.
"""
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import node_json  # noqa: E402

CALLS = {
    "global_cases": ['tree()', 'edit.compiled({"global": PROGRAM})'],
    "objects_cases": ['compiled()'],
    "pattern_parts_cases": ['fields()', 'edit.compiled({"values": PROGRAM})'],
    "plugin_api15_cases": ['edit.compiled({"api15": PROGRAM})'],
    "plugin_api18_cases": ['edit.compiled({"api18": PROGRAM})'],
    "plugin_api19_cases": ['edit.compiled(PROGRAMS)'],
    "plugin_catalog15_cases": ['edit.compiled({"stepcopy": PRESETS["stepcopy"]})', 'edit.compiled({name: PRESETS[name] for name in PLUGINS})'],
    "plugin_edit_cases": ['compiled({"edit": PROGRAMS["edit"].replace("LEVEL", "0")})',
                          'compiled({"edit": PROGRAMS["edit"].replace("LEVEL", str(level))})',
                          'compiled({k: v for k, v in PROGRAMS.items() if k != "edit"})'],
    "testmode_cases": ['compiled()'],
    "timer_cases": ['compiled()'],
}
# The values a name the case reads from the emulator can take: level is the LEVEL the knob left in a part (0 to 127).
FREE = {"level": range(128)}


def record():
    for name, calls in CALLS.items():
        space = vars(importlib.import_module(name))
        for call in calls:
            free = [k for k in FREE if k not in space and k in call]
            if not free:
                eval(call, space)
            for k in free:
                for value in FREE[k]:
                    eval(call, {**space, k: value})
    return node_json.RECORDED


if __name__ == "__main__":
    Path(sys.argv[1]).write_text(json.dumps(record(), sort_keys=True))
