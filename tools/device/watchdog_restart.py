"""Restart the red Electribe through the AM1808 watchdog (Timer64P1), run once by BLECH EXEC (docs/messungen/2026-11-16-watchdog-neustart.md).

The stub touches nothing but the registers of Timer 1 (0x01C21000): it reads TGCR, and only when the firmware left the timer in
watchdog mode (TGCR 0xB) it clears the counter, sets the period (100 ms by default at 24 MHz) and writes the two keys into WDTCR.
Then it returns 1, and the chip resets when the counter reaches the period. Any other TGCR: nothing is written, the stub returns
TGCR with bit 31 set. No flash, no firmware call, no other register. The stub goes to the EXEC buffer at 0xC1000000 through BLECH
WRITE and runs through BLECH EXEC (0x6F); the buffer is not put back after a reset, the start fills RAM anew.

    python3 watchdog_restart.py --print                    # the stub's words, nothing sent
    python3 watchdog_restart.py --emu PATCHED.VSB --reboot  # against the emulator, then start it again from its flash
    python3 watchdog_restart.py --dry-run                  # device on USB: INFO and checks only, nothing written
    python3 watchdog_restart.py --arm                      # device on USB: arms the watchdog, the device resets
    python3 watchdog_restart.py --after                    # device on USB after the restart: INFO and READ only
"""
import argparse
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "patch"))
from led_show import mido_ask
from remote_press import Blech, EXEC_FLAG, WRITE_FLAG
# The emulator (machine) is imported only in the function that runs it: the device path works without unicorn.

STUB_AT = 0xC1000000
TIMER1 = 0x01C21000
WATCHDOG_MODE = 0xB                # TGCR: both halves out of reset, timer mode 2 (watchdog); what the firmware sets
CLOCK_HZ = 24_000_000              # the timer clock of Timer 0 and 1 (docs/messungen/2026-10-12-vm-tempo.md)
ARMED = 1
NOT_WATCHDOG = 0x80000000


def source(ms=100):
    """The stub as assembler text: TGCR checked, counter cleared, period set, the two keys."""
    if not 50 <= ms <= 2000:
        raise ValueError("period 50 to 2000 ms: shorter could cut off the EXEC answer")
    return f"""
    ldr r0, ={TIMER1:#x}
    ldr r1, [r0, #0x24]            ; TGCR
    cmp r1, #{WATCHDOG_MODE:#x}
    orrne r0, r1, #{NOT_WATCHDOG:#x}
    bxne lr                        ; not in watchdog mode: nothing written
    mov r2, #0
    str r2, [r0, #0x10]            ; TIM12
    str r2, [r0, #0x14]            ; TIM34
    ldr r1, ={ms * CLOCK_HZ // 1000:#x}
    str r1, [r0, #0x18]            ; PRD12
    str r2, [r0, #0x1C]            ; PRD34
    ldr r1, =0xA5C64000            ; WDKEY 0xA5C6, WDEN
    str r1, [r0, #0x28]            ; WDTCR: pre-active
    ldr r1, =0xDA7E4000            ; WDKEY 0xDA7E, WDEN
    str r1, [r0, #0x28]            ; WDTCR: active, the counter runs
    mov r0, #{ARMED}
    bx lr
.pool
"""


def stub(ms=100):
    from arm import assemble
    return assemble(source(ms), origin=STUB_AT).bytes


def emu_ask(vsb, boot_s=4.0):
    """A booted emulator and a SysEx ask on its DIN line that stops when the chip was reset."""
    sys.path.insert(0, str(HERE.parent / "emu"))
    from machine import Machine, UART1
    m = Machine(Path(vsb).read_bytes()[0x100:], None)
    m.run_until(boot_s)
    box = {"m": m}

    def ask(message):
        m = box["m"]
        tx = m.uart[UART1]["tx"]
        start = len(tx)
        m.receive(UART1, message)
        deadline = m.time_ns + 2_000_000_000
        while m.time_ns < deadline and m.reset is None and not m.asserts:
            m.run_until(m.time_ns / 1e9 + 0.01)
            out = [b for b in tx[start:] if b < 0xF8]
            if 0xF0 in out and 0xF7 in out[out.index(0xF0):]:
                b = out.index(0xF0)
                return out[b:out.index(0xF7, b) + 1]
        raise SystemExit(f"emulator: no answer (reset {m.reset}, asserts {m.asserts})")
    return ask, box


