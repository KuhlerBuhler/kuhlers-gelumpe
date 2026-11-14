# SPDX-License-Identifier: GPL-2.0-only
"""The display light: three GPIO pins the firmware drives, GPIO 6.3, 6.4 and 6.5 for red, green and blue.

A level of 0 or 15 is a plain pin; a level between is a software PWM of 16 ticks of 0.5 ms, one period of
8 ms (measured in the emulator 2026-11-10: red at 5 rises every 8000 us and stays on for 2500 us). Power save
lights red and green in turn, each once every 27 ms. The eye, and the page, see the mean: each pin's share
of on-time over its last full period, from rising edge to rising edge. A pin that has not changed for
STEADY_NS is plain on or off.

Until the firmware first writes one of the pins nothing is known, and `levels` says None: the page then
keeps its own colours.
"""

PINS = (0x08, 0x10, 0x20)     # bits of GPIO register pair 3: red, green, blue
MASK = 0x38
STEADY_NS = 100_000_000       # longer than any PWM period the firmware uses (power save: 27 ms)


class Pin:
    def __init__(self, level, t_ns):
        self.level, self.since = level, t_ns
        self.rise = None          # device ns of the last rising edge
        self.lit = 0              # ns on since that edge
        self.duty = None          # share of on-time in the last full period

    def change(self, t_ns, level):
        if level == self.level:
            return
        if self.level:
            self.lit += t_ns - self.since
        if level:
            if self.rise is not None:
                self.duty = self.lit / (t_ns - self.rise)
            self.rise, self.lit = t_ns, 0
        self.level, self.since = level, t_ns

    def value(self, t_ns):
        if self.duty is None or t_ns - self.since > STEADY_NS:
            return 1.0 if self.level else 0.0
        return self.duty


class Backlight:
    def __init__(self):
        self.pins = None

    def write(self, t_ns, state):
        """The pins after a write of the firmware that touched them, `state` the bits of MASK."""
        if self.pins is None:
            self.pins = [Pin(bool(state & bit), t_ns) for bit in PINS]
            return
        for pin, bit in zip(self.pins, PINS):
            pin.change(t_ns, bool(state & bit))

    def off(self, t_ns):
        """Power gone: the light is dark."""
        self.pins = [Pin(False, t_ns) for _ in PINS]

    def levels(self, t_ns):
        """Red, green and blue as the eye sees them, 0 to 255 each, or None before the firmware drove the pins."""
        if self.pins is None:
            return None
        return [round(pin.value(t_ns) * 255) for pin in self.pins]
