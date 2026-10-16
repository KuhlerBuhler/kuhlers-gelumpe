script_card_hook:
    push {r0-r12, lr}
    .word 0xE10FC000
    push {r12, lr}
    ldr r0, =PANEL
    ldr r0, [r0]
    cmp r0, #0
    beq synth_start_native
    cmn r0, #1
    beq synth_start_native
    ldr r1, [r0, #0x18]
    tst r1, #KILL_MASK
    bne synth_start_native
    ldrb r1, [r0, #0x22]
    cmp r1, #0
    bne synth_start_native
    ldrb r1, [r0, #0x20]
    cmp r1, #0
    bne synth_start_native
    bl menu_arm_load
    ldr r0, =HOOK_RUNTIME
    bl blechy_boot
    ldr r0, =HOOK_RUNTIME
    bl script_card_load
    bl menu_recount
synth_start_native:
    pop {r12, lr}
    .word 0xE12FF00C
    pop {r0-r12, lr}
    ldrb r3, [r4, #4]
    ldr pc, =0xC0028174
.pool
script_card_wrapper_end:
