; CsTask posts view requests; only UiTask switches screens.
nr_input:
    push {r4-r6, lr}
    mov r4, r0
    ldrb r1, [r4, #12]
    ldrb r2, [r4, #13]
    orrs r1, r1, r2
    bne nr_input_pass
    bl nr_init
    mov r5, r0
    ldrb r0, [r4, #14]
    cmp r0, #0
    bne nr_input_press
    ldr r0, [r5, #NR_HELD]
    mov r1, #0
    str r1, [r5, #NR_HELD]
    pop {r4-r6, pc}
nr_input_press:
    ldr r0, [r5, #NR_HELD]
    cmp r0, #0
    bne nr_input_take
    bl nr_enabled
    cmp r0, #0
    beq nr_input_pass
    ldr r0, =MENU_STATE
    ldrb r0, [r0, #KP_SHIFT]
    cmp r0, #1
    bne nr_input_record
    mov r0, #1
    str r0, [r5, #NR_VIEW_REQUEST]
    b nr_input_take
nr_input_record:
    ldr r0, [r5, #NR_SETUP]
    cmp r0, #1
    bne nr_input_pass
    mov r0, #2
    str r0, [r5, #NR_VIEW_REQUEST]
nr_input_take:
    mov r0, #1
    str r0, [r5, #NR_HELD]
    pop {r4-r6, pc}
nr_input_pass:
    mov r0, #0
    pop {r4-r6, pc}
.pool

nr_view_frame:
    push {r4-r8, lr}
    bl nr_init
    mov r4, r0
    ldr r5, =MENU_STATE
    .word 0xE10F6000                 ; mrs r6, cpsr
    orr r0, r6, #0xC0
    .word 0xE121F000                 ; msr cpsr_c, r0
    ldr r8, [r4, #NR_VIEW_REQUEST]
    mov r0, #0
    str r0, [r4, #NR_VIEW_REQUEST]
    .word 0xE121F006                 ; msr cpsr_c, r6
    cmp r8, #1
    bne nr_view_screen
    bl nr_enabled
    cmp r0, #0
    beq nr_view_screen
    mov r0, #M_LEVEL_RECORD
    str r0, [r5, #M_LEVEL]
    mov r0, #0
    str r0, [r5, #M_PAGE]
    str r0, [r5, #M_ENTER]
    str r0, [r5, #M_STATUS]
    mov r0, #1
    str r0, [r4, #NR_SELECTED]
    mov r0, #MENU_SCREEN
    mov r1, #0
    ldr r12, =SWITCH_SCREEN
    blx r12
nr_view_screen:
    mov r6, #0
    ldr r0, =SCREEN_MANAGER
    ldr r0, [r0]
    cmp r0, #0
    cmnne r0, #1
    beq nr_view_publish
    mov r7, r0
    ldr r0, [r0, #0x2C]
    cmp r0, #MENU_SCREEN
    bne nr_view_publish
    ldr r0, [r5, #M_LEVEL]
    cmp r0, #M_LEVEL_RECORD
    moveq r6, #1
nr_view_publish:
    cmp r6, #1
    moveq r0, #1
    movne r0, #0
    str r0, [r4, #NR_SETUP]
    cmp r0, #0
    beq nr_view_done
    cmp r8, #2
    bne nr_view_draw
    bl nr_busy
    eor r0, r0, #1
    bl nr_post
nr_view_draw:
    ldr r0, [r7, #0x20]
    cmp r0, #0
    blne menu_show
nr_view_done:
    pop {r4-r8, pc}
.pool
nr_source_text: .asciz "RECORD"
.align 4
nr_blue_ui_end:
