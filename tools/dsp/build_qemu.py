#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the private QEMU Blackfin worker outside the repository.

QEMU executes the Blackfin instructions; the GNU simulator (built as by build_blackfin.py, as a
shared library) keeps the devices, the CEC, time and the BFIN9 protocol. QEMU's Blackfin port
(github.com/vapier/qemu, branch bfin) is pinned at COMMIT and patched with tools/dsp/qemu-bfin.patch
(instruction fixes) and tools/dsp/qemu-worker.patch (cycle costs, run budget, GNU delegation); the
board comes from tools/dsp/qemu/. dsp32alu, dsp32shift and dsp32shiftimm run GNU's decoders, copied
from the GNU source into target/bfin (tools/dsp/bfin_gnu_dsp32.c.inc). Only bfin-softmmu is built. The result is a local tool: both
halves carry GPL-3 code from the GNU simulator, so it is never shipped.

    build_qemu.py DIRECTORY [--jobs N]

prints the path of the worker (DIRECTORY/qemu-bfin-worker), which takes the same arguments as the
GNU worker (--operating, --channel PATH) and speaks BFIN9.
"""
import argparse
import hashlib
import json
import re
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


# GNU functions that bfin_gnu_dsp32.c.inc runs on the QEMU CPU state.
GNU_DSP32 = ('fmtconst_val', 'get_unextended_acc', 'get_extended_acc', 'ashiftrt', 'lshiftrt', 'lshift',
             'signbits', 'add16', 'sub16', 'saturate_s16', 'saturate_s32',
             'saturate_u16', 'xor_reduce', 'sgn_extend', 'setflags_nz', 'setflags_nz_2x16', 'setflags_logical',
             'add32', 'sub32', 'saturate_s40_astat', 'saturate_s40', 'rot40', 'rot32', 'rnd16', 'ones', 'min32',
             'max32', 'min2x16', 'max2x16', 'algn', 'decode_dsp32alu_0', 'decode_dsp32shift_0',
             'decode_dsp32shiftimm_0')


def gnu_dsp32(gnu, target):
    """Copies the GNU decoders of dsp32alu, dsp32shift and dsp32shiftimm with their helpers."""
    text = (gnu / 'sim/bfin/bfin-sim.c').read_text()
    lines = text.split('\n')

    def function(name):
        start = next((i for i, line in enumerate(lines) if line.startswith(name + ' (')), None)
        if start is None:
            raise ValueError('GNU function missing: ' + name)
        head = start
        while lines[head - 1].strip() and not lines[head - 1].startswith('}'):
            head -= 1
        end = lines.index('}', start)
        return '\n'.join(lines[head:end + 1])

    forms = text.index('typedef enum\n{\n  c_0,')
    table = text.index('};\n', text.index('} constant_formats[] =', forms)) + 2
    parts = [text[forms:table]]
    parts += [line for line in lines if re.match(r'#define \w+\(x\)\s+fmtconst_val ', line)]
    parts += [function(name) for name in sorted(GNU_DSP32, key=lambda name: text.find('\n' + name + ' ('))]
    (target / 'bfin-gnu-dsp32-gen.c.inc').write_text(
        '/* Generated by tools/dsp/build_qemu.py from GNU sim/bfin/bfin-sim.c. */\n\n' + '\n\n'.join(parts) + '\n')
    shutil.copyfile(DSP / 'bfin_gnu_dsp32.c.inc', target / 'bfin-gnu-dsp32.c.inc')


# CLI and STI that QEMU may run itself. STI qualifies only when no latched interrupt becomes
# unmasked: then the CEC event GNU schedules finds nothing, and skipping it changes nothing.
CEC_FAST = r'''
bool blech_cec_fast (SIM_CPU *, int, bu32, bu32 *);
bool
blech_cec_fast (SIM_CPU *cpu, int op, bu32 value, bu32 *result)
{
  struct bfin_cec *cec;
  bu32 imask;

  *result = 0;
  if (STATE_ENVIRONMENT (CPU_STATE (cpu)) != OPERATING_ENVIRONMENT)
    return true;
  cec = CEC_STATE (cpu);
  if (!_cec_is_supervisor_mode (cec))
    return false;
  if (op == 0)
    {
      *result = cec->imask;
      _cec_imask_write (cec, 0);
      return true;
    }
  imask = (value & IVG_MASKABLE_B) | (cec->imask & IVG_UNMASKABLE_B);
  if ((cec->ilat | (cec->system_lines & ~cec->ipend)) & imask)
    return false;
  cec->ilat |= cec->system_lines & ~cec->ipend;
  cec->imask = imask;
  return true;
}
'''


# GNU's dsp32 ALU and shift decoders, called by QEMU for each such insn (HELPER(dsp32_gnu)). A probe
# at translation time runs the decoder once, also for MAC and MULT, which QEMU computes itself; an
# encoding GNU rejects jumps back instead of raising the exception, and QEMU hands that insn to GNU.
DSP32_JUMP = '#include <setjmp.h>\nstatic jmp_buf *blech_dsp32_jump;\n'
DSP32_HOOK = '  if (blech_dsp32_jump)\n    _longjmp (*blech_dsp32_jump, 1);\n'
DSP32_GNU = r'''
SIM_CPU *blech_dsp32_cpu;
int blech_dsp32 (int, uint32_t, uint32_t *);

/* R0-R7 P0 I0 I1 A0.X A0.W A1.X A1.W ASTAT; returns 0 for an illegal insn,
   3 when it allows misaligned loads in its bundle (DISALGNEXCPT), else 1.
   A probe leaves the state as it was.  */
int
blech_dsp32 (int probe, uint32_t insn, uint32_t *r)
{
  SIM_CPU *cpu = blech_dsp32_cpu;
  struct bfin_cpu_state saved;
  bu16 iw0 = insn >> 16, iw1 = insn;
  jmp_buf jump;
  int i, legal = 1;

  if (probe)
    saved = BFIN_CPU_STATE;
  else
    {
      for (i = 0; i < 8; ++i)
        DREG (i) = r[i];
      PREG (0) = r[8];
      IREG (0) = r[9];
      IREG (1) = r[10];
      for (i = 0; i < 2; ++i)
        {
          /* GNU keeps A.X either as 8 bits or sign-extended, as in
             blech_hybrid_take.  */
          if ((AXREG (i) & 0xff) != (r[11 + 2 * i] & 0xff))
            AXREG (i) = r[11 + 2 * i] & 0xff;
          AWREG (i) = r[12 + 2 * i];
        }
      SET_ASTAT (r[15]);
    }
  BFIN_CPU_STATE.n_stores = 0;
  PARALLEL_GROUP = BFIN_PARALLEL_NONE;
  DIS_ALGN_EXPT &= ~1;
  blech_dsp32_jump = &jump;
  if (_setjmp (jump) == 0)
    {
      if ((iw0 & 0xF600) == 0xC000)
        decode_dsp32mac_0 (cpu, iw0, iw1);
      else if ((iw0 & 0xF600) == 0xC200)
        decode_dsp32mult_0 (cpu, iw0, iw1);
      else if ((iw0 & 0xF7C0) == 0xC400)
        decode_dsp32alu_0 (cpu, iw0, iw1);
      else if ((iw0 & 0xF7E0) == 0xC600 && (iw1 & 0x01C0) == 0)
        decode_dsp32shift_0 (cpu, iw0, iw1);
      else if ((iw0 & 0xF7E0) == 0xC680)
        decode_dsp32shiftimm_0 (cpu, iw0, iw1);
      else
        legal = 0;
    }
  else
    legal = 0;
  blech_dsp32_jump = NULL;
  if (legal && (DIS_ALGN_EXPT & 1))
    legal = 3;
  if (legal)
    for (i = 0; i < BFIN_CPU_STATE.n_stores; ++i)
      *BFIN_CPU_STATE.stores[i].addr = BFIN_CPU_STATE.stores[i].val;
  BFIN_CPU_STATE.n_stores = 0;
  if (probe)
    {
      BFIN_CPU_STATE = saved;
      return legal;
    }
  for (i = 0; i < 8; ++i)
    r[i] = DREG (i);
  for (i = 0; i < 2; ++i)
    {
      r[11 + 2 * i] = AXREG (i) & 0xff;
      r[12 + 2 * i] = AWREG (i);
    }
  r[15] = ASTAT;
  return legal;
}
'''


def patch_dsp32(source):
    file = source / 'sim/bfin/bfin-sim.c'
    text = file.read_text()
    if DSP32_JUMP in text:
        # The tree is reused between builds: replace the hooks and the appended function.
        text = text.replace(DSP32_HOOK.replace('_longjmp', 'longjmp'), DSP32_HOOK)
        file.write_text(text[:text.index(DSP32_GNU.split('\n', 2)[1])].rstrip('\n') + '\n' + DSP32_GNU)
        return
    for name in ('illegal_instruction (SIM_CPU *cpu)\n{\n', 'illegal_instruction_combination (SIM_CPU *cpu)\n{\n',
                 'unhandled_instruction (SIM_CPU *cpu, const char *insn)\n{\n'):
        head = 'static ATTRIBUTE_NORETURN void\n' + name
        if text.count(head) != 1:
            raise ValueError('unexpected GNU ' + name.split()[0])
        body = text.index(head) + len(head)
        end = text.index('\n\n', body) + 1  # after the local declarations, if any
        if 'unhandled' not in name:
            end = body
        text = text[:end] + DSP32_HOOK + text[end:]
    first = 'static ATTRIBUTE_NORETURN void\nillegal_instruction (SIM_CPU *cpu)\n'
    text = text.replace(first, DSP32_JUMP + '\n' + first)
    file.write_text(text + DSP32_GNU)


# Bytes from ADDR up to LAST that resolve to MAPPING, which sim_core_find_mapping found for ADDR: an
# earlier mapping in the list wins from its base on.
BLECH_CORE_RUN = '''static unsigned
blech_core_run (sim_core_common *core, unsigned map, sim_core_mapping *mapping,
\t\taddress_word addr, address_word last)
{
  sim_core_mapping *m;

  if (last < addr || last > mapping->bound)
    last = mapping->bound;
  for (m = core->map[map].first; m != mapping; m = m->next)
    if (m->base > addr && m->base <= last)
      last = m->base - 1;
  return last - addr + 1;
}

'''

# Each request resumes and halts the GNU engine; skip its wall clock (getrusage, only for `watch clock`
# and profiles) and the signal-mask save of setjmp/longjmp (system calls on macOS; the mask never changes).
SPEED = (
    ('sim/common/sim-events.c', '  events->resume_wallclock = sim_elapsed_time_get ();\n',
     '  events->resume_wallclock = 1;\n'),
    ('sim/common/sim-events.c', '  events->elapsed_wallclock += sim_elapsed_time_since (events->resume_wallclock);\n',
     ''),
    ('sim/common/sim-resume.c', '  jmpval = setjmp (buf);\n', '  jmpval = _setjmp (buf);\n'),
    ('sim/common/sim-engine.c', '      longjmp (*halt_buf, sim_engine_halt_jmpval);\n',
     '      _longjmp (*halt_buf, sim_engine_halt_jmpval);\n'),
    ('sim/common/sim-engine.c', '      longjmp (*halt_buf, sim_engine_restart_jmpval);\n',
     '      _longjmp (*halt_buf, sim_engine_restart_jmpval);\n'),
    # The poll event only checks for a host interrupt (Ctrl-C); every 4096 cycles it ended a QEMU run.
    ('sim/common/sim-events.c', '#define SIM_EVENTS_POLL_RATE 0x1000\n', '#define SIM_EVENTS_POLL_RATE 0x40000000\n'),
    # Buffer reads and writes (DMA, host requests) look the mapping up once per run, not per byte.
    ('sim/common/sim-core.c',
     '    ((unsigned_1*)buffer)[count] =\n      *(unsigned_1*)sim_core_translate (mapping, raddr);\n'
     '    count += 1;\n',
     '    for (unsigned n = blech_core_run (core, map, mapping, raddr, addr + (len - 1)); n; --n)\n'
     '      ((unsigned_1*)buffer)[count++] = *(unsigned_1*)sim_core_translate (mapping, raddr++);\n'),
    ('sim/common/sim-core.c',
     '      *(unsigned_1*)sim_core_translate (mapping, raddr) =\n\t((unsigned_1*)buffer)[count];\n'
     '      count += 1;\n',
     '      for (unsigned n = blech_core_run (core, map, mapping, raddr, addr + (len - 1)); n; --n)\n'
     '\t*(unsigned_1*)sim_core_translate (mapping, raddr++) = ((unsigned_1*)buffer)[count++];\n'),
    ('sim/common/sim-core.c', '#if EXTERN_SIM_CORE_P\nunsigned\nsim_core_read_buffer (',
     BLECH_CORE_RUN + '#if EXTERN_SIM_CORE_P\nunsigned\nsim_core_read_buffer ('),
)


def patch_speed(source):
    for name, old, new in SPEED:
        file = source / name
        text = file.read_text()
        if new and new in text:   # the tree is reused between builds
            continue
        if text.count(old) == 1:
            file.write_text(text.replace(old, new))
        elif old in text or new:
            raise ValueError(f'unexpected GNU {name}')


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
    cec = source / 'sim/bfin/dv-bfin_cec.c'
    text = cec.read_text()
    if CEC_FAST not in text:
        cec.write_text(text + CEC_FAST)
    patch_dsp32(source)
    patch_speed(source)
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
    gnu_dsp32(build_blackfin.source_tree(directory / 'gnu'), source / 'target/bfin')
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
