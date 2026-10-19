"""Builds the note assistant patch (docs/messungen/2026-10-15-note-assistant.md) for firmware 2.02 with Hacktribe and Korg's own 2.02.

In KEYBOARD mode, right after a note was played on a pad, the pads of the notes that fit light up in a dim pink
(the pad's red and blue LED together, very low), so the notes that do not fit stay dark:

    fits    a pad whose note is a unison or octave, a minor or major third, a fourth, a fifth or a minor or major sixth
            away from the played note (0, 3, 4, 5, 7, 8 or 9 semitones, modulo 12). The pads of the keyboard layout are the
            notes of the pattern's own key and scale already (the firmware builds the layout from them, measured), so that
            half of "fits" needs no check of its own.
    when    from the next tick of the LED manager (40 ms) after a pad went down or the sequencer played a note of the selected part
            that a pad of the layout holds, and off again 38 ticks (1.52 s) after it, if no new note came; a new note replaces them
            at once.
    never   on a pad the firmware lights itself (the pressed pad and the pads of the same note, the step LEDs), outside the
            KEYBOARD mode, or outside the main screen.
    part    the pad of the selected part holds the firmware's blue 255. While the hints are on it is a pad like any other: its hint
            colour when its note fits, dark when not (device feedback 2026-10-16: with the blue left on, the note of that pad could
            not be told apart). The patch remembers that pad (S_PARTPAD) and gives it the firmware's blue 255 back when the hints
            end (timeout, other pad mode, other screen, octave, key or scale, the setting off, a note of the sequencer), because the
            firmware does not light it again by itself.

The patch is on only when EXIT was not held at power-on, a card was seen since power-on and the setting word NA_SETTING is not 0 (the BLECH
menu page NOTE ASSIST in the BLECH list writes it, as bit 4 of the flags of the settings file: a file without the bit, or no file,
means ON; never written means on).

    python3 tools/patch/note_assist.py --vsb SYSTEM.VSB [--out data/patches/note-assistant.json]

Three hooks, all of them first or last instructions of firmware functions, none of them changes what the firmware does:
  keyboard pad  0xC0044B3C, the keyboard's pad event (object, pad, on, velocity): remembers the note of a pad that goes down
  pad light     0xC008870C, the firmware's own pad light for a note (manager, part, note, velocity): a note on of the selected
                part (from a pad or from the sequencer) takes the hints away before the firmware lights its pads, because the
                firmware does not write a pad whose LED already holds a value on a note on
  LED tick      0xC00877D4, the last instruction of the 40 ms task of the LED manager: counts the time and brings the hints
                where they belong (shows, keeps, or takes away)

The LEDs go through the LED manager's own tables and its own send function (0xC00875F4), the way the firmware lights its pads.
The two values the patch writes are odd, the firmware writes only 0, 192, 255 or twice a velocity (measured: even), so
the patch tells its own LEDs from the firmware's by value and keeps no list: whatever holds one of its values and should not,
is taken away, and a pad that holds any other value is the firmware's and is left alone.
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import arm  # noqa: E402
import ramdecl  # noqa: E402
import synthaddr  # noqa: E402
import card_gate  # noqa: E402

HEADER = 0x100
RAM = 0xC0000000

CODE_AT = 0xC0189000            # free (FF) in the image, behind the TAP motion patch (0xC0188000 to 0xC0189000)
CODE_END = 0xC0189800
STATE = 0xC0189F00              # run time state, in RAM only; FF there means "nothing"
STATE_END = 0xC0189F40
S_SETTING, S_SINCE, S_NOTE, S_PAD, S_PARTPAD, S_FADE, S_LEVEL = 0, 4, 8, 0xC, 0x10, 0x14, 0x20
S_DOWN = 0x18
NA_SETTING = STATE + S_SETTING  # the setting word the BLECH menu will write: never written (FFFFFFFF) or 1 is on, 0 is off
FLAG_OFF_BIT = 4                # bit of the settings file's flags that means "OFF" (bits 0 to 3 are taken, docs/plugins.md)

KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13, measured on the device 10.10.)

LEVEL_HIGH, LEVEL_MID, LEVEL_LOW = 63, 41, 21   # the red LED of a hint, of 255 (the blue gets 5/8, odd): about 25, 16 and 8 percent
# the level by the interval to the note, 0 to 11 semitones: unison and fifth bright, the thirds and the fourth middle, the sixths dim, the
# rest dark (the notes a step of the scale away get the middle level from their place in the layout)
LEVELS = (LEVEL_HIGH, 0, 0, LEVEL_MID, LEVEL_MID, LEVEL_MID, 0, LEVEL_HIGH, LEVEL_LOW, LEVEL_LOW, 0, 0)
# CHORD: by the interval of the roots: fourth and fifth (IV, V) bright, second, minor third and major sixth (ii, vi and back) middle,
# the same chord, major third, minor sixth and minor seventh dim
CHORD_LEVELS = (LEVEL_LOW, 0, LEVEL_MID, LEVEL_MID, LEVEL_LOW, LEVEL_HIGH, 0, LEVEL_HIGH, LEVEL_LOW, LEVEL_MID, LEVEL_LOW, 0)
FADE_TICKS = 3                  # while the pattern plays a level loses 2 every 3 ticks (120 ms): bright 3.7 s, middle 2.5 s, dim 1.3 s

PAD_HOOK = 0xC0044B3C           # push {r4, r5, r6, r7, r8, lr}
PAD_WORD = 0xE92D41F0
PAD_BODY = 0xC0044B40
LIGHT_HOOK = 0xC008870C         # push {r3, r4, r5, r6, r7, r8, sb, lr}
LIGHT_WORD = 0xE92D43F8
LIGHT_BODY = 0xC0088710
TICK_HOOK = 0xC00877D4          # pop {r4, r5, r6, pc}, the end of the LED manager's tick
TICK_WORD = 0xE8BD8070


FIRMWARE_PLACES = ["PAD_HOOK", "PAD_BODY", "LIGHT_HOOK", "LIGHT_BODY", "TICK_HOOK"]    # the .equ lines of SOURCE hold the other firmware places
BUILD = "hacktribe"


def use_build(build):
    """For the synth the firmware's places have their own addresses (data/synth-map/); the patch's code and state area stay where they are."""
    global BUILD
    BUILD = "synth" if build == "synth" else "hacktribe"
    synthaddr.use(globals(), FIRMWARE_PLACES, build)


def sha(data):
    return hashlib.sha256(data).hexdigest()


SOURCE = """
.equ PANEL, 0xC033E6F8          ; pointer to the panel object, +0x18 the keys held at power-on
.equ FATFS, 0xC06A010C          ; FatFs volume table: first entry is the volume of the card, its byte 0 is the mounted type (Sampler builds only)
.equ LEDMGR_PTR, 0xC0345A1C     ; pointer to the LED manager; +0xB58 the pad mode (5 is KEYBOARD), +0xB60 the selected part, +0xB98 the plugin LED lock
.equ KBOBJ_PTR, 0xC0348880      ; pointer to the keyboard object; +0x40 the 16 notes of the layout (octave and scale in, key in or not)
.equ SCREEN_PTR, 0xC03404C0     ; pointer to the screen manager, +0x2C the screen number
.equ LED_SEND, 0xC00875F4       ; (manager, led, force): sends the LED's entry to the panel; force 1 skips the comparison with the copy
.equ MODE_AT, 0xB58
.equ PART_AT, 0xB60
.equ LOCK_AT, 0xB98
.equ MODE_KEYBOARD, 5
.equ MODE_CHORD, 6
.equ PAD_HELD, 192              ; the firmware's red on a pad that is held
.equ MAIN_SCREEN, 1
.equ LED_PAD_FIRST, 0x2C        ; pad n: red LED 0x2C + 2n, blue LED 0x2D + 2n
.equ LED_VALUE, 0x4E            ; manager + 0x4E + 8 * led: the brightness the firmware wants (the entry of the first table)
.equ LED_VALUE2, 0x2C0          ; the same entry in the second table lies 0x2C0 further, where the firmware's pad light writes it too
.equ KILL, @KILL@
.equ STATE, @STATE@
.equ S_SETTING, @S_SETTING@     ; NA_SETTING: FFFFFFFF or 1 is on, 0 is off
.equ S_SINCE, @S_SINCE@         ; 0: a new note, the next tick gives the levels; 1 after that, FFFFFFFF at start
.equ S_NOTE, @S_NOTE@           ; the note of the last pad that went down (0 to 127), FFFFFFFF none
.equ S_PAD, @S_PAD@             ; and that pad, 0 to 15
.equ S_PARTPAD, @S_PARTPAD@     ; the pad of the selected part whose blue the patch has taken (hint or dark), FFFFFFFF none
.equ BLUE_PART, 255             ; the firmware's blue on the pad of the selected part
.equ WINDOW, 0x10000            ; bit 16 of the pad mask: the hint window is open (pads that do not fit are wanted dark, the part's pad included)
.equ S_FADE, @S_FADE@           ; ticks since the last fade step
.equ S_LEVEL, @S_LEVEL@         ; 16 bytes: the level of each pad's hint, the red LED's brightness (0 none)
.equ S_DOWN, @S_DOWN@           ; CHORD: the pad last seen held (FFFFFFFF none)
.equ LEVEL_MID, @LEVEL_MID@
.equ FADE, @FADE@
.equ TRANSPORT, 0xC06BC318      ; the transport state: 0 stopped, 1 playing, 2 paused, 3 record ready, 4 recording
.equ PAD_BODY, @PAD_BODY@
.equ LIGHT_BODY, @LIGHT_BODY@

.org @CODE_AT@

; ===================================================== is the patch on
; r0 = 1 when EXIT was not held at power-on, a card was seen since power-on and the setting is not off. Clobbers r0 and r12.
; Writes only the card latch (tools/patch/card_gate.py), the first time a card is there.
na_active:
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    beq nx_no
    ldr r0, [r12, #0x18]
    tst r0, #KILL
    bne nx_no
@CARD_CHECK@    ldr r12, =STATE
    ldr r12, [r12, #S_SETTING]
    cmn r12, #1
    moveq r0, #1
    bxeq lr
    ands r0, r12, #1
    bxne lr
nx_no:
    mov r0, #0
    bx lr

; On the main screen: r0 = 1 when the pads are in KEYBOARD mode, 2 in CHORD mode with a scale of seven notes (the keyboard's table
; holds the octave twice, places 7 and 8; the firmware builds the chords of other scales from scales of its own), else 0.
; Clobbers r0, r1 and r12. Reads memory only.
na_kbd:
    ldr r12, =LEDMGR_PTR
    ldr r12, [r12]
    cmp r12, #0
    beq nk_no
    ldr r0, [r12, #MODE_AT]
    cmp r0, #MODE_KEYBOARD
    moveq r1, #1
    beq nk_screen
    cmp r0, #MODE_CHORD
    bne nk_no
    ldr r12, =KBOBJ_PTR
    ldr r12, [r12]
    cmp r12, #0
    beq nk_no
    ldrb r0, [r12, #0x47]
    ldrb r1, [r12, #0x48]
    cmp r0, r1
    bne nk_no
    mov r1, #2
nk_screen:
    ldr r12, =SCREEN_PTR
    ldr r12, [r12]
    cmp r12, #0
    beq nk_no
    ldr r0, [r12, #0x2C]
    cmp r0, #MAIN_SCREEN
    moveq r0, r1
    bxeq lr
nk_no:
    mov r0, #0
    bx lr

; r1 = a pad, r9 = the keyboard object, r11 = the kind (1 KEYBOARD, 2 CHORD) -> r0 = the pad's note (KEYBOARD) or the root of its
; chord (CHORD: the lower row the places 0 to 7 of the table, the upper row goes on one step of the scale further than the
; keyboard's, measured over Dorian and Aeolian, docs/messungen/2026-10-19-notenassistent-helligkeit.md). Clobbers r0 to r3.
na_note:
    cmp r11, #2
    beq nn_chord
    cmp r1, #7
    addls r1, r1, #8
    subhi r1, r1, #8
    add r1, r9, r1
    ldrb r0, [r1, #0x40]
    bx lr
nn_chord:
    cmp r1, #8
    subhs r1, r1, #8
    addhs r1, r9, r1
    ldrbhs r0, [r1, #0x40]
    bxhs lr
    add r1, r1, #9
    cmp r1, #15
    addls r1, r9, r1
    ldrbls r0, [r1, #0x40]
    bxls lr
    ldrb r0, [r9, #0x4F]        ; past the table: one step on from its last note, the step of the octave's first two notes
    ldrb r2, [r9, #0x49]
    ldrb r3, [r9, #0x48]
    add r0, r0, r2
    sub r0, r0, r3
    bx lr

; ===================================================== one LED
; r0 = brightness, r1 = LED number, r4 = the LED manager. The value goes into both tables the way the firmware's own pad light
; writes it, then out through the firmware's send function (forced: the copy of what was sent is brought up to date by it).
; Clobbers r0 to r3 and r12 (the send function's own). A tail call: returns to the caller.
na_put:
    add r3, r4, r1, lsl #3
    strb r0, [r3, #LED_VALUE]
    add r3, r3, #LED_VALUE2
    strb r0, [r3, #LED_VALUE]
    mov r0, r4
    mov r2, #1
    b LED_SEND

; ===================================================== the pads
; r0 = a pad LED's value -> r0 = 1 when it is dark or one of the patch's values (odd and below 128; the firmware writes 0, 192, 255 or twice
; a velocity), else 0. na_ours: the same without dark. Leaves.
na_free:
    cmp r0, #0
    moveq r0, #1
    bxeq lr
na_ours:
    tst r0, #1
    moveq r0, #0
    bxeq lr
    cmp r0, #128
    movlo r0, #1
    movhs r0, #0
    bx lr

; r4 = the LED manager, r7 = 0: every hint off, 1: the pads as S_LEVEL wants them (the red LED's brightness, 0 none; the blue gets
; 5/8 of it, odd). The hint window is open while r7 is 1 and any pad has a level. For each pad: if it should show one and both of its
; LEDs are dark or hold values of the patch, they get the level; otherwise whatever LED of the pad holds a value of the patch is set
; dark again (a value that is not the patch's belongs to the firmware, the pad is not touched).
; The pad of the selected part (r8) is the exception: while the window is open it takes its hint or is dark, the blue 255 of the
; firmware replaced, and the pad is noted in S_PARTPAD; when the window is closed the noted pad gets the firmware's blue 255 back.
; Nothing is written while a plugin holds the LED lock. Clobbers r0 to r3, r5, r6, r8 to r11 and r12.
na_sync:
    ldrb r0, [r4, #LOCK_AT]
    cmp r0, #0
    bxne lr
    push {r7, lr}
    ldr r5, =STATE + S_LEVEL
    cmp r7, #0
    beq ns_part_check
    ldr r0, [r5]
    ldr r1, [r5, #4]
    orr r0, r0, r1
    ldr r1, [r5, #8]
    orr r0, r0, r1
    ldr r1, [r5, #12]
    orrs r0, r0, r1
    orrne r7, r7, #WINDOW
ns_part_check:
    ldr r8, [r4, #PART_AT]
    cmp r8, #15
    movhi r8, #16
    ldr r0, =STATE
    ldr r1, [r0, #S_PARTPAD]
    cmp r1, r8
    mvnne r1, #0
    strne r1, [r0, #S_PARTPAD]
    mov r6, #0
ns_loop:
    mov r9, r6, lsl #1
    add r9, r9, #LED_PAD_FIRST
    add r10, r4, r9, lsl #3
    mov r11, #0
    tst r7, #WINDOW
    ldrbne r11, [r5, r6]        ; the level this pad wants
    cmp r6, r8
    beq ns_part
    cmp r11, #0
    beq ns_release
    ldrb r0, [r10, #LED_VALUE]
    bl na_free
    cmp r0, #0
    beq ns_release
    ldrb r0, [r10, #LED_VALUE + 8]
    bl na_free
    cmp r0, #0
    beq ns_release
ns_show:
    ldrb r2, [r10, #LED_VALUE]
    cmp r2, r11
    movne r0, r11
    movne r1, r9
    blne na_put
    add r0, r11, r11, lsl #2
    mov r0, r0, lsr #3
    orr r0, r0, #1
    ldrb r3, [r10, #LED_VALUE + 8]
    cmp r3, r0
    addne r1, r9, #1
    blne na_put
    b ns_next
ns_release:
    ldrb r0, [r10, #LED_VALUE]
    bl na_ours
    cmp r0, #0
    movne r1, r9
    movne r0, #0
    blne na_put
    ldrb r0, [r10, #LED_VALUE + 8]
    bl na_ours
    cmp r0, #0
    addne r1, r9, #1
    movne r0, #0
    blne na_put
    b ns_next
ns_part:
    tst r7, #WINDOW
    beq ns_part_off
    ldrb r0, [r10, #LED_VALUE]
    bl na_free
    cmp r0, #0
    beq ns_next
    ldrb r0, [r10, #LED_VALUE + 8]
    cmp r0, #BLUE_PART
    beq ns_part_take
    bl na_free
    cmp r0, #0
    beq ns_next
ns_part_take:
    ldr r0, =STATE
    str r6, [r0, #S_PARTPAD]
    cmp r11, #0
    bne ns_show
    ldrb r0, [r10, #LED_VALUE]
    bl na_ours
    cmp r0, #0
    movne r1, r9
    movne r0, #0
    blne na_put
    ldrb r3, [r10, #LED_VALUE + 8]
    cmp r3, #0
    movne r0, #0
    addne r1, r9, #1
    blne na_put
    b ns_next
ns_part_off:
    ldr r0, =STATE
    ldr r1, [r0, #S_PARTPAD]
    cmp r1, r6
    bne ns_release
    ldrb r0, [r10, #LED_VALUE]
    bl na_ours
    cmp r0, #0
    movne r1, r9
    movne r0, #0
    blne na_put
    ldrb r0, [r10, #LED_VALUE + 8]
    bl na_free
    cmp r0, #0
    movne r0, #BLUE_PART
    addne r1, r9, #1
    blne na_put
    ldr r0, =STATE
    mvn r1, #0
    str r1, [r0, #S_PARTPAD]
ns_next:
    add r6, r6, #1
    cmp r6, #16
    bne ns_loop
    pop {r7, pc}

; ===================================================== the keyboard's pad event
; First instruction of the keyboard's pad event (r0 = the keyboard object, r1 = the pad, r2 = 1 down or 0 up, r3 = the velocity).
; A pad that goes down in KEYBOARD mode leaves its note, its number and the time 0 for the tick. The layout of the object is the
; firmware's: pad 0 to 7 are the notes 8 to 15 of the table, pad 8 to 15 the notes 0 to 7.
pad_hook:
    push {r0, r1, r2, r3, r4, r12, lr}
    cmp r2, #0
    beq ph_out
    mov r4, r0
    bl na_active
    cmp r0, #0
    beq ph_out
    push {r1}
    bl na_kbd
    pop {r1}
    cmp r0, #1
    bne ph_out
    cmp r1, #15
    bhi ph_out
    cmp r1, #7
    addls r3, r1, #8
    subhi r3, r1, #8
    add r3, r4, r3
    ldrb r0, [r3, #0x40]
    cmp r0, #0x7F
    bhi ph_out
    ldr r12, =STATE
    str r0, [r12, #S_NOTE]
    str r1, [r12, #S_PAD]
    mov r0, #0
    str r0, [r12, #S_SINCE]
ph_out:
    pop {r0, r1, r2, r3, r4, r12, lr}
    push {r4, r5, r6, r7, r8, lr}       ; the replaced first instruction
    b PAD_BODY

; ===================================================== the firmware's pad light
; First instruction of the function that lights the pads of a note (r0 = the LED manager, r1 = the part, r2 = the note, r3 = the
; velocity, 0 for a note off). A note on of the selected part takes every hint away, before the firmware writes its own LEDs (it
; writes a pad only if the pad is dark); the next tick brings back what still fits and is dark. In KEYBOARD mode the note becomes the
; one the hints are for, when a pad of the layout holds it: so a note of the sequencer shows its hints as a pad note does (device 18.10.).
light_hook:
    push {r0, r1, r2, r3, r4, r5, r6, r7, r8, r9, r10, r11, r12, lr}
    cmp r3, #0
    beq lh_out
    mov r4, r0
    ldr r0, [r4, #PART_AT]
    cmp r1, r0
    bne lh_out
    bl na_active
    cmp r0, #0
    beq lh_out
    push {r1}
    bl na_kbd
    pop {r1}
    cmp r0, #1
    bne lh_sync
    cmp r2, #0x7F
    bhi lh_sync
    ldr r0, =KBOBJ_PTR
    ldr r5, [r0]
    cmp r5, #0
    beq lh_sync
    mov r6, #0
lh_find:
    cmp r6, #7
    addls r1, r6, #8
    subhi r1, r6, #8
    add r1, r5, r1
    ldrb r0, [r1, #0x40]
    cmp r0, r2
    beq lh_found
    add r6, r6, #1
    cmp r6, #16
    bne lh_find
    b lh_sync
lh_found:
    ldr r12, =STATE
    str r2, [r12, #S_NOTE]
    str r6, [r12, #S_PAD]
    mov r0, #0
    str r0, [r12, #S_SINCE]
lh_sync:
    mov r7, #0
    bl na_sync
lh_out:
    pop {r0, r1, r2, r3, r4, r5, r6, r7, r8, r9, r10, r11, r12, lr}
    push {r3, r4, r5, r6, r7, r8, r9, lr}  ; the replaced first instruction
    b LIGHT_BODY

; ===================================================== the LED manager's tick, every 40 ms
; The last instruction of the tick (r6 = the LED manager) is where this runs. In KEYBOARD mode on the main screen a new note (S_SINCE 0)
; gives every pad its level from the interval to the note (LEVELS: unison and fifth bright, thirds and fourth middle, sixths dim) and the
; two neighbours of the note in the layout (a step of the scale up or down) at least the middle one (device wish 19.10.: the notes that fit
; best brighter). Stopped or paused the levels stay; while the pattern plays (transport 1, or 4 recording) every level loses 2 each FADE
; ticks and a pad that reaches 0 goes dark, so the notes that fit best stay longest. The note counts only while the table of the layout
; still holds it where the pad was (an octave shift, a new key or scale ends the hints). Outside KEYBOARD mode and the main screen the
; note is forgotten. Nothing is written while a plugin holds the LED lock (na_sync). With the patch off the patch's own values are
; taken away, and its state is touched only if a note had been noted.
tick_hook:
    push {r7, r8, r9, r10, r11, lr}
    mov r4, r6
    ldr r5, =STATE
    mov r7, #0
    bl na_active
    cmp r0, #0
    beq th_off
    bl na_kbd
    movs r11, r0                ; the kind: 1 KEYBOARD, 2 CHORD
    beq th_forget
    ldr r0, =KBOBJ_PTR
    ldr r9, [r0]
    cmp r9, #0
    beq th_none
    cmp r11, #2
    bne th_note
    ; CHORD: the chord that is played is the pad the firmware holds in its red 192; a new one gives the levels
    mov r6, #0
th_held:
    add r0, r4, r6, lsl #4
    ldrb r0, [r0, #LED_VALUE + 8 * LED_PAD_FIRST]
    cmp r0, #PAD_HELD
    beq th_held_pad
    add r6, r6, #1
    cmp r6, #16
    bne th_held
    mvn r6, #0
th_held_pad:
    ldr r0, [r5, #S_DOWN]
    cmp r0, r6
    beq th_note
    str r6, [r5, #S_DOWN]
    cmp r6, #15
    bhi th_note
    mov r1, r6
    bl na_note
    str r0, [r5, #S_NOTE]
    str r6, [r5, #S_PAD]
    mov r0, #0
    str r0, [r5, #S_SINCE]
th_note:
    ldr r8, [r5, #S_NOTE]
    cmp r8, #0x7F
    bhi th_none
    ldr r10, [r5, #S_PAD]
    cmp r10, #15
    bhi th_none
    mov r1, r10
    bl na_note
    cmp r0, r8
    bne th_forget
    ldr r0, [r5, #S_SINCE]
    cmp r0, #0
    bne th_fade
    mov r6, #0
th_level:
    mov r1, r6
    bl na_note
    mov r2, #0
    cmp r0, #0x7F
    bhi th_level_put
    sub r0, r0, r8
    add r0, r0, #132
th_mod:
    cmp r0, #12
    subcs r0, r0, #12
    bcs th_mod
    cmp r11, #2
    ldrne r1, =na_levels
    ldreq r1, =na_chord_levels
    ldrb r2, [r1, r0]
th_level_put:
    add r1, r5, #S_LEVEL
    strb r2, [r1, r6]
    add r6, r6, #1
    cmp r6, #16
    bne th_level
    cmp r11, #1                 ; KEYBOARD: a step of the scale up and down at least the middle level
    bne th_level_done
    cmp r10, #7
    addls r10, r10, #8
    subhi r10, r10, #8          ; the note's place in the table
    sub r0, r10, #1
    bl th_neighbour
    add r0, r10, #1
    bl th_neighbour
th_level_done:
    mov r0, #1
    str r0, [r5, #S_SINCE]
    mov r0, #0
    str r0, [r5, #S_FADE]
    b th_show
th_fade:
    ldr r0, =TRANSPORT
    ldr r0, [r0]
    cmp r0, #1
    cmpne r0, #4
    bne th_show
    ldr r0, [r5, #S_FADE]
    add r0, r0, #1
    cmp r0, #FADE
    movhs r0, #0
    str r0, [r5, #S_FADE]
    bne th_show
    add r1, r5, #S_LEVEL
    mov r6, #0
th_fade_pad:
    ldrb r0, [r1, r6]
    subs r0, r0, #2
    movmi r0, #0
    strb r0, [r1, r6]
    add r6, r6, #1
    cmp r6, #16
    bne th_fade_pad
th_show:
    mov r7, #1
    b th_sync
th_off:
    ldr r0, [r5, #S_NOTE]
    cmn r0, #1
    beq th_sync
th_forget:
    mvn r0, #0
    str r0, [r5, #S_NOTE]
    str r0, [r5, #S_DOWN]
th_none:
    mov r0, #0
    str r0, [r5, #S_LEVEL]
    str r0, [r5, #S_LEVEL + 4]
    str r0, [r5, #S_LEVEL + 8]
    str r0, [r5, #S_LEVEL + 12]
th_sync:
    bl na_sync
th_out:
    pop {r7, r8, r9, r10, r11, lr}
    pop {r4, r5, r6, pc}                ; the replaced instruction

; r0 = a place in the table of the layout, r5 = STATE: the pad there gets at least the middle level. Clobbers r0 to r2.
th_neighbour:
    cmp r0, #15
    bxhi lr
    cmp r0, #8
    subhs r0, r0, #8
    addlo r0, r0, #8
    add r1, r5, #S_LEVEL
    ldrb r2, [r1, r0]
    cmp r2, #LEVEL_MID
    movlo r2, #LEVEL_MID
    strblo r2, [r1, r0]
    bx lr

na_levels:                              ; the level of a pad by its interval to the note, 0 to 11 semitones
    .byte @LEVELS@
na_chord_levels:                        ; CHORD: the level of a chord by the interval of its root to the root played
    .byte @CHORD_LEVELS@
.align 4
lit_pool:
.pool
"""


def source():
    text = SOURCE.replace("@CARD_CHECK@", card_gate.source(BUILD, "nx_no", STATE + card_gate.LATCH_OFFSET))
    pristine = globals().get("_SAMPLER_ADDRESSES", {})
    body = {name: pristine.get(name, globals()[name]) for name in ("PAD_BODY", "LIGHT_BODY")}
    for key, value in {
        "KILL": f"{KILL_SWITCH:#x}", "STATE": f"{STATE:#x}", "CODE_AT": f"{CODE_AT:#x}",
        "S_SETTING": S_SETTING, "S_SINCE": S_SINCE, "S_NOTE": S_NOTE, "S_PAD": S_PAD, "S_PARTPAD": S_PARTPAD,
        "S_FADE": f"{S_FADE:#x}", "S_LEVEL": f"{S_LEVEL:#x}", "LEVEL_MID": LEVEL_MID, "FADE": FADE_TICKS,
        "LEVELS": ", ".join(str(v) for v in LEVELS), "CHORD_LEVELS": ", ".join(str(v) for v in CHORD_LEVELS), "S_DOWN": f"{S_DOWN:#x}",
        "PAD_BODY": f"{body['PAD_BODY']:#x}", "LIGHT_BODY": f"{body['LIGHT_BODY']:#x}",
    }.items():
        text = text.replace(f"@{key}@", str(value))
    if BUILD == "synth":
        # the substituted PAD_BODY and LIGHT_BODY are the Sampler's here, and so are the pointers of the .equ lines: all of them go through the table
        text = synthaddr.source(text, own=[(CODE_AT, CODE_END), (STATE, STATE_END)])
    return text


def build_code():
    code = arm.assemble(source())
    (at, data), = code.sections
    return at, data, code.symbols


def file_offset(addr):
    return addr - RAM + HEADER


def branch(at, target, link=False):
    return struct.pack("<I", (0xEB000000 if link else 0xEA000000) | ((target - (at + 8)) >> 2) & 0xFFFFFF)


def build_patch(vsb, build="hacktribe"):
    """The patch as a dict; `vsb` is the user's file, read for the hashes of the replaced bytes."""
    use_build(build)
    at, code, symbols = build_code()
    if at != CODE_AT or at + len(code) > CODE_END:
        raise SystemExit(f"code is {len(code):#x} bytes, room for {CODE_END - CODE_AT:#x}")

    def was(addr, n):
        return vsb[file_offset(addr):file_offset(addr) + n]

    def word(addr):
        return struct.unpack("<I", was(addr, 4))[0]

    def free(addr, n):
        if was(addr, n) != b"\xff" * n:
            raise SystemExit(f"{addr:#x}..{addr + n:#x} is not free in this VSB")
        return sha(was(addr, n))

    expected = (
        (PAD_HOOK, PAD_WORD, "the keyboard's pad event does not start with push {r4, r5, r6, r7, r8, lr}"),
        (LIGHT_HOOK, LIGHT_WORD, "the firmware's pad light does not start with push {r3, r4, r5, r6, r7, r8, sb, lr}"),
        (TICK_HOOK, TICK_WORD, "the LED manager's tick does not end with pop {r4, r5, r6, pc}"),
        (PAD_BODY, 0xE1A04000, "the keyboard's pad event does not go on with mov r4, r0"),
        (LIGHT_BODY, 0xE1A08003, "the firmware's pad light does not go on with mov r8, r3"),
    )
    for addr, want, why in expected:
        if word(addr) != want:
            raise SystemExit(f"{why} in this VSB")
    free(STATE, STATE_END - STATE)

    def hook(addr, name, note):
        return {"file": file_offset(addr), "bytes": branch(addr, symbols[name]).hex(), "expect": sha(was(addr, 4)), "note": note}

    def declare(addr, chain, note):
        return {"site": f"{addr:#010X}".replace("0X", "0x"), "kind": "instruction", "chain": chain, "position": "before", "swallow": False, "note": note}

    return {
        "format": "gelumpe-patch", "version": 1, "id": "note-assistant", "builds": ["synth"] if build == "synth" else ["hacktribe", "stock"],
        "name": "Notenassistent: nach einer Note leuchten die passenden Pads im KEYBOARD-Modus schwach rosa (NOTE ASSISTANT)",
        "changes": [
            {"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": free(CODE_AT, len(code)),
             "note": "note assistant: the three hooks and what they share, and what the BLECH menu's NOTE ASSISTANT page will write (NA_SETTING)"},
            hook(PAD_HOOK, "pad_hook", "first instruction of the keyboard's pad event jumps to the hook"),
            hook(LIGHT_HOOK, "light_hook", "first instruction of the firmware's pad light jumps to the hook"),
            hook(TICK_HOOK, "tick_hook", "last instruction of the LED manager's tick jumps to the hook"),
        ],
        "hooks": [
            declare(PAD_HOOK, "pad-note", "remembers the note of a pad that goes down in KEYBOARD mode"),
            declare(LIGHT_HOOK, "pad-note", "a note on of the selected part takes the hints away before the firmware lights its pads"),
            declare(TICK_HOOK, "led-tick-end", "counts the time since the last note and shows, keeps or takes away the hints"),
        ],
        "startPhase": [
            {"file": file_offset(TICK_HOOK), "length": 4, "why": "the LED manager's tick runs from about 140 ms, after the rescue paths, and now ends in a jump to tick_hook"},
            {"file": file_offset(CODE_AT), "length": len(code), "why": "tick_hook and what it calls: at start they look at the panel object, the kill switch, the card, the setting word and the pad mode, and write nothing; the pad hook and the light hook run only on a pad or a note"},
        ],
        "ram": [
            ramdecl.area(STATE, STATE_END - STATE, "run time state: NA_SETTING at +0 for the BLECH menu, the ticks since the last note, the note and the pad, the pad whose blue was taken", "tools/patch/note_assist.py:STATE"),
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vsb", required=True, type=Path)
    p.add_argument("--build", choices=["hacktribe", "synth"], default="hacktribe", help="synth: the blue Electribe 2's file, with the places of data/synth-map/")
    p.add_argument("--out", type=Path)
    p.add_argument("--listing", action="store_true")
    a = p.parse_args()
    raw = a.vsb.read_bytes()
    if len(raw) != 0x200100:
        raise SystemExit("a VSB has 0x200100 bytes")
    use_build(a.build)
    patch = build_patch(raw, a.build)
    if a.listing:
        at, code, symbols = build_code()
        print(f"section {at:#x} + {len(code):#x} bytes, state {STATE:#x}, setting word {NA_SETTING:#x}")
        for name, addr in sorted(symbols.items(), key=lambda kv: kv[1]):
            print(f"  {addr:#010x} {name}")
    text = json.dumps(patch, indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    elif not a.listing:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
