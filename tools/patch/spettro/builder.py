"""Build an opt-in add-on against the freshly assembled Hacktribe runtime.

Only own instructions and hashes are emitted. Native bytes stay in the user's
image; unchanged self-copies serve as compatibility guards in patch format v1.
"""
import hashlib
import json
import struct
import sys

from tools.patch.arm import assemble
from tools.patch.script_hooks import build as runtime_build
from tools.patch.ramdecl import share
from . import CONTEXT_SIZE, HERE, source

BASE = 0xC0000000
ORIGIN, LIMIT = 0xC0148880, 0xC014FE00
COMMAND = 0xC002A628


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ui_definitions(symbols, blob):
    names = dict(BLIT='script_display_blit', SCREEN_MANAGER='SCREEN_MANAGER',
                 APP_STATE='APP_STATE', POOL='HOOK_POOL', ENTRY_SIZE='SCRIPT_ENTRY_SIZE',
                 ENTRY_STATE='SCRIPT_ENTRY_STATE', ARMED='SCRIPT_STATE_ARMED',
                 ENTRY_BLOB='SCRIPT_ENTRY_BLOB', ENTRY_STORE='SCRIPT_ENTRY_STORE',
                 DISPLAY='DISPLAY_FB', PART='HW_PART', INPUT_MASK_SITE='input_mask_app',
                 INPUT_MASK_GO='input_mask_go', BLOB_MAGIC='SCRIPT_MAGIC')
    values = {key: symbols[name] for key, name in names.items()}
    values.update(POOL_END=symbols['HOOK_POOL'] + symbols['SCRIPT_POOL_BYTES'],
                  BLOB_SIZE=len(blob), BLOB_CRC=struct.unpack_from('<I', blob, 12)[0])
    return '\n'.join(f'.equ UI_{key}, {value}' for key, value in values.items()) + '\n'


def guarded_copy(address, length, digest, over=None):
    at = address - BASE + 0x100
    return dict(file=at, copy=dict(file=at, length=length, expect=digest),
                expect=digest, over=over or [])


def build(include, blob, build_name='hacktribe'):
    if build_name != 'hacktribe':
        raise ValueError('Spettro currently supports only the tested Hacktribe Sampler ABI')
    runtime = runtime_build(include, build=build_name)
    s = runtime.symbols
    code = assemble(ui_definitions(s, blob) + source() + '\n' +
                    (HERE / 'ui_bridge.s').read_text(encoding='utf-8'), origin=ORIGIN)
    if ORIGIN + len(code.bytes) > LIMIT:
        raise ValueError('Spettro code exceeds its reserved FF area')
    replacements = {
        s['script_display_blit']: ('scope_ui_hook', bytes.fromhex('00c0a0e3')),
        s['input_mask_app']: ('scope_input_hook', bytes.fromhex('011081e3')),
    }
    changes = [dict(file=ORIGIN - BASE + 0x100, bytes=code.bytes.hex(),
                    expect=sha(b'\xff' * len(code.bytes)), note='Spettro ARM code and control words')]
    old_call = assemble('bl 0xC002D844', origin=COMMAND).bytes
    changes.append(dict(file=COMMAND - BASE + 0x100,
                        bytes=assemble(f'bl {code.symbols["scope_command_hook"]}', origin=COMMAND).bytes.hex(),
                        expect=sha(old_call), note='CommandTask retains the original call'))
    seen = set()
    for address, data in runtime.sections:
        over = []
        for site, (target, expected) in replacements.items():
            if address <= site < address + len(data):
                offset = site - address
                if data[offset:offset + 4] != expected:
                    raise ValueError(f'Runtime instruction changed at {site:#x}')
                over.append(dict(at=offset, bytes=assemble(f'b {code.symbols[target]}', origin=site).bytes.hex()))
                seen.add(site)
        change = guarded_copy(address, len(data), sha(data), over)
        change['note'] = 'Exact generated plugin runtime compatibility guard'
        changes.append(change)
    if seen != set(replacements):
        raise ValueError('Runtime hook is outside generated sections')
    fingerprints = json.loads((HERE / 'native-abi.json').read_text(encoding='utf-8'))
    for region in fingerprints['regions']:
        changes.append(guarded_copy(int(region['at'], 16), region['length'], region['sha256']))
    hooks = [dict(site=hex(COMMAND), kind='call', chain='spettro-command', position='after', swallow=False),
             dict(site=hex(s['script_display_blit']), kind='instruction', chain='spettro-display', position='before', swallow=False),
             dict(site=hex(s['input_mask_app']), kind='instruction', chain='spettro-input', position='replace', swallow=False)]
    # These are the actual changed ranges, not the much larger unchanged guards.
    spans = [(ORIGIN, len(code.bytes)), (COMMAND, 4)] + [(a, 4) for a in replacements]
    shares = [share(s['APP_STATE'], 4, 'script-runtime', 'open app pointer',
                    'tools/patch/script_hooks.py:RUNTIME'),
              share(s['HOOK_POOL'], s['SCRIPT_POOL_BYTES'], 'script-runtime',
                    'companion identity and store in the runtime-owned plugin pool',
                    'tools/patch/script_hooks.py:POOL')]
    patch = dict(format='gelumpe-patch', version=1, id='spettro', name='Spettro (experimentell)',
                 builds=['hacktribe'], changes=changes, ram=[], shares=shares, hooks=hooks,
                 startPhase=[dict(file=a - BASE + 0x100, length=n,
                                  why='CommandTask und Anzeige behalten den Originalpfad; ohne geöffnete App bleibt die Analyse aus.')
                             for a, n in spans])
    return dict(patch=patch, layout=dict(symbols=s, contextBytes=CONTEXT_SIZE,
                codeAddress=ORIGIN, codeBytes=len(code.bytes),
                entries={k: v for k, v in code.symbols.items() if k.startswith('scope_')},
                runtimeSections=[[a, len(d), sha(d)] for a, d in runtime.sections]))


if __name__ == '__main__':
    request = json.load(sys.stdin)
    result = build(request['include'], bytes.fromhex(request['plugin']), request.get('build', 'hacktribe'))
    print(json.dumps(result, ensure_ascii=False))
