; One task owns this context; the controller serializes capture start and stop.
.equ RR_STATUS, 0
.equ RR_OWNED, 4
.equ RR_ARM_RING, 8
.equ RR_CAPACITY, 12
.equ RR_PRODUCED, 16
.equ RR_CONSUMED, 20
.equ RR_CURSOR, 24
.equ RR_TICK, 28
.equ RR_INFO, 32
.equ RR_TEMP, 80
.equ RR_MODE, 96
.equ RR_SIZE, 128
.equ RR_DSP_STATE, 0xFF9031D0
.equ RR_SOURCE_POINTER, 0xFF9031DC
.equ RR_DSP_RING, 0x01C722A0
.equ RR_DSP_BYTES, 19200
.equ RR_INPUT, 0xFF802878
.equ RR_GUARD, 1024
.equ RR_MAX_GAP, 80
.equ RR_MAX_READ, 4096
.equ RR_OK, 0
.equ RR_BAD_STATE, 1
.equ RR_BUSY, 2
.equ RR_BAD_ARG, 3
.equ RR_GAP, 4
.equ RR_LOST, 5
.equ RR_NO_PATCH, 6
.equ RR_OVERFLOW, 7

; r0 zeroed context, r1 ARM ring, r2 power-of-two capacity (64 KiB to 2 MiB).
rec_reader_prepare:
    push {r4-r8, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    ldr r0, [r4, #RR_OWNED]
    cmp r0, #0
    movne r0, #RR_BAD_STATE
    bne rec_prepare_return
    cmp r5, #0
    beq rec_prepare_bad
    tst r5, #3
    bne rec_prepare_bad
    cmp r6, #65536
    blo rec_prepare_bad
    cmp r6, #2097152
    bhi rec_prepare_bad
    sub r0, r6, #1
    tst r6, r0
    bne rec_prepare_bad
    adds r0, r5, r6
    bcs rec_prepare_bad
    ldr r0, =RR_MAGIC_ADDRESS
    add r1, r4, #RR_TEMP
    mov r2, #2
    mov r3, #2
    ldr r12, =RR_FW_READ
    blx r12
    ldr r0, [r4, #RR_TEMP]
    ldr r1, =RR_MAGIC
    cmp r0, r1
    movne r0, #RR_NO_PATCH
    bne rec_prepare_status
    bl rec_reader_info
    ldr r0, [r4, #RR_INFO]
    ldr r1, [r4, #RR_INFO+40]
    orrs r0, r0, r1
    movne r0, #RR_BUSY
    bne rec_prepare_status
    mov r0, #RR_OK
    b rec_prepare_return
rec_prepare_bad:
    mov r0, #RR_BAD_ARG
    b rec_prepare_return
rec_prepare_status:
    str r0, [r4, #RR_STATUS]
rec_prepare_return:
    pop {r4-r8, pc}
.pool

rec_reader_begin:
    push {r4-r8, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    bl rec_reader_prepare
    cmp r0, #0
    bne rec_begin_return
    str r5, [r4, #RR_ARM_RING]
    str r6, [r4, #RR_CAPACITY]
    mov r0, #0
    str r0, [r4, #RR_STATUS]
    str r0, [r4, #RR_PRODUCED]
    str r0, [r4, #RR_CONSUMED]
    str r0, [r4, #RR_TEMP]
    str r0, [r4, #RR_TEMP+4]
    str r0, [r4, #RR_TEMP+8]
    mov r0, #1
    str r0, [r4, #RR_TEMP+12]
    ldr r0, =RR_TAP_STATE
    add r1, r4, #RR_TEMP
    mov r2, #8
    bl rec_reader_write
    mov r0, #0
    ldr r12, =RR_FW_BEGIN
    blx r12
    mov r0, #2
    str r0, [r4, #RR_OWNED]
    ldr r0, =RR_CAPTURE
    str r0, [r4, #RR_TEMP]
    ldr r0, =RR_SOURCE_POINTER
    add r1, r4, #RR_TEMP
    mov r2, #2
    bl rec_reader_write
    ldr r0, =RR_TICKS
    ldr r0, [r0]
    str r0, [r4, #RR_TICK]
    bl rec_reader_info
    mov r0, #0
    bl rec_reader_validate
    cmp r0, #1
    bne rec_begin_lost
    bl rec_reader_deadline
    cmp r0, #0
    bne rec_begin_gap
    ldr r0, [r4, #RR_INFO+8]
    str r0, [r4, #RR_CURSOR]
    mov r0, #1
    str r0, [r4, #RR_OWNED]
    mov r0, #RR_OK
    b rec_begin_status
rec_begin_gap:
    mov r0, #RR_GAP
    b rec_begin_abort
rec_begin_lost:
    mov r0, #RR_LOST
rec_begin_abort:
    str r0, [r4, #RR_STATUS]
    mov r0, r4
    bl rec_reader_finish
    b rec_begin_return
rec_begin_status:
    str r0, [r4, #RR_STATUS]
rec_begin_return:
    pop {r4-r8, pc}
.pool

rec_reader_info:
    push {r3, lr}
    ldr r0, =RR_DSP_STATE
    add r1, r4, #RR_INFO
    mov r2, #22
    mov r3, #2
    ldr r12, =RR_FW_READ
    blx r12
    pop {r3, pc}
.pool

; r0 0: active master capture, 1: stopped capture with Korg's source reset.
rec_reader_validate:
    mov r12, r0
    rsb r1, r0, #1
    ldr r0, [r4, #RR_INFO]
    cmp r0, r1
    bne rec_info_no
    ldr r0, [r4, #RR_INFO+4]
    ldr r1, =RR_DSP_BYTES
    cmp r0, r1
    bne rec_info_no
    ldr r0, [r4, #RR_INFO+12]
    cmp r12, #0
    ldreq r1, =RR_CAPTURE
    ldrne r1, =RR_INPUT
    cmp r0, r1
    bne rec_info_no
    ldr r0, [r4, #RR_INFO+40]
    cmp r0, #0
    bne rec_info_no
    ldr r0, [r4, #RR_INFO+8]
    ldr r1, =RR_DSP_RING
    cmp r0, r1
    blo rec_info_no
    ldr r1, =RR_DSP_RING+RR_DSP_BYTES
    cmp r0, r1
    bhs rec_info_no
    tst r0, #3
    bne rec_info_no
    mov r0, #1
    bx lr
rec_info_no:
    mov r0, #0
    bx lr
.pool

rec_reader_poll:
    mov r1, #0
rec_reader_read:
    push {r4-r11, lr}
    sub sp, sp, #4
    mov r4, r0
    str r1, [r4, #RR_MODE]
    ldr r0, [r4, #RR_OWNED]
    cmp r0, #1
    movne r0, #RR_BAD_STATE
    bne rec_read_return
    ldr r0, [r4, #RR_STATUS]
    cmp r0, #0
    bne rec_read_return
    bl rec_reader_deadline
    cmp r0, #0
    bne rec_read_gap
    mov r11, r1
    bl rec_reader_info
    ldr r0, [r4, #RR_MODE]
    bl rec_reader_validate
    cmp r0, #1
    bne rec_read_lost
    ldr r6, [r4, #RR_CURSOR]
    ldr r5, [r4, #RR_INFO+8]
    subs r5, r5, r6
    addlo r5, r5, #RR_DSP_BYTES
    ldr r0, [r4, #RR_MODE]
    cmp r0, #0
    bne rec_read_capacity
    cmp r5, #RR_GUARD
    movls r5, #0
    subhi r5, r5, #RR_GUARD
rec_read_capacity:
    ldr r7, [r4, #RR_PRODUCED]
    ldr r8, [r4, #RR_CAPACITY]
    ldr r9, [r4, #RR_ARM_RING]
    ldr r0, [r4, #RR_CONSUMED]
    sub r0, r7, r0
    cmp r0, r8
    bhi rec_read_overflow
    sub r0, r8, r0
    cmp r5, r0
    bhi rec_read_overflow
rec_read_chunk:
    cmp r5, #0
    beq rec_read_verify
    mov r10, #RR_MAX_READ
    cmp r10, r5
    movhi r10, r5
    ldr r0, =RR_DSP_RING+RR_DSP_BYTES
    sub r0, r0, r6
    cmp r10, r0
    movhi r10, r0
    sub r1, r8, #1
    and r1, r7, r1
    sub r0, r8, r1
    cmp r10, r0
    movhi r10, r0
    add r1, r9, r1
    mov r0, r6
    mov r2, r10, lsr #1
    mov r3, #2
    ldr r12, =RR_FW_READ
    blx r12
    sub r1, r8, #1
    and r1, r7, r1
    add r1, r9, r1
    mov r2, r10, lsr #2
rec_read_swap:
    ldr r0, [r1]
    mov r0, r0, ror #16
    str r0, [r1], #4
    subs r2, r2, #1
    bne rec_read_swap
    add r6, r6, r10
    ldr r0, =RR_DSP_RING+RR_DSP_BYTES
    cmp r6, r0
    subhs r6, r6, #RR_DSP_BYTES
    add r7, r7, r10
    sub r5, r5, r10
    b rec_read_chunk
rec_read_verify:
    bl rec_reader_info
    ldr r0, [r4, #RR_MODE]
    bl rec_reader_validate
    cmp r0, #1
    bne rec_read_lost
    bl rec_reader_deadline
    cmp r0, #0
    bne rec_read_gap
    str r11, [r4, #RR_TICK]
    str r6, [r4, #RR_CURSOR]
    str r7, [r4, #RR_PRODUCED]
    mov r0, #RR_OK
    b rec_read_return
rec_read_gap:
    mov r0, #RR_GAP
    b rec_read_status
rec_read_lost:
    mov r0, #RR_LOST
    b rec_read_status
rec_read_overflow:
    mov r0, #RR_OVERFLOW
rec_read_status:
    str r0, [r4, #RR_STATUS]
rec_read_return:
    add sp, sp, #4
    pop {r4-r11, pc}
.pool

rec_reader_deadline:
    ldr r0, =RR_TICKS
    ldr r1, [r0]
    ldr r0, [r4, #RR_TICK]
    sub r0, r1, r0
    cmp r0, #RR_MAX_GAP
    movlo r0, #0
    movhs r0, #1
    bx lr
.pool

; A failed native stop retains ownership so the controller can retry it.
rec_reader_finish:
    push {r4-r8, lr}
    mov r4, r0
    ldr r5, [r4, #RR_OWNED]
    cmp r5, #1
    beq rec_stop_info
    cmp r5, #2
    movne r0, #RR_BAD_STATE
    bne rec_stop_return
rec_stop_info:
    bl rec_reader_info
    mov r0, #0
    bl rec_reader_validate
    cmp r0, #1
    beq rec_stop_native
    cmp r5, #2
    bne rec_stop_foreign
    ldr r0, [r4, #RR_INFO]
    cmp r0, #1
    bne rec_stop_foreign
    ldr r0, [r4, #RR_INFO+12]
    ldr r1, =RR_INPUT
    cmp r0, r1
    bne rec_stop_foreign
    ldr r0, [r4, #RR_INFO+40]
    cmp r0, #0
    bne rec_stop_foreign
rec_stop_native:
    ldr r12, =RR_FW_END
    blx r12
    bl rec_reader_info
    ldr r0, [r4, #RR_INFO]
    cmp r0, #1
    bne rec_stop_tail
    ldr r0, [r4, #RR_INFO+12]
    ldr r1, =RR_CAPTURE
    cmp r0, r1
    beq rec_stop_pending
    cmp r5, #2
    bne rec_stop_tail
    ldr r1, =RR_INPUT
    cmp r0, r1
    beq rec_stop_pending
rec_stop_tail:
    mov r0, r4
    mov r1, #1
    bl rec_reader_read
    b rec_stop_clear
rec_stop_foreign:
    ldr r0, [r4, #RR_STATUS]
    cmp r0, #0
    moveq r0, #RR_LOST
    str r0, [r4, #RR_STATUS]
rec_stop_clear:
    mov r0, #0
    str r0, [r4, #RR_TEMP]
    ldr r0, =RR_ENABLE
    add r1, r4, #RR_TEMP
    mov r2, #2
    bl rec_reader_write
    mov r0, #0
    str r0, [r4, #RR_OWNED]
    ldr r0, [r4, #RR_STATUS]
    b rec_stop_return
rec_stop_pending:
    ldr r0, [r4, #RR_STATUS]
    cmp r0, #0
    moveq r0, #RR_LOST
    str r0, [r4, #RR_STATUS]
rec_stop_return:
    pop {r4-r8, pc}
.pool

; Exact host-port writes under the firmware's DSP lock.
rec_reader_write:
    push {r4-r8, lr}
    sub sp, sp, #8
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r0, #1
    ldr r12, =RR_FW_LOCK
    blx r12
    ldr r12, =RR_FW_GET
    blx r12
    mov r1, r4
    mov r2, r5
    mov r3, r6
    mov r7, #2
    str r7, [sp]
    ldr r12, =RR_FW_WRITE_RAW
    blx r12
    mov r0, #1
    ldr r12, =RR_FW_UNLOCK
    blx r12
    add sp, sp, #8
    pop {r4-r8, pc}
.pool
