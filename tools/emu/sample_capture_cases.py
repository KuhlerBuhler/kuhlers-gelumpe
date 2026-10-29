"""Synthetic DSP capture completion and native PCM export, without audio or DMA."""
import argparse
import json
import struct
from pathlib import Path

import swap_cases as c


def cases(payload):
    box = c.Box(payload, None, {500: ("Own capture context", 2001)}, [500])
    transport = box.dev.call(0xC0030D28)
    cursor = box.u32(c.CURSOR)
    started = box.dev.call(0xC0082F1C, transport, 0)
    recording = box.u32(transport + 0x308)
    pcm = c.wav_pcm(501, 1025)
    end = cursor + len(pcm)
    box.m.dsp_mem[0xFF903210] = end & 0xFFFF
    box.m.dsp_mem[0xFF903212] = end >> 16
    for offset in range(0, len(pcm), 2):
        box.m.dsp_mem[cursor + offset] = struct.unpack_from("<H", pcm, offset)[0]
    box.dev.call(0xC0082D40, transport)
    extent = box.extent(501)
    finalized = box.resident(501) and extent == (cursor, len(pcm))
    out = [dict(id="synthetic_capture_finalizes_the_dsp_extent",
                ok=started == 1 and recording == 11 and box.u32(transport + 0x308) == 12
                and finalized and box.u32(c.CURSOR) == end and not box.m.asserts,
                model_assumption="generated PCM and capture end in DSP model; no audio or DMA",
                bytes=len(pcm), extent_correct=finalized)]
    exported = box.dev.call(0xC0039CC4, 0xC100A000, 501)
    volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
    try:
        waves = [volume.read(path) for path, _ in volume.walk() if path.lower().endswith(".wav")]
    finally:
        volume.close()
    file_equal = len(waves) == 1 and waves[0][44:44 + len(pcm)] == pcm
    box.dev.call(0xC004EDDC, 0xC1008000, cursor, len(pcm) // 2)
    read_equal = bytes(box.m.uc.mem_read(0xC1008000, len(pcm))) == pcm
    out.append(dict(id="native_capture_export_and_readback_preserve_generated_pcm",
                    ok=exported == 0 and file_equal and read_equal and not box.m.asserts,
                    file_pcm_equal=file_equal, dsp_read_equal=read_equal))
    destination = 0xC2770010
    box.m.uc.mem_write(destination - 4, b'HEAD' + bytes(len(pcm)) + b'TAIL')
    status = box.dev.call(box.sym["transfer"], 0, destination, cursor, len(pcm) // 2)
    bounded_equal = bytes(box.m.uc.mem_read(destination, len(pcm))) == pcm
    guards = (bytes(box.m.uc.mem_read(destination - 4, 4)) == b'HEAD'
              and bytes(box.m.uc.mem_read(destination + len(pcm), 4)) == b'TAIL')
    out.append(dict(id="bounded_capture_read_preserves_unaligned_pcm_and_buffer_edges",
                    ok=status == 0 and bounded_equal
                    and guards and cursor % 32 != 0 and len(pcm) % 32 != 0 and not box.m.asserts,
                    status=status, pcm_equal=bounded_equal,
                    buffer_edges_unchanged=guards))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patched", required=True, type=Path)
    args = parser.parse_args()
    checks = cases(args.patched.read_bytes()[c.HEADER:])
    print(json.dumps(dict(hardware_contact=False, audio=False, dma=False, checks=checks), indent=2))
    return 0 if all(check["ok"] for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
