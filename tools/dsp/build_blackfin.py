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
    file.write_text(text)
    file = source / 'sim/Makefile.in'
    text = file.read_text().replace(r'\1/;p}', r'\1/;p;}')
    file.write_text(text)


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
                    patches=['32-bit SIGNEXTEND', 'BSD sed module generation'],
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
