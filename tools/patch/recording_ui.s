; The setup lifetime is signalled by its constructor and destructor, without retaining a view pointer.
nr_setup_enter:
    push {r0-r3, r12, lr}
    .word 0xE10FC000                 ; mrs r12, cpsr
    push {r12, lr}
    bl nr_init
    mov r1, #1
    str r1, [r0, #NR_SETUP]
    pop {r12, lr}
    .word 0xE128F00C                 ; msr cpsr_f, r12
    pop {r0-r3, r12, lr}
    ldr r3, =0xC00E3AA8
    ldr pc, =0xC006B698
nr_setup_leave:
    push {r0-r3, r12, lr}
    .word 0xE10FC000                 ; mrs r12, cpsr
    push {r12, lr}
    bl nr_init
    mov r1, #0
    str r1, [r0, #NR_SETUP]
    pop {r12, lr}
    .word 0xE128F00C                 ; msr cpsr_f, r12
    pop {r0-r3, r12, lr}
    ldr r3, =0xC00E3AA8
    ldr pc, =0xC006B5A0
.pool

; r0 panel packet -> r0 1 swallowed, 0 native. REC is key 0; PLAY never enters this path.
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
    ldr r0, [r5, #NR_SETUP]
    cmp r0, #0
    beq nr_input_pass
    bl nr_busy
    mov r6, r0
    bl nr_enabled
    cmp r0, #0
    bne nr_input_enabled
    cmp r6, #0
    bne nr_input_take
    b nr_input_pass
nr_input_enabled:
    ldr r0, [r5, #NR_SELECTED]
    cmp r0, #0
    beq nr_input_sampling
    eor r0, r6, #1
    bl nr_post
    b nr_input_take
nr_input_sampling:
    cmp r6, #0
    beq nr_input_pass
nr_input_take:
    mov r0, #1
    str r0, [r5, #NR_HELD]
    pop {r4-r6, pc}
nr_input_pass:
    mov r0, #0
    pop {r4-r6, pc}
.pool

; Logical choices 0 Audio In, 1 Resampling, 2 Record keep the native engine's source boolean valid.
nr_source_hook:
    push {r0-r6, lr}
    mov r4, r0
    mov r5, r1
    bl nr_enabled
    cmp r0, #0
    beq nr_source_native
    bl nr_busy
    cmp r0, #0
    bne nr_source_done
    bl nr_init
    mov r6, r0
    ldr r0, [r4, #0x24]
    ldr r2, [r0, #0x708]
    ldr r3, [r6, #NR_SELECTED]
    cmp r3, #0
    movne r2, #2
    add r1, r2, r5
    cmp r1, #0
    movlt r1, #0
    cmp r1, #2
    movgt r1, #2
    cmp r1, #2
    moveq r2, #1
    movne r2, #0
    str r2, [r6, #NR_SELECTED]
    cmp r1, #0
    movne r1, #1
    ldr r4, [r0, #0x708]
    cmp r1, r4
    bne nr_source_notify
    cmp r2, r3
    beq nr_source_done
nr_source_notify:
    str r1, [r0, #0x708]
    sub sp, sp, #8
    mov r3, #1
    str r3, [sp]
    str r1, [sp, #4]
    add r0, r0, #0x400
    mov r1, sp
    ldr r12, =0xC0070688
    blx r12
    add sp, sp, #8
nr_source_done:
    pop {r0-r6, pc}
nr_source_native:
    pop {r0-r6, lr}
    push {r0-r2, lr}
    ldr pc, =0xC006B444
.pool

nr_source_label:
    push {r0, r1, r4, lr}
    mov r4, r0
    bl nr_enabled
    cmp r0, #0
    beq nr_source_label_native
    bl nr_init
    ldr r0, [r0, #NR_SELECTED]
    cmp r0, #0
    beq nr_source_label_native
    mov r0, r4
    ldr r1, =nr_record_text
    add r2, sp, #4
    ldr r12, =0xC00A324C
    blx r12
    mov r0, r4
    add sp, sp, #8
    pop {r4, pc}
nr_source_label_native:
    ldr r0, [sp]
    ldr r1, [sp, #4]
    ldr pc, =0xC008C2A4
nr_record_text:
    .asciz "RECORD"
.align 4
.pool

; Validated bytecode is scanned by instruction boundaries, including calls behind branches.
nr_requires_capture:
    ldr r0, [r0, #SCRIPT_ENTRY_BLOB]
    add r1, r0, #HDR_SIZE
    ldrb r2, [r0, #HDR_HANDLER_COUNT]
    ldrb r3, [r0, #HDR_HANDLER_COUNT+1]
    orr r2, r2, r3, lsl #8
    add r1, r1, r2, lsl #2
    ldrb r2, [r0, #HDR_CONST_COUNT]
    ldrb r3, [r0, #HDR_CONST_COUNT+1]
    orr r2, r2, r3, lsl #8
    add r1, r1, r2, lsl #2
    ldrb r2, [r0, #HDR_STRING_COUNT]
    ldrb r3, [r0, #HDR_STRING_COUNT+1]
    orr r2, r2, r3, lsl #8
    add r1, r1, r2, lsl #5
    ldrb r2, [r0, #HDR_CODE_SIZE]
    ldrb r3, [r0, #HDR_CODE_SIZE+1]
    orr r2, r2, r3, lsl #8
    add r2, r1, r2
    ldr r12, =NR_OP_SIZE
nr_capture_scan:
    cmp r1, r2
    bhs nr_capture_absent
    ldrb r0, [r1]
    cmp r0, #SCRIPT_OPCODE_COUNT
    bhs nr_capture_present
    ldrb r3, [r12, r0]
    cmp r3, #0
    beq nr_capture_present
    add r3, r1, r3
    cmp r3, r2
    bhi nr_capture_present
    cmp r0, #OP_CALLAPI
    bne nr_capture_next
    ldrb r0, [r1, #1]
    cmp r0, #API_KORG_AUDIO_CAPTURE
    beq nr_capture_present
nr_capture_next:
    mov r1, r3
    b nr_capture_scan
nr_capture_absent:
    mov r0, #0
    bx lr
nr_capture_present:
    mov r0, #1
    bx lr
.pool

nr_app_allowed:
    push {r4, lr}
    mov r4, r0
    bl nr_busy
    cmp r0, #0
    moveq r0, #1
    beq nr_app_allowed_done
    mov r0, r4
    bl nr_requires_capture
    eor r0, r0, #1
nr_app_allowed_done:
    pop {r4, pc}

nr_close_capture_app:
    push {r4, lr}
    ldr r0, =APP_STATE
    ldr r0, [r0, #SCRIPT_APPS_OPEN]
    cmp r0, #0
    beq nr_close_app_done
    bl nr_requires_capture
    cmp r0, #0
    blne script_app_close
nr_close_app_done:
    pop {r4, pc}
.pool

; r0 title buffer (32 bytes), r1 value buffer (16 bytes).
nr_format:
    push {r4-r8, lr}
    mov r4, r0
    mov r5, r1
    bl nr_init
    mov r6, r0
    mov r0, r5
    ldr r1, =nr_record_text
    bl nr_text_copy
    ldr r1, [r6, #NR_NUMBER]
    cmp r1, #0
    beq nr_format_title
    mov r0, r5
    ldr r1, =nr_file_prefix
    bl nr_text_copy
    ldr r1, [r6, #NR_NUMBER]
    mov r2, #1000
    bl nr_digit
    mov r2, #100
    bl nr_digit
    mov r2, #10
    bl nr_digit
    mov r2, #1
    bl nr_digit
    mov r1, #0
    strb r1, [r0]
nr_format_title:
    ldr r0, [r6, #NR_ERROR]
    cmp r0, #0
    bne nr_format_error
    ldr r0, [r6, #NR_PHASE]
    cmp r0, #3
    ldreq r1, =nr_opening_text
    beq nr_format_copy
    cmp r0, #2
    ldreq r1, =nr_saving_text
    beq nr_format_copy
    cmp r0, #1
    ldreq r1, =nr_running_text
    beq nr_format_time
    ldr r0, [r6, #NR_NUMBER]
    cmp r0, #0
    ldreq r1, =nr_source_text
    beq nr_format_copy
    ldr r1, =nr_saved_text
nr_format_time:
    mov r0, r4
    bl nr_text_copy
    mov r8, r0
    ldr r0, [r6, #NR_BYTES]
    mov r0, r0, lsr #2
    ldr r1, =48000
    bl glide_divide
    mov r7, r0
    mov r1, #3600
    bl glide_divide
    mov r6, r0
    mov r1, r0
    mov r0, r8
    bl nr_pair
    mov r1, #58
    strb r1, [r0], #1
    mov r8, r0
    mov r0, #3600
    mul r1, r6, r0
    sub r7, r7, r1
    mov r0, r7
    mov r1, #60
    bl glide_divide
    mov r6, r0
    mov r1, r0
    mov r0, r8
    bl nr_pair
    mov r1, #58
    strb r1, [r0], #1
    mov r2, #60
    mul r1, r6, r2
    sub r1, r7, r1
    bl nr_pair
    mov r1, #0
    strb r1, [r0]
    pop {r4-r8, pc}
nr_format_error:
    ldr r1, =nr_error_text
    cmp r0, #RW_IO
    ldreq r1, =nr_card_error_text
    cmp r0, #RW_FULL
    ldreq r1, =nr_full_text
    cmp r0, #RW_LIMIT
    ldreq r1, =nr_limit_text
    cmp r0, #RC_READER_ERROR+RR_BUSY
    ldreq r1, =nr_busy_text
    cmp r0, #RC_READER_ERROR+RR_GAP
    ldreq r1, =nr_gap_text
    cmp r0, #RC_READER_ERROR+RR_LOST
    ldreq r1, =nr_lost_text
    cmp r0, #RC_READER_ERROR+RR_NO_PATCH
    ldreq r1, =nr_patch_text
    cmp r0, #RC_READER_ERROR+RR_OVERFLOW
    ldreq r1, =nr_overflow_text
    cmp r0, #NR_OOM
    ldreq r1, =nr_oom_text
nr_format_copy:
    mov r0, r4
    bl nr_text_copy
    ldr r1, [r6, #NR_ERROR]
    cmp r1, #0
    beq nr_format_done
    ldr r1, [r6, #NR_GAPS]
    cmp r1, #0
    beq nr_format_done
    mov r2, #32
    strb r2, [r0], #1
    mov r2, #35
    strb r2, [r0], #1
    mov r2, #1
    bl nr_digit
    mov r1, #0
    strb r1, [r0]
nr_format_done:
    pop {r4-r8, pc}
.pool

; r0 destination, r1 text -> r0 points to the terminating zero.
nr_text_copy:
    ldrb r2, [r1], #1
    strb r2, [r0], #1
    cmp r2, #0
    bne nr_text_copy
    sub r0, r0, #1
    bx lr

nr_pair:
    push {r4, lr}
    mov r2, #10
    bl nr_digit
    mov r2, #1
    bl nr_digit
    pop {r4, pc}
nr_digit:
    mov r3, #48
nr_digit_sub:
    cmp r1, r2
    subhs r1, r1, r2
    addhs r3, r3, #1
    bhs nr_digit_sub
    strb r3, [r0], #1
    bx lr

; The native string compare avoids allocating a replacement when the text is unchanged.
nr_assign_text:
    push {r4-r6, lr}
    mov r4, r0
    mov r5, r1
    ldr r12, =0xC00A2034
    blx r12
    cmp r0, #0
    beq nr_assign_done
    mov r0, r4
    mov r1, r5
    ldr r12, =0xC00A26C0
    blx r12
    mov r0, #1
nr_assign_done:
    pop {r4-r6, pc}
.pool

nr_view_draw:
    push {r0-r6, lr}
    mov r4, r0
    bl nr_enabled
    cmp r0, #0
    beq nr_view_native
    bl nr_init
    ldr r6, [r0, #NR_SELECTED]
    ldr r0, =0xC00F9CD4
    ldr r0, [r0]
    cmp r0, #2
    bne nr_view_native
    cmp r6, #0
    beq nr_view_source
    sub sp, sp, #64
    mov r0, sp
    add r1, sp, #32
    bl nr_format
    add r0, r4, #0x48
    mov r1, sp
    bl nr_assign_text
    mov r5, r0
    add r0, r4, #0x4C
    add r1, sp, #32
    bl nr_assign_text
    orrs r0, r0, r5
    movne r0, #1
    strbne r0, [r4, #0x14]
    add sp, sp, #64
    b nr_view_native
nr_view_source:
    add r0, r4, #0x48
    ldr r1, =nr_source_text
    bl nr_assign_text
    cmp r0, #0
    movne r0, #1
    strbne r0, [r4, #0x14]
nr_view_native:
    pop {r0-r6, lr}
    push {r0-r6, lr}
    ldr pc, =0xC008C2E8
.pool

nr_file_prefix: .asciz "REC"
nr_source_text: .asciz "Sampling Source"
nr_opening_text: .asciz "Opening..."
nr_saving_text: .asciz "Saving..."
nr_running_text: .asciz "REC "
nr_saved_text: .asciz "Saved "
nr_error_text: .asciz "Record error"
nr_card_error_text: .asciz "Card error"
nr_full_text: .asciz "Card full"
nr_limit_text: .asciz "File limit"
nr_busy_text: .asciz "Sampling busy"
nr_gap_text: .asciz "Capture gap"
nr_lost_text: .asciz "Capture lost"
nr_patch_text: .asciz "No DSP patch"
nr_overflow_text: .asciz "Ring full"
nr_oom_text: .asciz "No memory"
.align 4
nr_ui_end:
