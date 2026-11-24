; CsTask posts view requests; only UiTask switches screens. Keys of class 0: REC 0, PLAY 2; NR_HELD holds the key number + 1
; of a swallowed press. SHIFT+REC opens the RECORD view (request 1). In the view PLAY starts a take bound to the transport,
; leaves the view (request 4) and goes on to the firmware, which plays the pattern; with a take running PLAY only leaves.
; REC in the view stops a running take (2) and, idle, leaves the view (4), as REC leaves the Sampler's setup.
nr_input:
    push {r4-r7, lr}
    mov r4, r0
    ldrb r1, [r4, #12]
    cmp r1, #0
    bne nr_input_pass
    ldrb r7, [r4, #13]
    cmp r7, #0
    cmpne r7, #2
    bne nr_input_pass
    bl nr_init
    mov r5, r0
    ldrb r0, [r4, #14]
    cmp r0, #0
    bne nr_input_press
    ldr r0, [r5, #NR_HELD]
    sub r0, r0, #1
    cmp r0, r7
    movne r0, #0
    bne nr_input_return
    mov r0, #0
    str r0, [r5, #NR_HELD]
    mov r0, #1
    b nr_input_return
nr_input_press:
    ldr r0, [r5, #NR_HELD]
    sub r0, r0, #1
    cmp r0, r7
    beq nr_input_take
    bl nr_enabled
    cmp r0, #0
    beq nr_input_pass
    cmp r7, #2
    beq nr_input_play
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
    bl nr_busy
    cmp r0, #0
    moveq r0, #4
    movne r0, #2
    str r0, [r5, #NR_VIEW_REQUEST]
    b nr_input_take
nr_input_play:
    ldr r0, [r5, #NR_SETUP]
    cmp r0, #1
    bne nr_input_pass
    bl nr_busy
    cmp r0, #0
    bne nr_input_leave
    mov r0, #1                       ; post here, not in UiTask: the firmware's PLAY may switch the screen first
    bl nr_post
    cmp r0, #0
    bne nr_input_take                ; refused (no card): the view stays and shows why
    mov r0, #NR_PLAY_WAIT
    strb r0, [r5, #NR_PLAY_BOUND]
nr_input_leave:
    mov r0, #4
    str r0, [r5, #NR_VIEW_REQUEST]
    b nr_input_pass
nr_input_take:
    add r0, r7, #1
    str r0, [r5, #NR_HELD]
    mov r0, #1
    b nr_input_return
nr_input_pass:
    mov r0, #0
nr_input_return:
    pop {r4-r7, pc}
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
    bne nr_view_leave
    bl nr_busy
    cmp r0, #0
    movne r0, #0
    blne nr_post
    b nr_view_draw
nr_view_leave:
    cmp r8, #4
    bne nr_view_draw
    mov r0, #0
    str r0, [r4, #NR_SETUP]
    mov r0, #1                       ; the screen EXIT goes to from the RECORD view (script_menu.s:menu_slot_exit)
    mov r1, #0
    ldr r12, =SWITCH_SCREEN
    blx r12
    b nr_view_done
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
