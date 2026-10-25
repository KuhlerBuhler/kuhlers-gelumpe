import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    import unicorn as uc
    from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_LR, UC_ARM_REG_SP, UC_ARM_REG_PC, UC_ARM_REG_CPSR
except ImportError:
    uc = None


class Contract(unittest.TestCase):
    def setUp(self):
        self.assertTrue((HERE / "sample_swap_probe.py").is_file(), "sample swap probe is missing")
        import sample_swap_probe as probe
        self.p = probe

    def test_default_plan_never_imports_device_dependencies(self):
        result = subprocess.run([sys.executable, str(HERE / "sample_swap_probe.py")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("offline", result.stdout)
        self.assertIn("no device contact", result.stdout)

    def test_execute_requires_explicit_slot_firmware_and_state(self):
        for argv in (["--execute"], ["--execute", "--slot", "501", "--vsb", "mine.VSB"],
                     ["--execute", "--slot", "501", "--vsb", "mine.VSB", "--stopped-confirmed", "--playback-confirmed"],
                     ["--kib", "0"], ["--kib", "65"], ["--slot", "500"]):
            with self.subTest(argv=argv), self.assertRaises(ValueError):
                self.p.arguments(argv)

    def test_target_must_be_active_large_enough_and_inside_current_allocation(self):
        meta = bytearray(0x45c)
        struct.pack_into("<II", meta, 0, 0x365ec0, 4096)
        meta[11] = 1
        self.assertEqual(self.p.target(meta, 0x366ec0, 1024), 0x365ec0)
        for change in ("inactive", "small", "cursor", "alignment"):
            data = bytearray(meta)
            cursor = 0x366ec0
            if change == "inactive": data[11] = 0
            if change == "small": struct.pack_into("<I", data, 4, 512)
            if change == "cursor": cursor = 0x365ec0 + 100
            if change == "alignment": struct.pack_into("<I", data, 0, 0x365ec1)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.p.target(data, cursor, 1024)

    def test_timer_period_wrap(self):
        self.assertEqual(self.p.elapsed(990, 12, 999), 22)
        self.assertEqual(self.p.elapsed(1, 101, 999), 100)

    def test_transport_rejects_unknown_protocol_and_crc_failure(self):
        p = self.p
        head = [0xf0, 0x42, 0x30, 0, 1, 0x24]
        def exchange(message):
            func = message[6]
            if func == 0x60:
                body = struct.pack("<6I", 0, 99, 0x43, 0x8000, 0, 0)
                return head + [0x68, *p.enc(body), 0xf7]
            body = struct.pack("<4I", 0, 0xc1000000, 4, 0) + b"abcd"
            return head + [0x69, *p.enc(body), 0xf7]
        link = p.Link(exchange, 0, 0x24)
        with self.assertRaises(ValueError): link.info()
        with self.assertRaises(ValueError): link.read(0xc1000000, 4)

    def test_execute_timeout_is_not_retried(self):
        calls = []
        def ask(message):
            calls.append(message)
            raise TimeoutError("no answer")
        with self.assertRaises(TimeoutError): self.p.Link(ask, 0, 0x24).execute(123)
        self.assertEqual(len(calls), 1)

    def test_stub_fits_exec_window_and_stays_away_from_stack(self):
        blob, symbols = self.p.stub(1024, 0x365ec0, 123)
        self.assertLessEqual(len(blob), 1024)
        self.assertGreaterEqual(self.p.BACKUP, 0xc274f000)
        self.assertLess(self.p.VERIFY + 65536, 0xc4000000)
        self.assertEqual(struct.unpack_from("<I", blob, 4)[0], 123)

    def fixture(self):
        p = self.p
        class Device:
            def __init__(self):
                self.memory, self.writes = {}, []
            def info(self): return 32768
            def read(self, addr, count): return self.memory.get(addr, bytes(count))
            def write(self, data): self.writes.append(data)
            def execute(self, run_id): raise TimeoutError("lost reply")
        device = Device()
        meta, name = bytearray(0x45c), bytearray(32)
        struct.pack_into("<II", meta, 0, 0x365ec0, 4096)
        meta[11] = 1
        struct.pack_into("<H", meta, 22, 500)
        struct.pack_into("<H", name, 30, 550)
        device.memory[p.META + 500 * 0x45c] = bytes(meta)
        device.memory[p.NAMES + 500 * 32] = bytes(name)
        device.memory[p.CURSOR] = struct.pack("<I", 0x366ec0)
        for base, stride, field in ((0xC035738C, 32, 16), (0xC035F06C, 16, 8), (0xC0350644, 8, 2)):
            device.memory[base + 500 * stride + field] = struct.pack("<H", 500)
        return device

    def test_mapping_must_resolve_to_the_exact_target_before_upload(self):
        device = self.fixture()
        self.assertEqual(len(self.p.identity_target(device, 501)), 3)
        device.memory[0xC0350644 + 500 * 8 + 2] = struct.pack("<H", 499)
        with self.assertRaises(ValueError):
            self.p.run(device, bytes(0x200100), 501, 1024, "stopped")
        self.assertEqual(device.writes, [])

    def test_lost_execute_reply_sends_no_retry_or_restore(self):
        device = self.fixture()
        with self.assertRaisesRegex(RuntimeError, "no retry or cleanup"):
            self.p.run(device, bytes(0x200100), 501, 1024, "stopped")
        self.assertEqual(len(device.writes), 1)

    def test_changed_write_wrapper_tail_refuses_every_upload(self):
        device = self.fixture()
        read = device.read
        def changed(addr, count):
            data = bytearray(read(addr, count))
            if addr <= 0xC004EF7C < addr + count:
                data[0xC004EF7C - addr] ^= 1
            return bytes(data)
        device.read = changed
        with self.assertRaisesRegex(ValueError, "live firmware differs"):
            self.p.run(device, bytes(0x200100), 501, 1024, "stopped")
        self.assertEqual(device.writes, [])

    def test_standard_allocator_hook_does_not_block_the_dsp_probe(self):
        device = self.fixture()
        read = device.read
        def allocator_hook(addr, count):
            data = bytearray(read(addr, count))
            if addr <= 0xC004EE0C < addr + count:
                data[0xC004EE0C - addr] ^= 1
            return bytes(data)
        device.read = allocator_hook
        with self.assertRaisesRegex(RuntimeError, "no retry or cleanup"):
            self.p.run(device, bytes(0x200100), 501, 1024, "stopped")
        self.assertEqual(len(device.writes), 1)

    def test_success_reports_only_a_verified_timer_interval(self):
        device = self.fixture()
        def complete(run_id):
            device.memory[self.p.STUB + 4] = struct.pack("<14I", run_id, self.p.MAGIC,
                0xffffff00, 14744, 0xffffffff, 0x80, 1, 100, 101, 3, 0, 0, 0, 123)
        device.execute = complete
        result = self.p.run(device, bytes(0x200100), 501, 1024, "stopped")
        self.assertTrue(result["dsp_bytes_equal"])
        self.assertFalse(result["audio_verified"])
        self.assertEqual(result["ticks"], 15000)
        self.assertEqual(len(device.writes), 2)

    def test_generated_wav_is_deterministic_and_refuses_repository_output(self):
        self.assertTrue(callable(getattr(self.p, "make_wav", None)), "synthetic WAV generator is missing")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "swap.wav"
            self.p.make_wav(output, 1024)
            original = output.read_bytes()
            self.p.make_wav(output, 1024)
            self.assertEqual(output.read_bytes(), original)
            self.assertEqual(original[:4], b"RIFF")
        with self.assertRaises(ValueError):
            self.p.make_wav(HERE / "forbidden.wav", 1024)


@unittest.skipIf(uc is None, "Unicorn not installed; use E2_EMU_PYTHON for ARM execution")
class StubExecution(unittest.TestCase):
    def execute(self, length=1024, corrupt=False, read_error=False, timer=True, wrong_id=False,
                write_error=False, partial_read=False, partial_verify=False, restore_read_error=False,
                timer_mode=0x80):
        import sample_swap_probe as p
        machine = uc.Uc(uc.UC_ARCH_ARM, uc.UC_MODE_ARM)
        for addr, size in ((p.STUB, 0x1000), (p.BACKUP, 0x20000), (0xC3000000, 0x10000),
                           (0xC004E000, 0x2000), (p.TIMER, 0x1000), (0xC3F00000, 0x1000), (0xC06A2000, 0x1000)):
            machine.mem_map(addr, size)
        blob, _ = p.stub(length, 0x365ec0, 123)
        machine.mem_write(p.STUB, blob)
        machine.mem_write(p.TIMER + 0x10, struct.pack("<6I", 0xffffff00, 0, 0xffffffff, 0, timer_mode if timer else 0, 1))
        original = bytes((i * 39 + 5) & 255 for i in range(length))
        dsp = bytearray(original)
        calls = []

        def api(machine, address, size, unused):
            if address not in (p.READ, p.WRITE):
                return
            self.assertFalse(machine.reg_read(UC_ARM_REG_CPSR) & 0x80, "IRQ was disabled")
            a, offset, count = (machine.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2))
            self.assertEqual((offset, count), (0x365ec0, length // 2))
            calls.append(address)
            if address == p.READ:
                data = bytearray(dsp)
                if corrupt and len(calls) == 4:
                    data[0] ^= 1
                if (not read_error or len(calls) > 2) and not (restore_read_error and len(calls) == 6):
                    partial = partial_read and len(calls) <= 2 or partial_verify and len(calls) == 4
                    machine.mem_write(a, bytes(data[:16] if partial else data))
                result = 0x12345678
            else:
                if not write_error or len(calls) > 3:
                    dsp[:] = machine.mem_read(a, count * 2)
                if len(calls) == 3 and not write_error:
                    self.assertNotEqual(bytes(dsp), original, "timed write must change the DSP bytes")
                ticks = struct.unpack("<I", machine.mem_read(p.TIMER + 0x10, 4))[0]
                machine.mem_write(p.TIMER + 0x10, struct.pack("<I", (ticks + 15000) & 0xffffffff))
                result = 0x12345678
            machine.reg_write(UC_ARM_REG_R0, result)
            machine.reg_write(UC_ARM_REG_PC, machine.reg_read(UC_ARM_REG_LR))

        machine.hook_add(uc.UC_HOOK_CODE, api)
        machine.reg_write(UC_ARM_REG_CPSR, 0x13)
        machine.reg_write(UC_ARM_REG_R0, 124 if wrong_id else 123)
        machine.reg_write(UC_ARM_REG_LR, 0xC3F00000)
        machine.reg_write(UC_ARM_REG_SP, 0xC300FFF0)
        machine.emu_start(p.STUB, 0xC3F00000, count=2_000_000)
        self.assertEqual(machine.reg_read(UC_ARM_REG_PC), 0xC3F00000, "stub did not return")
        self.assertEqual(bytes(dsp), original)
        self.assertEqual(bytes(machine.mem_read(p.BACKUP, length)), original if restore_read_error else bytes(length))
        self.assertEqual(bytes(machine.mem_read(p.VERIFY, length)), bytes(length))
        return p, calls, struct.unpack("<14I", machine.mem_read(p.STUB + 4, 56))

    def test_actual_arm_rewrites_only_its_span_restores_and_clears_scratch(self):
        for length in (1024, 65536):
            p, calls, result = self.execute(length)
            self.assertEqual(calls, [p.READ, p.READ, p.WRITE, p.READ, p.WRITE, p.READ])
            self.assertEqual(result[1], p.MAGIC)
            self.assertEqual(result[11:13], (0, 0))
            self.assertEqual(p.elapsed(result[2], result[3], result[4]), 15000)

    def test_read_failure_prevents_every_write(self):
        p, calls, result = self.execute(read_error=True)
        self.assertEqual(calls, [p.READ, p.READ])
        self.assertEqual(result[12], 1)

    def test_mismatch_is_reported_after_original_has_been_restored(self):
        p, calls, result = self.execute(corrupt=True)
        self.assertEqual(calls[-2:], [p.WRITE, p.READ])
        self.assertEqual(result[11], 1)
        self.assertEqual(result[12], 0)

    def test_invalid_timer_or_run_id_never_touch_dsp(self):
        self.assertEqual(self.execute(timer=False)[1], [])
        self.assertEqual(self.execute(wrong_id=True)[1], [])
        self.assertEqual(self.execute(timer_mode=0x40)[1], [])

    def test_partial_backup_read_prevents_writes(self):
        p, calls, result = self.execute(partial_read=True)
        self.assertEqual(calls, [p.READ, p.READ])
        self.assertEqual(result[12], 1)

    def test_failed_write_is_detected_even_with_undefined_status(self):
        p, calls, result = self.execute(write_error=True)
        self.assertGreater(result[11], 0)
        self.assertEqual(result[12], 0)

    def test_partial_readback_is_detected_and_original_is_restored(self):
        p, calls, result = self.execute(partial_verify=True)
        self.assertGreater(result[11], 0)
        self.assertEqual(result[12], 0)

    def test_missing_restore_readback_cannot_claim_restoration(self):
        p, calls, result = self.execute(restore_read_error=True)
        self.assertGreater(result[12], 0)


if __name__ == "__main__":
    unittest.main()
