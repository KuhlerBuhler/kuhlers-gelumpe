; Bounded RAM-only timing probe. No DSP, sequencer, parameters, flash or SD.
; Result allocated with native ALLOC; caller must EXEC fft_bench_free afterwards.
; 64-byte header, 32768-byte complex array, 16384-byte coefficient array.
.equ B_ALLOC, 0xC0028DCC
.equ B_FREE, 0xC0028DD4
.equ B_TICKS, 0xC06A292C
fft_bench:
    push {r4-r8, lr}
    ldr r8, =fft_bench_ptr
    ldr r0, [r8]
    cmp r0, #0
    bne fft_bench_none
    ldr r0, =49216
    bl B_ALLOC
    cmp r0, #0
    beq fft_bench_none
    str r0, [r8]
    mov r4, r0
    mov r1, #0
    mov r2, #0
    ldr r3, =49216
fft_bench_zero:
    str r1, [r4, r2]
    add r2, r2, #4
    cmp r2, r3
    blo fft_bench_zero
    ldr r0, =0x46465442
    str r0, [r4]
    add r5, r4, #64
    add r6, r5, #32768
    mov r0, #16384
    str r0, [r5]
    ldr r8, =B_TICKS
    ldr r7, [r8]
    mov r0, r6
    bl fft_coefficients
    ldr r0, [r8]
    sub r1, r0, r7
    str r1, [r4, #12]
    mov r7, r0
    mov r0, r5
    mov r1, r6
    bl fft4096
    ldr r0, [r8]
    sub r0, r0, r7
    str r0, [r4, #8]
    mov r0, #1
    str r0, [r4, #16]
    mov r0, r4
    pop {r4-r8, pc}
fft_bench_none:
    mov r0, #0
    pop {r4-r8, pc}
fft_bench_free:
    push {r4, lr}
    ldr r4, =fft_bench_ptr
    ldr r0, [r4]
    cmp r0, #0
    beq fft_bench_freed
    bl B_FREE
    mov r0, #0
    str r0, [r4]
fft_bench_freed:
    mov r0, #0
    pop {r4, pc}

; Populate 2048 coefficient pairs in caller-owned 16384 bytes.
; Q30 complex recurrence, rounded to Q15 on storage.
fft_coefficients:
    push {r4-r11, lr}
    mov r4, r0
    mov r5, #2048
    mov r6, #0x40000000
    mov r7, #0
    ldr r8, =1073740561
    ldr r9, =-1647099
fft_coeff_loop:
    add r0, r6, #16384
    mov r0, r0, asr #15
    str r0, [r4], #4
    add r0, r7, #16384
    mov r0, r0, asr #15
    str r0, [r4], #4
    .word 0xE0CBA896 ; smull r10, r11, r6, r8
    .word 0xE0C10997 ; smull r0, r1, r7, r9
    subs r10, r10, r0
    sbc r11, r11, r1
    mov r10, r10, lsr #30
    orr r10, r10, r11, lsl #2
    .word 0xE0C10897 ; smull r0, r1, r7, r8
    .word 0xE0E10996 ; smlal r0, r1, r6, r9
    mov r7, r0, lsr #30
    orr r7, r7, r1, lsl #2
    mov r6, r10
    subs r5, r5, #1
    bne fft_coeff_loop
    pop {r4-r11, pc}
.pool
fft_bench_ptr:
    .word 0
