"""Tube curve for the master output: curve, DRIVE steps, DSP parameter block and a bit-exact model of the DSP routine
that tools/patch/tube_curve.py puts in place of Korg's soft clipper (docs/messungen/2026-11-20-roehrenkurve.md).

The curve follows the Valve Force stage of the ESX/EMX: one 12AX7 as a differential pair, about 8.7 V across each
triode, 100 uA tail current. With the grid voltage u it is symmetric and tanh-like, 50 % at +-0.14 V, saturated from
+-0.34 V (Koren triode model, fitted at 9 V by hand, so the shape is sound, the dB values are not).

In the DSP the curve is an odd polynomial in v = u / 0.37 V, clamped beyond |v| = 1:

    p(v) = c1 v + c3 v^3 + c5 v^5 + c7 v^7,   p(1) = 1, max. error 0.0045 against the Koren model

TUBE DRIVE sets the grid voltage at full scale, D. TUBE ASYM drives the positive half softer than the negative one, so the
curve is no longer odd: the 2nd harmonic of a triode stage. After the curve a one-pole lowpass whose corner falls with
DRIVE softens the highs. The DSP computes, per sample and channel (x in Q31, y the channel's lowpass state):

    v = sat((h * x) << s)            h = g for x < 0, else gp; g * 2^s = D / 0.37 (g in Q15, s a shift), gp = g * k(ASYM)
    w = v * v
    t = sat((v * (q1 + w (q3 + w (q5 + w q7)))) << e)
    y = sat(y + a * sat(t - y))      a(DRIVE) in Q15: corner LP_HZ at 48 kHz

with q_k = c_k * N / 2^e and N = 1 / p(min(D / 0.37, 1)), so full scale stays full scale at every step (ASYM only lowers
the positive half). The DSP takes each multiplier operand's high half, so the coefficients count with 16 bits; model()
repeats every rounding and saturation of the instructions, tools/dsp/tube_qemu.py checks it against the QEMU DSP core.

Block, 12 words at DSP 0xFF803FD0 (the ARM writes the 10 words from 0xFF803FD8, one host port write of 20 halfwords):

    +0x00 y left   +0x04 y right   (lowpass state, the DSP's own; the boot stream leaves it zero)
    +0x08 gp (Q15 in the high half)   +0x0C a (high half)
    +0x10 g (high half)   +0x14 s   +0x18 e   +0x1C q7 (high half)
    +0x20 q5   +0x24 q3   +0x28 q1   +0x2C on (0 = Korg's clipper, bit for bit)

The ARM keeps the DRIVE rows (a, g, s, e, q7, q5, q3, q1, on) and the ASYM factors k as halfwords (kh, 0x8000 = 1) and
works out gp = ((g >> 16) * kh >> 15) << 16 itself (script_menu.s, tube_tick).

    python3 tools/dsp/tube_model.py            prints the rows of every step
"""

import math
import struct

BLOCK = 0xFF803FD0                # the DSP's P1: lowpass state, then the parameters
BLOCK_SIZE = 48
PARAM = 0xFF803FD8                # what the ARM writes: gp, a, g, s, e, q7, q5, q3, q1, on
PARAM_SIZE = 40
RATE = 48000
U_SAT = 0.37                      # grid volts at |v| = 1
COEF = (1.541016344553768, -0.21827883570175097, -0.6864913622578008, 0.36375385340578426)   # c1, c3, c5, c7
STEPS = (0.05, 0.08, 0.13, 0.2, 0.32, 0.5, 0.8)   # TUBE DRIVE 1..7: grid volts at full scale
DEFAULT_STEP = 4
LP_HZ = (16000, 14000, 12500, 11000, 10000, 9000, 8000)   # lowpass corner per TUBE DRIVE step
ASYM_STEPS = 8                    # TUBE ASYM 0..7
ASYM_K = tuple(round((1 - 0.045 * n) * 32768) for n in range(ASYM_STEPS))   # gain of the positive half, 0x8000 = 1
HEADROOM = 0.9                    # largest |coefficient| and |partial sum| in Q31 units


def p(v):
    """The curve, float, v in grid volts / U_SAT."""
    v = max(-1.0, min(1.0, v))
    return sum(c * v ** (2 * k + 1) for k, c in enumerate(COEF))


def curve(x, step, asym=0):
    """Float output of the curve alone (no lowpass) for float input x (full scale 1) at DRIVE step 1..7."""
    gain = STEPS[step - 1] / U_SAT
    if x >= 0:
        gain_x = gain * ASYM_K[asym] / 32768
    else:
        gain_x = gain
    return p(gain_x * x) / p(gain)


def lp_coef(step):
    """The lowpass coefficient a of DRIVE step 1..7 as a float."""
    return 1 - math.exp(-2 * math.pi * LP_HZ[step - 1] / RATE)


