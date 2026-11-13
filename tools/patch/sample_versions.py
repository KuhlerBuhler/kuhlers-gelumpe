"""Physical-row tags for verified file entries within one sample collection.

Zero means unregistered. The caller clears tags when replacing the library,
publishes tags with DSP metadata and protects catalogue changes with its lease.
This module installs no hooks or RAM reservations.
"""
import arm


def source(table, header, *, count=999):
    if not isinstance(count, int) or not 0 < count <= 1020:
        raise ValueError('sample count must fit the file header')
    if any(not isinstance(at, int) or at & 3 for at in (table, header)):
        raise ValueError('word aligned table and header required')
    if not 0 <= table <= 0x100000000 - count * 4 or not 0 <= header <= 0xFFFFF000:
        raise ValueError('version state exceeds the address space')
    if table < header + 4096 and header < table + count * 4:
        raise ValueError('version table overlaps the file header')
    values = dict(V_TABLE=table, V_HEADER=header, V_COUNT=count)
    return ''.join(f'.equ {name}, {value:#x}\n' for name, value in values.items()) + SOURCE


def build_code(origin, table, header, *, count=999):
    if not isinstance(origin, int) or origin & 3 or not 0 <= origin <= 0xFFFFFFFC:
        raise ValueError('word aligned version code required')
    code = source(table, header, count=count)
    end = origin + len(arm.assemble(code, origin=0).bytes)
    if end > 0x100000000:
        raise ValueError('version code exceeds the address space')
    for lo, hi in ((table, table + count * 4), (header, header + 4096)):
        if origin < hi and lo < end:
            raise ValueError('version code overlaps catalogue state')
    assembled = arm.assemble(code, origin=origin)
    return assembled.bytes, assembled.symbols


SOURCE = r'''
versions_clear:
    ldr r2, =V_TABLE
    ldr r3, =V_COUNT
    mov r0, #0
vc_word:
    str r0, [r2], #4
    subs r3, r3, #1
    bne vc_word
    bx lr

; r0 physical row, r1 verified file offset or zero. Returns zero on success.
version_set:
    ldr r2, =V_COUNT
    cmp r0, r2
    bhs vs_bad
    cmp r1, #0
    beq vs_store
    cmp r1, #4096
    blo vs_bad
vs_store:
    ldr r2, =V_TABLE
    str r1, [r2, r0, lsl #2]
    mov r0, #0
    bx lr
vs_bad:
    mov r0, #1
    bx lr

; r0 physical row. Returns its file offset, zero if unregistered or invalid.
version_get:
    ldr r1, =V_COUNT
    cmp r0, r1
    movhs r0, #0
    bxhs lr
    ldr r1, =V_TABLE
    ldr r0, [r1, r0, lsl #2]
    bx lr

; r0 logical slot, r1 physical row. A nonzero matching entry returns one.
version_matches:
    ldr r2, =V_COUNT
    cmp r0, r2
    bhs vm_no
    cmp r1, r2
    bhs vm_no
    ldr r2, =V_HEADER + 16
    ldr r2, [r2, r0, lsl #2]
    cmp r2, #4096
    blo vm_no
    ldr r3, =V_TABLE
    ldr r0, [r3, r1, lsl #2]
    cmp r0, r2
    moveq r0, #1
    movne r0, #0
    bx lr
vm_no:
    mov r0, #0
    bx lr
.pool
'''
