#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a private GNU 15.2 Blackfin worker outside the repository."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tarfile
import urllib.request

VERSION = '15.2'
SHA256 = '83350ccd35b5b5a0cba6b334c41294ea968158c573940904f00b92f76345314d'
URL = f'https://sourceware.org/pub/gdb/releases/gdb-{VERSION}.tar.xz'
ROOT = Path(__file__).resolve().parents[2]


def patch_sources(source):
    file = source / 'sim/bfin/bfin-sim.c'
    text = file.read_text()
    start = text.index('#define SIGNEXTEND(v, n)')
    end = text.index('\n\n', start)
    text = text[:start] + '#define SIGNEXTEND(v, n) (((bs32)((bu32)(v) << (32 - (n)))) >> (32 - (n)))' + text[end:]
    for expression in ('add32 (cpu, DREG (src0), DREG (src1), 1, s)',
                       'sub32 (cpu, DREG (src0), DREG (src1), 1, s, 0)'):
        old = f'SET_DREG (dst0, {expression});'
        new = f'STORE (DREG (dst0), {expression});'
        if text.count(old) == 1:
            text = text.replace(old, new)
        elif text.count(new) != 1:
            raise ValueError('unexpected GNU DSP32ALU arithmetic implementation')
    for expression in ('signbits (sv1, 32)', 'signbits (sv1, 16)',
                       'signbits (sv1 >> 16, 16)', 'signbits (acc, 40) & 0xFFFF'):
        old = f'SET_DREG_L (dst0, {expression});'
        new = f'STORE (DREG (dst0), REG_H_L (DREG (dst0), {expression}));'
        if text.count(old) == 1:
            text = text.replace(old, new)
        elif text.count(new) != 1:
            raise ValueError('unexpected GNU SIGNBITS implementation')
    file.write_text(text)
    file = source / 'sim/bfin/interp.c'
    text = file.read_text()
    begin, end = '/* BLECH_GUARD_BEGIN */\n', '/* BLECH_GUARD_END */\n'
    guard = begin + (ROOT / 'tools/dsp/blackfin_guard.c.inc').read_text() + '\n' + end
    if begin in text:
        a, b = text.index(begin), text.index(end) + len(end)
        text = text[:a] + guard + text[b:]
    else:
        at = '\nvoid\nsim_engine_run ('
        if text.count(at) != 1:
            raise ValueError('unexpected GNU Blackfin execution engine')
        text = text.replace(at, '\n' + guard + at)
    check = '      blech_bfin_check (sd, cpu);\n'
    if check not in text:
        at = '      step_once (cpu);\n'
        if text.count(at) != 1:
            raise ValueError('unexpected GNU Blackfin instruction loop')
        text = text.replace(at, check + at)
    file.write_text(text)
    file = source / 'sim/bfin/machs.c'
    text = file.read_text()
    for name in ('bf522_dev', 'bf526_dev'):
        start = text.index(f'static const struct bfin_dev_layout {name}[] =\n{{\n')
        stop = text.index('\n};', start)
        region = text[start:stop]
        if '"bfin_hostdp"' not in region:
            at = text.index('{\n', start) + 2
            text = text[:at] + '  DEVICE (0xFFC03400, 12, "bfin_hostdp"),\n' + text[at:]
    old = 'if (bfrom->sirev == sirev)\n'
    new = 'if (bfrom->sirev == sirev && bfrom->len != 0)\n'
    if text.count(old) == 1:
        text = text.replace(old, new)
    elif text.count(new) != 1:
        raise ValueError('unexpected GNU boot ROM mapping implementation')
    file.write_text(text)
    file = source / 'sim/Makefile.in'
    text = file.read_text().replace(r'\1/;p}', r'\1/;p;}')
    hostdp = '@SIM_ENABLE_ARCH_bfin_TRUE@\tbfin_hostdp \\\n'
    if hostdp not in text:
        anchor = '@SIM_ENABLE_ARCH_bfin_TRUE@\tbfin_gptimer \\\n'
        if text.count(anchor) != 1:
            raise ValueError('unexpected GNU Blackfin device list')
        text = text.replace(anchor, anchor + hostdp)
    file.write_text(text)
    shutil.copyfile(ROOT / 'tools/dsp/blackfin_hostdp.c', source / 'sim/bfin/dv-bfin_hostdp.c')


def build(directory, jobs=4):
    directory = directory.resolve()
    if directory == ROOT or ROOT in directory.parents:
        raise ValueError('the Blackfin SDK must be built outside the repository')
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / f'gdb-{VERSION}.tar.xz'
    if not archive.exists():
        with urllib.request.urlopen(URL, timeout=60) as response, archive.open('wb') as output:
            shutil.copyfileobj(response, output)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise ValueError('GNU source checksum mismatch')
    source = directory / f'gdb-{VERSION}'
    if not source.exists():
        with tarfile.open(archive) as files:
            for item in files.getmembers():
                target = (directory / item.name).resolve()
                if directory not in target.parents or item.issym() or item.islnk():
                    raise ValueError('unsafe GNU source archive member')
            files.extractall(directory)
    patch_sources(source)
    output = directory / 'build'
    output.mkdir(exist_ok=True)

    def run(args, cwd=output, name='build.log'):
        with (directory / name).open('ab') as log:
            subprocess.run(args, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, check=True)

    run([str(source / 'configure'), '--target=bfin-elf', '--enable-sim', '--disable-gdb',
         '--disable-gdbserver', '--disable-werror', '--disable-nls', '--without-guile',
         '--without-python', '--with-system-zlib', 'CFLAGS=-O2 -std=gnu11', 'MAKEINFO=true'],
        name='configure.log')
    run(['make', f'-j{jobs}', 'all-sim', 'MAKEINFO=true'])
    modules = (output / 'sim/bfin/modules.c').read_text()
    if '  sim_install_hw,' not in modules:
        raise RuntimeError('GNU simulator hardware module was not installed')
    worker = directory / 'blackfin-worker'
    libraries = ['sim/bfin/libsim.a', 'bfd/.libs/libbfd.a', 'opcodes/.libs/libopcodes.a',
                 'libiberty/libiberty.a', 'gnulib/import/libgnu.a']
    extra = ['-lz', '-lm']
    if shutil.which('pkg-config'):
        result = subprocess.run(['pkg-config', '--libs', 'libzstd'], capture_output=True, text=True)
        if result.returncode == 0:
            extra += shlex.split(result.stdout)
    run([os.environ.get('CC', 'cc'), '-O2', '-include', str(output / 'bfd/config.h'),
         '-I', str(output / 'bfd'), '-I', str(source / 'include'),
         str(ROOT / 'tools/dsp/blackfin_worker.c'), *(str(output / f) for f in libraries),
         *extra, '-o', str(worker)], name='worker-build.log')
    manifest = dict(version=VERSION, url=URL, sourceSHA256=SHA256,
                    patches=['32-bit SIGNEXTEND', 'BSD sed module generation',
                             'deferred DSP32ALU add/sub result writes',
                             'deferred SIGNBITS half-register writes',
                             'bounded execution inside the event loop',
                             'BF52x HOSTDP registers and interrupt sources',
                             'do not map empty built-in ROM images'],
                    workerSHA256=hashlib.sha256(worker.read_bytes()).hexdigest(),
                    bridgeSHA256=hashlib.sha256((ROOT / 'tools/dsp/blackfin_worker.c').read_bytes()).hexdigest())
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return worker


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--jobs', type=int, choices=range(1, 33), default=4)
    args = parser.parse_args()
    print(build(args.directory, args.jobs))
