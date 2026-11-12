; Shortcuts with EXIT held on the main screen (device wish 18.10.):
;   EXIT + WRITE  the pattern is saved into its own place at once: WRITE opens the firmware's Write window as always, and the next
;                 tick gives the window its second WRITE, which saves into the place the window starts on (the running pattern).
;   EXIT + pad    the sound of a part goes back to the values saved in the pattern bank: bytes 2 to 0x2F of the part (everything
;                 but last step and mute; the steps stay). Which part: the pad's, where a pad stands for a part, a note, a chord or a
;                 pattern (PART MUTE, PART ERASE, TRIGGER, KEYBOARD, CHORD, PATTERN SET); the selected part where it stands for a
;                 step (SEQUENCER, STEP JUMP).
;                 The firmware's pattern load (0xC004AB84) then applies the pattern in RAM onto itself, as after a pattern change,
;                 and the firmware's handler for a changed sample of a part (0xC0099FFC, what the SAMPLE knob runs) hands the part's
;                 sample to the voices; the load alone leaves the voices on the sample the part had before. Not the part sound setup
;                 of Copy Part (0xC009B5EC): it also switches the part off at the DSP, and on the device the part stayed silent
;                 (device test 11.11.). Stopped and playing.
; Not with EXIT held at power-on. On the synth too, with its places from data/synth-map/ (docs/messungen/2026-10-24-blau-shortcuts-akkorde.md). The firmware addresses SC_LEDMGR (LED manager:
; +0xB58 pad mode, +0xB60 selected part), SC_PLAYER (returns the player, +0x318 the running number), SC_PATPTR (the pattern in RAM,
; its file at +4), SC_BANK (the pattern bank, 0x4000 each), SC_LOAD ((pattern, source, 1): the firmware's pattern load) and
; SC_PART_OBJ ((part): the part's object for the voices) and SC_PART_SOUND ((part object): the firmware's handler for a changed
; sample of a part; the synth, which has no such handler, its per part setup of the pattern change) come with the build
; (script_hooks.py).
.equ SC_EXIT, -0x04             ; bytes in front of MENU_STATE (behind the MX_ bytes of the menu): 1 while EXIT is held
.equ SC_SAVE, -0x03             ; 1 to SC_WAIT: frames left for the Write window to open after EXIT + WRITE
.equ SC_RESET, -0x02            ; 1 to 16: the part (plus 1) the next tick resets
.equ SC_DIRTY, -0x01            ; 1 while the pattern in RAM differs from its place in the bank (sc_unsaved)
.equ SC_KEY_EXIT, 0x0D
.equ SC_KEY_WRITE, 0x0E
.equ SC_WINDOW, 18              ; the firmware's Write window (screen 0x12)
.equ SC_WAIT, 25                ; one second
.equ SC_SEQUENCER, 4            ; pad modes where a pad is a step (0 PART MUTE, 2 PART ERASE, 3 TRIGGER, 5 KEYBOARD, 6 CHORD,
.equ SC_STEP_JUMP, 7            ; 9 PATTERN SET: a pad is its part)
.equ SC_PART_AT, 0x800          ; part 0 in a pattern file
.equ SC_PART_SIZE, 0x330
.equ SC_SOUND, 0x2E             ; bytes 2 to 0x2F

; r0 = the panel message (type at +0x0C, data from +0x0D). Notes EXIT; with EXIT held on the main screen notes WRITE and takes a
; pad. Returns r0 = 1 to drop the message. Clobbers r0 to r3 and r12.
shortcut_input:
    push {r4, lr}
    mov r4, r0
    mov r0, #SHORTCUTS
    cmp r0, #0
    beq sc_pass
    ldr r1, =PANEL
    ldr r1, [r1]
    cmp r1, #0
    cmnne r1, #1
    beq sc_pass
    ldr r1, [r1, #0x18]
    tst r1, #0x2000
    bne sc_pass
    mov r0, r4
    bl kp_input
    cmp r0, #0
    bne sc_drop
    ldrb r1, [r4, #0x0c]
    cmp r1, #4
    beq sc_pad
    cmp r1, #0
    bne sc_pass
    ldrb r1, [r4, #0x0d]
    ldrb r2, [r4, #0x0e]
    cmp r1, #SC_KEY_EXIT
    bne sc_write
    cmp r2, #0
    movne r2, #1
    ldr r3, =MENU_STATE
    strb r2, [r3, #SC_EXIT]
    b sc_pass
sc_write:
    cmp r1, #SC_KEY_WRITE
    bne sc_pass
    cmp r2, #0
    beq sc_pass
    bl sc_held
    cmp r0, #0
    beq sc_pass
    ldr r3, =MENU_STATE
    mov r1, #SC_WAIT
    strb r1, [r3, #SC_SAVE]
    b sc_pass
sc_pad:
    bl sc_held
    cmp r0, #0
    beq sc_pass
    ldrb r1, [r4, #0x10]
    cmp r1, #0
    beq sc_drop
    ldrb r1, [r4, #0x0d]
    ldr r2, =SC_LEDMGR
    ldr r2, [r2]
    cmp r2, #0
    cmnne r2, #1
    beq sc_pad_part
    ldr r0, [r2, #0xB58]
    cmp r0, #SC_SEQUENCER
    cmpne r0, #SC_STEP_JUMP
    ldreq r1, [r2, #0xB60]
sc_pad_part:
    cmp r1, #16
    bhs sc_drop
    add r1, r1, #1
    ldr r3, =MENU_STATE
    strb r1, [r3, #SC_RESET]
sc_drop:
    mov r0, #1
    pop {r4, pc}
sc_pass:
    mov r0, #0
    pop {r4, pc}

; r0 = 1 while EXIT is held and the main screen is up. Clobbers r0.
sc_held:
    ldr r0, =MENU_STATE
    ldrb r0, [r0, #SC_EXIT]
    cmp r0, #1
    bne sc_held_no
    ldr r0, =SCREEN_MANAGER
    ldr r0, [r0]
    cmp r0, #0
    cmnne r0, #1
    beq sc_held_no
    ldr r0, [r0, #0x2c]
    cmp r0, #1
    bxeq lr
sc_held_no:
    mov r0, #0
    bx lr

; From the frame hook (UI task). Gives the Write window its second WRITE, resets the part that was asked for. Clobbers r0 to r3
; and r12.
shortcut_tick:
    push {r4-r6, lr}
    mov r0, #SHORTCUTS
    cmp r0, #0
    beq sc_tick_done
    ldr r4, =MENU_STATE
    ldrb r0, [r4, #SC_SAVE]
    sub r0, r0, #1
    cmp r0, #SC_WAIT
    bhs sc_tick_reset
    strb r0, [r4, #SC_SAVE]
    ldr r1, =SCREEN_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    cmnne r1, #1
    beq sc_tick_reset
    ldr r1, [r1, #0x2c]
    cmp r1, #SC_WINDOW
    bne sc_tick_reset
    mov r0, #0
    strb r0, [r4, #SC_SAVE]
    mov r0, #SC_KEY_WRITE
    mov r1, #1
    ldr r12, =HW_PANEL_KEY
    blx r12
    mov r0, #SC_KEY_WRITE
    mov r1, #0
    ldr r12, =HW_PANEL_KEY
    blx r12
sc_tick_reset:
    ldrb r5, [r4, #SC_RESET]
    sub r5, r5, #1
    cmp r5, #16
    bhs sc_tick_done
    mov r0, #0
    strb r0, [r4, #SC_RESET]
    ldr r6, =SC_PATPTR
    ldr r6, [r6]
    cmp r6, #0
    cmnne r6, #1
    beq sc_tick_done
    ldr r12, =SC_PLAYER
    blx r12
    ldr r0, [r0, #0x318]
    cmp r0, #250
    bhs sc_tick_done
    ldr r1, =SC_BANK
    add r1, r1, r0, lsl #14
    mov r2, #SC_PART_SIZE
    mul r3, r5, r2
    add r3, r3, #SC_PART_AT
    add r3, r3, #2
    add r1, r1, r3
    add r0, r6, #4
    add r0, r0, r3
    mov r2, #SC_SOUND
sc_tick_copy:
    ldrb r3, [r1], #1
    strb r3, [r0], #1
    subs r2, r2, #1
    bne sc_tick_copy
    mov r0, r6
    add r1, r6, #4
    mov r2, #1
    ldr r12, =SC_LOAD
    blx r12
    mov r0, r5                  ; the load does not set up the part's sound for the voices: without this the old sample plays
    ldr r12, =SC_PART_OBJ
    blx r12
    ldr r12, =SC_PART_SOUND
    blx r12
sc_tick_done:
    bl kp_tick
    bl sc_unsaved
    pop {r4-r6, pc}

; KEY PADS (idea 85, built in since the plugin keypads): KEYBOARD held on the main screen, a pad sets the KEY of the pattern, like
; TRANSPOSE on the old Electribes. The pads go up chromatically in pad order: pad 1 C, pad 2 C#, ... pad 12 B; pads 13 to 16
; set nothing (their press is still taken while KEYBOARD is held). The KEY goes through the Pattern menu's setter (field 4 of
; script_seq_set_pattern_value_glue), and the firmware's parameter window, the one a knob opens, shows "KEY" and the note.
; KEYBOARD is held away from the firmware: a short press without a pad goes on to it on release (script_press_key_glue, marked)
; and switches to KEYBOARD mode as always; with a pad it does not. SHIFT + KEYBOARD stays the firmware's, so does KEYBOARD while
; an app is open. The press of a pad taken here takes its release too. The page KEY PADS of FEATURES switches it (M_KP).
.equ KP_HELD, 0x108             ; bytes of MENU_STATE: 1 while KEYBOARD is held for KEY PADS
.equ KP_USED, 0x109             ; 1 once a pad was pressed while it is held
.equ KP_SHIFT, 0x10A            ; 1 while SHIFT is held
.equ KP_PRESS, 0x10B            ; 1: the next tick gives the firmware a short press of KEYBOARD
.equ KP_KEY, 0x10C              ; the KEY (plus 1) the next tick sets, 0 none
.equ KP_PADS, 0x110             ; word: the pads whose press was taken, their release is taken too
.equ KP_KEY_SHIFT, 10
.equ KP_KEY_KEYBOARD, 23
.equ KP_FIELD, 4                ; KEY in PATTERN_FIELDS
.equ KP_CODE, 0x5A              ; our code in the parameter window (the firmware's go from 0 to 0x12)
.equ KP_WIN_CODE, 0x318         ; the parameter window: its code, value and changed flag
.equ KP_WIN_VALUE, 0x31C
.equ KP_WIN_CHANGED, 0x320
.equ FT_KEY, 0x1C4              ; FILTER TOGGLE (ft_select), byte of MENU_STATE: the family (plus 1) of the key pressed with SHIFT, 0 a plain press
.equ FT_LAST, 0x1C8             ; 48 bytes: per part and family the type it had last, 0 none yet
.equ FT_KEY_LPF, 0x12
.equ FT_KEY_HPF, 0x14
.equ FT_KEY_BPF, 0x16

; r0 = the panel message. Returns r0 = 1 to drop it. Clobbers r0 to r3 and r12.
kp_input:
    ldr r3, =MENU_STATE
    ldr r1, [r3, #M_ON]         ; an unarmed menu reads FF everywhere (EXIT at power-on, before the arming): stock
    cmp r1, #1
    bne kp_pass
    ldrb r1, [r0, #0x0c]
    cmp r1, #4
    beq kp_pad
    cmp r1, #0
    bne kp_pass
    ldrb r1, [r0, #0x0d]
    ldrb r2, [r0, #0x0e]
    cmp r2, #0
    movne r2, #1
    cmp r1, #KP_KEY_SHIFT
    strbeq r2, [r3, #KP_SHIFT]
    beq kp_pass
    cmp r1, #FT_KEY_LPF
    cmpne r1, #FT_KEY_HPF
    cmpne r1, #FT_KEY_BPF
    beq ft_input
    cmp r1, #KP_KEY_KEYBOARD
    bne kp_pass
    cmp r2, #0
    beq kp_release
    ldr r1, [r3, #M_KP]
    cmp r1, #1
    bne kp_pass
    ldrb r1, [r3, #KP_SHIFT]
    cmp r1, #0
    bne kp_pass
    ldr r1, =APP_STATE
    ldr r1, [r1]
    cmp r1, #0
    bne kp_pass
    ldr r1, =SCREEN_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    cmnne r1, #1
    beq kp_pass
    ldr r1, [r1, #0x2c]
    cmp r1, #1
    bne kp_pass
    strb r1, [r3, #KP_HELD]
    mov r1, #0
    strb r1, [r3, #KP_USED]
    b kp_drop
kp_release:
    ldrb r1, [r3, #KP_HELD]
    cmp r1, #0
    beq kp_pass
    mov r1, #0
    strb r1, [r3, #KP_HELD]
    ldrb r1, [r3, #KP_USED]
    cmp r1, #0
    moveq r1, #1
    strbeq r1, [r3, #KP_PRESS]
    b kp_drop
kp_pad:
    ldrb r2, [r0, #0x10]
    ldrb r1, [r0, #0x0d]
    cmp r1, #16
    bhs kp_pass
    mov r12, #1
    mov r12, r12, lsl r1
    ldr r0, [r3, #KP_PADS]
    cmp r2, #0
    bne kp_pad_down
    tst r0, r12
    beq kp_pass
    bic r0, r0, r12
    str r0, [r3, #KP_PADS]
    b kp_drop
kp_pad_down:
    tst r0, r12                 ; again while it is down (pressure): ours as well
    bne kp_drop
    ldrb r2, [r3, #KP_HELD]
    cmp r2, #0
    beq kp_pass
    orr r0, r0, r12
    str r0, [r3, #KP_PADS]
    mov r2, #1
    strb r2, [r3, #KP_USED]
    ldr r2, =kp_notes
    ldrb r2, [r2, r1]
    cmp r2, #0
    strbne r2, [r3, #KP_KEY]
    b kp_drop
; FILTER TOGGLE: a press of LPF, HPF or BPF notes for ft_select whether SHIFT is held (the key's family plus 1) or not (0); the
; key goes on to the firmware either way
ft_input:
    cmp r2, #0
    beq kp_pass
    sub r1, r1, #FT_KEY_LPF
    mov r1, r1, lsr #1
    add r1, r1, #1
    ldr r2, [r3, #M_FT]
    cmp r2, #1
    ldrbeq r2, [r3, #KP_SHIFT]
    cmpeq r2, #1
    movne r1, #0
    strb r1, [r3, #FT_KEY]
    b kp_pass
kp_drop:
    mov r0, #1
    bx lr
kp_pass:
    mov r0, #0
    bx lr

; From shortcut_tick (UI task): the short press of KEYBOARD, then the KEY through the setter and the parameter window.
; Clobbers r0 to r3 and r12.
kp_tick:
    push {r4, r5, r6, lr}
    ldr r4, =MENU_STATE
    ldr r0, [r4, #M_ON]         ; unarmed: the bytes read FF, nothing is ours
    cmp r0, #1
    bne kp_tick_done
    ldrb r0, [r4, #KP_PRESS]
    cmp r0, #0
    beq kp_tick_key
    mov r0, #0
    strb r0, [r4, #KP_PRESS]
    mov r0, #KP_KEY_KEYBOARD
    bl script_press_key_glue
kp_tick_key:
    ldrb r5, [r4, #KP_KEY]
    subs r5, r5, #1
    bmi kp_tick_done
    mov r0, #0
    strb r0, [r4, #KP_KEY]
    mov r0, #KP_FIELD
    mov r1, r5
    bl script_seq_set_pattern_value_glue
    ldr r0, =KP_WINDOW
    cmp r0, #0
    beq kp_tick_done
    ldr r0, [r0]
    cmp r0, #0
    cmnne r0, #1
    beq kp_tick_done
    sub sp, sp, #8
    mov r1, #KP_CODE
    str r1, [sp]
    str r5, [sp, #4]
    add r0, r0, #4
    mov r1, sp
    ldr r12, =SEQ_NOTIFY
    blx r12
    add sp, sp, #8
kp_tick_done:
    pop {r4, r5, r6, pc}

; FILTER TOGGLE (idea 81, built in since the plugin filtertoggle): SHIFT + LPF, HPF or BPF turns the filter of the selected part
; off, and the same combination turns it on again with the type that key had last, kept per part and key until power off; SHIFT
; and another filter key goes straight to that key's last type (the family's first type before it had one). The firmware treats
; SHIFT + a filter key as the plain key; its handler (FT_AT, per build in script_hooks.py) branches here where it is about to set
; the type, so the type goes the firmware's own way, with its "FILTER TYPE" window. The page FILTER TOGGLE of FEATURES switches it
; (M_FT). Types: 0 OFF, 1 to 6 the LPF family, 7 to 11 HPF, 12 to 16 BPF. FT_KEY, FT_LAST: above kp_input, whose span notes the key.

; From the filter key handler at FT_AT: r4 = the type it is about to set, r5 = the part's type now. Sets r4, does the replaced
; mov r0, #8 and goes on at FT_BACK. r0 to r3, r5, r12 and lr are free there.
ft_select:
    ldr r3, =MENU_STATE
    ldr r0, [r3, #M_ON]
    cmp r0, #1
    bne ft_back
    ldrb r12, [r3, #FT_KEY]
    mov r0, #0
    strb r0, [r3, #FT_KEY]
    ldrb r0, [r3, #KP_SHIFT]
    cmp r0, #1
    movne r12, #0
    ldr r0, =SC_LEDMGR
    ldr r0, [r0]
    cmp r0, #0
    cmnne r0, #1
    beq ft_back
    ldr r0, [r0, #0xB60]
    cmp r0, #16
    bhs ft_back
    add r0, r0, r0, lsl #1
    add r0, r0, #FT_LAST
    add r0, r0, r3
    mov r1, r5
    bl ft_family
    cmp r2, #3
    strblo r5, [r0, r2]
    cmp r12, #0
    beq ft_keep
    sub r12, r12, #1
    cmp r12, r2
    moveq r4, #0
    beq ft_back
    ldrb r4, [r0, r12]
    cmp r4, #0
    ldreq r1, =ft_first
    ldrbeq r4, [r1, r12]
    b ft_back
ft_keep:
    mov r1, r4
    bl ft_family
    cmp r2, #3
    strblo r4, [r0, r2]
ft_back:
    mov r0, #8
    ldr r12, =FT_BACK
    bx r12

; r1 = a type -> r2 = its family (0 LPF, 1 HPF, 2 BPF, 3 OFF or none). Clobbers r2 only.
ft_family:
    mov r2, #3
    cmp r1, #1
    movhs r2, #0
    cmp r1, #7
    movhs r2, #1
    cmp r1, #12
    movhs r2, #2
    cmp r1, #17
    movhs r2, #3
    bx lr

ft_first:
    .byte 1, 7, 12, 0

; The three calls of the parameter window's draw function (KP_TITLE_AT, KP_VALUE_AT, KP_CHECK_AT, per build in script_hooks.py)
; branch here with r0 = the window: for our code the title "KEY", the note, and no extra mark; any other code goes on to the
; firmware's function, which returns to the draw function behind the call.
kp_title_hook:
    ldr lr, =KP_TITLE_AT+4
    ldr r12, [r0, #KP_WIN_CODE]
    cmp r12, #KP_CODE
    ldreq r0, =str_kp_title
    bxeq lr
    ldr r12, =KP_TITLE_FN
    bx r12

kp_value_hook:
    ldr lr, =KP_VALUE_AT+4
    ldr r12, [r0, #KP_WIN_CODE]
    cmp r12, #KP_CODE
    ldrne r12, =KP_VALUE_FN
    bxne r12
    mov r12, #0
    strb r12, [r0, #KP_WIN_CHANGED]
    ldr r12, [r0, #KP_WIN_VALUE]
    cmp r12, #11
    movhi r12, #0
    ldr r0, =kp_names
    add r0, r0, r12, lsl #2
    bx lr

kp_check_hook:
    ldr lr, =KP_CHECK_AT+4
    ldr r12, [r0, #KP_WIN_CODE]
    cmp r12, #KP_CODE
    moveq r0, #0
    bxeq lr
    ldr r12, =KP_CHECK_FN
    bx r12

; per pad the KEY it sets plus 1, 0 none
kp_notes:
    .byte 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 0, 0, 0, 0
kp_names:
    .asciz "C"
    .space 2
    .asciz "C#"
    .space 1
    .asciz "D"
    .space 2
    .asciz "D#"
    .space 1
    .asciz "E"
    .space 2
    .asciz "F"
    .space 2
    .asciz "F#"
    .space 1
    .asciz "G"
    .space 2
    .asciz "G#"
    .space 1
    .asciz "A"
    .space 2
    .asciz "A#"
    .space 1
    .asciz "B"
    .space 2
str_kp_title:
    .asciz "KEY"
.align 2

; The WRITE LED breathes while the pattern in RAM differs from its place in the bank (unsaved, device wish 19.10.): every 8 frames
; the two are compared word by word (bytes 0x3C, 0x3E and 0x3F left out: the firmware rewrites the pad's touch on every load, a touch of
; the pad writes its X and Y, neither is an edit), the LED goes from 1 to 61 and back in 32 frames (1.3 s), odd values only. The firmware writes
; the LED with even values or 255; a value of the firmware is left alone, and so is everything while a plugin holds the LED lock.
; Main screen only: elsewhere a value of ours goes dark. Clobbers r0 to r3 and r12.
.equ SC_WRITE_LED, 0x0B
.equ SC_LED_VALUE, 0x4E         ; LED manager + 0x4E + 8 * led: the brightness the firmware wants; the second table 0x2C0 further
sc_unsaved:
    push {r4-r7, lr}
    ldr r0, =SC_BANK
    cmp r0, #0
    beq sc_un_out
    ldr r4, =SC_LEDMGR
    ldr r4, [r4]
    cmp r4, #0
    cmnne r4, #1
    beq sc_un_out
    ldrb r0, [r4, #0xB98]
    cmp r0, #0
    bne sc_un_out
    mov r7, #0                  ; the wanted brightness
    ldr r0, =SCREEN_MANAGER
    ldr r0, [r0]
    cmp r0, #0
    cmnne r0, #1
    beq sc_un_put
    ldr r0, [r0, #0x2c]
    cmp r0, #1
    bne sc_un_put
    ldr r0, =HOOK_RUNTIME
    ldr r6, [r0, #RT_FRAMES]
    ldr r5, =MENU_STATE
    tst r6, #7
    bne sc_un_known
    ldr r0, =SC_PATPTR
    ldr r0, [r0]
    cmp r0, #0
    cmnne r0, #1
    beq sc_un_put
    ldr r12, =SC_PLAYER
    blx r12
    ldr r0, [r0, #0x318]
    cmp r0, #250
    bhs sc_un_put
    ldr r1, =SC_BANK
    add r1, r1, r0, lsl #14
    ldr r2, =SC_PATPTR
    ldr r2, [r2]
    add r2, r2, #4
    mov r3, #0x4000
    mov r0, #0
sc_un_cmp:
    subs r3, r3, #4
    bmi sc_un_cmp_done
    ldr r12, [r1, r3]
    ldr r0, [r2, r3]
    cmp r3, #0x3C               ; of this word only the MFX type (0x3D) counts: pad touched (0x3C), pad X and Y (0x3E, 0x3F) are not edits
    andeq r12, r12, #0xFF00
    andeq r0, r0, #0xFF00
    cmp r0, r12
    beq sc_un_cmp
    mov r0, #1
    b sc_un_cmp_store
sc_un_cmp_done:
    mov r0, #0
sc_un_cmp_store:
    strb r0, [r5, #SC_DIRTY]
sc_un_known:
    ldrb r0, [r5, #SC_DIRTY]
    cmp r0, #1
    bne sc_un_put
    and r0, r6, #31
    cmp r0, #16
    rsbhs r0, r0, #31
    mov r7, r0, lsl #2
    add r7, r7, #1
sc_un_put:
    add r3, r4, #SC_WRITE_LED * 8
    ldrb r0, [r3, #SC_LED_VALUE]
    cmp r0, r7
    beq sc_un_out
    cmp r0, #0
    beq sc_un_write
    tst r0, #1                  ; a value of the firmware (even, or 255): its LED
    beq sc_un_out
    cmp r0, #128
    bhs sc_un_out
sc_un_write:
    strb r7, [r3, #SC_LED_VALUE]
    add r3, r3, #0x2C0
    strb r7, [r3, #SC_LED_VALUE]
    mov r0, r4
    mov r1, #SC_WRITE_LED
    mov r2, #1
    ldr r12, =SC_LEDSEND
    blx r12
sc_un_out:
    pop {r4-r7, pc}
.align 4
shortcut_pool:
.pool
shortcut_end:
