; Timers of the plugin API (data/script/contract.mjs, TIMERS): korg.after, korg.every, korg.afterSteps and korg.cancel take a
; slot of the calling script's entry; the frame hook posts a due one as the internal event timer for that script only, with the
; callback number in the first value and the script entry in the third, as the app events carry theirs.
.align 4
; korg.after(ms, callback) -> the number of the timer, -1 when all slots are taken
script_timer_after_glue:
    push {r4-r6, lr}
    mov r5, r1
    mov r6, #0
timer_ms_take:
    mov r4, r0
    ldr r0, =HOOK_RUNTIME
    bl script_clock_update
    add r2, r0, r4
    mov r1, #TIMER_KIND_MS
    b timer_take
; korg.every(ms, callback): as korg.after, then again every ms
script_timer_every_glue:
    push {r4-r6, lr}
    mov r5, r1
    mov r6, r0
    b timer_ms_take
; korg.afterSteps(steps, callback): due counts the steps still to come
script_timer_after_steps_glue:
    push {r4-r6, lr}
    mov r5, r1
    mov r6, #0
    mov r2, r0
    mov r1, #TIMER_KIND_STEPS
; r1 kind, r2 due, r5 callback, r6 period -> r0 slot plus 8 times its new generation, or -1
timer_take:
    ldr r3, =HOOK_RUNTIME
    ldr r3, [r3, #RT_ENTRY]
    add r3, r3, #SCRIPT_ENTRY_TIMERS
    mov r0, #0
timer_find:
    ldrb r12, [r3, #TIMER_KIND]
    cmp r12, #TIMER_KIND_FREE
    beq timer_found
    add r3, r3, #TIMERS_RECORD_SIZE
    add r0, r0, #1
    cmp r0, #TIMERS_SLOTS
    blo timer_find
    mvn r0, #0
    mov r1, #ERR_OK
    pop {r4-r6, pc}
timer_found:
    str r2, [r3, #TIMER_DUE]
    str r6, [r3, #TIMER_PERIOD]
    strb r5, [r3, #TIMER_CALLBACK]
    ldrb r12, [r3, #TIMER_GENERATION]
    add r12, r12, #1
    and r12, r12, #31
    strb r12, [r3, #TIMER_GENERATION]
    strb r1, [r3, #TIMER_KIND]
    add r0, r0, r12, lsl #3
    mov r1, #ERR_OK
    pop {r4-r6, pc}

; korg.cancel(timer): frees the slot when its generation is still the one of that number; -1 does nothing
script_timer_cancel_glue:
    cmp r0, #0
    blt timer_cancel_done
    and r1, r0, #TIMERS_SLOTS-1
    mov r2, r0, lsr #3
    ldr r3, =HOOK_RUNTIME
    ldr r3, [r3, #RT_ENTRY]
    add r3, r3, #SCRIPT_ENTRY_TIMERS
    add r1, r1, r1, lsl #1
    add r3, r3, r1, lsl #2
    ldrb r12, [r3, #TIMER_KIND]
    cmp r12, #TIMER_KIND_FREE
    beq timer_cancel_done
    ldrb r12, [r3, #TIMER_GENERATION]
    cmp r12, r2
    moveq r12, #TIMER_KIND_FREE
    strbeq r12, [r3, #TIMER_KIND]
timer_cancel_done:
    mov r0, #0
    mov r1, #ERR_OK
    bx lr
.pool

; r0 runtime, r1 kind. Called by the frame hook (clock timers) and by the step event (step timers). Walks the armed scripts:
; a clock timer is due once the clock has reached it, a step timer counts one step down and is due at 0. A due timer goes into
; the ring; a full ring leaves it due (a step timer at 1) for the next call. Preserves r4 to r11.
script_timers_poll:
    push {r4-r10, lr}
    mov r4, r0
    mov r9, r1
    cmp r9, #TIMER_KIND_MS
    bne timers_entries
    bl script_clock_update
    mov r10, r0
timers_entries:
    ldr r5, [r4, #RT_HEAD]
timers_entry:
    cmp r5, #0
    beq timers_done
    ldr r0, [r5, #SCRIPT_ENTRY_STATE]
    cmp r0, #SCRIPT_STATE_ARMED
    bne timers_next_entry
    add r6, r5, #SCRIPT_ENTRY_TIMERS
    mov r7, #0
timers_slot:
    ldrb r0, [r6, #TIMER_KIND]
    cmp r0, r9
    bne timers_next_slot
    ldr r8, [r6, #TIMER_DUE]
    cmp r9, #TIMER_KIND_MS
    beq timers_clock
    subs r8, r8, #1
    str r8, [r6, #TIMER_DUE]
    bgt timers_next_slot
    bl timers_post
    cmp r0, #0
    moveq r0, #1
    streq r0, [r6, #TIMER_DUE]
    movne r0, #TIMER_KIND_FREE
    strbne r0, [r6, #TIMER_KIND]
    b timers_next_slot
timers_clock:
    subs r0, r10, r8
    bmi timers_next_slot
    bl timers_post
    cmp r0, #0
    beq timers_done
    ldr r0, [r6, #TIMER_PERIOD]
    cmp r0, #0
    moveq r0, #TIMER_KIND_FREE
    strbeq r0, [r6, #TIMER_KIND]
    beq timers_next_slot
    add r8, r8, r0
    subs r1, r10, r8
    addpl r8, r10, r0
    str r8, [r6, #TIMER_DUE]
timers_next_slot:
    add r6, r6, #TIMERS_RECORD_SIZE
    add r7, r7, #1
    cmp r7, #TIMERS_SLOTS
    blo timers_slot
timers_next_entry:
    ldr r5, [r5, #SCRIPT_ENTRY_NEXT]
    b timers_entry
timers_done:
    pop {r4-r10, pc}

; r4 runtime, r5 script entry, r6 timer -> r0 posted
timers_post:
    push {lr}
    sub sp, sp, #16
    mov r0, #EV_TIMER
    str r0, [sp]
    ldrb r0, [r6, #TIMER_CALLBACK]
    str r0, [sp, #4]
    mov r0, #0
    str r0, [sp, #8]
    str r5, [sp, #12]
    mov r0, r4
    mov r1, sp
    bl script_ring_post
    add sp, sp, #16
    pop {pc}

; The OS tick count when script_clock_update last ran: whole Timer3 periods it did not see show up there.
clock_ticks_last:
    .word 0
