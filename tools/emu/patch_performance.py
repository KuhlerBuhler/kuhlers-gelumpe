# SPDX-License-Identifier: GPL-2.0-only
"""Capture repeatable ARM work and compare private full-set check directories.

--capture DIR --out DIR/profile.json collects originals and patched copies.
--baseline DIR --candidate DIR --out REPORT.json --phase baseline compares captures.
Firmware and generated files stay outside the checkout. A missing required result fails.
"""
import argparse
import collections
import concurrent.futures
import hashlib
import inspect
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BUILDS = ('hacktribe', 'stock', 'synth')
CORE = ('idle', 'playing', 'playing-keyboard', 'sequencer-four-note-long-ties')
APPS = ('mandelbrot', 'life', 'pong')
INSTALLED_APPS = ('blechclicker', 'settimer', 'snake', 'tetris', 'life', 'pong', 'simon', 'mandelbrot')
BACKGROUND_PLUGINS = ('lauflicht', 'pulsieren', 'bpmglide', 'taktblinker')
REPEATS = 3
SECONDS = 2
MUL_MIN_REDUCTION_PERCENT = 19.83
APP_PROTOCOL = {'warmupFrames': 8, 'openClockMs': 0xB1EC, 'boundary': 'frame_return',
                'clockInput': 'native-clock-state-at-millis-entry',
                'installedApps': list(INSTALLED_APPS), 'backgroundPlugins': list(BACKGROUND_PLUGINS)}


class BlockCounter:
    def __init__(self, uc):
        import unicorn
        self.active = False
        self.instructions = 0
        self.hook = uc.hook_add(unicorn.UC_HOOK_BLOCK, self.block)
        uc.ctl_flush_tb()

    def block(self, _uc, _at, size, _data):
        if self.active:
            self.instructions += size // 4

    def measure(self, action):
        self.instructions = 0
        self.active = True
        try:
            result = action()
        finally:
            self.active = False
        return result, self.instructions


def require(ok, message):
    if not ok:
        raise ValueError(message)


def app_workload(programs, capacity):
    expected = set(INSTALLED_APPS) | set(BACKGROUND_PLUGINS) | {'gifplayer'}
    require(set(programs) == expected, 'all named plugin inputs required')
    require(len(INSTALLED_APPS) <= capacity, 'app workload exceeds native capacity')
    require(all(programs[name]['info'].get('app') is not None for name in INSTALLED_APPS), 'app metadata missing')
    require(all(programs[name]['info'].get('app') is None for name in BACKGROUND_PLUGINS), 'background plugin became an app')
    return INSTALLED_APPS


def run_completed_frames(dev, built, frames):
    machine, uc = dev.m, dev.m.uc
    require(isinstance(frames, int) and frames > 0, 'positive frame count required')
    frame_at = built.layout['runtime'] + built.symbols['SCRIPT_CONTROL_FRAMES']
    active_at = built.layout['runtime'] + built.symbols['SCRIPT_CONTROL_FRAME_ACTIVE']
    boundary = built.symbols['frame_return']
    previous, done = machine.u32(frame_at), 0
    deadline = machine.time_ns + 5e9
    uc.ctl_set_exits([*machine.ENTRIES, boundary])
    uc.ctl_flush_tb()
    try:
        while done < frames and machine.time_ns < deadline and not machine.asserts:
            if uc.reg_read(machine.A.UC_ARM_REG_PC) == boundary:
                current = machine.u32(frame_at)
                if current != previous:
                    require(current == (previous + 1) & 0xffffffff, 'missed frame boundary')
                    require(machine.u32(active_at) == 0, 'frame still active')
                    previous, done = current, done + 1
                    if done == frames:
                        break
                machine.step_over(boundary)
            else:
                machine.run_slice(limit=deadline)
            machine.lines()
            machine.irq()
    finally:
        uc.ctl_set_exits(list(machine.ENTRIES))
        uc.ctl_flush_tb()
    require(done == frames, 'completed frame boundary missing')


