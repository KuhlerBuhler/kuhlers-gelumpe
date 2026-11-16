; From Spettro by Luigi (GitHub reflectiveboi, PR #429), taken into the BLECH runtime as the service behind korg.audio (API 31).
; Continuous reader -> 4096-frame window -> native spectrum -> completed bitmap.
; Linked by spectrum_build.py; retains existing adapter request/status ABI.
.equ SP_STREAM, 8192
.equ SP_FFT, 28672
.equ SP_TWIDDLE, 61440
.equ SP_ROLL, 77824
.equ SP_POWER, 94208
; ctx +120 next ring word, +124 fill, +128 coefficient ready, +132 FFT tick.
scope_service:
    push {r3-r11, lr}
    mov r4, r0
    ldr r0, =OS_TICKS
    ldr r5, [r0]
    ldr r0, [r4, #32]
    sub r0, r5, r0
    cmp r0, #20
    blo sp_return
    str r5, [r4, #32]
    ldr r0, [r4, #36]
    cmp r0, #0
    beq sp_close
    cmp r0, #1
    bne sp_bad
    ldr r6, [r4, #40]
    cmp r6, #15
    bhi sp_bad
    ldr r7, [r4, #44]
    cmp r7, #1
    bhi sp_bad
    ldr r0, [r4, #48]
    cmp r0, #2
    bhi sp_bad
    ldr r0, [r4, #52]
    cmp r0, #9
    blo sp_bad
    cmp r0, #15
    bhi sp_bad
    cmp r7, #0
    ldreq r0, =0x118
    moveq r1, r6
    ldrne r0, =0x230
    movne r1, r6, lsr #1
    mul r8, r1, r0
    ldreq r0, =0xFF90197C
    ldrne r0, =0xFF901A98
    add r8, r8, r0
    ldr r0, [r4, #4]
    cmp r0, #1
    bne sp_begin
    ldr r0, [r4, #8]
    cmp r0, r8
    beq sp_poll
    mov r0, r4
    bl scope_close
sp_begin:
    bl sp_reset
    mov r0, r4
    mov r1, r6
    mov r2, r7
    bl scope_begin
    b sp_return
sp_poll:
    add r0, r4, #SP_STREAM
    str r8, [r0, #8]
    bl stream_poll
    cmp r0, #0
    beq sp_append
    cmp r0, #1
    beq sp_waiting
    cmp r0, #3
    moveq r1, #0
    streq r1, [r4, #4]
    bl sp_reset
    mov r0, #STALE
    str r0, [r4, #28]
    b sp_return
sp_waiting:
    mov r0, #FILLING
    str r0, [r4, #28]
    b sp_return
sp_append:
    add r0, r4, #SP_STREAM
    ldr r6, [r0, #12]
    cmp r6, #0
    beq sp_return
    mov r6, r6, lsr #2
    add r5, r0, #128
    ldr r7, [r4, #120]
    ldr r8, =SP_ROLL
    add r8, r4, r8
    ldr r9, =4095
    ldr r10, [r4, #124]
sp_append_word:
    ldr r0, [r5], #4
    str r0, [r8, r7, lsl #2]
    add r7, r7, #1
    and r7, r7, r9
    cmp r10, #4096
    addlo r10, r10, #1
    subs r6, r6, #1
    bne sp_append_word
    str r7, [r4, #120]
    str r10, [r4, #124]
    cmp r10, #4096
    blo sp_waiting
    ldr r0, [r4, #60]
    cmp r0, #0
    beq sp_not_frozen
    ldr r0, [r4, #56]
    cmp r0, #0
    beq sp_waiting
    b sp_draw
sp_not_frozen:
    ldr r0, =OS_TICKS
    ldr r5, [r0]
    ldr r0, [r4, #132]
    sub r0, r5, r0
    cmp r0, #50
    blo sp_return
    str r5, [r4, #132]
    ; Reuse the drained stream scratch as a contiguous chronological window.
    add r5, r4, #SP_STREAM
    add r5, r5, #128
    mov r6, #4096
sp_linearize:
    ldr r0, [r8, r7, lsl #2]
    str r0, [r5], #4
    add r7, r7, #1
    and r7, r7, r9
    subs r6, r6, #1
    bne sp_linearize
    ldr r0, [r4, #128]
    cmp r0, #1
    beq sp_coeff_ready
    ldr r0, =SP_TWIDDLE
    add r0, r4, r0
    bl fft_coefficients
    mov r0, #1
    str r0, [r4, #128]
sp_coeff_ready:
    mov r6, #0
sp_channel:
    add r0, r4, #SP_STREAM
    add r0, r0, #128
    ldr r1, =SP_FFT
    add r1, r4, r1
    ldr r2, =SP_TWIDDLE
    add r2, r4, r2
    mov r3, r6
    bl fft_prepare
    ldr r0, =SP_FFT
    add r0, r4, r0
    ldr r1, =SP_TWIDDLE
    add r1, r4, r1
    bl fft4096
    ldr r0, =SP_FFT
    add r0, r4, r0
    ldr r1, =SP_POWER
    add r1, r4, r1
    mov r2, #0
    ldr r3, [r4, #48]
    cmp r3, #2
    moveq r2, #1
    cmp r6, #2
    moveq r2, #2
    bl fft_power
    ldr r0, [r4, #48]
    cmp r0, #2
    bne sp_draw
    cmp r6, #0
    moveq r6, #2
    beq sp_channel
sp_draw:
    ldr r1, =FRAME_A
    add r8, r4, r1
    ldr r0, [r4, #56]
    cmp r0, r8
    ldreq r1, =FRAME_B
    addeq r8, r4, r1
    ; BLECH: the frame holds 128 columns of the full range, 128 of the bass range and 256 frames of wave for korg.audio.
    ldr r0, =SP_POWER
    add r0, r4, r0
    mov r1, r8
    ldr r2, =spectrum_bins_full
    bl audio_columns
    ldr r0, =SP_POWER
    add r0, r4, r0
    add r1, r8, #128
    ldr r2, =spectrum_bins_bass
    bl audio_columns
    add r0, r4, #SP_STREAM
    add r0, r0, #128
    add r1, r8, #256
    ldr r2, [r4, #48]
    bl audio_wave
    str r8, [r4, #56]
    mov r0, #OK
    str r0, [r4, #28]
    b sp_return
sp_close:
    mov r0, r4
    bl scope_close
    bl sp_reset
    b sp_return
sp_bad:
    mov r0, #BAD_ARG
    str r0, [r4, #28]
sp_return:
    ldr r0, [r4, #28]
    pop {r3-r11, pc}
sp_reset:
    mov r0, #0
    str r0, [r4, #56]
    str r0, [r4, #120]
    str r0, [r4, #124]
    add r1, r4, #SP_STREAM
    str r0, [r1]
    bx lr
.pool
