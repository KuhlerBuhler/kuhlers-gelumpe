"""Task-only resource-1 acquisition with bounded retries and a locked handoff."""
import hashlib

import arm
from sample_swap_io import IRQ_DEPTH, STARTED, SEMA, RELEASE

CURRENT_TASK, TICK, DELAY = 0xC06A289C, 0xC06A292C, 0xC0000B78
ATTEMPTS, TIMEOUT_MS = 1000, 1000
OK, BUSY, STALE, CONTEXT, INVALID = range(5)
DELAY_BYTES, DELAY_SHA256 = 0xCC, '7315c82dbbbd7492c880e201b45152e90566089a349260eb1a2f47646f92aecf'


def validate_firmware(vsb):
    offset = DELAY - 0xC0000000 + 0x100
    if hashlib.sha256(vsb[offset:offset + DELAY_BYTES]).hexdigest() != DELAY_SHA256:
        raise ValueError('unmapped native task delay')


def source(*, fault, mode, generation, gate, session, owner, scope,
           current_task=CURRENT_TASK, sema=SEMA, tick=TICK, irq_depth=IRQ_DEPTH,
           started=STARTED, delay=DELAY, release=RELEASE,
           attempts=ATTEMPTS, timeout_ms=TIMEOUT_MS, gate_owner=None):
    values = dict(RG_FAULT=fault, RG_MODE=mode, RG_GEN=generation, RG_GATE=gate,
                  RG_SESSION=session, RG_OWNER=owner, RG_SCOPE=scope,
                  RG_TASK=current_task, RG_SEMA=sema, RG_TICK=tick,
                  RG_DEPTH=irq_depth, RG_STARTED=started, RG_DELAY=delay, RG_RELEASE=release)
    if gate_owner is not None:
        values['RG_GATE_OWNER'] = gate_owner
    if any(not 0 <= value <= 0xFFFFFFFC or value & 3 for value in values.values()):
        raise ValueError('word aligned resource guard addresses required')
    if owner > 0xFFFFFFF0:
        raise ValueError('resource owner must contain four words')
    if not 0 < attempts <= 0xFFFFFFFF or not 0 < timeout_ms <= 0x7FFFFFFF:
        raise ValueError('positive attempts and bounded millisecond deadline required')
    values.update(RG_ATTEMPTS=attempts, RG_TIMEOUT=timeout_ms, RG_FIELDS=8 + int(gate_owner is not None),
                  RG_BUSY=BUSY, RG_STALE=STALE, RG_CONTEXT=CONTEXT, RG_INVALID=INVALID)
    body = SOURCE.replace('@GATE_OWNER_FIELD@', '    .word RG_GATE_OWNER' if gate_owner is not None else '')
    return ''.join(f'.equ {name}, {value:#x}\n' for name, value in values.items()) + body


def build_code(origin, **kwargs):
    result = arm.assemble(source(**kwargs), origin=origin)
    return result.bytes, result.symbols


SOURCE = r'''
; r0 resource1, r1 library-bound policy. Success owns one lease with IRQs masked.
; r1 retains the policy. A nonzero status owns no lease and restores entry CPSR.
; r4-r11 and SP are preserved.
native_resource_take:
    push {r3-r11, lr}
    sub sp, sp, #56
    .word 0xE10F4000
    mov r11, #0
    mov r9, r1
    cmp r0, #1
    bne rg_invalid
    cmp r9, #1
    bhi rg_invalid
    tst r4, #0x80
    bne rg_context
    and r0, r4, #31
    cmp r0, #0x13
    cmpne r0, #0x1F
    bne rg_context
    orr r0, r4, #0x80
    .word 0xE121F000
    ldr r0, =RG_DEPTH
    ldr r0, [r0]
    cmp r0, #0
    bne rg_context
    ldr r0, =RG_STARTED
    ldr r0, [r0]
    cmp r0, #0
    beq rg_context
    ldr r0, =RG_TASK
    ldr r10, [r0]
    cmp r10, #0
    beq rg_context
    cmp r9, #0
    beq rg_snapshot_done
    ldr r0, =resource_identity_fields
    mov r1, sp
    mov r2, #RG_FIELDS
rg_snapshot:
    ldr r3, [r0], #4
    ldr r3, [r3]
    str r3, [r1], #4
    subs r2, r2, #1
    bne rg_snapshot
rg_snapshot_done:
    ldr r0, =RG_TICK
    ldr r8, [r0]
    ldr r7, =RG_ATTEMPTS
    ldr r6, =RG_SEMA
rg_attempt:
    orr r0, r4, #0x80
    .word 0xE121F000
    bl resource_current
    cmp r0, #0
    beq rg_stale
    ldr r0, =RG_TICK
    ldr r0, [r0]
    sub r0, r0, r8
    ldr r1, =RG_TIMEOUT
    cmp r0, r1
    bhs rg_busy
    ldr r0, [r6]
    cmp r0, #0
    beq rg_wait
    cmp r0, #1
    bne rg_invalid
    ldr r0, =RG_SCOPE
    ldr r0, [r0]
    cmp r0, #0
    bne rg_stale
    str r0, [r6]
    mov r11, #1
native_resource_acquired:
    bl resource_current
    cmp r0, #0
    beq rg_stale
    mov r0, #0
    mov r1, r9
    .word 0xE128F004
    add sp, sp, #56
    pop {r3-r11, pc}
rg_wait:
    subs r7, r7, #1
    beq rg_busy
    .word 0xE121F004
    mov r0, #1
    bl RG_DELAY
    cmp r0, #0
    bne rg_context
    b rg_attempt
rg_context:
    mov r5, #RG_CONTEXT
    b rg_fail
rg_invalid:
    mov r5, #RG_INVALID
    b rg_fail
rg_busy:
    mov r5, #RG_BUSY
    b rg_fail
rg_stale:
    mov r5, #RG_STALE
rg_fail:
    .word 0xE121F004
    cmp r11, #1
    bne rg_return
    mov r0, #1
    bl RG_RELEASE
rg_return:
    .word 0xE121F004
    .word 0xE128F004
    mov r0, r5
    mov r1, r9
    add sp, sp, #56
    pop {r3-r11, pc}
.pool

resource_current:
    ldr r0, =RG_DEPTH
    ldr r0, [r0]
    cmp r0, #0
    bne rg_no
    ldr r0, =RG_STARTED
    ldr r0, [r0]
    cmp r0, #0
    beq rg_no
    ldr r0, =RG_TASK
    ldr r0, [r0]
    cmp r0, r10
    bne rg_no
    ldr r0, =RG_FAULT
    ldr r0, [r0]
    cmp r0, #1
    bhi rg_no
    cmp r11, #1
    bne rg_check_policy
    ldr r0, =RG_SCOPE
    ldr r0, [r0]
    cmp r0, #0
    bne rg_no
rg_check_policy:
    cmp r9, #0
    bne rg_identity
    mov r0, #1
    bx lr
rg_identity:
    ldr r0, =resource_identity_fields
    mov r1, sp
    mov r2, #RG_FIELDS
rg_compare:
    ldr r3, [r0], #4
    ldr r3, [r3]
    ldr r12, [r1], #4
    cmp r3, r12
    bne rg_no
    subs r2, r2, #1
    bne rg_compare
    mov r0, #1
    bx lr
rg_no:
    mov r0, #0
    bx lr
.pool
resource_identity_fields:
    .word RG_MODE
    .word RG_GEN
    .word RG_GATE
    .word RG_SESSION
    .word RG_OWNER
    .word RG_OWNER + 4
    .word RG_OWNER + 8
    .word RG_OWNER + 12
@GATE_OWNER_FIELD@
'''
