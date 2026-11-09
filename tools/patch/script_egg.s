; ---- the egg on the page VERSION of the BLECH menu (docs/messungen/2026-11-09-osterei.md)
; MENU five times in a row on VERSION starts a show: every LED of the keys and pads blinks (on, off, on, ...), the pads and the
; keys with a second LED change their colour at each "on" (red, blue, purple), the display light goes round the colour wheel and the
; display shows AUTISM in big letters, then the start image, each for a second. EXIT ends it and the page is VERSION again. The
; first show unlocks the sample BLECH: Global byte 251 (byte 247 of the Globals block, 0x2300F7 in the flash) becomes EGG_UNLOCKED.
; BLECH writes no flash for it: the byte lies in the Globals object in RAM, which the firmware saves itself at switch-off and on
; WRITE in GLOBAL PARAMETERS (docs/messungen/2026-10-13-globals-zurueckgesetzt.md). After the first show EXIT shows NEW SAMPLE
; Unlocked for two seconds, later shows go straight back to VERSION.
; Light: the LEDs blink with 250 ms on and 250 ms off, 2 flashes a second, under the 3 a second of the guidelines for photosensitive
; epilepsy; the display light changes its hue one step of 96 every 40 ms, a slow round of 3.8 s, it never flashes.
; Drawing is the firmware's: the word in its title font (font 3, the BLECH theme's where the set has it) and the start image (image
; 13, the user's own when the splash editor stored one) through its drawing functions into its frame buffer, taken from there into the
; runtime's picture, which the frame hook copies over the frame buffer each frame while the show runs (script_display_blit).
.equ M_EGG, 0x1F8               ; bytes of MENU_STATE behind FILTER TOGGLE's (script_shortcuts.s:FT_LAST), zeroed at arm: 0 off, 1 the
                                ; show runs, 2 the message NEW SAMPLE after the first show
.equ M_EGG_N, 0x1F9             ; the MENU presses in a row on VERSION
.equ M_EGG_PIC, 0x1FA           ; the picture shown (0 the word, 1 the start image), FF none yet
.equ M_EGG_FIRST, 0x1FB         ; 1 when this show unlocked the sample
.equ M_EGG_HUE, 0x1FC           ; the hue the light shows, FF none yet
.equ M_EGG_BL, 0x1FD            ; 3 bytes: the display light's colour (M_BL_R, G, B) before the show
.equ EGG_T0, 0                  ; words at EGG_WORK (script_hooks.py): word: the runtime's milliseconds at the start of the show or of the message (script_hooks.py:EGG_WORK)
.equ EGG_STEP, 4                ; word: the blink step last sent (milliseconds / EGG_BLINK_MS), FFFFFFFF none
.equ EGG_OBJ, 8                 ; word: the menu screen object the show runs on
.equ EGG_PRESSES, 5
.equ EGG_BLINK_MS, 250
.equ EGG_MSG_MS, 2000
.equ EGG_HUE_MS, 40             ; a step of the 96 of the colour wheel: a round in 3.84 s
.equ EGG_PIC_MS, 1000           ; the word and the start image change each second
.equ EGG_SLOT, 251              ; *GLOBALS_PTR + 251 is byte 247 of the Globals block (the object has a word in front)
.equ EGG_UNLOCKED, 0x5A         ; any other value is locked; the firmware's default for the byte is 0
.equ EGG_LEDS, 76               ; the LEDs of the keys, the encoders and the pads (data/script/names.mjs), not the lower RGB LEDs
.equ EGG_WORD_ROWS, 24          ; the rows the word is looked for in after the firmware drew it at the top left

; r0 = object. MENU on the BLECH screen (menu_slot_enter): counted on VERSION, the fifth in a row starts the show -> r0 = 1 when
; MENU was taken here (the page does nothing else with it), 0 when the page handles it. Keeps r4 to r11.
egg_menu_press:
    push {r4, r5, lr}
    mov r4, r0
    ldr r5, =MENU_STATE
    ldrb r0, [r5, #M_EGG]
    cmp r0, #0
    movne r0, #1                ; during the show and the message MENU does nothing
    popne {r4, r5, pc}
    ldr r0, [r5, #M_LEVEL]
    cmp r0, #1
    bne egg_press_other
    ldr r0, [r5, #M_PAGE]
    bl menu_kind
    cmp r0, #41
    bne egg_press_other
    ldrb r0, [r5, #M_EGG_N]
    add r0, r0, #1
    cmp r0, #EGG_PRESSES
    strblo r0, [r5, #M_EGG_N]
    movlo r0, #1
    poplo {r4, r5, pc}
    mov r0, r4
    bl egg_start
    mov r0, #1
    pop {r4, r5, pc}
egg_press_other:
    mov r0, #0
    strb r0, [r5, #M_EGG_N]
    pop {r4, r5, pc}
.pool

; r0 = object. Starts the show and unlocks the sample (the Global byte, in RAM only).
egg_start:
    push {r4, r5, lr}
    ldr r5, =MENU_STATE
    ldr r1, =EGG_WORK
    str r0, [r1, #EGG_OBJ]
    mvn r0, #0
    str r0, [r1, #EGG_STEP]
    mov r0, #0
    strb r0, [r5, #M_EGG_N]
    mov r0, #0xFF
    strb r0, [r5, #M_EGG_PIC]
    strb r0, [r5, #M_EGG_HUE]
    ldr r0, [r5, #M_BL_R]
    strb r0, [r5, #M_EGG_BL]
    ldr r0, [r5, #M_BL_G]
    strb r0, [r5, #M_EGG_BL+1]
    ldr r0, [r5, #M_BL_B]
    strb r0, [r5, #M_EGG_BL+2]
    mov r4, #0
    ldr r1, =GLOBALS_PTR
    ldr r1, [r1]
    cmp r1, #0
    beq egg_start_clock
    ldrb r2, [r1, #EGG_SLOT]
    cmp r2, #EGG_UNLOCKED
    movne r4, #1
    mov r2, #EGG_UNLOCKED
    strb r2, [r1, #EGG_SLOT]
egg_start_clock:
    strb r4, [r5, #M_EGG_FIRST]
    ldr r0, =HOOK_RUNTIME
    bl script_clock_update
    ldr r1, =EGG_WORK
    str r0, [r1, #EGG_T0]
    ldr r0, =HOOK_RUNTIME
    mov r1, #1
    str r1, [r0, #SCRIPT_CONTROL_DISPLAY_ACTIVE]
    mov r0, #1
    bl script_led_hold_glue
    mov r0, #1
    strb r0, [r5, #M_EGG]
    pop {r4, r5, pc}
.pool

; r0 = object, EXIT pressed during the show or the message (menu_slot_exit). The show ends; after the first one the page says
; NEW SAMPLE Unlocked for EGG_MSG_MS, then VERSION again (egg_frame). EXIT during the message goes to VERSION at once.
egg_exit:
    push {r4, r5, lr}
    mov r4, r0
    ldr r5, =MENU_STATE
    ldrb r0, [r5, #M_EGG]
    cmp r0, #1
    bne egg_exit_page
    bl egg_end
    ldrb r0, [r5, #M_EGG_FIRST]
    cmp r0, #0
    beq egg_exit_page
    mov r0, #0
    strb r0, [r5, #M_EGG_FIRST]
    ldr r0, =HOOK_RUNTIME
    bl script_clock_update
    ldr r1, =EGG_WORK
    str r0, [r1, #EGG_T0]
    str r4, [r1, #EGG_OBJ]
    mov r0, #2
    strb r0, [r5, #M_EGG]
    mov r0, r4
    bl menu_show
    pop {r4, r5, pc}
egg_exit_page:
    mov r0, #0
    strb r0, [r5, #M_EGG]
    mov r0, r4
    bl menu_show
    pop {r4, r5, pc}
.pool

; The show's light given back: the colour of the display light as before, the LEDs to the firmware (it sends all of them again),
; nothing of the show left in the runtime's LED queue, and the whole screen drawn anew. Clobbers r0 to r3 and r12.
egg_end:
    push {r4, lr}
    ldr r4, =MENU_STATE
    ldrb r0, [r4, #M_EGG_BL]
    str r0, [r4, #M_BL_R]
    ldrb r0, [r4, #M_EGG_BL+1]
    str r0, [r4, #M_BL_G]
    ldrb r0, [r4, #M_EGG_BL+2]
    str r0, [r4, #M_BL_B]
    bl menu_look_apply
    ldr r0, =HOOK_RUNTIME
    ldr r1, =RT_LED+SCRIPT_LED_PENDING
    add r0, r0, r1
    mov r1, #0
    mov r2, #0
egg_end_pending:
    strb r1, [r0, r2]
    add r2, r2, #1
    cmp r2, #EGG_LEDS
    blo egg_end_pending
    mov r0, #0
    bl script_led_hold_glue
    ldr r1, =UI_REDRAW
    mov r0, #1
    strb r0, [r1]
    pop {r4, pc}
.pool

; r0 = runtime, from the frame hook before the picture is copied. Runs the show: the LEDs at each blink step, the hue of the display
; light, the picture each second; ends the message after EGG_MSG_MS. When the firmware shows anything but the list of the BLECH
; menu (a key of its own switched the screen) the show ends as with EXIT, without the message. Keeps r4 to r11.
egg_frame:
    ldr r1, =MENU_STATE
    ldrb r2, [r1, #M_EGG]
    cmp r2, #0
    bxeq lr
    push {r4-r8, lr}
    mov r4, r0
    mov r5, r1
    ldr r1, =SCREEN_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    beq egg_frame_abort
    cmn r1, #1
    beq egg_frame_abort
    ldr r0, [r1, #0x2c]
    cmp r0, #MENU_SCREEN
    bne egg_frame_abort
    ldr r0, [r5, #M_LEVEL]
    cmp r0, #1
    bne egg_frame_abort
    mov r0, r4
    bl script_clock_update
    ldr r8, =EGG_WORK
    ldr r1, [r8, #EGG_T0]
    sub r6, r0, r1
    ldrb r2, [r5, #M_EGG]
    cmp r2, #2
    beq egg_frame_message
    mov r0, r6                  ; t / 250
    mov r1, #EGG_BLINK_MS
    bl egg_div
    mov r7, r0
    ldr r0, [r8, #EGG_STEP]
    cmp r0, r7
    beq egg_frame_hue
    str r7, [r8, #EGG_STEP]
    mov r0, r7
    bl egg_leds
egg_frame_hue:
    mov r0, r6                  ; (t / 40) modulo 96, one step of the wheel each 40 ms
    mov r1, #EGG_HUE_MS
    bl egg_div
    mov r1, #96
    bl egg_div
    mov r0, r1
    ldrb r1, [r5, #M_EGG_HUE]
    cmp r0, r1
    beq egg_frame_pic
    strb r0, [r5, #M_EGG_HUE]
    mov r1, #15
    mov r2, #15
    bl look_hsv_rgb
    str r0, [r5, #M_BL_R]
    str r1, [r5, #M_BL_G]
    str r2, [r5, #M_BL_B]
    bl menu_look_apply
egg_frame_pic:
    mov r0, r6                  ; (t / 1000) modulo 2
    ldr r1, =EGG_PIC_MS
    bl egg_div
    and r0, r0, #1
    ldrb r1, [r5, #M_EGG_PIC]
    cmp r0, r1
    beq egg_frame_out
    strb r0, [r5, #M_EGG_PIC]
    cmp r0, #0
    bne egg_frame_image
    bl egg_draw_word
    b egg_frame_out
egg_frame_image:
    bl egg_draw_image
egg_frame_out:
    pop {r4-r8, pc}
egg_frame_message:
    ldr r0, =EGG_MSG_MS
    cmp r6, r0
    blo egg_frame_out
    mov r0, #0
    strb r0, [r5, #M_EGG]
    ldr r0, [r8, #EGG_OBJ]
    bl menu_show
    b egg_frame_out
egg_frame_abort:
    ldrb r0, [r5, #M_EGG]
    cmp r0, #1
    bleq egg_end
    mov r0, #0
    strb r0, [r5, #M_EGG]
    b egg_frame_out
.pool

; r0 numerator, r1 nonzero denominator, both unsigned -> quotient r0, remainder r1. Clobbers r2, r3, r12.
egg_div:
    mov r2, #0
    mov r3, #0
    mov r12, #32
egg_div_bit:
    movs r0, r0, lsl #1
    adc r2, r2, r2
    cmp r2, r1
    subhs r2, r2, r1
    adc r3, r3, r3
    subs r12, r12, #1
    bne egg_div_bit
    mov r0, r3
    mov r1, r2
    bx lr

; r0 = blink step, r4 = runtime. Even steps light, odd ones are dark; each lit step has the colour (step / 2) modulo 3: 0 red, 1 blue,
; 2 purple (both). A key with one LED lights on every lit step; of a key or pad with two, the red one lights for red and purple, the
; blue one for blue and purple. Through the runtime's LED queue, as korg.led (script_led.s), with the LEDs held from the firmware.
egg_leds:
    push {r4-r8, lr}
    and r6, r0, #1
    mov r0, r0, lsr #1
    mov r1, #3
    bl egg_div
    mov r7, r1
    ldr r8, =egg_led_roles
    mov r5, #0
egg_leds_loop:
    ldrb r0, [r8, r5]
    mov r2, #255
    cmp r6, #0
    movne r2, #0
    cmp r0, #1
    cmpeq r7, #1
    moveq r2, #0
    cmp r0, #2
    cmpeq r7, #0
    moveq r2, #0
    mov r0, r4
    mov r1, r5
    bl script_led_request
    add r5, r5, #1
    cmp r5, #EGG_LEDS
    blo egg_leds_loop
    pop {r4-r8, pc}
.pool

; r0 = the colour (0 clear, 0xFF set) for the firmware's drawing functions, then the frame buffer cleared in it. Clobbers r0 to r3, r12.
egg_clear_frame:
    push {lr}
    mov r0, #0
    bl menu_brw_colour
    mov r0, #0
    mov r1, #0
    mov r2, #128
    mov r3, #64
    bl 0xC003F55C
    mov r0, #0xFF
    bl menu_brw_colour
    pop {pc}

; The word: the firmware draws it in its title font at the top left of its frame buffer; each of its pixels goes into the runtime's
; picture 3 wide and 4 high, the whole centred. Keeps r4 to r11.
egg_draw_word:
    push {r4-r11, lr}
    sub sp, sp, #8
    bl egg_clear_frame
    mov r0, #3
    str r0, [sp]
    mov r0, sp
    bl 0xC003F730
    mov r0, #0
    str r0, [sp]
    ldr r0, =str_egg_word
    mov r1, #0
    mov r2, #0
    mov r3, #0
    bl 0xC003F7D0
    ldr r4, =MG_VRAM
    mov r6, #128                ; left, right, top, bottom of the lit pixels
    mvn r7, #0
    mov r8, #128
    mvn r9, #0
    mov r11, #0
egg_word_box_row:
    mov r10, #0
egg_word_box_col:
    mov r0, r10
    mov r1, r11
    bl egg_lit
    cmp r0, #0
    beq egg_word_box_next
    cmp r10, r6
    movlt r6, r10
    cmp r10, r7
    movgt r7, r10
    cmp r11, r8
    movlt r8, r11
    cmp r11, r9
    movgt r9, r11
egg_word_box_next:
    add r10, r10, #1
    cmp r10, #128
    blo egg_word_box_col
    add r11, r11, #1
    cmp r11, #EGG_WORD_ROWS
    blo egg_word_box_row
    bl display_clear
    cmp r7, r6
    blt egg_word_done
    sub r0, r7, r6              ; width and height of the word, then where it starts on the display
    add r0, r0, #1
    add r0, r0, r0, lsl #1
    rsb r0, r0, #128
    mov r0, r0, asr #1
    str r0, [sp]                ; (128 - 3 * width) / 2
    sub r0, r9, r8
    add r0, r0, #1
    rsb r0, r0, #16
    mov r0, r0, lsl #1
    str r0, [sp, #4]            ; (64 - 4 * height) / 2
    mov r11, r8
egg_word_row:
    mov r10, r6
egg_word_col:
    mov r0, r10
    mov r1, r11
    bl egg_lit
    cmp r0, #0
    beq egg_word_next
    sub r0, r10, r6
    add r0, r0, r0, lsl #1
    ldr r1, [sp]
    add r0, r0, r1
    sub r1, r11, r8
    ldr r2, [sp, #4]
    add r1, r2, r1, lsl #2
    mov r2, #3
    mov r3, #4
    mov r12, #1
    bl display_fill
egg_word_next:
    add r10, r10, #1
    cmp r10, r7
    ble egg_word_col
    add r11, r11, #1
    cmp r11, r9
    ble egg_word_row
egg_word_done:
    add sp, sp, #8
    pop {r4-r11, pc}

; r0 = x, r1 = y, r4 = the frame buffer -> r0 = 1 when that pixel is set. Clobbers r1, r2.
egg_lit:
    mov r2, r1, lsr #3
    add r2, r4, r2, lsl #7
    ldrb r2, [r2, r0]
    and r1, r1, #7
    mov r0, r2, lsr r1
    and r0, r0, #1
    bx lr

; The start image: the firmware draws image 13 (the one the splash editor stored, or the set's) into its frame buffer, which goes
; whole into the runtime's picture. Keeps r4 to r11.
egg_draw_image:
    push {r4, lr}
    sub sp, sp, #16
    bl egg_clear_frame
    mov r0, #13
    str r0, [sp]
    mov r0, #0
    str r0, [sp, #4]
    str r0, [sp, #8]
    mov r0, sp
    add r1, sp, #4
    add r2, sp, #8
    bl 0xC003F650
    ldr r0, =MG_VRAM
    ldr r1, =DISPLAY_FB
    mov r2, #1024
egg_image_copy:
    subs r2, r2, #4
    ldr r3, [r0, r2]
    str r3, [r1, r2]
    bne egg_image_copy
    ldr r0, =HOOK_RUNTIME
    mov r1, #1
    str r1, [r0, #SCRIPT_CONTROL_DISPLAY_ACTIVE]
    add sp, sp, #16
    pop {r4, pc}
.pool

str_egg_word:
    .asciz "AUTISM"
str_egg_new:
    .asciz "NEW SAMPLE"
str_egg_unlocked:
    .asciz "Unlocked"
; per LED number (data/script/names.mjs): 0 one LED, 1 the red (first) LED of a key or pad with two, 2 its blue one
egg_led_roles:
    .byte 0,0,0,0,0, 0,0,0,0,1, 0,0,0,0,0, 0,0,0,0,0
    .byte 0,2,2,2,2, 2,0,0,0,0, 0,0,0,0,0, 0,0,0,0,0
    .byte 1,1,1,1,1, 2,1,2,1,2, 1,2,1,2,1, 2,1,2,1,2
    .byte 1,2,1,2,1, 2,1,2,1,2, 1,2,1,2,1, 2
.align 4
