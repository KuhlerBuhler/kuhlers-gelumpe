"""Builds the pattern switch patch (docs/ideen/46-patternwechsel-bestaetigung.md) for firmware 2.02 with Hacktribe.

While a pattern plays, the wheel only browses: the firmware already shows the chosen pattern as
NEXT:nnn and holds nothing but a number and a flag, so the patch keeps the choice from being applied.
MENU (ENTER) on the main screen confirms the browsed pattern, and it starts at the next sequence end.
EXIT takes the browse or the confirmation back. MENU's LED shows where to press: it blinks while a pattern is only browsed
(VIEW:) and is lit once one is confirmed (NEXT:), until the switch. Stopped with unsaved changes (the pattern in RAM differs from its
place in the pattern bank) the wheel browses the same way, so the edit is not thrown away by a turn: VIEW:nnn
shows, MENU loads the browsed pattern at once, EXIT stays on the edited one. Stopped without changes, in record and
for every other way to choose a pattern (pad, MIDI program change, chain), the firmware behaves as it always did.

    python3 tools/patch/pattern_switch.py --vsb SYSTEM.VSB [--out data/patches/pattern-switch.json]

Sync groups (sampler builds): a pattern carries a sync group, 0 (OFF) to 999, as a little endian half word at GROUP_AT of its
block (a byte range the firmware never reads or writes; the BLECH menu sets it). While a pattern plays, the wheel on another
pattern of the same group confirms it at once (NEXT:, no MENU needed), and a pattern load from one pattern of a group to another
carries the state of the pattern that played, changed or not: part mutes and sound, tempo, swing, level, the MFX pad and HOLD.
A part's sample goes along only when it was changed live (it differs from the bank block the pattern came from). Steps, motion, length, beat, key, scale, chord set and the MFX types (1 and 2) stay the new pattern's.

Twenty-one hooks; the stopped sync, command end, note cleanup and pattern load run before the main screen:
  wheel        the tail call of the main screen's VALUE handler into the selector, 0xC006513C
  pad          first instruction of the pad selection, 0xC006EDE4, clears browse and confirmation
  MIDI         first instruction of the program change handler, 0xC006EE00, ditto
  MENU         slot +0x18 of the main screen's class, 0xC00E34B0, confirms
  EXIT         slot +0x08 of the same class, 0xC00E34A0, takes browse or confirmation back
  sequence end the call that asks for the number to start, 0xC005F1C4 (runs in the engine task, only reads)
  STOP         first instruction of the pending-pattern applier, 0xC0081B5C
  label        the load of "NEXT:" in the lower line builder, 0xC0086DC4, shows VIEW: while browsing
  stopped sync first instruction of the observer that loads a chosen number while stopped, 0xC0081E18, idle during a stopped browse
  copy         the copy of the pattern load into the pattern in RAM, 0xC004AC44 (sampler builds only), the sync group's carry
  pad gate     the busy check of the pad handler, 0xC0044888: a pad pressed while the firmware runs a command (a pattern load) is
               kept instead of dropped
  command end  where the command runner clears its busy flag, 0xC002D81C: the kept pad presses are handed to the pad handler
  voice begin  held-pad cleanup at 0xC0079B90; same-group loads keep the existing note ownership
  voice stop   pre-copy silencing at 0xC0079BE0
  note cleanup source cleanup at 0xC0045DAC and note-off calls at 0xC004A728, 0xC004A7A8, 0xC00492F4
  note slots   voice-mode reinitialization at 0xC005A884; the carried voice mode keeps its active notes
  voice reset  global reset at 0xC0098C84; skipped within a protected load
  voice end    post-copy initialization at 0xC0079C2C; new samples are prepared for subsequent triggers

Pattern confirmation requires that EXIT was not held at power-on, a card was seen since power-on and PS_SETTING
is not 0 (the BLECH menu writes it; never written means on). Sync groups remain active independently of that setting
and the card latch; EXIT held at power-on disables them too.
Nothing of the firmware is copied and nothing is written to flash or to the card.
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

CODE_AT = 0xC0180000            # free (FF) in the image, far from the other patches
CODE_END = 0xC0180F00
STATE = 0xC0180F00              # run time state, in RAM only; FF there means "nothing"
STATE_END = 0xC0180F40
VOICE_CODE = STATE_END
VOICE_END = 0xC0181000
S_VOICES = 0x38
SG_BUF = 0xC0173000             # the sync group's buffer, in RAM only, in the free run between the SysEx patch's code and its table
SG_SIZE = 10 + 16 * 47          # 9 values of the pattern (tempo two bytes), 47 bytes of each part
S_BROWSE, S_ARMED, S_ARMNUM, S_SETTING, S_STOPPED, S_AUTO, S_LOADED, S_LED = 0, 4, 8, 0x10, 0x14, 0x18, 0x1C, 0x20
S_PADH, S_PADT, S_PADQ, PADQ_SIZE = 0x24, 0x25, 0x28, 4
LED_MGR, LED_MENU, S_LEDWAS = 0xC0345A1C, 7, 0x21
PS_SETTING = STATE + S_SETTING  # the setting word the BLECH menu writes: never written (FFFFFFFF) or 1 is on, 0 is off

KILL_SWITCH = 0x2000            # EXIT held at power-on (bit 13, measured on the device 10.10.)

WHEEL_HOOK = 0xC006513C         # b 0xC008206C, the VALUE handler's tail call into the selector
WHEEL_WORD = 0xEA0073CA
SELECT = 0xC008206C
PAD_HOOK = 0xC006EDE4           # push {r4, lr}
PAD_WORD = 0xE92D4010
PAD_BODY = 0xC006EDE8
MIDI_HOOK = 0xC006EE00          # push {r3, r4, r5, lr}
MIDI_WORD = 0xE92D4038
MIDI_BODY = 0xC006EE04
MENU_SLOT = 0xC00E34B0          # main screen class, slot 6
MENU_ORIG = 0xC0065144
EXIT_SLOT = 0xC00E34A0          # main screen class, slot 2
EXIT_ORIG = 0xC0060F04
SEQ_CALL = 0xC005F1C4           # bl 0xC00818D8, the pattern number the sequence end asks for
SEQ_FUNC = 0xC00818D8
STOP_HOOK = 0xC0081B5C          # ldrb r3, [r0, #0x341]
STOP_WORD = 0xE5D03341
STOP_BODY = 0xC0081B60
LABEL_HOOK = 0xC0086DC4         # ldr r1, [pc, #0xe0] = "NEXT:"
SYNC_HOOK = 0xC0081E18          # push {r4, r5, r6, lr}: stopped, a chosen number that does not run is loaded here
SYNC_WORD = 0xE92D4070
SYNC_BODY = 0xC0081E1C
LABEL_WORD = 0xE59F10E0
NEXT_TEXT = 0xC00A72E0
COPY_CALL = 0xC004AC44          # bl 0xC000985C: memcpy(pattern + 4, source, 0x4000) in the pattern load 0xC004AB84 (sampler builds)
MEMCPY = 0xC000985C
PGATE_HOOK = 0xC0044888         # bl 0xC002D634 in the pad handler 0xC0044874 (pad, pressed, velocity, source): busy and pressed -> dropped
PGATE_WORD = 0xEBFFA369
PGATE_CONT = 0xC004489C         # the handler goes on with the pad
PGATE_SKIP = 0xC004499C         # the handler's way out, the pad dropped
PAD_HANDLER = 0xC0044874
CMD_BUSY = 0xC002D634           # returns the command runner's busy byte (+0x10 of its object)
CMD_END = 0xC002D81C            # strb r3, [r6, #0x10]: the command runner clears its busy byte (r3 = 0)
CMD_END_WORD = 0xE5C63010
VIEW_W = 0xC0173400             # the view's own accessor and state, in RAM only (between SG_BUF and the SysEx patch's table)
VIEW_SIZE = 0x64
V_NUM, V_LIDX, V_SGNUM = 0x40, 0x44, 0x48
V_MNUM, V_MTOUCH, V_MUTE, V_TAKE = 0x4C, 0x50, 0x54, 0x58
V_PEND, V_COPY = 0x5C, 0x60
VIEW_CODE = 0xC0173480          # the view's pads (docs/messungen/2026-10-29-vorschau-pads.md), behind VIEW_W, up to the SysEx patch's table
VIEW_CODE_END = 0xC0173800
MUTE_GET = 0xC0048CFC           # ldr r3, [r0, #4]: the part mute getter (accessor, part), the pad LEDs read the mutes through it
MUTE_GET_WORD = 0xE5903004
MUTE_GET_BODY = 0xC0048D00
MUTE_SET = 0xC0049330           # the part mute setter (accessor, part, mute, notify): writes byte 1 of the part and tells the engine
MUTE_SET_CALL = 0xC0060D34      # bl MUTE_SET: the main screen's PART MUTE pad (UI task) sets the mute it read, inverted
COPY_PART = 0xC00667D4          # the firmware's Copy Part (Part Util 1/4): (object, part); +0x40 source pattern, +0x41 source part, +0x42 target part
COPY_PART_WORD = 0xE92D4FF0     # push {r4 to r11, lr}
SYNTH_COPY_PART_WORD = 0xE92D47F3   # push {r0, r1, r4 to r10, lr}: the synth's takes the target part in r1
INFO_HOOK = 0xC008684C          # ldrb r3, [r0, #0x5c]: the first instruction of the info line's builder that reads the label flag
INFO_WORD = 0xE5D0305C
INFO_BODY = 0xC0086850
CELL_W = 0xC0691388             # the pointer the pad LEDs read the pattern's accessor through (UI only)
CELL_O = 0xC069136C             # the pointer the info texts read the pattern through (UI only)
PADS_REFRESH = 0xC00892D4       # (LED manager): the firmware's own refresh of the pads after a pattern load, it draws the pads of the current mode
GROUP_AT = 0x3B80               # the sync group in a pattern block, u16 little endian; the firmware never touches 0x3B03 to 0x3BFB
VOICE_BEGIN_CALL = 0xC0079B90
VOICE_CONT = 0xC0079BD4
VOICE_SILENCE_CALL = 0xC0079BE0
VOICE_END_CALL = 0xC0079C2C
VOICE_RESET_CALL = 0xC0098C84
VOICE_BEGIN_ORIG = 0xC00413A8
VOICE_SILENCE_ORIG = 0xC009B5D8
VOICE_END_ORIG = 0xC009B5DC
VOICE_RESET_ORIG = 0xC0091F5C
NOTE_CLEAR_HOOK = 0xC0045DAC
NOTE_CLEAR_BODY = 0xC0045DB0
NOTE_CLEAR_WORD = 0xE5903014
NOTE_FLUSH_ORIG = 0xC005AA80
NOTE_FLUSH_KEY = 0xC004A728
NOTE_FLUSH_SCALE = 0xC004A7A8
NOTE_FLUSH_VOICE = 0xC00492F4
NOTE_ASSIGN_CALL = 0xC005A884
NOTE_ASSIGN_ORIG = 0xC005A7A4


FIRMWARE_PLACES = ["WHEEL_HOOK", "SELECT", "PAD_HOOK", "PAD_BODY", "MIDI_HOOK", "MIDI_BODY", "MENU_SLOT", "MENU_ORIG", "EXIT_SLOT", "EXIT_ORIG",
                   "SEQ_CALL", "SEQ_FUNC", "STOP_HOOK", "STOP_BODY", "LABEL_HOOK", "NEXT_TEXT",
                   "SYNC_HOOK", "SYNC_BODY", "COPY_CALL", "MEMCPY", "PGATE_HOOK", "PGATE_CONT", "PGATE_SKIP", "PAD_HANDLER",
                   "CMD_BUSY", "CMD_END", "INFO_HOOK", "INFO_BODY", "CELL_W", "CELL_O", "PADS_REFRESH", "VOICE_BEGIN_CALL", "VOICE_END_CALL", "VOICE_RESET_CALL",
                   "VOICE_BEGIN_ORIG", "VOICE_END_ORIG", "VOICE_RESET_ORIG", "VOICE_CONT", "VOICE_SILENCE_CALL", "VOICE_SILENCE_ORIG",
                   "NOTE_CLEAR_HOOK", "NOTE_CLEAR_BODY", "NOTE_FLUSH_ORIG", "NOTE_FLUSH_KEY", "NOTE_FLUSH_SCALE", "NOTE_FLUSH_VOICE",
                   "NOTE_ASSIGN_CALL", "NOTE_ASSIGN_ORIG", "MUTE_GET", "MUTE_GET_BODY",
                   "MUTE_SET", "MUTE_SET_CALL", "COPY_PART"]
SYNTH = False
SYNTH_LABEL_WORD = 0xE59F10FC   # ldr r1, [pc, #0xfc]: the synth's builder is laid out a little differently


def use_build(build):
    """For the synth the firmware's places have their own addresses (data/synth-map/); the code and the state stay where they are."""
    global SYNTH, LABEL_WORD, COPY_PART_WORD
    SYNTH = build == "synth"
    synthaddr.use(globals(), FIRMWARE_PLACES, build)
    LABEL_WORD = SYNTH_LABEL_WORD if SYNTH else _SAMPLER_LABEL_WORD
    COPY_PART_WORD = SYNTH_COPY_PART_WORD if SYNTH else _SAMPLER_COPY_PART_WORD


