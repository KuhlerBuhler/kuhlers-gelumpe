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

; korg.seq.getOn, getGate, getVelocity (r0 part, r1 step) -> r0 that byte of the step's record, as it is. getNote (r2 note place 0
; to 3) -> the MIDI note, -1 for an empty place. Reads only: the frame does not count as one that wrote steps (seq_address).
script_seq_get_on_glue:
    mov r3, #SCRIPT_STEP_ON
    b seq_get_byte

script_seq_get_gate_glue:
    mov r3, #SCRIPT_STEP_GATE
    b seq_get_byte

script_seq_get_velocity_glue:
    mov r3, #SCRIPT_STEP_VELOCITY
    b seq_get_byte

script_seq_get_note_glue:
    cmp r2, #4
    bhs hw_bad_arg
    add r3, r2, #SCRIPT_STEP_NOTES
seq_get_byte:
    cmp r0, #16
    cmplo r1, #SCRIPT_STEP_COUNT
    bhs hw_bad_arg
    push {lr}
    bl seq_address
    ldrb r0, [r12, r3]
    cmp r3, #SCRIPT_STEP_NOTES
    blo seq_got
    cmp r0, #0
    mvneq r0, #0
    subne r0, r0, #1
seq_got:
    mov r1, #ERR_OK
    pop {pc}

; r0 part, r1 step, r2 note (-1 for none), r3 velocity. A note with a velocity above 0 turns the step on with that note in the
; first note place (the other three cleared); note -1 or velocity 0 turns it off. The gate stays. The trigger is 1, or 0 when
; the step before is on with a TIE (gate above 96), as the firmware writes it when a TIE is set: then the same note goes on
; without a new strike (docs/messungen/2026-11-06-step-trigger.md). From API 22; before, always 1.
script_seq_set_step_glue:
    cmp r0, #16
    cmplo r1, #SCRIPT_STEP_COUNT
    bhs hw_bad_arg
    push {r4, lr}
    mov r4, r1                  ; the step: seq_record clobbers r1
    bl seq_record
    cmp r2, #0
    cmpge r3, #1
    movlt r1, #0
    strblt r1, [r12, #SCRIPT_STEP_ON]
    blt seq_step_done
    strb r3, [r12, #SCRIPT_STEP_VELOCITY]
    add r2, r2, #1
    strb r2, [r12, #SCRIPT_STEP_NOTES]
    mov r1, #0
    strb r1, [r12, #SCRIPT_STEP_NOTES+1]
    strb r1, [r12, #SCRIPT_STEP_NOTES+2]
    strb r1, [r12, #SCRIPT_STEP_NOTES+3]
    mov r1, #1
    cmp r4, #0
    beq seq_step_trigger
    ldrb r0, [r12, #SCRIPT_STEP_ON-SCRIPT_STEP_STRIDE]
    cmp r0, #0
    ldrbne r0, [r12, #SCRIPT_STEP_GATE-SCRIPT_STEP_STRIDE]
    cmpne r0, #96
    movhi r1, #0
seq_step_trigger:
    strb r1, [r12, #SCRIPT_STEP_TRIGGER]
    mov r1, #1
    strb r1, [r12, #SCRIPT_STEP_ON]
seq_step_done:
    mov r0, #0
    mov r1, #ERR_OK
    pop {r4, pc}

seq_done:
    mov r0, #0
    mov r1, #ERR_OK
    pop {pc}

; r0 part, r1 step, r2 gate 0 to 127 (above 96 ties into the next note).
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
; nothing. A field with a direct setter of its own (part_setters, PART_SETTERS in tools/patch/script_hooks.py) goes through
; that one instead, with (pattern object + 0x400C, part, value, 1) as the Part menu calls it. Three words per field there: the
; function, the mode and its argument (PART_MODES): 1 key tells the part panel's observers what the key would (its LED), 2 IFX
; ON also hands the value to the firmware's parameter set as the IFX ON key does, 3 top clamps to the byte at the argument (a
; field without a setter then goes through the part edit), 4 sample takes the whole slot number and only a slot the SAMPLE
; knob stops on; mode 1 on a field without a setter (the filter type) sends the key's message after the part edit. A fourth word
; (PART_CC) is the MIDI CC the field's knob, encoder or key sends: after a write the value goes out as that control sends it,
; for any part (the channel is the part's). A knob's field (a CC that is not on/off, through the part edit) then also goes to
; the parameter set (part + 1, CC id, value, 1) as the knob hands it to the sound engine; bit 10 of that word (PART_REFRESH)
; passes flag 1 to the part edit as the encoders do, so its dispatcher refreshes the sound engine. The parameter window stays
; shut while the calling plugin has the popups off (korg.display.popups, HD_QUIET).
script_seq_set_part_value_glue:
    cmp r0, #16
    cmplo r1, #SCRIPT_PART_FIELD_COUNT
    bhs hw_bad_arg
    ldr r3, =part_writes
    ldr r3, [r3, r1, lsl #2]
    cmp r3, #0
    beq hw_bad_arg
    push {r4-r10, lr}
    ldr r12, =part_setters
    add r12, r12, r1, lsl #4
    ldmia r12, {r6-r9}              ; r6 the setter, r7 the mode, r8 its argument, r9 the CC
    mov r4, r0
    cmp r7, #4
    beq part_value_sample
    mov r12, r3, lsl #8
    mov r12, r12, asr #24
    cmp r2, r12
    movlt r2, r12
    mov r12, r3, asr #24
    cmp r2, r12
    movgt r2, r12
    cmp r7, #3
    bne part_value_clamped
    ldr r12, [r8]                   ; the setter's `cmp r2, #top`: only a plain immediate counts, else nothing is written
    ldr r0, =0xFFFFFF00
    and r0, r12, r0
    ldr r5, =0xE3520000
    cmp r0, r5
    bne part_value_return
    and r12, r12, #255
    cmp r2, r12
    movgt r2, r12
part_value_clamped:
    and r5, r2, #255
    cmp r6, #0
    moveq r6, r3
    beq part_value_edit
    mov r1, r4
    ldr r0, =HW_PATTERN_OBJECT+0x400C
    mov r2, r5
    cmp r7, #2
    moveq r3, #0
    movne r3, #1
    blx r6
    cmp r7, #2
    bne part_value_key
    movs r2, r5
    movne r2, #127
    add r0, r4, #1
    and r1, r8, #255
    mov r3, #1
    ldr r12, =HW_PARAM_SET
    blx r12
    mov r8, r8, lsr #8
part_value_key:
    cmp r7, #1
    cmpne r7, #2
    bne part_value_cc
    ldr r0, =HW_PART
    ldr r0, [r0]
    cmp r0, r4
    bne part_value_cc
    sub sp, sp, #8
    strb r8, [sp]
    strb r5, [sp, #1]
    ldr r0, =HW_KEY_PANEL
    ldr r0, [r0]
    add r0, r0, #4
    mov r1, sp
    ldr r12, =SEQ_NOTIFY
    blx r12
    add sp, sp, #8
    b part_value_cc
part_value_sample:
    cmp r2, #0
    movlt r2, #0
    cmp r2, r8
    movgt r2, r8
    mov r5, r2
    mov r6, r3
    ldr r12, =HW_SAMPLE_NEXT
    cmp r12, #0
    beq part_value_return
    mov r0, r5
    mov r1, #1
    blx r12
    cmp r0, r5
    bne part_value_return
part_value_edit:
    ldr r12, =HW_PART_EDIT
    cmp r12, #0
    beq part_value_return
    and r0, r6, #255
    mov r1, r6, lsr #8
    and r1, r1, #255
    mov r2, r5
    mov r3, r9, lsr #10             ; flag 1 for the fields an encoder sets: the dispatcher refreshes the sound engine
    and r3, r3, #1
    bl part_edit_window
    cmp r7, #1
    beq part_value_key
    cmp r7, #4
    beq part_value_slice
    tst r9, #0x200
    bne part_value_cc
    ands r1, r9, #255               ; a knob's field: its parameter set (part + 1, id, value, 1) after the part edit, as the knob
    beq part_value_cc
    mov r2, r5
    tst r9, #0x100                  ; signed: the byte as -63 to 63, plus 64
    movne r2, r2, lsl #24
    movne r2, r2, asr #24
    addne r2, r2, #64
    add r0, r4, #1
    mov r3, #1
    ldr r12, =HW_PARAM_SET
    blx r12
    b part_value_cc
part_value_slice:
    ldr r12, =HW_SAMPLE_SLICED      ; a sliced sample: its slice to -1 as well, as the SAMPLE knob sets it turned up onto it
    cmp r12, #0
    beq part_value_cc
    mov r0, r5
    blx r12
    cmp r0, #0
    beq part_value_cc
    mov r0, #0x1E
    mov r1, #0x11
    mvn r2, #0
    mov r3, #0
    bl part_edit_window
part_value_cc:
    ands r12, r9, #255
    beq part_value_return
    ldr r12, =HW_MIDI_OBJ
    blx r12
    mov r3, r5
    tst r9, #0x100                  ; signed: the byte as -63 to 63, plus 64
    movne r3, r3, lsl #24
    movne r3, r3, asr #24
    addne r3, r3, #64
    tst r9, #0x200                  ; on/off: 127 or 0
    beq part_value_raw
    cmp r3, #0
    movne r3, #127
part_value_raw:
    mov r3, r3, lsl #1
    add r1, r4, #1
    and r2, r9, #255
    ldr r12, =HW_CC
    blx r12
part_value_return:
    pop {r4-r10, lr}
value_ok:
    mov r0, #0
    mov r1, #ERR_OK
    bx lr

; r4 part, r0 the part edit's parameter, r1 the window's code, r2 the value, r3 the part edit's flag (1 refreshes the sound
; engine through the dispatcher, as the encoders pass it; 0 as the knobs): the part edit, then for the selected part the
; parameter window unless the calling plugin keeps it shut. Clobbers r0 to r3 and r12.
part_edit_window:
    push {r4, r5, r6, lr}
    sub sp, sp, #16
    mov r5, r1
    mov r6, r2
    str r3, [sp, #4]
    mov r3, r0
    str r2, [sp]
    ldr r0, =HW_PART_EDITOR
    ldr r0, [r0]
    orr r1, r4, #0x10
    mov r2, #0
    ldr r12, =HW_PART_EDIT
    blx r12
    ldr r0, =HW_PART
    ldr r0, [r0]
    cmp r0, r4
    bne part_edit_done
    bl popups_quiet
    bne part_edit_done
    str r5, [sp, #8]
    str r6, [sp, #12]
    ldr r0, =HW_PARAM_WINDOW
    ldr r0, [r0]
    add r0, r0, #4
    add r1, sp, #8
    ldr r12, =SEQ_NOTIFY
    blx r12
part_edit_done:
    add sp, sp, #16
    pop {r4, r5, r6, pc}

; r0 field (PATTERN_FIELDS), r1 value: through the firmware's own setter for that field, the one the device's edit goes
; through, so the sound engine and the screen follow. The value is clamped to the field's range (pattern_writes) and turned
; from the units of korg.read.patternValue into the byte (bars 1 to 4 store 0 to 3, a chain -1 to 249 stores 0 to 250). The
; setters per build live in tools/patch/script_hooks.py (PATTERN_SETTERS), three words here each (pattern_setters): the
; function, the offset from the pattern object it gets in r0, and a lower top for the byte on this build (0 none) with what
; else the glue does (pattern_setter_actions); r1 the byte, r2 1 as the menu passes. A field without a setter (0) writes nothing (docs/messungen/2026-11-03-live-schreibwege.md);
; setter 1 stores the value as a halfword at that offset of the pattern in RAM, as the SYNC GROUP page does.
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
    beq value_ok
    cmp r12, #1
    beq pattern_value_store
    cmp r12, #2
    beq pattern_value_key
    cmp r12, #3
    beq pattern_value_mfx2_set
    push {r4, r5, r6, lr}
    ldr r4, [r3, #8]                ; top in bits 0 to 15, ALTERNATE index + 1 in 16 to 23, CC id in 24 to 31
    movs r0, r4, lsl #16
    beq pattern_value_top
    cmp r1, r0, lsr #16
    movgt r1, r0, lsr #16
pattern_value_top:
    mov r5, r1
    ldr r0, [r3, #4]
    ldr r3, =HW_PATTERN_OBJECT
    add r0, r0, r3
    mov r2, #1
    ands r6, r4, #0xFF0000
    beq pattern_value_call
    mov r2, r1                      ; the ALTERNATE pages: (pattern object, index, byte, 1)
    mov r1, r6, lsr #16
    sub r1, r1, #1
    mov r3, #1
pattern_value_call:
    blx r12
    movs r4, r4, lsr #24
    beq pattern_set_done
    ldr r12, =HW_MIDI_OBJ           ; as the touchpad sends it: global channel, raw value the byte times two
    blx r12
    mov r1, #17
    mov r2, r4
    mov r3, r5, lsl #1
    ldr r12, =HW_CC
    blx r12
pattern_set_done:
    pop {r4, r5, r6, lr}
    b value_ok
pattern_value_key:                  ; setter 2: press the key at word 1 when the byte at word 2 differs, as korg.pressKey
    ldr r0, [r3, #8]
    ldr r12, =HW_PATTERN_OBJECT+4
    ldrb r0, [r12, r0]
    cmp r0, r1
    beq value_ok
    ldr r0, [r3, #4]
    b script_press_key_glue
; setter 3: MFX 2 of the running pattern through the patch mfx-switch, nothing without the patch, with MFX 2 off in the
; menu BLECH or with EXIT held at power-on (mfx2_on). While MFX 2 is active the MFX type setter at word 1 runs as the MFX TYPE page calls it: the patch's hook on it stores
; the type in its table and the effect changes. Otherwise the entry is written and marked for the next WRITE, as that hook does.
pattern_value_mfx2_set:
    ldr r12, [r3, #8]
    cmp r12, #0
    beq pattern_mfx2_top
    cmp r1, r12
    movgt r1, r12
pattern_mfx2_top:
    push {r4, r5, r6, lr}
    mov r5, r1
    ldr r6, [r3, #4]
    bl mfx2_on
    cmp r0, #0
    beq pattern_mfx2_set_done
    ldr r12, =MFX2_ENTRY+4
    blx r12
    ldr r0, =MFX2_STATE
    ldr r0, [r0]
    cmp r0, #1
    bne pattern_mfx2_entry
    ldr r0, =HW_PATTERN_OBJECT+0x4004
    mov r1, r5
    mov r2, #1
    blx r6
    b pattern_mfx2_set_done
pattern_mfx2_entry:
    ldr r12, =SC_PLAYER
    blx r12
    ldr r0, [r0, #0x318]
    cmp r0, #250
    bhs pattern_mfx2_set_done
    ldr r1, =MFX2_TABLE
    add r2, r5, #1
    strb r2, [r1, r0]
    ldr r1, =MFX2_STATE
    mov r2, #1
    str r2, [r1, #24]
pattern_mfx2_set_done:
    pop {r4, r5, r6, lr}
    b value_ok
pattern_value_store:
    ldr r0, [r3, #4]
    ldr r3, =HW_PATTERN_OBJECT+4
    add r0, r0, r3
    strb r1, [r0]
    mov r1, r1, lsr #8
    strb r1, [r0, #1]
    b value_ok

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

; korg.read.patternName(array, pattern): the 16 bytes of the name, korg.read.patternBytes from offset 16 into at most 16 slots
script_read_pattern_name_glue:
    mov r12, r0, lsr #16
    cmp r12, #16
    movhi r0, r0, lsl #16
    movhi r0, r0, lsr #16
    orrhi r0, r0, #0x100000
    mov r2, #16
    b script_read_pattern_bytes_glue

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
    .word SCRIPT_PART_WRITE_20
    .word SCRIPT_PART_WRITE_21
    .word SCRIPT_PART_WRITE_22
    .word SCRIPT_PART_WRITE_23
    .word SCRIPT_PART_WRITE_24
    .word SCRIPT_PART_WRITE_25
    .word SCRIPT_PART_WRITE_26
    .word SCRIPT_PART_WRITE_27

part_setters:
    .word PS_SET_0, PS_MODE_0, PS_ARG_0, PS_CC_0
    .word PS_SET_1, PS_MODE_1, PS_ARG_1, PS_CC_1
    .word PS_SET_2, PS_MODE_2, PS_ARG_2, PS_CC_2
    .word PS_SET_3, PS_MODE_3, PS_ARG_3, PS_CC_3
    .word PS_SET_4, PS_MODE_4, PS_ARG_4, PS_CC_4
    .word PS_SET_5, PS_MODE_5, PS_ARG_5, PS_CC_5
    .word PS_SET_6, PS_MODE_6, PS_ARG_6, PS_CC_6
    .word PS_SET_7, PS_MODE_7, PS_ARG_7, PS_CC_7
    .word PS_SET_8, PS_MODE_8, PS_ARG_8, PS_CC_8
    .word PS_SET_9, PS_MODE_9, PS_ARG_9, PS_CC_9
    .word PS_SET_10, PS_MODE_10, PS_ARG_10, PS_CC_10
    .word PS_SET_11, PS_MODE_11, PS_ARG_11, PS_CC_11
    .word PS_SET_12, PS_MODE_12, PS_ARG_12, PS_CC_12
    .word PS_SET_13, PS_MODE_13, PS_ARG_13, PS_CC_13
    .word PS_SET_14, PS_MODE_14, PS_ARG_14, PS_CC_14
    .word PS_SET_15, PS_MODE_15, PS_ARG_15, PS_CC_15
    .word PS_SET_16, PS_MODE_16, PS_ARG_16, PS_CC_16
    .word PS_SET_17, PS_MODE_17, PS_ARG_17, PS_CC_17
    .word PS_SET_18, PS_MODE_18, PS_ARG_18, PS_CC_18
    .word PS_SET_19, PS_MODE_19, PS_ARG_19, PS_CC_19
    .word PS_SET_20, PS_MODE_20, PS_ARG_20, PS_CC_20
    .word PS_SET_21, PS_MODE_21, PS_ARG_21, PS_CC_21
    .word PS_SET_22, PS_MODE_22, PS_ARG_22, PS_CC_22
    .word PS_SET_23, PS_MODE_23, PS_ARG_23, PS_CC_23
    .word PS_SET_24, PS_MODE_24, PS_ARG_24, PS_CC_24
    .word PS_SET_25, PS_MODE_25, PS_ARG_25, PS_CC_25
    .word PS_SET_26, PS_MODE_26, PS_ARG_26, PS_CC_26
    .word PS_SET_27, PS_MODE_27, PS_ARG_27, PS_CC_27

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
    .word SCRIPT_PATTERN_WRITE_12
    .word SCRIPT_PATTERN_WRITE_13
    .word SCRIPT_PATTERN_WRITE_14
    .word SCRIPT_PATTERN_WRITE_15
    .word SCRIPT_PATTERN_WRITE_16
    .word SCRIPT_PATTERN_WRITE_17
    .word SCRIPT_PATTERN_WRITE_18

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
    .word PV_SET_12, PV_ARG_12, PV_TOP_12
    .word PV_SET_13, PV_ARG_13, PV_TOP_13
    .word PV_SET_14, PV_ARG_14, PV_TOP_14
    .word PV_SET_15, PV_ARG_15, PV_TOP_15
    .word PV_SET_16, PV_ARG_16, PV_TOP_16
    .word PV_SET_17, PV_ARG_17, PV_TOP_17
    .word PV_SET_18, PV_ARG_18, PV_TOP_18

; r0 part, r1 step -> r12 the step's record. Marks the frame as one that wrote steps (SQ_AT holds its own address). Clobbers r1.
seq_record:
    push {lr}
    bl seq_address
    ldr r1, =HOOK_CARD+SQ_AT
    str r1, [r1]
    pop {pc}

; r0 part, r1 step -> r12 the step's record, without marking anything. Clobbers r1.
seq_address:
    ldr r12, =SCRIPT_PART_STRIDE
    mul r12, r0, r12
    add r12, r12, r1, lsl #3
    add r12, r12, r1, lsl #2
    ldr r1, =HW_PATTERN_OBJECT+4+SCRIPT_PART_BASE+SCRIPT_STEP_BASE
    add r12, r12, r1
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
