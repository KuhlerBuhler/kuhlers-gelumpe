"""Boots your own SYSTEM.VSB in the emulator step by step and says how far it gets (Windows diagnosis)."""
import faulthandler
import sys
import threading
import time

faulthandler.enable()
import os  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

def say(*a):
    print(*a, flush=True)

LOG = None
SEEN = [0]


def trace(*a):
    """One line into bootprobe.log, flushed to disk at once, so the last line survives a hard crash."""
    line = " ".join(str(x) for x in a)
    LOG.write(line + "\n")
    LOG.flush()
    os.fsync(LOG.fileno())


def instrument(machine):
    M = machine.Machine
    rd, wr, run_slice, service = M._rd, M._wr, M.run_slice, M.service

    def _rd(self, uc, off, size, base):
        SEEN[0] += 1
        if SEEN[0] < 5000:
            trace("rd", hex(base + off), size)
        v = rd(self, uc, off, size, base)
        if SEEN[0] < 5000:
            trace("   =", hex(v))
        return v

    def _wr(self, uc, off, size, value, base):
        SEEN[0] += 1
        if SEEN[0] < 5000:
            trace("wr", hex(base + off), size, hex(value))
        return wr(self, uc, off, size, value, base)

    def _run_slice(self, limit=float("inf")):
        trace("slice pc", hex(self.reg(self.A.UC_ARM_REG_PC)), "insns", self.insns)
        r = run_slice(self, limit)
        trace("slice done pc", hex(self.reg(self.A.UC_ARM_REG_PC)))
        return r

    def _service(self):
        trace("service pc", hex(self.reg(self.A.UC_ARM_REG_PC)))
        return service(self)

    M._rd, M._wr, M.run_slice, M.service = _rd, _wr, _run_slice, _service


def boot(path, where):
    import machine
    from unicorn.unicorn_py3 import unicorn as u
    say(where, "uc_mmio_map argtypes", getattr(u.uclib.uc_mmio_map, "argtypes", None))
    payload = open(path, "rb").read()[0x100:]
    say(where, "payload", len(payload))
    flash = machine.blank_flash()
    say(where, "blank flash ok")
    m = machine.Machine(payload, flash)
    say(where, "Machine built, build", m.profile.build)
    for t in (0.001, 0.01, 0.1, 0.5, 1.0, 2.0, 4.0):
        m.run_until(t)
        say(where, f"ran to {t} s, insns {m.insns}, asserts {len(m.asserts)}")
    say(where, "screen", m.screen() if hasattr(m, "screen") else "?")

LOG = open(os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "bootprobe.log"), "w")
import machine as _m  # noqa: E402
instrument(_m)
path = sys.argv[1] if len(sys.argv) > 1 else input("Pfad zur SYSTEM.VSB (oder Datei hier reinziehen): ").strip().strip('"')
try:
    boot(path, "main")
    t = threading.Thread(target=boot, args=(path, "thread"))
    t.start()
    t.join()
    say("all done")
except Exception as e:
    import traceback
    traceback.print_exc()
    say("python error", e)
input("Enter zum Beenden ")
