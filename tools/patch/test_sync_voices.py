"""The sync voice guard preserves its callers and scopes protection to one playing load."""
import struct
import unittest

import arm
import pattern_switch as spec
try:
    import unicorn
    from unicorn import arm_const as regs
except ImportError:
    unicorn = None


@unittest.skipUnless(unicorn, "Unicorn is required for native guard tests")
class SyncVoices(unittest.TestCase):
    def guard(self, build, *, playing=1, old=7, new=7, held=0, reload=False, banked=True):
        spec.use_build(build)
        at, code, symbols = spec.build_code()
        tail = spec.build_voice_code()
        uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        for base, size in ((0xC0000000, 0x200000), (0xC0200000, 0xE00000)):
            uc.mem_map(base, size)
        uc.mem_write(at, code)
        for address, data in tail.sections:
            uc.mem_write(address, data)
        panel, transport, live, stop = 0xC0500000, 0xC0501000, 0xC0502000, 0xC070F000
        source = symbols["BANK"] + 0x4000 if banked else 0xC0508000
        word = lambda address, value: uc.mem_write(address, struct.pack("<I", value))
        word(symbols["PANEL"], panel)
        word(panel + 0x18, held)
        word(symbols["PATPTR"], live - 4)
        word(transport + 0x308, playing)
        word(spec.STATE + spec.S_LOADED, source if reload else symbols["BANK"])
        word(spec.STATE + spec.S_VOICES, 1)
        uc.mem_write(live + spec.GROUP_AT, struct.pack("<H", old))
        uc.mem_write(source + spec.GROUP_AT, struct.pack("<H", new))
        uc.mem_write(symbols["TRANSPORT"], arm.assemble(f"ldr r0, ={transport}\nbx lr").bytes)
        events = []
        uc.mem_write(spec.VOICE_CONT, arm.assemble("bx lr").bytes)
        for address, name in ((spec.VOICE_BEGIN_ORIG, "cleanup"), (spec.VOICE_SILENCE_ORIG, "silence"),
                              (spec.NOTE_CLEAR_BODY, "ownership"), (spec.NOTE_FLUSH_ORIG, "note-off"),
                              (spec.NOTE_ASSIGN_ORIG, "capacity"),
                              (spec.VOICE_RESET_ORIG, "reset")):
            uc.mem_write(address, arm.assemble("bx lr").bytes)
            uc.hook_add(unicorn.UC_HOOK_CODE, lambda _u, _a, _s, n: events.append(n), name,
                        begin=address, end=address)
        post = arm.assemble(f"push {{r4, lr}}\nbl {tail.symbols['voice_reset']}\npop {{r4, pc}}",
                            origin=spec.VOICE_END_ORIG)
        uc.mem_write(spec.VOICE_END_ORIG, post.bytes)
        uc.hook_add(unicorn.UC_HOOK_CODE, lambda *_: events.append("prepare"),
                    begin=spec.VOICE_END_ORIG, end=spec.VOICE_END_ORIG)

        def call(target):
            for k in range(12):
                uc.reg_write(regs.UC_ARM_REG_R0 + k, source if k == 7 else panel if k == 0 else 0x100 + k)
            uc.reg_write(regs.UC_ARM_REG_SP, 0xC0708000)
            uc.reg_write(regs.UC_ARM_REG_LR, stop)
            uc.emu_start(target, stop, count=1000)
            self.assertEqual(uc.reg_read(regs.UC_ARM_REG_PC), stop)
            for k in range(4, 12):
                self.assertEqual(uc.reg_read(regs.UC_ARM_REG_R0 + k), source if k == 7 else 0x100 + k)
            self.assertEqual(uc.reg_read(regs.UC_ARM_REG_SP), 0xC0708000)

        call(symbols["voice_begin"])
        protected = struct.unpack("<I", uc.mem_read(spec.STATE + spec.S_VOICES, 4))[0]
        call(tail.symbols["voice_silence"])
        call(tail.symbols["voice_clear"])
        call(tail.symbols["voice_flush"])
        call(tail.symbols["voice_assign"])
        call(tail.symbols["voice_end"])
        self.assertEqual(struct.unpack("<I", uc.mem_read(spec.STATE + spec.S_VOICES, 4))[0], 0)
        call(tail.symbols["voice_reset"])
        self.assertEqual(events.pop(), "reset", "ordinary resets still work after the load")
        return protected, events

    def test_group_load_prepares_the_next_sound_without_silencing(self):
        for build in ("hacktribe", "stock", "synth"):
            with self.subTest(build=build):
                self.assertEqual(self.guard(build), (1, ["prepare"]))

    def test_every_other_load_clears_stale_protection_and_keeps_both_resets(self):
        for build in ("hacktribe", "stock", "synth"):
            for options in ({"playing": 0}, {"old": 0}, {"new": 0}, {"new": 8},
                            {"held": spec.KILL_SWITCH}, {"reload": True}, {"banked": False}):
                with self.subTest(build=build, options=options):
                    self.assertEqual(self.guard(build, **options), (0, ["cleanup", "silence", "ownership", "note-off", "capacity", "prepare", "reset"]))


if __name__ == "__main__":
    unittest.main()
