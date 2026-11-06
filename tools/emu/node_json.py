"""The JSON a node snippet of a case prints: compiled plugins, fields of the contract, the object tree.

In a checkout node runs the snippet. The frozen app ships no node, so the sidecar build runs every snippet once
(record_node_json.py) and bundles the results as node-results.json; frozen, run() reads them from there.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILE = "node-results.json"
# Every result this process got from node, by key: what record_node_json.py writes.
RECORDED = {}
_bundled = None


def key(code, args):
    return hashlib.sha256(json.dumps([code, *args]).encode()).hexdigest()


def bundled():
    global _bundled
    if _bundled is None:
        _bundled = json.loads((Path(getattr(sys, "_MEIPASS")) / FILE).read_text())
    return _bundled


def run(code, *args):
    """Run `node --input-type=module -e code args` in the checkout's root and parse what it prints."""
    k = key(code, args)
    if getattr(sys, "frozen", False):
        results = bundled()
        if k not in results:
            raise RuntimeError(f"no recorded node result {k[:12]} in the app: the sidecar build did not run this snippet")
        return results[k]
    out = subprocess.run(["node", "--input-type=module", "-e", code, *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    RECORDED[k] = json.loads(out)
    return RECORDED[k]
