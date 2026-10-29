# SPDX-License-Identifier: GPL-2.0-only
"""How bright each display pixel looks while the firmware switches it.

The firmware drives the LCD with on and off only: the controller gets no grey
command, and no pixel is toggled between two frames to fake a level
(docs/messungen/2026-10-12-lcd-helligkeit.md). What looks dimmed on the device
is the liquid crystal: a pixel follows its switching slowly, so text the
firmware blinks every 280 ms never reaches full contrast. This models that
response, one first-order lag per pixel, and hands out 16 levels.

TAU_ON comes from a slow-motion video, TAU_OFF is the owner's estimate by eye
(see below), neither is a precise measurement. They are set here and nowhere else; the service takes them from `--lcd-tau-on` and
`--lcd-tau-off`, else from E2_LCD_TAU_ON and E2_LCD_TAU_OFF (seconds), else
these defaults."""

import math
import os

LEVELS = 16
TAU_ON = 0.040      # seconds for a pixel going dark (measured 2026-10-13, slow-motion video)
TAU_OFF = 0.20      # seconds for a pixel going clear: the owner's choice on 2026-10-29 (0.30 looked too slow in the
                    # emulator), after the estimate by eye on the device on 2026-10-27; not a measurement. The 0.028 s fitted to the slow-motion video of 2026-10-13 was too low: it took the fast
                    # first part of the edge and left out the long flat rest; a walking figure drags a smear.
WIDTH, HEIGHT = 128, 64


def taus(on=None, off=None, env=None):
    """(tau_on, tau_off) in seconds: the arguments, else the environment, else the defaults."""
    env = os.environ if env is None else env
    out = []
    for value, name, default in ((on, "E2_LCD_TAU_ON", TAU_ON), (off, "E2_LCD_TAU_OFF", TAU_OFF)):
        raw = value if value is not None else env.get(name)
        try:
            tau = default if raw in (None, "") else float(raw)
        except ValueError:
            raise ValueError(f"{name}: {raw!r} ist keine Zahl.") from None
        if not 0 < tau < 10:
            raise ValueError(f"{name}: {tau:g} s liegt nicht zwischen 0 und 10 s.")
        out.append(tau)
    return tuple(out)


class LcdResponse:
    """Fed the 1-bit display (8 pages of 128 columns, bit 0 the top row) and device time."""

    def __init__(self, tau_on=None, tau_off=None):
        self.tau_on, self.tau_off = taus(tau_on, tau_off)
        self.target = None          # the 1-bit display last seen, page-major
        self.t = 0                  # device time of that display, ns
        self.out = bytearray(WIDTH * HEIGHT)    # one level per pixel, row by row
        self.moving = {}            # pixel -> level (0..1) of those not yet at their target

    @staticmethod
    def _flat(fb, reverse=False):
        """The display as bytes, page-major; with `reverse` (the controller got 0xA7) dark and clear swapped."""
        flat = bytes(b for row in fb for b in row)
        return bytes(b ^ 0xFF for b in flat) if reverse else flat

    @staticmethod
    def _pixel(page_byte, bit):
        """Row-major index of bit `bit` of byte `page_byte` (page * 128 + column)."""
        page, x = divmod(page_byte, WIDTH)
        return (page * 8 + bit) * WIDTH + x

    def shades(self):
        return bytes(self.out)

    def settle(self, fb, reverse=False):
        """Show fb at once, every pixel at its end level."""
        flat = self._flat(fb, reverse)
        for i, b in enumerate(flat):
            for bit in range(8):
                self.out[self._pixel(i, bit)] = (LEVELS - 1) * ((b >> bit) & 1)
        self.target, self.moving = flat, {}

    def update(self, fb, t_ns, reverse=False):
        """Advance to device time t_ns with fb as what the firmware shows (reversed when the controller is). True when a level changed.
        Reversing swaps every pixel's target at once, so each one follows with its own lag like any other change."""
        flat = self._flat(fb, reverse)
        if self.target is None:
            self.settle(fb, reverse)
            self.t = t_ns
            return True
        dt = max(0.0, (t_ns - self.t) / 1e9)
        self.t = t_ns
        # a pixel that flipped did so some time in this step: it moves for half of it on average
        fresh = {}
        if flat != self.target:
            for i, (a, b) in enumerate(zip(self.target, flat)):
                if a != b:
                    for bit in range(8):
                        if (a ^ b) >> bit & 1:
                            p = self._pixel(i, bit)
                            if p not in self.moving:
                                fresh[p] = float((a >> bit) & 1)
        changed = False
        for pool, step in ((self.moving, dt), (fresh, dt / 2)):
            k_on, k_off = 1 - math.exp(-step / self.tau_on), 1 - math.exp(-step / self.tau_off)
            for p, v in list(pool.items()):
                y, x = divmod(p, WIDTH)
                goal = (flat[(y >> 3) * WIDTH + x] >> (y & 7)) & 1
                v += (goal - v) * (k_on if goal else k_off)
                level = round(v * (LEVELS - 1))
                if level == (LEVELS - 1) * goal:
                    self.moving.pop(p, None)
                else:
                    self.moving[p] = v
                if self.out[p] != level:
                    self.out[p], changed = level, True
        self.target = flat
        return changed
