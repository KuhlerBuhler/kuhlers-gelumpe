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