_SAMPLER_LABEL_WORD = LABEL_WORD
_SAMPLER_COPY_PART_WORD = COPY_PART_WORD


def sha(data):
    return hashlib.sha256(data).hexdigest()


SOURCE = """
.equ PANEL, 0xC033E6F8          ; pointer to the panel object, +0x18 the keys held at power-on
.equ FATFS, 0xC06A010C          ; FatFs volume table: first entry is the volume of the card, its byte 0 is the mounted type
.equ TRANSPORT, 0xC0030D28      ; returns the transport object, +0x308 its state (0 stopped, 3 to 5 record)
.equ PSEL, 0xC00431F0           ; returns the pattern selection object: +0x318 chosen number, +0x341 pending flag
.equ PLAYER, 0xC002FAFC         ; returns the player: +0x318 the number that runs
.equ SET_NUMBER, 0xC0081F50     ; (psel, number, send MIDI)
.equ NOTIFY, 0xC0070688         ; (psel + 4, message {1, number, ..., word 0}): what SET_NUMBER tells the display with
.equ PATPTR, 0xC033E6A4         ; the pattern in RAM, its file at + 4
.equ BANK, 0xC08B2940           ; the pattern bank in RAM, 0x4000 per pattern
.equ PAT_WORDS, 0x1000
.equ WRAP, 0xC0040D24           ; (value, 0, 249) wraps into the pattern range
.equ SELECT, @SELECT@
.equ MENU_ORIG, @MENU_ORIG@
.equ EXIT_ORIG, @EXIT_ORIG@
.equ NEXT_TEXT, @NEXT_TEXT@
.equ KILL, @KILL@
.equ STATE, @STATE@
.equ S_BROWSE, 0                ; 1 while the wheel has browsed away from what will play
.equ S_ARMED, 4                 ; 1 while a pattern is confirmed
.equ S_ARMNUM, 8                ; the confirmed number, valid while S_ARMED is 1
.equ S_SETTING, 0x10            ; PS_SETTING: FFFFFFFF or 1 is on, 0 is off
.equ S_STOPPED, 0x14            ; 1 while the wheel browses away from an unsaved pattern, stopped
.equ S_AUTO, 0x18               ; 1 while S_ARMED comes from the sync group (the next turn takes it back)
.equ GROUPS, @GROUPS@           ; 0 where the build has no sync groups (synth)
.equ GROUP_AT, @GROUP_AT@
.equ S_LOADED, 0x1C             ; the bank block the pattern in RAM was last loaded from, else not a bank block (FF at start)
.equ SG_BUF, @SG_BUF@           ; what the sync group puts into the new pattern, SG_SIZE bytes
.equ S_LED, 0x20                ; byte: the mode the patch last gave MENU's LED (0 none, 1 lit, 2 blinking), FF never
.equ S_LEDWAS, 0x21             ; 3 bytes: the LED's entry as the firmware had it (mode, brightness, on), given back after
.equ LED_UPDATE, 0xC00875F4     ; (manager, led, force): sends the LED's entry to the panel
.equ LED_ENTRY, 0x4D + 8 * 7    ; manager + 0x4D + 8 * led: mode, brightness, on (LED_SET writes these three)
.equ LED_MGR, 0xC0345A1C        ; pointer to the LED manager
.equ LED_SET, 0xC0087710        ; (manager, led, mode, duration): the manager's own path to set an LED and send it; mode 2 blinks
.equ LED_MENU, 7
.equ BLINK, 7
.equ S_PADH, 0x24               ; byte: pad presses kept so far (counts on, wraps at 256), FF at start
.equ S_PADT, 0x25               ; byte: pad presses handed on so far; equal to S_PADH: none waiting
.equ S_PADQ, 0x28               ; PADQ_SIZE entries of 4 bytes: pad, pressed, velocity, source
.equ PADQ_SIZE, 4
.equ VIEW_W, @VIEW_W@           ; the view's accessor (copy of the pattern's, pointing into the bank), its state behind it
.equ V_NUM, 0x40                ; the bank pattern the display shows, FFFFFFFF none (also: nothing ever written)
.equ V_LIDX, 0x44               ; the info line's index while the label was built
.equ V_SGNUM, 0x48              ; the bank block (address) a sync group carried into the pattern in RAM (SG_BUF holds what it put there), else not a bank block (FF at start)
.equ CELL_W, @CELL_W@
.equ CELL_O, @CELL_O@
.equ PADS_REFRESH, @PADS_REFRESH@
.equ REPLAYED, 0x80000000       ; in the source argument: a kept press handed on, the gate lets it through                   ; mode 2 toggles every BLINK ticks of the manager's 40 ms tick: 280 ms on, 280 ms off
.equ S_VOICES, 0x38
.equ VOICE_BEGIN_ORIG, @VOICE_BEGIN_ORIG@
.equ VOICE_CONT, @VOICE_CONT@
.equ VIEW_NEW, @VIEW_CODE@      ; the view's pads (build_view_code): its table of entries
.equ VIEW_PAD, @VIEW_CODE@ + 4
.equ VIEW_TAKE, @VIEW_CODE@ + 8
.equ VIEW_APPLY, @VIEW_CODE@ + 12
.equ VIEW_REFRESH, @VIEW_CODE@ + 16
.equ VIEW_PADS, @VIEW_CODE@ + 20

.org @CODE_AT@

; ===================================================== is the patch on
; r0 = 1 when EXIT was not held at power-on, a card was seen since power-on and the setting is not off. Clobbers r0 and r12.
; Writes only the card latch (tools/patch/card_gate.py), always the same value, so the engine task may call it too.
pc_active:
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    beq pa_no
    ldr r0, [r12, #0x18]
    tst r0, #KILL
    bne pa_no
@CARD_CHECK@    ldr r12, =STATE
    ldr r12, [r12, #S_SETTING]
    cmn r12, #1
    moveq r0, #1
    bxeq lr
    ands r0, r12, #1
    bxne lr
pa_no:
    mov r0, #0
    bx lr

; ===================================================== the wheel
; Entered from the VALUE handler's tail call: r0 = the selection object, r1 = the steps (times ten with SHIFT), lr = its caller.
; The firmware's selector would add them to the chosen number and set it with MIDI. While a pattern plays, this sets it
; without MIDI and remembers that it is only being browsed. Stopped or recording, the selector runs as always.
wheel_hook:
    push {r4, r5, r6, lr}
    mov r4, r0
    mov r5, r1
    bl pc_active
    cmp r0, #0
    beq wh_stock
    bl TRANSPORT
    ldr r0, [r0, #0x308]
    cmp r0, #0
    beq wh_stopped
    sub r0, r0, #3
    cmp r0, #2
    bls wh_stock
    ldr r6, =STATE
    mov r0, #0
    str r0, [r6, #S_STOPPED]
    ldrb r0, [r4, #0x341]
    cmp r0, #0
    bne wh_go
    mov r0, #0                  ; nothing is pending: an old browse or confirmation is gone
    str r0, [r6, #S_ARMED]
    str r0, [r6, #S_BROWSE]
wh_go:
    ldr r0, [r6, #S_AUTO]       ; a confirmation the sync group made is taken back by the next turn
    cmp r0, #1
    moveq r0, #0
    streq r0, [r6, #S_ARMED]
    streq r0, [r6, #S_AUTO]
    ldr r0, [r4, #0x318]
    add r0, r5, r0
    mov r1, #0
    mov r2, #249
    bl WRAP
    mov r5, r0
    bl pc_grouped
    cmp r0, #0
    beq wh_browse
    str r5, [r6, #S_ARMNUM]     ; another pattern of the running pattern's sync group: confirmed at once, MIDI as for MENU
    mov r0, #1
    str r0, [r6, #S_ARMED]
    str r0, [r6, #S_AUTO]
    mov r0, #0
    str r0, [r6, #S_BROWSE]
    mov r0, r4
    mov r1, r5
    mov r2, #1
    bl SET_NUMBER
    b wh_after
wh_browse:
    mov r0, #1                  ; browsing, set before the firmware tells the display (the lower line reads it then),
    ldr r1, [r6, #S_ARMED]      ; unless this is the confirmed number: nothing left to browse
    cmp r1, #1
    bne wh_set
    ldr r1, [r6, #S_ARMNUM]
    cmp r1, r5
    moveq r0, #0
wh_set:
    str r0, [r6, #S_BROWSE]
    mov r0, r4
    mov r1, r5
    mov r2, #0                  ; no MIDI while browsing
    bl SET_NUMBER
wh_after:
    ldrb r0, [r4, #0x341]
    cmp r0, #0
    bne wh_out
    mov r0, #0                  ; back on the number that runs: the firmware cleared the pending flag, so nothing is browsed or confirmed
    str r0, [r6, #S_BROWSE]
    str r0, [r6, #S_ARMED]
    str r0, [r6, #S_AUTO]
wh_out:
    bl pc_led
    pop {r4, r5, r6, pc}
wh_stock:
    mov r0, r4
    mov r1, r5
    pop {r4, r5, r6, lr}
    b SELECT

; stopped: an unsaved pattern is not thrown away by a turn. The wheel browses as while playing (the number and the
; pending flag, told to the display as SET_NUMBER does while playing), nothing is loaded; back on the number in RAM the
; browse is over. Without changes the firmware's selector runs and loads at once.
wh_stopped:
    ldr r6, =STATE
    ldr r0, [r6, #S_STOPPED]
    cmp r0, #1
    beq wh_stopped_go
    bl pc_dirty
    cmp r0, #0
    beq wh_stock
wh_stopped_go:
    ldr r0, [r4, #0x318]
    add r0, r5, r0
    mov r1, #0
    mov r2, #249
    bl WRAP
    mov r5, r0
    bl pc_grouped
    cmp r0, #0
    bne wh_group_load
    bl PLAYER
    ldr r1, [r0, #0x318]
    mov r0, #1
    cmp r1, r5
    moveq r0, #0
    str r0, [r6, #S_STOPPED]
    str r0, [r6, #S_BROWSE]
    str r5, [r4, #0x318]
    strb r0, [r4, #0x341]
    mov r0, r4
    mov r1, r5
    bl pc_notify
    bl pc_led
    pop {r4, r5, r6, pc}

; stopped, another pattern of the running pattern's sync group: no question, the firmware's selector loads it at once and the copy
; hook carries the group's state; a browse that was open ends here. r5 = the number, r4 = the selection object.
wh_group_load:
    mov r0, #0
    str r0, [r6, #S_STOPPED]
    str r0, [r6, #S_BROWSE]
    bl pc_led
    ldr r1, [r4, #0x318]
    sub r1, r5, r1              ; WRAP(number + step) is the target itself, whatever the browse number was
    mov r0, r4
    pop {r4, r5, r6, lr}
    b SELECT

; r5 = a pattern number -> r0 = 1 when it is not the running pattern and has the running pattern's sync group (not 0). The
; group of the running pattern is read in RAM (an unsaved change counts), the other's in the bank. Clobbers r0 to r3 and r12.
pc_grouped:
    push {r4, lr}
    mov r0, #GROUPS
    cmp r0, #0
    beq pg_no
    bl PLAYER
    ldr r1, [r0, #0x318]
    cmp r1, r5
    beq pg_no
    ldr r0, =PATPTR
    ldr r0, [r0]
    cmp r0, #0
    beq pg_no
    add r0, r0, #4
    bl pc_group
    movs r4, r0
    beq pg_no
    ldr r0, =BANK
    add r0, r0, r5, lsl #14
    bl pc_group
    cmp r0, r4
    moveq r0, #1
    popeq {r4, pc}
pg_no:
    mov r0, #0
    pop {r4, pc}

; r0 = a pattern block -> r0 = its sync group. Clobbers r1.
pc_group:
    add r0, r0, #GROUP_AT
    ldrb r1, [r0, #1]
    ldrb r0, [r0]
    orr r0, r0, r1, lsl #8
    bx lr

; @COPY_BEGIN@ ===================================================== the copy of the pattern load
; Replaces memcpy(pattern + 4, source, 0x4000) in the firmware's pattern load (CommandTask). Every full load into the pattern in RAM
; from the bank is remembered (S_LOADED, the bank block). When the pattern in RAM and the source have the same sync group (not 0)
; and the source is not the block the pattern in RAM came from, every value sg_walk names goes from the pattern in RAM into the new
; one before the firmware applies it (the part sound and mute, tempo, swing, level, MFX), changed or not: the patterns of a group
; play as one, only their steps differ. A part's sample goes along only when it was changed live (sg_sample). Not with EXIT held at power-on. All addresses
; are built without a literal: the firmware loads a pattern during the start, so this runs then.
copy_hook:
    push {r4-r10, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r7, #0                  ; 0 nothing, 1 synced, 2 only remembered
    cmp r6, #0x4000
    bne ch_copy
    cmp r4, r5
    beq ch_copy
    mov r12, #(PATPTR & 0xFF000000)
    orr r12, r12, #(PATPTR & 0x00FF0000)
    orr r12, r12, #(PATPTR & 0x0000FF00)
    orr r12, r12, #(PATPTR & 0x000000FF)
    ldr r12, [r12]
    add r12, r12, #4
    cmp r4, r12
    bne ch_copy
    mov r7, #2
    mov r12, #(PANEL & 0xFF000000)
    orr r12, r12, #(PANEL & 0x00FF0000)
    orr r12, r12, #(PANEL & 0x0000FF00)
    orr r12, r12, #(PANEL & 0x000000FF)
    ldr r12, [r12]
    cmp r12, #0
    beq ch_copy
    ldr r0, [r12, #0x18]
    tst r0, #KILL
    bne ch_copy
    mov r0, r4
    bl pc_group
    movs r8, r0
    beq ch_copy
    mov r0, r5
    bl pc_group
    cmp r0, r8
    bne ch_copy
    mov r12, #(STATE & 0xFF000000)
    orr r12, r12, #(STATE & 0x00FF0000)
    orr r12, r12, #(STATE & 0x0000FF00)
    orr r12, r12, #(STATE & 0x000000FF)
    ldr r8, [r12, #S_LOADED]
    cmp r8, r5
    beq ch_copy
    mov r10, #0
    bl sg_walk
    mov r7, #1
ch_copy:
    mov r0, r4
    mov r1, r5
    mov r2, r6
    bl @MEMCPY@
    cmp r7, #1
    moveq r10, #1
    bleq sg_walk
    cmp r7, #0
    beq ch_out
    bl VIEW_APPLY               ; the mutes set on the pads while this pattern was viewed
    mov r0, r5
    bl sg_banked
    cmp r0, #0
    mvneq r5, #0
    mov r12, #(STATE & 0xFF000000)
    orr r12, r12, #(STATE & 0x00FF0000)
    orr r12, r12, #(STATE & 0x0000FF00)
    orr r12, r12, #(STATE & 0x000000FF)
    str r5, [r12, #S_LOADED]
    cmp r7, #1
    mvnne r5, #0                ; only a carry makes SG_BUF what the pattern in RAM holds (pc_dirty)
    mov r12, #(VIEW_W & 0xFF000000)
    orr r12, r12, #(VIEW_W & 0x00FF0000)
    orr r12, r12, #(VIEW_W & 0x0000FF00)
    orr r12, r12, #(VIEW_W & 0x000000FF)
    str r5, [r12, #V_SGNUM]
ch_out:
    pop {r4-r10, pc}

; r0 = an address -> r0 = 1 when it is the start of a block of the pattern bank. Clobbers r1.
sg_banked:
    mov r1, #(BANK & 0xFF000000)
    orr r1, r1, #(BANK & 0x00FF0000)
    orr r1, r1, #(BANK & 0x0000FF00)
    orr r1, r1, #(BANK & 0x000000FF)
    subs r0, r0, r1
    blo sb_no
    cmp r0, #0x3E8000           ; 250 blocks
    bhs sb_no
    movs r1, r0, lsl #18
    moveq r0, #1
    bxeq lr
sb_no:
    mov r0, #0
    bx lr

; Walks the values a sync group carries: the pattern's bytes in sg_head, then bytes 1 to 0x2F of every part (mute and sound; the
; sample number at 8 as one half word). r4 = the pattern in RAM; r10 = 0: its values go into SG_BUF; r10 = 1: SG_BUF goes back
; into the pattern in RAM. Clobbers r0 to r3, r9 and r12.
sg_walk:
    push {r6, r7, r11, lr}
    mov r9, #(SG_BUF & 0xFF000000)
    orr r9, r9, #(SG_BUF & 0x00FF0000)
    orr r9, r9, #(SG_BUF & 0x0000FF00)
    orr r9, r9, #(SG_BUF & 0x000000FF)
    mov r11, #(sg_head & 0xFF000000)
    orr r11, r11, #(sg_head & 0x00FF0000)
    orr r11, r11, #(sg_head & 0x0000FF00)
    orr r11, r11, #(sg_head & 0x000000FF)
sw_head:
    ldrb r0, [r11], #1
    cmp r0, #0
    beq sw_parts
    tst r0, #0x80
    movne r1, #2
    moveq r1, #1
    and r0, r0, #0x7F
    bl sg_unit
    b sw_head
sw_parts:
    mov r6, #0x800
sw_part:
    mov r7, #1
sw_byte:
    cmp r7, #9
    beq sw_next
    add r0, r6, r7
    cmp r7, #8
    beq sw_sample
    mov r1, #1
    bl sg_unit
    b sw_next
sw_sample:
    bl sg_sample
sw_next:
    add r7, r7, #1
    cmp r7, #0x30
    blo sw_byte
    add r6, r6, #0x330
    cmp r6, #0x3B00
    blo sw_part
    pop {r6, r7, r11, pc}

; one value: r0 = its offset in the block, r1 = its size (1 or 2); see sg_walk. Clobbers r2, r3 and r12.
sg_unit:
    cmp r10, #0
    bne su_put
    add r2, r4, r0
    ldrb r3, [r2]
    strb r3, [r9], #1
    cmp r1, #2
    ldrbeq r3, [r2, #1]
    strbeq r3, [r9], #1
    bx lr
su_put:
    add r2, r4, r0
    ldrb r3, [r9], #1
    strb r3, [r2]
    cmp r1, #2
    ldrbeq r3, [r9], #1
    strbeq r3, [r2, #1]
    bx lr

; the sample number of a part, r0 = its offset: see sg_walk. It goes along only when the pattern in RAM changed it, that is when it
; differs from the bank block the pattern was loaded from (r8, S_LOADED); otherwise the new pattern (r5) keeps its own, so patterns of
; a group can play different samples on one part. Without a known bank block it goes along. Clobbers r1 to r3 and r12.
sg_sample:
    mov r1, #2
    cmp r10, #0
    bne sg_unit
    cmn r8, #1
    beq sg_unit
    add r2, r4, r0
    add r3, r8, r0
    ldrb r12, [r2]
    ldrb r1, [r3]
    cmp r12, r1
    ldrbeq r12, [r2, #1]
    ldrbeq r1, [r3, #1]
    cmpeq r12, r1
    mov r1, #2
    bne sg_unit
    add r2, r5, r0
    ldrb r3, [r2]
    strb r3, [r9], #1
    ldrb r3, [r2, #1]
    strb r3, [r9], #1
    bx lr

; the pattern's own values a sync group carries, offsets in the block, 0x80 marks a half word: tempo (34), swing, play level, MFX
; type, pad X and Y, byte 64, HOLD, alternate 13-14 and 15-16. Left out: length, beat, key, scale, chord set, the pad's touch (0x3C).
sg_head:
    ; not 61, the MFX type: with MFX 2 on it holds MFX 2's type, which would become the new pattern's MFX 1 (device 24.10.);
    ; each pattern keeps its own types, the pad and HOLD go along
    .byte 0xA2, 36, 42, 62, 63, 64, 65, 68, 69, 0
.align 4
; the same offsets one by one, the half word as two, for the unsaved check (pd_synced), closed by a value no offset reaches
sg_head_at:
    .word 34, 35, 36, 42, 62, 63, 64, 65, 68, 69, 0xFFFF
; @COPY_END@

; ===================================================== MENU's LED
; Shows where to press: blinking while a pattern is only browsed (VIEW:, MENU confirms it, or loads it when stopped), lit while
; one is confirmed (NEXT:). Otherwise the LED is the firmware's (dark on the main screen, mode 1 with brightness 0): its entry is
; remembered when the patch takes the LED and given back after. Sent only when that changes. Clobbers r0 to r3 and r12.
; Every change of the browse or the confirmation passes here, so the view follows it (pc_view_cells); pc_led_engine is for the engine
; task, where the view only ends and the firmware's own refresh after the pattern load draws the pads.
pc_led:
    push {lr}
    bl pc_led_core
    bl pc_view_cells
    cmp r0, #0
    blne pc_view_refresh
    pop {pc}
pc_led_engine:
    push {lr}
    bl pc_led_core
    bl pc_view_cells
    cmp r0, #0
    blne VIEW_PADS              ; the pads go out again in the colours of what they show now
    pop {pc}
pc_led_core:
    push {r4, lr}
    ldr r3, =STATE
    ldr r0, [r3, #S_BROWSE]
    cmp r0, #1
    moveq r4, #2
    beq pl_want
    ldr r0, [r3, #S_ARMED]
    cmp r0, #1
    moveq r4, #1
    movne r4, #0
pl_want:
    ldrb r0, [r3, #S_LED]
    cmp r0, #0xFF
    moveq r0, #0
    cmp r0, r4
    popeq {r4, pc}
    ldr r12, =LED_MGR
    ldr r12, [r12]
    cmp r12, #0
    popeq {r4, pc}
    add r1, r12, #LED_ENTRY
    cmp r0, #0                  ; taken now: remember the firmware's entry
    ldrbeq r2, [r1]
    strbeq r2, [r3, #S_LEDWAS]
    ldrbeq r2, [r1, #1]
    strbeq r2, [r3, #S_LEDWAS + 1]
    ldrbeq r2, [r1, #2]
    strbeq r2, [r3, #S_LEDWAS + 2]
    strb r4, [r3, #S_LED]
    cmp r4, #0
    bne pl_set
    ldrb r2, [r3, #S_LEDWAS]    ; given back as it was, and sent
    strb r2, [r1]
    ldrb r2, [r3, #S_LEDWAS + 1]
    strb r2, [r1, #1]
    ldrb r2, [r3, #S_LEDWAS + 2]
    strb r2, [r1, #2]
    mov r0, r12
    mov r1, #LED_MENU
    mov r2, #1
    bl LED_UPDATE
    pop {r4, pc}
pl_set:
    mov r0, r12
    mov r1, #LED_MENU
    mov r2, r4
    cmp r4, #2
    moveq r3, #BLINK
    movne r3, #0
    bl LED_SET
    pop {r4, pc}

; ===================================================== the view
; While a pattern is browsed or confirmed the display reads that pattern from the pattern bank in RAM: the pad LEDs (part mutes, steps)
; and the info texts (OSC, PITCH and the rest of the Edit line) take the pattern through two pointers that only the display code reads.
; One points at the pattern's accessor (an object inside the pattern in RAM, +4 holds the pattern), the other at the pattern. While
; viewing, the first points at a copy of the accessor whose pattern is the bank block (the block lies 4 bytes in front of its file),
; the second at that copy minus the accessor's place in the pattern. The engine and the sound read the pattern in RAM through other
; paths and stay on what plays. -> r0 = 1 when the pattern the display reads changed. Clobbers r0 to r3 and r12.
pc_view_cells:
    push {r4, r5, lr}
    mvn r4, #0                  ; the bank pattern to show, none
    ldr r3, =STATE
    ldr r0, [r3, #S_BROWSE]
    cmp r0, #1
    beq pv_want
    ldr r0, [r3, #S_ARMED]
    cmp r0, #1
    bne pv_set
pv_want:
    bl pc_active
    cmp r0, #0
    beq pv_set
    bl PSEL
    ldrb r1, [r0, #0x341]
    cmp r1, #0
    beq pv_set
    ldr r4, [r0, #0x318]
    bl PLAYER
    ldr r1, [r0, #0x318]
    cmp r1, r4
    mvneq r4, #0                ; back on the pattern that runs: its own display
    cmp r4, #249
    mvnhi r4, #0
pv_set:
    ldr r5, =VIEW_W
    ldr r0, [r5, #V_NUM]
    cmp r0, r4
    beq pv_same
    ldr r0, =PATPTR
    ldr r0, [r0]
    cmp r0, #0
    beq pv_same
    str r4, [r5, #V_NUM]
    bl VIEW_NEW
    add r1, r0, #0x4000         ; the accessor inside the pattern in RAM, 0x400C in
    add r1, r1, #0xC
    cmn r4, #1
    beq pv_cells
    mov r2, #0
pv_copy:
    ldr r3, [r1, r2]
    str r3, [r5, r2]
    add r2, r2, #4
    cmp r2, #V_NUM
    blo pv_copy
    ldr r3, =BANK
    add r3, r3, r4, lsl #14
    sub r3, r3, #4
    str r3, [r5, #4]
    mov r1, r5
pv_cells:
    ldr r2, =CELL_W
    str r1, [r2]
    sub r1, r1, #0x4000
    sub r1, r1, #0xC
    ldr r2, =CELL_O
    str r1, [r2]
    mov r0, #1
    pop {r4, r5, pc}
pv_same:
    mov r0, #0
    pop {r4, r5, pc}

; Draws the pads of the current mode again (the part mutes and the steps), from the UI task. Clobbers r0 to r3 and r12.
pc_view_refresh:
    push {lr}
    ldr r0, =LED_MGR
    ldr r0, [r0]
    cmp r0, #0
    popeq {pc}
    bl VIEW_REFRESH
    pop {pc}

; r0 = the selection object, r1 = number: the display is told as SET_NUMBER tells it. Clobbers r0 to r3 and r12.
pc_notify:
    push {r4, lr}
    sub sp, sp, #8
    mov r2, #1
    strb r2, [sp]
    strb r1, [sp, #1]
    mov r2, #0
    str r2, [sp, #4]
    add r0, r0, #4
    mov r1, sp
    bl NOTIFY
    add sp, sp, #8
    pop {r4, pc}

; -> r0 = 1 when the pattern in RAM differs from its place in the bank (unsaved changes), bytes 0x3C, 0x3E and 0x3F left out. Clobbers r0 to r3 and r12.
pc_dirty:
    push {r4, lr}
    bl PLAYER
    ldr r1, [r0, #0x318]
    cmp r1, #249
    bhi pd_clean
    ldr r2, =BANK
    add r2, r2, r1, lsl #14
    ldr r0, =PATPTR
    ldr r0, [r0]
    cmp r0, #0
    beq pd_clean
    add r0, r0, #4
    ldr r3, =VIEW_W
    ldr r3, [r3, #V_SGNUM]
    cmp r3, r2                  ; the carry's bank block is this pattern's place
    beq pd_synced
    add r4, r0, #0x40           ; behind the word of byte 0x3C: of it only the MFX type (0x3D) counts. 0x3C, pad touched, each load sets
    ldr r3, =PAT_WORDS          ; anew; 0x3E and 0x3F, pad X and Y, a touch of the pad writes (device wish 25.10.): not edits
pd_word:
    ldr r1, [r0], #4
    ldr r12, [r2], #4
    cmp r0, r4
    andeq r1, r1, #0xFF00
    andeq r12, r12, #0xFF00
    cmp r1, r12
    bne pd_dirty
    subs r3, r3, #1
    bne pd_word
pd_clean:
    mov r0, #0
    pop {r4, pc}
pd_dirty:
    mov r0, #1
    pop {r4, pc}

; The pattern in RAM came in through a sync group's carry: the values the group carries (sg_walk) differ from the bank block on
; purpose, so they are also compared with SG_BUF, which holds what the carry put there. Everything else, and the exclusions above, as
; before. The values are visited in address order, which is the order sg_walk stored them in. r0 = the pattern in RAM, r2 = its place in the bank.
pd_synced:
    push {r5-r8}
    ldr r4, =SG_BUF
    ldr r5, =sg_head_at
    mov r6, #0                  ; the offset inside the part, once the parts begin
    mov r3, #0                  ; the offset in the block
pd_byte:
    mov r1, #0                  ; 1 when this offset is a carried value
    cmp r3, #0x800
    bhs pd_part
    ldr r12, [r5]
    cmp r12, r3
    moveq r1, #1
    addeq r5, r5, #4
    b pd_cmp
pd_part:
    cmp r3, #0x3B00
    bhs pd_cmp
    sub r12, r6, #1
    cmp r12, #0x2E              ; 1 to 0x2F of a part
    movls r1, #1
pd_cmp:
    ldrb r7, [r0, r3]
    ldrb r8, [r2, r3]
    cmp r1, #0
    beq pd_plain
    ldrb r12, [r4], #1
    cmp r7, r12                 ; a carried value counts as the carry's or, after a WRITE, as the bank's
    beq pd_skip
pd_plain:
    cmp r3, #0x3C
    cmpne r3, #0x3E
    cmpne r3, #0x3F
    beq pd_skip
    cmp r7, r8
    bne pd_sdirty
pd_skip:
    cmp r3, #0x800
    addhs r6, r6, #1
    cmp r6, #0x330
    moveq r6, #0
    add r3, r3, #1
    cmp r3, #0x4000
    blo pd_byte
    pop {r5-r8}
    b pd_clean
pd_sdirty:
    pop {r5-r8}
    b pd_dirty

; the stopped browse is over: nothing pending, the number in RAM chosen and shown. Keeps r4 to r11.
pc_stopped_end:
    push {r4, r5, lr}
    ldr r3, =STATE
    mov r0, #0
    str r0, [r3, #S_STOPPED]
    str r0, [r3, #S_BROWSE]
    bl PSEL
    mov r4, r0
    mov r0, #0
    strb r0, [r4, #0x341]
    bl PLAYER
    ldr r5, [r0, #0x318]
    str r5, [r4, #0x318]
    mov r0, r4
    mov r1, r5
    bl pc_notify
    bl pc_led
    pop {r4, r5, pc}

; ===================================================== a pad or a program change chooses: that is a deliberate choice
pad_hook:
    push {r0, r12}
    ldr r12, =STATE
    mov r0, #0
    str r0, [r12, #S_ARMED]
    str r0, [r12, #S_BROWSE]
    str r0, [r12, #S_STOPPED]
    pop {r0, r12}
    push {r0, r1, r2, r3, r12, lr}
    bl pc_led
    pop {r0, r1, r2, r3, r12, lr}
    push {r4, lr}               ; the replaced first instruction
    b @PAD_BODY@

midi_hook:
    push {r0, r12}
    ldr r12, =STATE
    mov r0, #0
    str r0, [r12, #S_ARMED]
    str r0, [r12, #S_BROWSE]
    str r0, [r12, #S_STOPPED]
    pop {r0, r12}
    push {r0, r1, r2, r3, r12, lr}
    bl pc_led
    pop {r0, r1, r2, r3, r12, lr}
    push {r3, r4, r5, lr}       ; the replaced first instruction
    b @MIDI_BODY@

; ===================================================== MENU on the main screen
; Slot of the main screen's class: r0 = the screen. The firmware ignores MENU while a pattern is pending; this confirms
; a browsed pattern (MIDI goes out now, the pattern starts at the sequence end). Anything else is the firmware's.
menu_hook:
    push {r4, r5, r6, lr}
    mov r4, r0
    bl pc_active
    cmp r0, #0
    beq mn_stock
    bl pc_stopped_browse
    cmp r0, #0
    bne mn_load
    bl PSEL
    mov r5, r0
    ldrb r0, [r5, #0x341]
    cmp r0, #0
    beq mn_stock
    ldr r3, =STATE
    ldr r0, [r3, #S_BROWSE]
    cmp r0, #1
    bne mn_stock
    ldr r0, [r5, #0x318]
    str r0, [r3, #S_ARMNUM]     ; the number first, the engine task reads it as soon as S_ARMED is 1
    mov r1, #1
    str r1, [r3, #S_ARMED]
    mov r1, #0
    str r1, [r3, #S_BROWSE]
    str r1, [r3, #S_AUTO]
    mov r1, r0
    mov r0, r5
    mov r2, #1                  ; Bank Select and Program Change now, and the display is told
    bl SET_NUMBER
    bl pc_led
    pop {r4, r5, r6, pc}
mn_stock:
    mov r0, r4
    pop {r4, r5, r6, lr}
    b MENU_ORIG
mn_load:                        ; stopped: the browsed pattern is loaded now, the edit is given up on purpose
    bl VIEW_TAKE
    ldr r3, =STATE
    mov r1, #0
    str r1, [r3, #S_STOPPED]
    str r1, [r3, #S_BROWSE]
    bl PSEL
    mov r5, r0
    mov r1, #0
    strb r1, [r5, #0x341]
    ldr r1, [r5, #0x318]
    mov r2, #1
    bl SET_NUMBER
    bl pc_led
    pop {r4, r5, r6, pc}

; -> r0 = 1 while a stopped browse is open and the sequencer stands. Clobbers r0 to r3 and r12.
pc_stopped_browse:
    push {r4, lr}
    ldr r3, =STATE
    ldr r0, [r3, #S_STOPPED]
    cmp r0, #1
    bne psb_no
    bl TRANSPORT
    ldr r0, [r0, #0x308]
    cmp r0, #0
    moveq r0, #1
    popeq {r4, pc}
psb_no:
    mov r0, #0
    pop {r4, pc}

; ===================================================== EXIT on the main screen
; Browsing goes back to the confirmed number, or to the one that runs. A confirmation without browsing is taken back,
; with the program change for the running pattern. Anything else is the firmware's.
exit_hook:
    push {r4, r5, r6, lr}
    mov r4, r0
    bl pc_active
    cmp r0, #0
    beq ex_stock
    bl pc_stopped_browse
    cmp r0, #0
    beq ex_playing
    bl pc_stopped_end           ; stopped: stay on the edited pattern
    pop {r4, r5, r6, pc}
ex_playing:
    bl PSEL
    mov r5, r0
    ldrb r0, [r5, #0x341]
    cmp r0, #0
    beq ex_stock
    ldr r6, =STATE
    ldr r0, [r6, #S_BROWSE]
    cmp r0, #1
    beq ex_browse
    ldr r0, [r6, #S_ARMED]
    cmp r0, #1
    bne ex_stock
    mov r0, #0                  ; take the confirmation back
    str r0, [r6, #S_ARMED]
    bl PLAYER
    ldr r1, [r0, #0x318]
    mov r0, r5
    mov r2, #1
    bl SET_NUMBER
    bl pc_led
    pop {r4, r5, r6, pc}
ex_browse:
    mov r0, #0
    str r0, [r6, #S_BROWSE]
    ldr r0, [r6, #S_ARMED]
    cmp r0, #1
    ldreq r1, [r6, #S_ARMNUM]
    beq ex_to
    bl PLAYER
    ldr r1, [r0, #0x318]
ex_to:
    mov r0, r5
    mov r2, #0
    bl SET_NUMBER
    ldrb r0, [r5, #0x341]
    cmp r0, #0
    bne ex_out
    mov r0, #0                  ; back on the running pattern, nothing is confirmed any more
    str r0, [r6, #S_ARMED]
ex_out:
    bl pc_led
    pop {r4, r5, r6, pc}
ex_stock:
    mov r0, r4
    pop {r4, r5, r6, lr}
    b EXIT_ORIG

; ===================================================== sequence end
; Replaces the call that fetches the number to start (r0 = the selection object). Engine task: this only reads.
; Confirmed: that number (and the state is over). Browsing: the one that runs, so the pattern repeats or chains as it does
; without a choice. Anything else: the chosen number as always.
seq_hook:
    push {r4, lr}
    mov r4, r0
    bl pc_active
    cmp r0, #0
    beq sq_plain
    ldrb r0, [r4, #0x341]
    cmp r0, #0
    beq sq_plain
    ldr r3, =STATE
    ldr r0, [r3, #S_ARMED]
    cmp r0, #1
    bne sq_browse
    ldr r4, [r3, #S_ARMNUM]
    mov r1, #0
    str r1, [r3, #S_ARMED]
    str r1, [r3, #S_BROWSE]
    bl VIEW_TAKE                ; the viewed pattern is the one that loads: it takes the mutes set on its pads
    bl pc_led_engine            ; the firmware sets LEDs from this task too (the beat flash of TAP)
    mov r0, r4
    pop {r4, pc}
sq_browse:
    ldr r0, [r3, #S_BROWSE]
    cmp r0, #1
    bne sq_plain
    bl PLAYER
    ldr r0, [r0, #0x318]
    pop {r4, pc}
sq_plain:
    ldr r0, [r4, #0x318]
    pop {r4, pc}

; ===================================================== STOP
; First instruction of the function that applies a pending pattern at once (r0 = the selection object). A confirmed
; pattern is applied as the firmware does; a browse is dropped, the playing pattern stays and nothing is pending.
stop_hook:
    push {r1, r2, r3, r4, r5, lr}
    mov r4, r0
    bl pc_active
    cmp r0, #0
    beq st_out
    ldr r3, =STATE
    ldr r0, [r3, #S_STOPPED]
    cmp r0, #1
    bne st_playing
    bl pc_stopped_end           ; a stopped browse never loads: the edited pattern stays (the firmware's reload would drop it)
    b st_out
st_playing:
    ldrb r0, [r4, #0x341]
    cmp r0, #0
    beq st_out
    ldr r3, =STATE
    ldr r0, [r3, #S_ARMED]
    cmp r0, #1
    ldreq r0, [r3, #S_ARMNUM]
    streq r0, [r4, #0x318]
    bleq VIEW_TAKE              ; keeps the flags
    beq st_flags
    ldr r0, [r3, #S_BROWSE]
    cmp r0, #1
    bne st_out                  ; pending from a pad or a program change: the firmware's
    bl PLAYER
    ldr r1, [r0, #0x318]
    str r1, [r4, #0x318]
    mov r2, #0
    strb r2, [r4, #0x341]
    mov r0, r4
    bl SET_NUMBER               ; the firmware leaves the chosen number alone once it is the running one: written above, this tells the display
st_flags:
    ldr r3, =STATE
    mov r0, #0
    str r0, [r3, #S_ARMED]
    str r0, [r3, #S_BROWSE]
    bl pc_led
st_out:
    mov r0, r4
    pop {r1, r2, r3, r4, r5, lr}
    ldrb r3, [r0, #0x341]       ; the replaced first instruction
    b @STOP_BODY@

; ===================================================== the label of the lower line
; Replaces the load of "NEXT:" in the builder of that line (bl, so lr is ours; r0 = the screen must survive).
; Browsing shows VIEW: instead, a confirmed pattern keeps NEXT:.
label_hook:
    push {r0, lr}
    bl pc_active
    cmp r0, #0
    beq lb_next
    bl PSEL
    mov r3, r0
    ldrb r0, [r3, #0x341]
    cmp r0, #0
    beq lb_next
    ldr r1, [sp]                ; the screen: the info line's index while the label stands (info_hook)
    ldr r1, [r1, #0x54]
    ldr r2, =VIEW_W
    str r1, [r2, #V_LIDX]
    ldr r2, =STATE
    ldr r0, [r2, #S_BROWSE]
    cmp r0, #1
    bne lb_next
    ldr r1, =view_text
    pop {r0, pc}
lb_next:
    ldr r1, =NEXT_TEXT
    pop {r0, pc}

; ===================================================== the info line while viewing
; First instruction of the info line's builder that reads the label flag (r0 = the screen, r3 = the flag): while the lower line says
; VIEW: or NEXT: the builder does nothing. When the Edit key stepped the line on from where it was while the label was built, the flag is
; read as clear, so the line shows OSC, PITCH and the rest of the pattern that is viewed. Only r3 and r12 are used, and the state
; address is built without a literal: the main screen draws during the start.
info_hook:
    ldrb r3, [r0, #0x5c]
    cmp r3, #0
    beq ih_back
    mov r12, #(VIEW_W & 0xFF000000)
    orr r12, r12, #(VIEW_W & 0x00FF0000)
    orr r12, r12, #(VIEW_W & 0x0000FF00)
    orr r12, r12, #(VIEW_W & 0x000000FF)
    ldr r3, [r12, #V_NUM]
    cmn r3, #1
    beq ih_flag
    ldr r3, [r12, #V_LIDX]
    ldr r12, [r0, #0x54]
    cmp r12, r3
    movne r3, #0
    bne ih_back
ih_flag:
    ldrb r3, [r0, #0x5c]
ih_back:
    b @INFO_BODY@

; ===================================================== pad presses during a command
; The pad handler (r7 = pad, r4 = pressed, r8 = velocity, r9 = source) drops a press while the command runner is busy, a pattern load
; among others: a pad hit right on the change of a pattern was lost (device report 25.10.; emulator: presses from 1 ms before to
; 4 ms after the change). The gate keeps such a press and the presses and releases behind it, the command end hands them to the
; handler in their order. One writer each (the panel task keeps, the command task hands on), so the two counters need no lock.
; least-code: four presses at most, a fifth is dropped as by the firmware; if the panel task does not run above the command task, a
; press kept while the last one is handed on waits for the next command.
pad_gate:
    bl pc_active
    cmp r0, #0
    beq pdg_firmware
    tst r9, #REPLAYED           ; a kept press handed on went through VIEW_PAD when it came
    bicne r9, r9, #REPLAYED
    bne @PGATE_CONT@
    mov r0, r7                  ; while a pattern is viewed its pads take the presses (VIEW_PAD)
    mov r1, r4
    bl VIEW_PAD
    cmp r0, #0
    bne @PGATE_SKIP@
    ldr r3, =STATE
    ldrb r0, [r3, #S_PADH]
    ldrb r1, [r3, #S_PADT]
    cmp r0, r1
    bne pdg_keep                ; presses wait: this one goes behind them, released or not
    bl @CMD_BUSY@
    cmp r0, #0
    beq @PGATE_CONT@
    cmp r4, #0
    beq @PGATE_CONT@            ; a release passes, as in the firmware
pdg_keep:
    ldr r3, =STATE
    ldrb r0, [r3, #S_PADH]
    ldrb r1, [r3, #S_PADT]
    sub r2, r0, r1
    and r2, r2, #0xFF
    cmp r2, #PADQ_SIZE
    bhs @PGATE_SKIP@
    and r2, r0, #PADQ_SIZE - 1
    add r2, r3, r2, lsl #2
    strb r7, [r2, #S_PADQ]
    strb r4, [r2, #S_PADQ + 1]
    strb r8, [r2, #S_PADQ + 2]
    strb r9, [r2, #S_PADQ + 3]
    add r0, r0, #1
    strb r0, [r3, #S_PADH]
    b @PGATE_SKIP@
pdg_firmware:                   ; the replaced bl and what follows it
    bl @CMD_BUSY@
    cmp r0, #0
    beq @PGATE_CONT@
    cmp r4, #0
    bne @PGATE_SKIP@
    b @PGATE_CONT@

; Replaces the clear of the busy byte (r6 = the runner, r3 = 0) and then hands the kept pad presses to the handler. Runs during the
; start too (the first pattern load): STATE is built without a literal, and FF in both counters means nothing kept.
pad_replay:
    strb r3, [r6, #0x10]
    push {r4, lr}
    mov r4, #(STATE & 0xFF000000)
    orr r4, r4, #(STATE & 0x00FF0000)
    orr r4, r4, #(STATE & 0x0000FF00)
pr_next:
    ldrb r0, [r4, #S_PADT]
    ldrb r1, [r4, #S_PADH]
    cmp r0, r1
    beq pr_done
    and r2, r0, #PADQ_SIZE - 1
    add r2, r4, r2, lsl #2
    add r0, r0, #1
    ldrb r3, [r2, #S_PADQ + 3]
    orr r3, r3, #REPLAYED
    ldrb r1, [r2, #S_PADQ + 1]
    ldrb r12, [r2, #S_PADQ]
    ldrb r2, [r2, #S_PADQ + 2]
    strb r0, [r4, #S_PADT]      ; handed on before the call: the gate sees it gone
    mov r0, r12
    bl @PAD_HANDLER@
    b pr_next
pr_done:
    mov r3, #0
    pop {r4, pc}

; ===================================================== the stopped sync
; First instruction of the function that, stopped, loads a chosen number that does not run (0xC0081E18, called on and on).
; During a stopped browse it does nothing: the browsed number stays chosen and pending, the edited pattern stays loaded.
; The function is an observer called through a member pointer, often and from other tasks: the hook only reads its own word
; (S_STOPPED is 1 only after the wheel found the patch on) and touches nothing but r12, which a callee may use.
sync_hook:
    mov r12, #(STATE & 0xFF000000)  ; STATE built without a literal, so the start phase reads nothing outside this code
    orr r12, r12, #(STATE & 0x00FF0000)
    orr r12, r12, #(STATE & 0x0000FF00)
    ldr r12, [r12, #S_STOPPED]
    cmp r12, #1
    bxeq lr
    push {r4, r5, r6, lr}       ; the replaced first instruction
    b @SYNC_BODY@

; r7 is the source block. Only a playing load from a different bank block of the same group keeps voices.
voice_begin:
    push {r0-r6, lr}
    mov r4, #0
    mov r0, #(PANEL & 0xFF000000)
    orr r0, r0, #(PANEL & 0x00FF0000)
    orr r0, r0, #(PANEL & 0x0000FF00)
    orr r0, r0, #(PANEL & 0x000000FF)
    ldr r0, [r0]
    cmp r0, #0
    beq vb_off
    ldr r0, [r0, #0x18]
    tst r0, #KILL
    bne vb_off
    bl TRANSPORT
    ldr r0, [r0, #0x308]
    cmp r0, #0
    beq vb_off
    mov r0, r7
    bl sg_banked
    cmp r0, #0
    beq vb_off
    mov r5, #(STATE & 0xFF000000)
    orr r5, r5, #(STATE & 0x00FF0000)
    orr r5, r5, #(STATE & 0x0000FF00)
    ldr r0, [r5, #S_LOADED]
    cmp r0, r7
    beq vb_off
    mov r0, #(PATPTR & 0xFF000000)
    orr r0, r0, #(PATPTR & 0x00FF0000)
    orr r0, r0, #(PATPTR & 0x0000FF00)
    orr r0, r0, #(PATPTR & 0x000000FF)
    ldr r0, [r0]
    add r0, r0, #4
    bl pc_group
    movs r6, r0
    beq vb_off
    mov r0, r7
    bl pc_group
    cmp r0, r6
    moveq r4, #1
vb_off:
    mov r12, #(STATE & 0xFF000000)
    orr r12, r12, #(STATE & 0x00FF0000)
    orr r12, r12, #(STATE & 0x0000FF00)
    str r4, [r12, #S_VOICES]
    cmp r4, #1
    pop {r0-r6, lr}
    bne VOICE_BEGIN_ORIG
    b VOICE_CONT

view_text:
    .asciz "VIEW:"
.align 4
lit_pool:
.pool
"""


# the synth has no wrap function (its selector wraps inline); the patch carries its own for 0..249
WRAP_LOCAL = """
wrap_local:                     ; (value, 0, 249) like the firmware's, the range is the synth's pattern count
    cmp r0, #0
    addlt r0, r0, #250
    cmp r0, #249
    subgt r0, r0, #250
    bx lr
"""


def source():
    text = SOURCE.replace("@CARD_CHECK@", card_gate.source("synth" if SYNTH else "hacktribe", "pa_no", STATE + card_gate.LATCH_OFFSET))
    if SYNTH:
        text = synthaddr.source(text, own=[(STATE, STATE_END)], keep={0xC0040D24}).replace("bl WRAP", "bl wrap_local").replace("\nview_text:", WRAP_LOCAL + "\nview_text:")
    for key, value in {
        "SELECT": f"{SELECT:#x}", "MENU_ORIG": f"{MENU_ORIG:#x}", "EXIT_ORIG": f"{EXIT_ORIG:#x}", "NEXT_TEXT": f"{NEXT_TEXT:#x}",
        "KILL": f"{KILL_SWITCH:#x}", "STATE": f"{STATE:#x}", "CODE_AT": f"{CODE_AT:#x}", "PAD_BODY": f"{PAD_BODY:#x}",
        "MIDI_BODY": f"{MIDI_BODY:#x}", "STOP_BODY": f"{STOP_BODY:#x}", "SYNC_BODY": f"{SYNC_BODY:#x}",
        "GROUPS": "1", "GROUP_AT": f"{GROUP_AT:#x}", "MEMCPY": f"{MEMCPY:#x}", "SG_BUF": f"{SG_BUF:#x}",
        "VIEW_W": f"{VIEW_W:#x}", "INFO_BODY": f"{INFO_BODY:#x}",
        "CELL_W": f"{CELL_W:#x}", "CELL_O": f"{CELL_O:#x}", "PADS_REFRESH": f"{PADS_REFRESH:#x}",
        "PGATE_CONT": f"{PGATE_CONT:#x}", "PGATE_SKIP": f"{PGATE_SKIP:#x}", "PAD_HANDLER": f"{PAD_HANDLER:#x}", "CMD_BUSY": f"{CMD_BUSY:#x}",
        "VOICE_BEGIN_ORIG": f"{VOICE_BEGIN_ORIG:#x}",
        "VOICE_CONT": f"{VOICE_CONT:#x}", "VIEW_CODE": f"{VIEW_CODE:#x}",
    }.items():
        text = text.replace(f"@{key}@", value)
    return text


