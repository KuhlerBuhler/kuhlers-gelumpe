; Clock and read-only views of the firmware's state for the script API.
; Every address is a RAM address of firmware 2.02 with Hacktribe (docs/messungen/2026-10-14-skript-hardware.md).
.equ HW_TRANSPORT, 0xC06BC318
.equ HW_TEMPO, 0xC0691518
.equ HW_PATTERN, 0xC06B2420
.equ HW_PART, 0xC06B2428
.equ HW_STEP, 0xC06904B0
.equ HW_MUTE, 0xC06B2F9D

; r0 runtime. Adds the Timer3 ticks since the last call to the millisecond count and returns it. The counter wraps at SCRIPT_TIMER_PERIOD.
script_clock_update:
    ldr r1, =SCRIPT_TIMER_ADDRESS
    ldr r1, [r1]
    ldr r2, [r0, #SCRIPT_CONTROL_CLOCK_INIT]
    cmp r2, #0
    bne clock_running
    mov r2, #1
    str r2, [r0, #SCRIPT_CONTROL_CLOCK_INIT]
    str r1, [r0, #SCRIPT_CONTROL_CLOCK_LAST]
    mov r2, #0
    str r2, [r0, #SCRIPT_CONTROL_CLOCK_REM]
    str r2, [r0, #SCRIPT_CONTROL_CLOCK_MS]
    mov r0, #0
    bx lr
clock_running:
    ldr r2, [r0, #SCRIPT_CONTROL_CLOCK_LAST]
    cmp r1, r2
    sub r2, r1, r2
    ldrlo r3, =SCRIPT_TIMER_PERIOD
    addlo r2, r2, r3
    str r1, [r0, #SCRIPT_CONTROL_CLOCK_LAST]
    ldr r3, [r0, #SCRIPT_CONTROL_CLOCK_REM]
    add r3, r3, r2
    ldr r2, [r0, #SCRIPT_CONTROL_CLOCK_MS]
    ldr r1, =SCRIPT_TIMER_TICKS_PER_MS
clock_carry:
    cmp r3, r1
    subhs r3, r3, r1
    addhs r2, r2, #1
    bhs clock_carry
    str r3, [r0, #SCRIPT_CONTROL_CLOCK_REM]
    str r2, [r0, #SCRIPT_CONTROL_CLOCK_MS]
    mov r0, r2
    bx lr
.pool

script_clock_millis_glue:
    push {lr}
    ldr r0, =HOOK_RUNTIME
    bl script_clock_update
    pop {lr}
    mov r1, #ERR_OK
    bx lr
.pool

script_read_transport_glue:
    ldr r0, =HW_TRANSPORT
    ldr r0, [r0]
    mov r1, #ERR_OK
    bx lr

script_read_tempo_glue:
    ldr r0, =HW_TEMPO
    ldr r0, [r0]
    mov r1, #ERR_OK
    bx lr

script_read_pattern_glue:
    ldr r0, =HW_PATTERN
    ldr r0, [r0]
    mov r1, #ERR_OK
    bx lr

script_read_part_glue:
    ldr r0, =HW_PART
    ldr r0, [r0]
    mov r1, #ERR_OK
    bx lr

; r0 part -> step counter of that part, 0 to 63.
script_read_step_glue:
    cmp r0, #16
    bhs hw_bad_arg
    mov r1, r0, lsl #6
    add r1, r1, r0, lsl #3
    ldr r2, =HW_STEP
    ldr r0, [r2, r1]
    mov r1, #ERR_OK
    bx lr

; r0 part -> 1 when the part is muted.
script_read_mute_glue:
    cmp r0, #16
    bhs hw_bad_arg
    mov r1, r0, lsl #9
    add r1, r1, r0, lsl #8
    add r1, r1, r0, lsl #5
    add r1, r1, r0, lsl #4
    ldr r2, =HW_MUTE
    ldrb r0, [r2, r1]
    cmp r0, #0
    movne r0, #1
    mov r1, #ERR_OK
    bx lr

; r0 knob index -> the last raw value the input filter saw for it, 0 before it moved.
script_read_knob_glue:
    cmp r0, #SCRIPT_KNOBS
    bhs hw_bad_arg
    ldr r1, =HOOK_RUNTIME+RT_KNOBS
    ldr r0, [r1, r0, lsl #2]
    mov r1, #ERR_OK
    bx lr

hw_bad_arg:
    mov r0, #0
    mov r1, #ERR_API_ARG
    bx lr
.pool

; Actions: the firmware's own calls, made from the UiTask in the frame hook. Arguments are range checked by the VM.
.equ HW_PATTERN_SELECT, 0xC0081F50
.equ HW_TEMPO_SET, 0xC004A80C
.equ HW_MUTE_SET, 0xC0060C74
.equ HW_MODEL, 0xC06B2108
.equ HW_PATTERN_OBJECT, 0xC06B2798
.equ HW_KEY_STOP, 1
.equ HW_KEY_PLAY, 2

; PLAY pressed and released through the panel path, as the firmware does for the key.
script_play_glue:
    mov r2, #HW_KEY_PLAY
    b hw_press_key

script_stop_glue:
    mov r2, #HW_KEY_STOP

hw_press_key:
    push {r4, lr}
    mov r4, r2
    mov r0, r4
    mov r1, #1
    ldr r12, =HW_PANEL_KEY
    blx r12
    mov r0, r4
    mov r1, #0
    ldr r12, =HW_PANEL_KEY
    blx r12
    mov r0, #0
    mov r1, #ERR_OK
    pop {r4, pc}

; r0 pattern index.
script_pattern_glue:
    push {lr}
    cmp r0, #250
    bhs hw_pop_bad_arg
    mov r1, r0
    ldr r0, =HW_MODEL
    mov r2, #1
    ldr r12, =HW_PATTERN_SELECT
    blx r12
    b hw_pop_ok

; r0 tempo in tenths of a BPM.
script_tempo_glue:
    push {lr}
    sub r1, r0, #100
    ldr r2, =2900
    cmp r1, r2
    bhi hw_pop_bad_arg
    mov r1, r0
    ldr r0, =HW_PATTERN_OBJECT
    mov r2, #1
    ldr r12, =HW_TEMPO_SET
    blx r12
    b hw_pop_ok

; r0 part 0 to 15.
script_part_glue:
    push {lr}
    cmp r0, #16
    bhs hw_pop_bad_arg
    mov r1, r0
    ldr r0, =HW_MODEL
    ldr r12, =HW_PART_SELECT
    blx r12
    b hw_pop_ok

; r0 part, r1 1 to mute and 0 to play. The firmware call is the mute pad: a press (1) toggles, the release (0) does nothing,
; so it is pressed only when the part is not in the wanted state.
script_mute_glue:
    push {r4, r5, lr}
    cmp r0, #16
    bhs hw_pop3_bad_arg
    cmp r1, #1
    bhi hw_pop3_bad_arg
    mov r4, r0
    mov r5, r1
    mov r1, r0, lsl #9
    add r1, r1, r0, lsl #8
    add r1, r1, r0, lsl #5
    add r1, r1, r0, lsl #4
    ldr r2, =HW_MUTE
    ldrb r2, [r2, r1]
    cmp r2, #0
    movne r2, #1
    cmp r2, r5
    beq hw_pop3_ok
    ldr r0, =HW_MUTE_OBJECT
    mov r1, r4
    mov r2, #1
    ldr r12, =HW_MUTE_SET
    blx r12
    ldr r0, =HW_MUTE_OBJECT
    mov r1, r4
    mov r2, #0
    ldr r12, =HW_MUTE_SET
    blx r12
hw_pop3_ok:
    mov r0, #0
    mov r1, #ERR_OK
    pop {r4, r5, pc}
hw_pop3_bad_arg:
    mov r0, #0
    mov r1, #ERR_API_ARG
    pop {r4, r5, pc}
.pool
hw_pop_ok:
    mov r0, #0
    mov r1, #ERR_OK
    pop {pc}
hw_pop_bad_arg:
    mov r0, #0
    mov r1, #ERR_API_ARG
    pop {pc}
.pool

; Hardware outside the panel: the display light and the firmware's own LED rewriting.
.equ HW_GPIO, 0x01E26000
.equ HW_GPIO_WRITE, 0xC0016BB4
.equ HW_LED_MANAGER, 0xC0345A1C
.equ HW_LED_REFRESH, 0xC00875F4
.equ HW_LED_HOLD_BYTE, 0xB98
.equ HW_LED_LAST, 0x57

; r0 red, r1 green, r2 blue: 1 lights that colour of the display light, 0 darkens it. Not held against the dimming on battery.
script_backlight_glue:
    push {r4-r6, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    ldr r0, =HW_GPIO
    mov r1, r4
    mov r2, #3
    mov r3, #0x08
    ldr r12, =HW_GPIO_WRITE
    blx r12
    ldr r0, =HW_GPIO
    mov r1, r5
    mov r2, #3
    mov r3, #0x10
    ldr r12, =HW_GPIO_WRITE
    blx r12
    ldr r0, =HW_GPIO
    mov r1, r6
    mov r2, #3
    mov r3, #0x20
    ldr r12, =HW_GPIO_WRITE
    blx r12
    mov r0, #0
    mov r1, #ERR_OK
    pop {r4-r6, pc}

; r0 1 to keep the firmware from rewriting the panel LEDs (the pads, keys and the lower RGB LEDs then show what the script
; set), 0 to give them back: the firmware is then asked to send every LED again.
script_led_hold_glue:
    push {r4-r6, lr}
    mov r4, r0
    ldr r5, =HW_LED_MANAGER
    ldr r5, [r5]
    cmp r5, #0
    beq led_hold_done
    cmn r5, #1
    beq led_hold_done
    ldr r6, =HOOK_RUNTIME
    ldr r0, [r6, #SCRIPT_CONTROL_LED_HOLD]
    cmp r0, r4
    beq led_hold_done
    str r4, [r6, #SCRIPT_CONTROL_LED_HOLD]
    strb r4, [r5, #HW_LED_HOLD_BYTE]
    cmp r4, #0
    bne led_hold_done
    mov r6, #0
led_hold_refresh:
    mov r0, r5
    mov r1, r6
    mov r2, #1
    ldr r12, =HW_LED_REFRESH
    blx r12
    add r6, r6, #1
    cmp r6, #HW_LED_LAST+1
    blo led_hold_refresh
led_hold_done:
    mov r0, #0
    mov r1, #ERR_OK
    pop {r4-r6, pc}

; r0 runtime. Gives the LEDs back when a script held them and none is left to run.
script_led_hold_guard:
    ldr r1, [r0, #SCRIPT_CONTROL_LED_HOLD]
    cmp r1, #0
    bxeq lr
    ldr r1, [r0, #RT_HEAD]
led_guard_entry:
    cmp r1, #0
    beq led_guard_release
    ldr r2, [r1, #SCRIPT_ENTRY_STATE]
    cmp r2, #SCRIPT_STATE_ARMED
    bne led_guard_next
    ldr r2, [r1, #SCRIPT_ENTRY_BLOB]
    ldr r3, =HOOK_POOL
    cmp r2, r3
    bxhs lr
led_guard_next:
    ldr r1, [r1, #SCRIPT_ENTRY_NEXT]
    b led_guard_entry
led_guard_release:
    push {lr}
    mov r0, #0
    bl script_led_hold_glue
    pop {pc}
.pool
