/* SPDX-License-Identifier: AGPL-3.0-or-later */
.syntax unified
.cpu arm926ej-s
.arm
.section .text.entry,"ax"
.global doom_boot
@ Called from 0xC002AE64 after the sample-file query, replacing mov r4, r0.
@ Does that instruction and returns with every other register and the flags as they were, unless exactly SHIFT + TAP is held.
doom_boot:
    mov r4, r0
    push {r0-r3, r12, lr}
    mrs r12, cpsr
    push {r4, r12}               @ eight-byte stack alignment at the C entry
    ldr r0, =0xC033E6F8
    ldr r0, [r0]
    ldr r1, [r0, #0x18]
    ldr r2, =0x408
    cmp r1, r2
    bne normal
    ldr r1, [r0, #0x1c]
    cmp r1, #0
    bne normal
    ldrb r1, [r0, #0x20]
    cmp r1, #0
    bne normal
    ldrb r1, [r0, #0x22]
    cmp r1, #0
    bne normal
    b doom_load
normal:
    pop {r4, r12}
    msr cpsr_f, r12
    pop {r0-r3, r12, pc}
.global doom_enter
.type doom_enter,%function
doom_enter:
    mrs r3, cpsr
    orr r1, r3, #0x80
    msr cpsr_c, r1
    ldr r1, =0xC00A37A8
    mov r2, #0x10000
    str r2, [r1, #16]
    ldr r2, =0xC17F0000
    str r2, [r1, #20]
    ldr sp, =0xC1800000
    ldr r1, =0xC1000000
    ldr r2, =0xC1800000
clean:
    mcr p15, 0, r1, c7, c10, 1
    add r1, r1, #32
    cmp r1, r2
    blo clean
    mov r1, #0
    mcr p15, 0, r1, c7, c10, 4
    mcr p15, 0, r1, c7, c5, 0       @ no c7, c5, 4 here: the ARM926 has no such operation, on the device it hangs (22.10.)
    ldr r1, =0xC1000000
    msr cpsr_c, r3
    bx r1
.size doom_enter, .-doom_enter