def _s32(x):
    x &= 0xFFFFFFFF
    return x - (1 << 32) if x >> 31 else x


def _sat32(x):
    return max(-(1 << 31), min((1 << 31) - 1, x))


def _high(x):
    return _s32(x) >> 16


def _q31(f):
    return _sat32(round(f * (1 << 31)))


def row(step):
    """The 9 words the ARM keeps for DRIVE step 1..7 (signed ints): a, g, s, e, q7, q5, q3, q1, on = 1."""
    gain = STEPS[step - 1] / U_SAT
    shift = math.floor(math.log2(gain)) + 1           # gain = g * 2^shift, g in [0.5, 1)
    g = min(32767, round(gain / 2 ** shift * 32768))
    vmax = min(1.0, g / 32768 * 2 ** shift)
    norm = 1 / p(vmax)
    q = [c * norm for c in COEF]
    worst = max(max(abs(c) for c in q), _partial_max(q, vmax * vmax))
    e = max(0, math.ceil(math.log2(worst / HEADROOM)))
    q = [c / 2 ** e for c in q]
    a = min(32767, round(lp_coef(step) * 32768))
    words = [a << 16, g << 16, shift, e, _q31(q[3]) & ~0xFFFF, _q31(q[2]), _q31(q[1]), _q31(q[0]), 1]
    return [_s32(w) for w in words]


def gp(g, asym):
    """The gain word of the positive half, as the ARM works it out from the word g and TUBE ASYM 0..7."""
    return _s32((((g & 0xFFFFFFFF) >> 16) * ASYM_K[asym] >> 15) << 16)


def params(step, asym=0):
    """The 10 words the ARM writes for DRIVE step 1..7 and ASYM 0..7 (signed ints): gp, a, g, s, e, q7, q5, q3, q1, on."""
    r = row(step)
    return [gp(r[1], asym)] + r


def _partial_max(q, wmax, n=256):
    worst = 0.0
    for i in range(n + 1):
        w = wmax * i / n
        acc = q[3]
        for c in (q[2], q[1], q[0]):
            acc = acc * w + c
            worst = max(worst, abs(acc))
    return worst


def block(step, asym=0):
    """The bytes the ARM writes for DRIVE step 1..7 and ASYM 0..7, or the OFF block for step 0 (all zero: on = 0)."""
    if step == 0:
        return bytes(PARAM_SIZE)
    return struct.pack('<10i', *params(step, asym))


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


def _sub_sat(a, b):
    return _sat32(a - b)


def model(x, words, y=0):
    """(output, new lowpass state) of the routine for one Q31 sample x, the parameter words (as params() returns them)
    and the channel's lowpass state y."""
    gpos, a, g, s, e, q7, q5, q3, q1, on = words
    if not on:
        raise ValueError('on = 0 runs Korg clipper, not modelled here')
    v = _ashift(_mult32x16(g if x < 0 else gpos, x), s)
    w = _mult16(v, v)
    acc = _mult16(q7, w)
    acc = _sat32(acc + q5)
    acc = _mult16(acc, w)
    acc = _sat32(acc + q3)
    acc = _mult16(acc, w)
    acc = _sat32(acc + q1)
    t = _ashift(_mult32x16(acc, v), e)
    y = _sat32(y + _mult32x16(a, _sub_sat(t, y)))
    return y, y


def run(samples, words, y=0):
    """The routine over a stream of Q31 samples of one channel: (outputs, last lowpass state)."""
    out = []
    for x in samples:
        o, y = model(x, words, y)
        out.append(o)
    return out, y


def _curve_only(x, words):
    """model() without the lowpass: a = 1 would be the bypass, so take t directly."""
    gpos, a, g, s, e, q7, q5, q3, q1, on = words
    v = _ashift(_mult32x16(g if x < 0 else gpos, x), s)
    w = _mult16(v, v)
    acc = _sat32(_mult16(q7, w) + q5)
    acc = _sat32(_mult16(acc, w) + q3)
    acc = _sat32(_mult16(acc, w) + q1)
    return _ashift(_mult32x16(acc, v), e)


def main():
    for step in range(1, len(STEPS) + 1):
        words = row(step)
        worst = max(max(abs(_curve_only(_q31(i / 512), params(step, asym)) / 2 ** 31 - curve(i / 512, step, asym))
                        for i in range(-512, 512)) for asym in range(ASYM_STEPS))
        print(f'DRIVE {step} ({STEPS[step - 1]} V, {LP_HZ[step - 1]} Hz): ' + ' '.join(f'{w & 0xFFFFFFFF:08x}' for w in words)
              + f'  max |model - curve| {worst:.5f}')
    print('ASYM k: ' + ' '.join(f'{k:#06x}' for k in ASYM_K))


if __name__ == '__main__':
    main()
