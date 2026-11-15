; IDLE POWER SAVE (CUSTOMIZATION > POWER SAVE > IDLE SAVE, ON by default): with no touch for 2 minutes the backlight and the
; LEDs dim to 75 percent, after 3 minutes to 50, after 4 to 25, after 5 they go dark. A touch (key, pad, knob, encoder, touchpad,
; idle_input in script_hooks.s), a MIDI note or CC (script_midi.s), PLAY and korg.system.keepAwake() (script_remote.s) start
; the time again. The first touch while dimmed or dark wakes the device and is swallowed with all that belongs to it.
; The light: menu_look_apply scales INTENSITY and SAVE LIGHT by the stage (script_menu.s:idle_scale); with SAVE LIGHT 0 the
; firmware's own power save dim stays as it is until the stage goes dark (bl_pwm_save_none). The LEDs: the patch pad-colors
; scales every LED message by the percent kept (its S_IDLE byte, PC_IDLE), a plugin's LEDs are scaled in script_led_try_send,
; a plugin's korg.backlight is held from stage 1 on and comes back on waking. The test mode goes first: it keeps the device
; awake. With EXIT held at power-on menu_arm never runs, IS_STAGE stays FF and nothing of this runs.
; Measured in docs/messungen/2026-11-14-energie-befunde.md ("Idle Power Save").
.equ IS_LAST, 0                 ; the OS tick (1 ms) of the last touch, MIDI note or CC, PLAY or keepAwake
.equ IS_STAGE, 4                ; byte: the stage shown, 0 awake, 1 to 3 dimmed, 4 dark; FF before menu_arm
.equ IS_KEEP, 5                 ; byte: the percent of the LEDs' brightness kept in that stage (100, 75, 50, 25, 0)
.equ IS_BL, 6                   ; byte: a plugin's last korg.backlight (bit 0 red, 1 green, 2 blue), FF none
.equ IS_FRESH, 0x00FF6400       ; the word at IS_STAGE after menu_arm: stage 0, 100 kept, no backlight of a plugin
.equ IS_KEYS, 8                 ; 2 words: a bit per key whose press woke the device; its release is swallowed too
.equ IS_PADS, 16                ; a bit per pad whose press woke the device; its pressure and its release are swallowed too
.equ IS_KNOBS, 20               ; 20 bytes: the raw value each knob was last seen at, FF none yet
.equ IDLE_SIZE, 40
.equ IDLE_KNOBS, 17             ; knob messages 0 to 16 are the knobs; 17 on are the other ADC inputs, never a touch
.equ IDLE_KNOB_MOVE, 2          ; a knob counts as touched once it moved this far from where it was last seen (ADC noise is 1)
.equ IDLE_TOUCH_KEY, 34         ; the key message of the touchpad (byte 0x0e 1 touched, 0 let go)
.equ IDLE_FIRST_MS, 120000      ; stage 1 after 2 minutes
.equ IDLE_STEP_MS, 60000        ; each further stage a minute later
.equ IDLE_TICKS, OS_TICKS
.equ PC_IDLE, PC_CODE + 0xF8C   ; pad_colors.py STATE + S_IDLE: the percent the LED messages keep, FF never written

; Once a frame, past the first main screen. Works out the stage from the time since the last touch and, when it changed, sets
; the light, the LEDs of the firmware and those of the plugins to it. Keeps r4 to r11.
idle_frame:
    push {r4-r7, lr}
    ldr r4, =IDLE
    ldr r0, =MENU_STATE
    ldr r1, [r0, #M_ON]
    cmp r1, #1
    bne idle_frame_out
    ldrb r7, [r4, #IS_STAGE]
    cmp r7, #4
    bhi idle_frame_out
    ldr r5, =IDLE_TICKS
    ldr r5, [r5]
    ldr r1, =objects_test_mode
    ldrb r1, [r1]
    cmp r1, #0
    beq idle_frame_mode
    str r5, [r4, #IS_LAST]      ; the test mode keeps the device awake and owns the light and the LEDs; its end sends them again
    cmp r7, #0
    beq idle_frame_out
    mov r6, #0
    bl idle_keep_store
    b idle_frame_out
idle_frame_mode:
    ldrb r1, [r0, #MX_FLAGS2]
    mov r6, #0
    tst r1, #FLAGS2_IDLE_OFF
    bne idle_frame_stage
    ldr r1, =HW_TRANSPORT       ; PLAY keeps the device awake
    ldr r1, [r1]
    cmp r1, #0
    strne r5, [r4, #IS_LAST]
    ldr r1, [r4, #IS_LAST]
    sub r1, r5, r1              ; signed: a touch noted after the tick was read is no time at all
    ldr r2, =IDLE_FIRST_MS
    subs r1, r1, r2
    bmi idle_frame_stage
    mov r6, #1
    ldr r2, =IDLE_STEP_MS
idle_frame_count:
    cmp r6, #4
    beq idle_frame_stage
    subs r1, r1, r2
    addpl r6, r6, #1
    bpl idle_frame_count
idle_frame_stage:
    cmp r6, r7
    beq idle_frame_out
    bl idle_keep_store
    bl menu_look_apply
    bl idle_leds
    cmp r6, #0
    bne idle_frame_out
    ldrb r0, [r4, #IS_BL]       ; awake again: a plugin's own light comes back
    cmp r0, #0xFF
    beq idle_frame_out
    ands r1, r0, #2
    movne r1, #1
    ands r2, r0, #4
    movne r2, #1
    and r0, r0, #1
    bl script_backlight_glue
idle_frame_out:
    pop {r4-r7, pc}

; r4 = IDLE, r6 = the stage: noted with the percent the LEDs keep, which the patch pad-colors reads where the set has it.
; Clobbers r0 and r1.
idle_keep_store:
    strb r6, [r4, #IS_STAGE]
    ldr r0, =idle_keeps
    ldrb r0, [r0, r6]
    strb r0, [r4, #IS_KEEP]
    ldr r1, =PC_CODE
    ldr r1, [r1]
    cmn r1, #1
    ldrne r1, =PC_IDLE
    strbne r0, [r1]
    bx lr
idle_keeps:
    .byte 100, 75, 50, 25, 0
.align 4

; Every LED out again at the new brightness: the firmware's (forced, so the meter LEDs go too) where nothing holds them from
; it (a plugin's korg.ledHold, the test mode), and every LED a plugin set (script_led_try_send scales it).
; Clobbers r0 to r3 and r12.
idle_leds:
    push {r4-r6, lr}
    ldr r4, =HOOK_RUNTIME
    ldr r5, =RT_LED
    add r5, r4, r5
    ldr r0, [r4, #SCRIPT_CONTROL_LED_HOLD]
    cmp r0, #0
    bne idle_leds_plugins
    ldr r6, =HW_LED_MANAGER
    ldr r6, [r6]
    cmp r6, #0
    cmnne r6, #1
    beq idle_leds_plugins
    ldrb r0, [r6, #HW_LED_HOLD_BYTE]
    cmp r0, #0
    bne idle_leds_plugins
    mov r4, #0
idle_leds_firmware:
    mov r0, r6
    mov r1, r4
    mov r2, #1
    ldr r12, =HW_LED_REFRESH
    blx r12
    add r4, r4, #1
    cmp r4, #HW_LED_LAST+1
    blo idle_leds_firmware
idle_leds_plugins:
    mov r3, #0
    mov r2, #1
idle_leds_plugin:
    add r1, r5, #SCRIPT_LED_VALID
    ldrb r0, [r1, r3]
    tst r0, #SCRIPT_LED_VALID_DESIRED
    addne r1, r5, #SCRIPT_LED_PENDING
    strbne r2, [r1, r3]
    add r3, r3, #1
    cmp r3, #SCRIPT_LED_COUNT
    blo idle_leds_plugin
    pop {r4-r6, pc}
.pool
