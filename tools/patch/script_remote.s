; Keys from the computer, for tests on the device (KORG.press in the console). KORG.exec runs in the CommandTask and only leaves a
; command word here; the frame hook (UI task) takes it and goes through the firmware's key and encoder handlers, the way
; korg.play does. A key is pressed in one frame and released in the next. The work area of the card loader is FF at power-on,
; so only a word with RM_MARK in its top byte counts. Not on the synth (REMOTE 0, its encoder handler is not measured).
.equ RM_AT, 0xFC0               ; in the card work area, between the description of the import list and the state of fx_card.s
.equ RM_CMD, 0                  ; RM_MARK << 24 | value << 16 | index << 8 | kind; set to 0 when taken
.equ RM_HELD, 4                 ; RM_MARK << 24 | key: pressed in the last frame, released in this one
.equ RM_DONE, 8                 ; counts up once for every command done (a key after its release)
.equ RM_SIZE, 12
.equ RM_MARK, 0xA5
.equ RM_MARK_WORD, 0xA5000000
.equ RM_KEY, 1
.equ RM_ENCODER, 2              ; value: the delta, signed

; From the frame hook (UI task), after shortcut_tick. Clobbers r0 to r3 and r12.
remote_tick:
    push {r4, r5, lr}
    mov r0, #REMOTE
    cmp r0, #0
    beq rm_return
    ldr r4, =HOOK_CARD
    add r4, r4, #RM_AT
    ldr r0, [r4, #RM_HELD]
    mov r1, r0, lsr #24
    cmp r1, #RM_MARK
    bne rm_command
    mov r1, #0
    str r1, [r4, #RM_HELD]
    and r0, r0, #0xFF
    ldr r12, =HW_PANEL_KEY
    blx r12
    b rm_done
rm_command:
    ldr r5, [r4, #RM_CMD]
    mov r1, r5, lsr #24
    cmp r1, #RM_MARK
    bne rm_return
    mov r1, #0
    str r1, [r4, #RM_CMD]
    mov r0, r5, lsr #8
    and r0, r0, #0xFF
    and r1, r5, #0xFF
    cmp r1, #RM_KEY
    beq rm_key
    cmp r1, #RM_ENCODER
    bne rm_done
    mov r1, r5, lsl #8
    mov r1, r1, asr #24
    ldr r12, =HW_ENCODER
    blx r12
    b rm_done
rm_key:
    orr r1, r0, #RM_MARK_WORD
    str r1, [r4, #RM_HELD]
    mov r1, #1
    ldr r12, =HW_PANEL_KEY
    blx r12
    b rm_return
rm_done:
    ldr r0, [r4, #RM_DONE]
    add r0, r0, #1
    str r0, [r4, #RM_DONE]
rm_return:
    pop {r4, r5, pc}
.pool

; Found by the console (src/remote.mjs) in the code of a VSB: this word, then the address of the command word.
remote_sign:
    .word 0x544D4552
    .word HOOK_CARD+RM_AT
