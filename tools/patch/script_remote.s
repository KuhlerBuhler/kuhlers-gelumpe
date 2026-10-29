; The device from the computer, for tests on the device without anyone at it (KORG.press in the console, tools/device/remote_press.py).
; KORG.exec runs in the CommandTask and only leaves a command word here; the frame hook (UI task) takes it and puts a panel message
; into the queue the panel controller's reader fills (PANEL_QUEUE), so the CsTask hands it to the firmware's dispatcher exactly as a
; message from the panel: every key, pad, knob, encoder and the touchpad, through the input filter of the runtime too. A key is
; pressed in one frame and released in the next. The work area of the card loader is FF at power-on, so only a word with RM_MARK
; in its top byte counts.
.equ RM_AT, 0xFC0               ; in the card work area, between the description of the import list and the state of fx_card.s
.equ RM_CMD, 0                  ; RM_MARK << 24 | value << 16 | index << 8 | kind; set to 0 when taken
.equ RM_HELD, 4                 ; RM_MARK << 24 | key: pressed in the last frame, released in this one
.equ RM_DONE, 8                 ; counts up once for every command done (a key after its release)
.equ RM_SIZE, 12
.equ RM_MSG_AT, 0xFA0           ; RM_MESSAGE: the 8 bytes of a panel message (type, four data bytes, three unused)
.equ RM_LCD_AT, 0xFA8           ; RM_LCD_OFF once the display was switched off for the test mode, anything else: on
.equ RM_KEYS_AT, 0xFAC          ; what the computer holds down: a bit per key 0 to 63 (8 bytes), then a bit per pad (4 bytes)
.equ RM_IDLE_AT, 0xFB8          ; frames since the last command while something is held
.equ RM_INIT_AT, 0xFBC          ; RM_INIT_MARK once the three above are set up (the area is FF at power-on)
.equ RM_INIT_MARK, 0xA5A5A5A5
.equ RM_IDLE_FRAMES, 250        ; 10 s without a command: what the computer still holds is let go (a dropped link)
.equ RM_MARK, 0xA5
.equ RM_MARK_WORD, 0xA5000000
.equ RM_LCD_OFF, 0xA50000AE
.equ RM_KEY, 1
.equ RM_ENCODER, 2              ; value: the delta, signed
.equ RM_MESSAGE, 3              ; the panel message at RM_MSG_AT
.equ RM_TEST, 4                 ; value: korg.system.testMode (plugins only read it)
.equ RM_RELEASE, 5              ; lets go of every key and pad the computer holds
.equ PANEL_QUEUE, 0xC033E57C    ; the queue of panel messages the CsTask hands to the dispatcher; the panel's reader puts with QUEUE_PUT
.equ QUEUE_PUT, 0xC0024AFC      ; (queue, 8 bytes): copies; the event it sets for the first message is refused outside a task
.equ EVENT_SET, 0xC0000E9C      ; (group, bits) from outside a task, where the frame hook runs (the task call answers -25 there)
.equ IRQ_OFF, 0xC0000040        ; -> r0 the CPSR before
.equ IRQ_RESTORE, 0xC0000050    ; (r0 the CPSR before)
.equ APO_TIMER, 0xC033E6B4      ; Auto Power Off: *APO_TIMER + 0x18 counts 2 ms ticks down from 7200000, every panel byte starts it again
.equ APO_TICKS, 7200000
.equ LCD_SENT, 0xC031B710       ; the copy of the display buffer as last sent, 8 pages of 128 bytes; a page that differs is sent again

; From the frame hook (UI task), after shortcut_tick. A command is counted done only once its message is in the queue; a full queue
; leaves it uncounted (a key's release is tried again in the next frame). Clobbers r0 to r3 and r12.
remote_tick:
    push {r4, r5, lr}
    mov r0, #REMOTE
    cmp r0, #0
    beq rm_return
    bl testmode_tick
    bl rm_held_tick
    ldr r4, =HOOK_CARD
    add r4, r4, #RM_AT
    ldr r0, [r4, #RM_HELD]
    mov r1, r0, lsr #24
    cmp r1, #RM_MARK
    bne rm_command
    and r0, r0, #0xFF
    mov r0, r0, lsl #8          ; type 0 (key), the key, 0 (released)
    mov r1, #0
    bl rm_post
    cmp r0, #0
    beq rm_return
    mov r1, #0
    str r1, [r4, #RM_HELD]
    b rm_done
rm_command:
    ldr r5, [r4, #RM_CMD]
    mov r1, r5, lsr #24
    cmp r1, #RM_MARK
    bne rm_return
    mov r1, #0
    str r1, [r4, #RM_CMD]
    ldr r0, =HOOK_CARD+RM_IDLE_AT
    str r1, [r0]
    and r1, r5, #0xFF
    cmp r1, #RM_KEY
    beq rm_key
    cmp r1, #RM_ENCODER
    beq rm_encoder
    cmp r1, #RM_MESSAGE
    beq rm_message
    cmp r1, #RM_RELEASE
    beq rm_release
    cmp r1, #RM_TEST
    bne rm_done
    ands r2, r5, #0xFF0000
    movne r2, #1
    ldr r0, =objects_test_mode
    strb r2, [r0]
    bl testmode_apply
    b rm_done
rm_release:
    bl rm_release_all
    b rm_done
rm_message:
    ldr r0, =HOOK_CARD+RM_MSG_AT
    ldmia r0, {r0, r1}
    bl rm_post
    b rm_posted
rm_encoder:
    and r0, r5, #0xFF00         ; type 1, the encoder, 0, the delta
    orr r0, r0, #1
    and r1, r5, #0xFF0000
    orr r0, r0, r1, lsl #8
    mov r1, #0
    bl rm_post
    b rm_posted
rm_key:
    mov r0, r5, lsr #8
    and r5, r0, #0xFF
    mov r0, r5, lsl #8
    orr r0, r0, #0x10000        ; type 0, the key, 1 (pressed)
    mov r1, #0
    bl rm_post
    cmp r0, #0
    orrne r1, r5, #RM_MARK_WORD
    strne r1, [r4, #RM_HELD]
    b rm_return
rm_posted:
    cmp r0, #0
    beq rm_return
rm_done:
    ldr r0, [r4, #RM_DONE]
    add r0, r0, #1
    str r0, [r4, #RM_DONE]
rm_return:
    pop {r4, r5, pc}

; r0, r1: the 8 bytes of a panel message, as the panel controller's reader queues them -> r0 0 when the queue was full. The queue is
; not guarded against two writers, so the copy runs with interrupts off; the event that wakes the CsTask needs them on and follows.
; The frame hook runs outside a task (task number 0), so the event goes through the call for that context. Counts as panel input for
; Auto Power Off, as the reader does for every byte, and notes what is held down. Clobbers r1 to r3 and r12.
rm_post:
    push {r4-r8, lr}
    sub sp, sp, #8
    stmia sp, {r0, r1}
    mov r5, r0
    mov r6, r1
    bl IRQ_OFF
    mov r4, r0
    ldr r0, =PANEL_QUEUE
    mov r1, sp
    bl QUEUE_PUT
    mov r7, r0
    mov r0, r4
    bl IRQ_RESTORE
    cmp r7, #0
    beq rm_post_out
    ldr r0, =PANEL_QUEUE
    ldr r1, [r0, #0x1c]
    ldr r0, [r0, #8]
    bl EVENT_SET
    bl testmode_keep_awake
    mov r0, r5
    mov r1, r6
    bl rm_held_note
rm_post_out:
    mov r0, r7
    add sp, sp, #8
    pop {r4-r8, pc}

; r0, r1 a message that went out: a key (type 0) or a pad (type 4) is noted as held or let go. Clobbers r0 to r3 and r12.
rm_held_note:
    and r2, r0, #0xFF
    mov r3, r0, lsr #8
    and r3, r3, #0xFF
    cmp r2, #4
    beq rm_note_pad
    cmp r2, #0
    bxne lr
    cmp r3, #64
    bxhs lr
    mov r1, r0, lsr #16
    and r1, r1, #0xFF
    ldr r2, =HOOK_CARD+RM_KEYS_AT
    b rm_note_bit
rm_note_pad:
    cmp r3, #32
    bxhs lr
    and r1, r1, #0xFF
    ldr r2, =HOOK_CARD+RM_KEYS_AT+8
rm_note_bit:
    mov r12, r3, lsr #5
    add r2, r2, r12, lsl #2
    and r3, r3, #31
    mov r12, #1
    ldr r0, [r2]
    cmp r1, #0
    orrne r0, r0, r12, lsl r3
    biceq r0, r0, r12, lsl r3
    str r0, [r2]
    bx lr

; Lets go of every key and pad the computer holds, with the messages the panel sends when a finger leaves it. Clobbers r0 to r3, r12.
rm_release_all:
    push {r4, lr}
    mov r4, #0
rm_release_keys:
    ldr r0, =HOOK_CARD+RM_KEYS_AT
    mov r1, r4, lsr #5
    ldr r0, [r0, r1, lsl #2]
    and r1, r4, #31
    mov r2, #1
    tst r0, r2, lsl r1
    movne r0, r4, lsl #8        ; type 0, the key, 0 (released)
    movne r1, #0
    blne rm_post
    add r4, r4, #1
    cmp r4, #64
    blo rm_release_keys
    mov r4, #0
rm_release_pads:
    ldr r0, =HOOK_CARD+RM_KEYS_AT+8
    ldr r0, [r0]
    mov r2, #1
    tst r0, r2, lsl r4
    movne r0, r4, lsl #8
    orrne r0, r0, #4            ; type 4, the pad, velocity 0, off
    movne r1, #0
    blne rm_post
    add r4, r4, #1
    cmp r4, #32
    blo rm_release_pads
    pop {r4, pc}

; Every frame: sets up what is held once after power-on, and lets go of it after RM_IDLE_FRAMES without a command. Clobbers r0 to r3, r12.
rm_held_tick:
    push {r4, lr}
    ldr r4, =HOOK_CARD+RM_KEYS_AT
    ldr r0, [r4, #RM_INIT_AT-RM_KEYS_AT]
    ldr r1, =RM_INIT_MARK
    cmp r0, r1
    beq rm_held_ready
    str r1, [r4, #RM_INIT_AT-RM_KEYS_AT]
    mov r0, #0
    str r0, [r4]
    str r0, [r4, #4]
    str r0, [r4, #8]
    str r0, [r4, #RM_IDLE_AT-RM_KEYS_AT]
rm_held_ready:
    ldr r0, [r4]
    ldr r1, [r4, #4]
    orr r0, r0, r1
    ldr r1, [r4, #8]
    orrs r0, r0, r1
    streq r0, [r4, #RM_IDLE_AT-RM_KEYS_AT]
    popeq {r4, pc}
    ldr r0, [r4, #RM_IDLE_AT-RM_KEYS_AT]
    add r0, r0, #1
    cmp r0, #RM_IDLE_FRAMES
    movhs r0, #0
    str r0, [r4, #RM_IDLE_AT-RM_KEYS_AT]
    blhs rm_release_all
    pop {r4, pc}

; korg.system.keepAwake(): Auto Power Off starts its 4 hours again; a negative counter (Auto Power Off off) stays. Clobbers r0, r1.
testmode_keep_awake:
    ldr r0, =APO_TIMER
    ldr r0, [r0]
    cmp r0, #0
    bxeq lr
    ldr r1, [r0, #0x18]
    cmp r1, #0
    ldrge r1, =APO_TICKS
    strge r1, [r0, #0x18]
    bx lr

; Every frame while the test mode is on: the device stays awake, and the firmware stays kept from the LEDs (a plugin's
; korg.ledHold(0) does not reach the firmware then). Clobbers r0 to r3.
testmode_tick:
    ldr r0, =objects_test_mode
    ldrb r0, [r0]
    cmp r0, #0
    bxeq lr
    push {lr}
    bl testmode_keep_awake
    mov r0, #1
    bl testmode_led_hold
    pop {pc}

; r0 the firmware's LED hold byte (1 keeps it from sending LEDs). Clobbers r1.
testmode_led_hold:
    ldr r1, =HW_LED_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    cmnne r1, #1
    strbne r0, [r1, #HW_LED_HOLD_BYTE]
    bx lr

; After korg.system.testMode was set (RM_TEST). On: the firmware keeps from the LEDs, every LED of the runtime
; goes out once with 0 (script_led_try_send sends 0 while the test mode is on), the light pins go off; the display goes off at
; its next page (lcd_invert_hook). Off: the LEDs go back to whoever had them (a plugin's korg.ledHold, else the firmware sends
; every LED again), the plugins' own LED values go out again, the light follows the settings. Clobbers r0 to r3 and r12.
testmode_apply:
    push {r4-r6, lr}
    ldr r0, =LCD_SENT           ; every page goes out at the next frame, and with the first one lcd_invert_hook switches the display
    mov r1, #0
testmode_redraw:
    ldrb r2, [r0, r1, lsl #7]
    eor r2, r2, #0xFF
    strb r2, [r0, r1, lsl #7]
    add r1, r1, #1
    cmp r1, #8
    blo testmode_redraw
    ldr r4, =HOOK_RUNTIME
    ldr r5, =RT_LED
    add r5, r4, r5
    ldr r0, =objects_test_mode
    ldrb r0, [r0]
    cmp r0, #0
    beq testmode_off
    mov r0, #1
    bl testmode_led_hold
    add r1, r5, #SCRIPT_LED_PENDING
    mov r2, #1
    mov r3, #0
testmode_on_leds:
    strb r2, [r1, r3]
    add r3, r3, #1
    cmp r3, #SCRIPT_LED_COUNT
    blo testmode_on_leds
    ldr r0, =GPIO_BASE
    mov r1, #0
    mov r2, #3
    mov r3, #0x38
    bl GPIO_WRITE
    pop {r4-r6, pc}
testmode_off:
    ldr r0, [r4, #SCRIPT_CONTROL_LED_HOLD]
    bl testmode_led_hold
    ldr r0, [r4, #SCRIPT_CONTROL_LED_HOLD]
    cmp r0, #0
    bne testmode_off_pending
    ldr r6, =HW_LED_MANAGER
    ldr r6, [r6]
    cmp r6, #0
    cmnne r6, #1
    beq testmode_off_pending
    mov r4, #0
testmode_off_refresh:
    mov r0, r6
    mov r1, r4
    mov r2, #1
    ldr r12, =HW_LED_REFRESH
    blx r12
    add r4, r4, #1
    cmp r4, #HW_LED_LAST+1
    blo testmode_off_refresh
testmode_off_pending:
    mov r3, #0
testmode_off_leds:
    add r1, r5, #SCRIPT_LED_VALID
    ldrb r0, [r1, r3]
    ands r0, r0, #SCRIPT_LED_VALID_DESIRED
    movne r0, #1
    add r1, r5, #SCRIPT_LED_PENDING
    strb r0, [r1, r3]
    add r3, r3, #1
    cmp r3, #SCRIPT_LED_COUNT
    blo testmode_off_leds
    bl menu_look_apply
    pop {r4-r6, pc}
.pool

; Found by the console (src/remote.mjs) in the code of a VSB: "REMT", the address of the command word; then "RMT2", the address of
; RM_MSG_AT, of korg.system.testMode and of this build's sleep for the host's stub (the controls of every kind and the test mode; a
; runtime without them has other words there).
remote_sign:
    .word 0x544D4552
    .word HOOK_CARD+RM_AT
    .word 0x32544D52
    .word HOOK_CARD+RM_MSG_AT
    .word objects_test_mode
    .word OS_WAIT
