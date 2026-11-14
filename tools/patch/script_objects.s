; The object tree of the plugin API (data/script/objects.mjs): korg.get and korg.set reach every leaf through one table,
; a value outside its range is clamped and counted, and the stored ones are checked once the menu has read its settings.
; In the code area at MORE3_START. A row (OBJ_ROW_SIZE bytes): offset, min, max, factory (words), base, type, apply, flags (bytes), mirror, setter (words).
; The bases are the order of OBJECT_BASES (test/script-objects.test.mjs holds them): 0 MENU_STATE + offset, 1 the state words below + offset,
; 2 the absolute address offset, 3 the Global settings the firmware keeps + offset, 4 no address, offset picks a call into the patch pad-colors,
; 5 no address, read only, offset picks what the runtime knows about the device (INFO in data/script/objects.mjs),
; 6 no address: the touch pad mode, read from the firmware's touch pad object and the patch mfx-switch, set with the panel's keys,
; 7 no address: the motion switch of the selected part, set with one TAP of the patch tap-motion,
; 8 no address, read only: offset picks a state word of the firmware (STATE_WORDS in data/script/objects.mjs).
.equ OBJ_BASE_ABS, 2
.equ OBJ_BASE_GLOBAL, 3
.equ OBJ_BASE_PAD, 4
.equ OBJ_BASE_INFO, 5
.equ OBJ_BASE_TOUCHPAD, 6
.equ OBJ_BASE_MOTION, 7
.equ OBJ_BASE_STATE, 8
.equ POWER_MODEL, 0xC03405C4       ; pointer to the power source model, +0x308 1 on the adapter (docs/messungen/2026-11-11-plugin-api34-system.md)
.equ BATTERY_MODEL, 0xC03405C8     ; pointer to the battery model, +0x328 the level 0 to 4 its thresholds give
.equ STATE_MODEL, 0xC0348884       ; pointer to the sequencer model, +0x344 the bar section (as dice.py MODEL)
.equ KEY_TAP, 3
.equ MOTION_MODE_AT, 0x807        ; a part's Motion Sequence mode in the pattern object, 0x330 a part (0 off, 1 smooth, 2 trigger hold)
.equ TAP_HOOK, 0xC0042CC0         ; the key handler's word the patch tap-motion turns into a branch into its code
.equ TAP_CODE, 0xC0188000         ; its code; tm_active is the first function: r0 = 1 while the patch is on, clobbers r0 and r12
.equ TAP_CODE_END, 0xC0188800
.equ KEY_GATE_ARP, 4               ; korg.key: GATE ARP, TOUCH SCALE and MASTER FX follow each other
.equ KEY_TOUCH_SCALE, 5
.equ KEY_MASTER_FX, 6
.equ KEY_SHIFT, 10
.equ TOUCHPAD_OBJ, 0xC06912E0     ; pointer to the touch pad object, mode at +0x334 (0 GA, 1 TS, 2 MFX, 3 both), as mfx_switch.py CTL
.equ INFO_COUNT_IFX, 0xC003EFDC   ; the firmware's count of insert effects and of master effects, as fx_card.s calls them
.equ INFO_COUNT_MFX, 0xC003EFE4
.equ OBJ_SETTER_AT, 24            ; the Global menu's setter for the leaf on this build, 0 none (apply "setter")
.align 4
; korg.get(leaf, index) -> r0 = the value; no such leaf: API_ARG. A word above the leaf's range (a setting word a patch never
; wrote reads FFFFFFFF) reads as the factory value, which is what the patch does with it.
script_object_get_glue:
    push {r4, r5, lr}
    bl objects_row
    cmp r4, #0
    beq objects_bad_get
    ldrb r1, [r4, #16]
    cmp r1, #OBJ_BASE_PAD
    beq objects_pad_get
    cmp r1, #OBJ_BASE_INFO
    beq objects_info_get
    cmp r1, #OBJ_BASE_TOUCHPAD
    beq objects_touchpad_get
    cmp r1, #OBJ_BASE_MOTION
    beq objects_motion_get
    cmp r1, #OBJ_BASE_STATE
    beq objects_state_get
    ldrb r1, [r4, #17]
    cmp r1, #0
    ldrbeq r0, [r0]
    ldrne r0, [r0]
objects_get_done:
    ldr r1, [r4, #8]
    cmp r0, r1
    ldrhi r0, [r4, #12]
    mov r1, #ERR_OK
    pop {r4, r5, pc}
objects_bad_get:
    mov r0, #0
    mov r1, #ERR_API_ARG
    pop {r4, r5, pc}
; PAD COLOR, SELECT COLOR, OVERLAP, LED DIMMING and KNOB LEDS live in the patch pad-colors (menu_pc_call: 0 where the set has no such patch)
objects_pad_get:
    ldr r5, [r4]
    add r0, r5, #24                 ; the kind of PAD COLOR (24) or SELECT COLOR (25) for the entry +32
    cmp r5, #2
    movlo r1, #32
    moveq r1, #20
    movhi r1, #28
    cmp r5, #4
    moveq r1, #44
    bl menu_pc_call
    cmp r5, #3
    bleq led_dim_index              ; the patch's step -> the place in led_dim_percent the page counts by
    cmp r5, #4
    eoreq r0, r0, #1                ; KNOB LEDS: the entry says 1 for OFF, the leaf 1 for ON
    b objects_get_done
; korg.system.device, version and limits: r5 = what (INFO), the value from the build or the firmware at the time of the read
objects_info_get:
    ldr r5, [r4]
    cmp r5, #1
    movlo r0, #BUILD_DEVICE
    blo objects_get_done
    beq objects_info_version
    cmp r5, #3
    ldrlo r12, =INFO_COUNT_IFX
    ldreq r12, =INFO_COUNT_MFX
    ldrhi r0, =BUILD_SAMPLES
    bhi objects_get_done
    blx r12
    b objects_get_done
; korg.touchpad.mode: the firmware's mode, 4 for Master FX while the patch mfx-switch has MFX 2 active
objects_touchpad_get:
    bl objects_touchpad_mode
    b objects_get_done
; korg.motion.enabled: 1 when the selected part's Motion Sequence mode is not off
objects_motion_get:
    bl objects_motion_on
    b objects_get_done
; korg.pads.mode, korg.pads.bar and korg.screen
objects_state_get:
    ldr r0, [r4]
    bl objects_state_word
    b objects_get_done
; r0 = a state word (STATE_WORDS) -> r0 = the firmware's word, FFFFFFFF while its object does not exist (reads as the factory
; value). Clobbers r1, r2.
objects_state_word:
    ldr r1, =objects_state_words
    add r1, r1, r0, lsl #3
    ldr r2, [r1, #4]
    ldr r1, [r1]
    ldr r1, [r1]
    cmp r1, #0
    cmnne r1, #1
    mvneq r0, #0
    bxeq lr
    ldr r0, [r1, r2]
    bx lr
; per state word: the pointer to the firmware's object, the offset of the word in it
objects_state_words:
    .word HW_LED_MANAGER, 0xB58     ; padMode
    .word STATE_MODEL, 0x344        ; bar
    .word SCREEN_MANAGER, 0x2C      ; screen
    .word POWER_MODEL, 0x308        ; power: 1 adapter, 0 battery (panel message 7)
    .word BATTERY_MODEL, 0x328      ; battery: 4 full to 1 low, 0 empty
; r0 = 1 when the selected part plays its motion, 0 when it does not or no part is selected. Clobbers r1, r2.
objects_motion_on:
    ldr r1, =HW_PART
    ldr r1, [r1]
    cmp r1, #15
    movhi r0, #0
    bxhi lr
    ldr r2, =0x330
    mul r0, r1, r2
    ldr r1, =HW_PATTERN_OBJECT+MOTION_MODE_AT
    ldrb r0, [r1, r0]
    cmp r0, #0
    movne r0, #1
    bx lr
; r0 = the touch pad mode 0 to 4, 0xFF before the touch pad object exists (reads as the factory value). Clobbers r1, r2.
objects_touchpad_mode:
    ldr r0, =TOUCHPAD_OBJ
    ldr r0, [r0]
    cmp r0, #0
    moveq r0, #0xFF
    bxeq lr
    ldr r0, [r0, #0x334]
    cmp r0, #2
    bxne lr
    ldr r1, =MFX2_ENTRY
    ldr r1, [r1]
    ldr r2, =MFX2_RECORD_ID
    cmp r1, r2
    bxne lr
    ldr r1, =MFX2_STATE
    ldr r1, [r1]
    cmp r1, #1
    moveq r0, #4
    bx lr
; "BLECH x.y.z" of the patch blech-version -> x * 10000 + y * 100 + z; 0 where the set does not have it (FF)
objects_info_version:
    ldr r1, =VERSION_TEXT
    ldrb r2, [r1]
    cmp r2, #0x42
    movne r0, #0
    bne objects_get_done
    add r1, r1, #6
    mov r0, #0
    mov r3, #0
    mov r5, #0
objects_version_char:
    ldrb r2, [r1], #1
    sub r2, r2, #0x30
    cmp r2, #9
    bhi objects_version_part
    add r3, r3, r3, lsl #2
    add r3, r2, r3, lsl #1
    b objects_version_char
objects_version_part:               ; a dot or the NUL ends a number; the text is NUL padded, so a missing part reads 0
    mov r12, #100
    mla r0, r12, r0, r3
    mov r3, #0
    add r5, r5, #1
    cmp r5, #3
    blo objects_version_char
    b objects_get_done
; korg.set(leaf, index, value): clamps to the leaf's range (counted), writes, mirrors, applies; no such leaf or read only: API_ARG
script_object_set_glue:
    push {r4-r6, lr}
    mov r5, r2
    bl objects_row
    cmp r4, #0
    beq objects_bad_set
    ldrb r1, [r4, #19]
    tst r1, #1
    beq objects_bad_set
    mov r6, r0
    mov r0, r5
    bl objects_clamp
    ldrb r1, [r4, #16]
    cmp r1, #OBJ_BASE_PAD
    beq objects_pad_set
    cmp r1, #OBJ_BASE_TOUCHPAD
    beq objects_touchpad_set
    cmp r1, #OBJ_BASE_MOTION
    beq objects_motion_set
    ldr r12, [r4, #OBJ_SETTER_AT]   ; a Global setting goes through the firmware's own setter (Global object, value, 1), as the menu calls it
    cmp r12, #0
    bne objects_set_through
    ldrb r1, [r4, #17]
    cmp r1, #0
    strbeq r0, [r6]
    strne r0, [r6]
    ldr r1, [r4, #20]               ; the word a patch reads the setting from, next to the one the page shows
    cmp r1, #0
    strne r0, [r1]
    bl objects_apply
objects_set_done:
    ldr r1, =MENU_STATE             ; what the page said last ("SAVED") gives way to the new value
    ldr r2, [r1, #M_ON]
    cmp r2, #1
    moveq r2, #0
    streq r2, [r1, #M_STATUS]
    mov r0, #0
    mov r1, #ERR_OK
    pop {r4-r6, pc}
objects_set_through:
    mov r1, r0
    ldr r0, =GLOBALS_PTR
    ldr r0, [r0]
    cmp r0, #0
    beq objects_bad_set
    mov r2, #1
    blx r12
    b objects_set_done
objects_bad_set:
    mov r0, #0
    mov r1, #ERR_API_ARG
    pop {r4-r6, pc}
; r0 = the value, r4 = the row: the entries of the patch pad-colors (menu_pc_call takes the arguments r0 and r2)
objects_pad_set:
    ldr r1, [r4]
    cmp r1, #2
    blo objects_pad_colour
    beq objects_pad_over
    cmp r1, #4
    beq objects_pad_knob
    add r0, r0, #4                  ; LED DIMMING: the page's place -> the patch's step (the step 0 is 75 percent)
    cmp r0, #12
    subhs r0, r0, #12
    mov r1, #24
    b objects_pad_call
objects_pad_over:
    mov r1, #16
    b objects_pad_call
objects_pad_knob:
    eor r0, r0, #1                  ; KNOB LEDS: 1 OFF for the entry, r2 = 1 sends the five knob LEDs now as the page does
    mov r2, #1
    mov r1, #40
    b objects_pad_call
objects_pad_colour:
    mov r2, r0                      ; the colour; the entry swaps PAD and SELECT where the write would make them the same
    add r0, r1, #24
    mov r1, #36
objects_pad_call:
    bl menu_pc_call
    b objects_set_done

; korg.touchpad.mode = r0: one press of the key that leads from the current mode to r0, as a finger would, so LEDs and effect
; end up as after the key (korg.pressKey). The firmware's table is objects_touchpad_keys; with the patch mfx-switch on, GATE ARP
; gives 3, TOUCH SCALE 4 and MASTER FX 2 from every mode, and SHIFT + TOUCH SCALE 1. A mode no single press reaches stays as it is.
objects_touchpad_set:
    mov r5, r0
    bl objects_touchpad_mode
    cmp r0, r5
    beq objects_set_done
    mov r6, r0
    bl mfx2_on
    cmp r0, #0
    beq objects_touchpad_firmware
    cmp r5, #1
    beq objects_touchpad_shift
    subs r1, r5, #2
    bmi objects_set_done
    ldr r2, =objects_touchpad_patch
    ldrb r0, [r2, r1]
    b objects_touchpad_press
objects_touchpad_shift:
    mov r0, #KEY_SHIFT
    bl script_press_key_glue
    mov r0, #KEY_TOUCH_SCALE
    b objects_touchpad_press
objects_touchpad_firmware:
    cmp r6, #3
    bhi objects_set_done
    ldr r2, =objects_touchpad_keys
    add r2, r2, r6, lsl #2
    mov r1, #0
objects_touchpad_find:
    ldrb r3, [r2, r1]
    cmp r3, r5
    addeq r0, r1, #KEY_GATE_ARP
    beq objects_touchpad_press
    add r1, r1, #1
    cmp r1, #3
    blo objects_touchpad_find
    b objects_set_done
objects_touchpad_press:
    bl script_press_key_glue
    b objects_set_done

; korg.motion.enabled = r0: one press of TAP when the patch tap-motion is in the set and on and the switch differs, so its
; memory of the part's last mode and its LED stay right. Without the patch nothing changes.
objects_motion_set:
    mov r5, r0
    bl objects_motion_on
    cmp r0, r5
    beq objects_set_done
    ldr r1, =TAP_HOOK
    ldr r0, [r1]
    mov r2, r0, lsr #24
    cmp r2, #0xEA                   ; b, always
    bne objects_set_done
    mov r0, r0, lsl #8
    add r0, r1, r0, asr #6
    add r0, r0, #8
    ldr r2, =TAP_CODE
    cmp r0, r2
    blo objects_set_done
    ldr r2, =TAP_CODE_END
    cmp r0, r2
    bhs objects_set_done
    ldr r12, =TAP_CODE
    blx r12
    cmp r0, #0
    beq objects_set_done
    mov r0, #KEY_TAP
    b objects_touchpad_press

; r0 = leaf -> r4 = its row (0: no such leaf), r0 = the address of its value (bases 0 to 3; bases 4 to 8 have none)
objects_row:
    mov r4, #0
    cmp r0, #OBJ_COUNT
    bxhs lr
    ldr r4, =objects_table
    rsb r1, r0, r0, lsl #3          ; 7 words a row
    add r4, r4, r1, lsl #2
    ldrb r1, [r4, #16]
    ldr r0, [r4]
    cmp r1, #OBJ_BASE_ABS
    bxeq lr
    cmp r1, #OBJ_BASE_PAD
    bxeq lr
    cmp r1, #OBJ_BASE_INFO
    bxeq lr
    cmp r1, #OBJ_BASE_TOUCHPAD
    bxeq lr
    cmp r1, #OBJ_BASE_MOTION
    bxeq lr
    cmp r1, #OBJ_BASE_STATE
    bxeq lr
    cmp r1, #OBJ_BASE_GLOBAL
    beq objects_row_global
    ldr r2, =objects_bases
    ldr r2, [r2, r1, lsl #2]
    add r0, r2, r0
    bx lr
objects_row_global:                 ; before the Global settings exist the value is a word of its own, 0
    ldr r2, =GLOBALS_PTR
    ldr r2, [r2]
    cmp r2, #0
    addne r0, r2, r0
    ldreq r0, =objects_dummy
    bx lr

; r0 = value, r4 = row -> r0 inside min and max; one more in objects_repairs when it was outside (r1 to r3 change)
objects_clamp:
    ldr r1, [r4, #4]
    ldr r2, [r4, #8]
    cmp r0, r1
    movlt r0, r1
    blt objects_count
    cmp r0, r2
    bxle lr
    mov r0, r2
objects_count:
    ldr r3, =objects_state
    ldr r1, [r3]
    add r1, r1, #1
    str r1, [r3]
    bx lr

; r4 = row: makes the written value take effect
objects_apply:
    ldrb r0, [r4, #18]
    cmp r0, #1
    beq menu_look_apply
    cmp r0, #2
    beq testmode_keep_awake
    bx lr

; Every stored leaf outside its range goes to the nearest valid value, or to its factory value with the reset flag; each
; one counts. Called once the menu has read its settings (menu_arm_load), whatever left the value there.
objects_repair:
    push {r4-r7, lr}
    mov r5, #0
objects_repair_next:
    cmp r5, #OBJ_COUNT
    bhs objects_repair_out
    mov r0, r5
    bl objects_row
    add r5, r5, #1
    ldr r1, =objects_dummy          ; a Global leaf before the firmware has its Global settings: nothing stored to check yet
    cmp r0, r1
    beq objects_repair_next
    ldrb r1, [r4, #19]
    tst r1, #4
    beq objects_repair_next
    mov r6, r0
    ldrb r1, [r4, #17]
    cmp r1, #0
    ldrbeq r0, [r6]
    ldrne r0, [r6]
    mov r7, r0
    bl objects_clamp
    cmp r0, r7
    beq objects_repair_next
    ldrb r1, [r4, #19]
    tst r1, #2
    ldrne r0, [r4, #12]
    ldrb r1, [r4, #17]
    cmp r1, #0
    strbeq r0, [r6]
    strne r0, [r6]
    bl objects_apply
    b objects_repair_next
objects_repair_out:
    pop {r4-r7, pc}
; The frame hook (r0 = runtime): korg.menu.blech.write() asked for the settings file. Written as WRITE on a page writes it, once the
; main screen or BLECH is up (the card is idle there, as for the store of the plugins) and STORE_MIN_PAUSE_FRAMES after the last one.
; A request while the menu is not armed (EXIT at power-on) is dropped: there are no settings to write.
objects_write_flush:
    ldr r1, =objects_write
    ldrb r2, [r1]
    cmp r2, #1
    bxne lr
    ldr r2, =MENU_STATE
    ldr r2, [r2, #M_ON]
    cmp r2, #1
    movne r2, #0
    strbne r2, [r1]
    bxne lr
    ldr r2, =SCREEN_MANAGER
    ldr r2, [r2]
    cmp r2, #0
    bxeq lr
    cmn r2, #1
    bxeq lr
    ldr r2, [r2, #0x2c]
    cmp r2, #1
    cmpne r2, #MENU_SCREEN
    bxne lr
    ldr r2, =objects_write_frame
    ldr r3, [r2]
    ldr r12, [r0, #SCRIPT_CONTROL_FRAMES]
    cmp r3, #0
    beq objects_write_go
    sub r3, r12, r3
    cmp r3, #STORE_MIN_PAUSE_FRAMES
    bxlo lr
objects_write_go:
    str r12, [r2]
    mov r3, #0
    strb r3, [r1]
    b menu_settings_save
.pool

.align 4
; the mode after GATE ARP, TOUCH SCALE and MASTER FX in the firmware, a row per mode 0 to 3 (docs/messungen/2026-10-10-mfx-umschalter.md)
objects_touchpad_keys:
    .byte 0, 3, 2, 0
    .byte 3, 1, 2, 0
    .byte 0, 1, 2, 0
    .byte 0, 1, 2, 0
; with the patch mfx-switch on: the key for mode 2, 3 and 4
objects_touchpad_patch:
    .byte KEY_MASTER_FX, KEY_GATE_ARP, KEY_TOUCH_SCALE, 0
.align 4
objects_bases:
    .word MENU_STATE, objects_state
objects_state:
objects_repairs:
    .word 0                         ; values clamped or reset since start (korg.system.repairs)
objects_test_mode:
    .byte 0                         ; korg.system.testMode, 0 at power-on; set over USB only (script_remote.s, RM_TEST)
objects_keep_awake:
    .byte 0                         ; korg.system.keepAwake() writes 1 here
objects_write:
    .byte 0, 0                      ; korg.menu.blech.write() writes 1 here, objects_write_flush takes it
objects_dummy:
    .word 0                         ; the value of a Global leaf before the firmware has its Global settings
objects_write_frame:
    .word 0                         ; the frame of the last write
objects_touchpad_last:
    .word 0xFFFFFFFF                ; the touch pad mode of the last frame, for the event touchpadMode (script_events_poll)
objects_padmode_last:
    .word 0xFFFFFFFF                ; the pad mode and the screen number of the last frame, for padMode and screen
objects_screen_last:
    .word 0xFFFFFFFF
objects_table:
@OBJECT_ROWS@
.align 4
objects_end:
