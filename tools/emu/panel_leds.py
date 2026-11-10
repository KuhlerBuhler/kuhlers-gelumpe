# SPDX-License-Identifier: GPL-2.0-only
"""The panel controller's side of the LEDs: every LED change with its device time, and when it lights.

The firmware sends `00 LED value` over UART0 (machine.py, Machine.panel). What the panel controller does
with it (docs/hintergrund/panel-controller.md, read from its code, not run):

- derived: 88 LEDs (0x00 to 0x57) in a matrix of 11 rows by 8 PWM channels, PWM period 5000 counts at
  40 MHz / 4, about 2 kHz; the value becomes a duty cycle `value * period / 255`, linear, no gamma, the
  pads as well. The scheduler ticks every 100 us.
- Modellannahme: the controller takes a message within one tick of its last byte, and the rows are lit
  one per PWM period, so a row comes round every 11 periods (5.5 ms); a new value shows from the next
  round. A value that is replaced before then never lights.

Power save dims in the firmware (BLECH's pad_colors patch sends a quarter), not in the controller: the
values here are already the dimmed ones. `02 b` from the firmware may touch the LEDs; what it does is
open, the model ignores it.
"""

import collections

LED_COUNT = 0x58
TICK_NS = 100_000            # derived: dual timer 1 reloads 4000 at 40 MHz
PWM_NS = 500_000             # derived: 5000 counts at 10 MHz
ROWS = 11                    # derived: matrix table 0x8460 of the panel code
ROUND_NS = ROWS * PWM_NS     # Modellannahme: one row per PWM period
LOG_MAX = 1 << 16            # changes kept; the service reads them every 20 ms, a case right after its run


def duty(value):
    """The share of the time an LED with this value is on, 0 to 1 (derived: linear in the panel code)."""
    return max(0, min(255, value)) / 255


def lit_at(t_ns):
    """When a message the panel got at `t_ns` shows (Modellannahme, see the module text)."""
    return -(-(t_ns + TICK_NS) // ROUND_NS) * ROUND_NS


class PanelLeds:
    """Every change of an LED value, in order: (number, device ns the panel got it, ns it lights, led, value).

    `number` counts on across a full log, so a reader that remembers the last one it saw knows what it missed."""

    def __init__(self):
        self.value = {}
        self.log = collections.deque(maxlen=LOG_MAX)
        self.count = 0           # changes so far
        self.messages = 0        # LED messages so far, a resent value included

    def message(self, t_ns, led, value):
        self.messages += 1
        if self.value.get(led, 0) == value:
            return
        self.value[led] = value
        self.count += 1
        self.log.append((self.count, t_ns, lit_at(t_ns), led, value))

    def since(self, number):
        """The changes after `number`, and whether some of them fell out of the log already."""
        if not self.log or number >= self.count:
            return [], False
        first = self.log[0][0]
        lost = number + 1 < first
        skip = max(0, number + 1 - first)
        return [e for i, e in enumerate(self.log) if i >= skip], lost

    def between(self, start_ns, end_ns, leds=None):
        """The changes the panel got from `start_ns` up to `end_ns`, of the given LEDs or all."""
        return [e for e in self.log if start_ns <= e[1] < end_ns and (leds is None or e[3] in leds)]


def shown(changes, before=None):
    """The changes as the controller lights them: per LED only the last value of each row round.

    `before` is {led: value} at the start. Returns [(ns it lights, led, value)] where the value changes."""
    last = dict(before or {})
    pending = {}
    for _, _, at, led, value in changes:
        pending[(at, led)] = value
    out = []
    for (at, led), value in sorted(pending.items()):
        if last.get(led, 0) != value:
            out.append((at, led, value))
            last[led] = value
    return out


def blinks(changes, before=None, gap_ns=50_000_000):
    """Visible dark gaps: an LED that lit goes to 0 and lights again within `gap_ns`, as the controller shows it.

    Returns [(led, ns it went dark, ns it was dark)]."""
    out, dark = [], {}
    last = dict(before or {})
    for at, led, value in shown(changes, before):
        if value == 0 and last.get(led, 0):
            dark[led] = at
        elif value and led in dark:
            went = dark.pop(led)
            if at - went <= gap_ns:
                out.append((led, went, at - went))
        last[led] = value
    return out
