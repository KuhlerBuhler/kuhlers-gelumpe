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

.equ HW_VIEW_CELL, 0xC0691388   ; pointer to the accessor of the pattern the pads and info texts show (tools/patch/pattern_switch.py: CELL_W)
.equ HW_PS_STATE, 0xC0180F00    ; run time state of the pattern switch: +4 a pattern is confirmed (1), +8 its number; FFFFFFFF without the patch
.equ HW_PS_ARMED, 4
.equ HW_PS_ARMNUM, 8
.equ HW_PENDING_FLAG, 0x341     ; in the pattern selection object (HW_MODEL): a chosen number waits for the sequence end

; -> the pattern the display shows, 0 to 249: the bank block the view's cell points into, else the pattern that runs (the one in RAM).
script_read_viewed_pattern_glue:
    ldr r0, =HW_VIEW_CELL
    ldr r0, [r0]
    cmp r0, #0
    ldrne r0, [r0, #4]
    cmp r0, #0
    beq viewed_running
    ldr r1, =SC_BANK
    sub r0, r0, r1
    add r0, r0, #4
    cmp r0, #0x3E8000
    bhs viewed_running
    mov r0, r0, lsr #14
    mov r1, #ERR_OK
    bx lr
viewed_running:
    push {lr}
    ldr r12, =SC_PLAYER
    blx r12
    ldr r0, [r0, #0x318]
    mov r1, #ERR_OK
    pop {pc}
.pool

; -> the next pattern the pattern switch has confirmed, 0 to 249, while the firmware still holds it for the sequence end, else -1.
script_read_next_pattern_glue:
    ldr r2, =HW_PS_STATE
    ldr r0, [r2, #HW_PS_ARMED]
    cmp r0, #1
    bne next_pattern_none
    ldr r1, =HW_MODEL
    ldrb r1, [r1, #HW_PENDING_FLAG]
    cmp r1, #0
    beq next_pattern_none
    ldr r0, [r2, #HW_PS_ARMNUM]
    cmp r0, #250
    bhs next_pattern_none
    mov r1, #ERR_OK
    bx lr
next_pattern_none:
    mvn r0, #0
    mov r1, #ERR_OK
    bx lr
.pool

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
    cmp r12, #0x60000               ; kind 6 (mfx2): no byte of the pattern
    beq pattern_value_mfx2
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

; MFX 2 of pattern r0 (-1 the running one), from the table of the patch mfx-switch after its own load (MFX2_ENTRY + 4), so the
; table has one writer: an entry 1 to 100 is the type as the display numbers it, any other the patch's default (MFX2_ENTRY + 8).
; -1 without the patch.
; r0 = 1 while the patch mfx-switch is in the set and on (MFX 2 on in the menu BLECH, EXIT not held at power-on), else 0.
; Its entry at MFX2_ENTRY + 12 answers the second part. Clobbers r1 to r3 and r12.
mfx2_on:
    ldr r0, =MFX2_ENTRY
    ldr r0, [r0]
    ldr r1, =MFX2_RECORD_ID
    cmp r0, r1
    movne r0, #0
    bxne lr
    push {r4, lr}
    ldr r12, =MFX2_ENTRY+12
    blx r12
    eor r0, r0, #1
    pop {r4, pc}

pattern_value_mfx2:
    push {r4, lr}
    mov r4, r0
    ldr r3, =MFX2_ENTRY
    ldr r1, [r3]
    ldr r2, =MFX2_RECORD_ID
    cmp r1, r2
    mvnne r0, #0
    bne pattern_mfx2_out
    cmn r4, #1
    bne pattern_mfx2_load
    ldr r12, =SC_PLAYER
    blx r12
    ldr r4, [r0, #0x318]
pattern_mfx2_load:
    cmp r4, #250
    mvnhs r0, #0
    bhs pattern_mfx2_out
    ldr r12, =MFX2_ENTRY+4
    blx r12
    ldr r3, =MFX2_TABLE
    ldrb r0, [r3, r4]
    sub r0, r0, #1
    cmp r0, #99
    bls pattern_mfx2_out
    ldr r3, =MFX2_ENTRY
    ldr r0, [r3, #8]
    sub r0, r0, #1
pattern_mfx2_out:
    mov r1, #ERR_OK
    pop {r4, pc}
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
    .word SCRIPT_PATTERN_FIELD_12
    .word SCRIPT_PATTERN_FIELD_13
    .word SCRIPT_PATTERN_FIELD_14
    .word SCRIPT_PATTERN_FIELD_15
    .word SCRIPT_PATTERN_FIELD_16
    .word SCRIPT_PATTERN_FIELD_17
    .word SCRIPT_PATTERN_FIELD_18
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
    .word SCRIPT_PART_FIELD_20
    .word SCRIPT_PART_FIELD_21
    .word SCRIPT_PART_FIELD_22
    .word SCRIPT_PART_FIELD_23
    .word SCRIPT_PART_FIELD_24
    .word SCRIPT_PART_FIELD_25
    .word SCRIPT_PART_FIELD_26
    .word SCRIPT_PART_FIELD_27

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
.equ HW_LED_COPY, 0x88C            ; the manager's copy of what went to the panel, 8 bytes a LED, byte 2 the brightness
.equ HW_LED_COPY_PAGE, 0x880

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

; r0 LED 0 to HW_LED_LAST -> r0 the brightness the firmware last sent for it (the LED manager's copy, 0 to 255), 0 before the
; manager exists. LEDs a script sets with korg.led while it holds them are not in the copy.
script_read_led_glue:
    ldr r1, =HW_LED_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    cmnne r1, #1
    moveq r0, #0
    addne r1, r1, r0, lsl #3
    addne r1, r1, #HW_LED_COPY_PAGE
    ldrbne r0, [r1, #HW_LED_COPY+2-HW_LED_COPY_PAGE]
    mov r1, #ERR_OK
    bx lr

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

; What a plugin keeps from the firmware (korg.padHold, korg.knobHold, korg.keyHold, korg.keyMask): every plugin has four words
; in its own entry (SCRIPT_ENTRY_HOLDS: the keys 0 to 31, the keys 32 and 33, a bit per knob, 1 for the pads), the calls change
; only the caller's words, and holds_sync folds the words of all running plugins into what the input filter reads: a key, knob
; or the pads stay away from the firmware when ANY running plugin keeps them, the plugins get every input either way. A plugin
; that stops (switched off, faulted, removed) lets go of all its holds at the next frame's end. An app's close gives the pads
; back to all plugins (hold_pads_release), as it did when there was one pad flag.
.equ HD_KEYS, SCRIPT_ENTRY_HOLDS
.equ HD_KEYS_HI, SCRIPT_ENTRY_HOLDS+4
.equ HD_KNOBS, SCRIPT_ENTRY_HOLDS+8
.equ HD_PAD, SCRIPT_ENTRY_HOLDS+12
.equ HD_QUIET, 2                    ; in HD_PAD: korg.display.popups(0), bit 0 is the pad hold
.equ HD_MIDI_SHIFT, 8               ; in HD_PAD: korg.midi.hold, bits 8 to 14 a message type each (script_midi.s)

; r0 runtime, r1 a plugin to count although it is not armed yet (the one whose body runs), or 0. Folds the holds of the armed
; plugins into the key words (KY_FREE), the knob word (KH_FREE) and the pad bit of the capture mask. Clobbers r0 to r3 and r12.
holds_sync:
    push {r4-r9, lr}
    mov r4, r0
    mov r8, r1
    mov r5, #0
    mov r6, #0
    mov r7, #0
    mov r9, #0
    ldr r1, [r4, #RT_HEAD]
holds_next:
    cmp r1, #0
    beq holds_fold
    cmp r1, r8
    beq holds_count
    ldr r0, [r1, #SCRIPT_ENTRY_STATE]
    cmp r0, #SCRIPT_STATE_ARMED
    bne holds_skip
holds_count:
    ldr r0, [r1, #HD_KEYS]
    orr r5, r5, r0
    ldr r0, [r1, #HD_KEYS_HI]
    orr r6, r6, r0
    ldr r0, [r1, #HD_KNOBS]
    orr r7, r7, r0
    ldr r0, [r1, #HD_PAD]
    orr r9, r9, r0
    ands r0, r0, #1
    orrne r7, r7, r0, lsl #31
holds_skip:
    ldr r1, [r1, #SCRIPT_ENTRY_NEXT]
    b holds_next
holds_fold:
    ldr r1, =KEY_HOLD
    mvn r0, r5
    str r0, [r1, #KY_FREE]
    mvn r0, r6
    str r0, [r1, #KY_FREE+4]
    ldr r1, =KNOB_HOLD
    bic r0, r7, #0x80000000
    mvn r0, r0
    str r0, [r1, #KH_FREE]
    mov r0, r9, lsr #HD_MIDI_SHIFT
    and r0, r0, #0x7F
    mvn r0, r0
    ldr r1, =MIDI_FREE
    str r0, [r1]
    mov r0, r7, lsr #31
    bl pad_hold_set
    pop {r4-r9, pc}

; Folds with the running plugin counted: a hold set in its body, which runs before it is armed, works at once.
hold_sync_caller:
    ldr r0, =HOOK_RUNTIME
    ldr r1, [r0, #RT_ENTRY]
    b holds_sync

; -> r3 the running plugin's entry, r2 clobbered
hold_entry:
    ldr r2, =HOOK_RUNTIME
    ldr r3, [r2, #RT_ENTRY]
    bx lr

; The pads go back to the firmware: no plugin holds them any more. Preserves r4 to r8. Clobbers r0 to r3 and r12.
hold_pads_release:
    push {lr}
    ldr r0, =HOOK_RUNTIME
    ldr r1, [r0, #RT_HEAD]
holds_pad_next:
    cmp r1, #0
    beq holds_pad_done
    ldr r2, [r1, #HD_PAD]
    bic r2, r2, #1
    str r2, [r1, #HD_PAD]
    ldr r1, [r1, #SCRIPT_ENTRY_NEXT]
    b holds_pad_next
holds_pad_done:
    mov r1, #0
    bl holds_sync
    pop {pc}

; korg.padHold: pad presses stop reaching the firmware (no sound, no step edit) while the plugins still get `pad`. It is the
; pad bit of the capture mask the input filter reads (input_mask_pad in script_hooks.s), set while any plugin holds the pads.
; The hold ends with padHold(0), when an app closes (script_app_close) and when the plugin that holds no longer runs.

; r0 1 to keep the pad presses from the firmware, 0 to give them back (for this plugin).
script_pad_hold_glue:
    push {lr}
    bl hold_entry
    ldr r2, [r3, #HD_PAD]
    bic r2, r2, #1
    cmp r0, #0
    orrne r2, r2, #1
    str r2, [r3, #HD_PAD]
    bl hold_sync_caller
    mov r0, #0
    mov r1, #ERR_OK
    pop {pc}

; korg.display.popups: r0 0 keeps the parameter window shut on this plugin's writes (korg.seq.setPartValue), 1 lets it open as a
; knob opens it (the default). A bit in the plugin's own pad word (HD_QUIET), so it ends with the plugin.
script_display_popups_glue:
    push {lr}
    bl hold_entry
    ldr r2, [r3, #HD_PAD]
    cmp r0, #0
    orreq r2, r2, #HD_QUIET
    bicne r2, r2, #HD_QUIET
    str r2, [r3, #HD_PAD]
    mov r0, #0
    mov r1, #ERR_OK
    pop {pc}

; -> r0 1 while the running plugin lets the parameter window open, 0 while it keeps it shut
script_read_popups_glue:
    push {lr}
    bl popups_quiet
    moveq r0, #1
    movne r0, #0
    mov r1, #ERR_OK
    pop {pc}

; -> NE while the running plugin keeps the parameter window shut. Clobbers r0.
popups_quiet:
    ldr r0, =HOOK_RUNTIME
    ldr r0, [r0, #RT_ENTRY]
    cmp r0, #0
    ldrne r0, [r0, #HD_PAD]
    tstne r0, #HD_QUIET
    bx lr

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
.pool

; korg.knobHold and korg.knob: a plugin keeps a knob's moves from the firmware and sets the knob's value itself, to filter a
; knob that jumps. The record at KNOB_HOLD holds a bit per knob that still reaches the firmware (the input filter reads it,
; input_mask_knob in script_hooks.s), made by holds_sync from the plugins' holds: the FF of the power-on is all knobs free. The
; hold ends with knobHold(i, 0) and when the plugin that holds no longer runs, not when an app closes: a filter runs without an app.
.equ KH_FREE, 0

; r0 knob (0 to 10), r1 1 to hold, 0 to let go (for this plugin). Only the VM writes the record, the input filter reads one word.
script_knob_hold_glue:
    push {lr}
    mov r12, r0
    bl hold_entry
    add r3, r3, #HD_KNOBS
    ldr r0, [r3]
    mov r2, #1
    cmp r1, #0
    biceq r0, r0, r2, lsl r12
    orrne r0, r0, r2, lsl r12
    str r0, [r3]
    bl hold_sync_caller
    mov r0, #0
    mov r1, #ERR_OK
    pop {pc}

; r0 knob (0 to 10), r1 value (0 to 255): the firmware's knob handler, as if the knob had sent it.
script_knob_glue:
    push {lr}
    ldr r12, =HW_KNOB
    blx r12
    mov r0, #0
    mov r1, #ERR_OK
    pop {pc}
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
; (touch_lock_input, called from script_input_hook), so the firmware's touchpad modes see that X. The
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
touch_lock_set:
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

; korg.touchLockY: the same for bytes 0x0f and 0x10, the Y of a touch message, in its own record at TOUCH_LOCK_Y. The
; firmware takes (raw Y >> 4) * 2 in Master FX and raw Y >> 3 in Touch Scale and Gate Arp mode (measured in the emulator on all
; three builds): y rounded down to even in Master FX, y itself in the other two.
script_touch_lock_y_glue:
    ldr r2, =TOUCH_LOCK_Y
    b touch_lock_set

; r5 a touch message (class 5): bytes 0x0d and 0x0e are its X, 0x0f and 0x10 its Y, high byte first. Clobbers r1.
touch_lock_input:
    ldr r1, =TOUCH_LOCK
    ldr r1, [r1, #TL_RAW]
    cmn r1, #1
    strbne r1, [r5, #0x0e]
    movne r1, r1, lsr #8
    strbne r1, [r5, #0x0d]
    ldr r1, =TOUCH_LOCK_Y
    ldr r1, [r1, #TL_RAW]
    cmn r1, #1
    bxeq lr
    strb r1, [r5, #0x10]
    mov r1, r1, lsr #8
    strb r1, [r5, #0x0f]
    bx lr

; r0 runtime. Ends the lock when the plugin that locked is gone from the list, no longer armed or holds another block.
; Clobbers r1 to r3 and r12.
script_touch_lock_guard:
    push {r0, lr}
    ldr r1, =TOUCH_LOCK
    bl touch_lock_guard_one
    pop {r0, lr}
    ldr r1, =TOUCH_LOCK_Y
; r0 runtime, r1 a lock record (X or Y). Clobbers r1 to r3 and r12.
touch_lock_guard_one:
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

; korg.keyHold and korg.keyMask: a plugin keeps keys from the firmware, with or without an app (passKeys acts only while an app is
; open). The input filter asks script_key_hold for every key message outside the BLECH menu, before the app's own keys. The record
; at KEY_HOLD holds a word for keys 0 to 31 and one for 32 and 33 with a bit set for a key that still reaches the firmware (FF at
; power-on is all free; holds_sync makes them from the plugins' holds), then two words with a bit clear for a key whose press was
; kept (so its release is kept as well, even when the hold ended in between). A key is kept while ANY running plugin keeps it. The
; hold ends with keyHold(key, 0), a keyMask without the key and when the plugin that holds no longer runs, not when an app closes.
; EXIT is never held, apps stay closable.
.equ KY_FREE, 0
.equ KY_KEPT, 8

; r0 key (0 to 33), r1 1 to hold, 0 to let go (for this plugin).
script_key_hold_glue:
    cmp r0, #KEY_EXIT
    beq hw_bad_arg
    push {lr}
    mov r12, r0
    bl hold_entry
    add r3, r3, #HD_KEYS
    cmp r12, #32
    addhs r3, r3, #4
    subhs r12, r12, #32
    ldr r0, [r3]
    mov r2, #1
    cmp r1, #0
    biceq r0, r0, r2, lsl r12
    orrne r0, r0, r2, lsl r12
    str r0, [r3]
    bl hold_sync_caller
    mov r0, #0
    mov r1, #ERR_OK
    pop {pc}

; r0 the keys 0 to 31, r1 the keys 32 and 33 (checked by the VM), as the mask of this plugin: every key in it is kept, every one
; not in it is let go, as far as this plugin is concerned. EXIT in the mask is refused.
script_key_mask_glue:
    mov r2, #1
    tst r0, r2, lsl #KEY_EXIT
    bne hw_bad_arg
    push {lr}
    mov r12, r0
    bl hold_entry
    str r12, [r3, #HD_KEYS]
    str r1, [r3, #HD_KEYS_HI]
    bl hold_sync_caller
    mov r0, #0
    mov r1, #ERR_OK
    pop {pc}

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
.pool

; korg.pressKey: a plugin gives the firmware a short press of a key. The press goes into the panel queue at once (rm_post in
; script_remote.s, the way the remote's keys go), the release in the next frame (script_press_key_tick), so the firmware gets
; both through its own panel path. Both carry PK_MARK in their last byte: the input filter passes them on untouched (no remap,
; no hold, no app) and posts them to no plugin. The record at PRESS_KEY holds a word for keys 0 to 31 and one for 32 and 33,
; a bit clear for a key whose release is still to go; FF at power-on is none. A key pressed again before its release went out
; is not pressed twice. A full queue drops the press; a release waits for the next frame.
.equ PK_UP, 0

; r0 key (0 to 33). EXIT closes an open app first, as the input filter does for the panel's EXIT (since API 25; it was
; refused before, the app stayed open with the firmware on its own screen).
script_press_key_glue:
    push {r4-r6, lr}
    mov r5, r0
    cmp r0, #KEY_EXIT
    bleq script_app_close
    mov r0, r5
    ldr r4, =PRESS_KEY
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

; The panel as a finger works it (API 25): korg.keyDown and korg.keyUp, korg.padDown and korg.padUp, korg.encoder and korg.touch
; put the message the panel sends for the control into the panel queue (rm_post_quiet in script_remote.s), with PK_MARK in its
; last byte like korg.pressKey: the input filter passes it to the firmware untouched (no remap, no hold, no app, no shortcut, no
; touch lock) and posts it to no plugin, so a plugin's own pad is never kept by its own korg.padHold and never comes back to it as
; `pad`. The record at SIM_INPUT holds a bit per key (two words, the touchpad as bit 2 of the second) and per pad, clear while the
; plugin holds it down, so a second down or an up without a down sends nothing; then the plugin that put the last one down and
; the checksum of its block. When that plugin no longer runs, the frame's end lets go of everything still down
; (script_sim_input_guard). FF at power-on is nothing down. A full queue drops the message and leaves the bit as it was.
.equ SI_UP, 0
.equ SI_UP_HI, 4
.equ SI_PADS, 8
.equ SI_OWNER, 12
.equ SI_CRC, 16
.equ SI_TOUCH_BIT, 4
.equ SI_TOUCH_DOWN, 0x12200     ; type 0, the touchpad key (0x22), 1 (pressed)
.equ SI_TOUCH_UP, 0x2200        ; type 0, the touchpad key, 0 (released)

; r0 key (0 to 33) -> r4 the address of its word in SIM_INPUT, r6 its bit. Clobbers r0.
si_key_word:
    ldr r4, =SIM_INPUT
    cmp r0, #32
    addhs r4, r4, #4
    subhs r0, r0, #32
    mov r6, #1
    mov r6, r6, lsl r0
    bx lr

; The running plugin holds what is down now. Clobbers r2 and r3.
si_owner:
    ldr r2, =SIM_INPUT
    ldr r3, =HOOK_RUNTIME
    ldr r3, [r3, #RT_ENTRY]
    str r3, [r2, #SI_OWNER]
    ldr r3, [r3, #SCRIPT_ENTRY_BLOB]
    ldr r3, [r3, #12]
    str r3, [r2, #SI_CRC]
    bx lr

; r0 the first four bytes of a panel message, r1 the fifth -> r0 0 when the queue was full. Clobbers r1 to r3 and r12.
si_post:
    orr r1, r1, #PK_MARK_WORD
    b rm_post_quiet

; r0 key (0 to 33): the key goes down for the firmware and stays down until korg.keyUp. EXIT closes an open app first.
script_key_down_glue:
    push {r4-r6, lr}
    mov r5, r0
    bl si_key_word
    ldr r3, [r4]
    tst r3, r6
    beq si_done
    cmp r5, #KEY_EXIT
    bleq script_app_close
    mov r0, r5, lsl #8
    orr r0, r0, #0x10000        ; type 0, the key, 1 (pressed)
    mov r1, #0
    bl si_post
    cmp r0, #0
    beq si_done
    ldr r3, [r4]
    bic r3, r3, r6
    str r3, [r4]
    bl si_owner
si_done:
    mov r0, #0
    mov r1, #ERR_OK
    pop {r4-r6, pc}

; r0 key (0 to 33): the release of a key this plugin put down.
script_key_up_glue:
    push {r4-r6, lr}
    mov r5, r0
    bl si_key_word
    ldr r3, [r4]
    tst r3, r6
    bne si_done
    mov r0, r5, lsl #8          ; type 0, the key, 0 (released)
    mov r1, #0
    bl si_post
    cmp r0, #0
    ldrne r3, [r4]
    orrne r3, r3, r6
    strne r3, [r4]
    b si_done

; r0 pad (0 to 15), r1 velocity (1 to 127): the pad is hit and stays down until korg.padUp.
script_pad_down_glue:
    push {r4-r6, lr}
    ldr r4, =SIM_INPUT+SI_PADS
    mov r6, #1
    mov r6, r6, lsl r0
    ldr r3, [r4]
    tst r3, r6
    beq si_done
    mov r0, r0, lsl #8
    orr r0, r0, #4              ; type 4, the pad, 0, the velocity; then 1 (on)
    orr r0, r0, r1, lsl #24
    mov r1, #1
    bl si_post
    cmp r0, #0
    beq si_done
    ldr r3, [r4]
    bic r3, r3, r6
    str r3, [r4]
    bl si_owner
    b si_done

; r0 pad (0 to 15): the release of a pad this plugin hit, velocity 0 and off as the panel sends it.
script_pad_up_glue:
    push {r4-r6, lr}
    ldr r4, =SIM_INPUT+SI_PADS
    mov r6, #1
    mov r6, r6, lsl r0
    ldr r3, [r4]
    tst r3, r6
    bne si_done
    mov r0, r0, lsl #8
    orr r0, r0, #4              ; type 4, the pad, 0, 0; then 0 (off)
    mov r1, #0
    bl si_post
    cmp r0, #0
    ldrne r3, [r4]
    orrne r3, r3, r6
    strne r3, [r4]
    b si_done

; r0 encoder (0 to 4), r1 delta (-127 to 127, 0 sends nothing): one turn as the panel sends it, the delta as a signed byte.
script_encoder_glue:
    push {r4-r6, lr}
    cmp r1, #0
    beq si_done
    and r1, r1, #0xFF
    mov r0, r0, lsl #8
    orr r0, r0, #1              ; type 1, the encoder, 0, the delta
    orr r0, r0, r1, lsl #24
    mov r1, #0
    bl si_post
    b si_done

; r0 x (-1 to 1023), r1 y (0 to 1023): a finger on the touchpad at x, y, as the panel sends it: the touchpad key goes down at the
; first position, then the position; x -1 lifts the finger (the key's release).
script_touch_glue:
    push {r4-r6, lr}
    ldr r4, =SIM_INPUT+SI_UP_HI
    mov r6, #SI_TOUCH_BIT
    cmp r0, #0
    blt touch_up
    orr r5, r0, r1, lsl #16
    ldr r3, [r4]
    tst r3, r6
    beq touch_move
    ldr r0, =SI_TOUCH_DOWN
    mov r1, #0
    bl si_post
    cmp r0, #0
    beq si_done
    ldr r3, [r4]
    bic r3, r3, r6
    str r3, [r4]
    bl si_owner
touch_move:
    mov r2, r5, lsl #16
    mov r2, r2, lsr #16         ; x
    mov r0, #5                  ; type 5, x high, x low, y high; then y low
    mov r3, r2, lsr #8
    orr r0, r0, r3, lsl #8
    and r3, r2, #0xFF
    orr r0, r0, r3, lsl #16
    mov r2, r5, lsr #16         ; y
    mov r3, r2, lsr #8
    orr r0, r0, r3, lsl #24
    and r1, r2, #0xFF
    bl si_post
    b si_done
touch_up:
    ldr r3, [r4]
    tst r3, r6
    bne si_done
    mov r0, #SI_TOUCH_UP
    mov r1, #0
    bl si_post
    cmp r0, #0
    ldrne r3, [r4]
    orrne r3, r3, r6
    strne r3, [r4]
    b si_done

; r0 runtime. When something is still down and the plugin that put it down is gone from the list, no longer armed or holds
; another block, everything goes up. Preserves r4. Clobbers r0 to r3 and r12.
script_sim_input_guard:
    ldr r1, =SIM_INPUT
    ldr r2, [r1, #SI_UP]
    cmn r2, #1
    bne si_guard_owner
    ldr r2, [r1, #SI_UP_HI]
    and r2, r2, #7
    cmp r2, #7
    bne si_guard_owner
    ldr r2, [r1, #SI_PADS]
    mov r2, r2, lsl #16
    cmn r2, #0x10000
    bxeq lr
si_guard_owner:
    ldr r2, [r1, #SI_OWNER]
    ldr r12, [r1, #SI_CRC]
    push {r4-r6, lr}
    bl hold_owner_gone
    cmp r3, #0
    popeq {r4-r6, pc}
    mov r5, #0
si_release_key:
    mov r0, r5
    bl si_key_word
    ldr r3, [r4]
    tst r3, r6
    bne si_release_key_next
    mov r0, r5, lsl #8
    mov r1, #0
    bl si_post
    cmp r0, #0
    ldrne r3, [r4]
    orrne r3, r3, r6
    strne r3, [r4]
si_release_key_next:
    add r5, r5, #1
    cmp r5, #34
    blo si_release_key
    ldr r4, =SIM_INPUT+SI_UP_HI
    ldr r3, [r4]
    tst r3, #SI_TOUCH_BIT
    bne si_release_pads
    mov r0, #SI_TOUCH_UP
    mov r1, #0
    bl si_post
    cmp r0, #0
    ldrne r3, [r4]
    orrne r3, r3, #SI_TOUCH_BIT
    strne r3, [r4]
si_release_pads:
    mov r5, #0
si_release_pad:
    ldr r4, =SIM_INPUT+SI_PADS
    mov r6, #1
    mov r6, r6, lsl r5
    ldr r3, [r4]
    tst r3, r6
    bne si_release_pad_next
    mov r0, r5, lsl #8
    orr r0, r0, #4
    mov r1, #0
    bl si_post
    cmp r0, #0
    ldrne r3, [r4]
    orrne r3, r3, r6
    strne r3, [r4]
si_release_pad_next:
    add r5, r5, #1
    cmp r5, #16
    blo si_release_pad
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
