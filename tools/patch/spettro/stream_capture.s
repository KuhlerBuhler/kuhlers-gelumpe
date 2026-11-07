; Guarded native capture reader for the experimental spectrum add-on.
; stream_poll(ctx), CommandTask only, capture already owned by caller.
; Caller supplies zeroed 19328-byte context and expected DSP source at +8.
; +0 guarded read cursor, +4 last poll tick, +8 source, +12 valid bytes,
; +16 total frames, +20 status, +64 info[44], +128 raw[19200].
; Status 0 OK (possibly no new data), 1 primed, 3 lost/invalid DSP state,
; 4 gap/ambiguous wrap, 5 snapshot overwritten. Failure resets reader.
.equ S_READ, 0xC00141F8
.equ S_TICKS, 0xC06A292C
.equ S_STATE, 0xFF9031D0
.equ S_BASE, 0x01C722A0
.equ S_END, 0x01C76DA0
.equ S_BYTES, 19200
.equ S_GUARD, 1024
stream_poll:
    push {r3-r11, lr}
    mov r4, r0
    mov r0, #0
    str r0, [r4, #12]
    ldr r0, =S_TICKS
    ldr r8, [r0]
    bl stream_info
    bl stream_valid
    cmp r0, #1
    bne stream_lost
    ldr r9, [r4, #72]
    sub r6, r9, #S_GUARD
    ldr r0, =S_BASE
    cmp r6, r0
    ldrlo r0, =S_BYTES
    addlo r6, r6, r0
    ldr r10, [r4]
    cmp r10, #0
    beq stream_prime
    ldr r0, [r4, #4]
    sub r0, r8, r0
    cmp r0, #80
    bhs stream_gap
    ; Validate even a caller-supplied previous cursor before any transfer.
    ldr r0, =S_BASE
    cmp r10, r0
    blo stream_gap
    ldr r0, =S_END
    cmp r10, r0
    bhs stream_gap
    tst r10, #3
    bne stream_gap
    sub r7, r6, r10
    cmp r7, #0
    ldrlt r0, =S_BYTES
    addlt r7, r7, r0
    cmp r7, #0
    beq stream_success
    add r0, r7, #S_GUARD
    ldr r1, =S_BYTES
    cmp r0, r1
    bhs stream_gap
    ldr r11, =S_END
    sub r11, r11, r10
    cmp r11, r7
    movhi r11, r7
    mov r0, r10
    add r1, r4, #128
    mov r2, r11, lsr #1
    mov r3, #2
    bl S_READ
    sub r0, r7, r11
    cmp r0, #0
    beq stream_check
    mov r2, r0, lsr #1
    ldr r0, =S_BASE
    add r1, r4, #128
    add r1, r1, r11
    mov r3, #2
    bl S_READ
stream_check:
    bl stream_info
    bl stream_valid
    cmp r0, #1
    bne stream_lost
    ldr r0, =S_TICKS
    ldr r0, [r0]
    sub r0, r0, r8
    cmp r0, #80
    bhs stream_stale
    mov r1, #192
    mul r2, r0, r1
    ldr r3, =S_BYTES - S_GUARD
    sub r3, r3, r7
    cmp r2, r3
    bhs stream_stale
    ldr r0, [r4, #72]
    sub r0, r0, r9
    cmp r0, #0
    ldrlt r1, =S_BYTES
    addlt r0, r0, r1
    cmp r0, r3
    bhs stream_stale
stream_success:
    str r6, [r4]
    str r8, [r4, #4]
    str r7, [r4, #12]
    ldr r0, [r4, #16]
    add r0, r0, r7, lsr #2
    str r0, [r4, #16]
    mov r0, #0
    b stream_return
stream_prime:
    str r6, [r4]
    str r8, [r4, #4]
    mov r0, #1
    b stream_return
stream_lost:
    mov r0, #3
    b stream_reset
stream_gap:
    mov r0, #4
    b stream_reset
stream_stale:
    mov r0, #5
stream_reset:
    mov r1, #0
    str r1, [r4]
stream_return:
    str r0, [r4, #20]
    pop {r3-r11, pc}
stream_info:
    push {r3, lr}
    ldr r0, =S_STATE
    add r1, r4, #64
    mov r2, #22
    mov r3, #2
    bl S_READ
    pop {r3, pc}
stream_valid:
    ldr r0, [r4, #64]
    cmp r0, #1
    bne stream_no
    ldr r0, [r4, #68]
    ldr r1, =S_BYTES
    cmp r0, r1
    bne stream_no
    ldr r0, [r4, #76]
    ldr r1, [r4, #8]
    cmp r0, r1
    bne stream_no
    ldr r0, [r4, #104]
    cmp r0, #0
    bne stream_no
    ldr r0, [r4, #72]
    ldr r1, =S_BASE
    cmp r0, r1
    blo stream_no
    ldr r1, =S_END
    cmp r0, r1
    bhs stream_no
    tst r0, #3
    bne stream_no
    mov r0, #1
    bx lr
stream_no:
    mov r0, #0
    bx lr
.pool
