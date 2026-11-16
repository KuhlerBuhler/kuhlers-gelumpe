#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the private QEMU Blackfin worker outside the repository.

QEMU executes the Blackfin instructions; the GNU simulator (built as by build_blackfin.py, as a
shared library) keeps the devices, the CEC, time and the BFIN9 protocol. QEMU's Blackfin port
(github.com/vapier/qemu, branch bfin) is pinned at COMMIT and patched with tools/dsp/qemu-bfin.patch
(instruction fixes) and tools/dsp/qemu-worker.patch (cycle costs, run budget, GNU delegation); the
board comes from tools/dsp/qemu/. Only bfin-softmmu is built. The result is a local tool: both
halves carry GPL-3 code from the GNU simulator, so it is never shipped.

    build_qemu.py DIRECTORY [--jobs N]

prints the path of the worker (DIRECTORY/qemu-bfin-worker), which takes the same arguments as the
GNU worker (--operating, --channel PATH) and speaks BFIN9.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_blackfin  # noqa: E402

URL = 'https://github.com/vapier/qemu.git'
BRANCH = 'bfin'
COMMIT = 'ae8fe9a'
ROOT = Path(__file__).resolve().parents[2]
DSP = ROOT / 'tools/dsp'
BOARD = DSP / 'qemu'
PATCHES = [DSP / 'qemu-bfin.patch', DSP / 'qemu-worker.patch']
LIBRARY = 'libblackfin-hybrid.so'


def run(args, cwd, log, env=None):
    with log.open('ab') as out:
        out.write(('\n$ ' + ' '.join(map(str, args)) + '\n').encode())
        out.flush()
        subprocess.run(list(map(str, args)), cwd=cwd, stdout=out, stderr=subprocess.STDOUT, check=True, env=env)


def python():
    """QEMU 8.2's configure builds its own venv; very new Pythons break its bundled meson."""
    for name in ('python3.12', 'python3.13', 'python3.14', 'python3.11', 'python3'):
        found = shutil.which(name)
        # An x86 Python under Rosetta makes meson configure QEMU for an x86 host.
        if found and subprocess.run([found, '-c', 'import platform; print(platform.machine())'], capture_output=True,
                                    text=True).stdout.strip() == os.uname().machine:
            return found
    raise RuntimeError('no python3 found')


def checkout(directory, log):
    source = directory / 'qemu'
    if not source.exists():
        run(['git', 'clone', '--branch', BRANCH, '--single-branch', URL, source], directory, log)
    run(['git', 'checkout', '--quiet', '--force', COMMIT], source, log)
    run(['git', 'clean', '-fdq', '--', 'target/bfin', 'hw/bfin', 'system', 'include'], source, log)
    for patch in PATCHES:
        run(['git', 'apply', patch], source, log)
    for file in sorted(BOARD.iterdir()):
        if file.suffix in ('.c', '.h', '.inc'):
            shutil.copyfile(file, source / 'hw/bfin' / file.name)
    shutil.copyfile(DSP / 'blackfin_hybrid.h', source / 'hw/bfin/blackfin_hybrid.h')
    meson = source / 'hw/bfin/meson.build'
    text = meson.read_text()
    line = "bfin_ss.add(files('bfin_worker.c'))\n"
    if line not in text:
        text = text.replace("hw_arch += {'bfin': bfin_ss}", line + "hw_arch += {'bfin': bfin_ss}")
        if line not in text:
            raise ValueError('unexpected hw/bfin/meson.build')
        meson.write_text(text)
    return source


def patch_hybrid(source):
    """The GNU engine hands the instructions between two events to QEMU (blackfin_hybrid.c.inc)."""
    file = source / 'sim/bfin/interp.c'
    text = file.read_text()
    memory = (DSP / 'blackfin_memory.c.inc').read_text()
    check = '  if (kind >= 4 || begin >= end)\n    return;\n'
    if memory.count(check) != 1 or text.count(memory) != 1:
        raise ValueError('unexpected GNU memory observation')
    hook = '  if ((kind == 1 || kind == 3) && blech_qemu && length)\n    blech_qemu->written (address, length);\n'
    text = text.replace(memory, (DSP / 'blackfin_hybrid.c.inc').read_text() + '\n' + memory.replace(check, hook + check))
    call = '  blech_bfin_engine (sd, STATE_CPU (sd, 0));\n'
    if text.count(call) != 1:
        raise ValueError('unexpected GNU Blackfin execution engine')
    file.write_text(text.replace(call, '  blech_hybrid_engine (sd, STATE_CPU (sd, 0));\n'))
    shutil.copyfile(DSP / 'blackfin_hybrid.h', source / 'sim/bfin/blackfin_hybrid.h')


def build_gnu(directory, jobs):
    """The GNU simulator as a shared library that QEMU loads; its symbols stay private to it."""
    directory.mkdir(parents=True, exist_ok=True)
    source = build_blackfin.source_tree(directory)
    patch_hybrid(source)
    output = directory / 'build'
    build_blackfin.compile_sim(directory, source, output, jobs, cflags='-O2 -std=gnu11 -fPIC')
    library = directory / LIBRARY
    renames = ['-Dmain=blech_worker_main', '-Dsim_open=blech_hybrid_sim_open', '-Dsim_write=blech_hybrid_sim_write',
               '-Dblech_bfin_memory_window=blech_hybrid_memory_window']
    flags = ['-undefined', 'error'] if sys.platform == 'darwin' else ['-Wl,-Bsymbolic', '-Wl,--no-undefined']
    common = [os.environ.get('CC', 'cc'), '-O2', '-fPIC', '-include', output / 'bfd/config.h', '-I', output / 'bfd',
              '-I', source / 'include', '-I', DSP]
    objects = []
    for name, extra in (('blackfin_worker.c', renames), ('blackfin_channel.c', []), ('blackfin_hybrid.c', [])):
        obj = directory / (name + '.o')
        run([*common, *extra, '-c', DSP / name, '-o', obj], directory, directory / 'worker-build.log')
        objects.append(obj)
    run([os.environ.get('CC', 'cc'), '-shared', *flags, *objects, *(output / f for f in build_blackfin.LIBRARIES),
         *build_blackfin.system_libraries(), '-o', library], directory, directory / 'worker-build.log')
    return library


def build(directory, jobs=4):
    directory = directory.resolve()
    if directory == ROOT or ROOT in directory.parents:
        raise ValueError('QEMU must be built outside the repository')
    directory.mkdir(parents=True, exist_ok=True)
    log = directory / 'build.log'
    library = build_gnu(directory / 'gnu', jobs)
    source = checkout(directory, log)
    tools = directory / 'tools-venv'
    if not (tools / 'bin/ninja').exists():
        run([python(), '-m', 'venv', tools], directory, log)
        run([tools / 'bin/pip', 'install', '--quiet', 'ninja', 'distlib'], directory, log)
    env = {**os.environ, 'PATH': f"{tools / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"}
    output = source / 'build'
    if not (output / 'build.ninja').exists():
        output.mkdir(exist_ok=True)
        configure = [source / 'configure', f'--python={tools / "bin/python3"}', '--target-list=bfin-softmmu',
                     '--disable-docs', '--disable-werror', '--audio-drv-list=', '--disable-vnc',
                     '--disable-sdl', '--disable-gtk', '--disable-opengl', '--disable-slirp', '--disable-tools',
                     '--disable-guest-agent', '--disable-curl', '--disable-gnutls', '--disable-nettle',
                     '--disable-gcrypt', '--disable-libusb', '--disable-usb-redir', '--disable-zstd',
                     '--disable-capstone', '--disable-fdt', '--disable-png', '--disable-libssh']
        if sys.platform == 'darwin':
            configure += ['--objcc=clang', '--disable-coreaudio', '--disable-vmnet', '--disable-cocoa', '--disable-hvf']
        run(configure, output, log, env)
    run([tools / 'bin/ninja', f'-j{jobs}', 'qemu-system-bfin'], output, log, env)
    binary = output / 'qemu-system-bfin'
    worker = directory / 'qemu-bfin-worker'
    worker.write_text(
        '#!/bin/sh\n# BFIN9 worker on QEMU; arguments as the GNU worker (--operating, --channel PATH).\n'
        'BLECH_ARGC=$#; export BLECH_ARGC\ni=1\n'
        'for arg; do export "BLECH_ARG$i=$arg"; i=$((i + 1)); done\n'
        f'BLECH_HYBRID_LIB={shlex.quote(str(library))}; export BLECH_HYBRID_LIB\n'
        f'exec {shlex.quote(str(binary))} -M bf-electribe -accel tcg,thread=single -display none -nodefaults '
        '-serial none -monitor none -S\n')
    worker.chmod(0o755)
    manifest = dict(url=URL, branch=BRANCH, commit=COMMIT,
                    patchSHA256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in PATCHES},
                    boardSHA256=hashlib.sha256(b''.join(f.read_bytes() for f in sorted(BOARD.iterdir()))).hexdigest(),
                    gnuVersion=build_blackfin.VERSION,
                    librarySHA256=hashlib.sha256(library.read_bytes()).hexdigest(),
                    binarySHA256=hashlib.sha256(binary.read_bytes()).hexdigest())
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return worker


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--jobs', type=int, choices=range(1, 33), default=4)
    args = parser.parse_args()
    print(build(args.directory, args.jobs))
