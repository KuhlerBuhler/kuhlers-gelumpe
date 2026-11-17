; Caller owns a zeroed RW_SIZE context and invokes this writer from the card task.
.equ RW_STATE, 0
.equ RW_DATA_BYTES, 4
.equ RW_NUMBER, 8
.equ RW_CHANNELS, 12
.equ RW_STATUS, 16
.equ RW_FS_ERROR, 20
.equ RW_WRITTEN, 24
.equ RW_FIL, 32
.equ RW_FIL_SIZE, 0x240
.equ RW_HEADER, RW_FIL + RW_FIL_SIZE
.equ RW_PATH, RW_HEADER + 512
.equ RW_SIZE, RW_PATH + 32
.equ RW_MAX_DATA, 0xFFFFFDFC
.equ RW_OK, 0
.equ RW_IO, 1
.equ RW_FULL, 2
.equ RW_BAD_STATE, 3
.equ RW_BAD_ARG, 4
.equ RW_LIMIT, 5
.equ RW_NO_NAME, 6

; r0 context, r1 channels (1 or 2). FA_CREATE_NEW reserves the first unused name.
rec_writer_open:
    push {r4-r8, lr}
    mov r4, r0
    mov r5, r1
    ldr r0, [r4, #RW_STATE]
    cmp r0, #0
    movne r0, #RW_BAD_STATE
    bne rec_open_done
    sub r0, r5, #1
    cmp r0, #1
    movhi r0, #RW_BAD_ARG
    bhi rec_open_done
    mov r0, #0
    str r0, [r4, #RW_DATA_BYTES]
    str r0, [r4, #RW_STATUS]
    str r0, [r4, #RW_FS_ERROR]
    str r5, [r4, #RW_CHANNELS]
    ldr r0, =rec_directory
    ldr r12, =REC_FS_MKDIR
    blx r12
    cmp r0, #0
    beq rec_open_next
    cmp r0, #8
    bne rec_open_io
rec_open_next:
    ldr r6, [r4, #RW_NUMBER]
    ldr r7, =9999
    cmp r6, r7
    movhs r0, #RW_NO_NAME
    bhs rec_open_done
    add r6, r6, #1
    str r6, [r4, #RW_NUMBER]
    mov r0, r4
    bl rec_writer_path
    add r0, r4, #RW_FIL
    add r1, r4, #RW_PATH
    mov r2, #6
    ldr r12, =REC_FS_OPEN
    blx r12
    cmp r0, #8
    beq rec_open_next
    cmp r0, #0
    bne rec_open_io
    mov r0, #1
    str r0, [r4, #RW_STATE]
    mov r0, r4
    bl rec_writer_header
    mov r0, r4
    add r1, r4, #RW_HEADER
    mov r2, #512
    bl rec_writer_write
    cmp r0, #0
    beq rec_open_done
    mov r0, r4
    bl rec_writer_close
    b rec_open_done
rec_open_io:
    str r0, [r4, #RW_FS_ERROR]
    mov r0, #RW_IO
    str r0, [r4, #RW_STATUS]
rec_open_done:
    pop {r4-r8, pc}
.pool

; r0 context, r1 PCM bytes in WAV order, r2 bytes (at most 64 KiB, whole frames).
rec_writer_append:
    push {r4-r8, lr}
    mov r4, r0
    ldr r0, [r4, #RW_STATE]
    cmp r0, #1
    movne r0, #RW_BAD_STATE
    bne rec_append_done
    ldr r0, [r4, #RW_STATUS]
    cmp r0, #0
    bne rec_append_done
    cmp r2, #65536
    movhi r0, #RW_BAD_ARG
    bhi rec_append_done
    ldr r7, [r4, #RW_CHANNELS]
    mov r7, r7, lsl #1
    sub r7, r7, #1
    tst r2, r7
    movne r0, #RW_BAD_ARG
    bne rec_append_done
    cmp r2, #0
    beq rec_append_done
    ldr r5, [r4, #RW_DATA_BYTES]
    adds r6, r5, r2
    movcs r0, #RW_LIMIT
    bcs rec_append_done
    ldr r8, =RW_MAX_DATA
    cmp r6, r8
    movhi r0, #RW_LIMIT
    bhi rec_append_done
    mov r0, r4
    bl rec_writer_write
    ldr r6, [r4, #RW_WRITTEN]
    bic r6, r6, r7
    add r5, r5, r6
    str r5, [r4, #RW_DATA_BYTES]
rec_append_done:
    pop {r4-r8, pc}
.pool

; r0 context. Rewrites the sector header and closes, preserving an earlier fault.
rec_writer_finish:
    push {r4-r8, lr}
    mov r4, r0
    ldr r0, [r4, #RW_STATE]
    cmp r0, #2
    beq rec_finish_close
    cmp r0, #1
    movne r0, #RW_BAD_STATE
    bne rec_finish_done
    mov r0, r4
    bl rec_writer_header
    add r0, r4, #RW_FIL
    mov r1, #0
    ldr r12, =REC_FS_LSEEK
    blx r12
    cmp r0, #0
    bne rec_finish_io
    mov r0, r4
    add r1, r4, #RW_HEADER
    mov r2, #512
    bl rec_writer_write
    b rec_finish_close
rec_finish_io:
    str r0, [r4, #RW_FS_ERROR]
    mov r0, #RW_IO
    str r0, [r4, #RW_STATUS]
rec_finish_close:
    mov r0, r4
    bl rec_writer_close
rec_finish_done:
    pop {r4-r8, pc}
.pool

rec_writer_close:
    push {r4, lr}
    mov r4, r0
    add r0, r4, #RW_FIL
    ldr r12, =REC_FS_CLOSE
    blx r12
    cmp r0, #0
    beq rec_close_ok
    str r0, [r4, #RW_FS_ERROR]
    mov r0, #RW_IO
    str r0, [r4, #RW_STATUS]
    mov r0, #2
    str r0, [r4, #RW_STATE]
    b rec_close_return
rec_close_ok:
    str r0, [r4, #RW_STATE]
rec_close_return:
    ldr r0, [r4, #RW_STATUS]
    pop {r4, pc}
.pool

; A partial final frame is excluded from the declared data chunk.
rec_writer_write:
    push {r4-r6, lr}
    mov r4, r0
    mov r5, r2
    mov r0, #0
    str r0, [r4, #RW_WRITTEN]
    add r0, r4, #RW_FIL
    add r3, r4, #RW_WRITTEN
    ldr r12, =REC_FS_WRITE
    blx r12
    mov r6, r0
    ldr r1, [r4, #RW_WRITTEN]
    cmp r1, r5
    movhi r1, #0
    strhi r1, [r4, #RW_WRITTEN]
    bhi rec_write_io
    cmp r0, #0
    bne rec_write_io
    cmp r1, r5
    moveq r0, #RW_OK
    beq rec_write_done
    mov r0, #RW_FULL
    ldr r1, [r4, #RW_STATUS]
    cmp r1, #RW_IO
    strne r0, [r4, #RW_STATUS]
    b rec_write_done
rec_write_io:
    str r6, [r4, #RW_FS_ERROR]
    mov r0, #RW_IO
    str r0, [r4, #RW_STATUS]
rec_write_done:
    pop {r4-r6, pc}
.pool

rec_writer_header:
    push {r4-r6, lr}
    mov r4, r0
    add r5, r4, #RW_HEADER
    mov r1, r5
    mov r0, #0
    mov r2, #128
rec_header_zero:
    str r0, [r1], #4
    subs r2, r2, #1
    bne rec_header_zero
    ldr r0, =0x46464952
    str r0, [r5]
    ldr r0, [r4, #RW_DATA_BYTES]
    add r0, r0, #504
    str r0, [r5, #4]
    ldr r0, =0x45564157
    str r0, [r5, #8]
    ldr r0, =0x4B4E554A
    str r0, [r5, #12]
    mov r0, #460
    str r0, [r5, #16]
    ldr r0, =0x20746D66
    str r0, [r5, #480]
    mov r0, #16
    str r0, [r5, #484]
    ldr r6, [r4, #RW_CHANNELS]
    mov r0, #1
    orr r0, r0, r6, lsl #16
    str r0, [r5, #488]
    ldr r3, =48000
    str r3, [r5, #492]
    mov r2, r6, lsl #1
    mul r0, r2, r3
    str r0, [r5, #496]
    orr r0, r2, #0x100000
    str r0, [r5, #500]
    ldr r0, =0x61746164
    str r0, [r5, #504]
    ldr r0, [r4, #RW_DATA_BYTES]
    str r0, [r5, #508]
    pop {r4-r6, pc}
.pool

rec_writer_path:
    push {r4-r8, lr}
    mov r4, r0
    add r5, r4, #RW_PATH
    ldr r7, =rec_path_template
rec_path_copy:
    ldrb r0, [r7], #1
    strb r0, [r5], #1
    cmp r0, #0
    bne rec_path_copy
    add r5, r4, #RW_PATH
    add r5, r5, #17
    ldr r6, [r4, #RW_NUMBER]
    ldr r7, =rec_decimal_weights
    mov r8, #4
rec_path_digit:
    ldr r2, [r7], #4
    mov r1, #0
rec_path_subtract:
    cmp r6, r2
    subhs r6, r6, r2
    addhs r1, r1, #1
    bhs rec_path_subtract
    add r1, r1, #0x30
    strb r1, [r5], #1
    subs r8, r8, #1
    bne rec_path_digit
    pop {r4-r8, pc}
.pool
rec_decimal_weights:
    .word 1000, 100, 10, 1
rec_directory:
    .asciz "SD:Recordings"
rec_path_template:
    .asciz "SD:Recordings/REC0000.WAV"
.align 4
