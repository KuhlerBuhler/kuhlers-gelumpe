"""Reconstruct the exact recording DSP patch from its own checked-in program."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(getattr(sys, '_MEIPASS', '') or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT))
from tools.dsp import dsp_extract
from tools.patch import recording_dsp as spec


def load_manifest():
    manifest = json.loads((ROOT / 'data/patches/native-recording-dsp.json').read_text())
    for name in ('tools/patch/recording_dsp.py', 'tools/patch/recording_dsp.s'):
        if manifest.get('sources', {}).get(name) != hashlib.sha256((ROOT / name).read_bytes()).hexdigest():
            raise ValueError('the recording DSP program is stale')
    return manifest


def canonical_patch(base):
    manifest = load_manifest()
    changes = {change['file']: change for change in manifest['changes']}
    program = dict(code=bytes.fromhex(changes[spec.file_offset(spec.APPEND)]['bytes'])[:spec.PROGRAM_SIZE],
                   hooks=[(address, bytes.fromhex(changes[dsp_extract.vsb_offset(base, address)]['bytes']))
                          for address in spec.HOOK_HASHES])
    canonical = spec.build_patch(base, program)
    if canonical['changes'] != manifest['changes']:
        raise ValueError('the recording DSP manifest differs from its canonical boot-stream edits')
    return canonical
