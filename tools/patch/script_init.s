; The page INIT PATTERN of the BLECH menu's FEATURES (kind 40, script_menu.s): which pattern DATA UTILITY's INITIALIZE PATTERN
; copies (the patch init-pattern, tools/patch/init_pattern.py). In the third code area: the first one is full.
; INIT PATTERN: the pattern DATA UTILITY's INITIALIZE PATTERN copies (Global byte 247, the number plus one), FACTORY for the firmware's template
menu_text_ip:
    mov r0, #3
    bl menu_title_prefix
    ldr r1, =str_ip
    bl menu_copy
    bl menu_ip_at
    add r0, r5, #M_VALUE
    subs r1, r3, #1
    ldrmi r1, =str_factory
    bmi menu_text_app_value
    add r1, r1, #1
    bl menu_dec
    b menu_text_look_line3
; INIT PATTERN: 0 (FACTORY) to 250 into Global byte 247, at once; the firmware saves the Globals at switch-off
menu_value_ip:
    bl menu_ip_at
    cmp r2, #0
    beq menu_value_done
    adds r3, r3, r5
    movmi r3, #0
    cmp r3, #250
    movgt r3, #250
    strb r3, [r2, #IP_SLOT]
    mov r3, #0
    str r3, [r6, #M_STATUS]
    b menu_value_done
; -> r2 = the Global settings (0 before they exist), r3 = Global byte 247 there
menu_ip_at:
    ldr r2, =GLOBALS_PTR
    ldr r2, [r2]
    cmp r2, #0
    moveq r3, #0
    ldrbne r3, [r2, #IP_SLOT]
    bx lr
str_ip:
    .asciz "INIT PATTERN"
str_factory:
    .asciz "FACTORY"
.align 2
.pool
