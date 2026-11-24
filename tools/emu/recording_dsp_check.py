"""Reconstruct the exact recording DSP patch from its own checked-in program."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(getattr(sys, '_MEIPASS', '') or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT))
from tools.dsp import dsp_extract
from tools.patch import recording_dsp as spec


def load_manifest(build='hacktribe'):
    suffix = '-synth' if build == 'synth' else ''
    manifest = json.loads((ROOT / f'data/patches/native-recording-dsp{suffix}.json').read_text())
    for name in ('tools/patch/recording_dsp.py', 'tools/patch/recording_dsp.s'):
        if manifest.get('sources', {}).get(name) != hashlib.sha256((ROOT / name).read_bytes()).hexdigest():
            raise ValueError('the recording DSP program is stale')
    return manifest


def canonical_patch(base, build='hacktribe'):
    config = spec.configuration(build)
    manifest = load_manifest(build)
    blocks = list(dsp_extract.parse(base, start=config['stream'], length=config['length']))
    changes = {change['file']: change for change in manifest['changes']}
    program = dict(code=bytes.fromhex(changes[spec.file_offset(config['final'] + 16)]['bytes'])[:spec.PROGRAM_SIZE],
                   hooks=[(address, bytes.fromhex(changes[spec.payload_offset(blocks, address)]['bytes']))
                          for address in config['hooks']])
    canonical = spec.build_patch(base, program, build)
    if canonical['changes'] != manifest['changes']:
        raise ValueError('the recording DSP manifest differs from its canonical boot-stream edits')
    return canonical
