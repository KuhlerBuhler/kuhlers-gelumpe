; Hue, saturation and brightness for the colour pages of the BLECH menu (script_menu.s); in the second code area, the menu's has no room left.
; The colour pages show hue, saturation and brightness; the settings and the light stay red, green, blue (0 to 15 each), so a file from
; before reads as before. The wheel has 96 steps, 16 to each of red, yellow, green, cyan, blue and magenta and the way between.
; r0 = (r0 + r1 / 2) / r1 (r1 > 0). Clobbers r2.
look_div:
    add r0, r0, r1, lsr #1
    mov r2, #0
look_div_loop:
    cmp r0, r1
    subhs r0, r0, r1
    addhs r2, r2, #1
    bhs look_div_loop
    mov r0, r2
    bx lr
; r0 = hue 0 to 95, r1 = saturation 0 to 15, r2 = brightness 0 to 15 -> r0, r1, r2 = red, green, blue. Clobbers r3, r12.
look_hsv_rgb:
    push {r4-r9, lr}
    mov r4, r0
    mov r9, r2
    mul r0, r1, r2
    mov r1, #15
    bl look_div                 ; the spread between the largest and the smallest channel
    mov r5, r0
    sub r6, r9, r5              ; the smallest channel
    and r7, r4, #15
    mov r4, r4, lsr #4          ; the sector
    mul r0, r5, r7
    add r0, r0, #8
    mov r0, r0, lsr #4          ; the middle channel's share, rising
    rsb r8, r0, r5
    add r7, r6, r0              ; rising channel
    add r8, r6, r8              ; falling channel
    cmp r4, #0
    moveq r0, r9
    moveq r1, r7
    moveq r2, r6
    beq look_hsv_rgb_out
    cmp r4, #1
    moveq r0, r8
    moveq r1, r9
    moveq r2, r6
    beq look_hsv_rgb_out
    cmp r4, #2
    moveq r0, r6
    moveq r1, r9
    moveq r2, r7
    beq look_hsv_rgb_out
    cmp r4, #3
    moveq r0, r6
    moveq r1, r8
    moveq r2, r9
    beq look_hsv_rgb_out
    cmp r4, #4
    moveq r0, r7
    moveq r1, r6
    moveq r2, r9
    beq look_hsv_rgb_out
    mov r0, r9
    mov r1, r6
    mov r2, r8
look_hsv_rgb_out:
    pop {r4-r9, pc}
; r0 = three words (red, green, blue), not all 0 -> r0 = hue, r1 = saturation, r2 = brightness. Clobbers r3, r12.
look_hsv_get:
    push {r4-r10, lr}
    ldr r4, [r0]
    ldr r5, [r0, #4]
    ldr r6, [r0, #8]
    mov r7, r4
    cmp r5, r7
    movgt r7, r5
    cmp r6, r7
    movgt r7, r6                ; brightness: the largest channel
    mov r8, r4
    cmp r5, r8
    movlt r8, r5
    cmp r6, r8
    movlt r8, r6
    sub r9, r7, r8              ; spread
    mov r10, #0
    cmp r9, #0
    beq look_hsv_get_sat
    cmp r4, r7
    subeq r0, r5, r6
    moveq r10, #0
    beq look_hsv_get_h
    cmp r5, r7
    subeq r0, r6, r4
    moveq r10, #32
    subne r0, r4, r5
    movne r10, #64
look_hsv_get_h:
    cmp r0, #0
    rsblt r0, r0, #0
    movlt r6, #1
    movge r6, #0
    mov r0, r0, lsl #4
    mov r1, r9
    bl look_div
    cmp r6, #0
    rsbne r0, r0, #0
    add r10, r10, r0
    cmp r10, #0
    addlt r10, r10, #96
    cmp r10, #96
    subge r10, r10, #96
look_hsv_get_sat:
    rsb r0, r9, r9, lsl #4      ; 15 * spread
    mov r1, r7
    bl look_div
    mov r1, r0
    mov r0, r10
    mov r2, r7
    pop {r4-r10, pc}
; r0 = three words (red, green, blue), r1 = 0 hue, 1 saturation, 2 brightness, r2 = steps of the dial. Turns that part of the colour and
; writes the result back; where a step gives the same 4 bit colour it takes the next one. Nothing set (all 0) starts from red, full.
; The brightness stays 1 or more, and white at full brightness is the stock state again.
look_hsv_step:
    push {r4-r11, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    cmp r6, #0
    popeq {r4-r11, pc}
    mov r10, #1
    cmp r6, #0
    mvnlt r10, #0               ; the direction
    ldr r0, [r4]
    ldr r1, [r4, #4]
    ldr r2, [r4, #8]
    orr r11, r0, r1, lsl #8
    orr r11, r11, r2, lsl #16
    orr r11, r11, #0x60000000   ; 96 tries at most
    tst r11, #0xFF0000
    tsteq r11, #0xFF00
    tsteq r11, #0xFF
    bne look_hsv_step_have
    mov r7, #0                  ; nothing set
    mov r8, #15
    mov r9, #15
    b look_hsv_step_loop
look_hsv_step_have:
    mov r0, r4
    bl look_hsv_get
    mov r7, r0
    mov r8, r1
    mov r9, r2
look_hsv_step_loop:
    cmp r5, #0
    bne look_hsv_step_sv
    add r7, r7, r6
look_hsv_step_hi:
    cmp r7, #96
    subge r7, r7, #96
    bge look_hsv_step_hi
look_hsv_step_lo:
    cmp r7, #0
    addlt r7, r7, #96
    blt look_hsv_step_lo
    b look_hsv_step_build
look_hsv_step_sv:
    cmp r5, #1
    moveq r12, r8
    movne r12, r9
    add r12, r12, r6
    moveq r3, #0
    movne r3, #1
    cmp r12, r3
    movlt r12, r3
    cmp r12, #15
    movgt r12, #15
    cmp r5, #1
    bne look_hsv_step_bright
    cmp r12, r8
    beq look_hsv_step_done
    mov r8, r12
    b look_hsv_step_build
look_hsv_step_bright:
    cmp r12, r9
    beq look_hsv_step_done
    mov r9, r12
look_hsv_step_build:
    mov r0, r7
    mov r1, r8
    mov r2, r9
    bl look_hsv_rgb
    orr r3, r0, r1, lsl #8
    orr r3, r3, r2, lsl #16
    bic r12, r11, #0xFF000000
    cmp r3, r12
    bne look_hsv_step_store
    sub r11, r11, #0x01000000   ; the same colour: one more step the same way
    tst r11, #0xFF000000
    beq look_hsv_step_done
    mov r6, r10
    b look_hsv_step_loop
look_hsv_step_store:
    and r3, r0, r1
    and r3, r3, r2
    cmp r3, #15                 ; 15 15 15: the stock state
    moveq r0, #0
    moveq r1, #0
    moveq r2, #0
    str r0, [r4]
    str r1, [r4, #4]
    str r2, [r4, #8]
look_hsv_step_done:
    pop {r4-r11, pc}
