; korg.seq: plugins write steps into the pattern in RAM, the one that plays, the way the dice patch does (tools/patch/dice.py,
; docs/messungen/2026-10-16-wuerfeln.md): plain byte stores into a step's record, which the sequencer plays from the next pass.
; The pattern counts as changed until WRITE, because it then differs from its place in the bank. The record layout is
; PATTERN_STEPS of data/script/contract.mjs. Arguments are range checked by the VM; part and step are checked again here,
; they make the address.
.equ SEQ_NOTIFY, 0xC0070688     ; (observers, message): tells the observers of the sequencer's model (the pad LEDs) what changed
.equ SEQ_OBSERVERS, 4           ; the model's observer list
.equ SEQ_SECTION, 0x344         ; the model's selected bar section, 0 to 3: the pads show its 16 steps
.equ SEQ_MSG_SECTION, 0x0B      ; the message of a section change; the pad LEDs draw again from the pattern on it
.equ SQ_AT, 0xFD8               ; one word in the card loader's work area, behind the record of korg.remapKey (RP_AT) and before the
.equ SQ_SIZE, 4                 ; state of fx_card.s: its own address while steps wait for the pads to draw them (FF at power-on is not)

; r0 part, r1 step, r2 note (-1 for none), r3 velocity. A note with a velocity above 0 turns the step on with that note in the
; first note place (the other three cleared) and the trigger on; note -1 or velocity 0 turns it off. The gate stays.
script_seq_set_step_glue:
    cmp r0, #16
    cmplo r1, #SCRIPT_STEP_COUNT
    bhs hw_bad_arg
    push {lr}
    bl seq_record
    cmp r2, #0
    cmpge r3, #1
    movlt r1, #0
    strblt r1, [r12, #SCRIPT_STEP_ON]
    blt seq_done
    strb r3, [r12, #SCRIPT_STEP_VELOCITY]
    add r2, r2, #1
    strb r2, [r12, #SCRIPT_STEP_NOTES]
    mov r1, #0
    strb r1, [r12, #SCRIPT_STEP_NOTES+1]
    strb r1, [r12, #SCRIPT_STEP_NOTES+2]
    strb r1, [r12, #SCRIPT_STEP_NOTES+3]
    mov r1, #1
    strb r1, [r12, #SCRIPT_STEP_TRIGGER]
    strb r1, [r12, #SCRIPT_STEP_ON]
seq_done:
    mov r0, #0
    mov r1, #ERR_OK
    pop {pc}

; r0 part, r1 step, r2 gate 0 to 127 (127 ties into the next note).
script_seq_set_gate_glue:
    cmp r0, #16
    cmplo r1, #SCRIPT_STEP_COUNT
    bhs hw_bad_arg
    push {lr}
    bl seq_record
    strb r2, [r12, #SCRIPT_STEP_GATE]
    b seq_done

; r0 part: every step of it off, nothing else of the steps changes.
script_seq_clear_part_glue:
    cmp r0, #16
    bhs hw_bad_arg
    push {lr}
    mov r1, #0
    bl seq_record
    mov r1, #SCRIPT_STEP_COUNT
    mov r2, #0
seq_clear_loop:
    strb r2, [r12, #SCRIPT_STEP_ON]
    add r12, r12, #SCRIPT_STEP_STRIDE
    subs r1, r1, #1
    bne seq_clear_loop
    b seq_done

; r0 part, r1 step -> r12 the step's record. Marks the frame as one that wrote steps (SQ_AT holds its own address). Clobbers r1.
seq_record:
    ldr r12, =SCRIPT_PART_STRIDE
    mul r12, r0, r12
    add r12, r12, r1, lsl #3
    add r12, r12, r1, lsl #2
    ldr r1, =HW_PATTERN_OBJECT+4+SCRIPT_PART_BASE+SCRIPT_STEP_BASE
    add r12, r12, r1
    ldr r1, =HOOK_CARD+SQ_AT
    str r1, [r1]
    bx lr

; At the end of a frame in which a plugin wrote steps, once the main screen is up: the firmware's own message for the section
; that is shown already, so the pads draw the steps again (one message a frame, however many steps were written).
; Clobbers r0 to r3 and r12.
script_seq_flush:
    ldr r0, =HOOK_CARD+SQ_AT
    ldr r1, [r0]
    cmp r1, r0
    bxne lr
    ldr r1, =SCREEN_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    bxeq lr
    cmn r1, #1
    bxeq lr
    ldr r1, [r1, #0x2c]
    cmp r1, #1
    bxne lr
    mov r1, #0
    str r1, [r0]
    push {r4, lr}
    mov r4, sp
    sub sp, sp, #8
    bic sp, sp, #7
    ldr r0, =HW_MODEL
    ldr r1, [r0, #SEQ_SECTION]
    and r1, r1, #255
    mov r1, r1, lsl #8
    orr r1, r1, #SEQ_MSG_SECTION
    str r1, [sp]
    mov r1, #0
    str r1, [sp, #4]
    add r0, r0, #SEQ_OBSERVERS
    mov r1, sp
    ldr r12, =SEQ_NOTIFY
    blx r12
    mov sp, r4
    pop {r4, pc}
.pool
