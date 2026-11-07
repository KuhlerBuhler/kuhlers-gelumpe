; Generate twiddle coefficients in caller-owned RAM.
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
