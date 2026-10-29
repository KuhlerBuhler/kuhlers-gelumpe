; Sequencer and transport events, found by comparing the firmware's state words from one frame to the next,
; and the save event, posted by a hook on the firmware's settings writer. Both feed the same ring as the panel.

; r0 runtime, r1 event, r2 first argument, r3 second argument. Preserves r4-r11.
events_post:
    push {lr}
    sub sp, sp, #16
    str r1, [sp]
    str r2, [sp, #4]
    str r3, [sp, #8]
    mov r1, #0
    str r1, [sp, #12]
    mov r1, sp
    bl script_ring_post
    add sp, sp, #16
    pop {pc}

; r0 runtime. Called once per frame before the ready and queue phases.
script_events_poll:
    push {r4-r11, lr}
    mov r4, r0
    ldr r0, =HW_TRANSPORT
    ldr r5, [r0]
    ldr r0, =HW_TEMPO
    ldr r6, [r0]
    ldr r0, =HW_PATTERN
    ldr r7, [r0]
    ldr r0, =HW_PART
    ldr r8, [r0]
    ldr r0, =HW_STEP
    ldr r9, [r0]
    ldr r1, =HW_MUTE
    mov r10, #0
    mov r0, #0
events_mute_read:
    mov r2, r0, lsl #9
    add r2, r2, r0, lsl #8
    add r2, r2, r0, lsl #5
    add r2, r2, r0, lsl #4
    ldrb r2, [r1, r2]
    cmp r2, #0
    movne r2, #1
    orr r10, r10, r2, lsl r0
    add r0, r0, #1
    cmp r0, #16
    blo events_mute_read
    ldr r0, [r4, #SCRIPT_CONTROL_SEQ_INIT]
    cmp r0, #0
    bne events_compare
    mov r0, #1
    str r0, [r4, #SCRIPT_CONTROL_SEQ_INIT]
    b events_store
events_compare:
    ldr r11, [r4, #SCRIPT_CONTROL_SEQ_TRANSPORT]
    cmp r5, r11
    beq events_tempo
    cmp r5, #1
    moveq r1, #EV_PLAY
    beq events_transport_post
    cmp r5, #0
    cmpne r5, #2
    moveq r1, #EV_STOP
    beq events_transport_post
    sub r2, r11, #3
    cmp r2, #1
    bls events_tempo
    mov r1, #EV_REC
events_transport_post:
    mov r0, r4
    mov r2, #0
    mov r3, #0
    bl events_post
events_tempo:
    ldr r0, [r4, #SCRIPT_CONTROL_SEQ_TEMPO]
    cmp r6, r0
    beq events_pattern
    mov r0, r4
    mov r1, #EV_TEMPO
    mov r2, r6
    mov r3, #0
    bl events_post
events_pattern:
    ldr r0, [r4, #SCRIPT_CONTROL_SEQ_PATTERN]
    cmp r7, r0
    beq events_part
    mov r0, r4
    mov r1, #EV_PATTERN_CHANGE
    mov r2, r7
    mov r3, #0
    bl events_post
events_part:
    ldr r0, [r4, #SCRIPT_CONTROL_SEQ_PART]
    cmp r8, r0
    beq events_mute
    mov r0, r4
    mov r1, #EV_PART_CHANGE
    mov r2, r8
    mov r3, #0
    bl events_post
events_mute:
    ldr r11, [r4, #SCRIPT_CONTROL_SEQ_MUTES]
    eors r11, r11, r10
    beq events_step
    push {r8}
    mov r8, #0
events_mute_bit:
    mov r2, #1
    tst r11, r2, lsl r8
    beq events_mute_next
    mov r0, r4
    mov r1, #EV_MUTE
    mov r2, r8
    mov r3, r10, lsr r8
    and r3, r3, #1
    bl events_post
events_mute_next:
    add r8, r8, #1
    cmp r8, #16
    blo events_mute_bit
    pop {r8}
events_step:
    ldr r0, [r4, #SCRIPT_CONTROL_SEQ_STEP]
    cmp r9, r0
    beq events_store
    mov r0, r4
    mov r1, #EV_STEP
    mov r2, r9
    mov r3, #0
    bl events_post
    ; korg.afterSteps counts the steps while the sequencer runs; the jump back to 0 at STOP is no step
    cmp r5, #0
    cmpne r5, #2
    beq events_step_counted
    mov r0, r4
    mov r1, #TIMER_KIND_STEPS
    bl script_timers_poll
events_step_counted:
    tst r9, #3
    bne events_store
    mov r0, r4
    mov r1, #EV_BEAT
    mov r2, #0
    mov r3, #0
    bl events_post
events_store:
    str r5, [r4, #SCRIPT_CONTROL_SEQ_TRANSPORT]
    str r6, [r4, #SCRIPT_CONTROL_SEQ_TEMPO]
    str r7, [r4, #SCRIPT_CONTROL_SEQ_PATTERN]
    str r8, [r4, #SCRIPT_CONTROL_SEQ_PART]
    str r9, [r4, #SCRIPT_CONTROL_SEQ_STEP]
    str r10, [r4, #SCRIPT_CONTROL_SEQ_MUTES]
    pop {r4-r11, pc}
.pool

; Entered by a branch from the first word of the firmware's settings writer 0xC004C1B4 (push {r4, r5, r6, lr}),
; which runs here after the event is posted, then continues at the second word.
script_save_hook:
    push {r0-r3, r12, lr}
    ldr r0, =HOOK_RUNTIME
    ldr r1, [r0, #RT_ARMED]
    cmp r1, #1
    bne save_pass
    ldr r1, =PANEL
    ldr r1, [r1]
    cmp r1, #0
    beq save_pass
    cmn r1, #1
    beq save_pass
    ldr r1, [r1, #0x18]
    tst r1, #0x2000
    bne save_pass
    mov r1, #EV_SAVE
    mov r2, #0
    mov r3, #0
    bl events_post
save_pass:
    pop {r0-r3, r12, lr}
    push {r4, r5, r6, lr}
    ldr pc, =0xC004C1B8
.pool
script_save_hook_end:
