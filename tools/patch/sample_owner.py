"""Exclusive file leases and catalogue recovery state for ARM task callers.

State contains current token, last token, uncertain catalogue and lease kind.
Only a writer or recovery lease can acknowledge a checked catalogue.
The caller initializes state and performs all file I/O outside these routines.
"""
import struct

import arm
from sample_swap_io import IRQ_DEPTH, STARTED

READ, WRITE, RECOVER = 1, 2, 3
OK, BUSY, NEEDS_RECOVERY, CONTEXT, INVALID, EXHAUSTED = range(6)
INITIAL = struct.pack('<4I', 0, 0, 1, 0)


def source(state):
    if state & 3 or not 0 <= state <= 0xFFFFFFF0:
        raise ValueError('word aligned file owner state required')
    values = dict(FO_STATE=state, FO_IRQ_DEPTH=IRQ_DEPTH, FO_STARTED=STARTED,
                  FO_READ=READ, FO_WRITE=WRITE, FO_RECOVER=RECOVER,
                  FO_OK=OK, FO_BUSY=BUSY, FO_NEEDS_RECOVERY=NEEDS_RECOVERY,
                  FO_CONTEXT=CONTEXT, FO_INVALID=INVALID, FO_EXHAUSTED=EXHAUSTED)
    return ''.join(f'.equ {name}, {value:#x}\n' for name, value in values.items()) + SOURCE


def build_code(origin, state):
    if origin & 3:
        raise ValueError('word aligned file owner code required')
    result = arm.assemble(source(state), origin=origin)
    if origin < state + 16 and state < origin + len(result.bytes):
        raise ValueError('file owner code overlaps its state')
    return result.bytes, result.symbols


SOURCE = r'''
; r0 kind. Returns status in r0, a nonzero lease token in r1 on success.
owner_acquire:
    push {r4-r8, lr}
    mov r5, r0
    mov r6, #0
    cmp r5, #FO_READ
    blo own_invalid_context
    cmp r5, #FO_RECOVER
    bhi own_invalid_context
    b own_context

; r0 token. Releasing a writer never implicitly resolves its catalogue.
owner_release:
    push {r4-r8, lr}
    mov r5, r0
    mov r6, #1
    b own_context

; r0 token, after successful journal recovery and catalogue readback.
owner_resolve:
    push {r4-r8, lr}
    mov r5, r0
    mov r6, #2
    b own_context

; r0 token, after a read or close failure whose catalogue is not trusted.
owner_uncertain:
    push {r4-r8, lr}
    mov r5, r0
    mov r6, #3
    b own_context

; r0 token. Only the current reader of a checked catalogue may load samples.
owner_readable:
    push {r4-r8, lr}
    mov r5, r0
    mov r6, #4

own_context:
    .word 0xE10F4000
    and r0, r4, #31
    cmp r0, #0x13
    cmpne r0, #0x1f
    bne own_bad_context
    cmp r6, #0
    bne own_depth
    tst r4, #0x80
    bne own_bad_context
own_depth:
    ldr r0, =FO_IRQ_DEPTH
    ldr r0, [r0]
    cmp r0, #0
    bne own_bad_context
    ldr r0, =FO_STARTED
    ldr r0, [r0]
    cmp r0, #0
    beq own_bad_context
    ldr r7, =FO_STATE
    orr r3, r4, #0x80
    .word 0xE121F003
    mov r1, #0
    cmp r6, #0
    bne own_owned
    ldr r0, [r7]
    cmp r0, #0
    bne own_busy
    ldr r0, [r7, #8]
    cmp r0, #1
    bhi own_invalid
    cmp r5, #FO_RECOVER
    beq own_next
    cmp r0, #0
    bne own_recovery
own_next:
    ldr r0, [r7, #4]
    cmn r0, #1
    beq own_exhausted
    add r1, r0, #1
    str r1, [r7, #4]
    str r1, [r7]
    str r5, [r7, #12]
    cmp r5, #FO_READ
    movne r0, #1
    strne r0, [r7, #8]
    mov r0, #FO_OK
    b own_done

own_owned:
    cmp r5, #0
    beq own_invalid
    ldr r0, [r7]
    cmp r0, r5
    bne own_invalid
    ldr r0, [r7, #12]
    cmp r0, #FO_READ
    blo own_invalid
    cmp r0, #FO_RECOVER
    bhi own_invalid
    cmp r6, #1
    beq own_release
    cmp r6, #3
    moveq r0, #1
    streq r0, [r7, #8]
    moveq r0, #0
    beq own_done
    cmp r6, #4
    beq own_readable
    cmp r0, #FO_READ
    beq own_invalid
    ldr r0, [r7, #8]
    cmp r0, #1
    bhi own_invalid
    mov r0, #0
    str r0, [r7, #8]
    b own_done
own_readable:
    cmp r0, #FO_READ
    bne own_invalid
    ldr r0, [r7, #8]
    cmp r0, #0
    bne own_recovery
    b own_done
own_release:
    mov r0, #0
    str r0, [r7]
    str r0, [r7, #12]
    b own_done
own_busy:
    mov r0, #FO_BUSY
    b own_done
own_recovery:
    mov r0, #FO_NEEDS_RECOVERY
    b own_done
own_exhausted:
    mov r0, #FO_EXHAUSTED
    b own_done
own_invalid:
    mov r0, #FO_INVALID
own_done:
    .word 0xE121F004
    pop {r4-r8, pc}
own_invalid_context:
    mov r0, #FO_INVALID
    mov r1, #0
    pop {r4-r8, pc}
own_bad_context:
    mov r0, #FO_CONTEXT
    mov r1, #0
    pop {r4-r8, pc}
.pool
'''