def validate_capture(data):
    require(data.get('format') == 'blech-performance' and data.get('version') == 4, 'invalid capture format')
    require(data.get('appProtocol') == APP_PROTOCOL, 'different app input protocol')
    require(data.get('repeats') == REPEATS and data.get('seconds') == SECONDS, 'different workload duration or repeats')
    require(set(data.get('builds', {})) == set(BUILDS), 'all three builds required')
    require(bool(data.get('method')) and bool(data.get('programsSha256')), 'measurement identity missing')
    for build, item in data['builds'].items():
        require(bool(item.get('inputSha256')) and bool(item.get('outputSha256')), f'{build}: firmware hashes missing')
        loader = item.get('loader', {})
        repeats = loader.get('repeats', [])
        require(len(repeats) == REPEATS, 'loader needs three repetitions')
        for result in repeats:
            plugins = result.get('plugins', [])
            expected_plugins = set(INSTALLED_APPS) | set(BACKGROUND_PLUGINS) | {'gifplayer'}
            require(len(plugins) == len(expected_plugins) and {p.get('plugin') for p in plugins} == expected_plugins, 'all named loader inputs required')
            require(all(isinstance(p.get('instructions'), int) and p['instructions'] > 0 for p in plugins), 'invalid loader count')
            require(result.get('totalInstructions') == sum(p['instructions'] for p in plugins), 'inconsistent loader total')
        require(all(r == repeats[0] for r in repeats), 'non-reproducible loader counts')
        require(loader.get('totalInstructions') == repeats[0]['totalInstructions'] and loader.get('maxInstructions') == max(r['totalInstructions'] for r in repeats), 'loader summary differs')
        if 'sysex' in item:
            validate_sysex(item)
        for variant in ('original', 'patched'):
            runs = item.get(variant, [])
            require(len(runs) == REPEATS, f'{build}/{variant}: three repetitions required')
            expected = None
            for run in runs:
                rows = run.get('scenarios', [])
                names = [r.get('scenario') for r in rows]
                required = list(CORE) + (['blech-menu', 'closed-apps', *('app-' + p for p in APPS), 'background-plugins'] if variant == 'patched' else [])
                require(names == required, 'scenes missing, duplicated or out of order')
                require(expected is None or names == expected, 'repetitions use different scenes')
                expected = names
                for row in rows:
                    name = row['scenario']
                    require(isinstance(row.get('instructions'), int) and row['instructions'] > 0, 'invalid instruction count')
                    elapsed = row.get('deviceNs', 0)
                    require(isinstance(elapsed, (int, float)) and math.isfinite(elapsed) and elapsed > 0, 'invalid device time')
                    require(row.get('asserts') == [], 'firmware assertion')
                    require(row.get('transport') == (1 if name in CORE[1:] else 0), f'{name}: unexpected transport')
                    if name in CORE:
                        require(abs(elapsed - SECONDS * 1e9) <= 1e6, 'scene duration differs')
                    if name.startswith('app-'):
                        require(row.get('semantic', {}).get('frames') == 50 and row['semantic'].get('fault') == 0, 'incomplete app window or plugin fault')
                        require(row['semantic'].get('frameActive') == 0, 'incomplete app frame')
                        for key in ('initialStateSha256', 'stateSha256'):
                            require(isinstance(row['semantic'].get(key), str) and len(row['semantic'][key]) == 64,
                                    'app variable state missing')
            for name in expected:
                rows = [next(r for r in run['scenarios'] if r['scenario'] == name) for run in runs]
                require(len({r['instructions'] for r in rows}) == 1, f'{build}/{variant}/{name}: non-reproducible count')
                require(all(r.get('byPatch') == rows[0].get('byPatch') for r in rows), 'non-reproducible patch counters')
                require(all(r.get('semantic') == rows[0].get('semantic') for r in rows), 'non-reproducible app state')


def med(item, variant, scene, key='instructions'):
    values = [next(row for row in run['scenarios'] if row['scenario'] == scene)[key] for run in item[variant]]
    return statistics.median(values)


def validate_sysex(item):
    from sysex_bench import PROTOCOL
    value = item['sysex']
    require(value.get('protocol') == PROTOCOL, 'incomplete native transfer protocol')
    require(value.get('firmwareSha256') == item['outputSha256'], 'transfer firmware differs from checked build')
    for key in ('method', 'codeSha256', 'vectorsSha256', 'resultsSha256', 'ioSha256'):
        require(isinstance(value.get(key), str) and len(value[key]) == 64
                and all(c in '0123456789abcdef' for c in value[key]), f'invalid transfer {key}')
    require(value.get('maxBlock') == 32768 and value.get('bufferStart') == 0xc0191100
            and value.get('fileArea') == [0xc019f000, 0xc01a0000], 'transfer layout or maximum block changed')
    require(isinstance(value.get('bufferEnd'), int) and 0xc0191100 < value['bufferEnd'] <= 0xc019f000, 'invalid transfer buffer end')
    require(isinstance(value.get('instructions'), int) and value['instructions'] > 0
            and isinstance(value.get('cases'), int) and value['cases'] >= 250, 'transfer work missing')
    rows = value.get('repeats', [])
    require(len(rows) == REPEATS, 'three native transfer repetitions required')
    for row in rows:
        require(row == {key: value[key] for key in ('instructions', 'cases', 'vectorsSha256', 'resultsSha256', 'ioSha256')},
                'native transfer repetitions differ')


