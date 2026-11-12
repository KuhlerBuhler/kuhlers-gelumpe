# SPDX-License-Identifier: GPL-2.0-only
"""A model of the electribe 2 DSP for checks, not for sound (docs/messungen/2026-11-12-dsp-modell.md).

The emulator does not run the DSP's own program; the host port (machine.py, DSP_DATA and DSP_CTRL) takes every transfer and
reads unmodelled words as 0. This model listens to the same port and keeps what the CPU told the DSP, so a check can ask the
DSP's side of a question instead of hooking one firmware routine: "is part 1 switched on at the DSP after EXIT + pad?".

What it decodes (measured, Hacktribe 2.02, Korg's red and blue 2.02):

- Every write transfer (command 0xAB) to the mailbox 0xFF900A34 is one message: word 0 is 0x106, word 1 the command, the rest
  its data. The CPU always sends whole 16-word blocks; the words behind a message are stack left-overs.
- Command 0 sets DSP parameters: word 2 is the number of pairs minus one, then (parameter, value) pairs
  (0xC0011F54 one pair, 0xC001203C two; blue 0xC000E71C).
- Parameter PART_ON[build] + 0x6D * part is the part's switch at the DSP: 1 on, 0 off. The firmware switches a part on with
  every note it starts (Sampler 0xC0093988) and off in Copy Part's part sound setup (0xC0093A20, blue 0xC0081680); for a
  stereo sample both parts of the pair in one message.

What it does not know: the DSP's own reaction. It cannot say whether a part that was switched off and on again sounds (on
the device after #506's first fix it did not, docs/messungen/2026-11-12-dsp-modell.md); level, pan and mute never reach the
DSP as parameters of their own (level and pan go with each note, a muted part sends no note).

    from dsp_model import DspModel
    dsp = DspModel.attach(machine)
    mark = dsp.mark()
    ...                               # drive the firmware
    dsp.part_on(0), dsp.switched_off(0, since=mark)
"""

MAILBOX = 0xFF900A34
HEADER = 0x106                  # word 0 of every mailbox message
SET_PARAMS = 0                  # command: set DSP parameters
PART_ON = {"sampler": 0x2C2, "synth": 0x2A8}   # the part's switch at the DSP, parameter of part 0
PART_STRIDE = 0x6D              # parameters per part
PARTS = 16
WRITE, CTRL_WORDS = 0xAB, 7


class DspModel:
    """What the CPU told the DSP over the host port: the last value of every parameter, and every change of a part switch."""

    def __init__(self, machine):
        from machine import DSP_CTRL, DSP_DATA, DSP_SYNC
        self.m = machine
        self.part_base = PART_ON["synth" if machine.profile.build == "synth" else "sampler"]
        self.params = {}            # parameter -> last value
        self.switches = []          # (device time in ms, part, value) for every write of a part switch, in order
        self.messages = 0           # mailbox messages seen
        self._ctl, self._xfer = [], None
        original = machine.write

        def write(a, v):
            if a == DSP_CTRL:
                if not self._ctl and v & 0xFFFF == DSP_SYNC:     # Korg's build writes a lone sync word between frames
                    return original(a, v)
                self._ctl.append(v & 0xFFFF)
                if len(self._ctl) == CTRL_WORDS:
                    cmd, lo, hi, count = self._ctl[:4]
                    self._ctl = []
                    self._flush()
                    if cmd == WRITE and (hi << 16) | lo == MAILBOX:
                        self._xfer = [count, []]
            elif a == DSP_DATA and self._xfer is not None:
                self._xfer[1].append(v & 0xFFFF)
                if len(self._xfer[1]) >= self._xfer[0]:
                    self._flush()
            return original(a, v)
        machine.write = write

    @classmethod
    def attach(cls, machine):
        """The model of this machine, made on first use (one listener per machine)."""
        model = getattr(machine, "dsp_model", None)
        if model is None:
            model = machine.dsp_model = cls(machine)
        return model

    def _flush(self):
        x, self._xfer = self._xfer, None
        if x and x[1]:
            self.message(x[1])

    def message(self, words):
        """One mailbox message (its words as written)."""
        self.messages += 1
        if len(words) < 5 or words[0] != HEADER or words[1] != SET_PARAMS:
            return
        pairs = words[2] + 1
        for i in range(pairs):
            at = 3 + 2 * i
            if at + 1 >= len(words):
                break
            self.set_param(words[at], words[at + 1])

    def set_param(self, param, value):
        self.params[param] = value
        part, k = divmod(param - self.part_base, PART_STRIDE)
        if k == 0 and 0 <= part < PARTS:
            self.switches.append((self.m.time_ns // 1_000_000, part, value))

    # ---- what a check asks -------------------------------------------------------
    def mark(self):
        """A point in the switch log; pass it as `since` to look only at what came after."""
        return len(self.switches)

    def part_on(self, part):
        """True or False: the last value the part's switch got; None when the firmware never sent it."""
        value = self.params.get(self.part_base + PART_STRIDE * part)
        return None if value is None else value != 0

    def switched_off(self, part, since=0):
        """Device times (ms) at which the part was switched off at the DSP after `since`."""
        return [t for t, p, v in self.switches[since:] if p == part and v == 0]

    def parts_switched_off(self, since=0):
        return sorted({p for _, p, v in self.switches[since:] if v == 0})
