; Clock and read-only views of the firmware's state for the script API.
; Every address is a RAM address of firmware 2.02 with Hacktribe (docs/messungen/2026-10-14-skript-hardware.md).
.equ HW_TRANSPORT, 0xC06BC318
.equ HW_TEMPO, 0xC0691518
.equ HW_PATTERN, 0xC06B2420
.equ HW_PART, 0xC06B2428
.equ HW_STEP, 0xC06904B0
.equ HW_MUTE, 0xC06B2F9D

.equ OS_TICKS, 0xC06A292C

; r0 runtime. Adds the Timer3 ticks since the last call to the millisecond count and returns it. Timer3 wraps every second
; (SCRIPT_TIMER_PERIOD), so a gap of more than a second between two calls (the start with its sample load, before the first
; frame) would lose whole seconds: the OS tick count, one per millisecond, tells how many, Timer3 the rest. Preserves r4 to r11.
script_clock_update:
    push {r4, r5}
    ldr r1, =SCRIPT_TIMER_ADDRESS
    ldr r1, [r1]
    ldr r4, =OS_TICKS
    ldr r4, [r4]
    ldr r5, =clock_ticks_last
    ldr r2, [r0, #SCRIPT_CONTROL_CLOCK_INIT]
    cmp r2, #0
    bne clock_running
    mov r2, #1
    str r2, [r0, #SCRIPT_CONTROL_CLOCK_INIT]
    str r1, [r0, #SCRIPT_CONTROL_CLOCK_LAST]
    str r4, [r5]
    mov r2, #0
    str r2, [r0, #SCRIPT_CONTROL_CLOCK_REM]
    str r2, [r0, #SCRIPT_CONTROL_CLOCK_MS]
    mov r0, #0
    pop {r4, r5}
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
    ldr r2, [r5]
    str r4, [r5]
    sub r4, r4, r2
    ldr r2, [r0, #SCRIPT_CONTROL_CLOCK_MS]
    add r4, r4, r2
    ldr r1, =SCRIPT_TIMER_TICKS_PER_MS
clock_carry:
    cmp r3, r1
    subhs r3, r3, r1
    addhs r2, r2, #1
    bhs clock_carry
    sub r4, r4, r2
clock_seconds:
    cmp r4, #500
    blt clock_store
    add r2, r2, #1000
    sub r4, r4, #1000
    b clock_seconds
clock_store:
    str r3, [r0, #SCRIPT_CONTROL_CLOCK_REM]
    str r2, [r0, #SCRIPT_CONTROL_CLOCK_MS]
    mov r0, r2
    pop {r4, r5}
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

.equ HW_GLOBAL, 0xC06A2A94      ; the live global block (GLST, docs/messungen/2026-10-14-global-felder.md)
.equ HW_GLOBAL_CHAIN_MODE, 31   ; CHAIN MODE: without it the firmware does not chain

; -> 1 when CHAIN MODE is on in Global.
script_read_chain_mode_glue:
    ldr r0, =HW_GLOBAL
    ldrb r0, [r0, #HW_GLOBAL_CHAIN_MODE]
    cmp r0, #0
    movne r0, #1
    mov r1, #ERR_OK
    bx lr

; r0 pattern (-1 the pattern in RAM, so an unsaved edit counts; 0 to 249 the bank, 0x4000 per pattern, the same block layout),
; r1 part (-1 a value of the pattern, 0 to 15 a value of that part), r2 field -> the value. The fields and how their bytes
; become the value are PATTERN_FIELDS and PART_FIELDS of data/script/contract.mjs: a table word holds the offset (bits 0 to
; 15) and the kind (bits 16 and up). Clobbers r0 to r3 and r12.
script_read_pattern_value_glue:
    cmn r1, #1
    ldreq r12, =pattern_fields
    moveq r3, #SCRIPT_PATTERN_FIELD_COUNT
    ldrne r12, =part_fields
    movne r3, #SCRIPT_PART_FIELD_COUNT
    cmp r2, r3
    bhs hw_bad_arg
    ldr r12, [r12, r2, lsl #2]
    cmn r0, #1
    ldreq r3, =HW_PATTERN_OBJECT+4
    ldrne r3, =SC_BANK
    addne r3, r3, r0, lsl #14
    cmn r1, #1
    beq pattern_value_at
    ldr r2, =SCRIPT_PART_STRIDE
    mla r3, r1, r2, r3
    add r3, r3, #SCRIPT_PART_BASE
pattern_value_at:
    mov r2, r12, lsl #16
    add r3, r3, r2, lsr #16
    ldrb r0, [r3]
    mov r12, r12, lsr #16
    cmp r12, #1
    moveq r0, r0, lsl #24
    moveq r0, r0, asr #24
    cmp r12, #2
    ldrbeq r2, [r3, #1]
    orreq r0, r0, r2, lsl #8
    cmp r12, #3
    andeq r0, r0, #3
    addeq r0, r0, #1
    cmp r12, #4
    bne pattern_value_repeat
    sub r0, r0, #1
    cmp r0, #249
    mvnhi r0, #0
pattern_value_repeat:
    cmp r12, #5
    bne pattern_value_done
    cmp r0, #1
    movlo r0, #1
pattern_value_done:
    mov r1, #ERR_OK
    bx lr
.pool

pattern_fields:
    .word SCRIPT_PATTERN_FIELD_0
    .word SCRIPT_PATTERN_FIELD_1
    .word SCRIPT_PATTERN_FIELD_2
    .word SCRIPT_PATTERN_FIELD_3
    .word SCRIPT_PATTERN_FIELD_4
    .word SCRIPT_PATTERN_FIELD_5
    .word SCRIPT_PATTERN_FIELD_6
    .word SCRIPT_PATTERN_FIELD_7
    .word SCRIPT_PATTERN_FIELD_8
    .word SCRIPT_PATTERN_FIELD_9
    .word SCRIPT_PATTERN_FIELD_10
    .word SCRIPT_PATTERN_FIELD_11
part_fields:
    .word SCRIPT_PART_FIELD_0
    .word SCRIPT_PART_FIELD_1
    .word SCRIPT_PART_FIELD_2
    .word SCRIPT_PART_FIELD_3
    .word SCRIPT_PART_FIELD_4
    .word SCRIPT_PART_FIELD_5
    .word SCRIPT_PART_FIELD_6
    .word SCRIPT_PART_FIELD_7
    .word SCRIPT_PART_FIELD_8
    .word SCRIPT_PART_FIELD_9
    .word SCRIPT_PART_FIELD_10
    .word SCRIPT_PART_FIELD_11
    .word SCRIPT_PART_FIELD_12
    .word SCRIPT_PART_FIELD_13
    .word SCRIPT_PART_FIELD_14
    .word SCRIPT_PART_FIELD_15
    .word SCRIPT_PART_FIELD_16
    .word SCRIPT_PART_FIELD_17
    .word SCRIPT_PART_FIELD_18
    .word SCRIPT_PART_FIELD_19

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
    ldr r3, =objects_test_mode
    ldrb r3, [r3]
    cmp r3, #0
    bne backlight_done
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
backlight_done:
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
    ldr r0, =objects_test_mode      ; the test mode holds the LEDs itself and gives them to this choice when it ends
    ldrb r0, [r0]
    cmp r0, #0
    bne led_hold_done
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

; korg.padHold: pad presses stop reaching the firmware (no sound, no step edit) while the plugins still get `pad`. It is the
; pad bit of the capture mask the input filter reads (input_mask_pad in script_hooks.s). The hold ends with padHold(0), when
; an app closes (script_app_close) and when no plugin is left to run (script_pad_hold_guard).

; r0 1 to keep the pad presses from the firmware, 0 to give them back.
script_pad_hold_glue:
    push {lr}
    bl pad_hold_set
    mov r0, #0
    mov r1, #ERR_OK
    pop {pc}

; r0 1 sets, 0 clears the pad bit of the capture mask, with the interrupts off: the input filter writes the same word.
; Clobbers r0 to r3.
pad_hold_set:
    ldr r2, =HOOK_RUNTIME
    .word 0xE10F3000 ; mrs r3, cpsr
    orr r1, r3, #0x80
    .word 0xE121F001 ; msr cpsr_c, r1
    ldr r1, [r2, #SCRIPT_CONTROL_CAPTURE_MASK]
    cmp r0, #0
    orrne r1, r1, #INPUT_PAD_BIT
    biceq r1, r1, #INPUT_PAD_BIT
    str r1, [r2, #SCRIPT_CONTROL_CAPTURE_MASK]
    .word 0xE121F003 ; msr cpsr_c, r3
    bx lr

; r0 runtime. Gives the pads back when a script held them and none is left to run, as script_led_hold_guard does the LEDs.
; Clobbers r0 to r3 and r12.
script_pad_hold_guard:
    ldr r1, [r0, #SCRIPT_CONTROL_CAPTURE_MASK]
    tst r1, #INPUT_PAD_BIT
    bxeq lr
    ldr r2, [r0, #RT_HEAD]
pad_guard_entry:
    cmp r2, #0
    beq pad_guard_release
    ldr r3, [r2, #SCRIPT_ENTRY_STATE]
    cmp r3, #SCRIPT_STATE_ARMED
    bne pad_guard_next
    ldr r3, [r2, #SCRIPT_ENTRY_BLOB]
    ldr r12, =HOOK_POOL
    cmp r3, r12
    bxhs lr
pad_guard_next:
    ldr r2, [r2, #SCRIPT_ENTRY_NEXT]
    b pad_guard_entry
pad_guard_release:
    push {lr}
    mov r0, #0
    bl pad_hold_set
    pop {pc}
.pool

; korg.knobHold and korg.knob: a plugin keeps a knob's moves from the firmware and sets the knob's value itself, to filter a
; knob that jumps. The record at KNOB_HOLD holds a bit per knob that still reaches the firmware (the input filter reads it,
; input_mask_knob in script_hooks.s), then the plugin that held the last knob and the checksum of its block, as korg.remapKey
; keeps its owner. The bits count the free knobs, so the FF of the power-on is all knobs free. The hold ends with knobHold(i, 0)
; and when that plugin no longer runs (script_knob_hold_guard), not when an app closes: a filter runs without an app.
.equ KH_FREE, 0
.equ KH_OWNER, 4
.equ KH_CRC, 8

; r0 knob (0 to 10), r1 1 to hold, 0 to let go. Only the VM writes the record, the input filter reads one word.
script_knob_hold_glue:
    ldr r2, =KNOB_HOLD
    ldr r3, [r2, #KH_FREE]
    mov r12, #1
    cmp r1, #0
    orreq r3, r3, r12, lsl r0
    bicne r3, r3, r12, lsl r0
    str r3, [r2, #KH_FREE]
    beq knob_hold_done
    ldr r3, =HOOK_RUNTIME
    ldr r3, [r3, #RT_ENTRY]
    str r3, [r2, #KH_OWNER]
    ldr r3, [r3, #SCRIPT_ENTRY_BLOB]
    ldr r3, [r3, #12]
    str r3, [r2, #KH_CRC]
knob_hold_done:
    mov r0, #0
    mov r1, #ERR_OK
    bx lr

; r0 knob (0 to 10), r1 value (0 to 255): the firmware's knob handler, as if the knob had sent it.
script_knob_glue:
    push {lr}
    ldr r12, =HW_KNOB
    blx r12
    mov r0, #0
    mov r1, #ERR_OK
    pop {pc}

; r0 runtime. Lets the knobs go when the plugin that holds them is gone from the list, no longer armed or holds another block.
; Clobbers r1 to r3 and r12.
script_knob_hold_guard:
    ldr r1, =KNOB_HOLD
    ldr r2, [r1, #KH_FREE]
    cmn r2, #1
    bxeq lr
    ldr r2, [r1, #KH_OWNER]
    ldr r3, [r0, #RT_HEAD]
knob_guard_find:
    cmp r3, #0
    beq knob_guard_release
    cmp r3, r2
    beq knob_guard_owner
    ldr r3, [r3, #SCRIPT_ENTRY_NEXT]
    b knob_guard_find
knob_guard_owner:
    ldr r3, [r2, #SCRIPT_ENTRY_STATE]
    cmp r3, #SCRIPT_STATE_ARMED
    bne knob_guard_release
    ldr r3, [r2, #SCRIPT_ENTRY_BLOB]
    ldr r3, [r3, #12]
    ldr r12, [r1, #KH_CRC]
    cmp r3, r12
    bxeq lr
knob_guard_release:
    mvn r2, #0
    str r2, [r1, #KH_FREE]
    bx lr
.pool

; korg.passKeys: while an app is open, the input filter keeps the keys from the firmware but REC, STOP, PLAY and EXIT
; (input_mask in script_hooks.s); a plugin picks the keys that reach the firmware as well. The record at KEY_PASS holds a
; word for keys 0 to 31 and one for 32 and 33, each bit the key's pass bit XOR its default (1 for REC, STOP and PLAY) and
; inverted, so the FF of the power-on is the defaults; then two words with a bit clear for a key whose press reached the
; firmware while an app was open, so its release follows. The app's close puts the defaults back (script_app_close).
.equ KP_PASS, 0
.equ KP_HELD, 8
.equ KP_DEFAULT, 7

; r0 key (0 to 33), r1 1 to let it reach the firmware, 0 to keep it. Only the VM writes the pass words, the input filter reads them.
script_pass_keys_glue:
    ldr r2, =KEY_PASS
    mov r12, #KP_DEFAULT
    cmp r0, #32
    addhs r2, r2, #4
    subhs r0, r0, #32
    movhs r12, #0
    mov r3, #1
    mov r0, r3, lsl r0
    tst r12, r0
    moveq r12, #0
    movne r12, #1
    ldr r3, [r2, #KP_PASS]
    cmp r1, r12
    orreq r3, r3, r0
    bicne r3, r3, r0
    str r3, [r2, #KP_PASS]
    mov r0, #0
    mov r1, #ERR_OK
    bx lr

; r5 the panel message of a key while an app is open -> r0 nonzero when it reaches the firmware: a press when its key passes,
; a release when its key passes or its press reached the firmware. Clobbers r2, r3 and r12.
script_key_pass:
    push {r1, r4}
    ldrb r2, [r5, #0x0d]
    mov r0, #0
    cmp r2, #34
    bhs key_pass_done
    ldr r12, =KEY_PASS
    mov r4, #KP_DEFAULT
    cmp r2, #32
    addhs r12, r12, #4
    subhs r2, r2, #32
    movhs r4, #0
    ldr r0, [r12, #KP_PASS]
    eor r0, r0, r4
    mvn r0, r0
    mov r3, #1
    mov r3, r3, lsl r2
    and r0, r0, r3
    ldr r1, [r12, #KP_HELD]
    ldrb r4, [r5, #0x0e]
    cmp r4, #0
    beq key_pass_release
    cmp r0, #0
    bicne r1, r1, r3
    orreq r1, r1, r3
    b key_pass_store
key_pass_release:
    tst r1, r3
    orreq r0, r0, r3
    orr r1, r1, r3
key_pass_store:
    str r1, [r12, #KP_HELD]
key_pass_done:
    pop {r1, r4}
    bx lr

; Puts the keys back to their defaults when an app closes. Clobbers r0 and r2.
key_pass_reset:
    ldr r2, =KEY_PASS
    mvn r0, #0
    str r0, [r2, #KP_PASS]
    str r0, [r2, #KP_PASS+4]
    bx lr
.pool

; r0 runtime, r2 the plugin that took a hold, r12 the checksum of its block then -> r3 0 while that plugin is still in the
; runtime's list, armed and holds the same block (an entry address a later load reuses holds another block). Clobbers r3.
hold_owner_gone:
    ldr r3, [r0, #RT_HEAD]
hold_owner_find:
    cmp r3, #0
    beq hold_owner_lost
    cmp r3, r2
    beq hold_owner_found
    ldr r3, [r3, #SCRIPT_ENTRY_NEXT]
    b hold_owner_find
hold_owner_found:
    ldr r3, [r2, #SCRIPT_ENTRY_STATE]
    cmp r3, #SCRIPT_STATE_ARMED
    bne hold_owner_lost
    ldr r3, [r2, #SCRIPT_ENTRY_BLOB]
    ldr r3, [r3, #12]
    subs r3, r3, r12
    bx lr
hold_owner_lost:
    mov r3, #1
    bx lr

; korg.touchLockX: the input filter writes a fixed X into every touch message, after the plugins got the real one
; (touch_lock_input, called from script_input_hook), so the firmware's touchpad modes see that X while Y stays the finger's. The
; firmware takes (raw X >> 4) * 2 as its X in Master FX and Touch Scale mode (0xC004567C on hacktribe and red, 0xC003F99C on
; the blue) and raw X >> 3 in Gate Arp mode (measured in the emulator on all three builds), so the record holds the raw value
; x << 3: x rounded down to even in the first two, x itself in Gate Arp, the same X as a finger at raw x * 8. Then the plugin
; that locked and the checksum of its block; the lock ends with touchLockX(-1) and when that plugin no longer runs
; (script_touch_lock_guard). FF at power-on is no lock.
.equ TL_RAW, 0
.equ TL_OWNER, 4
.equ TL_CRC, 8

; r0 x (-1 to 127, checked by the VM). Only the VM writes the record, the input filter reads one word.
script_touch_lock_x_glue:
    ldr r2, =TOUCH_LOCK
    cmp r0, #0
    mvnlt r3, #0
    movge r3, r0, lsl #3
    str r3, [r2, #TL_RAW]
    blt touch_lock_done
    ldr r3, =HOOK_RUNTIME
    ldr r3, [r3, #RT_ENTRY]
    str r3, [r2, #TL_OWNER]
    ldr r3, [r3, #SCRIPT_ENTRY_BLOB]
    ldr r3, [r3, #12]
    str r3, [r2, #TL_CRC]
touch_lock_done:
    mov r0, #0
    mov r1, #ERR_OK
    bx lr

; r5 a touch message (class 5): bytes 0x0d and 0x0e are its X, high byte first. Clobbers r1.
touch_lock_input:
    ldr r1, =TOUCH_LOCK
    ldr r1, [r1, #TL_RAW]
    cmn r1, #1
    bxeq lr
    strb r1, [r5, #0x0e]
    mov r1, r1, lsr #8
    strb r1, [r5, #0x0d]
    bx lr

; r0 runtime. Ends the lock when the plugin that locked is gone from the list, no longer armed or holds another block.
; Clobbers r1 to r3 and r12.
script_touch_lock_guard:
    ldr r1, =TOUCH_LOCK
    ldr r2, [r1, #TL_RAW]
    cmn r2, #1
    bxeq lr
    ldr r2, [r1, #TL_OWNER]
    ldr r12, [r1, #TL_CRC]
    push {lr}
    bl hold_owner_gone
    pop {lr}
    cmp r3, #0
    bxeq lr
    mvn r2, #0
    str r2, [r1, #TL_RAW]
    bx lr
.pool

; korg.keyHold: a plugin keeps a key from the firmware, with or without an app (passKeys acts only while an app is open). The
; input filter asks script_key_hold for every key message outside the BLECH menu, before the app's own keys. The record at
; KEY_HOLD holds a word for keys 0 to 31 and one for 32 and 33 with a bit set for a key that still reaches the firmware (FF at
; power-on is all free), two words with a bit clear for a key whose press was kept (so its release is kept as well, even when the
; hold ended in between), then the plugin that held the last key and the checksum of its block. The hold ends with keyHold(key, 0)
; and when that plugin no longer runs (script_key_hold_guard), not when an app closes. EXIT is never held, apps stay closable.
.equ KY_FREE, 0
.equ KY_KEPT, 8
.equ KY_OWNER, 16
.equ KY_CRC, 20

; r0 key (0 to 33), r1 1 to hold, 0 to let go.
script_key_hold_glue:
    cmp r0, #KEY_EXIT
    beq hw_bad_arg
    ldr r2, =KEY_HOLD
    cmp r0, #32
    addhs r2, r2, #4
    subhs r0, r0, #32
    ldr r3, [r2, #KY_FREE]
    mov r12, #1
    cmp r1, #0
    orreq r3, r3, r12, lsl r0
    bicne r3, r3, r12, lsl r0
    str r3, [r2, #KY_FREE]
    beq key_hold_done
    ldr r2, =KEY_HOLD
    ldr r3, =HOOK_RUNTIME
    ldr r3, [r3, #RT_ENTRY]
    str r3, [r2, #KY_OWNER]
    ldr r3, [r3, #SCRIPT_ENTRY_BLOB]
    ldr r3, [r3, #12]
    str r3, [r2, #KY_CRC]
key_hold_done:
    mov r0, #0
    mov r1, #ERR_OK
    bx lr

; r5 a key message -> r0 nonzero when the firmware must not get it: a press of a held key, the release of a kept press.
; Clobbers r1 to r3 and r12.
script_key_hold:
    ldrb r2, [r5, #0x0d]
    mov r0, #0
    cmp r2, #34
    bxhs lr
    ldr r12, =KEY_HOLD
    cmp r2, #32
    addhs r12, r12, #4
    subhs r2, r2, #32
    mov r3, #1
    mov r3, r3, lsl r2
    ldr r1, [r12, #KY_KEPT]
    ldrb r2, [r5, #0x0e]
    cmp r2, #0
    beq key_hold_release
    ldr r0, [r12, #KY_FREE]
    bic r0, r3, r0
    cmp r0, #0
    bicne r1, r1, r3
    orreq r1, r1, r3
    b key_hold_store
key_hold_release:
    bic r0, r3, r1
    orr r1, r1, r3
key_hold_store:
    str r1, [r12, #KY_KEPT]
    bx lr

; r0 runtime. Gives all keys back when the plugin that held the last one no longer runs. Clobbers r1 to r3 and r12.
script_key_hold_guard:
    ldr r1, =KEY_HOLD
    ldr r2, [r1, #KY_FREE]
    ldr r3, [r1, #KY_FREE+4]
    and r2, r2, r3
    cmn r2, #1
    bxeq lr
    ldr r2, [r1, #KY_OWNER]
    ldr r12, [r1, #KY_CRC]
    push {lr}
    bl hold_owner_gone
    pop {lr}
    cmp r3, #0
    bxeq lr
    mvn r2, #0
    str r2, [r1, #KY_FREE]
    str r2, [r1, #KY_FREE+4]
    bx lr
.pool

; korg.pressKey: a plugin gives the firmware a short press of a key. The press goes into the panel queue at once (rm_post in
; script_remote.s, the way the remote's keys go), the release in the next frame (script_press_key_tick), so the firmware gets
; both through its own panel path. Both carry PK_MARK in their last byte: the input filter passes them on untouched (no remap,
; no hold, no app) and posts them to no plugin. The record at PRESS_KEY holds a word for keys 0 to 31 and one for 32 and 33,
; a bit clear for a key whose release is still to go; FF at power-on is none. A key pressed again before its release went out
; is not pressed twice. A full queue drops the press; a release waits for the next frame.
.equ PK_UP, 0

; r0 key (0 to 33). EXIT is refused, an app would stay open with the firmware on its own screen.
script_press_key_glue:
    cmp r0, #KEY_EXIT
    beq hw_bad_arg
    push {r4-r6, lr}
    ldr r4, =PRESS_KEY
    mov r5, r0
    cmp r0, #32
    addhs r4, r4, #4
    subhs r0, r0, #32
    mov r6, #1
    mov r6, r6, lsl r0
    ldr r3, [r4, #PK_UP]
    tst r3, r6
    beq press_key_done
    mov r0, r5, lsl #8
    orr r0, r0, #0x10000        ; type 0, the key, 1 (pressed)
    mov r1, #PK_MARK_WORD
    bl rm_post
    cmp r0, #0
    ldrne r3, [r4, #PK_UP]
    bicne r3, r3, r6
    strne r3, [r4, #PK_UP]
press_key_done:
    mov r0, #0
    mov r1, #ERR_OK
    pop {r4-r6, pc}

; From the frame hook, before the plugins run: the release of every key a plugin pressed in the last frame. Clobbers r0 to r3
; and r12.
script_press_key_tick:
    ldr r0, =PRESS_KEY
    ldr r1, [r0, #PK_UP]
    ldr r2, [r0, #PK_UP+4]
    and r1, r1, r2
    cmn r1, #1
    bxeq lr
    push {r4-r6, lr}
    mov r5, #0
press_tick_key:
    ldr r4, =PRESS_KEY
    cmp r5, #32
    addhs r4, r4, #4
    subhs r0, r5, #32
    movlo r0, r5
    mov r6, #1
    mov r6, r6, lsl r0
    ldr r3, [r4, #PK_UP]
    tst r3, r6
    bne press_tick_next
    mov r0, r5, lsl #8          ; type 0, the key, 0 (released)
    mov r1, #PK_MARK_WORD
    bl rm_post
    cmp r0, #0
    ldrne r3, [r4, #PK_UP]
    orrne r3, r3, r6
    strne r3, [r4, #PK_UP]
press_tick_next:
    add r5, r5, #1
    cmp r5, #34
    blo press_tick_key
    pop {r4-r6, pc}
.pool

; korg.remapKey: one key the panel sends reaches the firmware and the plugins as another, while the plugin that asked for it
; is armed. The record lies in the card loader's work area, between RM_AT and FX_STATE_AT: the plugin's entry, the checksum
; of its block (an entry address a later load reuses holds another block) and the two key codes (from in bits 0 to 7, to in
; bits 8 to 15). The area is FF at power-on, which matches no entry.
.equ RP_AT, 0xFCC
.equ RP_OWNER, 0
.equ RP_CRC, 4
.equ RP_KEYS, 8
.equ RP_SIZE, 12
.equ KEY_EXIT, 13

; r0 from, r1 to (0 to 33, checked by the VM). The same key twice ends the remap; EXIT is never remapped, so apps stay closable.
script_remap_key_glue:
    cmp r0, #KEY_EXIT
    cmpne r1, #KEY_EXIT
    beq hw_bad_arg
    ldr r2, =HOOK_CARD+RP_AT
    ldr r3, =HOOK_RUNTIME
    ldr r3, [r3, #RT_ENTRY]
    cmp r0, r1
    moveq r3, #0
    str r3, [r2, #RP_OWNER]
    orr r0, r0, r1, lsl #8
    str r0, [r2, #RP_KEYS]
    cmp r3, #0
    ldrne r3, [r3, #SCRIPT_ENTRY_BLOB]
    ldrne r3, [r3, #12]
    str r3, [r2, #RP_CRC]
    mov r0, #0
    mov r1, #ERR_OK
    bx lr

; r0 a panel message. A key message of the remapped key gets the other key code, before the firmware or a plugin sees it,
; when the owner is still in the runtime's list, armed and holds the same block. Clobbers r0 to r3 and r12.
remap_input:
    ldr r1, =HOOK_CARD+RP_AT
    ldr r2, [r1, #RP_OWNER]
    cmp r2, #0
    bxeq lr
    ldrb r3, [r0, #0x0c]
    cmp r3, #0
    bxne lr
    ldr r3, =HOOK_RUNTIME
    ldr r3, [r3]
remap_find:
    cmp r3, r2
    beq remap_owner
    cmp r3, #0
    cmnne r3, #1
    bxeq lr
    ldr r3, [r3]
    b remap_find
remap_owner:
    ldr r3, [r2, #SCRIPT_ENTRY_STATE]
    cmp r3, #SCRIPT_STATE_ARMED
    bxne lr
    ldr r3, [r2, #SCRIPT_ENTRY_BLOB]
    ldr r3, [r3, #12]
    ldr r12, [r1, #RP_CRC]
    cmp r3, r12
    bxne lr
    ldr r1, [r1, #RP_KEYS]
    ldrb r3, [r0, #0x0d]
    and r2, r1, #0xFF
    cmp r3, r2
    bxne lr
    mov r1, r1, lsr #8
    strb r1, [r0, #0x0d]
    bx lr
.pool
