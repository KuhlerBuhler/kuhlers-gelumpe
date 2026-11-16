; BATTERY % (CUSTOMIZATION > DISPLAY): the battery's charge in steps of 10 percent on the main screen's top row, left of LOAD
; METER's digits (page 0, columns 83 to 98, rows 1 to 7: hundreds, tens, ones and '%', each 3 columns and a blank one; columns
; 75 to 99 of that row are free on all three builds, docs/messungen/2026-11-16-batterie-prozent.md). Shown only on battery
; (POWER_MODEL +0x308 is 0) with Global BATTERY TYPE Alkali (byte 0x20 of the Global values is 1); on mains power and with
; Ni-MH nothing is drawn. On by default: the stored bit FLAGS2_BATT_OFF means off, so a file with the default stays version 3.
; The reading is the battery model's (BATTERY_MODEL +0x320, from panel message 6), its thresholds the table at +0x318 (full
; first, empty last). It is smoothed: every BP_STEP_MS it moves an eighth of the way to the reading, and the percent shown
; changes only when the new one is more than 8 percent away from it, so a short dip or noise around a step leaves it.
.equ BP_AVG, 0                  ; the smoothed reading times 256
.equ BP_TICK, 4                 ; the OS tick count (1 ms) at the last smoothing step
.equ BP_SHOWN, 8                ; byte: the percent shown, 0 to 100 in steps of 10, 0xFF before the first one
.equ BP_DRAWN, 9                ; byte: 1 while our digits may be on the display
.equ BP_INIT, 12                ; 1 while a reading is held (0 while not wanted, FF at power-on)
.equ BP_COL, 83                 ; the first column of the digits
.equ BP_STEP_MS, 250            ; one smoothing step
.equ BP_HOLD, 80                ; per mille: the percent shown changes only when the new one is further away than this

; Once a frame, behind glide_frame. Keeps r4 to r11.
battery_frame:
    push {r4-r8, lr}
    ldr r4, =BATT
    bl battery_model
    movs r5, r0
    bne batt_frame_on
    str r5, [r4, #BP_INIT]
    mov r0, #0xFF
    strb r0, [r4, #BP_SHOWN]
    ldrb r0, [r4, #BP_DRAWN]
    cmp r0, #1
    bne batt_frame_out
    bl load_meter_shown
    cmp r0, #0
    beq batt_frame_out          ; not on the main screen: the firmware draws its screen again when it comes back
    mov r0, #0
    strb r0, [r4, #BP_DRAWN]
    mov r0, #0xFF               ; no digits: the columns cleared
    bl battery_put
    b batt_frame_out
batt_frame_on:
    ldr r0, [r5, #0x320]
    cmp r0, #255
    movhi r0, #255
    mov r6, r0, lsl #8          ; the reading times 256
    ldr r2, =LM_OS_TICKS
    ldr r2, [r2]
    ldr r1, [r4, #BP_INIT]
    cmp r1, #1
    beq batt_frame_step
    cmp r0, #2                  ; no reading yet (0 and 1 are not ones, 1 is the power key)
    blo batt_frame_draw
    mov r1, #1
    str r1, [r4, #BP_INIT]
    str r2, [r4, #BP_TICK]
    str r6, [r4, #BP_AVG]
    mov r1, #0xFF
    strb r1, [r4, #BP_SHOWN]
    b batt_frame_value
batt_frame_step:
    ldr r1, [r4, #BP_TICK]
    sub r1, r2, r1
    cmp r1, #BP_STEP_MS
    blo batt_frame_draw
    str r2, [r4, #BP_TICK]
    cmp r0, #2
    blo batt_frame_draw
    ldr r1, [r4, #BP_AVG]
    subs r2, r6, r1             ; how far the reading is
    rsblt r3, r2, #0
    movge r3, r2
    cmp r3, #8
    movlo r1, r6                ; this close: there, so a steady reading gives its own percent
    addhs r1, r1, r2, asr #3
    str r1, [r4, #BP_AVG]
batt_frame_value:
    ldr r0, [r4, #BP_AVG]
    ldr r1, [r5, #0x318]
    ldrb r7, [r1]               ; full
    ldrb r8, [r1, #3]           ; empty
    sub r1, r7, r8
    subs r0, r0, r8, lsl #8
    movlt r0, #0
    mov r3, #1000
    mul r0, r3, r0
    mov r1, r1, lsl #8
    bl egg_div                  ; the place between empty and full in per mille
    cmp r0, #1000
    movhi r0, #1000
    mov r1, #100
    bl egg_div                  ; r0 the curve's segment, r1 the place in it
    ldr r2, =batt_curve
    add r2, r2, r0, lsl #2
    ldr r7, [r2]
    cmp r0, #10
    beq batt_frame_percent
    ldr r3, [r2, #4]
    sub r3, r3, r7
    mul r0, r3, r1
    mov r1, #100
    bl egg_div
    add r7, r7, r0              ; the charge in per mille
batt_frame_percent:
    ldrb r0, [r4, #BP_SHOWN]
    cmp r0, #0xFF
    beq batt_frame_set
    mov r1, #10
    mul r1, r0, r1
    subs r1, r7, r1
    rsblt r1, r1, #0
    cmp r1, #BP_HOLD
    bls batt_frame_draw
batt_frame_set:
    add r0, r7, #50
    mov r1, #100
    bl egg_div
    mov r1, #10
    mul r0, r1, r0
    strb r0, [r4, #BP_SHOWN]
batt_frame_draw:
    bl load_meter_shown
    cmp r0, #0
    strbeq r0, [r4, #BP_DRAWN]  ; the firmware draws its screen again when the main screen comes back
    beq batt_frame_out
    ldrb r0, [r4, #BP_SHOWN]
    cmp r0, #0xFF
    beq batt_frame_out
    mov r1, #1
    strb r1, [r4, #BP_DRAWN]
    bl battery_put
batt_frame_out:
    pop {r4-r8, pc}

; -> r0 = the battery model when the percent is wanted: the menu armed, the switch on, on battery, BATTERY TYPE Alkali and a
; threshold table with full above empty; else 0. Clobbers r1 to r3.
battery_model:
    ldr r1, =MENU_STATE
    ldr r0, [r1, #M_ON]
    cmp r0, #1
    bne batt_model_none
    ldrb r0, [r1, #MX_FLAGS2]
    tst r0, #FLAGS2_BATT_OFF
    bne batt_model_none
    ldr r1, =POWER_MODEL
    ldr r1, [r1]
    cmp r1, #0
    cmnne r1, #1
    beq batt_model_none
    ldr r0, [r1, #0x308]
    cmp r0, #0
    bne batt_model_none
    ldr r1, =GLOBAL_LIVE
    ldr r1, [r1]
    cmp r1, #0
    cmnne r1, #1
    beq batt_model_none
    ldrb r0, [r1, #4+0x20]
    cmp r0, #1
    bne batt_model_none
    ldr r0, =BATTERY_MODEL
    ldr r0, [r0]
    cmp r0, #0
    cmnne r0, #1
    beq batt_model_none
    ldr r1, [r0, #0x318]
    cmp r1, #0
    beq batt_model_none
    ldrb r2, [r1]
    ldrb r3, [r1, #3]
    cmp r2, r3
    bxhi lr
batt_model_none:
    mov r0, #0
    bx lr

; r0 = the percent, 0 to 100 (0xFF = blank): the sixteen columns from BP_COL in page 0 of the frame buffer, row 0 kept;
; written and marked as changed only when they differ. Clobbers r0 to r3, r5 to r7, r12.
battery_put:
    push {lr}
    sub sp, sp, #16
    mov r6, #0xFF
    mov r7, #0xFF
    mov r5, #0xFF
    cmp r0, #100
    bhi batt_put_glyphs
    moveq r6, #1
    moveq r0, #0
    cmp r0, #10
    blo batt_put_ones
    mov r1, #10
    bl egg_div
    mov r7, r0
    mov r0, r1
batt_put_ones:
    mov r5, r0
batt_put_glyphs:
    cmp r6, #1                  ; 100: the tens is 0 under the hundreds
    moveq r7, #0
    mov r0, r6
    mov r1, sp
    bl load_meter_glyph
    mov r0, r7
    add r1, sp, #4
    bl load_meter_glyph
    mov r0, r5
    add r1, sp, #8
    bl load_meter_glyph
    cmp r5, #0xFF
    ldrne r12, =batt_percent_glyph
    ldrne r12, [r12]
    moveq r12, #0
    str r12, [sp, #12]
    ldr r2, =MG_VRAM+BP_COL
    mov r3, #0
    mov r5, #0
batt_put_col:
    ldrb r0, [r2, r3]
    and r1, r0, #1
    ldrb r12, [sp, r3]
    orr r1, r1, r12
    cmp r1, r0
    strbne r1, [r2, r3]
    movne r5, #1
    add r3, r3, #1
    cmp r3, #16
    blo batt_put_col
    add sp, sp, #16
    cmp r5, #0
    popeq {pc}
    mov r0, #BP_COL
    mov r1, #0
    mov r2, #BP_COL+15
    mov r3, #7
    ldr r12, =MG_MARK
    blx r12
    pop {pc}
.pool
.align 4
batt_percent_glyph:             ; '%' in 3 x 7, as load_meter_font, and a blank column
    .byte 0x42, 0x38, 0x84, 0x00
; The charge in per mille at 0, 10, ... 100 percent of the way from the empty to the full threshold of BATTERY TYPE's table.
; PLACEHOLDER (derived, not measured): linear, a straight line between Korg's Alkali empty and full thresholds. Replace these
; eleven values with a discharge curve measured on a device (docs/messungen/2026-11-16-batterie-prozent.md); they must rise.
batt_curve:
    .word 0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000
.align 4
