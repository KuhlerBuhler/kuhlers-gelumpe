# SPDX-License-Identifier: GPL-2.0-only
"""A model of the electribe 2 DSP for checks, not for sound (docs/messungen/2026-11-12-dsp-modell.md).

The emulator does not run the DSP's own program (Blackfin code in the firmware at 0xC00F9E10, tools/dsp/dsp_extract.py). This
model listens to the host port (machine.py, DSP_DATA and DSP_CTRL), keeps an image of the DSP memory the CPU writes, and
answers the reads it models, so a check can ask the DSP's side of a question instead of hooking one firmware routine.

Host port: every transfer starts with 7 control words [0xA9 read | 0xAB write, address low, address high, count of 16-bit
words, 2, 0, 0]; a 32-bit DSP word travels low half first. A write outside mailbox and FIFO lands in the image and in
`uploads`: IMPORT SAMPLE puts its PCM there at byte addresses of the sample memory (16-bit, 24-bit files cut to their upper
16 bits, stereo interleaved; samples(), uploaded()). Reads of the sample memory stay with the emulator's answer.

Mailbox 0xFF900A34 (DSP handler 0xFFA04EC8): every write is one message, word 0 is 0x106, word 1 the command; the CPU always
sends 16 words, the words behind a message are stack left-overs. Parameter N lives at 0xFF800000 + 4N, from 0x4000 on at
0xFF8F0000 + 4N (DSP 0xFFA071CC). What the commands do at the DSP, read from its jump table 0x01F02B84:

    0     (n-1, then n pairs p, v)          slot p = v << 16
    1     (n-1, then n triples p, hi, lo)   slot p = hi << 16 | lo
    2     (n-1, start, n values v)          slots start.. = v << 16
    9     (src, dst)                        0x1A slots from src copied to dst (0xFFA0505A)
    0x16  (n-1, then n triples p, a, b)     slot p = a << 16, slot p + 1 = b << 16
    0x26  (n-1, then n pairs p, q)          slot p = 0, slot q = 0, slot q - 1 = slot p + 0x19 (0xFFA05172); blue: one pair
    0x2B  (p, v)                            slot p = v << 16; the DSP turns v + slot p + 1 into the generator's rate (0xFFA051C0)
    0x2C  (p, q, v)                         slot q = v << 16; the same with slot p + v (0xFFA05210)
    0x30  (flag, p, c hi, c lo, r hi, r lo, k hi, k lo) filter of slot p: cutoff c, resonance r, a third word k (0xFFA05308); blue: without the flag
    0x31  (n-1, start, n pairs hi, lo)      slots start.. = hi << 16 | lo

The other note commands compute generator, filter and part state inside the DSP; they are not applied, command() hands over
the words each last carried (DSP handlers from the jump table 0x01F02B84, Hacktribe):
    0x1F, 0x32  (n-1, then n pairs p, q)    a note's generator: slot p is voice word 3, q its generator state (0x1D4 + ...);
                                            a setter per voice type (0xFFA06670, 0xFFA057B8)
    0x2D, 0x2E  (p, v, ...)                 slot p = voice word 3; 0x2D's v is OSC EDIT * 258, sent about once a millisecond;
                                            a setter per voice type (0xFFA05DD0, 0xFFA06474)
    0x2F        (flag, p, ...)              as 0x30 without its filter part (0xFFA05CB2 only)
    0x33        (n-1, then n pairs p, q)    filter state: p is the part's filter slot (+0xA, its low half the filter kind),
                                            q a state block; set up per kind (0xFFA059F8)
    0x34        (n-1, then n pairs p, q)    clears the part's audio state: p the part's switch, q a state block
    0x35        (n-1, then n pairs p, q)    p the part's +0x8, q a state block (0xFFA054CC, not read further)
    0x36        (hi, lo)                    clears the voices of the 24-bit mask hi << 16 | lo in the DSP's voice mask
    0x37 to 0x39                            not seen with a note; 0x39 comes with a filter type change
The CPU sends 0x2B, 0x2C, 0x2D and 0x30 for every sounding voice about once a millisecond.

Voices: 24 blocks of 0x1A parameters from VOICE (0xFF900EAC), read by the DSP's voice loop (0xFFA0141A). A note copies its
part's template (parameter 0x18 + 0x1A * part) into a free voice with command 9, sets the voice's velocity gain at +0x15 and
then its gate, word 0, to 1; the note's end sets the gate to 0 with command 0x26. Word 1 is the note in 1/256 semitones (0x2B),
word 2 the part's PITCH offset in the same unit (0x2C).

Part values at the DSP, part p's parameter PART_ON[build] + 0x6D * p + offset (the part's block is insert slot p,
0xFF800B08 + 0x1B4 * p): the level at +0x23 (grows with the square of LEVEL, the amp EG rides on it) and the rate the DSP
ramps to it at +0x22 (command 0x16, CPU 0xC0093AF0); the left and right gain of PAN at +0x5F and +0x60 (balance: one side
stays 0x7FFF, CPU 0xC0090FBC); the filter at +0xA (command 0x30: cutoff follows CUTOFF, the filter EG and MOD; resonance
follows RESONANCE), and +0xA to +0x15 are loaded anew when the filter type changes; IFX ON at +0x5C and MFX SEND at +0x63,
0 off and 0x7FFF on. With AMP EG on a note's level starts at 0. OSC EDIT reaches the DSP only as the value of command 0x2D
(OSC EDIT * 258); attack, decay, MOD and GLIDE have no word of their own, the CPU applies them to the level, the filter and
the note commands.

Parameter PART_ON[build] + 0x6D * part is the part's switch at the DSP: 1 on, 0 off; the DSP's audio loop (0xFFA019DE) skips
a switched-off part and clears its output state. The firmware switches a part on with every note it starts (Sampler
0xC0093988) and off in Copy Part's part sound setup (0xC0093A20, blue 0xC0081680).

FIFO 0xFF900018 / 0xFF900098 (DSP handler 0x17FF8): two buffers of 32 words; a word is flags << 28 | channel << 22 |
code << 16 | value, channel 62 ends the buffer. A channel is an effect field: part p's insert effect is field 2p (2p + 1
its neighbour), the master effect field 32 (0x20). Codes below the unit's parameter count are its parameters (value = raw << 8 when
the CPU loads a unit; DSP 0x17DC4), code 0x18 the field's input gain and 0x19 its output gain (0x17CE0: a part's slot
words 40/41 and 44/45, the neighbour 46/47 and 50/51, target and ramped value around the effect call in the part loop
0xFFA019DE; the output is doubled, 0x7F00 and 0x4000 are unity), code 0x20 on channels 0 to 32 the tempo in hundredths of BPM; the DSP keeps it at 0xFF900004 and
recomputes the channel's tempo-synced effect (0x17C78). Field 40 (0x28) stages a unit: its parameters, code 0x38 the unit
number, code 0x39 the target field, which starts the loader. Codes 0x30 and 0x31 on a field mute it and clear its process
pointers ahead of a load. IFX ON is not in the FIFO: it is the part's parameter +0x5C at the mailbox (0x7FFF on).
The touchpad, IFX EDIT and PLAY move field codes as the preset's control map says (shortcut_cases.case_fx_map_dsp).

Reads the model answers: the output peak, 0xFF9030F4 (left) and 0xFF9030F8 (right), fields +0x50/+0x54 of the output block
0xFF9030A4. The DSP keeps max(abs(sample)) of the final stereo sum there (0xFFA01952), 1.31, saturating at 0x7FFFFFFF; the
CPU reads both every 40 ms for the meter LEDs (0xC0014080) and sets them back to 0 with command 0x31. The model has no
sound of its own: `output(left, right)` sets the level the DSP would see, and the peak words hold the larger of that level
and what the CPU wrote. Reads below L1 (the SDRAM, sample memory) return what the CPU uploaded there: EXPORT ALL SAMPLE
reads each sample back with 0xA9 (shortcut_cases.case_sample_dsp). Every other read stays with machine.py (0).

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
L1 = 0xFF800000                 # below: the DSP's SDRAM (sample memory), what the CPU uploaded reads back as written
PEAK = 0xFF9030F4               # output peak, left at +0, right at +4
FULL_SCALE = 0x7FFFFFFF
FIFO_END, FIFO_TEMPO, FIFO_CHANNELS = 62, 0x20, 33
VOICE, VOICE_WORDS, VOICES = 0x43AB, 0x1A, 24     # voice v is the block VOICE + VOICE_WORDS * v, word 0 its gate
TEMPLATE = 0x18                 # part p's voice template is the block TEMPLATE + VOICE_WORDS * p
VELOCITY = 0x15                 # the voice's velocity gain, inside its block
NOTE, PITCH = 1, 2              # the voice's note and its part's PITCH offset, 1/256 semitones, inside its block
LEVEL, RAMP, FILTER, IFX_ON, MFX_SEND = 0x23, 0x22, 0xA, 0x5C, 0x63    # part values, offsets from the part's switch
PAN_LEFT, PAN_RIGHT = 0x5F, 0x60
STAGING, UNIT, TARGET = 0x28, 0x38, 0x39    # FIFO field that stages a unit, its codes for the unit number and the target
MASTER_FX, FX_PARAMS = 0x20, 0x1A           # the master effect's field; codes below FX_PARAMS are effect parameters
FX_IN, FX_OUT = 0x18, 0x19                  # a field's input and output gain


def slot(param):
    """DSP address of parameter `param` (0xFFA071CC)."""
    return (0xFF800000 if param < 0x4000 else 0xFF8F0000) + 4 * param & 0xFFFFFFFF


class DspModel:
    """What the CPU told the DSP over the host port, and the DSP's answer to the reads the model knows."""

    def __init__(self, machine):
        from machine import DSP_CTRL, DSP_DATA, DSP_SYNC
        self.m = machine
        self.synth = machine.profile.build == "synth"
        self.part_base = PART_ON["synth" if self.synth else "sampler"]
        self.params = {}            # parameter -> last value
        self.mem = {}               # DSP address -> 16-bit word, as written
        self.switches = []          # (device time in ms, part, value) for every write of a part switch, in order
        self.messages = 0           # mailbox messages seen
        self.commands = Counter()   # mailbox command -> messages
        self.last = {}              # mailbox command -> the data words of its last message (command())
        self.fifo = []              # (device time in ms, channel, code, value) for every FIFO entry
        self.tempo = {}             # channel -> tempo in hundredths of BPM, as the FIFO last set it
        self.effects = {}           # field -> {"unit": loaded unit, "params": {code: value}}
        self.loads = []             # (device time in ms, field, unit) for every unit the CPU loaded, in order
        self.uploads = []           # (device time in ms, address, 16-bit words) for every write outside mailbox and FIFO
        self._staged = {}
        self.level = (0, 0)         # what the DSP would see at its output, 1.31
        self.voice_part = {}        # voice -> the part whose template it took last
        self.gates = []             # (device time in ms, voice, part, 1 on | 0 off) for every gate write, in order
        self.filters = {}           # part -> (cutoff, resonance), 1.31, as command 0x30 last set them
        self.filter_words = {}      # part -> all three words of the last command 0x30 (filter_curve.py computes them)
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
            self.uploads.append((self._now(), addr, len(words)))
            for i, w in enumerate(words):
                self.mem[addr + 2 * i] = w

    # ---- memory --------------------------------------------------------------------
    def put(self, addr, value):
        """One 32-bit DSP word."""
        self.mem[addr], self.mem[addr + 2] = value & 0xFFFF, value >> 16 & 0xFFFF

    def word(self, addr):
        return self.mem.get(addr, 0) | self.mem.get(addr + 2, 0) << 16

    def samples(self, addr, count):
        """`count` signed 16-bit words of the DSP memory from byte `addr` (sample memory: PCM as the importer wrote it)."""
        return [w - 0x10000 if w & 0x8000 else w for w in (self.mem.get(addr + 2 * i, 0) for i in range(count))]

    def uploaded(self, since=0):
        """(start, end) byte span of the uploads after index `since` into `uploads`, or None."""
        spans = [(a, a + 2 * n) for _, a, n in self.uploads[since:]]
        return (min(a for a, _ in spans), max(b for _, b in spans)) if spans else None

    def answers(self, addr):
        return PEAK <= addr < PEAK + 8 or (addr < L1 and addr in self.mem)

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
        self.last[cmd] = list(d)
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
        elif cmd == 9 and len(d) >= 2:
            src, dst = d[0], d[1]
            for i in range(VOICE_WORDS):
                self.put(slot(dst + i), self.word(slot(src + i)))
                if src + i in self.params:
                    self.params[dst + i] = self.params[src + i]
            part, k = divmod(src - TEMPLATE, VOICE_WORDS)
            voice, j = divmod(dst - VOICE, VOICE_WORDS)
            if k == j == 0 and 0 <= part < PARTS and 0 <= voice < VOICES:
                self.voice_part[voice] = part
        elif cmd == 0x16:
            for i in range(n):
                if 3 + 3 * i < len(d):
                    p, a, b = d[1 + 3 * i:4 + 3 * i]
                    self.set_param(p, a, a << 16)
                    self.set_param(p + 1, b, b << 16)
        elif cmd == 0x2B and len(d) >= 2:
            self.set_param(d[0], d[1], d[1] << 16)
        elif cmd == 0x2C and len(d) >= 3:
            self.set_param(d[1], d[2], d[2] << 16)
        elif cmd == 0x30:
            p, data = (d[0], d[1:]) if self.synth else (d[1] if len(d) > 1 else None, d[2:])
            part, k = divmod((p or 0) - self.part_base, PART_STRIDE)
            if p is not None and k == FILTER and 0 <= part < PARTS and len(data) >= 4:
                self.filters[part] = (data[0] << 16 | data[1], data[2] << 16 | data[3])
                self.filter_words[part] = tuple(data[2 * i] << 16 | data[2 * i + 1] for i in range(min(3, len(data) // 2)))
        elif cmd == 0x26:
            pairs = [(d[1 + 2 * i], d[2 + 2 * i]) for i in range(n) if 2 + 2 * i < len(d)]
            if self.synth:
                pairs = [(d[0], d[1])]      # blue sends one pair without a count (CPU side measured, its DSP code not read)
            for p, q in pairs:
                self.put(slot(q - 1), self.word(slot(p + 0x19)))
                self.set_param(p, 0, 0)
                self.set_param(q, 0, 0)

    def set_param(self, param, value, word=None):
        self.params[param] = value
        self.put(slot(param), value << 16 if word is None else word)
        part, k = divmod(param - self.part_base, PART_STRIDE)
        if k == 0 and 0 <= part < PARTS:
            self.switches.append((self._now(), part, value))
        voice, k = divmod(param - VOICE, VOICE_WORDS)
        if k == 0 and 0 <= voice < VOICES:
            self.gates.append((self._now(), voice, self.voice_part.get(voice), 1 if value else 0))

    # ---- FIFO ----------------------------------------------------------------------
    def fifo_buffer(self, words):
        for w in words:
            channel, code, value = w >> 22 & 0x3F, w >> 16 & 0x3F, w & 0xFFFF
            if channel == FIFO_END:
                break
            self.fifo.append((self._now(), channel, code, value))
            if code == FIFO_TEMPO and channel < FIFO_CHANNELS:
                self.tempo[channel] = value
            elif channel == STAGING:
                if code < FX_PARAMS or code == UNIT:
                    self._staged[code] = value
                elif code == TARGET:
                    staged, self._staged = self._staged, {}
                    unit = staged.pop(UNIT, None)
                    self.effects[value] = {"unit": unit, "params": staged}
                    self.loads.append((self._now(), value, unit))
            elif code < FX_PARAMS and channel < FIFO_CHANNELS:
                self.effects.setdefault(channel, {"unit": None, "params": {}})["params"][code] = value

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

    def voices(self):
        """The voices whose gate is open now: voice -> (part, velocity gain)."""
        return {v: (self.voice_part.get(v), self.params.get(VOICE + VOICE_WORDS * v + VELOCITY))
                for v in range(VOICES) if self.params.get(VOICE + VOICE_WORDS * v)}

    def command(self, cmd):
        """The data words (after the command) of the last message with this command, or None."""
        words = self.last.get(cmd)
        return None if words is None else list(words)

    def voice(self, v):
        """What voice `v` holds now: part, gate, velocity gain, note and PITCH offset in semitones (None until sent)."""
        block = VOICE + VOICE_WORDS * v
        semis = lambda x: None if x is None else (x - 0x10000 if x & 0x8000 else x) / 256
        return {"part": self.voice_part.get(v), "gate": bool(self.params.get(block)),
                "velocity": self.params.get(block + VELOCITY), "note": semis(self.params.get(block + NOTE)),
                "pitch": semis(self.params.get(block + PITCH))}

    def part_value(self, part, offset):
        """The last value the part's parameter at `offset` (LEVEL, PAN_LEFT, ...) got; None when the firmware never sent it."""
        return self.params.get(self.part_base + PART_STRIDE * part + offset)

    def filter(self, part):
        """(cutoff, resonance) of the part's filter as command 0x30 last set them, or None."""
        return self.filters.get(part)

    def coefficients(self, part):
        """The three words command 0x30 last sent for the part's filter, or None."""
        return self.filter_words.get(part)

    def effect(self, field):
        """The unit the CPU loaded into an effect field and its parameters as last sent ({code: value}), or None.
        Part p's insert effect is field 2p, the master effect MASTER_FX."""
        fx = self.effects.get(field)
        return None if fx is None else {"unit": fx["unit"], "params": dict(fx["params"])}

    def ifx(self, part):
        return self.effect(2 * part)

    def mfx_send(self, part):
        """True or False: the part's MFX SEND at the DSP; None when the firmware never sent it."""
        value = self.part_value(part, MFX_SEND)
        return None if value is None else value != 0

    def ifx_on(self, part):
        """True or False: the part's IFX ON at the DSP; None when the firmware never sent it."""
        value = self.part_value(part, IFX_ON)
        return None if value is None else value != 0

    def notes(self, part=None, since=0):
        """Device times (ms) at which a voice opened its gate after `since` (an index into `gates`), for one part or all."""
        return [t for t, _, p, on in self.gates[since:] if on and (part is None or p == part)]
