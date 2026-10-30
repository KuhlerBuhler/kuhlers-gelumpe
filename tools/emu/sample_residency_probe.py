"""Observe native voice bindings after a controlled sample mapping publication.

The model assigns unused identity-mapped rows and publishes their CPU tables
while emulation is paused. It is not an installed residency allocator and does
not test audio, DMA or concurrent publication.
"""
import argparse
import json
import struct
from pathlib import Path

import swap_cases as c
import sample_swap as spec


def publish_native(box, descriptor, key, base):
    """Use native CPU registration with IRQs masked across the temporary import binding."""
    wrapper = 0xC1003000
    assembly = f"""
        push {{r4-r10, lr}}
        mov r4, r0
        mov r10, r2
        ldrh r0, [r4]
        ldr r5, ={c.NAMES}
        add r5, r5, r0, lsl #5
        ldrh r7, [r5, #30]
        ldr r9, ={c.CURSOR}
        ldr r6, [r9]
        .word 0xE10F8000
        orr r3, r8, #0x80
        .word 0xE121F003
        add r3, r1, #50
        strh r3, [r5, #30]
        str r10, [r9]
        mov r0, r4
        bl {spec.FIRMWARE['RESERVE']}
        cmp r0, #0
        bne np_cursor
        strh r7, [r5, #30]
    np_cursor:
        ldr r3, [r9]
        cmp r6, r3
        strhi r6, [r9]
        .word 0xE121F008
        pop {{r4-r10, pc}}
        .pool
    """
    box.m.uc.mem_write(spec.DESC2, bytes(descriptor))
    box.m.uc.mem_write(wrapper, spec.arm.assemble(spec.halfword(assembly), origin=wrapper).bytes)
    return box.dev.call(wrapper, spec.DESC2, key, base)


def trace_part_update(box, slot):
    """Record peripheral accesses while the native part refresh runs."""
    wrapper = 0xC1004000
    code = f"push {{r4, r11, r12, lr}}\nldr r11, ={spec.STATE}\nbl {box.sym['apply_ready_parts']}\npop {{r4, r11, r12, pc}}\n.pool"
    box.m.uc.mem_write(wrapper, spec.arm.assemble(code, origin=wrapper).bytes)
    events, calls = [], []

    def entry(uc, address, size, _):
        calls.append(dict(entry=hex(address), return_pc=hex(uc.reg_read(box.m.A.UC_ARM_REG_LR)),
                          args=[uc.reg_read(box.m.A.UC_ARM_REG_R0 + i) for i in range(4)],
                          fifth=box.u32(uc.reg_read(box.m.A.UC_ARM_REG_SP))))

    def access(uc, kind, address, size, value, _):
        events.append(dict(pc=hex(uc.reg_read(box.m.A.UC_ARM_REG_PC)),
                           address=hex(address), size=size,
                           access="write" if kind == c.unicorn.UC_MEM_WRITE else "read",
                           value=value if kind == c.unicorn.UC_MEM_WRITE else None))

    hooks = [box.m.uc.hook_add(c.unicorn.UC_HOOK_MEM_READ | c.unicorn.UC_HOOK_MEM_WRITE, access, begin=lo, end=hi)
             for lo, hi in ((0, 0xBFFFFFFF), (0xC4000000, 0xFFFFFFFF))]
    hooks.extend(box.m.uc.hook_add(c.unicorn.UC_HOOK_CODE, entry, begin=at, end=at)
                 for at in (0xC001462C, 0xC00146B4, 0xC001488C))
    try:
        box.dev.call(wrapper, slot)
    finally:
        for hook in hooks:
            box.m.uc.hook_del(hook)
    return events, calls


def probe(payload, check_eviction=False, native_publication=False, kind="pcm16", trace_parts=False):
    if kind not in ("pcm16", "pcm24", "stereo16"):
        raise ValueError("unsupported generated sample kind")
    stereo = kind == "stereo16"
    wave = c.plain_wav(400) if kind == "pcm16" else c.sampleset.wav(600, "Own new", 400, kind=kind)
    pcm = c.plain_wav(400)[44:] if kind == "pcm16" else c.wav_pcm(600, 400, kind)
    box = c.Box(payload, None, {500: ("Own old", 100), 600: ("Own spare", 300)},
                [600, 600, 500] if stereo else [500, 600], record_dsp=True, extra={"/new.wav": wave.hex()})
    uc = box.m.uc

    def put32(address, value):
        uc.mem_write(address, struct.pack("<I", value))

    def put16(address, value):
        uc.mem_write(address, struct.pack("<H", value))

    put16(c.NAMES + 600 * 32 + 30, 550)
    box.dev.call(0xC009A0A8, 0xFFFFFFFF)
    voice_calls = []

    def voice_created(machine, *_):
        voice_calls.append((machine.reg_read(box.m.A.UC_ARM_REG_R0),
                            machine.reg_read(box.m.A.UC_ARM_REG_R1)))

    uc.hook_add(c.unicorn.UC_HOOK_CODE, voice_created, begin=0xC00998B4, end=0xC00998B4)
    for part in ((0, 2) if stereo else (0, 1)):
        box.m.send([4, part, 0, 100, 1])
        box.run(0.1)
    voices_before = [dict(address=address, slot=slot, import_number=box.u16(address + 0x40))
                     for address, slot in voice_calls]
    retained = [v for v in voices_before if v["slot"] == 500] if stereo else voices_before
    old = box.dsp_bytes(*box.extent(500))
    path = 0xC1001000
    uc.mem_write(path, b"SD:/new.wav\0")
    opened = box.dev.call(spec.FIRMWARE["F_OPEN"], spec.FIL, path, 1)
    box.dev.call(0xC004E1F4, spec.DESC)
    put32(spec.STATE + spec.OFF["PREP"], 1)
    parsed = box.dev.call(spec.FIRMWARE["PARSER"], spec.FIL, spec.DESC, 600, path)
    put32(spec.STATE + spec.OFF["PREP"], 0)
    closed = box.dev.call(spec.FIRMWARE["F_CLOSE"], spec.FIL)
    descriptor = bytearray(uc.mem_read(spec.DESC, 0x4A0))
    key, sentinel, physical = 601, 602, 601
    available = (box.meta_index(key) == physical and not box.resident(key)
                 and not box.resident(sentinel))
    if opened != 0 or parsed != 126 or closed != 0 or not available:
        return dict(ok=False, opened=opened, parsed=parsed, closed=closed, available=available)

    remapped = []
    for slot in range(spec.FIRST_USER, spec.LAST_USER + 1):
        if box.u16(c.NAMES + slot * 32 + 30) == key + 50:
            if box.resident(slot):
                return dict(ok=False, unexpected_resident=slot)
            put16(c.NAMES + slot * 32 + 30, sentinel + 50)
            remapped.append(slot)

    base = (box.u32(c.CURSOR) + 31) & ~31
    put32(c.CURSOR, base + len(pcm))
    uc.mem_write(spec.STAGE, pcm)
    transferred = box.dev.call(box.sym["transfer"], 1, spec.STAGE, base, len(pcm) // 2)
    if transferred != 0:
        return dict(ok=False, transferred=transferred)

    struct.pack_into("<H", descriptor, 20, key + 50)
    struct.pack_into("<I", descriptor, 56, base)
    published = publish_native(box, descriptor, key, base) if native_publication else None
    if not native_publication:
        meta = c.META + physical * 0x45C
        repeated_index = bytes(uc.mem_read(meta + 22, 2))
        uc.mem_write(meta, bytes(descriptor[56:56 + 0x45C]))
        uc.mem_write(meta + 22, repeated_index)
        play = c.PLAYBACK + physical * 16
        put32(play, base + struct.unpack_from("<I", descriptor, 40)[0])
        put32(play + 4, struct.unpack_from("<I", descriptor, 44)[0])
        put32(play + 8, struct.unpack_from("<I", descriptor, 48)[0])
        uc.mem_write(play + 14, bytes(descriptor[52:54]))
        mapped = box.u16(spec.FIRMWARE["MAP_B"] + key * 16 + 8)
        uc.mem_write(spec.FIRMWARE["MAP_C"] + mapped * 8 + 4, bytes(descriptor[34:38]))
        uc.mem_write(c.NAMES + 600 * 32 + 12, bytes(descriptor[2:34]))

    part_kinds, part_io, part_calls = None, None, None
    if stereo:
        part = box.dev.call(spec.FIRMWARE["PART"], 0)
        put16(box.u32(part + 8) + 8, 600)
        if not trace_parts:
            box.dev.call(spec.FIRMWARE["PART_UPDATE"], part)
    if trace_parts:
        part_io, part_calls = trace_part_update(box, 600)
    if stereo:
        part_kinds = [uc.mem_read(box.dev.call(spec.FIRMWARE["PART"], i) + 0x39, 1)[0] for i in range(3)]
    old_keys = all(box.u16(v["address"] + 0x40) == v["import_number"] for v in retained)
    part = 0 if stereo else 1
    box.m.send([4, part, 0, 0, 0])
    box.run(0.1)
    box.m.send([4, part, 0, 100, 1])
    box.run(0.1)
    voices_after = [dict(address=address, slot=slot, import_number=box.u16(address + 0x40))
                    for address, slot in dict(voice_calls).items()]
    retained_after_note = all(box.u16(v["address"] + 0x40) == v["import_number"]
                              and box.u32(v["address"] + 4) != 0 for v in retained)
    new_pcm = box.dsp_bytes(*box.extent(600)) == pcm
    old_pcm = box.dsp_bytes(*box.extent(500)) == old
    unloaded = not box.resident(601)
    new_voice = len(voice_calls) == 3 and box.u16(voice_calls[-1][0] + 0x40) == key + 50
    old_voices = len(voices_before) == 2 and all(v["import_number"] == 550 for v in voices_before)
    eviction = dict()
    if check_eviction:
        for part in range(16):
            address = box.dev.call(spec.FIRMWARE["PART"], part)
            put16(address + 0x34, 600)
            record = box.u32(address + 8)
            put16(record + 8, 600)
        uc.mem_write(spec.STATE + spec.PROT, struct.pack("<32H", *([600] * 16 + [0xFFFF] * 16)))
        if "mark_clean" in box.sym:
            # this box starts without the swap, so its start recorded no rows: slot 500 is still as the file loaded it
            box.dev.call(box.sym["mark_clean"], 500)
        wrapper = 0xC1002000
        source = f"push {{r4, r11, r12, lr}}\nldr r11, ={spec.STATE}\nbl {box.sym['victim']}\npop {{r4, r11, r12, pc}}\n.pool"
        uc.mem_write(wrapper, spec.arm.assemble(source, origin=wrapper).bytes)
        busy_before = [box.dev.call(spec.FIRMWARE["VOICE_USED"], (v["address"] - spec.FIRMWARE["VOICES"]) // 0x48)
                       for v in retained]
        pinned = box.dev.call(wrapper)
        for voice in retained:
            box.dev.call(0xC0091AD0, voice["address"])
        busy_after = [box.dev.call(spec.FIRMWARE["VOICE_USED"], (v["address"] - spec.FIRMWARE["VOICES"]) // 0x48)
                      for v in retained]
        released = box.dev.call(wrapper)
        stale_pointers = all(box.u32(v["address"] + 4) != 0 for v in retained)
        eviction = dict(ok=all(busy_before) and not any(busy_after) and pinned == 0 and released == 500 and stale_pointers,
                        candidate_with_old_voices=pinned, candidate_after_native_cleanup=released,
                        old_voice_busy_before=busy_before, old_voice_busy_after=busy_after,
                        released_voice_part_pointers_retained=stale_pointers,
                        completion_simulated=True)
    return dict(ok=new_pcm and old_pcm and unloaded and old_keys and old_voices and new_voice and retained_after_note
                and box.meta_index(600) == physical and not box.m.asserts and eviction.get("ok", True)
                and published in (None, 1),
                eviction=eviction, native_publication_status=published,
                kind=kind, voices_before=voices_before, voices_after=voices_after,
                protected_voices_before=retained, voice_creation_calls=len(voice_calls),
                part_kinds_after_publication=part_kinds, part_peripheral_accesses=part_io, part_native_calls=part_calls,
                protected_voice_imports_retained_at_publication=old_keys, remapped_unloaded_slots=remapped,
                protected_voice_imports_retained_after_new_note=retained_after_note,
                new_physical=box.meta_index(600), new_pcm_equal=new_pcm,
                old_alias_pcm_equal=old_pcm, unloaded_slot_stays_nonresident=unloaded,
                asserts=box.m.asserts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patched", required=True, type=Path)
    parser.add_argument("--check-eviction", action="store_true")
    parser.add_argument("--native-publication", action="store_true")
    parser.add_argument("--kind", choices=("pcm16", "pcm24", "stereo16"), default="pcm16")
    parser.add_argument("--trace-part-update", action="store_true")
    args = parser.parse_args()
    result = probe(args.patched.read_bytes()[c.HEADER:], args.check_eviction, args.native_publication, args.kind, args.trace_part_update)
    print(json.dumps(dict(hardware_contact=False, audio=False, dma=False,
                          model_assumptions=["inactive identity-mapped rows601 and602",
                                             "PCM completes before paused CPU table publication",
                                             "no concurrent native edit or voice control",
                                             "voice completion is simulated through native CPU cleanup"],
                          result=result), indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