def build_code():
    code = arm.assemble(source())
    (at, data), = code.sections
    return at, data, code.symbols


def build_voice_code():
    return arm.assemble(f"""
.equ STATE, {STATE}
.equ S_VOICES, {S_VOICES}
.org {VOICE_CODE}
voice_silence:
    ldr r12, =STATE
    ldr r12, [r12, #S_VOICES]
    cmp r12, #1
    bne {VOICE_SILENCE_ORIG}
    bx lr
voice_clear:
    ldr r12, =STATE
    ldr r12, [r12, #S_VOICES]
    cmp r12, #1
    bxeq lr
    ldr r3, [r0, #0x14]
    b {NOTE_CLEAR_BODY}
voice_flush:
    ldr r12, =STATE
    ldr r12, [r12, #S_VOICES]
    cmp r12, #1
    bne {NOTE_FLUSH_ORIG}
    bx lr
voice_assign:
    ldr r12, =STATE
    ldr r12, [r12, #S_VOICES]
    cmp r12, #1
    bne {NOTE_ASSIGN_ORIG}
    bx lr
voice_reset:
    ldr r12, =STATE
    ldr r12, [r12, #S_VOICES]
    cmp r12, #1
    bne {VOICE_RESET_ORIG}
    bx lr
voice_end:
    push {{r4, lr}}
    bl {VOICE_END_ORIG}
    ldr r12, =STATE
    mov r4, #0
    str r4, [r12, #S_VOICES]
    pop {{r4, pc}}
.pool
""")


# While a pattern is viewed (pc_view_cells), its pads are the ones the presses go to (Pascal's decision 29.10.): PART MUTE mutes
# and unmutes the parts of the viewed pattern, SEQUENCER drops the press (the playing pattern's steps stay as they are), and the
# pattern takes those mutes when it is switched to. The mutes live beside VIEW_W (V_MUTE, V_MTOUCH: one bit per part, only the
# parts touched count) and reach the display through the firmware's part mute getter: called with the view's accessor (only the
# display passes it, through the cell) it answers from them. docs/messungen/2026-10-29-vorschau-pads.md
# The first press on a part's pad brings it into the playing pattern at once, unmuted (decision 30.10., docs/ideen/82-vorschau-part-reinholen.md):
# the press goes on to the firmware, and where the main screen sets the mute (UI task) view_copy runs the firmware's own Copy Part
# from the viewed pattern's bank block and sets the part unmuted. From then on the pad of that part mutes and unmutes it in both.
# docs/messungen/2026-10-30-vorschau-part-reinholen.md
VIEW_SOURCE = """
.equ VIEW_W, @VIEW_W@
.equ V_NUM, 0x40                ; the bank pattern the display shows, FFFFFFFF none
.equ V_MNUM, 0x4C               ; the bank pattern V_MUTE and V_MTOUCH belong to
.equ V_MTOUCH, 0x50             ; one bit per part: muted or unmuted on the pads while viewed
.equ V_MUTE, 0x54               ; one bit per part: 1 muted (the firmware's part byte 1)
.equ V_TAKE, 0x58               ; 1 from the switch to the viewed pattern until its load (copy_hook): the mutes go along
.equ V_PEND, 0x5C               ; one bit per part: unmuted on the pads, its copy waits for the main screen (view_copy)
.equ V_COPY, 0x60               ; one bit per part: brought into the playing pattern while this pattern is viewed
.equ PSEL, 0xC00431F0           ; returns the pattern selection object: +0x318 the chosen number
.equ PLAYER, 0xC002FAFC         ; returns the player: +0x318 the number that runs
.equ MUTE_SET, @MUTE_SET@
.equ COPY_PART, @COPY_PART@
.equ BANK, 0xC08B2940
.equ LED_MGR, 0xC0345A1C
.equ LED_SEND, 0xC00875F4       ; (manager, led, force)
.equ MODE_AT, 0xB58             ; manager + 0xB58: the pad mode, 0 PART MUTE, 4 SEQUENCER
.equ LED_PAD_FIRST, 0x2C        ; the pads' LEDs, red and blue of each, 32 in all
.equ PADS_REFRESH, @PADS_REFRESH@
.equ MUTE_BODY, @MUTE_GET_BODY@
.org @VIEW_CODE@
    b view_new                  ; +0  r4 = the pattern the view shows now (FFFFFFFF none)
    b view_pad                  ; +4  (pad, pressed) -> r0 = 1 when the view took it
    b view_take                 ; +8  the viewed pattern is about to load
    b view_apply                ; +12 the pattern load's copy (r4 = the pattern in RAM, r5 = the source)
    b view_refresh              ; +16 (manager) the pads drawn again
    b view_pads                 ; +20 the pads sent again
    b view_copy                 ; +24 the main screen's mute setter call

; The firmware's part mute getter (r0 = accessor, r1 = part) -> r0 = the part's mute byte. The engine and everything else pass
; the pattern's own accessor; only the display, through the cell, passes VIEW_W: then a part touched on the pads answers with
; what the pads set. Runs during the start (the first pattern load reads the mutes): no literal. Clobbers r1 to r3 and r12.
view_mute:
    mov r12, #(VIEW_W & 0xFF000000)
    orr r12, r12, #(VIEW_W & 0x00FF0000)
    orr r12, r12, #(VIEW_W & 0x0000FF00)
    orr r12, r12, #(VIEW_W & 0x000000FF)
    cmp r0, r12
    bne vm_plain
    ldr r2, [r12, #V_MTOUCH]
    mov r3, #1
    tst r2, r3, lsl r1
    beq vm_plain
    ldr r2, [r12, #V_MUTE]
    tst r2, r3, lsl r1
    moveq r0, #0
    movne r0, #1
    bx lr
vm_plain:
    ldr r3, [r0, #4]            ; the replaced first instruction
    b MUTE_BODY

; From copy_hook, after the copy (and a sync group's carry) into the pattern in RAM: when the switch to the viewed pattern is
; due and the source is its bank block, the parts touched on the pads take the mutes set there. Every load ends the take.
; Runs during the start (V_TAKE is FF there): no literal. Keeps r4 to r11.
view_apply:
    mov r12, #(VIEW_W & 0xFF000000)
    orr r12, r12, #(VIEW_W & 0x00FF0000)
    orr r12, r12, #(VIEW_W & 0x0000FF00)
    orr r12, r12, #(VIEW_W & 0x000000FF)
    ldr r0, [r12, #V_TAKE]
    cmp r0, #1
    bxne lr
    mov r0, #0
    str r0, [r12, #V_TAKE]
    ldr r0, [r12, #V_MNUM]
    cmp r0, #249
    bhi va_clear
    mov r1, #(BANK & 0xFF000000)
    orr r1, r1, #(BANK & 0x00FF0000)
    orr r1, r1, #(BANK & 0x0000FF00)
    orr r1, r1, #(BANK & 0x000000FF)
    add r1, r1, r0, lsl #14
    cmp r1, r5
    bne va_clear
    ldr r0, [r12, #V_MTOUCH]
    ldr r1, [r12, #V_MUTE]
    add r2, r4, #0x800
    mov r3, #1
va_part:
    tst r0, r3
    beq va_next
    tst r1, r3
    push {r0}
    moveq r0, #0
    movne r0, #1
    strb r0, [r2, #1]
    pop {r0}
va_next:
    add r2, r2, #0x330
    mov r3, r3, lsl #1
    cmp r3, #0x10000
    blo va_part
va_clear:
    mov r0, #0
    str r0, [r12, #V_MTOUCH]
    bx lr
view_start_end:

; From pc_view_cells when the view changes (r4 = the pattern it shows now, FFFFFFFF none): another pattern starts without
; touched parts; the end of the view drops them, unless the viewed pattern is about to load (V_TAKE). Keeps r0, r4 and r5.
view_new:
    ldr r12, =VIEW_W
    cmn r4, #1
    beq vn_end
    ldr r1, [r12, #V_MNUM]
    cmp r1, r4
    bxeq lr
    str r4, [r12, #V_MNUM]
vn_clear:
    mov r1, #0
    str r1, [r12, #V_MTOUCH]
    str r1, [r12, #V_TAKE]
    str r1, [r12, #V_PEND]
    str r1, [r12, #V_COPY]
    bx lr
vn_end:
    ldr r1, [r12, #V_TAKE]
    cmp r1, #1
    bne vn_clear
    bx lr

; Keeps every register but r12 and the flags.
view_take:
    push {r0}
    ldr r12, =VIEW_W
    mov r0, #1
    str r0, [r12, #V_TAKE]
    pop {r0}
    bx lr

; From the pad gate (r0 = pad, r1 = pressed) -> r0 = 1 when the press is the view's alone. While a pattern is viewed, in PART MUTE
; the first press on a part brings it into the playing pattern, unmuted, muted in the bank or not (decision 30.10.): the press goes
; on to the firmware, marked in V_PEND, and view_copy copies it there. Every later press on it goes on as well, so the playing
; pattern mutes and unmutes it like the view. In SEQUENCER the press is dropped. Releases and other modes pass.
; Clobbers r0 to r3 and r12.
view_pad:
    push {r4, lr}
    cmp r1, #0
    beq vp_no
    ldr r12, =VIEW_W
    ldr r4, [r12, #V_NUM]
    cmp r4, #249
    bhi vp_no
    ldr r3, =LED_MGR
    ldr r3, [r3]
    cmp r3, #0
    beq vp_no
    ldr r3, [r3, #MODE_AT]
    cmp r3, #4
    beq vp_took
    cmp r3, #0
    bne vp_no
    cmp r0, #16
    bhs vp_no
    mov r3, #1
    mov r3, r3, lsl r0
    ldr r1, [r12, #V_COPY]
    tst r1, r3
    bne vp_flip                 ; brought in already: the playing pattern's mute follows the view's
    orr r1, r1, r3              ; the first press brings the part in, unmuted, whatever its mute in the bank
    str r1, [r12, #V_COPY]
    ldr r1, [r12, #V_PEND]
    orr r1, r1, r3
    str r1, [r12, #V_PEND]
    ldr r1, [r12, #V_MTOUCH]
    orr r1, r1, r3
    str r1, [r12, #V_MTOUCH]
    ldr r2, [r12, #V_MUTE]
    bic r2, r2, r3
    str r2, [r12, #V_MUTE]
    b vp_draw
vp_flip:
    ldr r2, [r12, #V_MUTE]
    eor r2, r2, r3
    str r2, [r12, #V_MUTE]
vp_draw:
    ldr r0, =LED_MGR
    ldr r0, [r0]
    bl view_refresh
    mov r0, #0                  ; goes on to the firmware: view_copy or the firmware's own mute
    pop {r4, pc}
vp_took:
    mov r0, #1
    pop {r4, pc}
vp_no:
    mov r0, #0
    pop {r4, pc}

; Replaces the main screen's call of the mute setter (r0 = the pattern's accessor, r1 = the part, r2 = the mute it sets, r3 = 1),
; UI task as the firmware's own Copy Part. A part pressed first on the pads of the viewed pattern (V_PEND, the pad's part or, for a
; stereo pair, the one right of it) is copied from the viewed pattern's bank block into the playing pattern first, sound, steps and
; motion, and set unmuted. Copy Part reads its source from the pattern in RAM when the source is the chosen number, which is the
; viewed one here: for the copy the chosen number is the one that runs, then it is given back. Every other call sets as it did.
view_copy:
    push {r0, r1, r2, r3, r4, r5, r6, lr}
    ldr r12, =VIEW_W
    ldr r4, [r12, #V_NUM]
    cmp r4, #249
    bhi vc_set
    ldr r5, [r12, #V_PEND]
    mov r6, #3
    ands r6, r5, r6, lsl r1
    beq vc_set
    bic r5, r5, r6
    str r5, [r12, #V_PEND]
    sub sp, sp, #0x48           ; Copy Part's object: only +0x40 to +0x42 are read (and +0x41 written)
    strb r4, [sp, #0x40]
    strb r1, [sp, #0x41]
    strb r1, [sp, #0x42]
    bl PSEL
    mov r5, r0
    ldr r6, [r5, #0x318]
    bl PLAYER
    ldr r0, [r0, #0x318]
    str r0, [r5, #0x318]
    mov r0, sp
    ldrb r1, [sp, #0x42]
    bl COPY_PART
    str r6, [r5, #0x318]
    add sp, sp, #0x48
    mov r0, #0
    str r0, [sp, #8]            ; r2: unmuted
vc_set:
    pop {r0, r1, r2, r3, r4, r5, r6, lr}
    b MUTE_SET

; r0 = the LED manager: the pads of the current mode drawn again, then every pad sent again, so the pad colours follow the view.
view_refresh:
    push {r4, lr}
    mov r4, r0
    bl PADS_REFRESH
    mov r0, r4
    pop {r4, lr}
    b vpd_mgr

; Every pad LED sent again (forced: the firmware sends a value only when it changed, the colour of a pad also follows the view,
; tools/patch/pad_colors.py). From the UI and from the engine task, as the firmware's own LED sends. Clobbers r0 to r3 and r12.
view_pads:
    ldr r0, =LED_MGR
    ldr r0, [r0]
vpd_mgr:
    cmp r0, #0
    bxeq lr
    push {r4, r5, lr}
    mov r4, r0
    mov r5, #LED_PAD_FIRST
vpd_led:
    mov r0, r4
    mov r1, r5
    mov r2, #1
    bl LED_SEND
    add r5, r5, #1
    cmp r5, #LED_PAD_FIRST + 32
    blo vpd_led
    pop {r4, r5, pc}
.pool
"""


