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
