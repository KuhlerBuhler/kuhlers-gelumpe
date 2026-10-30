"""Recovery for FP-based native void DSP transactions after resource 1 is taken.

The caller supplies initialized state and a frame with saved FP at FP-4
and return address at FP. Enter reserves 16 bytes for outgoing arguments.
Take wraps acquisition; close restores the native SP and releases its lease.
Leave clears the context for callers whose own epilogue restores SP.
Abort releases an owned resource once and returns to the native caller.
Borrowed resources remain with their outer caller on success and failure.
Refused acquisition aborts without releasing a resource.
Active scopes must be serialized; borrowing a lease does not nest scopes.
This module installs no firmware hooks.
Before initialization, native acquisition and release retain their original
behavior. Initialization preserves an active scope and any latched fault.
The kernel release runs with IRQs enabled; abort restores the caller's
interrupt control before returning.
"""
import hashlib

import arm
from sample_swap_io import TIMER, TIMER_HZ, DEADLINE_TICKS, POLL_BUDGET, RELEASE, validate_firmware as validate_transport

CONTEXT_BYTES = 96
ACQUIRE = 0xC0000D80
RESOURCE_SITES = (
    (0xc0012794, 0xc00127a4), (0xc0012800, 0xc0012820),
    (0xc0012884, 0xc00128a8), (0xc0012908, 0xc0012928),
    (0xc001298c, 0xc00129ac), (0xc0012a0c, 0xc0012a30),
    (0xc0012a94, 0xc0012ab4), (0xc0012b14, 0xc0012b38),
    (0xc0012b98, 0xc0012bb4), (0xc0012c10, 0xc0012c2c),
    (0xc0012c90, 0xc0012cb8), (0xc0012d18, 0xc0012d38),
    (0xc0012d9c, 0xc0012dbc), (0xc0012e20, 0xc0012e40),
    (0xc0012ea4, 0xc0012ec8), (0xc0012f28, 0xc0012f48),
    (0xc0012fac, 0xc0012fcc), (0xc001302c, 0xc00130f0),
    (0xc001315c, 0xc0013220), (0xc001328c, 0xc00132ac),
    (0xc0013310, 0xc00134d8), (0xc0013544, 0xc001370c),
    (0xc0013778, 0xc0013794), (0xc00137fc, 0xc0013948),
    (0xc00139b8, 0xc00139d8), (0xc0013a38, 0xc0013a58),
    (0xc0013abc, 0xc0013ae0), (0xc0013b44, 0xc0013c98),
    (0xc0013d50, 0xc0013d84), (0xc0013de8, 0xc0013ee8),
    (0xc0014248, 0xc0014274), (0xc00142d4, 0xc00142f8),
    (0xc0014348, 0xc0014358), (0xc00143b0, 0xc00143d4),
    (0xc0014420, 0xc0014438),
)
CONTROL_SITES = (0xC0014650, 0xC0014710, 0xC00147C0, 0xC0014920, 0xC00149E0)
GPIO_SITES = (0xC00146F8, 0xC00147A8, 0xC0014810, 0xC0014908, 0xC00149C8, 0xC0014A30)
HOOKS = tuple(hook for acquire, release in RESOURCE_SITES for hook in (
    (acquire, None, ACQUIRE, 'native_scope_take'),
    (release, None, RELEASE, 'native_scope_close'),
)) + tuple((site, 0xE1D330B0, None, 'native_scope_control') for site in CONTROL_SITES) + tuple(
    (site, None, 0xC00145F0, 'native_scope_gpio') for site in GPIO_SITES)


def validate_firmware(vsb):
    build = validate_transport(vsb)
    start = 0xC0011000 - 0xC0000000 + 0x100
    if hashlib.sha256(vsb[start:start + 0x362C]).hexdigest() != 'b5e36f35f65d015dfafd8205dee0a8f57daeaf7a696bb76f6b5ed8c289520169':
        raise ValueError('unmapped native DSP resource wrappers')
    return build


def source(*, scope, fault, mode, generation, release=RELEASE, acquire=ACQUIRE,
           timer=TIMER, poll_budget=POLL_BUDGET):
    values = dict(NS_SCOPE=scope, NS_FAULT=fault, NS_MODE=mode, NS_GEN=generation,
                  NS_RELEASE=release, NS_ACQUIRE=acquire, NS_TIMER=timer, NS_HZ=TIMER_HZ,
                  NS_DEADLINE=DEADLINE_TICKS, NS_POLLS=poll_budget)
    if any(value & 3 for value in (scope, fault, mode, generation, release, acquire, timer)):
        raise ValueError('scope addresses must be word aligned')
    if not 0 < poll_budget <= 0xFFFFFFFF:
        raise ValueError('positive 32-bit poll budget required')
    return ''.join(f'.equ {name}, {value:#x}\n' for name, value in values.items()) + SOURCE


def build_code(origin, **kwargs):
    result = arm.assemble(source(**kwargs), origin=origin)
    return result.bytes, result.symbols


def driver_source(**kwargs):
    return source(**kwargs) + DRIVER


def build_driver_code(origin, **kwargs):
    result = arm.assemble(driver_source(**kwargs), origin=origin)
    return result.bytes, result.symbols


SOURCE = r'''
native_scope_init:
    push {r0-r3, lr}
    .word 0xE10F3000
    orr r2, r3, #0x80
    .word 0xE121F002
    ldr r0, =NS_SCOPE
    ldr r1, [r0]
    cmn r1, #1
    bne ns_init_out
    ldr r1, =NS_FAULT
    ldr r2, [r1]
    cmn r2, #1
    moveq r2, #0
    streq r2, [r1]
    mov r2, #0
    str r2, [r0]
ns_init_out:
    .word 0xE121F003
    pop {r0-r3, pc}

native_scope_take:
    push {r12, lr}
    ldr r12, =NS_SCOPE
    ldr r12, [r12]
    cmn r12, #1
    pop {r12, lr}
    beq NS_ACQUIRE
    push {r4, lr}
    bl NS_ACQUIRE
native_scope_acquired:
    pop {r4, lr}
    cmp r0, #0
    bne native_scope_refused
    b native_scope_enter

; The native FP stays fixed; the final native epilogue discards the context.
native_scope_enter:
    sub sp, sp, #96
    str r12, [sp, #64]
    mov r12, #1
    str r12, [sp, #80]
    b ns_enter_saved
native_scope_enter_borrowed:
    sub sp, sp, #96
    str r12, [sp, #64]
    mov r12, #0
    str r12, [sp, #80]
    b ns_enter_saved
native_scope_refused:
    sub sp, sp, #96
    str r12, [sp, #64]
    mov r12, #2
    str r12, [sp, #80]
ns_enter_saved:
    add r12, sp, #16
    stmia r12, {r0-r11}
    str lr, [r12, #52]
    .word 0xE10F0000
    str r0, [r12, #56]
    add r0, sp, #96
    str r0, [r12, #60]
    ldr r0, [r12, #64]
    cmp r0, #2
    beq native_scope_abort
    ldr r0, =NS_SCOPE
    str r12, [r0]
    ldr r0, =NS_FAULT
    ldr r0, [r0]
    cmp r0, #0
    bne native_scope_abort
    ldr r0, =NS_POLLS
    str r0, [r12, #76]
    mov r0, #0
    str r0, [r12, #68]
    str r0, [r12, #72]
    ldr r1, =NS_TIMER
    ldr r2, [r1, #0x18]
    ldr r3, =NS_HZ - 1
    cmp r2, r3
    blo ns_enter_done
    ldr r2, [r1, #0x20]
    and r2, r2, #0xc0
    cmp r2, #0x80
    bne ns_enter_done
    ldr r2, [r1, #0x24]
    tst r2, #1
    beq ns_enter_done
    mov r0, #1
    str r0, [r12, #68]
    ldr r0, [r1, #0x10]
    str r0, [r12, #72]
ns_enter_done:
    ldr r0, [r12, #56]
    .word 0xE128F000
    ldmia r12, {r0-r12, lr}
    bx lr

; Poll hooks preserve their native live registers around this scratch-only call.
native_scope_tick:
    ldr r12, =NS_SCOPE
    ldr r12, [r12]
    cmp r12, #0
    bxeq lr
    cmn r12, #1
    bxeq lr
    ldr r0, =NS_FAULT
    ldr r0, [r0]
    cmp r0, #0
    bne native_scope_abort
    ldr r0, [r12, #76]
    subs r0, r0, #1
    str r0, [r12, #76]
    beq native_scope_abort
    ldr r0, [r12, #68]
    cmp r0, #0
    bxeq lr
    ldr r0, =NS_TIMER
    ldr r1, [r0, #0x10]
    ldr r2, [r12, #72]
    cmp r1, r2
    sub r1, r1, r2
    ldrlo r2, [r0, #0x18]
    addlo r1, r1, r2
    addlo r1, r1, #1
    ldr r2, =NS_DEADLINE
    cmp r1, r2
    bhs native_scope_abort
    bx lr

; The caller still owns resource 1 and executes its original release next.
native_scope_leave:
    push {r0, r1}
    ldr r0, =NS_SCOPE
    mov r1, #0
    str r1, [r0]
    pop {r0, r1}
    bx lr

; Restore the native SP before its release and epilogue.
native_scope_close:
    ldr r12, =NS_SCOPE
    ldr r12, [r12]
    cmp r12, #0
    beq NS_RELEASE
    cmn r12, #1
    beq NS_RELEASE
    ldr r0, [r12, #44]
    cmp r0, r11
    bne native_scope_refused
    ldr r0, =NS_FAULT
    ldr r0, [r0]
    cmp r0, #0
    bne native_scope_abort
    ldr r1, [r12, #64]
    ldr r0, [r12, #60]
    ldr r2, =NS_SCOPE
    mov r3, #0
    str r3, [r2]
    mov sp, r0
    cmp r1, #1
    mov r0, #1
    beq NS_RELEASE
    mov r0, #0
    bx lr

; Skip the failed transaction's remaining instructions.
native_scope_abort:
    mov r4, r12
    .word 0xE10F0000
    orr r0, r0, #0x80
    .word 0xE121F000
    ldr r0, =NS_FAULT
    ldr r1, [r0]
    cmp r1, #0
    bne ns_fault_latched
    mov r1, #1
    str r1, [r0]
    ldr r0, =NS_GEN
    ldr r1, [r0]
    add r1, r1, #1
    str r1, [r0]
ns_fault_latched:
    ldr r0, =NS_MODE
    mov r1, #2
    str r1, [r0]
    ldr r0, =NS_SCOPE
    ldr r1, [r0]
    cmp r1, r4
    moveq r1, #0
    streq r1, [r0]
    sub sp, r4, #16
    ldr r11, [r4, #44]
    ldr r0, [r4, #64]
    cmp r0, #1
    bne ns_return
    ldr r0, [r4, #56]
    bic r0, r0, #0x80
    .word 0xE121F000
    mov r0, #1
    bl NS_RELEASE
ns_return:
    ldr r0, [r4, #56]
    ldr r1, [r4, #44]
    ldr r2, [r1]
    ldr r11, [r1, #-4]
    add r3, r1, #4
    add r12, r4, #16
    ldmia r12, {r4-r10}
    mov sp, r3
    .word 0xE121F000
    mov r0, #0
    bx r2
.pool
'''

DRIVER = r'''
native_scope_control:
    push {r0-r3, r12, lr}
    bl native_scope_tick
    pop {r0-r3, r12, lr}
    .word 0xE1D330B0
    bx lr

native_scope_gpio:
    push {r0-r3, r12, lr}
    bl native_scope_tick
    pop {r0-r3, r12, lr}
    b 0xC00145F0
.pool
native_scope_driver_end:
'''