def build_view_code():
    text = VIEW_SOURCE
    if SYNTH:
        text = synthaddr.source(text, own=[(VIEW_CODE, VIEW_CODE_END)])
    for key, value in {"VIEW_W": f"{VIEW_W:#x}", "VIEW_CODE": f"{VIEW_CODE:#x}", "PADS_REFRESH": f"{PADS_REFRESH:#x}",
                       "MUTE_GET_BODY": f"{MUTE_GET_BODY:#x}", "MUTE_SET": f"{MUTE_SET:#x}", "COPY_PART": f"{COPY_PART:#x}"}.items():
        text = text.replace(f"@{key}@", value)
    return arm.assemble(text)


def file_offset(addr):
    return addr - RAM + HEADER


def branch(at, target, link=False):
    return struct.pack("<I", (0xEB000000 if link else 0xEA000000) | ((target - (at + 8)) >> 2) & 0xFFFFFF)


def branch_word(at, target):
    return struct.unpack("<I", branch(at, target))[0]


def bl_word(at, target):
    return struct.unpack("<I", branch(at, target, True))[0]


def build_patch(vsb, build="hacktribe"):
    """The patch as a dict; `vsb` is the user's file, read for the hashes of the replaced bytes."""
    use_build(build)
    at, code, symbols = build_code()
    if at != CODE_AT or at + len(code) > CODE_END:
        raise SystemExit(f"code is {len(code):#x} bytes, room for {CODE_END - CODE_AT:#x}")
    voices = build_voice_code()
    (voice_at, voice_code), = voices.sections
    if voice_at != VOICE_CODE or voice_at + len(voice_code) > VOICE_END:
        raise SystemExit("voice hooks exceed their code area")
    symbols.update(voices.symbols)
    view = build_view_code()
    (view_at, view_code), = view.sections
    if view_at != VIEW_CODE or view_at + len(view_code) > VIEW_CODE_END:
        raise SystemExit("the view's code exceeds its area")
    symbols.update(view.symbols)

    def was(addr, n):
        return vsb[file_offset(addr):file_offset(addr) + n]

    def word(addr):
        return struct.unpack("<I", was(addr, 4))[0]

    def free(addr, n):
        if was(addr, n) != b"\xff" * n:
            raise SystemExit(f"{addr:#x}..{addr + n:#x} is not free in this VSB")
        return sha(was(addr, n))

    expected = (
        (WHEEL_HOOK, branch_word(WHEEL_HOOK, SELECT), "the wheel handler does not end in the branch into the selector"),
        (PAD_HOOK, PAD_WORD, "the pad selection does not start with push {r4, lr}"),
        (MIDI_HOOK, MIDI_WORD, "the program change handler does not start with push {r3, r4, r5, lr}"),
        (MENU_SLOT, MENU_ORIG, "the MENU slot of the main screen is not the one the patch expects"),
        (EXIT_SLOT, EXIT_ORIG, "the EXIT slot of the main screen is not the one the patch expects"),
        (SEQ_CALL, bl_word(SEQ_CALL, SEQ_FUNC), "the sequence end does not call the number fetch where the patch expects it"),
        (STOP_HOOK, STOP_WORD, "the pending applier does not start with ldrb r3, [r0, #0x341]"),
        (LABEL_HOOK, LABEL_WORD, "the lower line builder does not load NEXT: as the patch expects"),
        (SYNC_HOOK, SYNC_WORD, "the stopped sync of the pattern selection does not start with push {r4, r5, r6, lr}"),
    ) + ((COPY_CALL, bl_word(COPY_CALL, MEMCPY), "the pattern load does not copy with memcpy where the patch expects it"),
         (PGATE_HOOK, bl_word(PGATE_HOOK, CMD_BUSY), "the pad handler does not ask the command runner whether it is busy where the patch expects it"),
         (CMD_END, CMD_END_WORD, "the command runner does not clear its busy byte with strb r3, [r6, #0x10] where the patch expects it"),
         (INFO_HOOK, INFO_WORD, "the info line's builder does not start by reading the label flag where the patch expects it"),
         (VOICE_BEGIN_CALL, bl_word(VOICE_BEGIN_CALL, VOICE_BEGIN_ORIG), "the pattern load's pre-copy voice call differs"),
         (VOICE_SILENCE_CALL, bl_word(VOICE_SILENCE_CALL, VOICE_SILENCE_ORIG), "the pattern load's pre-copy silencing differs"),
         (VOICE_END_CALL, bl_word(VOICE_END_CALL, VOICE_END_ORIG), "the pattern load's post-copy voice call differs"),
         (VOICE_RESET_CALL, bl_word(VOICE_RESET_CALL, VOICE_RESET_ORIG), "the post-copy global voice reset differs"),
         (NOTE_CLEAR_HOOK, NOTE_CLEAR_WORD, "the held-note source cleanup does not start with ldr r3, [r0, #0x14]"),
         (NOTE_FLUSH_KEY, bl_word(NOTE_FLUSH_KEY, NOTE_FLUSH_ORIG), "the key setter's note-off call differs"),
         (NOTE_FLUSH_SCALE, bl_word(NOTE_FLUSH_SCALE, NOTE_FLUSH_ORIG), "the scale setter's note-off call differs"),
         (NOTE_FLUSH_VOICE, bl_word(NOTE_FLUSH_VOICE, NOTE_FLUSH_ORIG), "the voice setter's note-off call differs"),
         (NOTE_ASSIGN_CALL, bl_word(NOTE_ASSIGN_CALL, NOTE_ASSIGN_ORIG), "voice mode does not reinitialize the note slots where expected"),
         (MUTE_GET, MUTE_GET_WORD, "the part mute getter does not start with ldr r3, [r0, #4]"),
         (MUTE_SET_CALL, bl_word(MUTE_SET_CALL, MUTE_SET), "the main screen's PART MUTE pad does not call the mute setter where the patch expects it"),
         (COPY_PART, COPY_PART_WORD, "Copy Part does not start as the patch expects"))
    for addr, want, why in expected:
        if word(addr) != want:
            raise SystemExit(f"{why} in this VSB")
    literal = LABEL_HOOK + 8 + (LABEL_WORD & 0xFFF)
    if word(literal) != NEXT_TEXT:
        raise SystemExit("the load of NEXT: does not read the address of the NEXT: text in this VSB")
    if was(NEXT_TEXT, 6) != b"NEXT:\x00":
        raise SystemExit("the NEXT: text is not where the patch expects it in this VSB")
    free(STATE, STATE_END - STATE)
    free(SG_BUF, SG_SIZE)
    free(VIEW_W, VIEW_SIZE)

    def hook(addr, name, link, note):
        return {"file": file_offset(addr), "bytes": branch(addr, symbols[name], link).hex(), "expect": sha(was(addr, 4)), "note": note}

    def slot(addr, name, note):
        return {"file": file_offset(addr), "bytes": struct.pack("<I", symbols[name]).hex(), "expect": sha(was(addr, 4)), "note": note}

    def declare(addr, kind, chain, position, swallow, note):
        return {"site": f"{addr:#010X}".replace("0X", "0x"), "kind": kind, "chain": chain, "position": position, "swallow": swallow, "note": note}

    return {
        "format": "gelumpe-patch", "version": 1, "id": "pattern-switch", "builds": ["synth"] if build == "synth" else ["hacktribe", "stock"],
        "name": "Patternwechsel erst nach Bestaetigung (MENU)",
        "changes": [
            {"file": file_offset(CODE_AT), "bytes": code.hex(), "expect": free(CODE_AT, len(code)),
             "note": "pattern switch: wheel, MENU, EXIT, pad, program change, sequence end, STOP, label and stopped sync hooks"},
            {"file": file_offset(VOICE_CODE), "bytes": voice_code.hex(), "expect": free(VOICE_CODE, len(voice_code)),
             "note": "sync group: scoped post-copy voice reset and cleanup"},
            {"file": file_offset(VIEW_CODE), "bytes": view_code.hex(), "expect": free(VIEW_CODE, len(view_code)),
             "note": "view: the viewed pattern's pads take the part mute presses, its mutes go along at the switch"},
            hook(MUTE_GET, "view_mute", False, "first instruction of the part mute getter jumps to the view (the display's mutes of the viewed pattern)"),
            hook(MUTE_SET_CALL, "view_copy", True, "the main screen's PART MUTE pad: a part unmuted on the viewed pattern's pads is copied into the playing pattern (Copy Part) first"),
            hook(VOICE_BEGIN_CALL, "voice_begin", True, "same-group playing loads keep their sounding voices"),
            hook(VOICE_SILENCE_CALL, "voice_silence", True, "keep the voices of a protected group load"),
            hook(NOTE_CLEAR_HOOK, "voice_clear", False, "keep held-note ownership during a protected group load"),
            hook(NOTE_FLUSH_KEY, "voice_flush", True, "the key setter keeps a protected group's notes"),
            hook(NOTE_FLUSH_SCALE, "voice_flush", True, "the scale setter keeps a protected group's notes"),
            hook(NOTE_FLUSH_VOICE, "voice_flush", True, "the voice setter keeps a protected group's notes"),
            hook(NOTE_ASSIGN_CALL, "voice_assign", True, "the carried voice mode keeps its note slots"),
            hook(VOICE_END_CALL, "voice_end", True, "prepare the new samples and clear the voice protection"),
            hook(VOICE_RESET_CALL, "voice_reset", True, "skip the global reset only during a protected group load"),
            hook(WHEEL_HOOK, "wheel_hook", False, "the wheel's tail call into the selector goes through the hook"),
            hook(PAD_HOOK, "pad_hook", False, "first instruction of the pad selection jumps to the hook"),
            hook(MIDI_HOOK, "midi_hook", False, "first instruction of the program change handler jumps to the hook"),
            slot(MENU_SLOT, "menu_hook", "MENU of the main screen goes to the hook"),
            slot(EXIT_SLOT, "exit_hook", "EXIT of the main screen goes to the hook"),
            hook(SEQ_CALL, "seq_hook", True, "the sequence end asks the hook for the number to start"),
            hook(STOP_HOOK, "stop_hook", False, "first instruction of the pending applier jumps to the hook"),
            hook(LABEL_HOOK, "label_hook", True, "the load of NEXT: goes through the hook"),
            hook(SYNC_HOOK, "sync_hook", False, "first instruction of the stopped sync jumps to the hook"),
            hook(COPY_CALL, "copy_hook", True, "the copy of the pattern load goes through the hook (sync groups)"),
            hook(PGATE_HOOK, "pad_gate", False, "the busy check of the pad handler jumps to the gate"),
            hook(CMD_END, "pad_replay", True, "the clear of the command runner's busy byte goes through the hook"),
            hook(INFO_HOOK, "info_hook", False, "the label flag read of the info line's builder goes through the hook (view)"),
        ],
        "hooks": [
            declare(VOICE_BEGIN_CALL, "call", "pattern-load-voices", "replace", False, "same-group voice protection begins at the load"),
            declare(VOICE_SILENCE_CALL, "call", "pattern-load-voices", "replace", False, "global silencing outside a protected load"),
            declare(NOTE_CLEAR_HOOK, "instruction", "note-cleanup", "replace", True, "preserve held-note ownership during the group load"),
            declare(NOTE_FLUSH_KEY, "call", "note-flush", "replace", True, "preserve the group's notes while applying the key"),
            declare(NOTE_FLUSH_SCALE, "call", "note-flush", "replace", True, "preserve the group's notes while applying the scale"),
            declare(NOTE_FLUSH_VOICE, "call", "note-flush", "replace", True, "preserve the group's notes while applying voice mode"),
            declare(NOTE_ASSIGN_CALL, "call", "note-capacity", "replace", True, "the carried voice mode retains its active note slots"),
            declare(VOICE_END_CALL, "call", "pattern-load-voices", "after", False, "sample preparation completes and voice protection ends"),
            declare(VOICE_RESET_CALL, "call", "pattern-load-voices", "replace", False, "global voice reset outside a protected load"),
            declare(WHEEL_HOOK, "instruction", "pattern-set", "replace", False, "wheel while playing: browse with set_number(psel, n, 0) instead of the branch into the selector; set_number is still called, so what reacts to it still sees the number"),
            declare(PAD_HOOK, "instruction", "pattern-set", "before", False, "pad selection clears browse and confirmation"),
            declare(MIDI_HOOK, "instruction", "pattern-set", "before", False, "MIDI program change clears browse and confirmation"),
            declare(MENU_SLOT, "vtable-slot", "key-dispatch", "before", True, "MENU on the main screen confirms the browsed pattern"),
            declare(EXIT_SLOT, "vtable-slot", "key-dispatch", "before", True, "EXIT on the main screen takes the browse or the confirmation back"),
            declare(SEQ_CALL, "call", "sequence-end", "replace", False, "the pattern number the sequence end asks for"),
            declare(STOP_HOOK, "instruction", "stop-pending", "before", False, "STOP drops a browse, or applies the confirmed pattern as the firmware does"),
            declare(LABEL_HOOK, "instruction", "pattern-label", "replace", False, "VIEW: instead of NEXT: while browsing"),
            declare(SYNC_HOOK, "instruction", "stopped-sync", "before", False, "stopped, an unsaved pattern browsed away from: the chosen number is not loaded"),
            declare(COPY_CALL, "call", "pattern-load-copy", "replace", False, "the copy carries the state of the pattern that played (part sound and mutes, tempo, MFX) between two patterns of one sync group"),
            declare(PGATE_HOOK, "instruction", "pad-input", "replace", False, "a pad pressed while a command runs is kept instead of dropped"),
            declare(CMD_END, "instruction", "command-end", "after", False, "after the busy byte is cleared the kept pad presses go to the pad handler"),
            declare(INFO_HOOK, "instruction", "info-line", "before", False, "while the lower line says VIEW: or NEXT:, the Edit key still shows the info texts of the pattern that is viewed"),
            declare(MUTE_GET, "instruction", "part-mute-get", "before", False, "called with the view's accessor (only the display passes it) the mutes set on the viewed pattern's pads answer"),
            declare(MUTE_SET_CALL, "call", "part-mute-pad", "replace", False, "a part unmuted on the viewed pattern's pads is first copied from its bank block into the playing pattern with the firmware's Copy Part, then set unmuted; every other press sets the mute as before"),
        ],
        "startPhase": [
            {"file": file_offset(VOICE_BEGIN_CALL), "length": 4, "why": "the first pattern load goes through the voice guard; stopped, the original initializer runs"},
            {"file": file_offset(VOICE_SILENCE_CALL), "length": 4, "why": "the first pattern load retains the pre-copy silencing"},
            {"file": file_offset(NOTE_CLEAR_HOOK), "length": 4, "why": "note source cleanup also runs during startup, without group protection"},
            {"file": file_offset(NOTE_FLUSH_KEY), "length": 4, "why": "the first pattern applies its key and retains the note-off cleanup"},
            {"file": file_offset(NOTE_FLUSH_SCALE), "length": 4, "why": "the first pattern applies its scale and retains the note-off cleanup"},
            {"file": file_offset(NOTE_FLUSH_VOICE), "length": 4, "why": "the first pattern applies voice mode and retains the note-off cleanup"},
            {"file": file_offset(NOTE_ASSIGN_CALL), "length": 4, "why": "the first pattern initializes its note slots without protection"},
            {"file": file_offset(VOICE_END_CALL), "length": 4, "why": "the first pattern load prepares samples and clears the guard"},
            {"file": file_offset(VOICE_RESET_CALL), "length": 4, "why": "the first pattern load keeps its global voice reset"},
            {"file": file_offset(VOICE_CODE), "length": len(voice_code), "why": "post-copy reset guard and completion, including their state literal"},
            {"file": file_offset(SYNC_HOOK), "length": 4, "why": "the stopped sync is an observer the firmware calls from the start on; the hook reads its own state word (FF at start, not 1) and runs the original"},
            {"file": file_offset(COPY_CALL), "length": 4, "why": "the pattern load copies the first pattern into RAM during the start, through the copy hook"},
            {"file": file_offset(symbols["pc_group"]), "length": symbols["pc_notify"] - symbols["pc_group"], "why": "copy_hook, pc_group and the sync group walk: the panel's keys, the two sync groups and the loaded bank block read, the memcpy, the bank block remembered, no literal"},
            {"file": file_offset(CMD_END), "length": 4, "why": "the command runner clears its busy byte after the first pattern load of the start, through pad_replay"},
            {"file": file_offset(INFO_HOOK), "length": 4, "why": "the main screen builds its info line during the start, through info_hook"},
            {"file": file_offset(MUTE_GET), "length": 4, "why": "the first pattern load reads the part mutes through the getter, through view_mute"},
            {"file": file_offset(VIEW_CODE), "length": symbols["view_start_end"] - VIEW_CODE, "why": "the view's table, view_mute (an address compare, then the replaced instruction and the way back) and view_apply from copy_hook (its state word FF at start: nothing taken); no literal"},
            {"file": file_offset(symbols["info_hook"]), "length": symbols["pad_gate"] - symbols["info_hook"], "why": "info_hook: the label flag read, the view state read when it is set (FF at start: no view), the way back, no literal"},
            {"file": file_offset(symbols["pad_replay"]), "length": symbols["view_text"] - symbols["pad_replay"], "why": "pad_replay and sync_hook, one span (check.py allows a run of changed bytes only inside one span): pad_replay clears the busy byte and reads the two counters (FF, equal: nothing kept), sync_hook is one load, a compare, then the replaced instruction and the way back; no literal in either"},
        ],
        "ram": [
            ramdecl.area(STATE, STATE_END - STATE, "run time state: browse, armed, armed number, PS_SETTING at +0x10 for the BLECH menu, the stopped browse at +0x14, the loaded bank block at +0x1C, MENU's LED at +0x20, the kept pad presses at +0x24, the voice-load guard at +0x38", "tools/patch/pattern_switch.py:STATE"),
            ramdecl.area(SG_BUF, SG_SIZE, "sync group: the values carried into the new pattern during one pattern load", "tools/patch/pattern_switch.py:SG_BUF"),
            ramdecl.area(VIEW_W, VIEW_SIZE, "view: the accessor the display reads the browsed or confirmed pattern through, the number shown, the info line's index, the bank block of a sync group's carry, and the part mutes set on the viewed pattern's pads (pattern, touched, muted, taken at the switch, copy waiting, brought into the playing pattern)", "tools/patch/pattern_switch.py:VIEW_W"),
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
        print(f"section {at:#x} + {len(code):#x} bytes, state {STATE:#x}, setting word {PS_SETTING:#x}")
        for name, addr in sorted(symbols.items(), key=lambda kv: kv[1]):
            print(f"  {addr:#010x} {name}")
    text = json.dumps(patch, indent=1) + "\n"
    if a.out:
        a.out.write_text(text)
    elif not a.listing:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
