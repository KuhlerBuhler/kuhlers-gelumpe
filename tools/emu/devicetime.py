# SPDX-License-Identifier: GPL-2.0-only
"""Estimate how long code that ran in the emulator takes on the device.

The emulator charges every instruction the same (`machine.NS_PER_INSN`) and knows nothing about the data
cache, SDRAM or the multiplier. Measured on the own device against the emulator
(docs/messungen/2026-10-16-emulator-timing.md, `tools/device/timing_probe.py`):

- Plain ALU code with a taken branch every fourth instruction runs at 5.04 ns per instruction: the emulator's
  5 ns is right for it, and stays the base rate.
- A dependent multiply costs 6.7 ns more than the 5 ns the emulator charges.
- Reading memory costs more per byte the less the data cache helps: 0.5 ns/B when it hits, 6.8 ns/B when it
  misses on every line (a streaming read over more than the cache holds), 12.4 ns/B uncached.

`estimate_device_ns` adds those surcharges to the emulator's time. It is an estimate from four small loops,
good to a few tens of percent for code that is mostly ALU and streaming reads, and says nothing about writes,
the DSP port or interrupt load. Nothing in the emulator uses it; it is for reading measurements.
"""

ALU_NS_PER_INSN = 5.0           # = machine.NS_PER_INSN (test_devicetime.py); the device measured 5.04
MUL_EXTRA_NS = 6.7              # per dependent multiply, on top of the ALU rate
READ_HIT_EXTRA_NS_PER_BYTE = 0.5
READ_STREAM_EXTRA_NS_PER_BYTE = 6.8
READ_UNCACHED_EXTRA_NS_PER_BYTE = 12.4


def estimate_device_ns(emulator_ns, mul_insns=0, read_hit_bytes=0, read_stream_bytes=0, read_uncached_bytes=0):
    """Device nanoseconds for a stretch the emulator timed at `emulator_ns`, given what it did besides plain
    instructions: dependent multiplies, bytes read from data that was in the cache, bytes streamed from RAM, bytes
    read through the uncached alias (0xC4000000)."""
    return (emulator_ns + mul_insns * MUL_EXTRA_NS + read_hit_bytes * READ_HIT_EXTRA_NS_PER_BYTE
            + read_stream_bytes * READ_STREAM_EXTRA_NS_PER_BYTE + read_uncached_bytes * READ_UNCACHED_EXTRA_NS_PER_BYTE)
