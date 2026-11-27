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
    mov r1, #RR_CHANNELS
    cmp r1, #1
    moveq r0, r0, lsr #1
    movne r0, r0, lsr #2
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
    bl nr_gaps
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
    cmp r0, #NR_NO_CARD
    ldreq r1, =nr_no_card_text
nr_format_copy:
    mov r0, r4
    bl nr_text_copy
    ldr r1, [r6, #NR_ERROR]
    cmp r1, #0
    blne nr_gaps
    pop {r4-r8, pc}
.pool

; r0 the end of a title: appends " #n" while the take has gaps (n up to 99) and the terminating zero.
nr_gaps:
    push {r4, lr}
    ldr r1, =NATIVE_RECORDING
    ldr r1, [r1, #NR_GAPS]
    cmp r1, #0
    beq nr_gaps_end
    cmp r1, #99
    movhi r1, #99
    mov r2, #32
    strb r2, [r0], #1
    mov r2, #35
    strb r2, [r0], #1
    cmp r1, #10
    movhs r2, #10
    blhs nr_digit
    mov r2, #1
    bl nr_digit
nr_gaps_end:
    mov r1, #0
    strb r1, [r0]
    pop {r4, pc}
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


nr_menu_text:
    add r0, r5, #M_TITLE
    add r1, r5, #M_VALUE
    bl nr_format
    pop {r4, r5, r6, r7, pc}

nr_file_prefix: .asciz "REC"
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
nr_no_card_text: .asciz "No card"
nr_record_text: .asciz "RECORD"
.align 4
nr_format_end:
