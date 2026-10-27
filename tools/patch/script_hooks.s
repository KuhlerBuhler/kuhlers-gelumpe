script_input_hook:
    push {r0-r12, lr}
    .word 0xE10FC000 ; mrs r12, cpsr
    push {r12, lr}
    ; The power key while the device still starts (no screen yet, or screen 0): the firmware takes it only after the start, which
    ; may wait a long time on a card that does not answer (device 18.10.: batteries out was the only way). The power hold
    ; (GPIO 7.11) is let go once the key has been held for 5 s, as Doom's error screen does. Let go earlier, the message is dropped:
    ; the firmware would switch off at the end of the start (device 19.10.: only a 5 s hold switches off). The key is read on its
    ; pin, as the firmware's power manager does (0xC00172D0). Not with EXIT held at power-on, not where it is not measured.
    ldrb r1, [r0, #0x0c]
    cmp r1, #6
    bne input_power_no
    ldrb r1, [r0, #0x0d]
    cmp r1, #1
    bne input_power_no
    ldr r1, =POWER_HOLD_MASK
    cmp r1, #0
    beq input_power_no
    ldr r1, =PANEL
    ldr r1, [r1]
    cmp r1, #0
    cmnne r1, #1
    beq input_power_screen
    ldr r1, [r1, #0x18]
    tst r1, #0x2000
    bne input_power_no
input_power_screen:
    ldr r1, =SCREEN_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    cmnne r1, #1
    beq input_power_off
    ldr r1, [r1, #0x2c]
    cmp r1, #0
    bne input_power_no
input_power_off:
    ldr r6, =POWER_HOLD_STEPS
input_power_held:
    ldr r1, =GPIO_IN67
    ldr r1, [r1]
    tst r1, #0x80000000
    bne input_drop
    mov r0, #POWER_HOLD_STEP_MS
    bl OS_WAIT
    subs r6, r6, #1
    bne input_power_held
    ldr r0, =0x01E26000
    mov r1, #0
    mov r2, #3
    ldr r3, =POWER_HOLD_MASK
    bl GPIO_WRITE
input_power_wait:
    b input_power_wait
input_power_no:
    bl migrate_input
    cmp r0, #0
    ldr r0, [sp, #8]
    bne input_drop
    ldr r4, =HOOK_RUNTIME
    ldr r1, [r4, #RT_ARMED]
    cmp r1, #1
    bne input_pass
script_input_guard_end:
    bl remap_input
    ldr r0, [sp, #8]
    bl shortcut_input
    cmp r0, #0
    ldr r0, [sp, #8]
    bne input_drop
    mov r8, #0
    ldr r1, =SCREEN_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    beq input_screen_ok
    cmn r1, #1
    beq input_screen_ok
    ldr r1, [r1, #0x2c]
    cmp r1, #MENU_SCREEN
    bne input_screen_ok
    ldr r1, =MENU_STATE
    ldr r2, [r1, #M_ON]
    cmp r2, #1
    bne input_pass
    ldr r2, [r1, #M_LEVEL]
    cmp r2, #M_LEVEL_BLECHY
    bne input_pass
    mov r8, #1
input_screen_ok:
    ldr r1, =PANEL
    ldr r1, [r1]
    cmp r1, #0
    beq input_pass
    cmn r1, #1
    beq input_pass
    ldr r1, [r1, #0x18]
    tst r1, #0x2000
    bne input_pass
    ldrb r1, [r0, #0x18]
    ldrb r2, [r0, #0x19]
    orrs r1, r1, r2
    bne input_pass
    mov r5, r0
    ldrb r6, [r5, #0x0c]
    ldrb r2, [r5, #0x0d]
    ldrb r3, [r5, #0x0e]
    ldrb r12, [r5, #0x0f]
    mov r7, #0
    cmp r8, #0
    beq input_dispatch
    cmp r6, #5
    beq input_dispatch
    cmp r6, #0
    bne input_pass
    cmp r2, #34
    bne input_pass
input_dispatch:
    cmp r6, #0
    beq input_button
    cmp r6, #1
    beq input_encoder
    cmp r6, #2
    beq input_knob
    cmp r6, #4
    beq input_pad
    cmp r6, #5
    beq input_touch
    b input_pass
input_button:
    cmp r2, #13
    bne input_button_go
    ldr r1, =APP_STATE
    ldr r1, [r1]
    cmp r1, #0
    beq input_button_go
    cmp r3, #0
    beq input_pass
    mov r0, r4
    bl script_app_close
    b input_pass
input_button_go:
    cmp r2, #34
    bne input_button_post
    ldr r7, =RT_TOUCH
    add r7, r4, r7
    cmp r3, #0
    movne r1, #1
    moveq r1, #0
    str r1, [r7]
    mov r7, #0
input_button_post:
    cmp r3, #0
    mov r1, #EV_BUTTON_RELEASE
    movne r1, #EV_BUTTON_PRESS
    mov r3, #0
    b input_post
input_encoder:
    mov r1, #EV_ENCODER
    mov r3, r12, lsl #24
    mov r3, r3, asr #24
    b input_post
input_knob:
    mov r1, #EV_KNOB
    orr r3, r12, r3, lsl #8
    cmp r2, #SCRIPT_KNOBS
    bhs input_post
    ldr r7, =RT_KNOBS
    add r7, r4, r7
    str r3, [r7, r2, lsl #2]
    mov r7, #0
    b input_post
input_pad:
    mov r1, #EV_PAD
    orr r7, r12, r3, lsl #8
    ldrb r3, [r5, #0x10]
    cmp r3, #0
    movne r3, #1
    b input_post
input_touch:
    mov r1, #EV_TOUCH
    orr r2, r3, r2, lsl #8
    ldrb r3, [r5, #0x10]
    orr r3, r3, r12, lsl #8
    ldr r7, =RT_TOUCH
    add r7, r4, r7
    ldr r0, [r7]
    cmp r0, #2
    mov r0, #2
    str r0, [r7]
    movne r7, #1
    moveq r7, #0
input_post:
    sub sp, sp, #16
    str r1, [sp]
    str r2, [sp, #4]
    str r3, [sp, #8]
    str r7, [sp, #12]
    mov r0, r4
    mov r1, sp
    bl script_ring_post
    add sp, sp, #16
    cmp r8, #0
    bne input_pass
    cmp r6, #0
    bne input_mask
    ldrb r1, [r5, #0x0d]
    cmp r1, #13
    beq input_pass
input_mask:
    ldr r1, [r4, #RT_CAPTURE_MASK]
    ldr r2, =APP_STATE
    ldr r2, [r2]
    cmp r2, #0
    beq input_mask_go
    cmp r6, #0
    bne input_mask_app
    ldrb r2, [r5, #0x0d]
    cmp r2, #0
    beq input_mask_go
    cmp r2, #1
    beq input_mask_go
    cmp r2, #2
    beq input_mask_go
input_mask_app:
    orr r1, r1, #1
input_mask_go:
    mov r2, #1
    mov r2, r2, lsl r6
    tst r1, r2
    beq input_pass
input_drop:
    pop {r12, lr}
    .word 0xE12FF00C ; msr cpsr_cxsf, r12
    pop {r0-r12, lr}
    bx lr
input_pass:
    pop {r12, lr}
    .word 0xE12FF00C ; msr cpsr_cxsf, r12
    pop {r0-r12, lr}
    ldrb r3, [r0, #0x18]
    ldr pc, =0xC0028380
script_input_pass_end:
script_input_literals:
.pool
script_input_literals_end:

; r0 runtime, r1 normalized event record -> r0 published.
script_ring_post:
    push {r4-r8, lr}
    mov r4, r0
    mov r5, r1
    .word 0xE10F6000 ; mrs r6, cpsr
    orr r7, r6, #0x80
    .word 0xE121F007 ; msr cpsr_c, r7
    ldr r7, [r4, #RT_RING_HEAD]
    ldr r8, [r4, #RT_RING_TAIL]
    cmp r7, r8
    beq ring_append
    ldr r0, [r5]
    cmp r0, #EV_KNOB
    bne ring_append
    sub r0, r7, #1
    and r0, r0, #SCRIPT_RING-1
    ldr r1, =RT_RING
    add r1, r4, r1
    add r1, r1, r0, lsl #4
    ldr r0, [r1]
    cmp r0, #EV_KNOB
    bne ring_append
    ldr r0, [r1, #4]
    ldr r2, [r5, #4]
    cmp r0, r2
    bne ring_append
    ldr r0, [r5, #8]
    str r0, [r1, #8]
    b ring_posted
ring_append:
    sub r0, r7, r8
    cmp r0, #SCRIPT_RING
    bhs ring_full
    and r0, r7, #SCRIPT_RING-1
    ldr r1, =RT_RING
    add r1, r4, r1
    add r1, r1, r0, lsl #4
    ldmia r5, {r0, r2, r3, r12}
    stmia r1, {r0, r2, r3, r12}
    add r7, r7, #1
    str r7, [r4, #RT_RING_HEAD]
ring_posted:
    mov r0, #1
    b ring_post_return
ring_full:
    ldr r0, [r4, #RT_OVERFLOW]
    add r0, r0, #1
    str r0, [r4, #RT_OVERFLOW]
    mov r0, #0
ring_post_return:
    .word 0xE12FF006 ; msr cpsr_cxsf, r6
    pop {r4-r8, pc}
.pool

; r0 runtime, r1 output record -> r0 copied; tail is released last.
script_ring_take:
    push {r4-r8, lr}
    mov r4, r0
    mov r5, r1
    .word 0xE10F6000 ; mrs r6, cpsr
    orr r7, r6, #0x80
    .word 0xE121F007 ; msr cpsr_c, r7
    ldr r7, [r4, #RT_RING_TAIL]
    ldr r8, [r4, #RT_RING_HEAD]
    cmp r7, r8
    beq ring_empty
    and r0, r7, #SCRIPT_RING-1
    ldr r1, =RT_RING
    add r1, r4, r1
    add r1, r1, r0, lsl #4
    ldmia r1, {r0, r2, r3, r12}
    stmia r5, {r0, r2, r3, r12}
    add r7, r7, #1
    str r7, [r4, #RT_RING_TAIL]
    mov r0, #1
    b ring_take_return
ring_empty:
    mov r0, #0
ring_take_return:
    .word 0xE12FF006 ; msr cpsr_cxsf, r6
    pop {r4-r8, pc}
.pool

script_frame_hook:
    push {r0-r12, lr}
    .word 0xE10FC000 ; mrs r12, cpsr
    push {r12, lr}
    ldr r0, =HOOK_RUNTIME
    bl script_frame_run
    pop {r12, lr}
    .word 0xE12FF00C ; msr cpsr_cxsf, r12
    pop {r0-r12, lr}
    ldr r0, =0xC0083710
    ldr r0, [r0]
    ldr pc, =0xC0083700
.pool
script_frame_wrapper_end:

script_frame_run:
    push {r4-r11, lr}
    sub sp, sp, #4
    mov r4, r0
    bl migrate_frame
    mov r7, #0
    mov r8, #ERR_OK
    ldr r1, [r4, #RT_ARMED]
    cmp r1, #1
    bne frame_return
script_frame_guard_end:
    ldr r1, =PANEL
    ldr r1, [r1]
    cmp r1, #0
    beq frame_return
    cmn r1, #1
    beq frame_return
    ldr r1, [r1, #0x18]
    tst r1, #0x2000
    bne frame_return
    ldr r1, [r4, #RT_FRAMES]
    add r1, r1, #1
    str r1, [r4, #RT_FRAMES]
    ldr r1, [r4, #RT_READY]
    cmp r1, #1
    beq frame_gate_open
    ldr r1, =SCREEN_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    beq frame_return
    cmn r1, #1
    beq frame_return
    ldr r1, [r1, #0x2c]
    cmp r1, #1
    bne frame_return
    str r1, [r4, #RT_READY]
frame_gate_open:
    bl blechy_follow
    bl shortcut_tick
    bl remote_tick
    ldr r1, =APP_STATE
    ldr r1, [r1]
    cmp r1, #0
    beq frame_app_ok
    ldr r2, [r1, #SCRIPT_ENTRY_BLOB]
    ldr r3, =HOOK_POOL
    cmp r2, r3
    blo frame_app_ok
    ldr r1, =SCREEN_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    beq frame_app_close
    cmn r1, #1
    beq frame_app_close
    ldr r1, [r1, #0x2c]
    cmp r1, #1
    beq frame_app_main
    ldr r1, =APP_STATE
    ldr r2, [r1, #SCRIPT_APPS_GRACE]
    cmp r2, #0
    beq frame_app_close
    sub r2, r2, #1
    str r2, [r1, #SCRIPT_APPS_GRACE]
    b frame_app_ok
frame_app_main:
    ldr r1, =APP_STATE
    mov r2, #0
    str r2, [r1, #SCRIPT_APPS_GRACE]
    b frame_app_ok
frame_app_close:
    bl script_app_close
frame_app_ok:
    mov r1, #0
    str r1, [r4, #RT_PAUSED]
    mov r1, #1
    str r1, [r4, #RT_FRAME_ACTIVE]
    ldr r1, =SCRIPT_TIMER_ADDRESS
    ldr r1, [r1]
    str r1, [r4, #RT_FRAME_START]
    mov r0, r4
    bl script_led_begin_frame
    mov r0, r4
    bl script_events_poll
    ldr r6, [r4, #RT_CURSOR_PHASE]
    cmp r6, #SCRIPT_PHASE_IDLE
    bne frame_loop
    mov r6, #SCRIPT_PHASE_READY
    str r6, [r4, #RT_CURSOR_PHASE]
    ldr r5, [r4, #RT_HEAD]
    str r5, [r4, #RT_CURSOR_ENTRY]
frame_loop:
    ldr r5, [r4, #RT_CURSOR_ENTRY]
    cmp r5, #0
    beq frame_phase_done
    ldr r1, [r5, #SCRIPT_ENTRY_STATE]
    cmp r1, #SCRIPT_STATE_ARMED
    beq frame_armed
    cmp r1, #SCRIPT_STATE_DISABLED
    bne frame_next_entry
    cmp r6, #SCRIPT_PHASE_READY
    bne frame_next_entry
    ldr r1, [r5, #SCRIPT_ENTRY_READY_SENT]
    cmp r1, #0
    bne frame_next_entry
    mov r1, #1
    str r1, [r5, #SCRIPT_ENTRY_READY_SENT]
    mov r0, r4
    mov r1, r5
    bl script_display_fault
    b frame_next_entry
frame_armed:
    ldr r1, [r5, #SCRIPT_ENTRY_READY_SENT]
    cmp r6, #SCRIPT_PHASE_READY
    beq frame_ready_candidate
    cmp r1, #1
    bne frame_next_entry
    ldr r2, [r4, #RT_CURSOR_EVENT]
    cmp r2, #EV_OPEN
    cmpne r2, #EV_CLOSE
    beq frame_app_event
    cmp r2, #EV_FRAME
    bne frame_candidate
    mov r0, r5
    bl script_app_closed
    cmp r0, #0
    bne frame_next_entry
    b frame_candidate
frame_app_event:
    ldr r1, [r4, #RT_CURSOR_ARGS]
    cmp r1, r5
    bne frame_next_entry
    b frame_candidate
frame_ready_candidate:
    cmp r1, #0
    bne frame_next_entry
frame_candidate:
    ldr r1, =SCRIPT_TIMER_ADDRESS
    ldr r1, [r1]
    ldr r2, [r4, #RT_FRAME_START]
    cmp r1, r2
    sub r1, r1, r2
    ldrlo r2, =SCRIPT_TIMER_PERIOD
    addlo r1, r1, r2
    ldr r2, [r4, #RT_MAXTICKS]
    cmp r1, r2
    bhi frame_pause
    cmp r6, #SCRIPT_PHASE_READY
    bne frame_dispatch
    mov r1, #1
    str r1, [r5, #SCRIPT_ENTRY_READY_SENT]
    mov r1, #EV_READY
    str r1, [r4, #RT_CURSOR_EVENT]
    mov r1, #0
    str r1, [r4, #RT_CURSOR_ARGS]
    str r1, [r4, #RT_CURSOR_ARGS+4]
    str r1, [r4, #RT_CURSOR_ARGS+8]
frame_dispatch:
    ldr r1, [r5, #SCRIPT_ENTRY_NEXT]
    str r1, [r4, #RT_CURSOR_ENTRY]
    mov r0, r4
    mov r1, r5
    ldr r2, [r4, #RT_CURSOR_EVENT]
    add r3, r4, #RT_CURSOR_ARGS
    ldr r12, =VM_SCRIPT_RUN_EVENT
    blx r12
    cmp r8, #ERR_OK
    moveq r8, r0
    cmp r0, #ERR_OK
    beq frame_dispatched
    mov r0, r4
    mov r1, r5
    bl script_display_fault
frame_dispatched:
    ldr r1, [r4, #RT_HANDLED]
    add r7, r7, r1
    ldr r1, =SCRIPT_TIMER_ADDRESS
    ldr r1, [r1]
    ldr r2, [r4, #RT_FRAME_START]
    cmp r1, r2
    sub r1, r1, r2
    ldrlo r2, =SCRIPT_TIMER_PERIOD
    addlo r1, r1, r2
    ldr r2, [r4, #RT_MAXTICKS]
    cmp r1, r2
    bhi frame_pause
    b frame_loop
frame_next_entry:
    ldr r5, [r5, #SCRIPT_ENTRY_NEXT]
    str r5, [r4, #RT_CURSOR_ENTRY]
    b frame_loop
frame_phase_done:
    cmp r6, #SCRIPT_PHASE_READY
    beq frame_start_queue
    cmp r6, #SCRIPT_PHASE_QUEUED
    beq frame_queue
    mov r6, #SCRIPT_PHASE_IDLE
    str r6, [r4, #RT_CURSOR_PHASE]
    b frame_finish
frame_start_queue:
    mov r6, #SCRIPT_PHASE_QUEUED
    str r6, [r4, #RT_CURSOR_PHASE]
    ldr r1, [r4, #RT_RING_HEAD]
    str r1, [r4, #RT_CURSOR_RING_END]
frame_queue:
    ldr r1, [r4, #RT_RING_TAIL]
    ldr r2, [r4, #RT_CURSOR_RING_END]
    cmp r1, r2
    beq frame_start_frame
    mov r0, r4
    add r1, r4, #RT_CURSOR_EVENT
    bl script_ring_take
    ldr r5, [r4, #RT_HEAD]
    str r5, [r4, #RT_CURSOR_ENTRY]
    b frame_loop
frame_start_frame:
    mov r6, #SCRIPT_PHASE_FRAME
    str r6, [r4, #RT_CURSOR_PHASE]
    mov r1, #EV_FRAME
    str r1, [r4, #RT_CURSOR_EVENT]
    mov r1, #0
    str r1, [r4, #RT_CURSOR_ARGS]
    str r1, [r4, #RT_CURSOR_ARGS+4]
    str r1, [r4, #RT_CURSOR_ARGS+8]
    ldr r5, [r4, #RT_HEAD]
    str r5, [r4, #RT_CURSOR_ENTRY]
    b frame_loop
frame_pause:
    mov r1, #1
    str r1, [r4, #RT_PAUSED]
frame_finish:
    mov r0, r4
    bl script_clock_update
    mov r0, r4
    bl script_led_hold_guard
    mov r0, r4
    bl script_display_blit
    bl display_calibrate
    mov r0, r4
    bl script_store_flush
    bl script_seq_flush
    ldr r1, [r4, #RT_PAUSED]
    cmp r1, #0
    bne frame_no_led_flush
    mov r0, r4
    bl script_led_flush
frame_no_led_flush:
    mov r1, #0
    str r1, [r4, #RT_FRAME_ACTIVE]
frame_return:
    mov r0, r7
    mov r1, r8
    add sp, sp, #4
    pop {r4-r11, pc}
.pool
script_frame_return_end:
