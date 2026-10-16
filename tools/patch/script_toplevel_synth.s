menu_toplevel:
    ldr r3, =MENU_STATE
    ldr r3, [r3, #M_ON]
    cmp r3, #1
    bne synth_toplevel_native
    cmp r5, #MENU_SCREEN
    streq r5, [r4, #0x50]
synth_toplevel_native:
    ldr r3, [r4, #0x1c]
    ldr pc, =0xC0061DE0
.pool
