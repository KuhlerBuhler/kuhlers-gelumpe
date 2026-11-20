"""Tube curve for the master output: curve, DRIVE steps, DSP parameter block and a bit-exact model of the DSP routine
that tools/patch/tube_curve.py puts in place of Korg's soft clipper (docs/messungen/2026-11-20-roehrenkurve.md).

The curve follows the Valve Force stage of the ESX/EMX: one 12AX7 as a differential pair, about 8.7 V across each
triode, 100 uA tail current. With the grid voltage u it is symmetric and tanh-like, 50 % at +-0.14 V, saturated from
+-0.34 V (Koren triode model, fitted at 9 V by hand, so the shape is sound, the dB values are not).

In the DSP the curve is an odd polynomial in v = u / 0.37 V, clamped beyond |v| = 1:

    p(v) = c1 v + c3 v^3 + c5 v^5 + c7 v^7,   p(1) = 1, max. error 0.0045 against the Koren model

TUBE DRIVE sets the grid voltage at full scale, D. The DSP computes, per sample and channel (x in Q31):

    v = sat((g * x) << s)            g * 2^s = D / 0.37 (g in Q15, s a shift)
    w = v * v
    y = sat((v * (q1 + w (q3 + w (q5 + w q7)))) << e)

with q_k = c_k * N / 2^e and N = 1 / p(min(D / 0.37, 1)), so full scale stays full scale at every step. The DSP takes
each multiplier operand's high half, so the coefficients count with 16 bits; model() repeats every rounding and
saturation of the instructions, tools/dsp/tube_qemu.py checks it against the QEMU DSP core.

Parameter block, 8 words at DSP 0xFF803FE0 (one host port write of 16 halfwords):

    +0x00 g (Q15 in the high half)   +0x04 s   +0x08 e   +0x0C q7 (high half)
    +0x10 q5   +0x14 q3   +0x18 q1   +0x1C on (0 = Korg's clipper, bit for bit)

    python3 tools/dsp/tube_model.py            prints the block of every step
"""

import math
import struct

PARAM = 0xFF803FE0
PARAM_SIZE = 32
U_SAT = 0.37                      # grid volts at |v| = 1
COEF = (1.541016344553768, -0.21827883570175097, -0.6864913622578008, 0.36375385340578426)   # c1, c3, c5, c7
STEPS = (0.05, 0.08, 0.13, 0.2, 0.32, 0.5, 0.8)   # TUBE DRIVE 1..7: grid volts at full scale
DEFAULT_STEP = 4
HEADROOM = 0.9                    # largest |coefficient| and |partial sum| in Q31 units


def p(v):
    """The curve, float, v in grid volts / U_SAT."""
    v = max(-1.0, min(1.0, v))
    return sum(c * v ** (2 * k + 1) for k, c in enumerate(COEF))


def curve(x, step):
    """Float output for float input x (full scale 1) at DRIVE step 1..7."""
    gain = STEPS[step - 1] / U_SAT
    return p(gain * x) / p(gain)


def _s32(x):
    x &= 0xFFFFFFFF
    return x - (1 << 32) if x >> 31 else x


def _sat32(x):
    return max(-(1 << 31), min((1 << 31) - 1, x))


def _high(x):
    return _s32(x) >> 16


def _q31(f):
    return _sat32(round(f * (1 << 31)))


def params(step):
    """The 8 words of the parameter block for DRIVE step 1..7 (signed ints), on = 1."""
    gain = STEPS[step - 1] / U_SAT
    shift = math.floor(math.log2(gain)) + 1           # gain = g * 2^shift, g in [0.5, 1)
    g = min(32767, round(gain / 2 ** shift * 32768))
    vmax = min(1.0, g / 32768 * 2 ** shift)
    norm = 1 / p(vmax)
    q = [c * norm for c in COEF]
    worst = max(max(abs(c) for c in q), _partial_max(q, vmax * vmax))
    e = max(0, math.ceil(math.log2(worst / HEADROOM)))
    q = [c / 2 ** e for c in q]
    words = [g << 16, shift, e, _q31(q[3]) & ~0xFFFF, _q31(q[2]), _q31(q[1]), _q31(q[0]), 1]
    return [_s32(w) for w in words]


def _partial_max(q, wmax, n=256):
    worst = 0.0
    for i in range(n + 1):
        w = wmax * i / n
        acc = q[3]
        for c in (q[2], q[1], q[0]):
            acc = acc * w + c
            worst = max(worst, abs(acc))
    return worst


def block(step):
    """Parameter block bytes for step 1..7, or the OFF block for step 0 (all zero: on = 0)."""
    if step == 0:
        return bytes(PARAM_SIZE)
    return struct.pack('<8i', *params(step))


# Instruction semantics of the routine, as the Blackfin computes them.

def _mult32x16(a, x):
    """A1 = a.H * x.L (M), A0 = a.H * x.H; A1 = A1 >>> 15; R = (A0 += A1)."""
    ah, xh, xl = _high(a), _high(x), x & 0xFFFF
    a0 = (ah * xh) << 1                 # fractional, into the 40-bit accumulator: no saturation
    a1 = (ah * xl) >> 15                # mixed mode, integer product
    return _sat32(a0 + a1)


def _mult16(a, b):
    """R = a.H * b.H, fractional into a 32-bit register."""
    ah, bh = _high(a), _high(b)
    if ah == bh == -32768:
        return (1 << 31) - 1
    return (ah * bh) << 1


def _ashift(x, by):
    """R = ASHIFT x BY by.L (S)."""
    n = by & 0x3F
    n = n - 64 if n & 0x20 else n
    if n >= 0:
        return _sat32(x << n)
    return x >> -n


def model(x, words):
    """Output of the routine for one Q31 sample x and the parameter words (as params() returns them)."""
    g, s, e, q7, q5, q3, q1, on = words
    if not on:
        raise ValueError('on = 0 runs Korg clipper, not modelled here')
    v = _ashift(_mult32x16(g, x), s)
    w = _mult16(v, v)
    acc = _mult16(q7, w)
    acc = _sat32(acc + q5)
    acc = _mult16(acc, w)
    acc = _sat32(acc + q3)
    acc = _mult16(acc, w)
    acc = _sat32(acc + q1)
    return _ashift(_mult32x16(acc, v), e)


def main():
    for step in range(1, len(STEPS) + 1):
        words = params(step)
        worst = max(abs(model(_q31(i / 512), words) / 2 ** 31 - curve(i / 512, step)) for i in range(-512, 512))
        print(f'DRIVE {step} ({STEPS[step - 1]} V): ' + ' '.join(f'{w & 0xFFFFFFFF:08x}' for w in words)
              + f'  max |model - curve| {worst:.5f}')


if __name__ == '__main__':
    main()
