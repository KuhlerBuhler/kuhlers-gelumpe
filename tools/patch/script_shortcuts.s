; Shortcuts with EXIT held on the main screen (device wish 18.10.):
;   EXIT + WRITE  the pattern is saved into its own place at once: WRITE opens the firmware's Write window as always, and the next
;                 tick gives the window its second WRITE, which saves into the place the window starts on (the running pattern).
;   EXIT + pad    the sound of a part goes back to the values saved in the pattern bank: bytes 2 to 0x2F of the part (everything
;                 but last step and mute; the steps stay). TRIGGER mode resets the pad's part, the other modes the selected part.
;                 The firmware's pattern load (0xC004AB84) then applies the pattern in RAM onto itself, as after a pattern change.
; Not with EXIT held at power-on, not on the synth (SHORTCUTS 0, not measured there). The firmware addresses SC_LEDMGR (LED manager:
; +0xB58 pad mode, +0xB60 selected part), SC_PLAYER (returns the player, +0x318 the running number), SC_PATPTR (the pattern in RAM,
; its file at +4), SC_BANK (the pattern bank, 0x4000 each) and SC_LOAD ((pattern, source, 1): the firmware's pattern load) come
; with the build (script_hooks.py).
.equ SC_EXIT, -0x04             ; bytes in front of MENU_STATE (behind the MX_ bytes of the menu): 1 while EXIT is held
.equ SC_SAVE, -0x03             ; 1 to SC_WAIT: frames left for the Write window to open after EXIT + WRITE
.equ SC_RESET, -0x02            ; 1 to 16: the part (plus 1) the next tick resets
.equ SC_DIRTY, -0x01            ; 1 while the pattern in RAM differs from its place in the bank (sc_unsaved)
.equ SC_KEY_EXIT, 0x0D
.equ SC_KEY_WRITE, 0x0E
.equ SC_WINDOW, 18              ; the firmware's Write window (screen 0x12)
.equ SC_WAIT, 25                ; one second
.equ SC_TRIGGER, 3              ; pad mode TRIGGER (4 SEQUENCER, 5 KEYBOARD)
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
    cmp r0, #SC_TRIGGER
    ldrne r1, [r2, #0xB60]
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
sc_tick_done:
    bl sc_unsaved
    pop {r4-r6, pc}

; The WRITE LED breathes while the pattern in RAM differs from its place in the bank (unsaved, device wish 19.10.): every 8 frames
; the two are compared word by word (byte 0x3C left out, the firmware rewrites it on every load), the LED goes from 1 to 61 and back in 32 frames (1.3 s), odd values only. The firmware writes
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
    cmp r3, #0x3C               ; byte 0x3C, MFX pad touched: each pattern load sets it anew (0 without HOLD), not an edit
    biceq r12, r12, #0xFF
    biceq r0, r0, #0xFF
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
