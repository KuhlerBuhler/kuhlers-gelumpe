"""A small ARM (32-bit, v5) assembler for firmware patches.

The Electribe's firmware is ARM code, and a patch that adds a menu page is
ARM code too. No assembler ships with this repository and none can be
assumed on the user's machine, so this one covers exactly the instructions
the patches here use, and says so when it meets anything else. It reads GNU
style UAL text (what Capstone prints, too), so every line can be checked
against a disassembler:

    mov r0, #1          ldr r1, =0xC0029A40     ldr r2, [r3, #8]
    bl 0xC0029A74       push {r4, lr}           eorcs r2, r2, r12

Beyond the instruction set: labels (`name:`), `.equ NAME, value`, `.org addr`
(a new section, as a patch writes to several places), `.word`, `.byte`,
`.ascii`, `.asciz`, `.space`, `.align n`, `.pool` (place the literal pool
here; `ldr rd, =value` otherwise ends up at the end of its section) and `;`
comments.
Expressions are Python arithmetic over numbers and symbols.

    code = assemble(text, origin=0xC01A2100)   # -> Assembled(bytes, symbols)
"""

import re
import struct
from dataclasses import dataclass

COND = {"eq": 0, "ne": 1, "cs": 2, "hs": 2, "cc": 3, "lo": 3, "mi": 4, "pl": 5, "vs": 6, "vc": 7,
        "hi": 8, "ls": 9, "ge": 10, "lt": 11, "gt": 12, "le": 13, "al": 14, "": 14}
REG = {**{f"r{i}": i for i in range(16)}, "sb": 9, "sl": 10, "fp": 11, "ip": 12, "sp": 13, "lr": 14, "pc": 15}
DATA_OPS = {"and": 0, "eor": 1, "sub": 2, "rsb": 3, "add": 4, "adc": 5, "sbc": 6, "rsc": 7,
            "tst": 8, "teq": 9, "cmp": 10, "cmn": 11, "orr": 12, "mov": 13, "bic": 14, "mvn": 15}
NO_RESULT = {"tst", "teq", "cmp", "cmn"}
NO_RN = {"mov", "mvn"}
SHIFT = {"lsl": 0, "lsr": 1, "asr": 2, "ror": 3}
BLOCK_MODES = {"ia": (0, 1), "ib": (1, 1), "da": (0, 0), "db": (1, 0)}
STACK_ALIAS_STM = {"fd": "db", "ed": "ib", "fa": "da", "ea": "ia"}
STACK_ALIAS_LDM = {"fd": "ia", "ed": "da", "fa": "ib", "ea": "db"}


class AsmError(Exception):
    pass


@dataclass
class Assembled:
    sections: list          # [(address, bytes)], one per .org
    symbols: dict
    origin: int

    @property
    def bytes(self):
        """The code of a source without .org."""
        if len(self.sections) != 1:
            raise AsmError("this source has several sections")
        return self.sections[0][1]


def _rot32(v, n):
    n %= 32
    return ((v << n) | (v >> (32 - n))) & 0xFFFFFFFF if n else v


def encode_immediate(value):
    """(rotate, imm8) so that imm8 rotated right by 2*rotate is value, or None."""
    value &= 0xFFFFFFFF
    for rot in range(16):
        imm = _rot32(value, 2 * rot)
        if imm < 256:
            return rot, imm
    return None


def _split(text):
    """Operands split at top-level commas (not inside [] or {})."""
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


class _Assembler:
    def __init__(self, text, origin):
        self.origin = origin
        self.symbols = {}
        self.items = []             # (kind, payload, source line number)
        self.pool_refs = []         # index into items of ldr =value, pending a pool
        self.parse(text)

    # ---- pass 1: lay out ---------------------------------------------------
    def parse(self, text):
        pc = self.origin
        for n, raw in enumerate(text.splitlines(), 1):
            line = re.split(r";|//|@", raw, maxsplit=1)[0].strip()
            while True:
                m = re.match(r"^([A-Za-z_]\w*):\s*", line)
                if not m:
                    break
                if m.group(1) in self.symbols:
                    raise AsmError(f"line {n}: {m.group(1)} defined twice")
                self.symbols[m.group(1)] = pc
                line = line[m.end():]
            if not line:
                continue
            head, _, rest = line.partition(" ")
            head = head.lower()
            rest = rest.strip()
            try:
                if head == ".equ":
                    name, _, expr = rest.partition(",")
                    self.symbols[name.strip()] = self.value(expr, defer=False)
                    continue
                if head == ".org":                  # a new section; the pool of the old one goes first
                    pc += self.flush_pool(at=pc)
                    pc = self.value(rest, defer=False)
                    self.items.append(("org", pc, n, pc))
                    continue
                size = self.layout(head, rest, pc, n)
            except AsmError as e:
                raise AsmError(f"line {n}: {e}: {raw.strip()}") from None
            pc += size
        self.end = pc
        self.flush_pool()           # literals left over go at the very end

    def layout(self, head, rest, pc, n):
        if head == ".pool":
            return self.flush_pool(at=pc)
        if head == ".align":
            to = int(rest, 0)
            pad = (-pc) % to
            self.items.append(("space", pad, n, pc))
            return pad
        if head == ".space":
            k = int(rest, 0)
            self.items.append(("space", k, n, pc))
            return k
        if head in (".word", ".byte"):
            width = 4 if head == ".word" else 1
            values = _split(rest)
            self.items.append((head, values, n, pc))
            return width * len(values)
        if head in (".ascii", ".asciz"):
            s = re.match(r'^"(.*)"$', rest)
            if not s:
                raise AsmError("a string in double quotes")
            data = s.group(1).encode("latin-1") + (b"\0" if head == ".asciz" else b"")
            self.items.append(("bytes", data, n, pc))
            return len(data)
        self.items.append(("ins", (head, rest), n, pc))
        if head.startswith("ldr") and re.match(r"^\w+\s*,\s*=", rest):
            self.pool_refs.append(len(self.items) - 1)
        return 4

    def flush_pool(self, at=None):
        """Literal words for the pending ldr =value lines, placed at `at` (or at the end)."""
        if not self.pool_refs:
            return 0
        pc = self.end if at is None else at
        pc_start = pc
        if pc % 4:
            self.items.append(("space", (-pc) % 4, 0, pc))
            pc += (-pc) % 4
        pool = {}
        for idx in self.pool_refs:
            kind, (head, rest), n, ipc = self.items[idx]
            reg, _, expr = rest.partition(",")
            expr = expr.strip()[1:].strip()
            if expr not in pool:
                pool[expr] = pc
                self.items.append((".word", [expr], n, pc))
                pc += 4
            self.items[idx] = ("ins", (head, f"{reg.strip()}, [pc, #{pool[expr] - (ipc + 8)}]"), n, ipc)
        self.pool_refs = []
        return pc - pc_start

    # ---- expressions -------------------------------------------------------
    def value(self, expr, defer=True):
        expr = expr.strip()
        names = {k: v for k, v in self.symbols.items()}
        try:
            return int(eval(expr, {"__builtins__": {}}, names)) & 0xFFFFFFFF  # noqa: S307
        except NameError as e:
            raise AsmError(f"unknown symbol in {expr!r}") from e
        except SyntaxError as e:
            raise AsmError(f"cannot read {expr!r}") from e

    def imm(self, text):
        t = text.strip()
        if not t.startswith("#"):
            raise AsmError(f"expected #immediate, got {t!r}")
        return self.value(t[1:])

    # ---- pass 2: encode ----------------------------------------------------
    def encode(self):
        sections = []
        start, out = self.origin, bytearray()
        for kind, payload, n, pc in self.items:
            if kind == "org":
                if out:
                    sections.append((start, bytes(out)))
                start, out = payload, bytearray()
                continue
            assert pc == start + len(out), f"layout drift at line {n}"
            try:
                if kind == "space":
                    out += bytes(payload)
                elif kind == "bytes":
                    out += payload
                elif kind == ".word":
                    for v in payload:
                        out += struct.pack("<I", self.value(v))
                elif kind == ".byte":
                    for v in payload:
                        out += bytes([self.value(v) & 0xFF])
                else:
                    out += struct.pack("<I", self.instruction(payload[0], payload[1], pc))
            except AsmError as e:
                raise AsmError(f"line {n}: {e}") from None
        if out:
            sections.append((start, bytes(out)))
        return sections

    def reg(self, text):
        t = text.strip().lower()
        if t not in REG:
            raise AsmError(f"not a register: {text!r}")
        return REG[t]

    def split_mnemonic(self, head, bases):
        """(base, cond bits, s flag, suffix) for UAL names like addseq, ldrbne, movs."""
        for base in sorted(bases, key=len, reverse=True):
            if not head.startswith(base):
                continue
            tail = head[len(base):]
            for s in ("s", ""):
                if tail.startswith(s):
                    cond = tail[len(s):]
                    if cond in COND:
                        return base, COND[cond], 1 if s else 0
        return None

    def instruction(self, head, rest, pc):
        if head == "nop":
            return 0xE1A00000
        ops = _split(rest)
        # branches
        m = re.match(r"^(bl|b)(%s)$" % "|".join(c for c in COND if c), head)
        if m or head in ("b", "bl"):
            link = (m.group(1) if m else head) == "bl"
            cond = COND[m.group(2)] if m and m.group(2) else 14
            target = self.value(ops[0].lstrip("#"))
            off = target - (pc + 8)
            if off % 4 or not -(1 << 25) <= off < (1 << 25):
                raise AsmError(f"branch target {target:#x} out of reach from {pc:#x}")
            return cond << 28 | 0b101 << 25 | link << 24 | (off >> 2) & 0xFFFFFF
        m = re.match(r"^(bx|blx)(%s)$" % "|".join(c for c in COND if c), head)
        if m or head in ("bx", "blx"):
            name = m.group(1) if m else head
            cond = COND[m.group(2)] if m and m.group(2) else 14
            return cond << 28 | (0x012FFF10 if name == "bx" else 0x012FFF30) | self.reg(ops[0])
        # push / pop
        sm = self.split_mnemonic(head, ["push", "pop"])
        if sm:
            base, cond, _ = sm
            regs = self.reglist(ops[0])
            return cond << 28 | (0x092D0000 if base == "push" else 0x08BD0000) | regs
        # ARMv5 multiply destinations must differ from the first source.
        sm = self.split_mnemonic(head, ["mla"])
        if sm:
            if len(ops) != 4:
                raise AsmError("mla: four registers required")
            rd, rm, rs, rn = (self.reg(op) for op in ops)
            if 15 in (rd, rm, rs, rn) or rd == rm:
                raise AsmError("mla: no PC; destination must differ from the first source")
            return sm[1] << 28 | 0x00200090 | sm[2] << 20 | rd << 16 | rn << 12 | rs << 8 | rm
        sm = self.split_mnemonic(head, ["mul"])
        if sm:
            rd, rm, rs = (self.reg(op) for op in ops[:3])
            if rd == rm:
                raise AsmError("mul: the destination must differ from the first source")
            return sm[1] << 28 | sm[2] << 20 | rd << 16 | rs << 8 | 0x90 | rm
        # block transfers
        for base in ("ldm", "stm"):
            if head.startswith(base):
                tail = head[3:]
                mode = tail[:2]
                cond_text = tail[2:]
                table = STACK_ALIAS_LDM if base == "ldm" else STACK_ALIAS_STM
                mode = table.get(mode, mode)
                if mode in BLOCK_MODES and cond_text in COND:
                    p, u = BLOCK_MODES[mode]
                    wb = ops[0].endswith("!")
                    rn = self.reg(ops[0].rstrip("!"))
                    return (COND[cond_text] << 28 | 0b100 << 25 | p << 24 | u << 23 | wb << 21
                            | (base == "ldm") << 20 | rn << 16 | self.reglist(ops[1]))
        # load / store
        sm = self.split_mnemonic(head, ["ldrb", "strb", "ldr", "str"])
        if sm and sm[2] == 0:
            return self.memory(sm[0], sm[1], ops, pc)
        # shifts are mov with a shifted operand: lsrs r2, r2, #1
        sm = self.split_mnemonic(head, list(SHIFT))
        if sm:
            rd, rm = ops[0], ops[1] if len(ops) == 3 else ops[0]
            return self.data("mov", sm[1], sm[2], [rd, rm, f"{sm[0]} {ops[-1]}"])
        # data processing
        sm = self.split_mnemonic(head, list(DATA_OPS))
        if sm:
            return self.data(sm[0], sm[1], sm[2], ops)
        raise AsmError(f"instruction not supported: {head}")

    def reglist(self, text):
        t = text.strip()
        if not (t.startswith("{") and t.endswith("}")):
            raise AsmError("a register list in braces")
        mask = 0
        for part in t[1:-1].split(","):
            part = part.strip()
            if "-" in part:
                a, b = (self.reg(x) for x in part.split("-"))
                for r in range(a, b + 1):
                    mask |= 1 << r
            else:
                mask |= 1 << self.reg(part)
        return mask

    def operand2(self, ops):
        """(I bit, 12-bit operand 2) from the operand list after the registers."""
        first = ops[0]
        if first.startswith("#"):
            enc = encode_immediate(self.imm(first))
            return 1, enc
        rm = self.reg(first)
        if len(ops) == 1:
            return 0, rm
        shift = ops[1].lower().split()
        if shift[0] == "rrx":
            return 0, 3 << 5 | rm
        typ = SHIFT[shift[0]]
        arg = ops[1].split(None, 1)[1].strip()
        if arg.startswith("#"):
            amount = self.imm(arg)
            if shift[0] in ("lsr", "asr") and amount == 32:
                amount = 0
            if not 0 <= amount < 32:
                raise AsmError("shift amount 0 to 31")
            return 0, amount << 7 | typ << 5 | rm
        return 0, self.reg(arg) << 8 | typ << 5 | 1 << 4 | rm

    def data(self, base, cond, s, ops):
        op = DATA_OPS[base]
        if base in NO_RESULT:
            rd, rn, rest = 0, self.reg(ops[0]), ops[1:]
            s = 1
        elif base in NO_RN:
            rd, rn, rest = self.reg(ops[0]), 0, ops[1:]
        elif len(ops) == 2:                   # `add r0, #1` means add r0, r0, #1
            rd = self.reg(ops[0])
            rn, rest = rd, ops[1:]
        else:
            rd, rn, rest = self.reg(ops[0]), self.reg(ops[1]), ops[2:]
        if rest[0].startswith("#"):
            value = self.imm(rest[0])
            enc = encode_immediate(value)
            if enc is None and base == "mov":
                enc, op = encode_immediate(~value), DATA_OPS["mvn"]
            elif enc is None and base == "mvn":
                enc, op = encode_immediate(~value), DATA_OPS["mov"]
            if enc is None:
                raise AsmError(f"{value:#x} is not an ARM immediate")
            return cond << 28 | 1 << 25 | op << 21 | s << 20 | rn << 16 | rd << 12 | enc[0] << 8 | enc[1]
        i, o2 = self.operand2(rest)
        return cond << 28 | i << 25 | op << 21 | s << 20 | rn << 16 | rd << 12 | o2

    def memory(self, base, cond, ops, pc):
        load = base.startswith("ldr")
        byte = base.endswith("b")
        rd = self.reg(ops[0])
        rest = ", ".join(ops[1:])
        m = re.match(r"^\[(.*)\](!?)\s*(?:,\s*(.*))?$", rest)
        if not m:
            raise AsmError("memory operand in brackets")
        inner, bang, post = _split(m.group(1)), m.group(2) == "!", m.group(3)
        rn = self.reg(inner[0])
        pre = post is None
        spec = inner[1:] if pre else _split(post)
        up, reg_off, shift_bits = 1, None, 0
        offset = 0
        if spec:
            first = spec[0].strip()
            if first.startswith("#"):
                offset = self.imm(first)
                if offset >= 1 << 31:
                    offset -= 1 << 32
                if offset < 0:
                    up, offset = 0, -offset
                if offset > 0xFFF:
                    raise AsmError(f"offset {offset} does not fit 12 bits")
            else:
                if first.startswith("-"):
                    up, first = 0, first[1:]
                elif first.startswith("+"):
                    first = first[1:]
                reg_off = self.reg(first)
                if len(spec) > 1:
                    kind, _, arg = spec[1].lower().partition(" ")
                    shift_bits = self.imm(arg) << 7 | SHIFT[kind] << 5
        p = 1 if pre else 0
        w = 1 if (pre and bang) else 0
        if not pre:
            w = 0
        if reg_off is None:
            return (cond << 28 | 0b01 << 26 | p << 24 | up << 23 | byte << 22 | w << 21 | load << 20
                    | rn << 16 | rd << 12 | offset)
        return (cond << 28 | 0b011 << 25 | p << 24 | up << 23 | byte << 22 | w << 21 | load << 20
                | rn << 16 | rd << 12 | shift_bits | reg_off)


def assemble(text, origin=0):
    """Assemble `text` for load address `origin`."""
    a = _Assembler(text, origin)
    return Assembled(a.encode(), dict(a.symbols), origin)