def arm(dev, ms):
    """Write the stub and run it once. Returns what it returned (ARMED, or TGCR | NOT_WATCHDOG)."""
    code = stub(ms)
    original = dev.read(STUB_AT, len(code))
    dev.write(STUB_AT, code)
    value = dev.execute(STUB_AT)
    if value != ARMED:
        dev.write(STUB_AT, original)               # nothing armed: the buffer goes back as it was
    return value


def check(dev):
    if dev.flags & (EXEC_FLAG | WRITE_FLAG) != EXEC_FLAG | WRITE_FLAG:
        raise SystemExit(f"BLECH flags {dev.flags:#x}: no WRITE or no EXEC (the blue Electribe); nothing written")


def run_emu(vsb, ms, reboot, boot_s):
    ask, box = emu_ask(vsb)
    m = box["m"]
    dev = Blech(ask)
    check(dev)
    before = {"reset": m.reset, "watchdog": m.wd_state, "asserts": len(m.asserts)}
    value = arm(dev, ms)
    answered = m.time_ns
    m.run_until(m.time_ns / 1e9 + 1.0)
    out = {"stub_bytes": len(stub(ms)), "before_exec": before, "exec_value": value,
           "reset": m.reset, "reset_after_answer_ms": None if m.reset is None else round(m.reset["ms"] - answered / 1e6, 1),
           "asserts": m.asserts}
    if reboot and m.reset is not None:
        again = m.reboot()
        again.run_until(boot_s)
        box["m"] = again
        info = Blech(ask)                      # INFO answers again: the READ-only check after the restart
        out["reboot"] = {"booted_ms": again.boot_ms, "asserts": again.asserts, "reset": again.reset,
                         "watchdog": again.wd_state, "blech_flags": hex(info.flags)}
    return out


def after(dev, ms):
    """READ only: INFO answered (by Blech), and whether the stub is still in RAM (the reset left RAM as it was)."""
    code = stub(ms)
    kept = dev.read(STUB_AT, len(code)) == code
    return {"blech_flags": hex(dev.flags), "stub_still_in_ram": kept}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--print", action="store_true", help="print the stub, send nothing")
    g.add_argument("--emu", metavar="VSB", help="a BLECH-patched SYSTEM.VSB in the emulator")
    g.add_argument("--dry-run", action="store_true", help="device: INFO and checks, nothing written")
    g.add_argument("--arm", action="store_true", help="device: arm the watchdog, the device resets")
    g.add_argument("--after", action="store_true", help="device after the restart: INFO and READ only")
    p.add_argument("--ms", type=int, default=100, help="watchdog period in ms (50 to 2000, default 100)")
    p.add_argument("--reboot", action="store_true", help="with --emu: start the emulator again after the reset")
    p.add_argument("--boot", type=float, default=6.0, help="with --reboot: seconds of device time for the new start")
    a = p.parse_args()
    if a.print:
        code = stub(a.ms)
        print(json.dumps({"at": hex(STUB_AT), "bytes": len(code), "hex": code.hex(),
                          "words": [f"{w:08x}" for w in struct.unpack(f"<{len(code) // 4}I", code)]}, indent=1))
        return 0
    if a.emu:
        print(json.dumps(run_emu(a.emu, a.ms, a.reboot, a.boot), indent=1))
        return 0
    dev = Blech(mido_ask())
    if a.after:
        print(json.dumps(after(dev, a.ms), indent=1))
        return 0
    check(dev)
    print(f"BLECH flags {dev.flags:#x}: WRITE and EXEC present; stub {len(stub(a.ms))} bytes at {STUB_AT:#x}", file=sys.stderr)
    if a.dry_run:
        print("dry run: nothing written", file=sys.stderr)
        return 0
    value = arm(dev, a.ms)
    if value == ARMED:
        print(f"armed: the chip should reset in about {a.ms} ms; the MIDI port goes away", file=sys.stderr)
        return 0
    print(f"not armed: TGCR {value & ~NOT_WATCHDOG:#x} is not watchdog mode; nothing written, buffer restored", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
