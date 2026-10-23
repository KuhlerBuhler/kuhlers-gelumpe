; The original LCD CONTRAST page keeps its input and save handlers. Only its middle six display pages are replaced.
; The picture goes straight into the frame buffer every frame; the firmware redraws only its own widgets, so when the page is left
; (EDIT to the next page) the whole display is drawn anew once (device 22.10.: the balls stayed on the next page).
display_calibrate:
    ldr r1, =SCREEN_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    cmnne r1, #1
    beq calibrate_off
    ldr r2, [r1, #0x24]
    cmp r2, #0
    bne calibrate_off
    ldr r2, [r1, #0x2c]
    cmp r2, #9
    bne calibrate_off
    ldr r1, [r1, #0x20]
    cmp r1, #0
    cmnne r1, #1
    beq calibrate_off
    ldr r2, [r1, #0x2c]
    cmp r2, #12
    bne calibrate_off
    push {r4-r8, lr}
    sub sp, sp, #8
    ldr r0, =0xC033E6A0
    ldr r0, [r0]
    cmp r0, #0
    cmnne r0, #1
    beq calibrate_done
    ldrb r5, [r0, #0x22]
    cmp r5, #18
    blo calibrate_done
    cmp r5, #42
    bhi calibrate_done
    sub r5, r5, #17
    ldr r8, =MENU_STATE
    mov r0, #1
    strb r0, [r8, #M_CAL_ON]
    ldr r8, =SCRIPT_DISPLAY_RAM
    add r1, r8, #128
    mov r2, #768
    mov r0, #0
calibrate_clear:
    str r0, [r1], #4
    subs r2, r2, #4
    bne calibrate_clear
    ldr r0, =calibrate_title
    add r1, r8, #128
    add r1, r1, #13
    bl calibrate_text
    ldr r0, =calibrate_contrast
    add r1, r8, #256
    add r1, r1, #31
    bl calibrate_text
    mov r6, #0
calibrate_tens:
    cmp r5, #10
    subhs r5, r5, #10
    addhs r6, r6, #1
    bhs calibrate_tens
    mov r0, sp
    cmp r6, #0
    addne r6, r6, #48
    strbne r6, [r0], #1
    add r5, r5, #48
    strb r5, [r0], #1
    mov r2, #0
    strb r2, [r0]
    mov r0, sp
    bl calibrate_text
    ldr r0, =calibrate_help
    add r1, r8, #768
    add r1, r1, #22
    bl calibrate_text
    ldr r4, =HOOK_RUNTIME
    ldr r4, [r4, #RT_FRAMES]
    mov r5, #0
calibrate_ball:
    mov r0, r4, lsl r5
    and r0, r0, #255
    cmp r0, #128
    rsbhs r0, r0, #255
    mov r2, #117
    mul r0, r2, r0
    mov r0, r0, lsr #7
    add r0, r0, #2
    add r6, r8, #384
    add r6, r6, r5, lsl #7
    add r6, r6, r0
    ldr r1, =calibrate_circle
    mov r7, #0
calibrate_ball_column:
    ldrb r2, [r1, r7]
    strb r2, [r6, r7]
    add r7, r7, #1
    cmp r7, #7
    blo calibrate_ball_column
    add r5, r5, #1
    cmp r5, #3
    blo calibrate_ball
calibrate_done:
    add sp, sp, #8
    pop {r4-r8, pc}
.pool

; not on the page: once after the picture was drawn, the firmware draws the whole display anew. Clobbers r1 and r2.
calibrate_off:
    ldr r1, =MENU_STATE
    ldrb r2, [r1, #M_CAL_ON]
    cmp r2, #1
    bxne lr
    mov r2, #0
    strb r2, [r1, #M_CAL_ON]
    ldr r1, =UI_REDRAW
    mov r2, #1
    strb r2, [r1]
    bx lr
.pool

; ASCII string r0 to an aligned LCD page at r1, using the runtime's own five-column font.
calibrate_text:
    ldrb r2, [r0], #1
    cmp r2, #0
    bxeq lr
    sub r2, r2, #32
    add r2, r2, r2, lsl #2
    ldr r3, =SCRIPT_FONT
    add r3, r3, r2
    mov r12, #0
calibrate_text_column:
    ldrb r2, [r3, r12]
    strb r2, [r1], #1
    add r12, r12, #1
    cmp r12, #5
    blo calibrate_text_column
    add r1, r1, #1
    b calibrate_text
.pool
calibrate_title:
    .asciz "CALIBRATE DISPLAY"
calibrate_contrast:
    .asciz "CONTRAST "
calibrate_help:
    .asciz "VALUE: ADJUST"
calibrate_circle:
    .byte 0x1c, 0x3e, 0x7f, 0x7f, 0x7f, 0x3e, 0x1c
.align 4