def validate_inherited(baseline, inherited):
    require(inherited.get('format') == 'blech-integrated-acceptance' and inherited.get('version') == 1,
            'invalid inherited acceptance')
    require(inherited.get('inheritedPhases') == ['pad', 'loader', 'mul']
            and inherited.get('codeBudgetBytes') == 112, 'unapproved inherited phases or code budget')
    profile = {**baseline, 'builds': {build: {k: v for k, v in item.items() if k != 'sysex'}
                                   for build, item in baseline['builds'].items()}}
    digest = hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    require(digest == inherited.get('baselineDigest'), 'inherited acceptance belongs to another baseline')
    expected = {'2026-10-20-pad-geometrie-zahlen.json', '2026-10-20-arm-optimierungen-zahlen.json',
                '2026-10-21-patch-effizienz-basis-zahlen.json'}
    evidence = inherited.get('evidence', [])
    require(len(evidence) == len(expected) and {r['file'] for r in evidence} == expected,
            'historical acceptance evidence missing')
    for row in evidence:
        path = ROOT / 'docs/messungen' / row['file']
        require(hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256'], 'historical acceptance changed')
    registered = json.loads((ROOT / 'docs/messungen/2026-10-21-patch-effizienz-basis-zahlen.json').read_text())
    require(inherited.get('firmwareSourceCommit') == registered['firmwareSourceCommit'],
            'different integrated firmware source')


def compare(baseline, candidate, phase, inherited=None):
    require(phase in ('baseline', 'pad', 'loader', 'decoder', 'mul', 'sysex', 'combined'), 'unknown phase')
    require(baseline['method'] == candidate['method'] and baseline['programsSha256'] == candidate['programsSha256'], 'different measurement or plugin input')
    if inherited is not None:
        require(phase == 'combined', 'inherited acceptance requires combined comparison')
        validate_inherited(baseline, inherited)
    results = {}
    for build in BUILDS:
        old, new = baseline['builds'][build], candidate['builds'][build]
        require(old['inputSha256'] == new['inputSha256'], 'different original firmware')
        for scene in CORE:
            require(med(old, 'original', scene) == med(new, 'original', scene), 'original workload differs')
        old_names = [r['scenario'] for r in old['patched'][0]['scenarios']]
        new_names = [r['scenario'] for r in new['patched'][0]['scenarios']]
        require(old_names == new_names, 'different measured scenes')
        rows = {}
        for name in new_names:
            before, after = med(old, 'patched', name), med(new, 'patched', name)
            rows[name] = {'baselineInstructions': before, 'candidateInstructions': after, 'ratio': after / before,
                          'maxInstructions': max(next(r for r in run['scenarios'] if r['scenario'] == name)['instructions'] for run in new['patched'])}
            old_row = next(r for r in old['patched'][0]['scenarios'] if r['scenario'] == name)
            new_row = next(r for r in new['patched'][0]['scenarios'] if r['scenario'] == name)
            if name.startswith('app-'):
                require(old_row.get('semantic') == new_row.get('semantic'), f'{build}/{name}: app state or framebuffer differs')
            if name != CORE[3] and not name.startswith('app-'):
                require(after <= before * 1.01, f'{build}/{name}: ordinary regression exceeds 1 percent')
        if phase in ('pad', 'combined'):
            require(med(new, 'patched', CORE[3]) <= med(new, 'original', CORE[3]) * 1.05, f'{build}: long ties exceed original by 5 percent')
            ram_budget = -19456 if inherited else (0 if build == 'synth' else 1024)
            code_budget = inherited['codeBudgetBytes'] if inherited else (0 if build == 'synth' else 768)
            require(new['footprint']['ramBytes'] <= old['footprint']['ramBytes'] + ram_budget, 'pad RAM budget exceeded')
            require(new['footprint']['codeDataBytes'] <= old['footprint']['codeDataBytes'] + code_budget, 'pad code budget exceeded')
            if inherited:
                require(new['footprint']['largestGap'] >= max(19456, old['footprint']['largestGap']), 'contiguous free space shrank')
        if phase in ('loader', 'decoder', 'mul'):
            require(new['footprint']['codeDataBytes'] <= old['footprint']['codeDataBytes'], 'VM code grew')
        if phase in ('loader', 'combined'):
            require('loader' in old and 'loader' in new, 'loader evidence missing')
            require(new['loader']['totalInstructions'] <= old['loader']['totalInstructions'] * (1 if inherited else .30), 'loader target not reached')
        if phase in ('decoder', 'combined'):
            for plugin in ('mandelbrot', 'life'):
                name = 'app-' + plugin
                require(name in new_names, 'app evidence missing')
                old_runtime = statistics.median(next(r for r in run['scenarios'] if r['scenario'] == name)['byPatch'].get('script-runtime', 0) for run in old['patched'])
                new_runtime = statistics.median(next(r for r in run['scenarios'] if r['scenario'] == name)['byPatch'].get('script-runtime', 0) for run in new['patched'])
                require(old_runtime > 0 and 0 < new_runtime <= old_runtime * .97, 'decoder target not reached')
        if phase in ('mul', 'combined') and inherited is None:
            require('mul' in old and 'mul' in new, 'MUL microbenchmark evidence missing')
            for evidence in (old['mul'], new['mul']):
                mean = evidence.get('meanInstructions')
                require(isinstance(mean, (int, float)) and math.isfinite(mean) and mean > 0,
                        'invalid MUL instruction count')
                require(evidence.get('resultsMatch') is True and evidence.get('pairs', 0) >= 2225,
                        'MUL numeric comparison missing')
            require(old['mul'].get('vectorsSha256') == new['mul'].get('vectorsSha256')
                    and isinstance(old['mul'].get('vectorsSha256'), str)
                    and len(old['mul']['vectorsSha256']) == 64, 'different MUL vectors')
            require(new['mul']['meanInstructions'] <= old['mul']['meanInstructions'] *
                    (1 - MUL_MIN_REDUCTION_PERCENT / 100), 'MUL target not reached')
            require(all(rows.get('app-' + p, {}).get('ratio', math.inf) <= 1.01 for p in APPS), 'app regression exceeds 1 percent')
        if phase in ('sysex', 'combined'):
            require('sysex' in old and 'sysex' in new, 'full transfer evidence missing')
            validate_sysex(old)
            validate_sysex(new)
            for key in ('method', 'protocol', 'cases', 'vectorsSha256', 'resultsSha256', 'ioSha256'):
                require(old['sysex'][key] == new['sysex'][key], f'different transfer {key}')
            require(new['sysex']['maxBlock'] == old['sysex']['maxBlock'] == 32768, 'maximum block changed')
            require(new['sysex']['bufferEnd'] <= old['sysex']['bufferEnd'] - 19456, 'contiguous buffer saving missing')
            require(new['sysex']['instructions'] <= old['sysex']['instructions'] * 1.01, 'transfer regression exceeds 1 percent')
            require(all(row['ratio'] <= 1.01 for row in rows.values()), 'ordinary or app regression exceeds 1 percent')
        if phase == 'combined' and build != 'synth':
            require(new['footprint']['occupiedBytes'] < old['footprint']['occupiedBytes'], 'no net sampler space gain')
        results[build] = rows
    return {'ok': True, 'phase': phase, 'builds': results,
            **({'inheritedPhases': inherited['inheritedPhases']} if inherited else {}),
            **({'mulMinimumReductionPercent': MUL_MIN_REDUCTION_PERCENT}
               if phase in ('mul', 'combined') else {})}


def capture_worker(folder, build, variant):
    sys.path[:0] = [str(ROOT), str(ROOT / 'tools/emu'), str(ROOT / 'tools/patch')]
    import struct
    import unicorn
    from tools.patch import script_hooks, dice
    from menu_cases import boot, SWITCH_SCREEN
    from script_cases import install
    info = json.loads((folder / 'sets.json').read_text())['builds'][build]
    raw = (folder / info[variant if variant == 'original' else 'patched']).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == info['inputSha256' if variant == 'original' else 'outputSha256'], 'firmware hash differs from checked set')
    payload = raw[256:]
    built = script_hooks.build((folder / 'contract.inc').read_text(), build=build)
    symbols = built.symbols
    if variant == 'patched':
        require(all(payload[at - 0xc0000000:at - 0xc0000000 + len(data)] == data for at, data in built.sections), 'generated runtime differs from checked firmware')
    dice.use_build(build)
    _, _, dice_symbols = dice.build_code()
    dev = boot(payload, adapter=True, seconds=3)
    machine, uc = dev.m, dev.m.uc
    counts = collections.Counter()
    active = False
    def block(_uc, at, size, _data):
        if active:
            counts[(at, size)] += 1
    uc.hook_add(unicorn.UC_HOOK_BLOCK, block)
    intervals = [(0xbfffff00 + s['file'], 0xbfffff00 + s['file'] + s['length'], s['patch']) for s in info['spans']
                 if any(run['start'] <= 0xbfffff00 + s['file'] and 0xbfffff00 + s['file'] + s['length'] <= run['end'] for run in info['freeRuns'])]
    results = []
    def measure(scene, frames=None, entry=None, program=None):
        nonlocal active
        counts.clear()
        frame_at = built.layout['runtime'] + symbols['SCRIPT_CONTROL_FRAMES']
        before = machine.u32(frame_at) if frames else 0
        if frames:
            variables = machine.u32(entry + symbols['SCRIPT_ENTRY_VARS'])
            initial_state = hashlib.sha256(uc.mem_read(variables, program['info']['vars'] * 4)).hexdigest()
        t0 = machine.time_ns
        uc.ctl_flush_tb()
        active = True
        if frames:
            run_completed_frames(dev, built, frames)
        else:
            dev.run(SECONDS)
        active = False
        by_patch = collections.Counter()
        for (at, size), n in counts.items():
            for start, end, label in intervals:
                if start <= at and at + size <= end:
                    by_patch[label] += size // 4 * n
                    break
        row = {'scenario': scene, 'instructions': sum(size // 4 * n for (_, size), n in counts.items()),
               'deviceNs': machine.time_ns - t0, 'transport': machine.u32(symbols['HW_TRANSPORT']), 'asserts': list(machine.asserts), 'byPatch': dict(by_patch)}
        if frames:
            variables = machine.u32(entry + symbols['SCRIPT_ENTRY_VARS'])
            keep = {'head', 'tail', 'pending', 'done', 'at', 'tile', 'n', 'genRow', 'computing', 'paintAt', 'soupAt'}
            row['semantic'] = {'frames': machine.u32(frame_at) - before, 'fault': machine.u32(entry + symbols['SCRIPT_ENTRY_FAULT']),
                'frameActive': machine.u32(built.layout['runtime'] + symbols['SCRIPT_CONTROL_FRAME_ACTIVE']),
                'initialStateSha256': initial_state,
                'stateSha256': hashlib.sha256(uc.mem_read(variables, program['info']['vars'] * 4)).hexdigest(),
                'framebufferSha256': hashlib.sha256(dev.fb()).hexdigest(),
                'progress': {name: machine.u32(variables + spec['slot'] * 4) for name, spec in program['info']['symbols'].items() if name in keep}}
        require(not machine.asserts, f'{build}/{variant}/{scene}: firmware assertion')
        results.append(row)
    measure('idle')
    pattern = machine.u32(dice_symbols['PATPTR']) + 4
    require(pattern > 4, 'pattern pointer unavailable')
    uc.mem_write(pattern + 37, bytes([3]))
    for part in range(16):
        for step in range(64):
            uc.mem_write(pattern + 0x830 + part * 0x330 + step * 12,
                         bytes([1, 96, 96, int(part == 0 and step % 4 == 0), 61 if part == 0 else 0, 0, 0, 0, 0, 0, 0, 0]))
    dev.press(2, .4)
    measure('playing')
    dev.press(0x17, .3)
    measure('playing-keyboard')
    dev.press(1, .3)
    uc.mem_write(pattern + 0x802, bytes([2]))
    for step in range(64):
        uc.mem_write(pattern + 0x830 + step * 12, bytes([1, 127, 96, int(step == 0), 61, 65, 68, 73, 0, 0, 0, 0]))
    dev.press(0x15, .3)
    dev.press(2, .4)
    measure('sequencer-four-note-long-ties')
    dev.press(1, .3)
    dev.press(0x17, .3)
    if variant == 'patched':
        dev.call(SWITCH_SCREEN, built.profile.screen, 0)
        measure('blech-menu')
        dev.press('exit', .3)
        programs = json.loads((folder / 'programs.json').read_text())
        app_names = app_workload(programs, symbols['SCRIPT_APPS_MAX'])
        installed_entries = install(dev, built, programs, app_names)
        dev.run(1)
        apps = built.layout['runtime'] + symbols['RT_APPS']
        app_count = machine.u32(apps + symbols['SCRIPT_APPS_COUNT'])
        require(app_count in (len(app_names), len(app_names) + symbols['SCRIPT_APPS_BUILTIN']), 'app registration incomplete')
        registered = {machine.u32(apps + symbols['SCRIPT_APPS_TABLE'] + i * 12) for i in range(app_count)}
        require(set(installed_entries.values()) <= registered and len(registered) == app_count, 'installed app missing from native table')
        measure('closed-apps')
        for plugin in APPS:
            apps = built.layout['runtime'] + symbols['RT_APPS']
            count = machine.u32(apps + symbols['SCRIPT_APPS_COUNT'])
            index = next((i for i in range(count) if plugin in bytes(uc.mem_read(machine.u32(apps + symbols['SCRIPT_APPS_TABLE'] + i * 12 + 4), 32)).split(b'\0')[0].decode('ascii', 'replace').lower().replace(' ', '')), None)
            require(index is not None, f'app missing: {plugin}')
            require(dev.call(symbols['script_app_open'], index) == 1, 'app did not open')
            entry = machine.u32(apps + symbols['SCRIPT_APPS_TABLE'] + index * 12)
            clock_reads = []
            def app_clock_input(_uc, _at, _size, _data):
                runtime = built.layout['runtime']
                for key, value in (('INIT', 1), ('LAST', machine.u32(symbols['SCRIPT_TIMER_ADDRESS'])),
                                   ('REM', 0), ('MS', APP_PROTOCOL['openClockMs'])):
                    uc.mem_write(runtime + symbols['SCRIPT_CONTROL_CLOCK_' + key], struct.pack('<I', value))
                clock_reads.append(APP_PROTOCOL['openClockMs'])
            clock_hook = uc.hook_add(unicorn.UC_HOOK_CODE, app_clock_input,
                                     begin=symbols['script_clock_millis_glue'], end=symbols['script_clock_millis_glue'])
            try:
                run_completed_frames(dev, built, APP_PROTOCOL['warmupFrames'])
            finally:
                uc.hook_del(clock_hook)
                uc.ctl_flush_tb()
            require(len(clock_reads) == (0 if plugin == 'mandelbrot' else 1), f'unexpected app clock reads: {plugin}: {len(clock_reads)}')
            measure('app-' + plugin, frames=50, entry=entry, program=programs[plugin])
            dev.press('exit', .3)
        install(dev, built, programs, (*app_names, *BACKGROUND_PLUGINS))
        dev.run(1)
        measure('background-plugins')
    return {'scenarios': results}


def loader_profile(folder, build):
    sys.path[:0] = [str(ROOT), str(ROOT / 'tools/emu'), str(ROOT / 'tools/patch')]
    from tools.patch import script_vm
    from tools.patch.test_script_vm import BareMachine
    code = script_vm.build((folder / 'contract.inc').read_text())
    programs = json.loads((folder / 'programs.json').read_text())
    repeats = []
    for _ in range(REPEATS):
        machine = BareMachine(code)
        counter = BlockCounter(machine.uc)
        rows = []
        for name, program in programs.items():
            (error, _), count = counter.measure(lambda: machine.load(bytes.fromhex(program['blob'])))
            require(error == 0, f'{name}: native load failed')
            rows.append({'plugin': name, 'instructions': count})
        repeats.append({'totalInstructions': sum(r['instructions'] for r in rows), 'plugins': rows})
    require(all(result == repeats[0] for result in repeats), 'loader counts differ between repeats')
    return {**repeats[0], 'maxInstructions': max(r['totalInstructions'] for r in repeats), 'repeats': repeats}


def capture(folder):
    manifest = json.loads((folder / 'sets.json').read_text())
    require(manifest.get('ok') is True and manifest.get('sourcesUnchanged') is True, 'full set checks not passed')
    require(set(manifest.get('builds', {})) == set(BUILDS), 'three checked builds required')
    data = {'format': 'blech-performance', 'version': 4, 'appProtocol': APP_PROTOCOL.copy(),
            'method': hashlib.sha256((inspect.getsource(BlockCounter) + inspect.getsource(app_workload) + inspect.getsource(run_completed_frames) + inspect.getsource(capture_worker) + inspect.getsource(loader_profile) + json.dumps(APP_PROTOCOL, sort_keys=True)).encode()).hexdigest(),
            'repeats': REPEATS, 'seconds': SECONDS, 'programsSha256': hashlib.sha256((folder / 'programs.json').read_bytes()).hexdigest(), 'builds': {}}
    for build in BUILDS:
        meta = manifest['builds'][build]
        require(meta.get('ok') is True, f'{build}: full set checks missing')
        item = {key: meta[key] for key in ('inputSha256', 'outputSha256', 'footprint')}
        data['builds'][build] = item
        for variant in ('original', 'patched'):
            item[variant] = []
            command = [sys.executable, str(Path(__file__).resolve()), '--worker', str(folder), build, variant]
            print(f'{build}/{variant}: {REPEATS} independent profiles started', file=sys.stderr, flush=True)
            import parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=parallel.workers(REPEATS)) as pool:
                jobs = [pool.submit(subprocess.run, command, capture_output=True, text=True, check=True) for _ in range(REPEATS)]
                for repeat, job in enumerate(jobs):
                    try:
                        result = job.result()
                    except subprocess.CalledProcessError as error:
                        log = folder / f'{build}-{variant}-{repeat + 1}-error.log'
                        log.write_text(error.stderr or str(error))
                        raise ValueError(f'{build}/{variant}: profile failed; see {log.name}') from error
                    item[variant].append(json.loads(result.stdout))
                    (folder / 'profile-progress.json').write_text(json.dumps(data, indent=2) + '\n')
                    print(f'{build}/{variant}: profile {repeat + 1}/{REPEATS} complete', file=sys.stderr, flush=True)
        item['loader'] = loader_profile(folder, build)
        from sysex_bench import profile as sysex_profile
        item['sysex'] = sysex_profile(folder, build)
    validate_capture(data)
    return data


