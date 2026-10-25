#!/usr/bin/env python3
"""Time one DSP function of the electribe sampler in the GNU Blackfin simulator.

Builds a small ELF in a scratch directory: the regions from dsp_extract.py
(L1 code, L1 data, SDRAM code and tables) plus a harness that calls the
function N times on a synthetic context and reads the CYCLES counter around
every call. Prints simulated cycles per call and host wall-clock time.

Nothing here contains Korg data. The extracted regions are read from OUTDIR
(written by dsp_extract.py) and the ELF is written next to them, so keep
OUTDIR outside the repository.

Synthetic context ("soup"): the region SOUP_BASE..SOUP_BASE+SOUP_SIZE is
filled so that every 32-bit word holds the address of a 4 KiB page inside the
same region, chosen by a hash of the word address. Every pointer the function
loads then lands in mapped memory, and different pointer fields usually land
on different pages. Values are meaningless as audio; that is fine for timing
branch-free kernels, whose cycle count does not depend on data. A function
with data-dependent loops or branches needs a real context (see --check).

Usage:
  bfsim_bench.py OUTDIR FUNC_ADDR [--calls N] [--reg R0=soup] [--reg P3=0x...]
                 [--run PATH_TO_SIM_RUN] [--as PATH_TO_bfin-elf-as] [--ld ...]

  --reg REG=VALUE  register preset before every call. VALUE is a number or
                   'soup' (a fresh soup page per register).
  --calls N        number of calls (default 1000).

Building the tools (none of this is installed system-wide):
  binutils 2.42 and gdb 14.2 from ftp.gnu.org, configured with
  --target=bfin-elf, CFLAGS='-O2 -std=gnu11', make MAKEINFO=true. From gdb
  only 'make all-sim' is needed (--enable-sim --disable-sim-igen --disable-gdb).
  The simulator is sim/bfin/run.

  Fix before building on arm64 with clang: SIGNEXTEND in sim/bfin/bfin-sim.c
  shifts a 32-bit value by 64 - n bits, which is undefined and gets folded
  away, so 16-bit constant loads such as 'R1 = 7 (X)' produce wrong values.
  Replace it with
    #define SIGNEXTEND(v, n) (((bs32)((bu32)(v) << (32 - (n)))) >> (32 - (n)))
  The QEMU port (github.com/vapier/qemu, branch bfin) has the same macro in
  target/bfin/bfin-sim.c. It also lacks 'Dreg = ASHIFT Dreg BY Dreg_lo (S)'
  (sop 1, sopcde 2 in decode_dsp32shift_0), which several effects use.
  Configure it with --target-list=bfin-softmmu --objcc=clang
  --audio-drv-list= --disable-coreaudio --disable-vmnet --disable-cocoa.

Output (one line, JSON): calls, cycles per call (min, max, mean), total
simulated cycles, a checksum of the soup after all calls (equal checksums in
both simulators mean both computed the same thing), host seconds, simulated
Mcycles per host second.
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import time

SOUP_BASE = 0x00100000   # inside the boot-time zero fill of SDRAM, unused by code
SOUP_SIZE = 0x00100000
PAGE = 0x1000
HARNESS = 0x03000000
RESULT = 0x03100000
STACK = 0x03F00000
SDRAM_SIZE = 0x04000000

# BF527 memory that the regions need; the simulator does not map it in the
# virtual environment by itself.
REGIONS = [
    (0x00000000, SDRAM_SIZE),
    (0xFF800000, 0x8000),     # L1 data A
    (0xFF900000, 0x8000),     # L1 data B
    (0xFFA00000, 0x14000),    # L1 instruction
]


def soup_bytes():
    pages = SOUP_SIZE // PAGE
    out = bytearray(SOUP_SIZE)
    for off in range(0, SOUP_SIZE, 4):
        addr = SOUP_BASE + off
        page = ((addr >> 2) * 2654435761 & 0xFFFFFFFF) >> 8
        value = SOUP_BASE + (page % pages) * PAGE + 0x800
        struct.pack_into('<I', out, off, value)
    return out


def harness_asm(func, presets, calls, qemu=False):
    """Assembly for the call loop. Results: [RESULT] = min, max, sum lo, sum hi.

    The 24 result bytes (the five words above plus the soup checksum) go to stdout through a libgloss syscall (GNU sim) or
    through UART0 (QEMU, which has no exit call; the harness then spins).
    """
    lines = [
        '\t.section .text', '\t.global _start', '_start:',
        f'\tSP.H = 0x{STACK >> 16:04X}; SP.L = 0x{STACK & 0xFFFF:04X};',
        '\tFP = SP;',
        '\tR0 = SYSCFG; BITSET(R0, 1); SYSCFG = R0;',
        f'\tP4.H = 0x{RESULT >> 16:04X}; P4.L = 0x{RESULT & 0xFFFF:04X};',
        '\tR0 = -1 (X); [P4] = R0;',          # min
        '\tR0 = 0 (X); [P4 + 4] = R0; [P4 + 8] = R0; [P4 + 12] = R0;',
        f'\tR0.H = 0x{calls >> 16:04X}; R0.L = 0x{calls & 0xFFFF:04X}; [P4 + 16] = R0;',
        '.Lloop:',
    ]
    for reg, value in presets:
        lines.append(f'\t{reg}.H = 0x{value >> 16:04X}; {reg}.L = 0x{value & 0xFFFF:04X};')
    lines += [
        f'\tP5.H = 0x{func >> 16:04X}; P5.L = 0x{func & 0xFFFF:04X};',
        '\tR6 = CYCLES;',
        '\t[--SP] = R6;',
        '\tCALL (P5);',
        '\tR7 = CYCLES;',
        '\tR6 = [SP++];',
        '\tR7 = R7 - R6;',
        f'\tP4.H = 0x{RESULT >> 16:04X}; P4.L = 0x{RESULT & 0xFFFF:04X};',
        '\tR1 = [P4 + 4];',
        '\tCC = R1 < R7 (IU); IF CC R1 = R7; [P4 + 4] = R1;',
        '\tR0 = [P4]; CC = R7 < R0 (IU); IF CC R0 = R7; [P4] = R0;',
        '\tR0 = [P4 + 8]; R1 = R0 + R7; [P4 + 8] = R1;',
        '\tCC = R1 < R0 (IU); R0 = CC; R2 = [P4 + 12]; R2 = R2 + R0; [P4 + 12] = R2;',
        '\tR0 = [P4 + 16]; R0 += -1; [P4 + 16] = R0;',
        '\tCC = R0 == 0;',
        '\tIF !CC JUMP .Lloop;',
        # checksum of the soup after all calls, to compare simulators
        f'\tP2.H = 0x{SOUP_BASE >> 16:04X}; P2.L = 0x{SOUP_BASE & 0xFFFF:04X};',
        f'\tP0.H = 0x{(SOUP_SIZE // 4) >> 16:04X}; P0.L = 0x{(SOUP_SIZE // 4) & 0xFFFF:04X};',
        '\tR0 = 0 (X);',
        '\tLSETUP(.Lcb, .Lce) LC1 = P0;',
        '.Lcb:\tR1 = [P2++];',
        '.Lce:\tR0 = R0 + R1;',
        f'\tP4.H = 0x{RESULT >> 16:04X}; P4.L = 0x{RESULT & 0xFFFF:04X};',
        '\t[P4 + 20] = R0;',
    ]
    if qemu:
        lines += [
            '\tP1.H = 0xFFC0; P1.L = 0x0400;',   # UART0_THR on the bf537 board model
            '\tP2 = P4; P0 = 24 (X);',
            '\tLSETUP(.Lub, .Lue) LC1 = P0;',
            '.Lub:\tR0 = B[P2++] (Z);',
            '.Lue:\tW[P1] = R0.L;',
            '.Lspin:\tJUMP .Lspin;',
        ]
        return '\n'.join(lines) + '\n'
    lines += [
        # libgloss write(1, RESULT, 16): P0 = 5, R0 = pointer to the arguments
        '\tR0 = 1 (X); [P4 + 32] = R0;',
        '\tR0 = P4; [P4 + 36] = R0;',
        '\tR0 = 24 (X); [P4 + 40] = R0;',
        '\tR0 = P4; R0 += 32;',
        '\tP0.H = 0; P0.L = 5;',
        '\tEXCPT 0;',
        '\tR0 = 0 (X); [P4 + 32] = R0; R0 = P4; R0 += 32;',
        '\tP0.H = 0; P0.L = 1;',
        '\tEXCPT 0;',
    ]
    return '\n'.join(lines) + '\n'


def build(outdir, func, presets, calls, tools, qemu=False):
    meta = json.load(open(os.path.join(outdir, 'map.json')))
    work = os.path.join(outdir, 'bench')
    os.makedirs(work, exist_ok=True)
    with open(os.path.join(work, 'soup.bin'), 'wb') as handle:
        handle.write(soup_bytes())
    asm = [harness_asm(func, presets, calls, qemu)]
    ld = ['SECTIONS {', f'  . = 0x{HARNESS:08X}; .text : {{ *(.text) }}']
    sections = [(m['target'], os.path.abspath(os.path.join(outdir, m['file']))) for m in meta]
    sections.append((SOUP_BASE, os.path.abspath(os.path.join(work, 'soup.bin'))))
    for target, path in sections:
        name = f'.r{target:08x}'
        asm.append(f'\t.section {name},"aw"\n\t.incbin "{path}"\n')
        ld.append(f'  . = 0x{target:08X}; {name} : {{ *({name}) }}')
    ld += ['}', 'ENTRY(_start)']
    with open(os.path.join(work, 'h.s'), 'w') as handle:
        handle.write('\n'.join(asm))
    with open(os.path.join(work, 'h.ld'), 'w') as handle:
        handle.write('\n'.join(ld) + '\n')
    subprocess.run([tools['as'], 'h.s', '-o', 'h.o'], cwd=work, check=True)
    subprocess.run([tools['ld'], '-T', 'h.ld', 'h.o', '-o', 'h.elf'], cwd=work, check=True)
    return os.path.join(work, 'h.elf')


def run(elf, sim):
    cmd = [sim, '--environment', 'virtual', '--model', 'bf527']
    for base, size in REGIONS:
        cmd += ['--memory-region', f'0x{base:X},0x{size:X}']
    cmd.append(elf)
    start = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True)
    seconds = time.perf_counter() - start
    return proc, seconds


def run_qemu(elf, qemu):
    """QEMU never exits on its own: read the 16 result bytes, then stop it."""
    cmd = [qemu, '-M', 'bf537-stamp', '-m', '64M', '-display', 'none', '-monitor', 'none',
           '-serial', 'stdio', '-kernel', elf]
    start = time.perf_counter()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    data = b''
    while len(data) < 24:
        chunk = proc.stdout.read(24 - len(data))
        if not chunk:
            break
        data += chunk
    seconds = time.perf_counter() - start
    proc.kill()
    err = proc.stderr.read()
    proc.wait()
    return subprocess.CompletedProcess(cmd, 0, data, err), seconds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('outdir')
    ap.add_argument('func')
    ap.add_argument('--calls', type=int, default=1000)
    ap.add_argument('--reg', action='append', default=[])
    ap.add_argument('--run', default=os.environ.get('BFIN_RUN', 'bfin-elf-run'))
    ap.add_argument('--as', dest='asm', default=os.environ.get('BFIN_AS', 'bfin-elf-as'))
    ap.add_argument('--ld', default=os.environ.get('BFIN_LD', 'bfin-elf-ld'))
    ap.add_argument('--qemu', help='qemu-system-bfin from github.com/vapier/qemu; '
                    'CYCLES then reads the virtual clock in ns, not DSP cycles')
    args = ap.parse_args()
    presets = []
    soup_next = SOUP_BASE + 0x800
    for item in args.reg:
        reg, value = item.split('=')
        if value == 'soup':
            presets.append((reg.upper(), soup_next))
            soup_next += 16 * PAGE
        else:
            presets.append((reg.upper(), int(value, 0)))
    elf = build(args.outdir, int(args.func, 16), presets, args.calls,
                {'as': args.asm, 'ld': args.ld}, bool(args.qemu))
    if args.qemu:
        proc, seconds = run_qemu(elf, args.qemu)
    else:
        proc, seconds = run(elf, args.run)
    if len(proc.stdout) < 24:
        sys.exit(f'simulator failed: {proc.stderr.decode(errors="replace").strip()}')
    cmin, cmax, slo, shi, _, check = struct.unpack('<IIIIII', proc.stdout[:24])
    total = slo | shi << 32
    print(json.dumps({
        'func': args.func, 'calls': args.calls,
        'cycles_min': cmin, 'cycles_max': cmax,
        'cycles_mean': round(total / args.calls, 1), 'cycles_total': total,
        'soup_checksum': f'{check:08x}',
        'host_s': round(seconds, 3),
        'sim_mcycles_per_s': round(total / seconds / 1e6, 2),
    }))


if __name__ == '__main__':
    main()
