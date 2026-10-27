; korg.display.*: drawing into the runtime's own 1 KiB picture, and its copy
; over the firmware display RAM once per frame. Arguments are range checked by
; the VM; coordinates that run past the edge are cut off, never wrapped.
.equ DISPLAY_FB, HOOK_RUNTIME+RT_DISPLAY

; Drawing is taken from the open app only: any other script's drawing calls do nothing (and say nothing). Z is set
; when the running script owns the display. Keeps r0 to r3.
display_gate:
    push {r0, r1}
    ldr r0, =HOOK_RUNTIME
    ldr r1, [r0, #RT_ENTRY]
    ldr r0, =APP_STATE
    ldr r0, [r0]
    cmp r0, r1
    pop {r0, r1}
    bx lr
.pool

display_denied:
    mov r0, #0
    mov r1, #ERR_OK
    bx lr

display_done:
    ldr r2, =HOOK_RUNTIME
    mov r3, #1
    str r3, [r2, #SCRIPT_CONTROL_DISPLAY_ACTIVE]
    mov r0, #0
    mov r1, #ERR_OK
    bx lr
.pool

script_display_clear_glue:
    push {lr}
    bl display_gate
    pop {lr}
    bne display_denied
    push {lr}
    bl display_clear
    pop {lr}
    b display_done

display_clear:
    ldr r0, =DISPLAY_FB
    mov r1, #0
    mov r2, #SCRIPT_DISPLAY_BYTES
display_clear_loop:
    subs r2, r2, #4
    str r1, [r0, r2]
    bne display_clear_loop
    bx lr
.pool

; r0 x, r1 y, r2 on. Leaf, clobbers r0-r3 and r12.
display_set_pixel:
    cmp r0, #SCRIPT_DISPLAY_WIDTH
    bxhs lr
    cmp r1, #SCRIPT_DISPLAY_HEIGHT
    bxhs lr
    ldr r3, =DISPLAY_FB
    mov r12, r1, lsr #3
    add r3, r3, r12, lsl #7
    add r3, r3, r0
    and r12, r1, #7
    mov r1, #1
    mov r1, r1, lsl r12
    ldrb r12, [r3]
    cmp r2, #0
    orrne r12, r12, r1
    biceq r12, r12, r1
    strb r12, [r3]
    bx lr
.pool

script_display_pixel_glue:
    push {lr}
    bl display_gate
    pop {lr}
    bne display_denied
    push {lr}
    bl display_set_pixel
    pop {lr}
    b display_done

script_display_rect_glue:
    push {lr}
    bl display_gate
    pop {lr}
    bne display_denied
    mov r12, #1
    b display_fill

script_display_clear_rect_glue:
    push {lr}
    bl display_gate
    pop {lr}
    bne display_denied
    mov r12, #0

; r0 x, r1 y, r2 width, r3 height, r12 1 to fill or 0 to clear.
display_fill:
    push {r4-r11, lr}
    sub sp, sp, #8
    add r2, r0, r2
    cmp r2, #SCRIPT_DISPLAY_WIDTH
    movhi r2, #SCRIPT_DISPLAY_WIDTH
    add r3, r1, r3
    cmp r3, #SCRIPT_DISPLAY_HEIGHT
    movhi r3, #SCRIPT_DISPLAY_HEIGHT
    cmp r0, r2
    bhs fill_done
    cmp r1, r3
    bhs fill_done
    sub r3, r3, #1
    mov r4, r1, lsr #3
    mov r5, r3, lsr #3
    mov r6, r4
fill_masks:
    mov r8, r6, lsl #3
    subs r9, r1, r8
    movlt r9, #0
    sub r10, r3, r8
    cmp r10, #7
    movgt r10, #7
    rsb r10, r10, #7
    mov r11, #0xFF
    mov r11, r11, lsr r10
    mov r7, #0xFF
    mov r7, r7, lsl r9
    and r7, r7, r11
    and r7, r7, #0xFF
    strb r7, [sp, r6]
    add r6, r6, #1
    cmp r6, r5
    bls fill_masks
    ldr r9, =DISPLAY_FB
    mov r6, r0
fill_column:
    mov r7, r4
fill_page:
    ldrb r8, [sp, r7]
    add r10, r9, r7, lsl #7
    add r10, r10, r6
    ldrb r11, [r10]
    cmp r12, #0
    orrne r11, r11, r8
    biceq r11, r11, r8
    strb r11, [r10]
    add r7, r7, #1
    cmp r7, r5
    bls fill_page
    add r6, r6, #1
    cmp r6, r2
    blo fill_column
fill_done:
    add sp, sp, #8
    pop {r4-r11, lr}
    b display_done
.pool

; r4 NUL terminated text, r5 x, r6 y. Draws lit pixels only, stops at the right edge.
display_draw_text:
    push {r7-r10, lr}
draw_char:
    ldrb r7, [r4], #1
    cmp r7, #0
    beq draw_done
    cmp r5, #SCRIPT_DISPLAY_WIDTH
    bge draw_done
    sub r7, r7, #32
    cmp r7, #95
    movhs r7, #31
    add r7, r7, r7, lsl #2
    ldr r8, =SCRIPT_FONT
    add r7, r8, r7
    mov r8, #0
draw_column:
    ldrb r9, [r7, r8]
    mov r10, #0
draw_row:
    mov r12, r9, lsr r10
    tst r12, #1
    beq draw_next_row
    add r0, r5, r8
    add r1, r6, r10
    mov r2, #1
    bl display_set_pixel
draw_next_row:
    add r10, r10, #1
    cmp r10, #7
    blo draw_row
    add r8, r8, #1
    cmp r8, #5
    blo draw_column
    add r5, r5, #6
    b draw_char
draw_done:
    pop {r7-r10, lr}
    bx lr
.pool

script_display_text_glue:
    push {lr}
    bl display_gate
    pop {lr}
    bne display_denied
    push {r4-r6, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    bl display_draw_text
    pop {r4-r6, lr}
    b display_done

; r0 signed value, r5 x, r6 y.
display_draw_number:
    push {r4, r7-r11, lr}
    sub sp, sp, #16
    mov r4, sp
    mov r7, r0
    cmp r7, #0
    bge number_digits
    mov r8, #45
    strb r8, [r4], #1
    rsb r7, r7, #0
number_digits:
    ldr r10, =display_powers
    mov r9, #0
    mov r11, #0
number_digit:
    ldr r1, [r10, r11, lsl #2]
    mov r0, #0
number_subtract:
    cmp r7, r1
    blo number_emit
    sub r7, r7, r1
    add r0, r0, #1
    b number_subtract
number_emit:
    cmp r11, #9
    beq number_write
    cmp r0, #0
    bne number_write
    cmp r9, #0
    beq number_next
number_write:
    mov r9, #1
    add r0, r0, #48
    strb r0, [r4], #1
number_next:
    add r11, r11, #1
    cmp r11, #10
    blo number_digit
    mov r0, #0
    strb r0, [r4]
    mov r4, sp
    bl display_draw_text
    add sp, sp, #16
    pop {r4, r7-r11, lr}
    bx lr
display_powers:
    .word 1000000000, 100000000, 10000000, 1000000, 100000, 10000, 1000, 100, 10, 1
.pool

script_display_number_glue:
    push {lr}
    bl display_gate
    pop {lr}
    bne display_denied
    push {r5, r6, lr}
    mov r5, r1
    mov r6, r2
    bl display_draw_number
    pop {r5, r6, lr}
    b display_done

; r0 text, r1 signed value, r2 x, r3 y. Text first, the number right behind its last character.
script_display_text_number_glue:
    push {lr}
    bl display_gate
    pop {lr}
    bne display_denied
    push {r4-r8, lr}
    mov r4, r0
    mov r8, r1
    mov r5, r2
    mov r6, r3
    bl display_draw_text
    mov r0, r8
    bl display_draw_number
    pop {r4-r8, lr}
    b display_done

; r0 array handle (first slot in the low half, length in the high half, checked by the VM), r1 x, r2 y, r3 width.
; The slots are columns of 8 pixels, a band is `width` of them, bit 0 on top. Only lit pixels are set; what lies beyond
; the display is skipped. r4 slots of the band, r5 slots left, r6 width, r7 x, r8 shift (y and 7), r9 page of the band
; (y asr 3, plus one for each band), r10 first column, r11 end column, r1 address of the band's page at x, r2 column.
script_display_bitmap_glue:
    push {lr}
    bl display_gate
    pop {lr}
    bne display_denied
    push {r4-r11, lr}
    ldr r4, =HOOK_RUNTIME
    ldr r4, [r4, #RT_ENTRY]
    ldr r4, [r4, #SCRIPT_ENTRY_VARS]
    mov r5, r0, lsl #16
    add r4, r4, r5, lsr #14
    mov r5, r0, lsr #16
    mov r6, r3
    mov r7, r1
    and r8, r2, #7
    mov r9, r2, asr #3
    rsbs r10, r7, #0
    movlt r10, #0
    rsb r11, r7, #SCRIPT_DISPLAY_WIDTH
    cmp r11, r6
    movhi r11, r6
    cmp r10, r11
    bhs bitmap_done
bitmap_band:
    cmp r5, r6
    blo bitmap_done
    cmp r9, #7
    bgt bitmap_done
    cmn r9, #1
    blt bitmap_next
    ldr r1, =DISPLAY_FB
    add r1, r1, r7
    add r1, r1, r9, lsl #7
    mov r2, r10
bitmap_column:
    cmp r2, r11
    bhs bitmap_next
    ldr r3, [r4, r2, lsl #2]
    ands r3, r3, #0xFF
    beq bitmap_skip
    cmp r9, #0
    blt bitmap_high
    mov r12, r3, lsl r8
    ands r12, r12, #0xFF
    beq bitmap_high
    ldrb r0, [r1, r2]
    orr r0, r0, r12
    strb r0, [r1, r2]
bitmap_high:
    cmp r8, #0
    beq bitmap_skip
    add r12, r9, #1
    cmp r12, #7
    bhi bitmap_skip
    rsb r0, r8, #8
    movs r3, r3, lsr r0
    beq bitmap_skip
    add r12, r1, r2
    ldrb r0, [r12, #128]
    orr r0, r0, r3
    strb r0, [r12, #128]
bitmap_skip:
    add r2, r2, #1
    b bitmap_column
bitmap_next:
    add r4, r4, r6, lsl #2
    sub r5, r5, r6
    add r9, r9, #1
    b bitmap_band
bitmap_done:
    pop {r4-r11, lr}
    b display_done
.pool

; r0 runtime. Copies the picture over the firmware's display RAM while an app is open and the main screen shows, or
; while the built-in app is open and its page in the menu ring shows and no window lies over it (the Power Off window
; has its own picture: the screen manager's word at +0x24 points at a window, 0 when there is none).
; Blechy's page is always dark: the LCD turns a pixel dark fast but clear only in about 0.3 s, so a dark figure on a clear
; field drags a smear wherever he walks. With DISPLAY INVERT OFF his picture goes over complemented (r12 = FFFFFFFF), so
; the display shows him light on dark as with DISPLAY INVERT ON. Only for him (his block lies outside the pool), never for
; a plugin app or the page DESCRIPTION.
script_display_blit:
    mov r12, #0
    ldr r1, [r0, #SCRIPT_CONTROL_DISPLAY_ACTIVE]
    cmp r1, #1
    bxne lr
    ldr r1, =SCREEN_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    bxeq lr
    cmn r1, #1
    bxeq lr
    ldr r1, [r1, #0x2c]
    ldr r2, =MENU_STATE
    cmp r1, #MENU_SCREEN
    bne blit_app
    ldrb r3, [r2, #M_DESC_ON]   ; the page DESCRIPTION draws its description into the picture (menu_desc_frame)
    cmp r3, #1
    beq blit_menu
blit_app:
    ldr r3, =APP_STATE
    ldr r3, [r3]
    cmp r3, #0
    bxeq lr
    cmp r1, #1
    beq blit_go
    cmp r1, #MENU_SCREEN
    bxne lr
    ldr r1, [r2, #M_LEVEL]
    cmp r1, #M_LEVEL_BLECHY
    bxne lr
    ldr r1, [r2, #M_INV]
    ldr r2, [r3, #SCRIPT_ENTRY_BLOB]
    ldr r3, =HOOK_POOL
    cmp r2, r3
    bhs blit_menu
    cmp r1, #0
    mvneq r12, #0
blit_menu:
    ldr r1, =SCREEN_MANAGER
    ldr r1, [r1]
    ldr r1, [r1, #0x24]
    cmp r1, #0
    bxne lr
blit_go:
    push {r4-r11}
    ldr r2, =RT_DISPLAY
    add r2, r0, r2
    ldr r3, =SCRIPT_DISPLAY_RAM
    mov r1, #SCRIPT_DISPLAY_BYTES/32
blit_loop:
    ldmia r2!, {r4-r11}
    eor r4, r4, r12
    eor r5, r5, r12
    eor r6, r6, r12
    eor r7, r7, r12
    eor r8, r8, r12
    eor r9, r9, r12
    eor r10, r10, r12
    eor r11, r11, r12
    stmia r3!, {r4-r11}
    subs r1, r1, #1
    bne blit_loop
    pop {r4-r11}
    bx lr
.pool

; r0 runtime, r1 script entry. Replaces the picture with the script name, the source line and the error name.
script_display_fault:
    ldr r2, =APP_STATE
    ldr r2, [r2]
    cmp r2, r1
    bxne lr
    push {r4-r11, lr}
    sub sp, sp, #32
    mov r7, r1
    bl display_clear
    ldr r6, [r7, #SCRIPT_ENTRY_BLOB]
    add r6, r6, #HDR_NAME
    mov r0, #0
fault_name:
    ldrb r1, [r6, r0]
    strb r1, [sp, r0]
    cmp r1, #0
    beq fault_name_done
    add r0, r0, #1
    cmp r0, #15
    blo fault_name
    mov r1, #0
    strb r1, [sp, r0]
fault_name_done:
    mov r4, sp
    mov r5, #4                  ; 4 pixels from the side, 2 from the top, as the firmware's menus
    mov r6, #2
    bl display_draw_text
    ldr r4, =fault_label
    mov r5, #4
    mov r6, #12
    bl display_draw_text
    ldr r0, [r7, #SCRIPT_ENTRY_LINE]
    mov r5, #40
    mov r6, #12
    bl display_draw_number
    ldr r0, [r7, #SCRIPT_ENTRY_FAULT]
    cmp r0, #SCRIPT_ERROR_COUNT
    movhs r0, #0
    ldr r4, =SCRIPT_ERROR_NAMES
    add r4, r4, r0, lsl #4
    mov r5, #4
    mov r6, #22
    bl display_draw_text
    ldr r2, =HOOK_RUNTIME
    mov r3, #1
    str r3, [r2, #SCRIPT_CONTROL_DISPLAY_ACTIVE]
    add sp, sp, #32
    pop {r4-r11, pc}
fault_label:
    .asciz "Line"
.align 4
.pool
