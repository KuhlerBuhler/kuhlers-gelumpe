# SPDX-License-Identifier: GPL-2.0-only
"""A model of the electribe 2 DSP for checks, not for sound (docs/messungen/2026-11-12-dsp-modell.md).

The emulator does not run the DSP's own program (Blackfin code in the firmware at 0xC00F9E10, tools/dsp/dsp_extract.py). This
model listens to the host port (machine.py, DSP_DATA and DSP_CTRL), keeps an image of the DSP memory the CPU writes, and
answers the reads it models, so a check can ask the DSP's side of a question instead of hooking one firmware routine.

Host port: every transfer starts with 7 control words [0xA9 read | 0xAB write, address low, address high, count of 16-bit
words, 2, 0, 0]; a 32-bit DSP word travels low half first.

Mailbox 0xFF900A34 (DSP handler 0xFFA04EC8): every write is one message, word 0 is 0x106, word 1 the command; the CPU always
sends 16 words, the words behind a message are stack left-overs. Parameter N lives at 0xFF800000 + 4N, from 0x4000 on at
0xFF8F0000 + 4N (DSP 0xFFA071CC). What the commands do at the DSP, read from its jump table 0x01F02B84:

    0     (n-1, then n pairs p, v)          slot p = v << 16
    1     (n-1, then n triples p, hi, lo)   slot p = hi << 16 | lo
    2     (n-1, start, n values v)          slots start.. = v << 16
    0x16  (p, a, b)                         slot p = a << 16, the word after it = b << 16
    0x31  (n-1, start, n pairs hi, lo)      slots start.. = hi << 16 | lo

The other commands (notes: 9, 0x1F, 0x26, 0x2B to 0x39) are counted, not applied.

Parameter PART_ON[build] + 0x6D * part is the part's switch at the DSP: 1 on, 0 off; the DSP's audio loop (0xFFA019DE) skips
a switched-off part and clears its output state. The firmware switches a part on with every note it starts (Sampler
0xC0093988) and off in Copy Part's part sound setup (0xC0093A20, blue 0xC0081680).

FIFO 0xFF900018 / 0xFF900098 (DSP handler 0x17FF8): two buffers of 32 words; a word is flags << 28 | channel << 22 |
code << 16 | value, channel 62 ends the buffer. Code 0x20 on channels 0 to 32 is the tempo in hundredths of BPM; the DSP
keeps it at 0xFF900004 and recomputes the channel's tempo-synced effect (0x17C78).

Reads the model answers: the output peak, 0xFF9030F4 (left) and 0xFF9030F8 (right), fields +0x50/+0x54 of the output block
0xFF9030A4. The DSP keeps max(abs(sample)) of the final stereo sum there (0xFFA01952), 1.31, saturating at 0x7FFFFFFF; the
CPU reads both every 40 ms for the meter LEDs (0xC0014080) and sets them back to 0 with command 0x31. The model has no
sound of its own: `output(left, right)` sets the level the DSP would see, and the peak words hold the larger of that level
and what the CPU wrote. Every other read stays with machine.py (0).

    from dsp_model import DspModel
    dsp = DspModel.attach(machine)
    mark = dsp.mark()
    ...                               # drive the firmware
    dsp.part_on(0), dsp.switched_off(0, since=mark), dsp.tempo
"""

from collections import Counter

MAILBOX = 0xFF900A34
FIFO = (0xFF900018, 0xFF900098)
HEADER = 0x106                  # word 0 of every mailbox message
SET_PARAMS = 0                  # command: set DSP parameters
PART_ON = {"sampler": 0x2C2, "synth": 0x2A8}   # the part's switch at the DSP, parameter of part 0
PART_STRIDE = 0x6D              # parameters per part
PARTS = 16
READ, WRITE, CTRL_WORDS = 0xA9, 0xAB, 7
PEAK = 0xFF9030F4               # output peak, left at +0, right at +4
FULL_SCALE = 0x7FFFFFFF
FIFO_END, FIFO_TEMPO, FIFO_CHANNELS = 62, 0x20, 33


def slot(param):
    """DSP address of parameter `param` (0xFFA071CC)."""
    return (0xFF800000 if param < 0x4000 else 0xFF8F0000) + 4 * param & 0xFFFFFFFF


