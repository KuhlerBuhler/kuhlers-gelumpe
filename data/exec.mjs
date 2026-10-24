/**
 * Where code may be put and run: BLECH's EXEC (0x6F) runs only here and clears the
 * instruction cache itself; Hacktribe's execute (0x57) is the way on a firmware without BLECH.
 *
 * Not a field the editor edits, so it is not in the device map: a scratch
 * buffer and one firmware routine. Both measured on the own device and in the
 * emulator, see tools/device/led_show.py and backlight.py.
 *
 * The buffer is Hacktribe's own upload area. Import and export use the same
 * shared memory (docs/speicherbereiche.md), so the region is only the first
 * KiB, which holds every stub so far (60 bytes for the LEDs, 7 x 64 for the
 * light colours), and a stub is always restored after a run.
 */
export default {
  evidence: "measure:2026-10-08/led-execute",
  /** Start of the stub buffer, and how many bytes of it may be written. */
  stubAt: 0xc1000000,
  stubSize: 0x400,
  /** The firmware's own instruction cache invalidation; run once before a fresh stub (measure:2026-10-08/led-execute). */
  icache: { addr: 0xc00016a4, length: 0x34 },
};
