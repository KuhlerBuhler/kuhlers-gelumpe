; korg.midi (API 30): channel messages out through the firmware's own MIDI senders, and the event midiIn for every channel message
; the firmware receives. The senders write the bytes to DIN out and USB as the firmware's notes and CCs go out; the MIDI SEND
; FILTER of the GLOBAL menu applies as it does to the firmware's own messages: notes, CCs and the other short messages go out
; only with the filter Off, a program change also with Short (docs/messungen/2026-11-11-plugin-api30-midi.md).
.equ MIDI_SEND3, 0xC002775C        ; (_, status, data1, data2): three bytes to both ports
.equ MIDI_SEND2, 0xC002779C        ; (_, status, data1): two bytes to both ports
.equ MIDI_GLOBAL, 0xC033E6A0       ; -> the global object: +0x2D the global MIDI channel 0 to 15, +0x2E the MIDI SEND FILTER
.equ MIDI_CHANNEL_AT, 0x2D
.equ MIDI_FILTER_AT, 0x2E
.equ MIDI_FILTER_PROGRAM, 2        ; Short + Program: the filter value that also keeps program changes in
.equ MIDI_IN_FN, 0xC003BB00        ; the firmware's handler of a received channel message (obj, status, data1, data2, ...)
.equ MIDI_IN_AT, 0xC002B2D8        ; the receive loop's call of it, replaced by a branch to script_midi_in_hook
.equ MIDI_FREE, KEY_HOLD+16        ; a bit per message type (status >> 4) - 8 that reaches the firmware, folded by holds_sync
.align 4

; r0 channel -1 (the global channel) or 0 to 15, r1 the status nibble -> r1 the status byte; EQ when the filter keeps it in,
; r2 the filter value. Clobbers r0, r2.
midi_status:
    ldr r2, =MIDI_GLOBAL
    ldr r2, [r2]
    cmp r0, #0
    ldrblt r0, [r2, #MIDI_CHANNEL_AT]
    and r0, r0, #15
    orr r1, r1, r0
    ldrb r2, [r2, #MIDI_FILTER_AT]
    cmp r2, #0
    bx lr

; korg.midi.cc(channel, cc, value) -> 1 sent, 0 kept in by the MIDI SEND FILTER
script_midi_cc_glue:
    mov r12, #0xB0
    b midi_three
; korg.midi.noteOn(channel, note, velocity)
script_midi_note_on_glue:
    mov r12, #0x90
    b midi_three
; korg.midi.noteOff(channel, note): velocity 64, as the firmware's pads send it
script_midi_note_off_glue:
    mov r2, #0x40
    mov r12, #0x80
; r0 channel, r1 data1, r2 data2, r12 the status nibble
midi_three:
    push {r4, r5, lr}
    mov r4, r1
    mov r5, r2
    mov r1, r12
    bl midi_status
    bne midi_kept
    mov r2, r4
    mov r3, r5
    ldr r12, =MIDI_SEND3
    b midi_send
; korg.midi.program(channel, program)
script_midi_program_glue:
    push {r4, r5, lr}
    mov r4, r1
    mov r1, #0xC0
    bl midi_status
    cmp r2, #MIDI_FILTER_PROGRAM
    beq midi_kept
    mov r2, r4
    ldr r12, =MIDI_SEND2
; r1 to r3 the arguments, r12 the sender: called on an 8 byte aligned stack
midi_send:
    mov r4, sp
    bic sp, sp, #7
    mov r0, #0
    blx r12
    mov sp, r4
    mov r0, #1
    mov r1, #ERR_OK
    pop {r4, r5, pc}
midi_kept:
    mov r0, #0
    mov r1, #ERR_OK
    pop {r4, r5, pc}

; korg.midi.hold(type, on): r0 the message type 0 to 6 (note off, note on, poly pressure, CC, program, channel pressure, pitch
; bend), r1 1 keeps it from the firmware, 0 gives it back (for this plugin). Bits 8 to 14 of the plugin's pad word.
script_midi_hold_glue:
    push {lr}
    mov r12, r0
    bl hold_entry
    ldr r0, [r3, #HD_PAD]
    add r12, r12, #HD_MIDI_SHIFT
    mov r2, #1
    cmp r1, #0
    biceq r0, r0, r2, lsl r12
    orrne r0, r0, r2, lsl r12
    str r0, [r3, #HD_PAD]
    bl hold_sync_caller
    mov r0, #0
    mov r1, #ERR_OK
    pop {pc}

; Entered by a branch from the receive loop's call of the firmware's handler (r0 its object, r1 status, r2 data1, r3 data2, more
; on the stack): a channel message is posted as midiIn, then goes to the handler unless a running plugin keeps its type.
script_midi_in_hook:
    ldr lr, =MIDI_IN_AT+4
    cmp r1, #0x80
    blo midi_in_pass
    cmp r1, #0xF0
    bhs midi_in_pass
    push {r0-r3, r12, lr}
    ldr r0, =HOOK_RUNTIME
    ldr r12, [r0, #RT_ARMED]
    cmp r12, #1
    bne midi_in_free
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    beq midi_in_free
    cmn r12, #1
    beq midi_in_free
    ldr r12, [r12, #0x18]
    tst r12, #0x2000
    bne midi_in_free
    sub sp, sp, #16
    mov r12, #EV_MIDI_IN
    str r12, [sp]
    and r1, r1, #0xFF
    and r2, r2, #0x7F
    and r3, r3, #0x7F
    str r1, [sp, #4]
    str r2, [sp, #8]
    str r3, [sp, #12]
    mov r1, sp
    bl script_ring_post
    add sp, sp, #16
midi_in_free:
    ldr r1, [sp, #4]
    mov r1, r1, lsr #4
    sub r1, r1, #8
    ldr r0, =MIDI_FREE
    ldr r0, [r0]
    mov r0, r0, lsr r1
    tst r0, #1
    pop {r0-r3, r12, lr}
    bxeq lr
midi_in_pass:
    ldr pc, =MIDI_IN_FN
.pool
script_midi_in_hook_end:
