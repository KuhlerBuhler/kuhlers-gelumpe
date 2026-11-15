; LOAD METER (CUSTOMIZATION > DISPLAY): the ARM's load in percent, two digits on the main screen's top row left of the card
; symbol (page 0, columns 100 to 106, rows 1 to 7; columns 75 to 108 of that row are free on all three builds, measured
; docs/messungen/2026-11-14-energie-befunde.md, "Lastanzeige").
; The measurement (method A, docs/messungen/2026-11-14-energie-befunde.md, 0.1): the idle loop sets the word 0xC06A2894 to 1
; before it sleeps (wfi), every IRQ adds 1 to it on entry. The time from that store to the next IRQ entry that finds 1 is
; sleep, the rest is load. Timer3 (SCRIPT_TIMER_ADDRESS, 150 MHz, wraps every second) gives the time. The two hooks run
; always, the switch only decides whether the frame draws: off costs the two hooks and nothing else.
.equ LM_STAMP, 0                ; Timer3 when the idle loop set the word to 1
.equ LM_VALID, 4                ; 1 from that store to the first IRQ entry behind it (FF at power-on is not valid)
.equ LM_SLEEP, 8                ; the sum of all sleep in Timer3 ticks, wrapping (the frame takes differences)
.equ LM_INIT, 12                ; 1 once the frame has its first reading (0 while the switch is off)
.equ LM_LAST, 16                ; Timer3 at the frame before
.equ LM_ACC, 20                 ; Timer3 ticks since the last value
.equ LM_SNAP, 24                ; LM_SLEEP at the last value
.equ LM_VALUE, 28               ; byte: the load shown, 0 to 99, 0xFF before the first value
.equ LM_DRAWN, 29               ; byte: 1 while our digits may be on the display
.equ LM_COL, 100                ; the first column of the digits
.equ LM_SECOND, 150000000       ; Timer3 ticks in a second (SCRIPT_TIMER_PERIOD)

; 0xC00017F0, the idle loop's `str r3, [r6]` (r3 = 1, r6 = the word) in front of wfi, IRQs masked. The stamp goes first, so
; an IRQ never finds the word at 1 with an old stamp. r0 to r2 are loaded again before the loop uses them.
load_idle_hook:
    ldr r1, =LOAD_METER
    ldr r0, =SCRIPT_TIMER_ADDRESS
    ldr r0, [r0]
    str r0, [r1, #LM_STAMP]
    str r3, [r1, #LM_VALID]
    str r3, [r6]
    ldr pc, =0xC00017F4

; 0xC000159C, the IRQ entry's `str r0, [r2]` (r0 = the word + 1, r2 = the word, r3 = the word before), in SVC mode with IRQs
; masked, r1 free (the SPSR is pushed). The first IRQ that finds 1 behind a stamp ends a sleep: its length goes onto
; LM_SLEEP and the stamp is used up (a nested IRQ over a task also finds 1, it adds nothing). With r3 = 1 the firmware loads
; r0, r1 and r2 again before it uses them and only compares r3; with any other r3 the hook touches nothing but the flags.
load_irq_hook:
    str r0, [r2]
    cmp r3, #1
    bne load_irq_out
    ldr r2, =LOAD_METER
    ldr r0, [r2, #LM_VALID]
    cmp r0, #1
    bne load_irq_out
    mov r0, #0
    str r0, [r2, #LM_VALID]
    ldr r0, =SCRIPT_TIMER_ADDRESS
    ldr r0, [r0]
    ldr r1, [r2, #LM_STAMP]
    subs r0, r0, r1
    ldrlo r1, =LM_SECOND
    addlo r0, r0, r1
    ldr r1, [r2, #LM_SLEEP]
    add r1, r1, r0
    str r1, [r2, #LM_SLEEP]
load_irq_out:
    ldr pc, =0xC00015A0
.pool

; Once a frame, past the first main screen. With the switch off the digits go (once) and the reading starts again when it is
; turned on. With it on: Timer3's ticks are summed, and once a second's worth is in, the load is 100 minus the share of sleep.
; The digits are drawn only on the main screen with no window over it, no open app and no question of our own on the
; display, and only into the frame buffer when what is there differs (the firmware may have drawn the row again).
; Keeps r4 to r11.
load_meter_frame:
    push {r4-r7, lr}
    ldr r4, =LOAD_METER
    ldr r0, =MENU_STATE
    ldr r1, [r0, #M_ON]
    cmp r1, #1
    ldrbeq r1, [r0, #MX_FLAGS2]
    movne r1, #0
    tst r1, #FLAGS2_LOAD_METER
    bne load_frame_on
    mov r0, #0
    str r0, [r4, #LM_INIT]
    ldrb r0, [r4, #LM_DRAWN]
    cmp r0, #1
    bne load_frame_out
    bl load_meter_shown
    cmp r0, #0
    beq load_frame_out          ; not on the main screen: the firmware draws its screen again when it comes back
    mov r0, #0
    strb r0, [r4, #LM_DRAWN]
    mov r6, #0xFF               ; no digits: the columns cleared
    mov r7, #0xFF
    bl load_meter_put
    b load_frame_out
load_frame_on:
    ldr r0, =SCRIPT_TIMER_ADDRESS
    ldr r0, [r0]
    ldr r1, [r4, #LM_INIT]
    cmp r1, #1
    beq load_frame_count
    mov r1, #1
    str r1, [r4, #LM_INIT]
    str r0, [r4, #LM_LAST]
    mov r1, #0
    str r1, [r4, #LM_ACC]
    ldr r1, [r4, #LM_SLEEP]
    str r1, [r4, #LM_SNAP]
    mov r1, #0xFF
    strb r1, [r4, #LM_VALUE]
    b load_frame_draw
load_frame_count:
    ldr r1, [r4, #LM_LAST]
    str r0, [r4, #LM_LAST]
    subs r0, r0, r1
    ldrlo r1, =LM_SECOND
    addlo r0, r0, r1
    ldr r1, [r4, #LM_ACC]
    add r1, r1, r0
    ldr r2, =LM_SECOND
    cmp r1, r2
    strlo r1, [r4, #LM_ACC]
    blo load_frame_draw
    mov r0, #0
    str r0, [r4, #LM_ACC]
    ldr r2, [r4, #LM_SLEEP]
    ldr r3, [r4, #LM_SNAP]
    str r2, [r4, #LM_SNAP]
    sub r2, r2, r3              ; sleep in this window
    cmp r2, r1
    movhi r2, r1
    mov r1, r1, lsr #8          ; both / 256, so sleep * 100 stays in 32 bits
    mov r2, r2, lsr #8
    mov r3, #100
    mul r0, r2, r3
    add r0, r0, r1, lsr #1      ; rounded
    bl egg_div
    rsb r0, r0, #100
    cmp r0, #99
    movhi r0, #99
    strb r0, [r4, #LM_VALUE]
load_frame_draw:
    bl load_meter_shown
    cmp r0, #0
    moveq r0, #0
    strbeq r0, [r4, #LM_DRAWN]  ; the firmware draws its screen again when the main screen comes back
    beq load_frame_out
    ldrb r0, [r4, #LM_VALUE]
    cmp r0, #0xFF
    beq load_frame_out
    mov r6, #0xFF               ; the tens, none below 10
    cmp r0, #10
    blo load_frame_ones
    mov r1, #10
    bl egg_div
    mov r6, r0
    mov r0, r1
load_frame_ones:
    mov r7, r0
    mov r0, #1
    strb r0, [r4, #LM_DRAWN]
    bl load_meter_put
load_frame_out:
    pop {r4-r7, pc}

; -> r0 = 1 when the digits may be drawn: the main screen, no window over it, no open app drawing, no question of ours.
; Clobbers r1 to r3.
load_meter_shown:
    mov r0, #0
    ldr r1, =SCREEN_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    cmnne r1, #1
    bxeq lr
    ldr r2, [r1, #0x2c]
    cmp r2, #1
    bxne lr
    ldr r2, [r1, #0x24]         ; a window over the screen (the Power Off window, the firmware's questions)
    cmp r2, #0
    bxne lr
    ldr r1, =HOOK_RUNTIME
    ldr r2, [r1, #SCRIPT_CONTROL_DISPLAY_ACTIVE]
    cmp r2, #1
    bxeq lr
    ldr r1, =MENU_STATE
    ldr r2, [r1, #M_FL]
    tst r2, #FL_ASK
    bxne lr
    ldr r1, =MG_WORK
    ldr r2, [r1, #MG_ACTIVE]
    cmp r2, #1
    bxeq lr
    mov r0, #1
    bx lr

; r6 = the tens digit, r7 = the ones digit (0xFF = blank): the eight columns from LM_COL in page 0 of the frame buffer, row 0
; kept; written and marked as changed only when they differ. Clobbers r0 to r3, r5, r12.
load_meter_put:
    push {lr}
    sub sp, sp, #8
    mov r0, r6
    mov r1, sp
    bl load_meter_glyph
    mov r0, r7
    add r1, sp, #4
    bl load_meter_glyph
    ldr r2, =MG_VRAM+LM_COL
    mov r3, #0
    mov r5, #0
load_put_col:
    ldrb r0, [r2, r3]
    and r1, r0, #1
    ldrb r12, [sp, r3]
    orr r1, r1, r12
    cmp r1, r0
    strbne r1, [r2, r3]
    movne r5, #1
    add r3, r3, #1
    cmp r3, #8
    blo load_put_col
    add sp, sp, #8
    cmp r5, #0
    popeq {pc}
    mov r0, #LM_COL
    mov r1, #0
    mov r2, #LM_COL+7
    mov r3, #7
    ldr r12, =MG_MARK
    blx r12
    pop {pc}

; r0 = a digit 0 to 9 or 0xFF, r1 = 4 bytes -> its three columns and a blank one (all blank for 0xFF). Clobbers r0, r12.
load_meter_glyph:
    cmp r0, #9
    movhi r12, #0
    ldrls r12, =load_meter_font
    ldrls r12, [r12, r0, lsl #2]
    str r12, [r1]
    bx lr
.pool
.align 4
load_meter_font:                ; 3 x 7 digits, a column a byte, bit 1 the top row (row 0 of the page stays the firmware's)
    .byte 0xFE, 0x82, 0xFE, 0x00, 0x84, 0xFE, 0x80, 0x00, 0xF2, 0x92, 0x9E, 0x00, 0x92, 0x92, 0xFE, 0x00, 0x1E, 0x10, 0xFE, 0x00
    .byte 0x9E, 0x92, 0xF2, 0x00, 0xFE, 0x92, 0xF2, 0x00, 0x02, 0x02, 0xFE, 0x00, 0xFE, 0x92, 0xFE, 0x00, 0x9E, 0x92, 0xFE, 0x00
.align 4
