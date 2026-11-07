; spectrum_render(powers[2049], bitmap1024, shift9..15, view0=full/1=bass).
; Log frequency bins generated offline. Fixed 72 dB range; no auto normalization.
; Trace y10..54. Q8 log2 approximation uses a 16-entry mantissa table.
spectrum_render:
    push {r4-r11, lr}
    mov r4, r0
    mov r5, r1
    mov r0, #0
    mov r1, #0
sr_clear:
    str r0, [r5, r1]
    add r1, r1, #4
    cmp r1, #1024
    blo sr_clear
    cmp r3, #1
    ldreq r6, =spectrum_bins_bass
    ldrne r6, =spectrum_bins_full
    rsb r0, r2, #11
    ldr r1, =240299
    mul r8, r0, r1
    mov r7, #0
    mov r11, #54
sr_column:
    ldmia r6!, {r0, r1}
    tst r1, #0x80000000
    bne sr_interpolate
    mov r10, #0
sr_peak:
    ldr r2, [r4, r0, lsl #2]
    cmp r2, r10
    movhi r10, r2
    add r0, r0, #1
    cmp r0, r1
    blo sr_peak
    b sr_level
sr_interpolate:
    and r1, r1, #255
    ldr r2, [r4, r0, lsl #2]
    add r0, r0, #1
    ldr r3, [r4, r0, lsl #2]
    rsb r0, r1, #256
    .word 0xE089A092 ; umull r10, r9, r2, r0
    .word 0xE0A9A193 ; umlal r10, r9, r3, r1
    mov r10, r10, lsr #8
    orr r10, r10, r9, lsl #24
sr_level:
    cmp r10, #0
    moveq r9, #54
    beq sr_join
    mov r0, r10
    mvn r1, #0
sr_exponent:
    add r1, r1, #1
    movs r0, r0, lsr #1
    bne sr_exponent
    subs r0, r1, #4
    movge r2, r10, lsr r0
    rsblt r0, r0, #0
    movlt r2, r10, lsl r0
    sub r2, r2, #16
    ldr r0, =spectrum_log_fraction
    ldr r0, [r0, r2, lsl #2]
    add r0, r0, r1, lsl #8
    sub r0, r0, #7680
    ldr r1, =471
    mul r2, r0, r1
    add r2, r2, r8
    mov r2, r2, asr #16
    rsb r9, r2, #10
    cmp r9, #10
    movlt r9, #10
    cmp r9, #54
    movgt r9, #54
sr_join:
    cmp r7, #0
    moveq r11, r9
    cmp r11, r9
    movle r0, r11
    movle r1, r9
    movgt r0, r9
    movgt r1, r11
sr_pixel:
    mov r2, r0, lsr #3
    add r2, r5, r2, lsl #7
    add r2, r2, r7
    and r3, r0, #7
    mov r10, #1
    mov r3, r10, lsl r3
    ldrb r10, [r2]
    orr r10, r10, r3
    strb r10, [r2]
    add r0, r0, #1
    cmp r0, r1
    ble sr_pixel
    mov r11, r9
    add r7, r7, #1
    cmp r7, #128
    blo sr_column
    mov r0, #0
    pop {r4-r11, pc}
.pool