def load_capture(folder):
    data = json.loads((folder / 'profile.json').read_text())
    sets = json.loads((folder / 'sets.json').read_text())
    require(sets.get('ok') is True and sets.get('sourcesUnchanged') is True, 'checked set metadata missing')
    for build in BUILDS:
        meta, item = sets['builds'][build], data['builds'][build]
        require(meta.get('ok') is True, 'full check missing')
        for field, key in (('original', 'inputSha256'), ('patched', 'outputSha256')):
            actual = hashlib.sha256((folder / meta[field]).read_bytes()).hexdigest()
            require(actual == meta[key] == item[key], 'capture firmware has changed')
    require(hashlib.sha256((folder / 'programs.json').read_bytes()).hexdigest() == data['programsSha256'], 'plugin corpus has changed')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--phase', choices=('baseline', 'pad', 'loader', 'decoder', 'mul', 'sysex', 'combined'))
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--integrated-baseline', action='store_true',
                        help='use the registered baseline containing accepted pad, loader and MUL changes')
    parser.add_argument('--baseline-transfers', type=Path, help='native SysEx evidence for the exact baseline firmware')
    parser.add_argument('--worker', nargs=3, metavar=('DIRECTORY', 'BUILD', 'VARIANT'))
    args = parser.parse_args()
    if args.worker:
        folder, build, variant = args.worker
        require(build in BUILDS and variant in ('original', 'patched'), 'invalid worker selection')
        print(json.dumps(capture_worker(Path(folder), build, variant)))
        return
    require(args.out is not None, '--out required')
    if args.capture:
        data = capture(args.capture)
    else:
        require(args.baseline and args.candidate and args.phase, 'baseline, candidate and phase required')
        old = load_capture(args.baseline)
        new = load_capture(args.candidate)
        inherited = None
        if args.integrated_baseline:
            inherited = json.loads((ROOT / 'docs/messungen/2026-10-22-gesamtpruefung-basis.json').read_text())
            sets = json.loads((args.baseline / 'sets.json').read_text())
            require(sets['commit'] == inherited['firmwareSourceCommit'], 'different integrated source commit')
        if args.baseline_transfers:
            transfers = json.loads(args.baseline_transfers.read_text())
            require(set(transfers) == set(BUILDS), 'three baseline transfer builds required')
            for build in BUILDS:
                require('sysex' not in old['builds'][build], 'baseline transfer evidence already present')
                old['builds'][build]['sysex'] = transfers[build]
        validate_capture(old)
        validate_capture(new)
        data = compare(old, new, args.phase, inherited)
    args.out.write_text(json.dumps(data, indent=2) + '\n')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
