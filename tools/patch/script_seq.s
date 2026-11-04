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

; r0 array, r1 part, r2 first step: whole records of 12 slots (PATTERN_STEPS: on, gate, velocity, trigger, four note places,
; four more the runtime leaves alone) from step `first`, as far as the slots and the 64 steps go -> r0 the steps written.
; Each value is clamped to its range; the on byte goes last, so the sequencer never plays a step that is half written.
script_seq_write_steps_glue:
    cmp r1, #16
    cmplo r2, #SCRIPT_STEP_COUNT
    bhs hw_bad_arg
    push {r4-r8, lr}
    ldr r3, =HOOK_RUNTIME
    ldr r3, [r3, #RT_ENTRY]
    ldr r3, [r3, #SCRIPT_ENTRY_VARS]
    mov r12, r0, lsl #16
    add r4, r3, r12, lsr #14
    mov r5, r0, lsr #16
    rsb r7, r2, #SCRIPT_STEP_COUNT
    mov r6, #0
steps_count:
    cmp r5, #SCRIPT_STEP_STRIDE
    blo steps_counted
    cmp r6, r7
    bhs steps_counted
    sub r5, r5, #SCRIPT_STEP_STRIDE
    add r6, r6, #1
    b steps_count
steps_counted:
    movs r7, r6
    beq steps_done
    mov r0, r1
    mov r1, r2
    bl seq_record
    mov r8, r12
steps_record:
    ldr r0, [r4, #4]
    mov r1, #0
    mov r2, #127
    bl steps_clamp
    strb r0, [r8, #SCRIPT_STEP_GATE]
    ldr r0, [r4, #8]
    mov r1, #1
    bl steps_clamp
    strb r0, [r8, #SCRIPT_STEP_VELOCITY]
    ldr r0, [r4, #12]
    mov r1, #0
    mov r2, #1
    bl steps_clamp
    strb r0, [r8, #SCRIPT_STEP_TRIGGER]
    mov r2, #128
    mov r3, #0
steps_note:
    add r12, r4, r3, lsl #2
    ldr r0, [r12, #16]
    bl steps_clamp
    add r12, r8, r3
    strb r0, [r12, #SCRIPT_STEP_NOTES]
    add r3, r3, #1
    cmp r3, #4
    blo steps_note
    ldr r0, [r4]
    mov r2, #1
    bl steps_clamp
    strb r0, [r8, #SCRIPT_STEP_ON]
    add r4, r4, #SCRIPT_STEP_STRIDE*4
    add r8, r8, #SCRIPT_STEP_STRIDE
    subs r7, r7, #1
    bne steps_record
steps_done:
    mov r0, r6
    mov r1, #ERR_OK
    pop {r4-r8, pc}

; r0 value, r1 minimum, r2 maximum -> r0 clamped.
steps_clamp:
    cmp r0, r1
    movlt r0, r1
    cmp r0, r2
    movgt r0, r2
    bx lr

; r0 part, r1 field (PART_FIELDS), r2 value: through the firmware's part edit, the setter the knobs go through, which writes
; the pattern in RAM and the sound engine's copy. The value is clamped to the field's range first, the setter does not check
; it. For the selected part the parameter window opens as a knob opens it. A build without the setter (HW_PART_EDIT 0) writes
; nothing.
script_seq_set_part_value_glue:
    cmp r0, #16
    cmplo r1, #SCRIPT_PART_FIELD_COUNT
    bhs hw_bad_arg
    ldr r3, =part_writes
    ldr r3, [r3, r1, lsl #2]
    cmp r3, #0
    beq hw_bad_arg
    ldr r12, =HW_PART_EDIT
    cmp r12, #0
    beq part_value_return
    push {r4-r6, lr}
    sub sp, sp, #16
    mov r12, r3, lsl #8
    mov r12, r12, asr #24
    cmp r2, r12
    movlt r2, r12
    mov r12, r3, asr #24
    cmp r2, r12
    movgt r2, r12
    and r5, r2, #255
    mov r4, r0
    mov r6, r3
    str r5, [sp]
    mov r12, #0
    str r12, [sp, #4]
    ldr r12, =HW_PART_EDITOR
    ldr r0, [r12]
    orr r1, r4, #0x10
    mov r2, #0
    and r3, r6, #255
    ldr r12, =HW_PART_EDIT
    blx r12
    ldr r0, =HW_PART
    ldr r0, [r0]
    cmp r0, r4
    bne part_value_done
    mov r0, r6, lsr #8
    and r0, r0, #255
    str r0, [sp, #8]
    str r5, [sp, #12]
    ldr r0, =HW_PARAM_WINDOW
    ldr r0, [r0]
    add r0, r0, #4
    add r1, sp, #8
    ldr r12, =SEQ_NOTIFY
    blx r12
part_value_done:
    add sp, sp, #16
    pop {r4-r6, lr}
part_value_return:
    mov r0, #0
    mov r1, #ERR_OK
    bx lr

; r0 field (PATTERN_FIELDS), r1 value: through the firmware's own setter for that field, the one the device's edit goes
; through, so the sound engine and the screen follow. The value is clamped to the field's range (pattern_writes) and turned
; from the units of korg.read.patternValue into the byte (bars 1 to 4 store 0 to 3, a chain -1 to 249 stores 0 to 250). The
; setters per build live in tools/patch/script_hooks.py (PATTERN_SETTERS), three words here each (pattern_setters): the
; function, the offset from the pattern object it gets in r0, and a lower top for the byte on this build (0 none); r1 the
; byte, r2 1 as the menu passes. A field without a setter (0)
; writes nothing (docs/messungen/2026-11-03-live-schreibwege.md).
script_seq_set_pattern_value_glue:
    cmp r0, #SCRIPT_PATTERN_FIELD_COUNT
    bhs hw_bad_arg
    ldr r3, =pattern_writes
    ldr r3, [r3, r0, lsl #2]
    cmp r3, #0
    beq hw_bad_arg
    mov r12, r3, lsl #16
    mov r12, r12, asr #16
    cmp r1, r12
    movlt r1, r12
    mov r12, r3, asr #16
    cmp r1, r12
    movgt r1, r12
    ldr r3, =pattern_fields
    ldr r3, [r3, r0, lsl #2]
    mov r3, r3, lsr #16
    cmp r3, #3
    subeq r1, r1, #1
    cmp r3, #4
    addeq r1, r1, #1
    ldr r3, =pattern_setters
    add r0, r0, r0, lsl #1
    add r3, r3, r0, lsl #2
    ldr r12, [r3]
    cmp r12, #0
    beq part_value_return
    ldr r0, [r3, #8]
    cmp r0, #0
    beq pattern_value_top
    cmp r1, r0
    movgt r1, r0
pattern_value_top:
    ldr r0, [r3, #4]
    ldr r3, =HW_PATTERN_OBJECT
    add r0, r0, r3
    mov r2, #1
    push {r4, lr}
    blx r12
    pop {r4, lr}
    b part_value_return

; r0 array, r1 pattern (-1 the one in RAM, 0 to 249 the bank), r2 offset in its block: one byte per slot, as far as the block
; goes -> r0 the bytes read.
script_read_pattern_bytes_glue:
    cmn r1, #1
    blt hw_bad_arg
    cmp r1, #250
    bge hw_bad_arg
    cmp r2, #0x4000
    bhs hw_bad_arg
    ldr r3, =HOOK_RUNTIME
    ldr r3, [r3, #RT_ENTRY]
    ldr r3, [r3, #SCRIPT_ENTRY_VARS]
    mov r12, r0, lsl #16
    add r3, r3, r12, lsr #14
    mov r0, r0, lsr #16
    rsb r12, r2, #0x4000
    cmp r0, r12
    movhi r0, r12
    cmn r1, #1
    ldreq r12, =HW_PATTERN_OBJECT+4
    ldrne r12, =SC_BANK
    addne r12, r12, r1, lsl #14
    add r12, r12, r2
    mov r1, #0
pattern_bytes_loop:
    cmp r1, r0
    beq pattern_bytes_done
    ldrb r2, [r12, r1]
    str r2, [r3, r1, lsl #2]
    add r1, r1, #1
    b pattern_bytes_loop
pattern_bytes_done:
    mov r1, #ERR_OK
    bx lr
.pool

part_writes:
    .word SCRIPT_PART_WRITE_0
    .word SCRIPT_PART_WRITE_1
    .word SCRIPT_PART_WRITE_2
    .word SCRIPT_PART_WRITE_3
    .word SCRIPT_PART_WRITE_4
    .word SCRIPT_PART_WRITE_5
    .word SCRIPT_PART_WRITE_6
    .word SCRIPT_PART_WRITE_7
    .word SCRIPT_PART_WRITE_8
    .word SCRIPT_PART_WRITE_9
    .word SCRIPT_PART_WRITE_10
    .word SCRIPT_PART_WRITE_11
    .word SCRIPT_PART_WRITE_12
    .word SCRIPT_PART_WRITE_13
    .word SCRIPT_PART_WRITE_14
    .word SCRIPT_PART_WRITE_15
    .word SCRIPT_PART_WRITE_16
    .word SCRIPT_PART_WRITE_17
    .word SCRIPT_PART_WRITE_18
    .word SCRIPT_PART_WRITE_19

pattern_writes:
    .word SCRIPT_PATTERN_WRITE_0
    .word SCRIPT_PATTERN_WRITE_1
    .word SCRIPT_PATTERN_WRITE_2
    .word SCRIPT_PATTERN_WRITE_3
    .word SCRIPT_PATTERN_WRITE_4
    .word SCRIPT_PATTERN_WRITE_5
    .word SCRIPT_PATTERN_WRITE_6
    .word SCRIPT_PATTERN_WRITE_7
    .word SCRIPT_PATTERN_WRITE_8
    .word SCRIPT_PATTERN_WRITE_9
    .word SCRIPT_PATTERN_WRITE_10
    .word SCRIPT_PATTERN_WRITE_11

pattern_setters:
    .word PV_SET_0, PV_ARG_0, PV_TOP_0
    .word PV_SET_1, PV_ARG_1, PV_TOP_1
    .word PV_SET_2, PV_ARG_2, PV_TOP_2
    .word PV_SET_3, PV_ARG_3, PV_TOP_3
    .word PV_SET_4, PV_ARG_4, PV_TOP_4
    .word PV_SET_5, PV_ARG_5, PV_TOP_5
    .word PV_SET_6, PV_ARG_6, PV_TOP_6
    .word PV_SET_7, PV_ARG_7, PV_TOP_7
    .word PV_SET_8, PV_ARG_8, PV_TOP_8
    .word PV_SET_9, PV_ARG_9, PV_TOP_9
    .word PV_SET_10, PV_ARG_10, PV_TOP_10
    .word PV_SET_11, PV_ARG_11, PV_TOP_11

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
