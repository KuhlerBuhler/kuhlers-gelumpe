; Isolated FFT kernel, not linked into firmware or sent to the device.
; fft4096(r0=8192 signed32 interleaved real/imag, r1=2048 Q15 cos/sin pairs).
; Forward, in-place, normalized 1/4096, arithmetic truncation per stage.
; Caller supplies real signed16 samples in Q7 (imaginary input zero).
; Twiddle table: round(32768*cos(-2*pi*k/4096)), sin likewise, signed32.
; No native calls, allocation, MIDI, or display access.
fft4096:
    push {r3-r11, lr}
    sub sp, sp, #16
    mov r4, r0
    mov r5, r1
    mov r6, #1
    mov r7, #0
fft_reverse:
    mov r8, #2048
fft_reverse_bit:
    tst r7, r8
    eor r7, r7, r8
    movne r8, r8, lsr #1
    bne fft_reverse_bit
    cmp r6, r7
    bhs fft_reverse_next
    add r0, r4, r6, lsl #3
    add r1, r4, r7, lsl #3
    ldmia r0, {r2, r3}
    ldmia r1, {r10, r11}
    stmia r0, {r10, r11}
    stmia r1, {r2, r3}
fft_reverse_next:
    add r6, r6, #1
    cmp r6, #4096
    blo fft_reverse
    mov r6, #2
    mov r8, #2048
fft_stage:
    mov r7, r6, lsr #1
    mov r9, #0
fft_group:
    mov r10, #0
fft_butterfly:
    mul r0, r10, r8
    add r0, r5, r0, lsl #3
    ldmia r0, {r1, r2}
    add r0, r9, r10
    add r0, r4, r0, lsl #3
    add r3, r0, r7, lsl #3
    str r0, [sp]
    str r3, [sp, #4]
    ldmia r3, {r11, r12}
    .word 0xE0CE019B ; smull r0, lr, r11, r1
    rsb r2, r2, #0
    .word 0xE0EE029C ; smlal r0, lr, r12, r2
    rsb r2, r2, #0
    mov r0, r0, lsr #15
    orr r0, r0, r14, lsl #17
    .word 0xE0CE329B ; smull r3, lr, r11, r2
    .word 0xE0EE319C ; smlal r3, lr, r12, r1
    mov r3, r3, lsr #15
    orr r3, r3, r14, lsl #17
    ldr r1, [sp]
    ldr r2, [sp, #4]
    ldmia r1, {r11, r12}
    add r14, r11, r0
    mov r14, r14, asr #1
    str r14, [r1]
    sub r14, r11, r0
    mov r14, r14, asr #1
    str r14, [r2]
    add r14, r12, r3
    mov r14, r14, asr #1
    str r14, [r1, #4]
    sub r14, r12, r3
    mov r14, r14, asr #1
    str r14, [r2, #4]
    add r10, r10, #1
    cmp r10, r7
    blo fft_butterfly
    add r9, r9, r6
    cmp r9, #4096
    blo fft_group
    mov r6, r6, lsl #1
    mov r8, r8, lsr #1
    cmp r6, #4096
    bls fft_stage
    mov r0, #0
    add sp, sp, #16
    pop {r3-r11, pc}
