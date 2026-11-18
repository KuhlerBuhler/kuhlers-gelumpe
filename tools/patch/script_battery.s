; BATTERY % (CUSTOMIZATION > DISPLAY): the battery's charge in steps of 10 percent on the main screen's top row, right before
; the battery symbol (page 0, columns 101 to 116, rows 1 to 7: hundreds, tens, ones and '%', each 3 columns and a blank one).
; While the percent is wanted (battery_model) the card symbol moves to 94 to 99 on the main screen (card_place, card_frame);
; without it (mains, Ni-MH, the switch off) it goes back to Korg's 109, which every other screen keeps. LOAD METER sits at
; 86 to 93 either way (docs/messungen/2026-11-16-batterie-prozent.md). Shown only on battery
; (POWER_MODEL +0x308 is 0) with Global BATTERY TYPE Alkali (byte 0x20 of the Global values is 1); on mains power and with
; Ni-MH nothing is drawn. On by default: the stored bit FLAGS2_BATT_OFF means off, so a file with the default stays version 3.
; The reading is the battery model's (BATTERY_MODEL +0x320, from panel message 6). Empty is the last byte of its threshold
; table at +0x318, where the firmware switches off; full is BP_FULL, a little under fresh Alkali cells (162 to 163 measured),
; because Korg's full threshold 127 is reached only after about an hour. It is smoothed: every BP_STEP_MS it moves an eighth of the way to the reading, and the percent shown
; changes only when the new one is more than 8 percent away from it, so a short dip or noise around a step leaves it.
.equ BP_AVG, 0                  ; the smoothed reading times 256
.equ BP_TICK, 4                 ; the OS tick count (1 ms) at the last smoothing step
.equ BP_SHOWN, 8                ; byte: the percent shown, 0 to 100 in steps of 10, 0xFF before the first one
.equ BP_DRAWN, 9                ; byte: 1 while our digits may be on the display
.equ BP_INIT, 12                ; 1 while a reading is held (0 while not wanted, FF at power-on)
.equ BP_CARD, 16                ; 6 bytes: columns 94 to 99 of page 0 (row 0 left out) as card_frame last drew them
.equ BP_TARGET, 22              ; byte: the screen card_place placed the card for (FF before the first switch)
.equ BP_CARD_IN, 23             ; byte: the card flag of the widget when card_frame last drew it
.equ BP_SWITCH, 24              ; the OS tick count at that switch
.equ BP_PENDING_MS, 300         ; how long card_frame waits for the screen manager to show that screen
.equ BP_COL, 101                ; the first column of the digits
.equ BP_STEP_MS, 250            ; one smoothing step
.equ BP_HOLD, 80                ; per mille: the percent shown changes only when the new one is further away than this
.equ BP_FULL, 160               ; the reading shown as 100 percent

; Once a frame, behind glide_frame. Keeps r4 to r11.
battery_frame:
    push {r4-r8, lr}
    bl card_frame
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
    mov r7, #BP_FULL
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
batt_put_pool:
.pool
.align 4
; The card symbol: Korg's widget is the third of the status bar ([SCREEN_MANAGER] + 0x10, widgets at +0x34, +0x38, +0x3C), x at
; +4, y +8, width +0xC (6), height +0x10 (8), +0x14 the byte that makes its draw clear its place and draw again, +0x48 a card
; is in; its draw is slot 2 of its class table. The status bar draws it on every screen; the main screen draws its own widgets
; behind it, among them the EDIT mark at 84 to 97 in the clearing colour, so the main screen needs card_frame as well.
.equ CARD_X_KORG, 109
.equ CARD_X_MAIN, 94

; -> r0 = the card widget when it is the one these lines know (width 6, height 8, x 109 or 94), else 0; r1 = the screen
; manager. Clobbers r2.
card_widget:
    ldr r1, =SCREEN_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    cmnne r1, #1
    beq card_widget_none
    ldr r0, [r1, #0x4C]
    cmp r0, #0
    cmnne r0, #1
    beq card_widget_none
    ldr r2, [r0, #0xC]
    cmp r2, #6
    ldreq r2, [r0, #0x10]
    cmpeq r2, #8
    bne card_widget_none
    ldr r2, [r0, #4]
    cmp r2, #CARD_X_KORG
    cmpne r2, #CARD_X_MAIN
    bxeq lr
card_widget_none:
    mov r0, #0
    bx lr

; r0 = the screen to come (SWITCH_SCREEN, autosave_switch_hook), before it is drawn: the card's x for it, its old place cleared
; (not every screen clears the top row where the card was), and its byte to draw again, so the new screen draws it in its
; place. With the menu not armed nothing moves. Keeps r4 to r11.
card_place:
    push {r4-r6, lr}
    mov r4, r0
    ldr r0, =MENU_STATE
    ldr r0, [r0, #M_ON]
    cmp r0, #1
    popne {r4-r6, pc}
    bl card_widget
    cmp r0, #0
    popeq {r4-r6, pc}
    mov r5, r0
    ldr r1, =BATT               ; the switch is posted, the screen manager shows the screen later: card_frame waits for it
    strb r4, [r1, #BP_TARGET]
    ldr r2, =LM_OS_TICKS
    ldr r2, [r2]
    str r2, [r1, #BP_SWITCH]
    mov r0, #CARD_X_KORG
    cmp r4, #1
    bleq card_main_x
    mov r1, r0
    mov r0, r5
    ldr r4, [r0, #4]
    cmp r4, r1
    popeq {r4-r6, pc}
    str r1, [r0, #4]
    mov r1, #1
    strb r1, [r0, #0x14]
    ldr r0, =BATT+BP_CARD       ; card_frame draws it again on the main screen
    mov r1, #0xFF
    strb r1, [r0]
    mov r0, r4
    bl card_clear
    pop {r4-r6, pc}

; -> r0 = the card's x on the main screen: 94 while the percent is wanted, else Korg's 109. Clobbers r1 to r3.
card_main_x:
    push {lr}
    bl battery_model
    cmp r0, #0
    movne r0, #CARD_X_MAIN
    moveq r0, #CARD_X_KORG
    pop {pc}

; r0 = a column: the six columns of the card from there cleared in page 0, row 0 kept, and marked. Clobbers r0 to r3, r12.
card_clear:
    push {r4, lr}
    mov r4, r0
    ldr r2, =MG_VRAM
    add r2, r2, r4
    mov r3, #0
card_clear_col:
    ldrb r0, [r2, r3]
    and r0, r0, #1
    strb r0, [r2, r3]
    add r3, r3, #1
    cmp r3, #6
    blo card_clear_col
    mov r0, r4
    mov r1, #0
    add r2, r4, #5
    mov r3, #7
    ldr r12, =MG_MARK
    blx r12
    pop {r4, pc}

; Once a frame: on the main screen the card sits where card_main_x says; at 94, when its columns differ from what card_frame drew last (the main screen
; cleared them with its EDIT mark, or the card came or went) it is drawn again there, only with no window, app or question of
; ours over the screen. Any other screen gets Korg's 109 back (card_place does it before the screen is drawn; this is the
; fallback, as at the first start when the menu was armed behind the main screen). Keeps r4 to r11.
card_frame:
    push {r4-r6, lr}
    ldr r0, =MENU_STATE
    ldr r0, [r0, #M_ON]
    cmp r0, #1
    bne card_frame_out
    bl card_widget
    movs r4, r0
    beq card_frame_out
    ldr r2, [r1, #0x2C]
    ldr r5, =BATT               ; a switch card_place saw that the screen manager has not shown yet: nothing until it has
    ldrb r3, [r5, #BP_TARGET]
    and r0, r2, #0xFF
    cmp r3, r0
    cmpne r3, #0xFF
    beq card_frame_screen
    ldr r0, =LM_OS_TICKS
    ldr r0, [r0]
    ldr r3, [r5, #BP_SWITCH]
    sub r0, r0, r3
    cmp r0, #BP_PENDING_MS
    blo card_frame_out
card_frame_screen:
    cmp r2, #1
    beq card_frame_main
    ldr r2, [r4, #4]
    cmp r2, #CARD_X_MAIN
    bne card_frame_out
    mov r2, #CARD_X_KORG
    str r2, [r4, #4]
    mov r2, #1
    strb r2, [r4, #0x14]
    b card_frame_out
card_frame_main:
    bl card_main_x
    ldr r2, [r4, #4]
    cmp r2, r0
    beq card_frame_same
    str r0, [r4, #4]
    cmp r0, #CARD_X_MAIN
    bne card_frame_back
    mov r0, #CARD_X_KORG        ; the card drawn at 109 before the move
    bl card_clear
    b card_frame_draw_check
card_frame_back:                ; the percent gone: Korg's widget draws the card at 109 again, ours at 94 cleared
    mov r0, #1
    strb r0, [r4, #0x14]
    bl load_meter_shown
    cmp r0, #0
    beq card_frame_out          ; a window or app over the screen: the firmware draws the screen again when it goes
    mov r0, #CARD_X_MAIN
    bl card_clear
    b card_frame_out
card_frame_same:
    cmp r0, #CARD_X_KORG
    beq card_frame_out
card_frame_check:
    ldrb r0, [r4, #0x14]
    cmp r0, #0
    bne card_frame_draw_check
    ldrb r0, [r4, #0x48]        ; a card put in or pulled during a redraw that also cleared 84 to 97 leaves the columns as they were
    ldr r5, =BATT
    ldrb r1, [r5, #BP_CARD_IN]
    cmp r0, r1
    bne card_frame_draw_check
    ldr r2, =MG_VRAM+CARD_X_MAIN
    ldr r5, =BATT+BP_CARD
    mov r3, #0
card_frame_cmp:
    ldrb r0, [r2, r3]
    bic r0, r0, #1
    ldrb r1, [r5, r3]
    cmp r0, r1
    bne card_frame_draw_check
    add r3, r3, #1
    cmp r3, #6
    blo card_frame_cmp
    b card_frame_out
card_frame_draw_check:
    bl load_meter_shown
    cmp r0, #0
    beq card_frame_out
    mov r0, #1
    strb r0, [r4, #0x14]
    mov r0, r4
    ldr r1, [r4]
    ldr r1, [r1, #8]
    blx r1
    ldrb r0, [r4, #0x48]
    ldr r1, =BATT
    strb r0, [r1, #BP_CARD_IN]
    mov r0, #CARD_X_MAIN
    mov r1, #0
    mov r2, #CARD_X_MAIN+5
    mov r3, #8
    ldr r12, =MG_MARK
    blx r12
    ldr r2, =MG_VRAM+CARD_X_MAIN
    ldr r5, =BATT+BP_CARD
    mov r3, #0
card_frame_keep:
    ldrb r0, [r2, r3]
    bic r0, r0, #1
    strb r0, [r5, r3]
    add r3, r3, #1
    cmp r3, #6
    blo card_frame_keep
card_frame_out:
    pop {r4-r6, pc}
.pool
.align 4
batt_percent_glyph:             ; '%' in 3 x 7, as load_meter_font, and a blank column
    .byte 0x42, 0x38, 0x84, 0x00
; The charge in per mille at 0, 10, ... 100 percent of the way from empty (the table's last byte) to BP_FULL.
; The share of the running time left at each point (raw 97 + 6.3 per step up to BP_FULL), from two runs on a red with
; Alkali AA cells and Power Save on (docs/messungen/2026-11-16-batterie-prozent.md): fresh cells 162 down to 132 while
; playing, old cells 123 down to the switch-off at 98 without playing; 132 to 123 estimated. They must rise.
batt_curve:
    .word 0, 97, 221, 369, 421, 488, 626, 795, 908, 974, 1000
.align 4