class DspModel:
    """What the CPU told the DSP over the host port, and the DSP's answer to the reads the model knows."""

    def __init__(self, machine):
        from machine import DSP_CTRL, DSP_DATA, DSP_SYNC
        self.m = machine
        self.part_base = PART_ON["synth" if machine.profile.build == "synth" else "sampler"]
        self.params = {}            # parameter -> last value
        self.mem = {}               # DSP address -> 16-bit word, as written
        self.switches = []          # (device time in ms, part, value) for every write of a part switch, in order
        self.messages = 0           # mailbox messages seen
        self.commands = Counter()   # mailbox command -> messages
        self.fifo = []              # (device time in ms, channel, code, value) for every FIFO entry
        self.tempo = {}             # channel -> tempo in hundredths of BPM, as the FIFO last set it
        self.level = (0, 0)         # what the DSP would see at its output, 1.31
        self._ctl, self._xfer = [], None
        write, read = machine.write, getattr(machine, "dsp_read", None)

        def on_write(a, v):
            if a == DSP_CTRL:
                if not self._ctl and v & 0xFFFF == DSP_SYNC:     # Korg's build writes a lone sync word between frames
                    return write(a, v)
                self._ctl.append(v & 0xFFFF)
                if len(self._ctl) == CTRL_WORDS:
                    cmd, lo, hi, count = self._ctl[:4]
                    self._ctl = []
                    self._flush()
                    if cmd == WRITE:
                        self._xfer = [(hi << 16) | lo, count, []]
            elif a == DSP_DATA and self._xfer is not None:
                self._xfer[2].append(v & 0xFFFF)
                if len(self._xfer[2]) >= self._xfer[1]:
                    self._flush()
            return write(a, v)
        machine.write = on_write

        if read is not None:
            def on_read():
                x = machine.dsp_xfer
                addr = x[1] if x and x[0] == READ and x[2] > 0 else None
                value = read()
                return value if addr is None or not self.answers(addr) else self.read(addr)
            machine.dsp_read = on_read

    @classmethod
    def attach(cls, machine):
        """The model of this machine, made on first use (one listener per machine)."""
        model = getattr(machine, "dsp_model", None)
        if model is None:
            model = machine.dsp_model = cls(machine)
        return model

    def _now(self):
        return self.m.time_ns // 1_000_000

    def _flush(self):
        x, self._xfer = self._xfer, None
        if not x or not x[2]:
            return
        addr, _, words = x
        if addr == MAILBOX:
            self.message(words)
        elif addr in FIFO:
            self.fifo_buffer([words[i] | words[i + 1] << 16 for i in range(0, len(words) - 1, 2)])
        else:
            for i, w in enumerate(words):
                self.mem[addr + 2 * i] = w

    # ---- memory --------------------------------------------------------------------
    def put(self, addr, value):
        """One 32-bit DSP word."""
        self.mem[addr], self.mem[addr + 2] = value & 0xFFFF, value >> 16 & 0xFFFF

    def word(self, addr):
        return self.mem.get(addr, 0) | self.mem.get(addr + 2, 0) << 16

    def answers(self, addr):
        return PEAK <= addr < PEAK + 8

    def read(self, addr):
        """The 16-bit word the DSP hands back at `addr`."""
        base = addr & ~3
        if PEAK <= base < PEAK + 8:
            value = max(self.word(base), min(self.level[(base - PEAK) // 4], FULL_SCALE))
            return value >> 16 if addr & 2 else value & 0xFFFF
        return self.mem.get(addr, 0)

    def output(self, left, right=None):
        """The level the DSP would see at its output, as a fraction of full scale (0 to 1) per channel."""
        right = left if right is None else right
        self.level = tuple(min(int(round(abs(x) * FULL_SCALE)), FULL_SCALE) for x in (left, right))

    def peak(self):
        """The output peak words (left, right) as the CPU would read them now."""
        return tuple(self.read(PEAK + 4 * c) | self.read(PEAK + 4 * c + 2) << 16 for c in (0, 1))

    # ---- mailbox -------------------------------------------------------------------
    def message(self, words):
        """One mailbox message (its words as written)."""
        self.messages += 1
        if len(words) < 3 or words[0] != HEADER:
            return
        cmd, d = words[1], words[2:]
        self.commands[cmd] += 1
        n = d[0] + 1
        if cmd == SET_PARAMS:
            for i in range(n):
                if 2 + 2 * i < len(d):
                    self.set_param(d[1 + 2 * i], d[2 + 2 * i], d[2 + 2 * i] << 16)
        elif cmd == 1:
            for i in range(n):
                if 3 + 3 * i < len(d):
                    value = d[2 + 3 * i] << 16 | d[3 + 3 * i]
                    self.set_param(d[1 + 3 * i], value, value)
        elif cmd == 2 and len(d) > 1:
            for i in range(min(n, len(d) - 2)):
                self.set_param(d[1] + i, d[2 + i], d[2 + i] << 16)
        elif cmd == 0x31 and len(d) > 1:
            for i in range(min(n, (len(d) - 2) // 2)):
                value = d[2 + 2 * i] << 16 | d[3 + 2 * i]
                self.set_param(d[1] + i, value, value)
        elif cmd == 0x16 and len(d) >= 3:
            self.set_param(d[0], d[1], d[1] << 16)
            self.put(slot(d[0]) + 4, d[2] << 16)

    def set_param(self, param, value, word=None):
        self.params[param] = value
        self.put(slot(param), value << 16 if word is None else word)
        part, k = divmod(param - self.part_base, PART_STRIDE)
        if k == 0 and 0 <= part < PARTS:
            self.switches.append((self._now(), part, value))

    # ---- FIFO ----------------------------------------------------------------------
    def fifo_buffer(self, words):
        for w in words:
            channel, code, value = w >> 22 & 0x3F, w >> 16 & 0x3F, w & 0xFFFF
            if channel == FIFO_END:
                break
            self.fifo.append((self._now(), channel, code, value))
            if code == FIFO_TEMPO and channel < FIFO_CHANNELS:
                self.tempo[channel] = value

    # ---- what a check asks ---------------------------------------------------------
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
