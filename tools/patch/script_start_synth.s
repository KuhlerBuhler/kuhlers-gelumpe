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

; the blue Electribe draws its start image before the flash can be read (docs/messungen/2026-10-29-hintergrundlicht-beim-start.md):
; no colour at power-on, the light calls and the settings go their way (the labels around are the start phase span)
boot_light_hook:
bl_red_boot:
    b bl_red_go
bl_green_boot:
    b bl_green_go
bl_blue_boot:
    b bl_blue_go
boot_light_save:
    bx lr
boot_light_settle:
    bx lr
boot_light_end:
