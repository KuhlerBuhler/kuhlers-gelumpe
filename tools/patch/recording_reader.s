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
.equ RR_RAW_TARGET, 100
.equ RR_FAULT, 104
.equ RR_ACK, 128
.equ RR_CHECK, 132
.equ RR_STOP_ACK, 136
.equ RR_BACKLOG, 140
.equ RR_GAPS, 144
.equ RR_STOP_TICK, 148
.equ RR_SIZE, 152
.equ RR_DSP_BYTES, 19200
.equ RR_GUARD, 1024
; The DSP writes 192 bytes per tick (48 kHz stereo, 1 ms ticks). RR_BACKLOG keeps the unread bytes behind the DSP's
; pointer at the last good read; a read is too late once those plus 192 per tick since then could reach the cursor
; (RR_DSP_BYTES less RR_GUARD as margin). A late read does not end the take: the cursor jumps to half a ring behind the
; DSP's pointer, the bytes skipped go in as silence (so the time stays right) and RR_GAPS counts it.
.equ RR_RATE, 192
.equ RR_LATE, RR_DSP_BYTES-RR_GUARD
.equ RR_RESYNC, RR_DSP_BYTES/2
.equ RR_MAX_READ, 4096
.equ RR_OK, 0
.equ RR_BAD_STATE, 1
.equ RR_BUSY, 2
.equ RR_BAD_ARG, 3
.equ RR_GAP, 4
.equ RR_LOST, 5
.equ RR_NO_PATCH, 6
.equ RR_OVERFLOW, 7
; The DSP takes command 0x37 in its own time and then sets the source back to the input (INFO+12), so the source pointer is
; written only after INFO shows that, and a stop is judged only after it. RR_ACK and RR_STOP_ACK keep the ticks it took,
; all ones when it never showed within the bounds.
.equ RR_ACK_TICKS, 40
.equ RR_ACK_POLLS, 4096
; A stop the DSP still has not taken after RR_STOP_LIMIT ticks of retries is given up: the source goes back to the input,
; the capture word INFO[0] is cleared, the tap is switched off and the take ends, so a DSP that never answers cannot
; hold the recorder forever and the next take can start.
.equ RR_STOP_LIMIT, 1000
; RR_FAULT holds the first failure of a take, (place << 4) | check, then INFO[0], +4, +8, +12 (the source pointer) and +40
; as read when it failed. Places: 1 begin, 2 read before copying, 3 read after copying, 4 stop with a foreign capture,
; 5 stop left pending, 6 resync after a late read. Checks 1 to 6 are rec_reader_validate's in order, 7 the deadline, 8 overflow, 9 pending stop,
; 10 a stop given up.
; The runtime marks a copied fault with RR_FAULT_SEEN.
.equ RR_FAULT_SEEN, 0x100

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
    bl rec_reader_sampling
    mov r1, r0
    ldr r0, [r4, #RR_INFO]
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
    str r0, [r4, #RR_BACKLOG]
    str r0, [r4, #RR_GAPS]
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
    mov r0, #1
    bl rec_reader_acknowledge
    str r0, [r4, #RR_ACK]
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
    mov r0, #0x17
    bl rec_reader_fault
    mov r0, #RR_GAP
    b rec_begin_abort
rec_begin_lost:
    ldr r0, [r4, #RR_CHECK]
    orr r0, r0, #0x10
    bl rec_reader_fault
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
    mov r2, #RR_INFO_HALFWORDS
    mov r3, #2
    ldr r12, =RR_FW_READ
    blx r12
    pop {r3, pc}
.pool

; r0 the INFO[0] the command leaves (1 start, 0 stop); returns the ticks it took or all ones.
rec_reader_acknowledge:
    push {r5-r7, lr}
    mov r7, r0
    ldr r0, =RR_TICKS
    ldr r5, [r0]
    ldr r6, =RR_ACK_POLLS
rec_ack_poll:
    bl rec_reader_info
    ldr r0, [r4, #RR_INFO]
    cmp r0, r7
    bne rec_ack_wait
    ldr r0, [r4, #RR_INFO+12]
    ldr r1, =RR_INPUT
    cmp r0, r1
    beq rec_ack_done
rec_ack_wait:
    ldr r0, =RR_TICKS
    ldr r0, [r0]
    sub r0, r0, r5
    cmp r0, #RR_ACK_TICKS
    bhs rec_ack_late
    subs r6, r6, #1
    bne rec_ack_poll
rec_ack_late:
    mvn r0, #0
    pop {r5-r7, pc}
rec_ack_done:
    ldr r0, =RR_TICKS
    ldr r0, [r0]
    sub r0, r0, r5
    pop {r5-r7, pc}
.pool

; r0 the fault code; only the first fault of a take is kept.
rec_reader_fault:
    ldr r1, [r4, #RR_FAULT]
    cmp r1, #0
    bxne lr
    str r0, [r4, #RR_FAULT]
    ldr r0, [r4, #RR_INFO]
    str r0, [r4, #RR_FAULT+4]
    ldr r0, [r4, #RR_INFO+4]
    str r0, [r4, #RR_FAULT+8]
    ldr r0, [r4, #RR_INFO+8]
    str r0, [r4, #RR_FAULT+12]
    ldr r0, [r4, #RR_INFO+12]
    str r0, [r4, #RR_FAULT+16]
    ldr r0, [r4, #RR_INFO+40]
    str r0, [r4, #RR_FAULT+20]
    bx lr

rec_reader_sampling:
    mov r0, #RR_HAS_SAMPLING
    cmp r0, #0
    ldrne r0, [r4, #RR_INFO+40]
    bx lr

; r0 0: active master capture, 1: stopped capture with Korg's source reset.
rec_reader_validate:
    mov r12, r0
    rsb r1, r0, #1
    mov r2, #1
    ldr r0, [r4, #RR_INFO]
    cmp r0, r1
    bne rec_info_no
    mov r2, #2
    ldr r0, [r4, #RR_INFO+4]
    ldr r1, =RR_DSP_BYTES
    cmp r0, r1
    bne rec_info_no
    mov r2, #3
    ldr r0, [r4, #RR_INFO+12]
    cmp r12, #0
    ldreq r1, =RR_CAPTURE
    ldrne r1, =RR_INPUT
    cmp r0, r1
    bne rec_info_no
    mov r2, #4
    ldr r0, [r4, #RR_INFO+40]
    cmp r0, #0
    bne rec_info_no
    mov r2, #5
    ldr r0, [r4, #RR_INFO+8]
    ldr r1, =RR_DSP_RING
    cmp r0, r1
    blo rec_info_no
    ldr r1, =RR_DSP_RING+RR_DSP_BYTES
    cmp r0, r1
    bhs rec_info_no
    mov r2, #6
    tst r0, #3
    bne rec_info_no
    mov r0, #1
    bx lr
rec_info_no:
    str r2, [r4, #RR_CHECK]
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
    movne r0, #0x27
    bne rec_read_gap
    mov r11, r1
    bl rec_reader_info
    ldr r0, [r4, #RR_MODE]
    bl rec_reader_validate
    cmp r0, #1
    movne r0, #0x20
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
    mov r1, r5
    mov r2, #RR_CHANNELS
    cmp r2, #1
    moveq r1, r5, lsr #1
    cmp r1, r0
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
    mov r2, #RR_CHANNELS
    cmp r2, #1
    bne rec_read_target
    ldr r0, [r4, #RR_CONSUMED]
    sub r0, r7, r0
    sub r0, r8, r0
    cmp r10, r0
    movhi r10, r0
    bic r10, r10, #3
    cmp r10, #0
    addeq r1, r4, #RR_TEMP
    moveq r10, #4
rec_read_target:
    str r1, [r4, #RR_RAW_TARGET]
    mov r0, r6
    mov r2, r10, lsr #1
    mov r3, #2
    ldr r12, =RR_FW_READ
    blx r12
    sub r1, r8, #1
    and r1, r7, r1
    add r1, r9, r1
    mov r2, #RR_CHANNELS
    cmp r2, #1
    beq rec_read_mono
    mov r2, r10, lsr #2
rec_read_swap:
    ldr r0, [r1]
    mov r0, r0, ror #16
    str r0, [r1], #4
    subs r2, r2, #1
    bne rec_read_swap
    b rec_read_advance
rec_read_mono:
    ldr r2, [r4, #RR_RAW_TARGET]
    add r2, r2, #2
    mov r3, r10, lsr #2
rec_read_mono_sample:
    ldrb r0, [r2]
    strb r0, [r1], #1
    ldrb r0, [r2, #1]
    strb r0, [r1], #1
    add r2, r2, #4
    subs r3, r3, #1
    bne rec_read_mono_sample
rec_read_advance:
    add r6, r6, r10
    ldr r0, =RR_DSP_RING+RR_DSP_BYTES
    cmp r6, r0
    subhs r6, r6, #RR_DSP_BYTES
    mov r0, #RR_CHANNELS
    cmp r0, #1
    moveq r0, r10, lsr #1
    movne r0, r10
    add r7, r7, r0
    sub r5, r5, r10
    b rec_read_chunk
rec_read_verify:
    bl rec_reader_info
    ldr r0, [r4, #RR_MODE]
    bl rec_reader_validate
    cmp r0, #1
    movne r0, #0x30
    bne rec_read_lost
    bl rec_reader_deadline
    cmp r0, #0
    movne r0, #0x37
    bne rec_read_gap
    ldr r0, [r4, #RR_INFO+8]
    subs r0, r0, r6
    addlo r0, r0, #RR_DSP_BYTES
    str r0, [r4, #RR_BACKLOG]
rec_read_commit:
    str r11, [r4, #RR_TICK]
    str r6, [r4, #RR_CURSOR]
    str r7, [r4, #RR_PRODUCED]
    mov r0, #RR_OK
    b rec_read_return
; Late: drop what this call copied, estimate the bytes the DSP wrote past the old cursor, fill all of them but the half
; ring still unread with silence, as far as the ARM ring has room, and go on from there. The ticks are capped at 0xFFFF
; only to keep the product in 32 bits; that much silence never fits the largest ring (2 MiB) anyway.
rec_read_gap:
    bl rec_reader_fault
    ldr r0, [r4, #RR_GAPS]
    add r0, r0, #1
    str r0, [r4, #RR_GAPS]
    ldr r0, =RR_TICKS
    ldr r11, [r0]
    ldr r1, [r4, #RR_TICK]
    sub r0, r11, r1
    ldr r1, =0xFFFF
    cmp r0, r1
    movhi r0, r1
    mov r1, #RR_RATE
    mul r5, r0, r1
    ldr r0, [r4, #RR_BACKLOG]
    add r5, r5, r0
    ldr r0, =RR_RESYNC
    subs r5, r5, r0
    movlo r5, #0
    bic r5, r5, #3
    bl rec_reader_info
    ldr r0, [r4, #RR_MODE]
    bl rec_reader_validate
    cmp r0, #1
    movne r0, #0x60
    bne rec_read_lost
    ldr r6, [r4, #RR_INFO+8]
    ldr r0, =RR_RESYNC
    sub r6, r6, r0
    ldr r0, =RR_DSP_RING
    cmp r6, r0
    addlo r6, r6, #RR_DSP_BYTES
    ldr r7, [r4, #RR_PRODUCED]
    ldr r8, [r4, #RR_CAPACITY]
    ldr r9, [r4, #RR_ARM_RING]
    ldr r0, [r4, #RR_CONSUMED]
    sub r0, r7, r0
    sub r10, r8, r0
    mov r0, #RR_CHANNELS
    cmp r0, #1
    moveq r5, r5, lsr #1
    cmp r5, r10
    movhi r5, r10
    bic r5, r5, #1
    sub r1, r8, #1
    mov r2, #0
rec_read_silence:
    subs r5, r5, #2
    bmi rec_read_resynced
    and r0, r7, r1
    add r3, r9, r0
    strb r2, [r3]
    strb r2, [r3, #1]
    add r7, r7, #2
    b rec_read_silence
rec_read_resynced:
    ldr r0, =RR_RESYNC
    str r0, [r4, #RR_BACKLOG]
    b rec_read_commit
rec_read_lost:
    ldr r1, [r4, #RR_CHECK]
    orr r0, r0, r1
    bl rec_reader_fault
    mov r0, #RR_LOST
    b rec_read_status
rec_read_overflow:
    mov r0, #0x28
    bl rec_reader_fault
    mov r0, #RR_OVERFLOW
rec_read_status:
    str r0, [r4, #RR_STATUS]
rec_read_return:
    add sp, sp, #4
    pop {r4-r11, pc}
.pool

; -> r0 1 when late, r1 the tick it read; keeps r4 to r12.
rec_reader_deadline:
    ldr r0, =RR_TICKS
    ldr r1, [r0]
    ldr r0, [r4, #RR_TICK]
    sub r0, r1, r0
    cmp r0, #RR_DSP_BYTES/RR_RATE
    movhs r0, #1
    bxhs lr
    mov r2, #RR_RATE
    mul r3, r0, r2
    ldr r2, [r4, #RR_BACKLOG]
    add r3, r3, r2
    ldr r2, =RR_LATE
    cmp r3, r2
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
    bl rec_reader_sampling
    cmp r0, #0
    bne rec_stop_foreign
rec_stop_native:
    ldr r12, =RR_FW_END
    blx r12
    mov r0, #0
    bl rec_reader_acknowledge
    str r0, [r4, #RR_STOP_ACK]
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
    ldr r0, [r4, #RR_CHECK]
    orr r0, r0, #0x40
    bl rec_reader_fault
    ldr r0, [r4, #RR_STATUS]
    cmp r0, #0
    moveq r0, #RR_LOST
    str r0, [r4, #RR_STATUS]
rec_stop_clear:
    mov r0, #0
    str r0, [r4, #RR_STOP_TICK]
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
    ldr r0, =RR_TICKS
    ldr r0, [r0]
    ldr r1, [r4, #RR_STOP_TICK]
    cmp r1, #0
    beq rec_stop_first
    sub r0, r0, r1
    ldr r1, =RR_STOP_LIMIT
    cmp r0, r1
    bhs rec_stop_give_up
    b rec_stop_wait
rec_stop_first:
    cmp r0, #0
    moveq r0, #1
    str r0, [r4, #RR_STOP_TICK]
rec_stop_wait:
    mov r0, #0x59
    bl rec_reader_fault
    bl rec_stop_lost
    b rec_stop_return
rec_stop_give_up:
    mov r0, #0x5A
    bl rec_reader_fault
    bl rec_stop_lost
    ldr r0, [r4, #RR_INFO+12]
    ldr r1, =RR_CAPTURE
    cmp r0, r1
    bne rec_stop_release
    ldr r0, =RR_INPUT
    str r0, [r4, #RR_TEMP]
    ldr r0, =RR_SOURCE_POINTER
    add r1, r4, #RR_TEMP
    mov r2, #2
    bl rec_reader_write
rec_stop_release:
    mov r0, #0
    str r0, [r4, #RR_TEMP]
    ldr r0, =RR_DSP_STATE
    add r1, r4, #RR_TEMP
    mov r2, #2
    bl rec_reader_write
    b rec_stop_clear
rec_stop_return:
    pop {r4-r8, pc}
.pool

rec_stop_lost:
    ldr r0, [r4, #RR_STATUS]
    cmp r0, #0
    moveq r0, #RR_LOST
    str r0, [r4, #RR_STATUS]
    bx lr

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
