; BLECH menu: an own top-level screen between Global and Data Util.
;
; Built like the Global pages screen (number 9): the constructor below is that
; constructor with our class table, tab text and page counter. The screen sits in
; the Edit ring (EDIT left and right move through its pages and on to the
; neighbours), shows one page at a time and keeps all of its state in MENU_STATE.
; Nothing here runs before the card hook has armed the menu (M_ON == 1) and EXIT
; at power-on keeps it unarmed, so the firmware stays as it was.
.equ M_ON, 0
.equ M_PAGE, 4
.equ M_ENTER, 8
.equ M_COUNT, 12
.equ M_SET_RUN, 16
.equ M_SET_MFX, 20
.equ M_EFF_RUN, 24
.equ M_EFF_MFX, 28
.equ M_GEN, 32
.equ M_STATUS, 36
.equ M_NSCRIPTS, 40
.equ M_TRUST_N, 44
.equ M_IMP_N, 48
.equ M_IMP_SEL, 52
.equ M_LISTED, 56
.equ M_ITEMS_N, 60
.equ MENU_ITEMS_MAX, 12
.equ M_LED_MODE, 0xA0
.equ M_LED_R, 0xA4
.equ M_LED_G, 0xA8
.equ M_LED_B, 0xAC
.equ M_BL_R, 0xB0
.equ M_BL_G, 0xB4
.equ M_BL_B, 0xB8
.equ M_LED_EFF, 0xBC
.equ M_LED_V, 0xC0
.equ M_BL_ON, 0xC4
.equ M_BL_PWM, 0xC8
.equ M_BL_N, 0xCC
.equ M_BL_CLR, 0xD0
.equ MX_INTENS, -0x20          ; the 32 bytes in front of MENU_STATE (behind the menu items): byte, INTENSITY of the backlight 0 to 15
.equ MX_SAVE, -0x1F            ; byte, SAVE LIGHT: 0 the firmware's own dim in power save, 1 to 15 the backlight at that intensity
.equ MX_OVER, -0x1E            ; byte, OVERLAP of the pad colours (0 the colour that is left)
.equ MX_METER, -0x1C           ; 4 bytes, the colours of the meter (STILL, LOW, MID, LOUD), 0 the firmware's
.equ MX_SAVE_ON, -0x18         ; byte, the backlight pins that light in power save
.equ MX_PHASE, -0x1D           ; byte, the hue of METER STILL RAINBOW, three steps every 40 ms
.equ MX_LOUD_PHASE, -0x17      ; 2 bytes (low, high), the hue of METER LOUD RAINBOW in 1/256 steps, a round a bar at the tempo
.equ METER_OFF, 9              ; METER STILL only: the still meter stays dark (bit 1 of byte 5 of the settings file)
.equ METER_RAINBOW, 8          ; METER STILL and LOUD: the colours turn round the wheel (STILL bit 30 of the settings flags, LOUD bit 0 of byte 5)
.equ MX_SAVE_CLR, -0x14        ; 16 bytes, the pins the PWM clears at tick n in power save
.equ M_PC, 0x158              ; the gap between the two settings buffers (M_FILE_A ends at 0x158, M_FILE_B starts at 0x160)
.equ PS_SETTING, 0xC0180F10
.equ M_TM, 0x15C              ; the other word of that gap: the page TAP MOTION, 1 on (the default), 0 off, 2 once
.equ TM_SETTING, 0xC0188F00   ; the setting word of the patch tap-motion: never written (FFFFFFFF) or 1 is on, 0 is off, 2 is once
.equ M_NA, 0xFC               ; the page NOTE ASSIST, 1 on (the default), 0 off
.equ NA_SETTING, 0xC0189F00   ; the setting word of the patch note-assistant: never written (FFFFFFFF) or 1 is on, 0 is off
.equ GPIO_BASE, 0x01E26000
.equ GPIO_WRITE, 0xC0016BB4
.equ GPIO_IN67, 0x01E26098    ; GPIO IN_DATA67; bit 31 (GPIO 7.15) is low while the power key is held
.equ OS_WAIT, 0xC0000B78      ; (ms): the operating system's sleep
.equ POWER_HOLD_STEP_MS, 50   ; the power key during the start: read every 50 ms,
.equ POWER_HOLD_STEPS, 100    ; held for 100 reads (5 s) switches off
.equ BL_DIM_FLAG, 0xC00F9310
.equ M_TRUST, 0x1C0
.equ M_INV, 0x1B8
.equ M_INV_HW, 0x1BC
.equ LCD_PAGE_HOOK_BACK, 0xC00161A8
.equ LCD_SEND, 0xC00160C4
.equ MENU_MAX_TRUST, 16
.equ M_TITLE, 0x40
.equ M_VALUE, 0x60
.equ M_LINE3, 0x80
.equ M_FILE_A, 0x100
.equ M_FILE_B, 0x160
.equ SETTINGS_MAGIC, 0x54455347
.equ SETTINGS_SIZE, 24
.equ SETTINGS_SIZE_V1, 20
.equ SETTINGS_MAX, 24+4*MENU_MAX_TRUST
.equ M_STATE_WORDS, 128
.equ SWITCH_SCREEN, 0xC0083D28
.equ PC_CODE, 0xC018B000        ; the patch pad-colors (tools/patch/pad_colors.py), FF where the set does not have it; its entries:
                                ; +0 (look word) takes the colours from it, +4 -> its bits for them, +8 (kind, steps) the next colour,
                                ; +12 (kind) -> title, r1 = value text; each sends the pads again where the colours change
; INIT PATTERN: the patch init-pattern (tools/patch/init_pattern.py), FF where the set does not have it; the page writes Global byte 247
.equ INIT_CODE, 0xC014FD00
.equ GLOBALS_PTR, 0xC0691324
.equ IP_SLOT, 247
.equ VERSION_TEXT, 0xC014FCF0   ; the patch blech-version (tools/patch/blech_version.mjs): "BLECH 1.3.7", NUL padded, FF where the set does not have it
.equ SPLASH_IMPORT, 0xC01A2500 ; the splash editor's entries (tools/patch/splash_editor.py), FF where the build has no editor
.equ SPLASH_DRAW, 0xC01A2504
.equ SPLASH_RESET, 0xC01A2508
.equ M_LEVEL, 0xE0
.equ M_GROUP, 0xE4
.equ M_RAW, 0xE8
.equ M_TOP, 0xEC
.equ M_TABW, 0xF0
.equ M_DESC_TOP, 0xF4           ; DESCRIPTION with the description read (M_LISTED 2): the first line of it on the screen
.equ M_DESC_N, 0xF8             ; byte: the lines of that description
.equ M_DESC_ON, 0xF9            ; byte: 1 while the picture of the description is on the display (script_display_blit copies it)
.equ M_CAL_ON, 0xFA             ; byte: 1 while the calibration picture is on the display (script_calibrate.s)
.equ M_PSEL, 0xFB               ; byte: the plugin SELECT PLUGIN chose (level 5), counted as menu_entry counts
.equ BLOCK_DELETED_HI, 0x80     ; bit 15 of a block's header flags, set in RAM by DELETE PLUGIN: the lists and EXPORT leave the block out
.equ DESC_ROWS, 5
.equ FS_OPENDIR, 0xC009E660
.equ FS_READDIR, 0xC009E740
.equ FS_CLOSEDIR, 0xC009E728
.equ LIST_DIR, 0x300
.equ LIST_INFO, 0x340
.equ LIST_LFN, 0x380
.equ LIST_PATH, 0x3C0
.equ LIST_NAMES, 0x400
.equ LIST_MAX, 16
.equ LIST_NAME_SIZE, 32
.equ LIST_TITLES, 0x600         ; the plugin name in the header of each listed file, 16 bytes each
.equ LIST_DESC, 0x700           ; the description of the plugin open in the list (DESC_MAX_BYTES and a zero); the list reads headers here
.equ MENU_MAX_SCRIPTS, 40
.equ BLOCK_PROBED, 1
.equ M_LEVEL_BLECHY, 3        ; level 3 of the screen is not a menu: it is the page of Blechy at the end of the ring
.equ M_LEVEL_SYNC, 4          ; level 4: the page SYNC GROUP, behind Blechy and right before the Pattern menu, where the build has sync groups
.equ HAS_SYNC, SYNC_GROUP_AT != 0
.equ M_LEVEL_PLUGIN, 5        ; level 5: the pages of one plugin, opened by ENTER on PLUGIN EDIT, built like the firmware's Sample Edit
.equ MENU_RING_TAIL, 1 + HAS_SYNC   ; the page of Blechy (and SYNC GROUP) come after the last page of the firmware's ring (Event)

; ---- start: arm the menu (called from the card hook wrapper, registers saved there)
menu_arm:
    push {r4, lr}
    ldr r4, =MENU_STATE
    ldr r0, =PANEL
    ldr r0, [r0]
    cmp r0, #0
    beq menu_arm_out
    cmn r0, #1
    beq menu_arm_out
    ldr r1, [r0, #0x18]
    tst r1, #KILL_MASK
    bne menu_arm_out
    ldrb r1, [r0, #0x22]
    cmp r1, #0
    bne menu_arm_out
    mov r0, r4
    mov r1, #0
    mov r2, #M_STATE_WORDS
menu_arm_zero:
    str r1, [r0], #4
    subs r2, r2, #1
    bne menu_arm_zero
    mov r0, #1
    str r0, [r4, #M_COUNT]
    mov r0, #1
    str r0, [r4, #M_SET_RUN]
    str r0, [r4, #M_SET_MFX]
    str r0, [r4, #M_EFF_RUN]
    str r0, [r4, #M_EFF_MFX]
    str r0, [r4, #M_PC]
    str r0, [r4, #M_TM]
    str r0, [r4, #M_NA]
    str r0, [r4, #M_INV]        ; DISPLAY INVERT is ON without a settings file: a light trail on dark smears less
    mov r0, #0x38
    str r0, [r4, #M_BL_ON]
    sub r0, r4, #0x20
    mov r1, #0
    mov r2, #8
menu_arm_extra:
    str r1, [r0], #4
    subs r2, r2, #1
    bne menu_arm_extra
    mov r0, #15
    strb r0, [r4, #MX_INTENS]
    mov r0, #1
    str r0, [r4, #M_ON]
menu_arm_out:
    pop {r4, pc}
.pool
menu_arm_end:

; Arms the menu and reads the settings once. A subsequent startup call leaves an armed menu intact.
menu_arm_load:
    push {lr}
    ldr r0, =MENU_STATE
    ldr r0, [r0, #M_ON]
    cmp r0, #1
    popeq {pc}
    bl menu_arm
    bl menu_settings_load
    bl objects_repair
    pop {pc}
.pool
menu_arm_load_end:

; ---- settings file: settings.a.bin and settings.b.bin alternate, the newer valid one is read.
; magic, version u16 (1 or 2), count u16 (the checksums of the foreign scripts the user allowed), generation u32, flags u32 (bit 0 scripts,
; bit 1 MFX 2, bit 2 the pattern confirmation is OFF, bit 3 TAP MOTION is OFF, bit 5 TAP MOTION is ONCE (only when bit 3 is clear), bit 4 NOTE ASSIST is OFF: a file without the bit, or no file, means ON), version 2 only: look u32 (bits 0 to 1 bottom LED mode 0 METER 1 COLOR 2 OFF, bits 4 to 15 LED red, green, blue
; level 0 to 15 each, all zero means the stock colours, bits 16 to 27 backlight red, green, blue level 0 to 15 each, all zero
; means the stock white, bit 28 the display inverted (no file or a version 1 file: inverted), bits 2 to 3 and 29 to 30 the pad colours (tools/patch/pad_colors.py); the pages show an all-zero triple as 15 each: a missing file or a zero word is the stock state, which is what the device shows, full light), count checksums u32, CRC-32 of
; everything before it: version 1 20 to 84 bytes, version 2 24 to 88 bytes. Always written as version 2, version 1 is still read.
; Called from the card hook wrapper after menu_arm, before the script loader reads M_EFF_RUN.
menu_settings_load:
    push {r4-r8, lr}
    ldr r4, =MENU_STATE
    ldr r0, [r4, #M_ON]
    cmp r0, #1
    bne menu_load_out
    ldr r5, =HOOK_CARD
    add r6, r5, #CARD_FIL
    ldr r0, =settings_path_a
    add r1, r4, #M_FILE_A
    bl menu_file_read
    mov r7, r0
    ldr r0, =settings_path_b
    add r1, r4, #M_FILE_B
    bl menu_file_read
    mov r8, r0
    add r0, r4, #M_FILE_A
    cmp r7, #0
    beq menu_load_b
    cmp r8, #0
    beq menu_load_apply
    ldr r1, [r4, #M_FILE_A+8]
    ldr r2, [r4, #M_FILE_B+8]
    cmp r2, r1
    addhi r0, r4, #M_FILE_B
    b menu_load_apply
menu_load_b:
    cmp r8, #0
    beq menu_load_out
    add r0, r4, #M_FILE_B
menu_load_apply:
    ldr r1, [r0, #8]
    str r1, [r4, #M_GEN]
    ldr r1, [r0, #12]
    and r2, r1, #1
    str r2, [r4, #M_SET_RUN]
    str r2, [r4, #M_EFF_RUN]
    mov r2, r1, lsr #1
    and r2, r2, #1
    str r2, [r4, #M_SET_MFX]
    str r2, [r4, #M_EFF_MFX]
    mov r2, r1, lsr #2
    and r2, r2, #1
    eor r2, r2, #1
    str r2, [r4, #M_PC]
    ldr r12, =PS_SETTING
    str r2, [r12]
    ldr r1, [r0, #12]
    mov r2, r1, lsr #3
    and r2, r2, #1
    eor r2, r2, #1
    cmp r2, #0
    tstne r1, #0x20
    movne r2, #2
    str r2, [r4, #M_TM]
    ldr r12, =TM_SETTING
    str r2, [r12]
    mov r2, r1, lsr #4
    and r2, r2, #1
    eor r2, r2, #1
    str r2, [r4, #M_NA]
    ldr r12, =NA_SETTING
    str r2, [r12]
    mov r2, r1, lsr #8          ; bits 8 to 11: 15 - INTENSITY, bits 12 to 15: SAVE LIGHT (0 in an older file: full light, the firmware's dim)
    and r2, r2, #15
    rsb r2, r2, #15
    strb r2, [r4, #MX_INTENS]
    mov r2, r1, lsr #12
    and r2, r2, #15
    strb r2, [r4, #MX_SAVE]
    mov r2, r1, lsr #16         ; bits 16 to 27: the four colours of the meter, 3 bits each, bit 30 STILL is RAINBOW
    sub r12, r4, #-MX_METER
    mov r1, #4
menu_load_meter:
    and r3, r2, #7
    strb r3, [r12], #1
    mov r2, r2, lsr #3
    subs r1, r1, #1
    bne menu_load_meter
    tst r2, #4                  ; bit 30, shifted down with the colours
    movne r3, #METER_RAINBOW
    strbne r3, [r4, #MX_METER]
    ldrb r3, [r0, #5]           ; bit 1 of byte 5: STILL is OFF (a file from before has 0 there)
    tst r3, #2
    movne r2, #METER_OFF
    strbne r2, [r4, #MX_METER]
    ldrb r3, [r0, #5]           ; bit 0 of byte 5: LOUD is RAINBOW
    tst r3, #1
    movne r3, #METER_RAINBOW
    strbne r3, [r4, #MX_METER+3]
    push {r0-r3}                ; bits 28 to 29: OVERLAP of the pad colours (the patch pad-colors keeps it)
    ldr r0, [r0, #12]
    mov r0, r0, lsr #28
    and r0, r0, #3
    mov r1, #16
    bl menu_pc_call
    ldr r0, [sp]                ; LED DIMMING (POWER SAVE): bits 6 and 7 and 31 of these flags, bit 31 of the look word (version 2)
    ldr r1, [r0, #12]
    ldrb r3, [r0, #4]
    cmp r3, #2
    ldreq r2, [r0, #16]
    movne r2, #0
    mov r0, r1, lsr #6
    and r0, r0, #3
    tst r1, #0x80000000
    orrne r0, r0, #4
    tst r2, #0x80000000
    orrne r0, r0, #8
    mov r1, #24
    bl menu_pc_call
    pop {r0-r3}
    ldrb r1, [r0, #6]
    str r1, [r4, #M_TRUST_N]
    add r2, r4, #M_TRUST
    ldrb r3, [r0, #4]
    cmp r3, #2
    addne r0, r0, #16
    bne menu_load_trust
    ldr r3, [r0, #16]
    and r12, r3, #3
    cmp r12, #2
    movhi r12, #0
    str r12, [r4, #M_LED_MODE]
    mov r12, r3, lsr #4
    and r12, r12, #15
    str r12, [r4, #M_LED_R]
    mov r12, r3, lsr #8
    and r12, r12, #15
    str r12, [r4, #M_LED_G]
    mov r12, r3, lsr #12
    and r12, r12, #15
    str r12, [r4, #M_LED_B]
    mov r12, r3, lsr #16
    and r12, r12, #15
    str r12, [r4, #M_BL_R]
    mov r12, r3, lsr #20
    and r12, r12, #15
    str r12, [r4, #M_BL_G]
    mov r12, r3, lsr #24
    and r12, r12, #15
    str r12, [r4, #M_BL_B]
    mov r12, r3, lsr #28
    and r12, r12, #1
    str r12, [r4, #M_INV]
    push {r0-r3}
    mov r0, r3
    mov r1, #0
    bl menu_pc_call
    pop {r0-r3}
    add r0, r0, #20
menu_load_trust:
    cmp r1, #0
    beq menu_load_look
    ldr r3, [r0], #4
    str r3, [r2], #4
    sub r1, r1, #1
    b menu_load_trust
menu_load_look:
    bl menu_look_apply
menu_load_out:
    pop {r4-r8, pc}
.pool

; r0 = path, r1 = buffer of SETTINGS_SIZE bytes, r5 = card scratch, r6 = file object -> r0 = 1 when the file is a valid settings file
menu_file_read:
    push {r4, r7, lr}
    mov r7, r1
    mov r1, r0
    mov r0, r6
    mov r2, #1
    ldr r12, =FS_OPEN
    blx r12
    cmp r0, #0
    bne menu_read_fail
    mov r0, r6
    mov r1, r7
    mov r2, #SETTINGS_MAX
    add r3, r5, #CARD_BR
    ldr r12, =FS_READ
    blx r12
    mov r4, r0
    mov r0, r6
    ldr r12, =FS_CLOSE
    blx r12
    cmp r4, #0
    bne menu_read_fail
    ldr r4, [r5, #CARD_BR]
    cmp r4, #SETTINGS_SIZE_V1
    blo menu_read_fail
    ldr r0, [r7]
    ldr r1, =SETTINGS_MAGIC
    cmp r0, r1
    bne menu_read_fail
    ldrb r0, [r7, #4]
    ldrb r1, [r7, #5]
    bics r1, r1, #3             ; byte 5: only bit 0 (LOUD RAINBOW) and bit 1 (STILL OFF) may be set
    bne menu_read_fail
    cmp r0, #2
    moveq r2, #SETTINGS_SIZE
    movne r2, #SETTINGS_SIZE_V1
    cmpne r0, #1
    bne menu_read_fail
    ldrb r0, [r7, #6]
    ldrb r1, [r7, #7]
    orr r0, r0, r1, lsl #8
    cmp r0, #MENU_MAX_TRUST
    bhi menu_read_fail
    mov r1, r0, lsl #2
    add r1, r1, r2
    cmp r4, r1
    bne menu_read_fail
    sub r4, r1, #4
    mvn r0, #0
    str r0, [r5, #CARD_CRC]
    mov r0, r7
    mov r1, r4
    bl card_crc
    ldr r0, [r5, #CARD_CRC]
    mvn r0, r0
    ldr r1, [r7, r4]
    cmp r0, r1
    bne menu_read_fail
    mov r0, #1
    pop {r4, r7, pc}
menu_read_fail:
    mov r0, #0
    pop {r4, r7, pc}
.pool

; Writes the edited settings as the next generation, in one write, to the file the newer one is not in.
; Sets M_STATUS: 1 written, 0x20 + code of the failing FatFs call otherwise.
menu_settings_save:
    push {r4-r10, lr}
    bl menu_off_sync
    ldr r4, =MENU_STATE
    ldr r5, =HOOK_CARD
    add r6, r5, #CARD_FIL
    add r7, r4, #M_FILE_A
    ldr r0, =SETTINGS_MAGIC
    str r0, [r7]
    mov r0, #2
    strb r0, [r7, #4]
    mov r0, #0
    strb r0, [r7, #5]
    ldr r9, [r4, #M_TRUST_N]
    strb r9, [r7, #6]
    strb r0, [r7, #7]
    ldr r8, [r4, #M_GEN]
    add r8, r8, #1
    str r8, [r7, #8]
    mov r0, #0
    ldr r1, [r4, #M_SET_RUN]
    cmp r1, #0
    orrne r0, r0, #1
    ldr r1, [r4, #M_SET_MFX]
    cmp r1, #0
    orrne r0, r0, #2
    ldr r1, [r4, #M_PC]
    cmp r1, #0
    orreq r0, r0, #4
    ldr r1, [r4, #M_TM]
    cmp r1, #0
    orreq r0, r0, #8
    cmp r1, #2
    orreq r0, r0, #0x20
    ldr r1, [r4, #M_NA]
    cmp r1, #0
    orreq r0, r0, #16
    ldrb r1, [r4, #MX_INTENS]
    rsb r1, r1, #15
    orr r0, r0, r1, lsl #8
    ldrb r1, [r4, #MX_SAVE]
    orr r0, r0, r1, lsl #12
    ldrb r2, [r4, #MX_METER+3]  ; the meter's colours, colour n at bits 16 + 3n
    cmp r2, #METER_RAINBOW      ; LOUD RAINBOW: its three bits stay 0, bit 0 of byte 5 says it
    moveq r2, #0
    moveq r1, #1
    strbeq r1, [r7, #5]
    ldrb r1, [r4, #MX_METER+2]
    orr r2, r1, r2, lsl #3
    ldrb r1, [r4, #MX_METER+1]
    orr r2, r1, r2, lsl #3
    ldrb r1, [r4, #MX_METER]
    cmp r1, #METER_OFF
    moveq r1, #0                ; OFF: the three bits of STILL stay 0, bit 1 of byte 5 says it
    ldrbeq r12, [r7, #5]
    orreq r12, r12, #2
    strbeq r12, [r7, #5]
    cmp r1, #METER_RAINBOW
    moveq r1, #0                ; RAINBOW: the three bits of STILL stay 0, bit 30 says it
    orr r2, r1, r2, lsl #3
    orr r0, r0, r2, lsl #16
    orreq r0, r0, #0x40000000
    mov r10, r0
    mov r1, #20
    bl menu_pc_call
    orr r10, r10, r0, lsl #28
    mov r1, #28                 ; LED DIMMING: bits 0 to 1 at 6 to 7, bit 2 at 31; bit 3 goes to bit 31 of the look word
    bl menu_pc_call
    and r1, r0, #3
    orr r10, r10, r1, lsl #6
    tst r0, #4
    orrne r10, r10, #0x80000000
    str r10, [r7, #12]
    ldr r0, [r4, #M_LED_MODE]
    ldr r1, [r4, #M_LED_R]
    orr r0, r0, r1, lsl #4
    ldr r1, [r4, #M_LED_G]
    orr r0, r0, r1, lsl #8
    ldr r1, [r4, #M_LED_B]
    orr r0, r0, r1, lsl #12
    ldr r1, [r4, #M_BL_R]
    orr r0, r0, r1, lsl #16
    ldr r1, [r4, #M_BL_G]
    orr r0, r0, r1, lsl #20
    ldr r1, [r4, #M_BL_B]
    orr r0, r0, r1, lsl #24
    ldr r1, [r4, #M_INV]
    orr r0, r0, r1, lsl #28
    mov r10, r0
    mov r1, #4
    bl menu_pc_call
    orr r10, r10, r0
    mov r1, #28
    bl menu_pc_call
    tst r0, #8
    orrne r10, r10, #0x80000000
    str r10, [r7, #16]
    add r0, r7, #20
    add r1, r4, #M_TRUST
    mov r2, r9
menu_save_trust:
    cmp r2, #0
    beq menu_save_trust_done
    ldr r3, [r1], #4
    str r3, [r0], #4
    sub r2, r2, #1
    b menu_save_trust
menu_save_trust_done:
    mov r10, r9, lsl #2
    add r10, r10, #20
    mvn r0, #0
    str r0, [r5, #CARD_CRC]
    mov r0, r7
    mov r1, r10
    bl card_crc
    ldr r0, [r5, #CARD_CRC]
    mvn r0, r0
    str r0, [r7, r10]
    add r10, r10, #4
    ldr r1, =settings_path_a
    tst r8, #1
    ldrne r1, =settings_path_b
    mov r0, r6
    bl card_create
    cmp r0, #0
    bne menu_save_fail
    mov r0, r6
    mov r1, r7
    mov r2, r10
    add r3, r5, #CARD_BR
    ldr r12, =FS_WRITE
    blx r12
    mov r9, r0
    mov r0, r6
    ldr r12, =FS_CLOSE
    blx r12
    cmp r9, #0
    bne menu_save_fail_r9
    ldr r0, [r5, #CARD_BR]
    cmp r0, r10
    movne r9, #2
    bne menu_save_fail_r9
    str r8, [r4, #M_GEN]
    mov r0, #1
    str r0, [r4, #M_STATUS]
    pop {r4-r10, pc}
menu_save_fail:
    mov r9, r0
menu_save_fail_r9:
    add r0, r9, #0x20
    str r0, [r4, #M_STATUS]
    pop {r4-r10, pc}
; Works out what the settings of the group CUSTOMIZATION do and puts them to work: the kind and the brightness of the
; bottom LEDs (M_LED_EFF: 0 the stock meter, 1 the meter in our colour, 2 a fixed colour; M_LED_V: red, green, blue as 0 to 255)
; and the backlight (pins that may light, the tables of the software PWM), then sets the backlight now.
; Called after the settings are read and after every change on one of the pages.
menu_look_apply:
    push {r4-r8, lr}
    ldr r4, =MENU_STATE
    ldr r0, [r4, #M_LED_R]
    ldr r1, [r4, #M_LED_G]
    ldr r2, [r4, #M_LED_B]
    orr r3, r0, r1
    orr r3, r3, r2
    add r0, r0, r0, lsl #4
    add r1, r1, r1, lsl #4
    add r2, r2, r2, lsl #4
    ldr r5, [r4, #M_LED_MODE]
    cmp r5, #2
    moveq r12, #2
    moveq r0, #0
    moveq r1, #0
    moveq r2, #0
    beq look_led_store
    cmp r3, #0
    bne look_led_custom
    cmp r5, #0
    moveq r12, #0
    beq look_led_store
    mov r0, #120
    mov r1, #120
    mov r2, #120
    mov r12, #2
    b look_led_store
look_led_custom:
    cmp r5, #0
    moveq r12, #1
    movne r12, #2
look_led_store:
    cmp r5, #0                  ; METER with a colour of the meter set: the meter in four colours (3)
    bne look_led_kind
    ldr r3, [r4, #MX_METER]
    cmp r3, #0
    movne r12, #3
look_led_kind:
    strb r0, [r4, #M_LED_V]
    strb r1, [r4, #M_LED_V+1]
    strb r2, [r4, #M_LED_V+2]
    str r12, [r4, #M_LED_EFF]
    ldr r0, [r4, #M_BL_R]
    ldr r7, [r4, #M_BL_G]
    ldr r8, [r4, #M_BL_B]
    orr r3, r0, r7
    orrs r3, r3, r8
    moveq r0, #15
    moveq r7, #15
    moveq r8, #15
    push {r0, r7, r8}           ; the levels of the colour, scaled by INTENSITY for the light and by SAVE LIGHT for power save
    ldrb r1, [r4, #MX_INTENS]
    add r5, r4, #M_BL_CLR
    bl look_triple
    str r12, [r4, #M_BL_ON]
    str r6, [r4, #M_BL_PWM]
    ldrb r1, [r4, #MX_SAVE]     ; DISPLAY LIGHT 1 to 15 lights at 3 to 15 of 15: 1 of 15 was dark on battery (device 19.10.)
    cmp r1, #0
    movne r0, #12
    mulne r2, r1, r0
    addne r2, r2, #30
    ldrne r0, =4682             ; / 14: * 4682 >> 16
    mulne r1, r2, r0
    movne r1, r1, lsr #16
    sub r5, r4, #-MX_SAVE_CLR
    bl look_triple
    strb r12, [r4, #MX_SAVE_ON]
    add sp, sp, #12
    mov r0, #0
    str r0, [r4, #M_BL_N]
    bl menu_backlight_now
    pop {r4-r8, pc}

; r1 = intensity 0 to 15, r5 = a table of 16 bytes, the three levels of the colour at sp (the caller's push): the levels scaled
; by the intensity go into the table -> r12 = the pins that light, r6 = 1 when a level needs the PWM. Clobbers r0 to r3.
look_triple:
    push {r7, lr}
    mov r7, r1
    mov r3, #0
    str r3, [r5]
    str r3, [r5, #4]
    str r3, [r5, #8]
    str r3, [r5, #12]
    mov r12, #0
    mov r6, #0
    ldr r0, [sp, #8]
    bl look_scale
    mov r3, #0x08
    bl look_channel
    ldr r0, [sp, #12]
    bl look_scale
    mov r3, #0x10
    bl look_channel
    ldr r0, [sp, #16]
    bl look_scale
    mov r3, #0x20
    bl look_channel
    pop {r7, pc}

; r0 = level 0 to 15, r7 = intensity 0 to 15 -> r0 = level * intensity / 15, rounded. Clobbers r2.
look_scale:
    mul r2, r0, r7
    add r2, r2, #7
    mov r0, #0x1100
    orr r0, r0, #0x12
    mul r0, r2, r0
    mov r0, r0, lsr #16
    bx lr

; r0 = level 0 to 15, r3 = the pin of the channel, r12 = pins that may light, r6 = 1 when a level needs the PWM,
; r5 = the table of the pins the PWM clears at tick n
look_channel:
    cmp r0, #0
    bxeq lr
    orr r12, r12, r3
    cmp r0, #15
    bxhs lr
    mov r6, #1
    ldrb r2, [r5, r0]
    orr r2, r2, r3
    strb r2, [r5, r0]
    bx lr
; The backlight as the firmware sets it when the light comes back from power save: all three pins on, our setter hooks leave
; on what the settings allow. Not while the firmware dims (power save), the dim routine owns the pins then.
menu_backlight_now:
    push {r4, lr}
    ldr r0, =BL_DIM_FLAG
    ldrb r0, [r0]
    cmp r0, #0
    bne bl_now_out
    ldr r4, =GPIO_BASE
    mov r0, r4
    mov r1, #1
    bl 0xC0016C98
    mov r0, r4
    mov r1, #1
    bl 0xC0016CE0
    mov r0, r4
    mov r1, #1
    bl 0xC0016D28
bl_now_out:
    pop {r4, pc}
.pool
settings_path_a:
    .asciz "SD:KORG/blechtribe/settings.a.bin"
settings_path_b:
    .asciz "SD:KORG/blechtribe/settings.b.bin"
.align 4
.pool
menu_settings_end:

; ---- hooks into the firmware: each returns to the word behind the one it replaced
; 0xC0064430, the Event menu's EDIT right: `push {r3, r4, r5, lr}` (it prepares the Pattern menu and switches to it). With the menu armed
; the ring goes on to the page BLECH first, level 0 of our screen, then Blechy (level 3), then the Pattern menu: BLECH is the last
; menu of the ring, behind Event (device 18.10.: it sat between Global and Data Util).
menu_event_right:
    ldr r2, =MENU_STATE
    ldr r3, [r2, #M_ON]
    cmp r3, #1
    bne menu_event_right_go
    mov r3, #0
    str r3, [r2, #M_LEVEL]
    str r3, [r2, #M_ENTER]
    mov r0, #MENU_SCREEN
    mov r1, #0
    ldr pc, =SWITCH_SCREEN
menu_event_right_go:
    push {r3, r4, r5, lr}
    ldr pc, =0xC0064434
.pool
; 0xC0067754, the Pattern menu's EDIT left on its first page: `mov r0, #10` (Event), then it switches screens. With the menu armed
; the ring goes back to the page SYNC GROUP first (the page of Blechy where the build has no sync groups).
menu_pattern_left:
    ldr r2, =MENU_STATE
    ldr r3, [r2, #M_ON]
    cmp r3, #1
    movne r0, #10
    bne menu_pattern_left_go
    mov r3, #M_LEVEL_BLECHY+HAS_SYNC
    str r3, [r2, #M_LEVEL]
    mov r3, #0
    str r3, [r2, #M_ENTER]
    mov r0, #MENU_SCREEN
menu_pattern_left_go:
    ldr pc, =0xC0067758
.pool
; BLECH stays a top-level screen for MENU navigation.
@MENU_TOPLEVEL@
; 0xC006F094, WRITE on every screen: `push {r3, r4, r5, lr}`. Ours does not open
; the pattern write window, except on the page SYNC GROUP: it is a setting of the pattern, WRITE saves the pattern as on its other pages.
menu_write:
    ldr r3, [r0, #0x1c]
    cmp r3, #MENU_SCREEN
    bne menu_write_go
    ldr r3, =MENU_STATE
    ldr r3, [r3, #M_LEVEL]
    cmp r3, #M_LEVEL_SYNC
    bxne lr
menu_write_go:
    push {r3, r4, r5, lr}
    ldr pc, =0xC006F098
.pool
; 0xC008A83C and 0xC008A8A8, the page counter "n/29": the total grows by the page BLECH and the page of Blechy while the menu is
; armed (both sit behind Event, the last of the firmware's: BLECH is 30/31, Blechy 31/31).
menu_counter_new:
    ldr r3, =MENU_STATE
    ldr r3, [r3, #M_RAW]
    cmp r3, #0
    bne menu_counter_new_go
    cmp r2, #MENU_RING_TOTAL
    bne menu_counter_new_go
    ldr r3, =MENU_STATE
    ldr r3, [r3, #M_ON]
    cmp r3, #1
    bne menu_counter_new_go
    ldr r3, =MENU_STATE
    ldr r3, [r3, #M_COUNT]
    add r2, r2, r3
    add r2, r2, #MENU_RING_TAIL
    cmp r1, #MENU_RING_FIRST
    addge r1, r1, r3
menu_counter_new_go:
    mov r3, #0
    ldr pc, =0xC008A840
.pool
menu_counter_set:
    push {r4, lr}
    ldr r3, =MENU_STATE
    ldr r3, [r3, #M_RAW]
    cmp r3, #0
    bne menu_counter_set_go
    cmp r2, #MENU_RING_TOTAL
    bne menu_counter_set_go
    ldr r3, =MENU_STATE
    ldr r3, [r3, #M_ON]
    cmp r3, #1
    bne menu_counter_set_go
    ldr r3, =MENU_STATE
    ldr r3, [r3, #M_COUNT]
    add r2, r2, r3
    add r2, r2, #MENU_RING_TAIL
    cmp r1, #MENU_RING_FIRST
    addge r1, r1, r3
menu_counter_set_go:
    ldr pc, =0xC008A8AC
.pool
menu_hooks_end:

; ---- hooks of the group CUSTOMIZATION, each returns to the word behind the one it replaced.
; All of them give the firmware its way when the menu is not armed (EXIT at power-on), and the backlight ones also while
; the firmware dims the light for power save: that stays exactly as it is.
; 0xC0088284, the bottom LEDs (the level meter), called every 40 ms: r0 = LED manager, r1 = 1 meter on, 0 off.
; The stock function starts with `ldrb r3, [r0, #0xb98]` (the lock a plugin holds). r1 = 0 is the firmware's own
; switch off (Global power save with battery), it stays. Otherwise, with another look than the stock meter, the twelve
; channels are set the way the firmware does it (brightness into the target table, then 0xC00875F4), from the
; same smoothed level the meter uses (0xC0088220), so the colour follows the level.
led_meter_hook:
    ldr r2, =MENU_STATE
    ldr r3, [r2, #M_ON]
    cmp r3, #1
    bne led_meter_pass
    cmp r1, #0
    beq led_meter_pass
    ldr r3, [r2, #M_LED_EFF]
    cmp r3, #0
    beq led_meter_pass
    ldrb r12, [r0, #0xb98]
    cmp r12, #0
    bne led_meter_pass
    push {r4-r10, lr}
    sub sp, sp, #8
    mov r4, r0
    mov r9, #256
    mov r10, #256
    cmp r3, #2
    beq led_meter_loop_start
    ldr r6, =0xC033E4F4
    ldr r6, [r6]
    mov r0, #0
    mov r1, #0
    cmp r6, #0
    beq led_meter_levels
    ldrb r0, [r6, #0x13]
    mov r0, r0, lsl #24
    mov r0, r0, asr #23
    ldr r1, [r6, #0x14]
    mov r1, r1, asr #24
    mov r1, r1, lsl #1
led_meter_levels:
    str r0, [sp]
    str r1, [sp, #4]
    mov r0, sp
    add r1, sp, #4
    bl 0xC0088220
    ldr r0, [sp]
    ldr r1, [sp, #4]
    ldr r3, =MENU_STATE
    ldr r3, [r3, #M_LED_EFF]
    cmp r3, #3
    beq led_meter_four
    mov r3, #191
    mul r2, r0, r0
    mov r2, r2, lsr #8
    mul r10, r2, r3
    mov r10, r10, lsr #8
    add r10, r10, #64
    mul r2, r1, r1
    mov r2, r2, lsr #8
    mul r9, r2, r3
    mov r9, r9, lsr #8
    add r9, r9, #64
led_meter_loop_start:
    ldr r6, =MENU_STATE
    add r6, r6, #M_LED_V
    mov r5, #0
    mov r7, #0
led_meter_loop:
    cmp r5, #6
    movlo r8, r9
    movhs r8, r10
    ldrb r2, [r6, r7]
    mul r3, r2, r8
    mov r3, r3, lsr #8
    cmp r3, #1                  ; never 1: see led_meter_four_loop
    moveq r3, #2
    add r0, r4, r5, lsl #3
    strb r3, [r0, #0x2ae]
    mov r0, r4
    add r1, r5, #0x4c
    mov r2, #0
    bl 0xC00875F4
    add r7, r7, #1
    cmp r7, #3
    moveq r7, #0
    add r5, r5, #1
    cmp r5, #12
    blo led_meter_loop
    add sp, sp, #8
    pop {r4-r10, pc}
; The meter in four colours (device 18.10.): per side the zone of its level as the firmware divides it (0 STILL, up to 70 LOW, up to
; 187 MID, above LOUD) gives the colour, the user's from the palette or, for a zone left at STOCK, the firmware's (white, blue,
; green, red). r0, r1 = the levels of the two sides (LEDs 6 to 11, 0 to 5).
led_meter_four:
    bl meter_rainbow
    mov r12, sp
    bl meter_colour
    mov r10, r2
    mov r0, r1
    add r12, sp, #4
    bl meter_colour
    mov r9, r2
    mov r5, #0
led_meter_four_loop:
    cmp r5, #6
    movlo r8, r9
    movhs r8, r10
    mov r0, r5
led_meter_mod3:
    cmp r0, #3
    subhs r0, r0, #3
    bhs led_meter_mod3
    ldrb r3, [r8, r0]
    cmp r3, #1                  ; never 1: 0xC00875F4 compares what it sent last with the message's mode byte (1 for these LEDs),
    moveq r3, #2                ; so after a 1 it sends nothing more and the channel sticks (emulator 22.10., the rainbow)
    add r0, r4, r5, lsl #3
    strb r3, [r0, #0x2ae]
    mov r0, r4
    add r1, r5, #0x4c
    mov r2, #0
    bl 0xC00875F4
    add r5, r5, #1
    cmp r5, #12
    blo led_meter_four_loop
    add sp, sp, #8
    pop {r4-r10, pc}
; r0 = level 0 to 255, r12 = 3 free bytes -> r2 = the three bytes (red, green, blue) of its colour. Keeps r1.
; A zone left at STOCK takes the colour of the LED pages when one is set, as bright as the level like the meter in our colour.
meter_colour:
    cmp r0, #0
    moveq r3, #0
    beq meter_zone
    cmp r0, #70
    movle r3, #1
    ble meter_zone
    cmp r0, #187
    movle r3, #2
    movgt r3, #3
meter_zone:
    ldr r2, =MENU_STATE
    sub r2, r2, #-MX_METER
    ldrb r2, [r2, r3]
    cmp r2, #METER_RAINBOW
    beq meter_zone_rainbow
    cmp r2, #METER_OFF
    moveq r2, #0                ; OFF: the palette's black
    beq meter_zone_palette
    cmp r2, #0
    bne meter_zone_palette
    ldr r2, =MENU_STATE
    ldr r2, [r2, #M_LED_V]
    bics r2, r2, #0xFF000000
    addeq r2, r3, #8            ; STOCK without a colour on the LED pages: the firmware's colour of the zone, behind the palette
    beq meter_zone_palette
    push {r1, r4}
    mul r3, r0, r0              ; 64 + level² * 191, as led_meter_hook does for the meter in our colour
    mov r3, r3, lsr #8
    mov r4, #191
    mul r0, r3, r4
    mov r0, r0, lsr #8
    add r0, r0, #64
    mov r1, #0
meter_zone_led:
    and r3, r2, #255
    mul r4, r3, r0
    mov r4, r4, lsr #8
    strb r4, [r12, r1]
    mov r2, r2, lsr #8
    add r1, r1, #1
    cmp r1, #3
    blo meter_zone_led
    mov r2, r12
    pop {r1, r4}
    bx lr
meter_zone_palette:
    ldr r0, =meter_palette
    add r2, r2, r2, lsl #1
    add r2, r0, r2
    bx lr
; RAINBOW of a zone (r3 = 0 STILL, else LOUD): the colour of its hue to the 3 bytes at r12 -> r2 = r12. Keeps r1.
; Round the wheel red, green, blue: three segments of 256 steps.
meter_zone_rainbow:
    ldr r2, =MENU_STATE
    cmp r3, #0
    ldrbeq r3, [r2, #MX_PHASE]
    ldrbne r3, [r2, #MX_LOUD_PHASE+1]
    push {r0, r1}
    add r3, r3, r3, lsl #1      ; 0 to 765: three segments of 256
    and r1, r3, #255            ; rising
    rsb r0, r1, #255            ; falling
    mov r3, r3, lsr #8
    mov r2, #0
    cmp r3, #1
    beq meter_rainbow_gb
    bhi meter_rainbow_br
    strb r0, [r12]              ; red to green
    strb r1, [r12, #1]
    strb r2, [r12, #2]
    b meter_rainbow_out
meter_rainbow_gb:               ; green to blue
    strb r2, [r12]
    strb r0, [r12, #1]
    strb r1, [r12, #2]
    b meter_rainbow_out
meter_rainbow_br:               ; blue to red
    strb r1, [r12]
    strb r2, [r12, #1]
    strb r0, [r12, #2]
meter_rainbow_out:
    mov r2, r12
    pop {r0, r1}
    bx lr
; The hues of RAINBOW, a step each tick (40 ms). STILL: three steps of 256, round the wheel in 86 ticks, about 3.4 s.
; LOUD: a round a bar (four beats) at the tempo, the hue in 1/256 steps: tempo/10 BPM / 60 * 0.04 s / 4 * 65536 = tempo * 1.0923,
; at 128 BPM 1.9 s a round. Keeps r0 and r1.
meter_rainbow:
    ldr r2, =MENU_STATE
    ldrb r3, [r2, #MX_METER]
    cmp r3, #METER_RAINBOW
    ldrbeq r3, [r2, #MX_PHASE]
    addeq r3, r3, #3
    strbeq r3, [r2, #MX_PHASE]
    ldrb r3, [r2, #MX_METER+3]
    cmp r3, #METER_RAINBOW
    bxne lr
    push {r0, r1}
    ldr r0, =HW_TEMPO
    ldr r0, [r0]                ; tenths of a BPM
    ldr r1, =4474               ; * 1.0923: * 4474 >> 12
    mul r3, r0, r1
    mov r3, r3, lsr #12
    ldrb r0, [r2, #MX_LOUD_PHASE]
    ldrb r1, [r2, #MX_LOUD_PHASE+1]
    orr r0, r0, r1, lsl #8
    add r0, r0, r3
    strb r0, [r2, #MX_LOUD_PHASE]
    mov r0, r0, lsr #8
    strb r0, [r2, #MX_LOUD_PHASE+1]
    pop {r0, r1}
    bx lr
led_meter_pass:
    ldrb r3, [r0, #0xb98]
    ldr pc, =0xC0088288
.pool
; 0xC0016C98, 0xC0016CE0, 0xC0016D28: the firmware's red, green and blue backlight pin, r0 = GPIO, r1 = 1 on. The firmware
; calls them with 1 wherever its normal light is due (start, back from power save), here a channel the settings keep dark
; stays off. Each starts with `push {fp, lr}`.
bl_set_red:
    ldr r2, =MENU_STATE
    ldr r3, [r2, #M_ON]
    cmp r3, #1
    bne bl_red_go
    ldr r3, =BL_DIM_FLAG
    ldrb r3, [r3]
    cmp r3, #0
    bne bl_red_go
    ldr r3, [r2, #M_BL_ON]
    tst r3, #0x08
    moveq r1, #0
bl_red_go:
    push {fp, lr}
    ldr pc, =0xC0016C9C
.pool
bl_set_green:
    ldr r2, =MENU_STATE
    ldr r3, [r2, #M_ON]
    cmp r3, #1
    bne bl_green_go
    ldr r3, =BL_DIM_FLAG
    ldrb r3, [r3]
    cmp r3, #0
    bne bl_green_go
    ldr r3, [r2, #M_BL_ON]
    tst r3, #0x10
    moveq r1, #0
bl_green_go:
    push {fp, lr}
    ldr pc, =0xC0016CE4
.pool
bl_set_blue:
    ldr r2, =MENU_STATE
    ldr r3, [r2, #M_ON]
    cmp r3, #1
    bne bl_blue_go
    ldr r3, =BL_DIM_FLAG
    ldrb r3, [r3]
    cmp r3, #0
    bne bl_blue_go
    ldr r3, [r2, #M_BL_ON]
    tst r3, #0x20
    moveq r1, #0
bl_blue_go:
    push {fp, lr}
    ldr pc, =0xC0016D2C
.pool
; 0xC00289F4, the firmware's dim routine, called from the 2 kHz timer interrupt (0xC0025B60): `push {r4, r5, r6, lr}`.
; A backlight colour with a level between 1 and 14 is a software PWM of 16 ticks (8 ms, 125 Hz): at tick 0 the pins of all
; lit channels go on, the pin of a channel goes off at the tick that equals its level (M_BL_CLR). Levels 0 and 15 and
; the stock white need no PWM (M_BL_PWM is 0, nothing here runs). Not while the firmware dims.
bl_pwm_hook:
    ldr r2, =MENU_STATE
    ldr r3, [r2, #M_ON]
    cmp r3, #1
    bne bl_pwm_pass
    ldr r3, =BL_DIM_FLAG
    ldrb r3, [r3]
    cmp r3, #0
    beq bl_pwm_normal
    ldrb r3, [r2, #MX_SAVE]     ; power save dims: with SAVE LIGHT the light of the colour at that intensity, else the firmware's dim
    cmp r3, #0
    beq bl_pwm_pass
    push {r4, r5, r6, r7, r8, lr}
    mov r5, r2
    ldrb r6, [r5, #MX_SAVE_ON]
    sub r7, r5, #-MX_SAVE_CLR
    b bl_pwm_run
bl_pwm_normal:
    ldr r3, [r2, #M_BL_PWM]
    cmp r3, #0
    beq bl_pwm_pass
    push {r4, r5, r6, r7, r8, lr}
    mov r5, r2
    ldr r6, [r5, #M_BL_ON]
    add r7, r5, #M_BL_CLR
bl_pwm_run:
    ldr r4, [r5, #M_BL_N]
    add r4, r4, #1
    and r4, r4, #15
    str r4, [r5, #M_BL_N]
    cmp r4, #0
    bne bl_pwm_clear
    ldr r0, =GPIO_BASE
    mov r1, #0
    mov r2, #3
    eor r3, r6, #0x38           ; the pins that stay dark (the firmware's dim may have left one on)
    bl GPIO_WRITE
    ldr r0, =GPIO_BASE
    mov r1, #1
    mov r2, #3
    mov r3, r6
    bl GPIO_WRITE
bl_pwm_clear:
    ldrb r3, [r7, r4]
    cmp r3, #0
    beq bl_pwm_done
    ldr r0, =GPIO_BASE
    mov r1, #0
    mov r2, #3
    bl GPIO_WRITE
bl_pwm_done:
    pop {r4, r5, r6, r7, r8, pc}   ; the firmware's dim routine would only return (not dimming) or is replaced (SAVE LIGHT)
bl_pwm_pass:
    push {r4, r5, r6, lr}
    ldr pc, =0xC00289F8
.pool
; 0xC00161A4, the display's page write: after the commands that select the page and the column (0xB0 + page, 0x40, 0x10, 0x00,
; the data line is still low) the stock code runs `ldr r3, [fp, #-0x10]` (the display object). When the settings want the other
; polarity than the one sent last, the controller gets 0xA7 (display reversed: dark and clear swap) or 0xA6 (normal) here, once.
; Nothing else is ever sent: with the menu not armed (EXIT at power-on) the hook does nothing, otherwise it only compares
; two words once the polarity is sent (the default is ON, so the first page write after the arm sends 0xA7). The firmware never sends either command itself.
lcd_invert_hook:
    ldr r2, =MENU_STATE
    ldr r3, [r2, #M_ON]
    cmp r3, #1
    bne lcd_invert_pass
    ldr r3, [r2, #M_INV]
    ldr r1, [r2, #M_INV_HW]
    cmp r3, r1
    beq lcd_invert_pass
    str r3, [r2, #M_INV_HW]
    push {r4, lr}
    cmp r3, #0
    movne r1, #0xA7
    moveq r1, #0xA6
    ldr r0, [fp, #-0x10]
    bl LCD_SEND
    pop {r4, lr}
lcd_invert_pass:
    ldr r3, [fp, #-0x10]
    ldr pc, =LCD_PAGE_HOOK_BACK
.pool
look_hooks_end:

; ---- the screen
; Table entry 45, factory(arg): an object of 52 bytes, built like Global's.
menu_factory:
    push {r4, lr}
    mov r0, #52
    bl 0xC0028DCC
    mov r4, r0
    bl menu_construct
    mov r0, r4
    pop {r4, pc}

; r0 = object. Global's constructor (0xC0064C30), with our vtable, tab text,
; counter and first page.
menu_construct:
    ldr r2, =MENU_VTABLE
    mov r3, #0
    push {r0, r1, r4, r5, r6, r7, r8, lr}
    str r3, [r0, #0x4]
    str r3, [r0, #0x8]
    str r3, [r0, #0xc]
    str r3, [r0, #0x10]
    str r3, [r0, #0x14]
    str r3, [r0, #0x18]
    strb r3, [r0, #0x1c]
    strb r3, [r0, #0x1d]
    str r3, [r0, #0x2c]
    strb r3, [r0, #0x30]
    str r2, [r0]
    mov r4, r0
    bl 0xC00431B8
    add r5, sp, #8
    add r6, r4, #16
    mov r0, #56
    bl 0xC0028DCC
    mov r7, r0
    bl 0xC0085464
    str r7, [r5, #-0x4]!
    mov r0, r6
    mov r1, r5
    bl 0xC00614FC
    bl 0xC00431B8
    cmp r0, #0
    addne r8, r0, #4
    moveq r8, r0
    mov r0, #204
    bl 0xC0028DCC
    mov r1, r8
    mov r7, r0
    bl 0xC00856C0
    mov r1, r5
    str r7, [r4, #0x24]
    mov r0, r6
    str r7, [sp, #0x4]
    bl 0xC00614FC
    mov r0, #60
    bl 0xC0028DCC
    ldr r1, =menu_tab
    mov r7, r0
    bl 0xC0085218
    ldr r3, =MENU_STATE
    str r7, [r3, #M_TABW]
    mov r1, r5
    mov r0, r6
    str r7, [sp, #0x4]
    bl 0xC00614FC
    bl menu_enter_page
    mov r0, #84
    bl 0xC0028DCC
    mov r7, r0
    bl menu_counter_args
    mov r0, r7
    bl 0xC008A83C
    ldr r3, =MENU_STATE
    mov r2, #0
    str r2, [r3, #M_RAW]
    mov r0, r6
    mov r1, r5
    str r7, [r4, #0x28]
    str r7, [sp, #0x4]
    bl 0xC00614FC
    mov r0, r4
    bl menu_show
    mov r0, r4
    add sp, sp, #8
    pop {r4, r5, r6, r7, r8, pc}
.pool

; r0 = object. Fills the three text lines and the counter for the current page.
menu_show:
    push {r4, r5, lr}
    mov r4, r0
    ldr r5, =MENU_STATE
    ldr r0, [r5, #M_PAGE]
    bl menu_texts
    bl menu_tab_text
    bl menu_desc_frame
    ldr r0, [r4, #0x24]
    add r1, r5, #M_TITLE
    bl 0xC00857E4
    ldr r0, [r4, #0x24]
    add r1, r5, #M_VALUE
    bl 0xC0085828
    ldr r0, [r4, #0x24]
    add r1, r5, #M_LINE3
    bl 0xC0085888
    bl menu_counter_args
    ldr r0, [r4, #0x28]
    bl 0xC008A8A8
    mov r2, #0
    str r2, [r5, #M_RAW]
    pop {r4, r5, pc}
.pool

; r0 = page. Writes the title and the value into the buffers of MENU_STATE. The firmware's third line (the unit) is drawn
; from a fixed column (28) on the row of the value, so any value wider than a character or two runs into it: it is
; never used. What a page has to say goes into the value, which has room for about 14 characters; the title row
; holds about 18.
menu_texts:
    push {r4, lr}
    bl menu_texts_fill
    pop {r4, pc}

; r0 = group -> r0 = the title buffer: a page's title is its own name, the tab on top of the screen names the group (menu_tab_text).
menu_title_prefix:
    add r0, r5, #M_TITLE
    bx lr

; The tab on top of the screen reads BLECH on the top level and the name of the group inside one. The tab widget keeps a
; pointer to its text, which points straight at the name in tab_names here (no copy, so a name may be longer than 7
; characters). r5 = MENU_STATE.
menu_tab_text:
    push {lr}
    ldr r0, [r5, #M_TABW]
    cmp r0, #0
    bne menu_tab_go
    pop {pc}
menu_tab_go:
    ldr r2, [r5, #M_LEVEL]
    mov r3, #0
    cmp r2, #2
    ldreq r3, [r5, #M_GROUP]
    addeq r3, r3, #1
    ldr r1, =tab_names
    ldr r1, [r1, r3, lsl #2]
    cmp r2, #M_LEVEL_PLUGIN     ; the pages of one plugin stay under Plugins
    ldreq r1, =str_tab_plugins
    cmp r2, #M_LEVEL_SYNC       ; SYNC GROUP is a page of the pattern: its tab says so
    ldreq r1, =str_tab_pattern
    ldr r0, [r5, #M_TABW]
    str r1, [r0, #0x38]
    pop {pc}
.pool

menu_texts_fill:
    push {r4, r5, r6, r7, lr}
    ldr r5, =MENU_STATE
    mov r1, #0
    mov r2, #23
menu_texts_clear:
    add r3, r5, #M_TITLE
    str r1, [r3, r2, lsl #2]
    subs r2, r2, #1
    bpl menu_texts_clear
    bl menu_kind
    mov r7, r1
    cmp r0, #0
    beq menu_text_run
    cmp r0, #1
    beq menu_text_mfx
    cmp r0, #2
    beq menu_text_script
    cmp r0, #3
    beq menu_text_export
    cmp r0, #6
    beq menu_text_item
    cmp r0, #15
    beq menu_text_app
    cmp r0, #16
    beq menu_text_group
    cmp r0, #17
    beq menu_text_ring
    cmp r0, #18
    beq menu_text_pc
    cmp r0, #19
    beq menu_text_done
    cmp r0, #20
    beq menu_text_tm
    cmp r0, #21
    beq menu_text_na
    cmp r0, #22
    beq menu_text_splash
    cmp r0, #23
    beq menu_text_splash
    cmp r0, #24
    beq menu_text_colour
    cmp r0, #25
    beq menu_text_colour
    cmp r0, #26
    beq menu_text_intens
    cmp r0, #27
    beq menu_text_save
    sub r1, r0, #28
    cmp r1, #3
    bls menu_text_meter
    cmp r0, #32
    beq menu_text_over
    cmp r0, #33
    beq menu_text_mg
    cmp r0, #34
    beq menu_text_ledsave
    cmp r0, #35
    beq menu_text_splash
    cmp r0, #36
    beq menu_text_psel
    cmp r0, #37
    beq menu_text_pdel
    cmp r0, #38
    beq menu_text_pedit
    cmp r0, #39
    beq menu_text_pdesc
    cmp r0, #40
    beq menu_text_ip
    cmp r0, #41
    beq menu_text_version
    cmp r0, #7
    bhs menu_text_look
    pop {r4, r5, r6, r7, pc}
; VERSION: the set's version text (the patch blech-version) as the title, the firmware this runtime is built for as the value
menu_text_version:
    add r0, r5, #M_TITLE
    ldr r1, =VERSION_TEXT
    ldrb r2, [r1]
    cmp r2, #0xFF
    ldreq r1, =str_blech
    bl menu_copy16
    ldr r1, =base_names
    ldr r1, [r1, #BUILD_BASE]
    add r0, r5, #M_VALUE
    bl menu_copy
    pop {r4, r5, r6, r7, pc}
; the page BLECH in the ring and the groups of the list look like Data Util: the name as the title, "press  [ Enter ]" under it
menu_text_ring:
    add r0, r5, #M_TITLE
    ldr r1, =str_blech
    bl menu_copy
    b menu_text_press
menu_text_group:
    ldr r1, =group_names
    ldr r1, [r1, r7, lsl #2]
    add r0, r5, #M_TITLE
    bl menu_copy
menu_text_press:
    add r0, r5, #M_LINE3
    ldr r1, =str_press
    bl menu_copy
    pop {r4, r5, r6, r7, pc}
menu_text_export:
    add r0, r5, #M_TITLE
    ldr r1, =str_export
    bl menu_copy
    ldr r1, [r5, #M_STATUS]
    cmp r1, #0
    bne menu_text_status_value
    b menu_text_press
; PLUGIN EDIT, built like SAMPLE EDIT: "press [ Enter ]", or what ENTER (No Plugin) or DELETE PLUGIN said
menu_text_pedit:
    add r0, r5, #M_TITLE
    ldr r1, =str_pedit
    bl menu_copy
    ldr r1, [r5, #M_STATUS]
    cmp r1, #0
    bne menu_text_status_value
    b menu_text_press
; SELECT PLUGIN: its name; the dial chooses the plugin the next pages are about (as SELECT SAMPLE)
menu_text_psel:
    add r0, r5, #M_TITLE
    ldr r1, =str_psel
    bl menu_copy
    mov r0, r7
    bl menu_psel_name
    add r0, r5, #M_VALUE
    bl menu_copy16
    pop {r4, r5, r6, r7, pc}
; DESCRIPTION: the description of the plugin, from the file behind its block, drawn as a picture (menu_desc_frame); the value line
; under it is the plugin's state, or what went wrong reading the file. The dial scrolls.
menu_text_pdesc:
    ldr r0, [r5, #M_LISTED]
    cmp r0, #2
    blne menu_desc_load
    mov r0, r7
    bl menu_entry
    bl menu_state_text
    add r0, r5, #M_VALUE
    bl menu_copy
    ldr r1, [r5, #M_STATUS]
    cmp r1, #0
    bne menu_text_status
    pop {r4, r5, r6, r7, pc}
; DELETE PLUGIN: "press [ Enter ]"; the first ENTER asks, the second deletes (menu_delete)
menu_text_pdel:
    add r0, r5, #M_TITLE
    ldr r1, =str_pdel
    bl menu_copy
    ldr r1, [r5, #M_STATUS]
    cmp r1, #0
    bne menu_text_status_value
    b menu_text_press
menu_text_item:
    ldr r6, =MENU_ITEMS
    add r6, r6, r7, lsl #5
    add r6, r6, r7, lsl #3
    mov r0, #0
    bl menu_title_prefix
    add r1, r6, #20
    bl menu_copy16
    ldr r1, [r6, #12]
    add r0, r5, #M_VALUE
    bl menu_dec
    pop {r4, r5, r6, r7, pc}
menu_text_app:
    ldr r1, =APP_STATE
    add r6, r1, #SCRIPT_APPS_TABLE
    add r6, r6, r7, lsl #3
    add r6, r6, r7, lsl #2
    ldr r0, [r6, #SCRIPT_APP_GROUP]
    add r0, r0, #1
    bl menu_title_prefix
    ldr r1, [r6, #SCRIPT_APP_NAME]
    bl menu_copy16
    ldr r6, [r6]
    ldr r2, [r6, #SCRIPT_ENTRY_STATE]
    cmp r2, #SCRIPT_STATE_ARMED
    beq menu_text_press
    ldr r1, =str_off
    cmp r2, #SCRIPT_STATE_LOADED
    ldrne r1, =str_fault
menu_text_app_value:
    add r0, r5, #M_VALUE
    bl menu_copy
    pop {r4, r5, r6, r7, pc}
menu_text_script:
    mov r0, r7
    bl menu_entry
    movs r6, r0
    beq menu_text_script_off
    mov r0, #0
    bl menu_title_prefix
    ldr r1, =str_state          ; the plugin's name is on SELECT PLUGIN, the page before
    bl menu_copy16
    ldr r2, [r6, #SCRIPT_ENTRY_STATE]
    cmp r2, #SCRIPT_STATE_DISABLED
    beq menu_text_script_fault
    ldr r1, =str_on
    cmp r2, #SCRIPT_STATE_ARMED
    beq menu_text_script_value
    mov r0, r6
    bl menu_needs_confirm
    cmp r0, #0
    ldrne r1, =str_allow
    ldreq r1, =str_off
menu_text_script_value:
    add r0, r5, #M_VALUE
    bl menu_copy
    b menu_text_script_status
menu_text_script_off:           ; not loaded: OFF, as a plugin that is switched off; the dial up loads and starts it
    mov r0, #0
    bl menu_title_prefix
    ldr r1, =str_state
    bl menu_copy16
    ldr r1, =str_off
    b menu_text_script_value
menu_text_script_fault:
    ldr r0, [r6, #SCRIPT_ENTRY_FAULT]
    cmp r0, #SCRIPT_ERROR_COUNT
    movhs r0, #0
    ldr r1, =SCRIPT_ERROR_NAMES
    add r1, r1, r0, lsl #4
    add r0, r5, #M_VALUE
    bl menu_copy16
    ldr r1, =str_line
    bl menu_copy
    ldr r1, [r6, #SCRIPT_ENTRY_LINE]
    cmp r1, #1000
    movhs r1, #0
    bl menu_dec
menu_text_script_status:
    ldr r1, [r5, #M_STATUS]
    cmp r1, #0
    bne menu_text_status
    b menu_text_done
; the pages of the group CUSTOMIZATION, r0 = kind 7 to 13
menu_text_look:
    mov r6, r0
    mov r0, #3
    bl menu_title_prefix
    cmp r6, #7
    beq menu_text_ledmode
    cmp r6, #14
    beq menu_text_invert
    sub r6, r6, #8
    ldr r1, =look_titles
    ldr r1, [r1, r6, lsl #2]
    bl menu_copy
    cmp r6, #3
    addlo r2, r5, #M_LED_R
    addhs r2, r5, #M_BL_R
    ldr r1, [r2]
    ldr r3, [r2, #4]
    orr r1, r1, r3
    ldr r3, [r2, #8]
    orrs r1, r1, r3
    moveq r7, #1
    movne r7, #0
    cmp r7, #0
    beq menu_text_look_hsv
    add r0, r5, #M_VALUE
    ldr r1, =str_stock_word
    bl menu_copy
    b menu_text_look_line3
menu_text_look_hsv:             ; the colour as hue (0 to 95), saturation and brightness (0 to 15); the stored values stay red, green, blue
    cmp r6, #3
    addlo r0, r5, #M_LED_R
    addhs r0, r5, #M_BL_R
    bl look_hsv_get
    cmp r6, #3
    subhs r3, r6, #3
    movlo r3, r6
    cmp r3, #0
    moveq r1, r0
    cmp r3, #2
    moveq r1, r2
    add r0, r5, #M_VALUE
    bl menu_dec
    b menu_text_look_line3
; INTENSITY (26) and SAVE LIGHT (27, 0 is the firmware's dim: STOCK)
menu_text_intens:
    add r0, r5, #M_TITLE
    ldr r1, =str_intens
    bl menu_copy
    ldrb r1, [r5, #MX_INTENS]
    add r0, r5, #M_VALUE
    bl menu_dec
    b menu_text_look_line3
menu_text_save:
    add r0, r5, #M_TITLE
    ldr r1, =str_save
    bl menu_copy
    ldrb r1, [r5, #MX_SAVE]
    add r0, r5, #M_VALUE
    cmp r1, #0
    ldreq r1, =str_stock_word
    bleq menu_copy
    blne menu_dec
    b menu_text_look_line3
; LED DIMMING (34): how much power save dims the LEDs, 0 (not at all) to 100 percent (off), from the patch pad-colors
menu_text_ledsave:
    add r0, r5, #M_TITLE
    ldr r1, =str_led_dim
    bl menu_copy
    mov r1, #28
    bl menu_pc_call
    bl led_dim_index
    ldr r1, =led_dim_percent
    ldrb r1, [r1, r0]
    add r0, r5, #M_VALUE
    bl menu_dec
    ldr r1, =str_percent
    bl menu_copy
    b menu_text_look_line3
; r0 = the step pad_colors.py keeps (0 is 75 percent) -> r0 = its place in led_dim_percent. Clobbers nothing else.
led_dim_index:
    add r0, r0, #8
    cmp r0, #12
    subhs r0, r0, #12
    bx lr
; METER STILL, LOW, MID, LOUD (28 to 31): the zone's colour from the palette, STOCK the firmware's. r1 = the zone.
menu_text_meter:
    mov r6, r1
    add r0, r5, #M_TITLE
    ldr r1, =meter_titles
    ldr r1, [r1, r6, lsl #2]
    bl menu_copy
    sub r1, r5, #-MX_METER
    ldrb r1, [r1, r6]
    ldr r2, =colour_names
    ldr r1, [r2, r1, lsl #2]
    add r0, r5, #M_VALUE
    bl menu_copy
    b menu_text_look_line3
; OVERLAP (32): the colour of a pad that is both lit and selected, from the patch pad-colors
menu_text_over:
    add r0, r5, #M_TITLE
    ldr r1, =str_over
    bl menu_copy
    mov r1, #20
    bl menu_pc_call
    ldr r2, =over_names
    ldr r1, [r2, r0, lsl #2]
    add r0, r5, #M_VALUE
    bl menu_copy
    b menu_text_look_line3
menu_text_invert:
    ldr r1, =str_invert
    bl menu_copy
    ldr r2, [r5, #M_INV]
    ldr r1, =str_off
    cmp r2, #0
    ldrne r1, =str_on
    add r0, r5, #M_VALUE
    bl menu_copy
    b menu_text_look_line3
; PAD COLOR (24) and SELECT COLOR (25): title and value come from the patch pad-colors
menu_text_colour:
    mov r1, #12
    bl menu_pc_call
    mov r6, r1
    mov r1, r0
    add r0, r5, #M_TITLE
    bl menu_copy
    mov r1, r6
    add r0, r5, #M_VALUE
    bl menu_copy
    b menu_text_look_line3

; r0, r2 arguments, r1 = offset of the entry of the patch pad-colors -> what it returns (r0, r1); 0 where the set has no such patch.
menu_pc_call:
    ldr r12, =PC_CODE
    ldr r3, [r12]
    cmn r3, #1
    moveq r0, #0
    bxeq lr
    add r12, r12, r1
    mov r1, r2
    bx r12

; SPLASH IMPORT (22): ENTER reads KORG/blechtribe/splash.bmp into the start image; SPLASH DRAW (23): ENTER opens the editor;
; SPLASH RESET (35): ENTER drops the stored image, the start image of the firmware comes back
menu_text_splash:
    mov r6, r0
    mov r0, #3
    bl menu_title_prefix
    cmp r6, #22
    ldreq r1, =str_splash_import
    cmp r6, #23
    ldreq r1, =str_splash_draw
    cmp r6, #35
    ldreq r1, =str_splash_reset
    bl menu_copy
    ldr r1, [r5, #M_STATUS]
    cmp r1, #0
    bne menu_text_status_value
    b menu_text_press

; PATTERN CONFIRM: whether the pattern change waits for a second press (the patch pattern-switch reads the word PS_SETTING)
menu_text_pc:
    mov r0, #3
    bl menu_title_prefix
    ldr r1, =str_pc
    bl menu_copy
    ldr r2, [r5, #M_PC]
    ldr r1, =str_off
    cmp r2, #0
    ldrne r1, =str_on
    add r0, r5, #M_VALUE
    bl menu_copy
    b menu_text_look_line3
; TAP MOTION: whether TAP switches the recorded motion (the patch tap-motion reads the word TM_SETTING)
menu_text_tm:
    mov r0, #3
    bl menu_title_prefix
    ldr r1, =str_tm
    bl menu_copy
    ldr r2, [r5, #M_TM]
    ldr r1, =str_off
    cmp r2, #0
    ldrne r1, =str_on
    cmp r2, #2
    ldreq r1, =str_once
    add r0, r5, #M_VALUE
    bl menu_copy
    b menu_text_look_line3
; NOTE ASSIST: whether the pads show the notes that fit (the patch note-assistant reads the word NA_SETTING)
menu_text_na:
    mov r0, #3
    bl menu_title_prefix
    ldr r1, =str_na
    bl menu_copy
    ldr r2, [r5, #M_NA]
    ldr r1, =str_off
    cmp r2, #0
    ldrne r1, =str_on
    add r0, r5, #M_VALUE
    bl menu_copy
    b menu_text_look_line3
; SYNC GROUP: the group of the pattern in RAM (the patch pattern-switch), OFF for 0; saved with the pattern
menu_text_mg:
    mov r0, #3
    bl menu_title_prefix
    ldr r1, =str_mg
    bl menu_copy
    bl menu_mg_at
    add r0, r5, #M_VALUE
    movs r1, r3
    ldreq r1, =str_off
    beq menu_text_app_value
    bl menu_dec
    b menu_text_look_line3
menu_text_ledmode:
    ldr r1, =str_ledmode
    bl menu_copy
    ldr r2, [r5, #M_LED_MODE]
    ldr r1, =str_meter
    cmp r2, #1
    ldreq r1, =str_color
    cmp r2, #2
    ldreq r1, =str_off
    add r0, r5, #M_VALUE
    bl menu_copy
menu_text_look_line3:
    ldr r1, [r5, #M_STATUS]
    cmp r1, #0
    bne menu_text_status
    pop {r4, r5, r6, r7, pc}
menu_text_run:
    mov r0, #0
    bl menu_title_prefix
    ldr r1, =str_runtime
    bl menu_copy
    ldr r6, [r5, #M_SET_RUN]
    ldr r4, [r5, #M_EFF_RUN]
    b menu_text_onoff
menu_text_mfx:
    add r0, r5, #M_TITLE
    ldr r1, =str_mfx
    bl menu_copy
    ldr r6, [r5, #M_SET_MFX]
    ldr r4, [r5, #M_EFF_MFX]
menu_text_onoff:
    add r0, r5, #M_VALUE
    ldr r1, =str_off
    cmp r6, #0
    ldrne r1, =str_on
    bl menu_copy
    ldr r1, [r5, #M_STATUS]
    cmp r1, #0
    bne menu_text_status
    cmp r6, #0
    movne r6, #1
    cmp r4, #0
    movne r4, #1
    cmp r6, r4
    beq menu_text_done
    add r0, r5, #M_VALUE
    ldr r1, =str_on_restart
    cmp r6, #0
    ldreq r1, =str_off_restart
    bl menu_copy
menu_text_done:
    pop {r4, r5, r6, r7, pc}
; r1 = status: in the third line (beside a short value), or as the value itself where the value is long
menu_text_status:
menu_text_status_value:
    add r0, r5, #M_VALUE
    cmp r1, #1
    ldreq r1, =str_saved
    beq menu_text_status_go
    cmp r1, #2
    bne menu_text_status_more
    ldr r1, [r5, #M_NSCRIPTS]
    bl menu_dec
    ldr r1, =str_exported
    bl menu_copy
    pop {r4, r5, r6, r7, pc}
menu_text_status_more:
    cmp r1, #0x30
    ldreq r1, =str_nothing
    beq menu_text_status_go
    cmp r1, #0x31
    ldreq r1, =str_no_files
    beq menu_text_status_go
    cmp r1, #0x32
    ldreq r1, =str_runtime_off
    beq menu_text_status_go
    cmp r1, #0x33
    ldreq r1, =str_not_script
    beq menu_text_status_go
    cmp r1, #0x34
    ldreq r1, =str_rejected
    beq menu_text_status_go
    cmp r1, #0x35
    ldreq r1, =str_duplicate
    beq menu_text_status_go
    cmp r1, #0x36
    ldreq r1, =str_pool_full
    beq menu_text_status_go
    cmp r1, #0x37
    ldreq r1, =str_apps_full
    beq menu_text_status_go
    cmp r1, #0x38
    ldreq r1, =str_noplugin
    beq menu_text_status_go
    cmp r1, #0x23
    ldreq r1, =str_nocard
    beq menu_text_status_go
    cmp r1, #0x21
    ldreq r1, =str_nocard
    beq menu_text_status_go
    cmp r1, #0x2C
    ldreq r1, =str_nocard
    beq menu_text_status_go
    cmp r1, #0x2A
    ldreq r1, =str_protected
    beq menu_text_status_go
    cmp r1, #0x24
    ldreq r1, =str_nofolder
    beq menu_text_status_go
    cmp r1, #0x40
    ldreq r1, =str_splash_saved
    beq menu_text_status_go
    cmp r1, #0x41
    ldreq r1, =str_splash_nofile
    beq menu_text_status_go
    cmp r1, #0x42
    ldreq r1, =str_splash_format
    beq menu_text_status_go
    cmp r1, #0x44
    ldreq r1, =str_splash_reset_done
    beq menu_text_status_go
    cmp r1, #0x25
    ldreq r1, =str_nofolder
    beq menu_text_status_go
    cmp r1, #0x50
    ldreq r1, =str_pdel_sure
    beq menu_text_status_go
    cmp r1, #0x51
    ldreq r1, =str_pdeleted
    beq menu_text_status_go
    ldr r1, =str_writeerr
menu_text_status_go:
    bl menu_copy
    pop {r4, r5, r6, r7, pc}
.pool

; r0 = destination, r1 = signed value (magnitude below 100 million) -> r0 = the end of the digits (the terminator is written)
menu_dec:
    push {r4}
    cmp r1, #0
    bge menu_dec_pos
    mov r2, #0x2D
    strb r2, [r0], #1
    rsb r1, r1, #0
menu_dec_pos:
    ldr r3, =menu_powers
    mov r12, #0
menu_dec_loop:
    ldr r2, [r3], #4
    mov r4, #0
menu_dec_sub:
    cmp r1, r2
    blo menu_dec_digit
    sub r1, r1, r2
    add r4, r4, #1
    b menu_dec_sub
menu_dec_digit:
    cmp r4, #0
    bne menu_dec_emit
    cmp r12, #0
    bne menu_dec_emit
    cmp r2, #1
    bne menu_dec_next
menu_dec_emit:
    add r4, r4, #0x30
    strb r4, [r0], #1
    mov r12, #1
menu_dec_next:
    cmp r2, #1
    bne menu_dec_loop
    mov r2, #0
    strb r2, [r0]
    pop {r4}
    bx lr
menu_powers:
    .word 10000000, 1000000, 100000, 10000, 1000, 100, 10, 1
.pool

; ---- korg.menu.add(label, min, max, value): r0 = label text, r1 = min, r2 = max, r3 = value
; -> r0 = the page's id (its place in the item table), -1 when all MENU_ITEMS_MAX places are taken, r1 = error code.
; The same label from the same script is the same page.
script_menu_add_glue:
    push {r4-r9, lr}
    cmp r1, r2
    bgt menu_add_bad
    mov r4, r0
    mov r8, r1
    mov r9, r2
    ldr r5, =HOOK_RUNTIME
    ldr r5, [r5, #RT_ENTRY]
    ldr r6, =MENU_ITEMS
    ldr r7, =MENU_STATE
    ldr r2, [r7, #M_ITEMS_N]
    mov r1, #0
menu_add_find:
    cmp r1, r2
    bhs menu_add_new
    add r12, r6, r1, lsl #5
    add r12, r12, r1, lsl #3
    ldr r0, [r12]
    cmp r0, r5
    bne menu_add_find_next
    push {r1, r2, r3}
    add r1, r12, #20
    mov r0, r4
    bl menu_streq
    mov r12, r0
    pop {r1, r2, r3}
    cmp r12, #0
    movne r0, r1
    bne menu_add_done
menu_add_find_next:
    add r1, r1, #1
    b menu_add_find
menu_add_new:
    cmp r2, #MENU_ITEMS_MAX
    mvnhs r0, #0
    bhs menu_add_done
    cmp r3, r8
    movlt r3, r8
    cmp r3, r9
    movgt r3, r9
    add r12, r6, r2, lsl #5
    add r12, r12, r2, lsl #3
    str r5, [r12]
    str r8, [r12, #4]
    str r9, [r12, #8]
    str r3, [r12, #12]
    mov r0, #0
    str r0, [r12, #16]
    add r0, r12, #20
    mov r1, r4
    push {r2}
    bl menu_copy16
    pop {r2}
    add r0, r2, #1
    str r0, [r7, #M_ITEMS_N]
    push {r2}
    bl menu_recount
    pop {r2}
    mov r0, r2
menu_add_done:
    mov r1, #ERR_OK
    pop {r4-r9, pc}
menu_add_bad:
    mov r0, #0
    mov r1, #ERR_API_ARG
    pop {r4-r9, pc}
.pool

; r0, r1 = two zero-terminated texts -> r0 = 1 when they are equal in their first 15 characters
menu_streq:
    mov r3, #15
menu_streq_loop:
    ldrb r2, [r0], #1
    ldrb r12, [r1], #1
    cmp r2, r12
    movne r0, #0
    bxne lr
    cmp r2, #0
    moveq r0, #1
    bxeq lr
    subs r3, r3, #1
    bne menu_streq_loop
    mov r0, #1
    bx lr


; r0 = script entry -> r0 = 1 when the block was not probed in the editor and the user has not allowed it yet
menu_needs_confirm:
    ldr r1, [r0, #SCRIPT_ENTRY_BLOB]
    ldrb r2, [r1, #HDR_FLAGS]
    tst r2, #BLOCK_PROBED
    movne r0, #0
    bxne lr
    ldr r2, =MENU_STATE
    ldr r3, [r2, #M_ON]
    cmp r3, #1
    movne r0, #1
    bxne lr
    ldr r1, [r1, #HDR_CHECKSUM]
    ldr r3, [r2, #M_TRUST_N]
    add r2, r2, #M_TRUST
menu_needs_loop:
    cmp r3, #0
    moveq r0, #1
    bxeq lr
    ldr r12, [r2], #4
    cmp r12, r1
    moveq r0, #0
    bxeq lr
    sub r3, r3, #1
    b menu_needs_loop
.pool

; Plugins switched off stay off over a restart: the checksum list of the settings file holds, beside the checksums of the
; foreign plugins the user allowed, the inverted checksum (mvn) of every plugin that is off. The file format stays as it was
; (an older BLECH reads them as allowed checksums that match nothing). The loader does not start a plugin marked so.
; r0 = script entry -> r0 = 1 when the settings keep it off
menu_is_off:
    ldr r1, [r0, #SCRIPT_ENTRY_BLOB]
    ldr r1, [r1, #HDR_CHECKSUM]
    mvn r1, r1
    ldr r2, =MENU_STATE
    ldr r3, [r2, #M_ON]
    cmp r3, #1
    movne r0, #0
    bxne lr
    ldr r3, [r2, #M_TRUST_N]
    add r2, r2, #M_TRUST
menu_off_loop:
    cmp r3, #0
    moveq r0, #0
    bxeq lr
    ldr r12, [r2], #4
    cmp r12, r1
    moveq r0, #1
    bxeq lr
    sub r3, r3, #1
    b menu_off_loop

; Before a save: for every loaded plugin the marker goes (every copy of it), and comes back when the plugin is off (loaded,
; allowed and not armed). Markers of plugins no longer on the card stay, like their allowed checksums, until the list is full:
; then the oldest of them makes room (menu_trust_room). Blechy is always armed, so he never gets one.
menu_off_sync:
    push {r4-r7, lr}
    ldr r4, =MENU_STATE
    ldr r5, =HOOK_RUNTIME
    ldr r5, [r5, #RT_HEAD]
    cmn r5, #1
    moveq r5, #0
menu_off_entry:
    cmp r5, #0
    beq menu_off_done
    ldr r6, [r5, #SCRIPT_ENTRY_BLOB]
    ldr r7, [r6, #HDR_CHECKSUM]
    mvn r7, r7
    ldr r1, [r4, #M_TRUST_N]
    add r2, r4, #M_TRUST
    mov r3, #0
menu_off_find:
    cmp r3, r1
    bhs menu_off_keep
    ldr r12, [r2, r3, lsl #2]
    cmp r12, r7
    addne r3, r3, #1
    bne menu_off_find
    sub r1, r1, #1
    str r1, [r4, #M_TRUST_N]
menu_off_shift:
    cmp r3, r1
    movhs r3, #0
    bhs menu_off_find
    add r12, r3, #1
    ldr r12, [r2, r12, lsl #2]
    str r12, [r2, r3, lsl #2]
    add r3, r3, #1
    b menu_off_shift
menu_off_keep:
    ldr r0, [r5, #SCRIPT_ENTRY_STATE]
    cmp r0, #SCRIPT_STATE_LOADED
    bne menu_off_next
    mov r0, r5
    bl menu_needs_confirm
    cmp r0, #0
    bne menu_off_next
    bl menu_trust_room
    cmp r0, #0
    beq menu_off_next
    ldr r1, [r4, #M_TRUST_N]
    add r2, r4, #M_TRUST
    str r7, [r2, r1, lsl #2]
    add r1, r1, #1
    str r1, [r4, #M_TRUST_N]
menu_off_next:
    ldr r5, [r5, #SCRIPT_ENTRY_NEXT]
    b menu_off_entry
menu_off_done:
    pop {r4-r7, pc}
.pool

; A full list drops its oldest entry that no loaded plugin uses (neither its checksum nor its marker): a plugin removed from
; the card, or an older build of one. -> r0 = 1 when the list has room for one more entry. Keeps r4 to r8.
menu_trust_room:
    push {r4-r8, lr}
    ldr r4, =MENU_STATE
    ldr r1, [r4, #M_TRUST_N]
    cmp r1, #MENU_MAX_TRUST
    movlo r0, #1
    poplo {r4-r8, pc}
    add r6, r4, #M_TRUST
    mov r7, #0
menu_room_scan:
    cmp r7, r1
    movhs r0, #0
    pophs {r4-r8, pc}
    ldr r8, [r6, r7, lsl #2]
    ldr r5, =HOOK_RUNTIME
    ldr r5, [r5, #RT_HEAD]
    cmn r5, #1
    moveq r5, #0
menu_room_live:
    cmp r5, #0
    beq menu_room_drop
    ldr r0, [r5, #SCRIPT_ENTRY_BLOB]
    ldr r0, [r0, #HDR_CHECKSUM]
    cmp r0, r8
    mvnne r0, r0
    cmpne r0, r8
    addeq r7, r7, #1
    beq menu_room_scan
    ldr r5, [r5, #SCRIPT_ENTRY_NEXT]
    b menu_room_live
menu_room_drop:
    sub r1, r1, #1
    str r1, [r4, #M_TRUST_N]
menu_room_shift:
    cmp r7, r1
    movhs r0, #1
    pophs {r4-r8, pc}
    add r12, r7, #1
    ldr r12, [r6, r12, lsl #2]
    str r12, [r6, r7, lsl #2]
    add r7, r7, #1
    b menu_room_shift
.pool

; r0 = script entry waiting for its confirmation: remember its checksum, run its start body, save the settings
menu_confirm:
    push {r4, r5, lr}
    mov r4, r0
    ldr r5, =MENU_STATE
    bl menu_trust_room
    ldr r1, [r4, #SCRIPT_ENTRY_BLOB]
    ldr r1, [r1, #HDR_CHECKSUM]
    ldr r2, [r5, #M_TRUST_N]
    cmp r2, #MENU_MAX_TRUST
    blo menu_confirm_add
    mov r2, #0
menu_confirm_shift:
    add r0, r5, #M_TRUST
    ldr r3, [r0, r2, lsl #2]
    sub r12, r2, #1
    cmp r2, #0
    strne r3, [r0, r12, lsl #2]
    add r2, r2, #1
    cmp r2, #MENU_MAX_TRUST
    blo menu_confirm_shift
    mov r2, #MENU_MAX_TRUST-1
menu_confirm_add:
    add r0, r5, #M_TRUST
    str r1, [r0, r2, lsl #2]
    add r2, r2, #1
    str r2, [r5, #M_TRUST_N]
    ldr r0, =HOOK_RUNTIME
    mov r1, r4
    mov r2, #EV_START
    ldr r3, =HOOK_INPUT
    ldr r12, =VM_SCRIPT_RUN_EVENT
    blx r12
    bl menu_settings_save
    pop {r4, r5, pc}
.pool

; The menu has three levels, the way Data Util has two. Level 0 is the one page BLECH in the ring of the firmware, between Global and
; Data Util ("press [ Enter ]"); ENTER opens level 1, the list of the groups FEATURES, CUSTOMIZATION and PLUGINS, and behind them the
; groups plugins add by declaring an app (korg.app): GAMES and TOOLS, each only when an app is declared in it, and last the page
; VERSION (the set's version and the firmware it is built for, no group). Each group is again
; "press [ Enter ]". ENTER on a group opens level 2, the pages of that group, M_GROUP (0 PLUGINS, 1 GAMES, 2 TOOLS, 3 CUSTOMIZATION,
; 4 FEATURES, 5 DISPLAY, 6 LED, 7 PAD COLOR, 8 POWER SAVE, 9 SPLASH). Those five are rows of CUSTOMIZATION that open their pages;
; EXIT there goes back to that row. FEATURES holds the built-in features with their switches: MFX 2, PATTERN CONFIRM, TAP MOTION and NOTE ASSIST (the
; main dial changes them, WRITE keeps them). EXIT goes one level up. M_PAGE counts within the level, the counter shows only that
; level. Level 3 (M_LEVEL_BLECHY) is no menu: it is a page of the ring, after Event, on which Blechy, the app built into
; BLECH, shows himself (the frame hook opens and closes him by this level). Level 4 (M_LEVEL_SYNC) is the page SYNC GROUP behind
; him, right before the Pattern menu: a setting of the pattern in RAM, saved with WRITE as the Pattern menu's pages.
; r0 = page -> r0 = kind (0 plugins runtime setting, 1 MFX 2 setting, 2 a plugin, 3 export, 4 and 5 unused, 6 a page a
; plugin added, 7 bottom LED mode, 8 LED red, 9 green, 10 blue, 11 backlight red, 12 green, 13 blue, 14 display invert, 15 an app,
; 16 a group in the list of level 1, 17 the page BLECH of level 0, 18 pattern confirm, 19 the page of Blechy, 20 TAP MOTION, 21 NOTE ASSIST, 33 SYNC GROUP of level 4,
; 36 SELECT PLUGIN, 37 DELETE PLUGIN, 38 PLUGIN EDIT, 39 DESCRIPTION, 40 INIT PATTERN, 41 VERSION), r1 = its index (the plugin, the page, the app's table index,
; the group). Keeps r4 to r8.
menu_kind:
    push {r4, r5, lr}
    ldr r4, =MENU_STATE
    ldr r2, [r4, #M_LEVEL]
    mov r5, r0
    cmp r2, #M_LEVEL_BLECHY
    moveq r0, #19
    moveq r1, #0
    beq menu_kind_done
    cmp r2, #M_LEVEL_SYNC
    moveq r0, #33
    moveq r1, #0
    beq menu_kind_done
    cmp r2, #M_LEVEL_PLUGIN
    beq menu_kind_plugin
    cmp r2, #0
    moveq r0, #17
    moveq r1, #0
    beq menu_kind_done
    cmp r2, #1
    bne menu_kind_group
    mov r0, #16
    cmp r5, #0
    moveq r1, #4
    beq menu_kind_done
    cmp r5, #1
    moveq r1, #3
    beq menu_kind_done
    cmp r5, #2
    moveq r1, #0
    beq menu_kind_done
    bl menu_page_count          ; VERSION is the last row of the list
    sub r0, r0, #1
    cmp r5, r0
    moveq r0, #41
    moveq r1, #0
    beq menu_kind_done
    sub r5, r5, #3
    mov r0, #0
    bl app_count
    cmp r0, #0
    beq menu_kind_no_games
    cmp r5, #0
    moveq r0, #16
    moveq r1, #1
    beq menu_kind_done
menu_kind_no_games:
    mov r0, #16
    mov r1, #2
    b menu_kind_done
menu_kind_group:
    ldr r3, [r4, #M_GROUP]
    cmp r3, #0
    beq menu_kind_plugins
    cmp r3, #4
    beq menu_kind_features
    cmp r3, #5                  ; DISPLAY, LED, PAD COLOR, POWER SAVE, SPLASH (5 to 9) and CUSTOMIZATION (3): the kinds of their pages from tables
    bhs menu_kind_sub
    cmp r3, #3
    bne menu_kind_apps
    ldr r1, =custom_kinds
    ldrb r0, [r1, r5]
    cmp r0, #16
    addeq r1, r5, #5            ; rows 0 to 4 open the groups 5 to 9
    movne r1, #0
    b menu_kind_done
menu_kind_sub:
    ldr r1, =sub_kinds
    sub r3, r3, #5
    add r1, r1, r3, lsl #3
    ldrb r0, [r1, r5]
    mov r1, #0
    b menu_kind_done
menu_kind_features:
    mov r0, #21
    mov r1, #0
    cmp r5, #4
    moveq r0, #40
    cmp r5, #2
    moveq r0, #20
    cmp r5, #1
    moveq r0, #18
    cmp r5, #0
    moveq r0, #1
    b menu_kind_done
menu_kind_apps:
    cmp r3, #2
    bne menu_kind_nth
    mov r0, #0
    bl app_count
    add r5, r5, r0
menu_kind_nth:
    mov r1, r5
    bl app_nth
    mov r0, #15
    b menu_kind_done
menu_kind_plugins:              ; RUNTIME, PLUGIN EDIT, EXPORT
    mov r1, #0
    cmp r5, #1
    movlo r0, #0
    moveq r0, #38
    cmp r5, #2
    moveq r0, #3
    b menu_kind_done
menu_kind_plugin:               ; SELECT PLUGIN, STATE, DESCRIPTION, the pages the plugin added (korg.menu.add), DELETE PLUGIN
    ldrb r0, [r4, #M_PSEL]
    mov r1, r0
    cmp r5, #1
    movlo r0, #36
    blo menu_kind_done
    moveq r0, #2
    beq menu_kind_done
    cmp r5, #2
    moveq r0, #39
    beq menu_kind_done
    bl menu_entry
    sub r1, r5, #3
    bl menu_item_nth
    cmp r0, #0
    movge r1, r0
    movge r0, #6
    bge menu_kind_done
    ldrb r1, [r4, #M_PSEL]
    mov r0, #37
menu_kind_done:
    pop {r4, r5, pc}
.pool

; -> r0 = how many pages the current level has. Keeps r4 to r8.
menu_page_count:
    push {r4, lr}
    ldr r4, =MENU_STATE
    ldr r1, [r4, #M_LEVEL]
    cmp r1, #M_LEVEL_PLUGIN
    beq menu_count_plugin
    cmp r1, #M_LEVEL_BLECHY
    cmpne r1, #M_LEVEL_SYNC
    cmpne r1, #0
    bne menu_count_level1
    mov r0, #1
    pop {r4, pc}
menu_count_level1:
    cmp r1, #1
    bne menu_count_group
    mov r4, #4                  ; FEATURES, CUSTOMIZATION, PLUGINS, VERSION, and GAMES and TOOLS where an app is declared in them
    mov r0, #0
    bl app_count
    cmp r0, #0
    addne r4, r4, #1
    mov r0, #1
    bl app_count
    cmp r0, #0
    addne r4, r4, #1
    mov r0, r4
    pop {r4, pc}
menu_count_group:
    ldr r1, [r4, #M_GROUP]
    cmp r1, #0
    beq menu_count_plugins
    cmp r1, #3
    bne menu_count_features
    mov r0, #2                  ; DISPLAY and LED
    ldr r1, =PC_CODE
    ldr r1, [r1]
    cmn r1, #1
    beq menu_count_out          ; without the pad colours there is no PAD COLOR and no splash page (the splash editor comes with them)
    add r0, r0, #2              ; PAD COLOR and POWER SAVE (its LED DIMMING is in the pad colours patch)
    ldr r1, =SPLASH_IMPORT
    ldr r1, [r1]
    cmn r1, #1
    addne r0, r0, #1            ; SPLASH (IMPORT, DRAW and RESET), where the build has the splash editor
    b menu_count_out
menu_count_features:
    cmp r1, #5
    blo menu_count_list
    ldr r0, =sub_counts
    sub r1, r1, #5
    ldrb r0, [r0, r1]
    b menu_count_out
menu_count_list:
    cmp r1, #3
    bls menu_count_apps
    mov r0, #4                  ; FEATURES: the four switches, and INIT PATTERN where the set has the patch init-pattern
    ldr r1, =INIT_CODE
    ldr r1, [r1]
    cmn r1, #1
    addne r0, r0, #1
    b menu_count_out
menu_count_apps:
    sub r0, r1, #1
    bl app_count
menu_count_out:
    pop {r4, pc}
menu_count_plugins:
    mov r0, #3
    pop {r4, pc}
menu_count_plugin:              ; a plugin that is not loaded has SELECT PLUGIN, STATE and DESCRIPTION only
    ldrb r0, [r4, #M_PSEL]
    bl menu_entry
    cmp r0, #0
    moveq r0, #3
    popeq {r4, pc}
    mvn r1, #0
    bl menu_item_nth
    add r0, r1, #4
    pop {r4, pc}
.pool

; Called by the constructor: the page M_ENTER (-1 is the last one) within the current level becomes M_PAGE. Clobbers r0 to r3.
menu_enter_page:
    push {lr}
    ldr r3, =MENU_STATE
    mov r0, #0
    str r0, [r3, #M_LISTED]
    bl menu_page_count
    ldr r3, =MENU_STATE
    ldr r1, [r3, #M_ENTER]
    cmp r1, r0
    movhs r1, r0
    subhs r1, r1, #1
    cmp r1, #0
    movlt r1, #0
    str r1, [r3, #M_PAGE]
    pop {pc}
.pool

; -> r1 = the counter's index, r2 = its total, for the page counter. On level 0 it is the place in the ring of the firmware (27 of
; 31, the counter shows the index plus one), on levels 3 (Blechy) and 4 (SYNC GROUP) the places behind it, the last ones, below it
; the page within the level. Sets M_RAW so the counter hooks leave the
; numbers alone. Clobbers r0 to r3.
menu_counter_args:
    push {lr}
    ldr r3, =MENU_STATE
    mov r1, #1
    str r1, [r3, #M_RAW]
    ldr r1, [r3, #M_LEVEL]
    cmp r1, #M_LEVEL_BLECHY
    cmpne r1, #M_LEVEL_SYNC
    beq menu_counter_last
    cmp r1, #0
    bne menu_counter_level
    ldr r2, [r3, #M_COUNT]
    add r2, r2, #MENU_RING_TOTAL+MENU_RING_TAIL
    mov r1, #MENU_RING_FIRST
    pop {pc}
menu_counter_last:
    ldr r2, [r3, #M_COUNT]
    add r2, r2, #MENU_RING_TOTAL+MENU_RING_TAIL
    sub r1, r1, #M_LEVEL_BLECHY+MENU_RING_TAIL
    add r1, r2, r1
    pop {pc}
menu_counter_level:
    bl menu_page_count
    mov r2, r0
    ldr r3, =MENU_STATE
    ldr r1, [r3, #M_PAGE]
    pop {pc}
.pool

; r0 = the group to go into (on level 1), r1 = the screen object: ENTER on level 0 opens the list, on level 1 the group. Shows the first page.
menu_go_in:
    push {r4, lr}
    mov r4, r1
    ldr r2, =MENU_STATE
    ldr r3, [r2, #M_LEVEL]
    cmp r3, #0
    bne menu_go_group
    mov r3, #1
    str r3, [r2, #M_LEVEL]
    ldr r0, [r2, #M_TOP]        ; the list opens on the group it was last left from (device 18.10.)
    b menu_go_page
menu_go_group:
    cmp r3, #2                  ; COLORS inside CUSTOMIZATION: only the group changes, M_TOP keeps the list's page
    beq menu_go_sub
    ldr r3, [r2, #M_PAGE]
    str r3, [r2, #M_TOP]
    mov r3, #2
    str r3, [r2, #M_LEVEL]
menu_go_sub:
    str r0, [r2, #M_GROUP]
    mov r0, #0
menu_go_page:
    str r0, [r2, #M_PAGE]
    str r0, [r2, #M_ENTER]
    mov r3, #0
    str r3, [r2, #M_STATUS]
    str r3, [r2, #M_LISTED]
    mov r0, r4
    bl menu_show
    pop {r4, pc}
.pool

; r0 = index -> r0 = the script entry, 0 when there is none. Blechy (his block lies outside the pool) is no page and not counted.
menu_entry:
    ldr r1, =HOOK_RUNTIME
    ldr r1, [r1, #RT_HEAD]
    cmn r1, #1
    moveq r1, #0
menu_entry_loop:
    cmp r1, #0
    moveq r0, #0
    bxeq lr
    ldr r2, [r1, #SCRIPT_ENTRY_BLOB]
    ldr r3, =HOOK_POOL
    cmp r2, r3
    blo menu_entry_next
    ldrb r3, [r2, #HDR_FLAGS+1]
    tst r3, #BLOCK_DELETED_HI
    bne menu_entry_next
    cmp r0, #0
    moveq r0, r1
    bxeq lr
    sub r0, r0, #1
menu_entry_next:
    ldr r1, [r1, #SCRIPT_ENTRY_NEXT]
    b menu_entry_loop
.pool

; r0 = script entry, r1 = n -> r0 = the index in MENU_ITEMS of the n-th page it added (korg.menu.add), -1 when it added fewer;
; r1 = how many it added. Clobbers r2, r3 and r12.
menu_item_nth:
    push {r4, r5, r6}
    ldr r2, =MENU_STATE
    ldr r2, [r2, #M_ITEMS_N]
    ldr r3, =MENU_ITEMS
    mov r12, #0
    mov r4, #0
    mvn r5, #0
menu_item_nth_loop:
    cmp r12, r2
    bhs menu_item_nth_done
    ldr r6, [r3], #40
    cmp r6, r0
    bne menu_item_nth_next
    cmp r4, r1
    moveq r5, r12
    add r4, r4, #1
menu_item_nth_next:
    add r12, r12, #1
    b menu_item_nth_loop
menu_item_nth_done:
    mov r0, r5
    mov r1, r4
    pop {r4, r5, r6}
    bx lr
.pool

; r0 = script entry: DELETE PLUGIN. A plugin that runs stops (as with STATE OFF), its block is marked in RAM so the lists and EXPORT
; leave it out, and e2sPlugin.all is written again without it, also when none is left; the block stays in the pool until the next
; start. Back on PLUGIN EDIT, which shows the result. Clobbers r0 to r3 and r12.
menu_delete:
    push {r4, lr}
    ldr r1, [r0, #SCRIPT_ENTRY_STATE]
    cmp r1, #SCRIPT_STATE_ARMED
    moveq r1, #SCRIPT_STATE_LOADED
    streq r1, [r0, #SCRIPT_ENTRY_STATE]
    ldr r1, [r0, #SCRIPT_ENTRY_BLOB]
    ldrb r2, [r1, #HDR_FLAGS+1]
    orr r2, r2, #BLOCK_DELETED_HI
    strb r2, [r1, #HDR_FLAGS+1]
    mov r0, #1
    bl menu_export
    bl menu_recount
    ldr r4, =MENU_STATE
    ldr r0, [r4, #M_STATUS]
    cmp r0, #2
    moveq r0, #0x51
    str r0, [r4, #M_STATUS]
    mov r0, #0
    strb r0, [r4, #M_PSEL]
    mov r0, #2
    str r0, [r4, #M_LEVEL]
    mov r0, #1
    str r0, [r4, #M_PAGE]
    str r0, [r4, #M_ENTER]
    pop {r4, pc}
.pool

; Counts the loaded scripts (not Blechy, whose block lies outside the pool, nor a deleted one) and sets the number of pages. Runs after the loader and after an import.
menu_recount:
    ldr r2, =MENU_STATE
    ldr r0, [r2, #M_ON]
    cmp r0, #1
    bxne lr
    ldr r0, =HOOK_RUNTIME
    ldr r0, [r0, #RT_HEAD]
    mov r1, #0
    cmn r0, #1
    moveq r0, #0
menu_recount_loop:
    cmp r0, #0
    beq menu_recount_done
    ldr r3, [r0, #SCRIPT_ENTRY_BLOB]
    ldr r12, =HOOK_POOL
    cmp r3, r12
    blo menu_recount_next
    ldrb r12, [r3, #HDR_FLAGS+1]
    tst r12, #BLOCK_DELETED_HI
    addeq r1, r1, #1
menu_recount_next:
    cmp r1, #MENU_MAX_SCRIPTS
    bhs menu_recount_done
    ldr r0, [r0, #SCRIPT_ENTRY_NEXT]
    b menu_recount_loop
menu_recount_done:
    str r1, [r2, #M_NSCRIPTS]
    mov r1, #1
    str r1, [r2, #M_COUNT]
    bx lr
.pool
menu_recount_end:

; Writes every loaded block as e2sPlugin.all in one pass (header, then the blocks as they sit in the pool), a deleted one left out.
; r0 = 1 writes the file also with no block (DELETE PLUGIN of the last one), 0 refuses that (EXPORT).
; Sets M_STATUS: 2 written, 0x30 nothing loaded, 0x20 + code of the failing FatFs call otherwise.
menu_export:
    push {r4-r11, lr}
    mov r11, r0
    ldr r4, =MENU_STATE
    ldr r5, =HOOK_CARD
    add r6, r5, #CARD_FIL
    ldr r7, =HOOK_RUNTIME
    ldr r7, [r7, #RT_HEAD]
    cmn r7, #1
    moveq r7, #0
    mov r8, #0
    mov r9, #ARCHIVE_HEADER_SIZE
    mvn r0, #0
    str r0, [r5, #CARD_CRC]
    mov r10, r7
menu_export_scan:
    cmp r10, #0
    beq menu_export_scanned
    ldr r0, [r10, #SCRIPT_ENTRY_BLOB]
    ldr r2, =HOOK_POOL
    cmp r0, r2
    blo menu_export_scan_next
    ldrb r1, [r0, #HDR_FLAGS+1]
    tst r1, #BLOCK_DELETED_HI
    bne menu_export_scan_next
    ldr r1, [r0, #HDR_TOTAL_SIZE]
    add r9, r9, r1
    add r8, r8, #1
    bl card_crc
menu_export_scan_next:
    ldr r10, [r10, #SCRIPT_ENTRY_NEXT]
    b menu_export_scan
menu_export_scanned:
    cmp r8, #0
    cmpeq r11, #0
    moveq r0, #0x30
    beq menu_export_status
    add r11, r4, #M_FILE_A
    ldr r0, =ARCHIVE_MAGIC
    str r0, [r11]
    mov r0, #ARCHIVE_VERSION
    strb r0, [r11, #4]
    mov r0, #0
    strb r0, [r11, #5]
    strb r8, [r11, #6]
    mov r0, r8, lsr #8
    strb r0, [r11, #7]
    str r9, [r11, #8]
    ldr r0, [r5, #CARD_CRC]
    mvn r0, r0
    str r0, [r11, #12]
    mov r0, r6
    ldr r1, =export_path
    bl card_create
    cmp r0, #0
    bne menu_export_fail
    mov r0, r6
    mov r1, r11
    mov r2, #ARCHIVE_HEADER_SIZE
    add r3, r5, #CARD_BR
    ldr r12, =FS_WRITE
    blx r12
    cmp r0, #0
    bne menu_export_close
    ldr r0, [r5, #CARD_BR]
    cmp r0, #ARCHIVE_HEADER_SIZE
    movne r0, #2
    bne menu_export_close
    mov r10, r7
menu_export_write:
    cmp r10, #0
    beq menu_export_done
    ldr r1, [r10, #SCRIPT_ENTRY_BLOB]
    ldr r2, =HOOK_POOL
    cmp r1, r2
    blo menu_export_write_next
    ldrb r2, [r1, #HDR_FLAGS+1]
    tst r2, #BLOCK_DELETED_HI
    bne menu_export_write_next
    ldr r2, [r1, #HDR_TOTAL_SIZE]
    mov r0, r6
    add r3, r5, #CARD_BR
    ldr r12, =FS_WRITE
    blx r12
    cmp r0, #0
    bne menu_export_close
    ldr r1, [r10, #SCRIPT_ENTRY_BLOB]
    ldr r2, [r1, #HDR_TOTAL_SIZE]
    ldr r0, [r5, #CARD_BR]
    cmp r0, r2
    movne r0, #2
    bne menu_export_close
menu_export_write_next:
    ldr r10, [r10, #SCRIPT_ENTRY_NEXT]
    b menu_export_write
menu_export_done:
    mov r0, r6
    ldr r12, =FS_CLOSE
    blx r12
    cmp r0, #0
    bne menu_export_fail
    str r8, [r4, #M_NSCRIPTS]
    bl menu_settings_save           ; and the settings, so the plugins switched off stay off (the page shows the export)
    mov r0, #2
    b menu_export_status
menu_export_close:
    mov r9, r0
    mov r0, r6
    ldr r12, =FS_CLOSE
    blx r12
    mov r0, r9
menu_export_fail:
    add r0, r0, #0x20
menu_export_status:
    str r0, [r4, #M_STATUS]
    pop {r4-r11, pc}
export_path:
    .asciz "SD:KORG/blechtribe/Plugin/e2sPlugin.all"
.align 4
.pool
menu_export_end:

; Lists the *.blech files of KORG/blechtribe/Plugin that start with a plugin header into the name table (up to LIST_MAX names of
; at most 31 characters) and their plugin names into LIST_TITLES.
menu_list:
    push {r4-r10, lr}
    ldr r4, =MENU_STATE
    ldr r5, =HOOK_CARD
    mov r0, #0
    str r0, [r4, #M_IMP_N]
    str r0, [r4, #M_IMP_SEL]
    mov r0, #1
    str r0, [r4, #M_LISTED]
    add r6, r5, #LIST_DIR
    add r7, r5, #LIST_INFO
    add r8, r5, #LIST_LFN
    mov r0, r6
    ldr r1, =import_folder
    ldr r12, =FS_OPENDIR
    blx r12
    cmp r0, #0
    bne menu_list_out
    str r8, [r7, #0x18]
    mov r0, #63
    str r0, [r7, #0x1C]
menu_list_next:
    mov r0, #0
    strb r0, [r8]
    mov r0, r6
    mov r1, r7
    ldr r12, =FS_READDIR
    blx r12
    cmp r0, #0
    bne menu_list_done
    ldrb r0, [r7, #9]
    cmp r0, #0
    beq menu_list_done
    ldrb r0, [r7, #8]
    tst r0, #0x10
    bne menu_list_next
    ldrb r0, [r7, #8]
    tst r0, #0x06
    bne menu_list_next
    ldrb r0, [r8]
    cmp r0, #0
    addeq r9, r7, #9
    movne r9, r8
    ldrb r0, [r9]
    cmp r0, #0x2E
    beq menu_list_next
    mov r10, #0
menu_list_len:
    ldrb r0, [r9, r10]
    cmp r0, #0
    addne r10, r10, #1
    bne menu_list_len
    cmp r10, #7
    blo menu_list_next
    cmp r10, #31
    bhi menu_list_next
    sub r2, r10, #6
    add r2, r9, r2
    ldr r1, =str_suffix
    mov r3, #6
menu_list_suffix:
    ldrb r0, [r2], #1
    orr r0, r0, #0x20
    ldrb r12, [r1], #1
    cmp r0, r12
    bne menu_list_next
    subs r3, r3, #1
    bne menu_list_suffix
    ldr r0, [r4, #M_IMP_N]
    cmp r0, #LIST_MAX
    bhs menu_list_done
    add r1, r5, #LIST_NAMES
    add r0, r1, r0, lsl #5
    mov r1, r9
    bl menu_copy
    bl menu_list_title
    cmp r0, #0
    beq menu_list_next
    ldr r0, [r4, #M_IMP_N]
    add r0, r0, #1
    str r0, [r4, #M_IMP_N]
    b menu_list_next
menu_list_done:
    mov r0, r6
    ldr r12, =FS_CLOSEDIR
    blx r12
menu_list_out:
    pop {r4-r10, pc}
str_suffix:
    .asciz ".blech"
import_folder:
    .asciz "SD:KORG/blechtribe/Plugin"
import_prefix:
    .asciz "SD:KORG/blechtribe/Plugin/"
.align 4
.pool

; Reads the selected .blech file, loads its block, and starts it unless it waits for the user's yes. The file goes through the
; buffer of the store image, which is read back from the card afterwards (and gives the new plugin its saved values).
; Sets M_STATUS: 0 loaded, 0x31 nothing to import, 0x32 scripts are off, 0x33 not a script file, 0x34 rejected,
; 0x35 name already loaded, 0x36 memory full, 0x37 loaded but no app place left (korg.app sets it), 0x20 + code of the failing FatFs call.
menu_import:
    push {r4-r11, lr}
    ldr r4, =MENU_STATE
    ldr r5, =HOOK_CARD
    add r6, r5, #CARD_FIL
    ldr r7, =HOOK_RUNTIME
    mov r11, #0
    ldr r0, [r4, #M_IMP_N]
    cmp r0, #0
    moveq r0, #0x31
    beq menu_import_status
    ldr r0, [r4, #M_EFF_RUN]
    cmp r0, #0
    moveq r0, #0x32
    beq menu_import_status
    ldr r1, [r4, #M_IMP_SEL]
    add r2, r5, #LIST_NAMES
    add r1, r2, r1, lsl #5
    bl menu_open_listed
    cmp r0, #0
    bne menu_import_fail
    mov r11, #1                 ; from here the store image is gone: read it back before returning
    ldr r9, =HOOK_INPUT
    mov r0, r6
    mov r1, r9
    ldr r2, =ARCHIVE_MAX_BLOCK
    add r3, r5, #CARD_BR
    ldr r12, =FS_READ
    blx r12
    mov r10, r0
    mov r0, r6
    ldr r12, =FS_CLOSE
    blx r12
    cmp r10, #0
    movne r0, r10
    bne menu_import_fail
    ldr r10, [r5, #CARD_BR]
    cmp r10, #HDR_SIZE
    movlo r0, #0x33
    blo menu_import_status
    ldr r0, [r9, #HDR_TOTAL_SIZE]
    cmp r0, r10
    movhi r0, #0x33
    bhi menu_import_status
    mov r10, r0
    ldr r0, [r7, #RT_HEAD]
    cmn r0, #1
    bne menu_import_unique
    mov r0, r7
    ldr r1, =HOOK_POOL
    ldr r2, =SCRIPT_POOL_BYTES
    ldr r12, =VM_SCRIPT_RUNTIME_INIT
    blx r12
    ldr r0, [r7, #RT_HEAD]
menu_import_unique:
    cmp r0, #0
    beq menu_import_load
    ldr r1, [r0, #SCRIPT_ENTRY_BLOB]
    ldrb r2, [r1, #HDR_FLAGS+1]
    tst r2, #BLOCK_DELETED_HI
    bne menu_import_next        ; a deleted plugin's block stays in the pool until the next start; its file can be loaded again
    ldr r2, [r1, #HDR_NAME]
    ldr r3, [r9, #HDR_NAME]
    cmp r2, r3
    bne menu_import_next
    ldr r2, [r1, #HDR_NAME+4]
    ldr r3, [r9, #HDR_NAME+4]
    cmp r2, r3
    bne menu_import_next
    ldr r2, [r1, #HDR_NAME+8]
    ldr r3, [r9, #HDR_NAME+8]
    cmp r2, r3
    bne menu_import_next
    ldr r2, [r1, #HDR_NAME+12]
    ldr r3, [r9, #HDR_NAME+12]
    cmp r2, r3
    moveq r0, #0x35
    beq menu_import_status
menu_import_next:
    ldr r0, [r0, #SCRIPT_ENTRY_NEXT]
    b menu_import_unique
menu_import_load:
    mov r0, r7
    mov r1, r9
    mov r2, r10
    ldr r12, =VM_SCRIPT_LOAD_BLOCK
    blx r12
    cmp r0, #0
    beq menu_import_loaded
    cmp r0, #ERR_POOL_BUDGET
    beq menu_import_full
    cmp r0, #ERR_VARS_BUDGET
    beq menu_import_full
    mov r0, #0x34
    b menu_import_status
menu_import_full:
    mov r0, #0x36
    b menu_import_status
menu_import_loaded:
    mov r0, #0
    str r0, [r4, #M_STATUS]         ; korg.app sets 0x37 here when all places are taken
    ldr r9, [r7, #RT_TAIL]
    mov r0, r7
    mov r1, r9
    bl script_store_load
    mov r11, #0
    mov r0, r9
    bl menu_needs_confirm
    cmp r0, #0
    bne menu_import_armed
    mov r0, r7
    mov r1, r9
    mov r2, #EV_START
    ldr r3, =HOOK_INPUT
    ldr r12, =VM_SCRIPT_RUN_EVENT
    blx r12
menu_import_armed:
    mov r0, #1
    str r0, [r7, #RT_ARMED]
    bl menu_recount
    ldr r0, [r4, #M_STATUS]
    cmp r0, #0x37
    movne r0, #0
    b menu_import_status
menu_import_fail:
    add r0, r0, #0x20
menu_import_status:
    mov r8, r0
    cmp r11, #0
    movne r0, r7
    movne r1, r11               ; 1: no plugin is handed values
    blne script_store_load
    str r8, [r4, #M_STATUS]
    pop {r4-r11, pc}
.pool

; r1 = the name of a file in KORG/blechtribe/Plugin -> r0 = the FatFs result of opening it for reading, at CARD_FIL.
; Clobbers r0 to r3 and r12.
menu_open_listed:
    push {r4, lr}
    mov r4, r1
    ldr r0, =HOOK_CARD
    add r0, r0, #LIST_PATH
    ldr r1, =import_prefix
    bl menu_copy
    mov r1, r4
    bl menu_copy
    ldr r0, =HOOK_CARD
    add r1, r0, #LIST_PATH
    add r0, r0, #CARD_FIL
    mov r2, #1
    ldr r12, =FS_OPEN
    blx r12
    pop {r4, pc}

; r0 = destination, r1 = bytes -> r0 = 0 when exactly that many came from the file at CARD_FIL. Clobbers r0 to r3 and r12.
menu_read_listed:
    push {r4, lr}
    mov r4, r1
    mov r2, r1
    mov r1, r0
    ldr r0, =HOOK_CARD
    add r3, r0, #CARD_BR
    add r0, r0, #CARD_FIL
    ldr r12, =FS_READ
    blx r12
    cmp r0, #0
    popne {r4, pc}
    ldr r0, =HOOK_CARD
    ldr r0, [r0, #CARD_BR]
    subs r0, r0, r4
    pop {r4, pc}

menu_close_listed:
    ldr r0, =HOOK_CARD
    add r0, r0, #CARD_FIL
    ldr r12, =FS_CLOSE
    bx r12

; The file just put at LIST_NAMES + M_IMP_N -> r0 = 1 when it starts with a plugin header, whose name then goes to LIST_TITLES.
; Clobbers r0 to r3 and r12.
menu_list_title:
    push {r4-r6, lr}
    ldr r5, =HOOK_CARD
    ldr r6, =MENU_STATE
    ldr r6, [r6, #M_IMP_N]
    add r1, r5, #LIST_NAMES
    add r1, r1, r6, lsl #5
    bl menu_open_listed
    cmp r0, #0
    bne menu_list_title_no
    add r0, r5, #LIST_DESC
    mov r1, #HDR_SIZE
    bl menu_read_listed
    mov r4, r0
    bl menu_close_listed
    cmp r4, #0
    bne menu_list_title_no
    ldr r0, [r5, #LIST_DESC]
    ldr r1, =SCRIPT_MAGIC
    cmp r0, r1
    bne menu_list_title_no
    add r0, r5, #LIST_TITLES
    add r0, r0, r6, lsl #4
    add r1, r5, #LIST_DESC
    add r1, r1, #HDR_NAME
    mov r2, #15
menu_list_title_copy:
    ldrb r3, [r1], #1
    strb r3, [r0], #1
    subs r2, r2, #1
    bne menu_list_title_copy
    strb r2, [r0]
    mov r0, #1
    pop {r4-r6, pc}
menu_list_title_no:
    mov r0, #0
    pop {r4-r6, pc}

; r0 = a file's index in the list -> r0 = the loaded plugin (not Blechy, not a deleted one) with the name of that file, 0 when none.
; Clobbers r1 to r3 and r12.
menu_file_entry:
    push {r4, lr}
    ldr r4, =HOOK_CARD
    add r4, r4, #LIST_TITLES
    add r4, r4, r0, lsl #4
    ldr r0, =HOOK_RUNTIME
    ldr r0, [r0, #RT_HEAD]
    cmn r0, #1
    moveq r0, #0
menu_file_entry_loop:
    cmp r0, #0
    popeq {r4, pc}
    ldr r1, [r0, #SCRIPT_ENTRY_BLOB]
    ldr r2, =HOOK_POOL
    cmp r1, r2
    blo menu_file_entry_next
    ldrb r3, [r1, #HDR_FLAGS+1]
    tst r3, #BLOCK_DELETED_HI
    bne menu_file_entry_next
    add r1, r1, #HDR_NAME
    mov r2, #0
menu_file_entry_cmp:
    ldr r3, [r1, r2]
    ldr r12, [r4, r2]
    cmp r3, r12
    bne menu_file_entry_next
    add r2, r2, #4
    cmp r2, #16
    blo menu_file_entry_cmp
    pop {r4, pc}
menu_file_entry_next:
    ldr r0, [r0, #SCRIPT_ENTRY_NEXT]
    b menu_file_entry_loop

; r0 = a script entry, 0 for a plugin that is not loaded -> r1 = its state: ON, OFF (also not loaded), FAULT or ENTER=ALLOW.
; Clobbers r0 to r3 and r12.
menu_state_text:
    push {r4, lr}
    movs r4, r0
    ldreq r1, =str_off
    popeq {r4, pc}
    ldr r2, [r4, #SCRIPT_ENTRY_STATE]
    ldr r1, =str_on
    cmp r2, #SCRIPT_STATE_ARMED
    popeq {r4, pc}
    ldr r1, =str_fault
    cmp r2, #SCRIPT_STATE_DISABLED
    popeq {r4, pc}
    mov r0, r4
    bl menu_needs_confirm
    cmp r0, #0
    ldrne r1, =str_enter_allow
    ldreq r1, =str_off
    pop {r4, pc}
.pool

; The list of PLUGIN EDIT is the loaded plugins in their order (menu_entry), then the plugins of the listed files that are not loaded,
; in the order of the files. M_PSEL counts through both.
; r0 = a plugin's index in it -> r0 = the index of its file in the list of files, -1 when it has none (a plugin only in e2sPlugin.all).
; Clobbers r1 to r3 and r12.
menu_psel_file:
    push {r4-r6, lr}
    mov r6, r0
    bl menu_entry
    mov r5, r0
    ldr r0, =MENU_STATE
    ldr r0, [r0, #M_NSCRIPTS]
    sub r6, r6, r0              ; the place among the plugins that are not loaded, when it is one
    mov r4, #0
menu_psel_file_loop:
    ldr r0, =MENU_STATE
    ldr r0, [r0, #M_IMP_N]
    cmp r4, r0
    bhs menu_psel_file_none
    mov r0, r4
    bl menu_file_entry
    cmp r5, #0
    beq menu_psel_file_free
    cmp r0, r5
    beq menu_psel_file_found
    b menu_psel_file_next
menu_psel_file_free:
    cmp r0, #0
    bne menu_psel_file_next
    cmp r6, #0
    beq menu_psel_file_found
    sub r6, r6, #1
menu_psel_file_next:
    add r4, r4, #1
    b menu_psel_file_loop
menu_psel_file_found:
    mov r0, r4
    pop {r4-r6, pc}
menu_psel_file_none:
    mvn r0, #0
    pop {r4-r6, pc}
.pool

; -> r0 = how many plugins the list of PLUGIN EDIT has. Clobbers r1 to r3 and r12.
menu_psel_total:
    push {r4, r5, lr}
    ldr r0, =MENU_STATE
    ldr r5, [r0, #M_NSCRIPTS]
    mov r4, #0
menu_psel_total_loop:
    ldr r0, =MENU_STATE
    ldr r0, [r0, #M_IMP_N]
    cmp r4, r0
    bhs menu_psel_total_done
    mov r0, r4
    bl menu_file_entry
    cmp r0, #0
    addeq r5, r5, #1
    add r4, r4, #1
    b menu_psel_total_loop
menu_psel_total_done:
    mov r0, r5
    pop {r4, r5, pc}
.pool

; r0 = a plugin's index in the list of PLUGIN EDIT -> r1 = its name, a zero terminated text: from its block, or from its file when it is
; not loaded. Clobbers r0 to r3 and r12.
menu_psel_name:
    push {r4, lr}
    mov r4, r0
    bl menu_entry
    cmp r0, #0
    ldrne r1, [r0, #SCRIPT_ENTRY_BLOB]
    addne r1, r1, #HDR_NAME
    popne {r4, pc}
    mov r0, r4
    bl menu_psel_file
    cmp r0, #0
    ldrlt r1, =str_noplugin
    poplt {r4, pc}
    ldr r1, =HOOK_CARD
    add r1, r1, #LIST_TITLES
    add r1, r1, r0, lsl #4
    pop {r4, pc}
.pool

; Loads and starts the plugin SELECT PLUGIN chose when it is not loaded (the dial up on STATE, or ENTER there), from its file. A
; plugin that loaded takes the next place among the loaded ones, which M_PSEL then points at. M_STATUS says what went wrong.
; Clobbers r0 to r3 and r12.
menu_load_psel:
    push {r4, r5, lr}
    ldr r4, =MENU_STATE
    mov r0, #0
    str r0, [r4, #M_STATUS]
    ldr r5, [r4, #M_NSCRIPTS]
    ldrb r0, [r4, #M_PSEL]
    bl menu_psel_file
    str r0, [r4, #M_IMP_SEL]
    cmp r0, #0
    movlt r0, #0x31
    strlt r0, [r4, #M_STATUS]
    poplt {r4, r5, pc}
    bl menu_import
    ldr r0, [r4, #M_NSCRIPTS]
    cmp r0, r5
    strbhi r5, [r4, #M_PSEL]
    pop {r4, r5, pc}
.pool

; The page DESCRIPTION of the plugin SELECT PLUGIN chose: its file (a plugin that is only in e2sPlugin.all has none, its description
; is empty) is read by menu_desc_open. Clobbers r0 to r3 and r12.
menu_desc_load:
    push {r4, lr}
    ldr r4, =MENU_STATE
    ldrb r0, [r4, #M_PSEL]
    bl menu_psel_file
    str r0, [r4, #M_IMP_SEL]
    cmp r0, #0
    bge menu_desc_load_file
    mov r0, #0
    ldr r1, =HOOK_CARD
    add r1, r1, #LIST_DESC
    strb r0, [r1]
    strb r0, [r4, #M_DESC_N]
    str r0, [r4, #M_DESC_TOP]
    str r0, [r4, #M_STATUS]
    mov r0, #2
    str r0, [r4, #M_LISTED]
    pop {r4, pc}
menu_desc_load_file:
    bl menu_desc_open
    pop {r4, pc}
.pool

; Reads the description behind the block of the file M_IMP_SEL (DESC_TRAILER) into LIST_DESC and marks it open (M_LISTED 2).
; M_STATUS 0x20 + the FatFs code when the file does not open. Clobbers r0 to r3 and r12.
menu_desc_open:
    push {r4-r7, lr}
    ldr r4, =MENU_STATE
    ldr r5, =HOOK_CARD
    add r6, r5, #LIST_DESC
    mov r0, #0
    strb r0, [r6]
    ldr r1, [r4, #M_IMP_SEL]
    add r1, r5, r1, lsl #5
    add r1, r1, #LIST_NAMES
    bl menu_open_listed
    cmp r0, #0
    addne r0, r0, #0x20
    bne menu_desc_status
    mov r0, r6
    mov r1, #HDR_SIZE
    bl menu_read_listed
    cmp r0, #0
    bne menu_desc_none
    ldr r7, [r6, #HDR_TOTAL_SIZE]
    sub r7, r7, #HDR_SIZE
menu_desc_skip:
    cmp r7, #0
    ble menu_desc_trailer
    mov r1, r7
    cmp r1, #0x400
    movhi r1, #0x400
    sub r7, r7, r1
    mov r0, r6
    bl menu_read_listed
    cmp r0, #0
    beq menu_desc_skip
    b menu_desc_none
menu_desc_trailer:
    mov r0, r6
    mov r1, #8
    bl menu_read_listed
    cmp r0, #0
    bne menu_desc_none
    ldr r0, [r6]
    ldr r1, =DESC_MAGIC
    cmp r0, r1
    bne menu_desc_none
    ldr r7, [r6, #4]
    ldr r1, =DESC_MAX_BYTES
    cmp r7, r1
    movhi r7, r1
    mov r0, r6
    mov r1, r7
    bl menu_read_listed
    cmp r0, #0
    strbeq r0, [r6, r7]
    beq menu_desc_close
menu_desc_none:
    mov r0, #0
    strb r0, [r6]
menu_desc_close:
    bl menu_close_listed
    mov r0, #0
menu_desc_count:
    ldrb r1, [r6], #1
    cmp r1, #10
    addeq r0, r0, #1
    cmp r1, #0
    bne menu_desc_count
    cmp r0, #255
    movhi r0, #255
    strb r0, [r4, #M_DESC_N]
    mov r0, #0
    str r0, [r4, #M_DESC_TOP]
    mov r0, #2
    str r0, [r4, #M_LISTED]
    mov r0, #0
menu_desc_status:
    str r0, [r4, #M_STATUS]
    pop {r4-r7, pc}
.pool

; r5 = MENU_STATE. On the page DESCRIPTION with the description read: the plugin's name, its description from M_DESC_TOP and the value
; line (its state or what was done) go into the runtime's picture, which script_display_blit puts on the display, and the three text lines of
; the firmware stay empty. When that picture was up and is no more, the firmware draws its whole screen again. Clobbers r0 to
; r3 and r12.
menu_desc_frame:
    push {r4-r8, lr}
    mov r8, r5
    ldr r0, [r8, #M_LISTED]
    cmp r0, #2
    bne menu_desc_frame_off
    ldr r0, [r8, #M_PAGE]
    bl menu_kind
    cmp r0, #39
    bne menu_desc_frame_off
    bl display_clear
    ldrb r0, [r8, #M_PSEL]
    bl menu_psel_name
    mov r4, r1
    mov r5, #4                  ; 4 pixels from the sides, 2 from top and bottom, as the firmware's menus (device 19.10.)
    mov r6, #2
    bl display_draw_text
    mov r0, #0
    mov r1, #11
    mov r2, #128
    mov r3, #1
    mov r12, #1
    bl display_fill
    mov r0, #0
    mov r1, #53
    mov r2, #128
    mov r3, #1
    mov r12, #1
    bl display_fill
    ldr r7, =HOOK_CARD
    add r7, r7, #LIST_DESC
    ldrb r0, [r8, #M_DESC_N]
    cmp r0, #0
    ldreq r4, =str_no_desc
    moveq r5, #4
    moveq r6, #13
    bleq display_draw_text
    ldr r0, [r8, #M_DESC_TOP]
menu_desc_frame_skip:
    cmp r0, #0
    beq menu_desc_frame_rows
    ldrb r1, [r7]
    cmp r1, #0
    beq menu_desc_frame_rows
    add r7, r7, #1
    cmp r1, #10
    subeq r0, r0, #1
    b menu_desc_frame_skip
menu_desc_frame_rows:
    sub sp, sp, #24
    mov r6, #13
menu_desc_frame_row:
    mov r0, #0
menu_desc_frame_char:
    ldrb r1, [r7]
    cmp r1, #0
    beq menu_desc_frame_line
    add r7, r7, #1
    cmp r1, #10
    beq menu_desc_frame_line
    cmp r0, #DESC_WIDTH
    strblo r1, [sp, r0]
    addlo r0, r0, #1
    b menu_desc_frame_char
menu_desc_frame_line:
    mov r1, #0
    strb r1, [sp, r0]
    mov r4, sp
    mov r5, #4
    bl display_draw_text
    add r6, r6, #8
    cmp r6, #13+8*DESC_ROWS
    blo menu_desc_frame_row
    add sp, sp, #24
    ldr r0, [r8, #M_DESC_TOP]   ; the scroll marks in the title row: ^ more above, v more below
    cmp r0, #0
    ldrne r4, =str_up
    movne r5, #112
    movne r6, #2
    blne display_draw_text
    ldr r0, [r8, #M_DESC_TOP]
    ldrb r1, [r8, #M_DESC_N]
    add r0, r0, #DESC_ROWS
    cmp r0, r1
    ldrlo r4, =str_down
    movlo r5, #119
    movlo r6, #2
    bllo display_draw_text
    add r4, r8, #M_VALUE
    mov r5, #4
    mov r6, #55
    bl display_draw_text
    mov r0, #0
    strb r0, [r8, #M_TITLE]
    strb r0, [r8, #M_VALUE]
    strb r0, [r8, #M_LINE3]
    mov r0, #1
    strb r0, [r8, #M_DESC_ON]
    pop {r4-r8, pc}
menu_desc_frame_off:
    ldrb r0, [r8, #M_DESC_ON]
    cmp r0, #0
    popeq {r4-r8, pc}
    mov r0, #0
    strb r0, [r8, #M_DESC_ON]
    ldr r1, =UI_REDRAW
    mov r0, #1
    strb r0, [r1]
    pop {r4-r8, pc}
.pool

; r0 = destination, r1 = zero-terminated source; at most 31 characters
menu_copy16:
    mov r3, #15
    b menu_copy_loop
menu_copy14:
    mov r3, #14
    b menu_copy_loop
menu_copy:
    mov r3, #31
menu_copy_loop:
    ldrb r2, [r1], #1
    cmp r2, #0
    beq menu_copy_end
    strb r2, [r0], #1
    subs r3, r3, #1
    bne menu_copy_loop
menu_copy_end:
    mov r2, #0
    strb r2, [r0]
    bx lr

; ---- slots of the class, this = r0
menu_slot_prev:
    push {r4, lr}
    mov r4, r0
    ldr r2, =MENU_STATE
    ldr r1, [r2, #M_PAGE]
    cmp r1, #0
    bne menu_prev_step
    ldr r3, [r2, #M_LEVEL]
    cmp r3, #M_LEVEL_BLECHY
    beq menu_prev_blechy
    cmp r3, #M_LEVEL_SYNC
    beq menu_prev_sync
    cmp r3, #0
    bne menu_prev_wrap
    pop {r4, lr}
    b menu_leave_left
menu_prev_wrap:
    bl menu_page_count
    mov r1, r0
    ldr r2, =MENU_STATE
menu_prev_step:
    sub r1, r1, #1
    str r1, [r2, #M_PAGE]
    str r1, [r2, #M_ENTER]
    mov r3, #0
    str r3, [r2, #M_STATUS]
    str r3, [r2, #M_LISTED]
    mov r0, r4
    bl menu_show
    pop {r4, pc}
menu_leave_left:
    mov r0, #10                 ; the page BLECH, EDIT left: back to Event
    mov r1, #0
    ldr pc, =SWITCH_SCREEN
; the page SYNC GROUP, EDIT left: back to the page of Blechy (level 3 of the same screen)
menu_prev_sync:
    mov r3, #M_LEVEL_BLECHY
    str r3, [r2, #M_LEVEL]
    mov r3, #0
    str r3, [r2, #M_PAGE]
    str r3, [r2, #M_ENTER]
    mov r0, r4
    bl menu_show
    pop {r4, pc}
; the page of Blechy, EDIT left: back to the page BLECH (level 0 of the same screen)
menu_prev_blechy:
    mov r3, #0
    str r3, [r2, #M_LEVEL]
    str r3, [r2, #M_PAGE]
    str r3, [r2, #M_ENTER]
    bl blechy_leave
    mov r0, r4
    bl menu_show
    pop {r4, pc}
.pool

menu_slot_next:
    push {r4, lr}
    mov r4, r0
    bl menu_page_count
    ldr r2, =MENU_STATE
    ldr r1, [r2, #M_PAGE]
    add r1, r1, #1
    cmp r1, r0
    blo menu_next_step
    ldr r3, [r2, #M_LEVEL]
    cmp r3, #M_LEVEL_SYNC
    beq menu_next_pattern
    cmp r3, #M_LEVEL_BLECHY
    beq menu_next_blechy
    cmp r3, #0
    beq menu_next_leave
    mov r1, #0
menu_next_step:
    str r1, [r2, #M_PAGE]
    str r1, [r2, #M_ENTER]
    mov r3, #0
    str r3, [r2, #M_STATUS]
    str r3, [r2, #M_LISTED]
    mov r0, r4
    bl menu_show
    pop {r4, pc}
menu_next_leave:               ; the page BLECH, EDIT right: the page of Blechy (level 3 of the same screen)
    mov r3, #M_LEVEL_BLECHY
    str r3, [r2, #M_LEVEL]
    mov r3, #0
    str r3, [r2, #M_PAGE]
    str r3, [r2, #M_ENTER]
    mov r0, r4
    bl menu_show
    pop {r4, pc}
; the page of Blechy, EDIT right: the page SYNC GROUP (level 4), or the Pattern menu where the build has no sync groups
menu_next_blechy:
    mov r3, #HAS_SYNC
    cmp r3, #0
    beq menu_next_pattern
    mov r3, #M_LEVEL_SYNC
    str r3, [r2, #M_LEVEL]
    mov r3, #0
    str r3, [r2, #M_PAGE]
    str r3, [r2, #M_ENTER]
    bl blechy_leave
    mov r0, r4
    bl menu_show
    pop {r4, pc}
; the last page of the ring, EDIT right: on to the Pattern menu, the way the firmware's Event menu does it (its slot 0xC0064430 is
; hooked, so the displaced first instruction runs here and the rest of it from the second word)
menu_next_pattern:
    pop {r4, lr}
    push {r3, r4, r5, lr}
    ldr pc, =0xC0064434
.pool

; r1 = steps of the main dial
menu_slot_value:
    push {r4, r5, r6, lr}
    mov r4, r0
    mov r5, r1
    ldr r6, =MENU_STATE
    ldr r0, [r6, #M_PAGE]
    bl menu_kind
    cmp r0, #18
    beq menu_value_pc
    cmp r0, #20
    beq menu_value_tm
    cmp r0, #21
    beq menu_value_na
    cmp r0, #24
    beq menu_value_colour
    cmp r0, #25
    beq menu_value_colour
    mov r2, #15
    cmp r0, #26
    moveq r3, #MX_INTENS
    beq menu_value_byte
    cmp r0, #27
    moveq r3, #MX_SAVE
    beq menu_value_byte
    mov r2, #7
    cmp r0, #28
    cmpne r0, #31
    moveq r2, #METER_RAINBOW    ; STILL and LOUD have RAINBOW behind the palette
    cmp r0, #28
    moveq r2, #METER_OFF        ; STILL has OFF behind RAINBOW
    sub r3, r0, #28
    cmp r3, #3
    subls r3, r3, #-MX_METER
    bls menu_value_byte
    cmp r0, #32
    beq menu_value_over
    cmp r0, #33
    beq menu_value_mg
    cmp r0, #34
    beq menu_value_ledsave
    cmp r0, #36
    beq menu_value_psel
    cmp r0, #39
    beq menu_value_desc
    cmp r0, #40
    beq menu_value_ip
    cmp r0, #15
    bhs menu_value_done
    cmp r0, #7
    bhs menu_value_look
    mov r12, #1
    cmp r5, #0
    movle r12, #0
    cmp r0, #0
    streq r12, [r6, #M_SET_RUN]
    cmp r0, #1
    streq r12, [r6, #M_SET_MFX]
    cmp r0, #2
    bhs menu_value_script
    mov r3, #0
    str r3, [r6, #M_STATUS]
    b menu_value_done
; INTENSITY, SAVE LIGHT and the meter's colours: r3 = the byte's offset from MENU_STATE, 0 to r2, acting at once like the other look pages
menu_value_byte:
    ldrb r1, [r6, r3]
    adds r1, r1, r5
    movmi r1, #0
    cmp r1, r2
    movgt r1, r2
    strb r1, [r6, r3]
    b menu_value_look_done
; SYNC GROUP: 0 (OFF) to 999 into the pattern in RAM, at once; the pattern keeps it when it is saved
menu_value_mg:
    bl menu_mg_at
    cmp r2, #0
    beq menu_value_done
    adds r3, r3, r5
    movmi r3, #0
    ldr r1, =999
    cmp r3, r1
    movgt r3, r1
    strb r3, [r2]
    mov r3, r3, lsr #8
    strb r3, [r2, #1]
    mov r3, #0
    str r3, [r6, #M_STATUS]
    b menu_value_done
; SELECT PLUGIN: 0 to the last plugin of the list (loaded ones first), no wrap (as SELECT SAMPLE)
menu_value_psel:
    bl menu_psel_total
    subs r2, r0, #1
    movmi r2, #0
    ldrb r1, [r6, #M_PSEL]
    adds r1, r1, r5
    movmi r1, #0
    cmp r1, r2
    movgt r1, r2
    strb r1, [r6, #M_PSEL]
    mov r3, #0
    str r3, [r6, #M_STATUS]
    b menu_value_done
; -> r2 = the sync group's place in the pattern in RAM (0 when there is none), r3 = the group there. Clobbers r1.
menu_mg_at:
    ldr r2, =SYNC_GROUP_AT
    cmp r2, #0
    moveq r3, #0
    bxeq lr
    ldr r1, =SC_PATPTR
    ldr r1, [r1]
    cmp r1, #0
    cmnne r1, #1
    moveq r2, #0
    moveq r3, #0
    bxeq lr
    add r2, r2, r1
    add r2, r2, #4
    ldrb r3, [r2, #1]
    ldrb r1, [r2]
    orr r3, r1, r3, lsl #8
    bx lr
; OVERLAP: 0 the colour left, 1 red, 2 blue, 3 pink, in the patch pad-colors; WRITE keeps it
menu_value_over:
    mov r1, #20
    bl menu_pc_call
    adds r0, r0, r5
    movmi r0, #0
    cmp r0, #3
    movgt r0, #3
    mov r1, #16
    bl menu_pc_call
    b menu_value_look_done
; LED DIMMING: the dial goes through led_dim_percent, the patch pad-colors keeps the step and sends the LEDs; WRITE keeps it
menu_value_ledsave:
    mov r1, #28
    bl menu_pc_call
    bl led_dim_index
    adds r0, r0, r5
    movmi r0, #0
    cmp r0, #11
    movgt r0, #11
    add r0, r0, #4              ; back to the patch's step
    cmp r0, #12
    subhs r0, r0, #12
    mov r1, #24
    bl menu_pc_call
    b menu_value_look_done
; PAD COLOR and SELECT COLOR: the dial steps the colour in the patch, which skips the other page's and sends the pads; WRITE keeps it.
menu_value_colour:
    mov r2, r5
    mov r1, #8
    bl menu_pc_call
    b menu_value_look_done

; the look pages of the group CUSTOMIZATION act at once (the menu is the preview); only WRITE keeps them
menu_value_look:
    cmp r0, #7
    bne menu_value_level
    ldr r1, [r6, #M_LED_MODE]
    add r1, r1, r5
    cmp r1, #0
    movlt r1, #0
    cmp r1, #2
    movgt r1, #2
    str r1, [r6, #M_LED_MODE]
    b menu_value_look_done
menu_value_level:
    cmp r0, #14
    beq menu_value_invert
    sub r1, r0, #8              ; 0 to 5: HUE, SAT, BRIGHT of the LEDs, then of the backlight
    cmp r1, #3
    addlo r0, r6, #M_LED_R
    addhs r0, r6, #M_BL_R
    subhs r1, r1, #3
    mov r2, r5
    bl look_hsv_step
    b menu_value_look_done
menu_value_invert:
    mov r1, #1
    cmp r5, #0
    movle r1, #0
    str r1, [r6, #M_INV]
menu_value_look_done:
    mov r3, #0
    str r3, [r6, #M_STATUS]
    bl menu_look_apply
    b menu_value_done
; PATTERN CONFIRM acts at once, like the look pages: the word of the pattern switch follows, WRITE keeps it
menu_value_pc:
    mov r1, #1
    cmp r5, #0
    movle r1, #0
    str r1, [r6, #M_PC]
    ldr r2, =PS_SETTING
    str r1, [r2]
    mov r3, #0
    str r3, [r6, #M_STATUS]
    b menu_value_done
; TAP MOTION acts at once as well: the word of the patch tap-motion follows, WRITE keeps it
menu_value_tm:
    ldr r1, [r6, #M_TM]
    cmp r5, #0
    addgt r1, r1, #1
    sublt r1, r1, #1
    cmp r1, #0
    movlt r1, #0
    cmp r1, #2
    movgt r1, #2
    str r1, [r6, #M_TM]
    ldr r2, =TM_SETTING
    str r1, [r2]
    mov r3, #0
    str r3, [r6, #M_STATUS]
    b menu_value_done
; NOTE ASSIST acts at once as well: the word of the patch note-assistant follows, WRITE keeps it
menu_value_na:
    mov r1, #1
    cmp r5, #0
    movle r1, #0
    str r1, [r6, #M_NA]
    ldr r2, =NA_SETTING
    str r1, [r2]
    mov r3, #0
    str r3, [r6, #M_STATUS]
    b menu_value_done
menu_value_script:
    cmp r0, #6
    beq menu_value_item
    cmp r0, #2
    bne menu_value_done
    mov r0, r1
    bl menu_entry
    cmp r0, #0
    beq menu_value_unloaded
    mov r6, r0
    bl menu_needs_confirm
    cmp r0, #0
    bne menu_value_done
    mov r0, r6
    mov r12, #1
    cmp r5, #0
    movle r12, #0
    ldr r3, [r0, #SCRIPT_ENTRY_STATE]
    cmp r3, #SCRIPT_STATE_LOADED
    cmpeq r12, #1
    beq menu_value_script_on
    cmp r3, #SCRIPT_STATE_ARMED
    cmpeq r12, #0
    moveq r1, #SCRIPT_STATE_LOADED
    streq r1, [r0, #SCRIPT_ENTRY_STATE]
menu_value_done:
    mov r0, r4
    bl menu_show
    pop {r4, r5, r6, pc}
menu_value_unloaded:            ; not loaded: the dial up loads and starts it, down does nothing
    cmp r5, #0
    blgt menu_load_psel
    b menu_value_done
menu_value_script_on:
    bl menu_script_on
    b menu_value_done
; r0 = a plugin switched off: on again. One the settings kept off at start never ran its start body (no cost recorded for it), so
; it runs now and arms it. Clobbers r0 to r3 and r12.
menu_script_on:
    ldr r1, [r0, #SCRIPT_ENTRY_MAX_COST+4*EV_START]
    cmp r1, #0
    movne r1, #SCRIPT_STATE_ARMED
    strne r1, [r0, #SCRIPT_ENTRY_STATE]
    bxne lr
    mov r1, r0
    ldr r0, =HOOK_RUNTIME
    mov r2, #EV_START
    ldr r3, =HOOK_INPUT
    ldr r12, =VM_SCRIPT_RUN_EVENT
    bx r12
menu_value_item:
    ldr r0, =MENU_ITEMS
    add r0, r0, r1, lsl #5
    add r0, r0, r1, lsl #3
    ldr r2, [r0, #4]
    ldr r3, [r0, #8]
    ldr r12, [r0, #12]
    add r12, r12, r5
    cmp r12, r2
    movlt r12, r2
    cmp r12, r3
    movgt r12, r3
    ldr r2, [r0, #12]
    cmp r12, r2
    beq menu_value_done
    str r12, [r0, #12]
    sub sp, sp, #16
    mov r2, #EV_MENU
    str r2, [sp]
    str r1, [sp, #4]
    str r12, [sp, #8]
    mov r2, #0
    str r2, [sp, #12]
    ldr r0, =HOOK_RUNTIME
    mov r1, sp
    bl script_ring_post
    add sp, sp, #16
    b menu_value_done
; DESCRIPTION: the dial scrolls it line by line
menu_value_desc:
    ldr r2, [r6, #M_LISTED]
    cmp r2, #2
    bne menu_value_done
    ldr r3, [r6, #M_DESC_TOP]
    add r3, r3, r5
    ldrb r2, [r6, #M_DESC_N]
    subs r2, r2, #DESC_ROWS
    movmi r2, #0
    cmp r3, r2
    movgt r3, r2
    cmp r3, #0
    movlt r3, #0
    str r3, [r6, #M_DESC_TOP]
    b menu_value_done
.pool

; r1 = key, r2 = 1 pressed. MENU (ENTER) goes into a group, opens an app or exports; WRITE does that and saves.
menu_slot_keys:
    cmp r2, #1
    bxne lr
    cmp r1, #0x0E
    cmpne r1, #0x09
    bxne lr
    push {r4, r5, r6, lr}
    mov r4, r0
    mov r6, r1
    ldr r0, =MENU_STATE
    ldr r0, [r0, #M_PAGE]
    bl menu_kind
    cmp r0, #16
    beq menu_keys_group
    cmp r0, #17
    beq menu_keys_group
    cmp r0, #15
    beq menu_keys_app
    cmp r0, #3
    beq menu_keys_export
    cmp r0, #19
    cmpne r0, #33
    beq menu_keys_done
    cmp r0, #22
    beq menu_keys_splash_import
    cmp r0, #23
    beq menu_keys_splash_draw
    cmp r0, #35
    beq menu_keys_splash_reset
    cmp r0, #38
    beq menu_keys_pedit
    cmp r0, #37
    beq menu_keys_pdel
    cmp r0, #39
    cmpne r0, #41
    beq menu_keys_done
    cmp r0, #2
    cmpeq r6, #0x09
    beq menu_keys_load
    cmp r6, #0x09
    beq menu_keys_done
    cmp r0, #2
    bne menu_keys_save
    mov r0, r1
    bl menu_entry
    cmp r0, #0
    beq menu_keys_done
    mov r5, r0
    bl menu_needs_confirm
    cmp r0, #0
    beq menu_keys_save
    ldr r0, [r5, #SCRIPT_ENTRY_STATE]
    cmp r0, #SCRIPT_STATE_LOADED
    bne menu_keys_save
    mov r0, r5
    bl menu_confirm
    b menu_keys_done
menu_keys_load:                 ; ENTER on STATE: a plugin that is not loaded is loaded and started
    mov r0, r1
    bl menu_entry
    cmp r0, #0
    bleq menu_load_psel
    b menu_keys_done
menu_keys_group:
    mov r0, r1
    mov r1, r4
    bl menu_go_in
    pop {r4, r5, r6, pc}
menu_keys_app:
    mov r0, r1
    bl script_app_open
    cmp r0, #0
    beq menu_keys_done
    pop {r4, r5, r6, lr}
    mov r0, #1
    mov r1, #0
    ldr pc, =SWITCH_SCREEN
; PLUGIN EDIT: ENTER reads the files of the plugin folder and opens the pages of the plugin SELECT PLUGIN chose last (level 5), "No Plugin"
; when there is none, WRITE saves as on the other pages
menu_keys_pedit:
    cmp r6, #0x09
    bne menu_keys_save
    bl menu_list
    ldr r2, =MENU_STATE
    mov r0, #0
    str r0, [r2, #M_LISTED]
    str r0, [r2, #M_STATUS]
    bl menu_psel_total
    ldr r2, =MENU_STATE
    cmp r0, #0
    moveq r1, #0x38
    streq r1, [r2, #M_STATUS]
    beq menu_keys_done
    ldrb r1, [r2, #M_PSEL]
    cmp r1, r0
    movhs r1, #0
    strb r1, [r2, #M_PSEL]
    mov r0, #M_LEVEL_PLUGIN
    str r0, [r2, #M_LEVEL]
    mov r0, #0
    str r0, [r2, #M_PAGE]
    str r0, [r2, #M_ENTER]
    str r0, [r2, #M_STATUS]
    b menu_keys_done
; DELETE PLUGIN: the first ENTER asks, the second deletes; WRITE does nothing here
menu_keys_pdel:
    cmp r6, #0x09
    bne menu_keys_done
    ldr r2, =MENU_STATE
    ldr r0, [r2, #M_STATUS]
    cmp r0, #0x50
    movne r0, #0x50
    strne r0, [r2, #M_STATUS]
    bne menu_keys_done
    ldrb r0, [r2, #M_PSEL]
    bl menu_entry
    cmp r0, #0
    beq menu_keys_done
    bl menu_delete
    b menu_keys_done
menu_keys_export:
    mov r0, #0
    bl menu_export
    b menu_keys_done
menu_keys_splash_import:
    cmp r6, #0x09
    bne menu_keys_done
    ldr r12, =SPLASH_IMPORT
    blx r12
    add r0, r0, #0x40           ; 0x40 stored, 0x41 no file, 0x42 not such a BMP, 0x43 the flash write failed
    ldr r1, =MENU_STATE
    str r0, [r1, #M_STATUS]
    b menu_keys_done
menu_keys_splash_reset:
    cmp r6, #0x09
    bne menu_keys_done
    ldr r12, =SPLASH_RESET
    blx r12
    cmp r0, #0
    moveq r0, #0x44             ; 0x44 the firmware's image is back
    movne r0, #0x43             ; else the flash write failed (or the editor is off), said as the write error
    ldr r1, =MENU_STATE
    str r0, [r1, #M_STATUS]
    b menu_keys_done
menu_keys_splash_draw:
    cmp r6, #0x09
    bne menu_keys_done
    pop {r4, r5, r6, lr}        ; the switch destroys this screen: jump, do not come back
    ldr pc, =SPLASH_DRAW
menu_keys_save:
    bl menu_settings_save
menu_keys_done:
    mov r0, r4
    bl menu_show
    pop {r4, r5, r6, pc}
.pool

; Slot 2 of the class, the firmware's handler for the keys no other slot takes (this, key, pressed): EXIT calls
; SWITCH_SCREEN(1, 0) there. Below level 0 EXIT goes one level up (out of the pages of a plugin first); every other key,
; and EXIT on level 0, is the firmware's own.
menu_slot_exit:
    cmp r1, #13
    cmpeq r2, #1
    bne menu_exit_stock
    push {r1, r2, r4, lr}
    ldr r2, =MENU_STATE
    ldr r3, [r2, #M_LEVEL]
    cmp r3, #0
    cmpne r3, #M_LEVEL_BLECHY
    cmpne r3, #M_LEVEL_SYNC
    beq menu_exit_stock_pop
    mov r4, r0
    cmp r3, #M_LEVEL_PLUGIN
    beq menu_exit_plugin
    cmp r3, #2
    bne menu_exit_up
    ldr r12, [r2, #M_GROUP]
    cmp r12, #5
    bhs menu_exit_sub
menu_exit_up:
    mov r12, #0
    str r12, [r2, #M_STATUS]
    str r12, [r2, #M_LISTED]
    cmp r3, #1                  ; out of the list: it opens on this row the next time
    ldreq r12, [r2, #M_PAGE]
    streq r12, [r2, #M_TOP]
    moveq r12, #0
    sub r3, r3, #1
    str r3, [r2, #M_LEVEL]
    cmp r3, #1
    ldreq r12, [r2, #M_TOP]
    str r12, [r2, #M_PAGE]
    str r12, [r2, #M_ENTER]
menu_exit_show:
    mov r0, r4
    bl menu_show
    pop {r1, r2, r4, pc}
menu_exit_plugin:                ; out of the pages of one plugin: back to PLUGIN EDIT
    mov r12, #2
    str r12, [r2, #M_LEVEL]
    mov r12, #1
    str r12, [r2, #M_PAGE]
    str r12, [r2, #M_ENTER]
    mov r12, #0
    str r12, [r2, #M_STATUS]
    str r12, [r2, #M_LISTED]
    b menu_exit_show
menu_exit_sub:                   ; out of DISPLAY, LED, PAD COLOR, POWER SAVE or SPLASH: back to its row in CUSTOMIZATION
    sub r12, r12, #5
    str r12, [r2, #M_PAGE]
    str r12, [r2, #M_ENTER]
    mov r12, #3
    str r12, [r2, #M_GROUP]
    b menu_exit_show
menu_exit_stock_pop:
    pop {r1, r2, r4, lr}
menu_exit_stock:
    ldr pc, =0xC0060F04
.pool

; MENU is the firmware's slot of its own and does not come through the key slot on a press: it is ENTER here.
menu_slot_enter:
    mov r1, #0x09
    mov r2, #1
    b menu_slot_keys
menu_slot_none:
    bx lr

str_scripts:
    .asciz "PLUGINS"
str_mfx:
    .asciz "MFX 2"
str_blech:
    .asciz "BLECH"
str_apps:
    .asciz " apps"
str_app_one:
    .asciz " app"
str_tab_plugins:
    .asciz "Plugins"
str_tab_games:
    .asciz "Games"
str_tab_tools:
    .asciz "Tools"
str_tab_custom:
    .asciz "Custom"
str_tab_features:
    .asciz "Feature"
str_tab_pattern:
    .asciz "Pattern"
str_pedit:
    .asciz "PLUGIN EDIT"
str_psel:
    .asciz "SELECT PLUGIN"
str_pdel:
    .asciz "DELETE PLUGIN"
str_state:
    .asciz "STATE"
str_noplugin:
    .asciz "No Plugin"
str_pdel_sure:
    .asciz "Enter = delete"
str_pdeleted:
    .asciz "deleted"
str_meter_still:
    .asciz "METER STILL"
str_meter_low:
    .asciz "METER LOW"
str_meter_mid:
    .asciz "METER MID"
str_meter_loud:
    .asciz "METER LOUD"
str_over:
    .asciz "OVERLAP"
str_auto:
    .asciz "AUTO"
str_c_white:
    .asciz "WHITE"
str_c_red:
    .asciz "RED"
str_c_green:
    .asciz "GREEN"
str_c_blue:
    .asciz "BLUE"
str_c_yellow:
    .asciz "YELLOW"
str_c_cyan:
    .asciz "CYAN"
str_c_rainbow:
    .asciz "RAINBOW"
str_c_pink:
    .asciz "PINK"
str_intens:
    .asciz "INTENSITY"
str_save:
    .asciz "DISPLAY LIGHT"
str_led_dim:
    .asciz "LED DIMMING"
str_percent:
    .asciz "%"
str_psave:
    .asciz "POWER SAVE"
str_tab_psave:
    .asciz "Power"
str_splash:
    .asciz "SPLASH"
str_tab_splash:
    .asciz "Splash"
str_stock_word:
    .asciz "STOCK"
str_tab_display:
    .asciz "Display"
str_tab_led:
    .asciz "LED"
str_tab_pads:
    .asciz "Pads"
str_display:
    .asciz "DISPLAY"
str_pads:
    .asciz "PAD COLOR"
str_press:
    .asciz "press  [ Enter ]"
str_runtime:
    .asciz "RUNTIME"
str_enter:
    .asciz "ENTER"
str_open_enter:
    .asciz "ENTER=OPEN"
str_no_files:
    .asciz "no files"
str_enter_allow:
    .asciz "ENTER=ALLOW"
str_no_desc:
    .asciz "no description"
str_up:
    .asciz "^"
str_down:
    .asciz "v"
str_runtime_off:
    .asciz "plugins off"
str_not_script:
    .asciz "not a plugin"
str_rejected:
    .asciz "rejected"
str_duplicate:
    .asciz "already loaded"
str_pool_full:
    .asciz "memory full"
str_apps_full:
    .asciz "max 12 apps"
str_allow:
    .asciz "WRITE=ALLOW"
str_fault:
    .asciz "FAULT"
str_line:
    .asciz " L"
str_on_restart:
    .asciz "ON, RESTART"
str_off_restart:
    .asciz "OFF, RESTART"
str_saved:
    .asciz "saved"
str_nocard:
    .asciz "no card"
str_protected:
    .asciz "card protected"
str_nofolder:
    .asciz "folder missing"
str_export:
    .asciz "EXPORT ALL"
str_exported:
    .asciz " exported"
str_nothing:
    .asciz "no plugins"
str_writeerr:
    .asciz "write error"
str_ledmode:
    .asciz "BOTTOM LEDS"
str_meter:
    .asciz "METER"
str_color:
    .asciz "COLOR"
str_custom:
    .asciz "CUSTOMIZATION"
str_features:
    .asciz "FEATURES"
str_led_red:
    .asciz "LED HUE"
str_led_green:
    .asciz "LED SAT"
str_led_blue:
    .asciz "LED BRIGHT"
str_bl_red:
    .asciz "BACKLIGHT HUE"
str_bl_green:
    .asciz "BACKLIGHT SAT"
str_bl_blue:
    .asciz "BACKLIGHT BRIGHT"
str_invert:
    .asciz "DISPLAY INVERT"
str_splash_import:
    .asciz "SPLASH IMPORT"
str_splash_draw:
    .asciz "SPLASH DRAW"
str_splash_reset:
    .asciz "SPLASH RESET"
str_splash_reset_done:
    .asciz "original back"
str_splash_saved:
    .asciz "loaded"
str_splash_nofile:
    .asciz "no splash.bmp"
str_splash_format:
    .asciz "not 128x64 1 bit"
str_pc:
    .asciz "PATTERN CONFIRM"
str_tm:
    .asciz "TAP MOTION"
str_na:
    .asciz "NOTE ASSIST"
str_mg:
    .asciz "SYNC GROUP"
str_base_hacktribe:
    .asciz "HACKTRIBE"
str_base_red:
    .asciz "KORG RED"
str_base_blue:
    .asciz "KORG BLUE"
.align 4
base_names:                     ; the value of VERSION, by BUILD_BASE (tools/patch/script_hooks.py): Hacktribe, Korg's red, Korg's blue
    .word str_base_hacktribe, str_base_red, str_base_blue
tab_names:
    .word str_blech, str_tab_plugins, str_tab_games, str_tab_tools, str_tab_custom, str_tab_features, str_tab_display, str_tab_led, str_tab_pads, str_tab_psave, str_tab_splash
group_names:
    .word str_scripts, str_group_games, str_group_tools, str_custom, str_features, str_display, str_tab_led, str_pads, str_psave, str_splash
custom_kinds:                   ; the rows of CUSTOMIZATION: DISPLAY, LED, PAD COLOR, POWER SAVE, SPLASH (groups 5 to 9)
    .byte 16, 16, 16, 16, 16
.align 4
sub_kinds:                      ; the kinds of the pages of DISPLAY, LED, PAD COLOR and POWER SAVE, 8 a group (device 18.10.)
    .byte 11, 12, 13, 26, 14, 0, 0, 0   ; DISPLAY: backlight red, green, blue, INTENSITY, display invert
    .byte 7, 8, 9, 10, 28, 29, 30, 31   ; LED: bottom LEDs, LED red, green, blue, the meter's four colours
    .byte 24, 25, 32, 0, 0, 0, 0, 0     ; PAD COLOR: pad colour, select colour, overlap
    .byte 27, 34, 0, 0, 0, 0, 0, 0      ; POWER SAVE: DISPLAY LIGHT, LED DIMMING (device 19.10.: SAVE LIGHT under DISPLAY said too little)
    .byte 22, 23, 35, 0, 0, 0, 0, 0     ; SPLASH: IMPORT, DRAW, RESET (device 22.10.: three rows of their own in CUSTOMIZATION were too many)
sub_counts:
    .byte 5, 8, 3, 2, 3
led_dim_percent:                ; LED DIMMING, the steps of the dial: percent dimmed (pad_colors.py keeps the step 8 places on, 75 is 0)
    .byte 0, 10, 20, 30, 40, 50, 60, 70, 75, 80, 90, 100
meter_palette:                  ; red, green, blue of the colours 1 to 7, then the firmware's colours of the four zones
    .byte 0, 0, 0,  160, 160, 160,  255, 0, 0,  0, 255, 0,  0, 0, 255,  255, 160, 0,  0, 200, 255,  255, 0, 160
    .byte 120, 120, 120,  0, 0, 255,  0, 255, 0,  255, 0, 0
.align 4
meter_titles:
    .word str_meter_still, str_meter_low, str_meter_mid, str_meter_loud
over_names:
    .word str_auto, str_c_red, str_c_blue, str_c_pink
colour_names:
    .word str_stock_word, str_c_white, str_c_red, str_c_green, str_c_blue, str_c_yellow, str_c_cyan, str_c_pink, str_c_rainbow, str_off
look_titles:
    .word str_led_red, str_led_green, str_led_blue, str_bl_red, str_bl_green, str_bl_blue
str_once:
    .asciz "ONCE"
str_on:
    .asciz "ON"
str_off:
    .asciz "OFF"
menu_tab:
    .asciz "BLECH"
    .align 4
menu_screen_end:
