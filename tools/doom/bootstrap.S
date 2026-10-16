/* SPDX-License-Identifier: AGPL-3.0-or-later */
.syntax unified
.cpu arm926ej-s
.arm
.section .text.entry,"ax"
.global doom_boot
doom_boot:
    push {r4, lr}
    ldr r4, =0xC002A35C
    blx r4
    push {r0-r3}
    mrs r4, cpsr
    push {r4, r5}
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
    pop {r4, r5}
    msr cpsr_f, r4
    pop {r0-r3}
    pop {r4, pc}
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
    mcr p15, 0, r1, c7, c5, 0
    mcr p15, 0, r1, c7, c5, 4
    ldr r1, =0xC1000000
    msr cpsr_c, r3
    bx r1
.size doom_enter, .-doom_enter
