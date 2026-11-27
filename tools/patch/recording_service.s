; The card task owns the context and at least two 64-KiB blocks. Other tasks only post RC_REQUEST.
.equ RC_READER, RW_SIZE
.equ RC_REQUEST, RC_READER + RR_SIZE
.equ RC_ERROR, RC_REQUEST + 4
.equ RC_ACTIVE, RC_REQUEST + 8
.equ RC_RING, RC_REQUEST + 12
.equ RC_CAPACITY, RC_REQUEST + 16
.equ RC_CHANNELS, RC_REQUEST + 20
.equ RC_DROPPED, RC_REQUEST + 24
.equ RC_FILE_BYTES, RC_REQUEST + 28
.equ RC_CHECKPOINT, RC_REQUEST + 32
; 1 while one task runs rec_reader_poll. CommandTask and the UiTask frame (nr_reader_frame) both read the DSP ring, so a
; card write that blocks CommandTask longer than the ring lasts no longer starves the reader.
.equ RC_POLLER, RC_REQUEST + 36
; The longest checkpoint and the longest single card write of the take in ticks (plain READ via the public CONTEXT), and
; the tick a timed call started.
.equ RC_CHECK_TICKS, RC_REQUEST + 40
.equ RC_PIECE_TICKS, RC_REQUEST + 44
.equ RC_STAMP, RC_REQUEST + 48
; A checkpoint (sync, header at the file start, back to the end, sync) jumps around on the card, so it runs every five
; seconds of PCM: a power cut loses at most that much.
.equ RC_CHECK_BYTES, 480000
.equ RC_SIZE, 1536
.equ RC_READER_ERROR, 16
.equ RC_PIECE, 8192

; r0 context, r1 1 start or 0 stop. No allocation, DSP call or card operation.
recorder_command:
    push {r4-r6, lr}
    mov r4, r0
    mov r5, r1
    .word 0xE10F6000                 ; mrs r6, cpsr
    cmp r5, #1
    movhi r0, #RW_BAD_ARG
    bhi recorder_command_done
    orr r2, r6, #0xC0
    .word 0xE121F002                 ; msr cpsr_c, r2
    bl recorder_busy
    cmp r5, #0
    beq recorder_command_stop
    cmp r0, #0
    movne r0, #RW_BAD_STATE
    bne recorder_command_done
    mov r0, #1
    str r0, [r4, #RC_REQUEST]
    mov r0, #0
    b recorder_command_done
recorder_command_stop:
    cmp r0, #0
    movne r0, #2
    strne r0, [r4, #RC_REQUEST]
    mov r0, #0
recorder_command_done:
    .word 0xE121F006                 ; msr cpsr_c, r6
    pop {r4-r6, pc}
.pool

recorder_busy:
    ldr r1, [r0, #RC_ACTIVE]
    ldr r2, [r0, #RW_STATE]
    orr r1, r1, r2
    ldr r2, [r0, #RC_READER+RR_OWNED]
    orrs r1, r1, r2
    movne r0, #1
    bxne lr
    ldr r1, [r0, #RC_REQUEST]
    cmp r1, #1
    moveq r0, #1
    movne r0, #0
    bx lr

; One card write per running step; stop freezes capture before draining its tail.
recorder_pump:
    push {r4-r10, lr}
    mov r4, r0
    ldr r0, [r4, #RC_ACTIVE]
    cmp r0, #0
    beq recorder_idle
    cmp r0, #1
    beq recorder_active
    cmp r0, #2
    beq recorder_stop
    b recorder_return
recorder_idle:
    .word 0xE10FA000                 ; mrs r10, cpsr
    orr r2, r10, #0xC0
    .word 0xE121F002                 ; msr cpsr_c, r2
    ldr r0, [r4, #RC_REQUEST]
recorder_claim_loaded:
    cmp r0, #1
    mov r0, #0
    str r0, [r4, #RC_REQUEST]
    moveq r1, #3
    streq r1, [r4, #RC_ACTIVE]
    .word 0xE121F00A                 ; msr cpsr_c, r10
    bne recorder_return
    str r0, [r4, #RC_ERROR]
    str r0, [r4, #RC_DROPPED]
    str r0, [r4, #RC_FILE_BYTES]
    str r0, [r4, #RC_CHECKPOINT]
    str r0, [r4, #RC_CHECK_TICKS]
    str r0, [r4, #RC_PIECE_TICKS]
    ldr r0, [r4, #RC_CHANNELS]
    cmp r0, #RR_CHANNELS
    movne r0, #RW_BAD_ARG
    bne recorder_start_error
    ldr r0, [r4, #RC_CAPACITY]
    cmp r0, #131072
    movlo r0, #RW_BAD_ARG
    blo recorder_start_error
    add r0, r4, #RC_READER
    ldr r1, [r4, #RC_RING]
    ldr r2, [r4, #RC_CAPACITY]
    bl rec_reader_prepare
    cmp r0, #0
    addne r0, r0, #RC_READER_ERROR
    bne recorder_start_error
    mov r0, r4
    ldr r1, [r4, #RC_CHANNELS]
    bl rec_writer_open
    cmp r0, #0
    bne recorder_writer_error
    add r0, r4, #RC_READER
    ldr r1, [r4, #RC_RING]
    ldr r2, [r4, #RC_CAPACITY]
    bl rec_reader_begin
    cmp r0, #0
    addne r0, r0, #RC_READER_ERROR
    bne recorder_writer_error
    mov r0, #1
    str r0, [r4, #RC_ACTIVE]
recorder_active:
    ldr r0, [r4, #RC_REQUEST]
    cmp r0, #2
    beq recorder_stop_request
    mov r0, r4
    bl recorder_poll
    cmp r0, #0
    beq recorder_drain
    add r0, r0, #RC_READER_ERROR
recorder_writer_error:
    bl recorder_error
    mov r0, #2
    str r0, [r4, #RC_ACTIVE]
    b recorder_stop
recorder_start_error:
    str r0, [r4, #RC_ERROR]
    mov r0, #0
    str r0, [r4, #RC_ACTIVE]
    b recorder_return
recorder_stop_request:
    mov r0, #0
    str r0, [r4, #RC_REQUEST]
    mov r0, #2
    str r0, [r4, #RC_ACTIVE]
recorder_stop:
    ldr r0, [r4, #RC_POLLER]         ; RC_ACTIVE is no longer 1, so no new read starts; one still running ends first
    cmp r0, #0
    bne recorder_return
    ldr r0, [r4, #RC_READER+RR_OWNED]
    cmp r0, #0
    beq recorder_drain
    add r0, r4, #RC_READER
    bl rec_reader_finish
    cmp r0, #0
    addne r0, r0, #RC_READER_ERROR
    blne recorder_error
    ldr r0, [r4, #RC_READER+RR_OWNED]
    cmp r0, #0
    bne recorder_return
recorder_drain:
    add r5, r4, #RC_READER
    ldr r6, [r5, #RR_PRODUCED]
    ldr r7, [r5, #RR_CONSUMED]
    sub r6, r6, r7
    ldr r8, [r4, #RC_CAPACITY]
    cmp r6, r8
    bhi recorder_overflow
    ldr r0, [r4, #RW_STATUS]
    cmp r0, #0
    bne recorder_discard
    cmp r6, #0
    beq recorder_drained
    ldr r0, [r4, #RC_ACTIVE]
    cmp r6, #65536
    bhs recorder_full_block
    cmp r0, #2
    bne recorder_return
    mov r2, r6
    b recorder_write
recorder_full_block:
    mov r2, #65536
recorder_write:
    mov r10, r2
; A card write can stall longer than the 100 ms DSP ring, so the block goes out
; in pieces and the reader copies between them.
recorder_piece:
    mov r2, r10
    cmp r2, #RC_PIECE
    movhi r2, #RC_PIECE
    ldr r9, [r4, #RW_DATA_BYTES]
    ldr r0, =RW_MAX_DATA
    sub r0, r0, r9
    cmp r0, #0
    beq recorder_rotate
    cmp r2, r0
    movhi r2, r0
    sub r0, r8, #1
    and r0, r7, r0
    sub r1, r8, r0
    cmp r2, r1
    movhi r2, r1
    ldr r1, [r4, #RC_RING]
    add r1, r1, r0
    bl recorder_mark
    mov r0, r4
    bl rec_writer_append
    mov r6, r0
    ldr r1, =RC_PIECE_TICKS
    bl recorder_measure
    ldr r0, [r4, #RW_DATA_BYTES]
    str r0, [r4, #RC_FILE_BYTES]
    sub r0, r0, r9
    add r7, r7, r0
    str r7, [r5, #RR_CONSUMED]
    cmp r6, #0
    strne r6, [r4, #RW_STATUS]
    movne r0, r6
    bne recorder_writer_error
    subs r10, r10, r0
    beq recorder_checkpoint
    cmp r0, #0
    beq recorder_checkpoint
    ldr r0, [r4, #RC_ACTIVE]
    cmp r0, #1
    bne recorder_piece
    mov r0, r4
    bl recorder_poll
    cmp r0, #0
    beq recorder_piece
    add r0, r0, #RC_READER_ERROR
    b recorder_writer_error
recorder_rotate:
    mov r0, r4
    bl rec_writer_finish
    cmp r0, #0
    bne recorder_writer_error
    mov r0, r4
    ldr r1, [r4, #RC_CHANNELS]
    bl rec_writer_open
    cmp r0, #0
    strne r0, [r4, #RW_STATUS]
    bne recorder_writer_error
    mov r0, #0
    str r0, [r4, #RC_CHECKPOINT]
    str r0, [r4, #RC_FILE_BYTES]
    b recorder_return
recorder_checkpoint:
    ldr r0, [r4, #RC_ACTIVE]
    cmp r0, #1
    bne recorder_return
    ldr r0, [r4, #RW_DATA_BYTES]
    ldr r1, [r4, #RC_CHECKPOINT]
    sub r0, r0, r1
    ldr r2, =RC_CHECK_BYTES
    ldr r3, [r4, #RC_CHANNELS]
    mul r2, r3, r2
    cmp r0, r2
    blo recorder_return
    bl recorder_mark
    mov r0, r4
    bl rec_writer_checkpoint
    ldr r1, =RC_CHECK_TICKS
    bl recorder_measure
    cmp r0, #0
    bne recorder_writer_error
    ldr r0, [r4, #RW_DATA_BYTES]
    str r0, [r4, #RC_CHECKPOINT]
    b recorder_return
recorder_drained:
    ldr r0, [r4, #RC_ACTIVE]
    cmp r0, #2
    beq recorder_finish_file
    b recorder_return
recorder_overflow:
    mov r0, #RC_READER_ERROR+RR_OVERFLOW
    bl recorder_error
    bl recorder_drop
    mov r0, #2
    str r0, [r4, #RC_ACTIVE]
    b recorder_stop
recorder_discard:
    bl recorder_error
    ldr r0, [r4, #RC_ACTIVE]
    cmp r0, #2
    movne r0, #2
    strne r0, [r4, #RC_ACTIVE]
    bne recorder_stop
    bl recorder_drop
recorder_finish_file:
    ldr r0, [r4, #RW_STATE]
    cmp r0, #0
    beq recorder_closed
    mov r0, r4
    bl rec_writer_finish
    cmp r0, #0
    blne recorder_error
    ldr r0, [r4, #RW_STATE]
    cmp r0, #0
    bne recorder_return
recorder_closed:
    mov r0, #0
    str r0, [r4, #RC_ACTIVE]
    ldr r0, [r4, #RW_DATA_BYTES]
    str r0, [r4, #RC_FILE_BYTES]
recorder_return:
    ldr r0, [r4, #RC_ERROR]
    pop {r4-r10, pc}
.pool

; r0 context. Reads the DSP ring unless another task reads it now or the take is not running (RC_ACTIVE 1 claims under the
; interrupt mask, so a stop that sets RC_ACTIVE first sees every read still running). Returns the reader's status, also when
; it skipped.
recorder_poll:
    push {r4, r5, r6, lr}
    mov r4, r0
    .word 0xE10F5000                 ; mrs r5, cpsr
    orr r1, r5, #0xC0
    .word 0xE121F001                 ; msr cpsr_c, r1
    ldr r0, [r4, #RC_POLLER]
    ldr r1, [r4, #RC_ACTIVE]
    cmp r1, #1
    cmpeq r0, #0
    moveq r0, #1
    streq r0, [r4, #RC_POLLER]
    .word 0xE121F005                 ; msr cpsr_c, r5 (flags kept)
    ldrne r0, [r4, #RC_READER+RR_STATUS]
    bne recorder_poll_return
    add r0, r4, #RC_READER
    bl rec_reader_poll
    mov r1, #0
    str r1, [r4, #RC_POLLER]
recorder_poll_return:
    pop {r4, r5, r6, pc}

; r4 context. recorder_mark keeps r1 to r3, recorder_measure (r1 the field's offset) keeps r0.
recorder_mark:
    ldr r0, =RR_TICKS
    ldr r0, [r0]
    str r0, [r4, #RC_STAMP]
    bx lr

recorder_measure:
    add r1, r4, r1
    ldr r2, =RR_TICKS
    ldr r2, [r2]
    ldr r3, [r4, #RC_STAMP]
    sub r2, r2, r3
    ldr r3, [r1]
    cmp r2, r3
    strhi r2, [r1]
    bx lr

recorder_error:
    ldr r1, [r4, #RC_ERROR]
    cmp r1, #0
    bxne lr
    str r0, [r4, #RC_ERROR]
    mov r1, #0
    cmp r0, #RC_READER_ERROR+RR_GAP
    moveq r1, #1
    cmp r0, #RC_READER_ERROR+RR_LOST
    moveq r1, #2
    cmp r0, #RC_READER_ERROR+RR_OVERFLOW
    moveq r1, #3
    str r1, [r4, #RW_MARKER]
    bx lr

recorder_drop:
    ldr r0, [r5, #RR_PRODUCED]
    ldr r1, [r5, #RR_CONSUMED]
    sub r1, r0, r1
    ldr r2, [r4, #RC_DROPPED]
    adds r2, r2, r1
    mvncs r2, #0
    str r2, [r4, #RC_DROPPED]
    str r0, [r5, #RR_CONSUMED]
    bx lr
.pool
