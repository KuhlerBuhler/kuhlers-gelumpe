"""Swap reader cleanup against native FatFs with generated collection data."""
import argparse
import json
import struct
from pathlib import Path

import swap_cases as c


def case(payload, close_error=False, short_header=False):
    sections, _ = c.spec.build_code(c.firmware.identify(payload).screens)
    if any(payload[at - c.IMAGE:at - c.IMAGE + len(data)] != data for at, data in sections):
        raise ValueError('patched sample runtime differs from the current builder')
    samples = {500: ('Own reader', 100), 501: ('Other reader', 200)}
    box = c.Box(payload, None, samples, [500])
    uc = box.m.uc
    end = max(at + len(data) for at, data in sections if c.spec.STORE_CODE <= at < c.spec.STORE_CODE_END)
    origin = (end + 15) & ~15
    assembled = c.spec.arm.assemble(f'''
read_header:
    push {{r4, r10, r11, lr}}
    ldr r11, ={c.spec.STATE}
    mov r0, #{c.spec.sample_owner.READ}
    bl {box.sym['owner_acquire']}
    cmp r0, #0
    popne {{r4, r10, r11, pc}}
    mov r10, r1
    bl {box.sym['ensure_file']}
    mov r4, r0
    mov r0, r10
    bl {box.sym['owner_release']}
    mov r0, r4
    pop {{r4, r10, r11, pc}}
close_header:
    push {{r4, r10, r11, lr}}
    ldr r11, ={c.spec.STATE}
    ldr r0, ={c.spec.FILE_OWNER + 8}
    ldr r0, [r0]
    cmp r0, #0
    moveq r0, #{c.spec.sample_owner.READ}
    movne r0, #{c.spec.sample_owner.RECOVER}
    bl {box.sym['owner_acquire']}
    cmp r0, #0
    popne {{r4, r10, r11, pc}}
    mov r10, r1
    bl {box.sym['close_reader']}
    mov r4, r0
    mov r0, r10
    bl {box.sym['owner_release']}
    mov r0, r4
    pop {{r4, r10, r11, pc}}
.pool
''', origin=origin)
    if origin + len(assembled.bytes) > c.spec.STORE_CODE_END:
        raise ValueError('reader probe exceeds unused owned code space')
    if any(value != 255 for value in payload[origin - c.IMAGE:origin - c.IMAGE + len(assembled.bytes)]):
        raise ValueError('reader probe code space is occupied')
    uc.mem_write(origin, assembled.bytes)
    warm = box.dev.call(assembled.symbols['read_header'])
    before = bytes(uc.mem_read(c.META, c.spec.SAMPLE_COUNT * 0x45C))
    generation = box.state('GEN') + 1
    uc.mem_write(c.spec.STATE + c.spec.OFF['GEN'], struct.pack('<I', generation))
    observed = dict(opens=0, closes=0, shortened=0)
    inject = [True]

    def opened(*_):
        observed['opens'] += 1

    def closing(machine, *_):
        observed['closes'] += 1
        if inject[0] and close_error and observed['closes'] == (2 if short_header else 1):
            machine.reg_write(box.m.A.UC_ARM_REG_R0, 1)
            machine.reg_write(box.m.A.UC_ARM_REG_PC, machine.reg_read(box.m.A.UC_ARM_REG_LR))

    def reading(machine, *_):
        if short_header:
            machine.reg_write(box.m.A.UC_ARM_REG_R2, 4092)
            observed['shortened'] += 1

    for address, callback in ((c.spec.FIRMWARE['F_OPEN'], opened), (c.spec.FIRMWARE['F_CLOSE'], closing),
                              (c.spec.FIRMWARE['F_READ'], reading)):
        uc.hook_add(c.unicorn.UC_HOOK_CODE, callback, begin=address, end=address)
    result = box.dev.call(assembled.symbols['read_header'])
    file_state, mode = box.state('FILE'), box.state('MODE')
    expected_file = 2 if close_error else 0 if short_header else 1
    expected_opens = 0 if close_error and not short_header else 1
    inject[0] = False
    cleanup = box.dev.call(assembled.symbols['close_header'])
    volume = c.fat32.Volume(bytes(box.m.mmc.card.medium.data))
    try:
        library = volume.read(f'KORG/{c.cardstore.card_folder(payload)}/Sample/e2sSample.all')
    finally:
        volume.close()
    unchanged = bytes(uc.mem_read(c.META, len(before))) == before
    owner = struct.unpack('<4I', uc.mem_read(c.spec.FILE_OWNER, 16))
    ok = (warm == 0 and (result != 0) == (close_error or short_header)
          and file_state == expected_file and observed['opens'] == expected_opens
          and mode == (2 if close_error or short_header else 0)
          and cleanup == 0 and box.state('FILE') == 0 and unchanged
          and library == c.sampleset.build(samples) and owner[0] == 0
          and owner[2] == int(close_error or short_header)
          and not box.m.asserts)
    return dict(ok=ok, close_error=close_error, short_header=short_header, result=result,
                file_state_before_cleanup=file_state, file_state_after_cleanup=box.state('FILE'),
                mode=mode, cleanup=cleanup, metadata_unchanged=unchanged, owner=owner,
                **observed, asserts=box.m.asserts)


def competing_owner(payload):
    box = c.Box(payload, None, c.small(range(500, 510)), [500], cap=0x40000)
    uc, owner = box.m.uc, c.spec.sample_owner
    acquired = box.dev.call(box.sym['owner_acquire'], owner.WRITE)
    token = box.u32(c.spec.FILE_OWNER)
    before = bytes(uc.mem_read(c.META, c.spec.SAMPLE_COUNT * 0x45C))
    generation = box.state('GEN')
    calls = []
    hooks = [uc.hook_add(c.unicorn.UC_HOOK_CODE, lambda machine, at, *args: calls.append(at), begin=address, end=address)
             for address in (c.spec.FIRMWARE['F_OPEN'], c.spec.FIRMWARE['F_READ'], c.spec.FIRMWARE['F_CLOSE'])]
    box.dev.call(box.sym['ss_step'])
    reload_result = box.dev.call(0xC00364F0, 0)
    held = box.u32(c.spec.FILE_OWNER) == token
    unchanged = bytes(uc.mem_read(c.META, len(before))) == before and box.state('GEN') == generation
    released = box.dev.call(box.sym['owner_release'], token)
    box.dev.call(box.sym['ss_step'])
    blocked = box.dev.call(box.sym['owner_acquire'], owner.READ)
    for hook in hooks:
        uc.hook_del(hook)
    state = struct.unpack('<4I', uc.mem_read(c.spec.FILE_OWNER, 16))
    ok = (acquired == 0 and token != 0 and reload_result == 4 and held and unchanged and not calls
          and released == 0 and blocked == owner.NEEDS_RECOVERY and state[0] == 0
          and state[2] == 1 and not box.m.asserts)
    return dict(ok=ok, competing_owner=True, acquired=acquired, reload_result=reload_result,
                lease_retained=held, metadata_and_generation_unchanged=unchanged, card_calls=calls,
                released=released, subsequent_reader=blocked, owner=state, asserts=box.m.asserts)


def cases(payload):
    return [case(payload, close_error, short_header) for close_error in (False, True) for short_header in (False, True)] + [competing_owner(payload)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patched', type=Path, required=True)
    args = parser.parse_args()
    rows = cases(args.patched.read_bytes()[256:])
    print(json.dumps(dict(hardware_contact=False, audio=False, dma=False, results=rows), indent=2))
    return 0 if all(row['ok'] for row in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
