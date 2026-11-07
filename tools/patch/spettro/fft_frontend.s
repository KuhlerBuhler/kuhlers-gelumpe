; Isolated spectrum preprocessing, not linked into installable firmware.
; fft_prepare(r0=4096 packed signed16 pairs, r1=FFT complex signed32 array,
;             r2=2048 Q15 twiddle pairs, r3=component byte offset 0 or 2).
; Removes the arithmetic mean, applies a periodic Hann and divides by two.
; Keeps seven fractional bits through the FFT; 64-bit products avoid overflow.
; Power is stored after >>8: calibration is power / 2^30 for an ordinary sine.
fft_prepare:
    push {r4-r10, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r7, r3
    mov r8, #0
    mov r9, #4096
    add r10, r4, r7
fft_mean_loop:
    .word 0xE1DA00F0 ; ldrsh r0, [r10]
    add r8, r8, r0
    add r10, r10, #4
    subs r9, r9, #1
    bne fft_mean_loop
    mov r8, r8, asr #12
    add r10, r4, r7
    mov r9, #0
fft_window_loop:
    bic r0, r9, #2048
    ldr r1, [r6, r0, lsl #3]
    cmp r9, #2048
    rsbhs r1, r1, #0
    rsb r1, r1, #32768
    mov r1, r1, asr #1
    .word 0xE1DA00F0 ; ldrsh r0, [r10]
    sub r0, r0, r8
    mul r2, r0, r1
    mov r2, r2, asr #9
    str r2, [r5], #4
    mov r0, #0
    str r0, [r5], #4
    add r10, r10, #4
    add r9, r9, #1
    cmp r9, #4096
    blo fft_window_loop
    mov r0, #0
    pop {r4-r10, pc}

; fft_power(r0=FFT array, r1=2049 unsigned32 powers, r2=mode).
; mode 0 mono overwrite, 1 first stereo component /2, 2 add second /2.
; Combining powers avoids cancelling stereo components of opposite phase.
fft_power:
    push {r4-r6, lr}
    ldr r6, =2049
fft_power_loop:
    ldmia r0!, {r3, r12}
    .word 0xE0C54393 ; smull r4, r5, r3, r3
    .word 0xE0E54C9C ; smlal r4, r5, r12, r12
    cmp r5, #256
    movlo r4, r4, lsr #8
    orrlo r4, r4, r5, lsl #24
    mvnhs r4, #0
    cmp r2, #0
    movne r4, r4, lsr #1
    cmp r2, #2
    ldreq r5, [r1]
    addeq r4, r4, r5
    str r4, [r1], #4
    subs r6, r6, #1
    bne fft_power_loop
    mov r0, #0
    pop {r4-r6, pc}
.pool
