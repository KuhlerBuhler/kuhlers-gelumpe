"""WAV import from the native command handler on both red builds: Korg's import loads a user slot into the DSP alone and
SAMPLE EDIT opens on it as a preview, WRITE there keeps it in the card library and EXIT discards it; with no room in the
DSP the card library takes it at once. A factory slot (below 500) goes to Korg's import alone."""

import hashlib

CALL = 0xC0038DE0
NATIVE = 0xC003644C
COMMAND_TASK = 0xC06A2564
TRANSPORT_PTR = 0xC03405BC
SPANS = (
    (0xC0038D34, 76, "8090b73c5000a4ca768ce23b2546f0ccf81516f985815e0ffd017a8eeeb9fa73"),
    (0xC0038D80, 116, "db7b11637250adc5310f6b9bc361a1ba1c121e1010b7839e8019566ac648ff91"),
    (NATIVE, 164, "c4ac89bbfea3a7408d400000f4068129ee0f856852d281c2efa92f4698bca17f"),
    (0xC0082F1C, 156, "da7865ac59fe275b7a8ae47c9a20cc450a0d8443b98b798929b28b7e498c8673"),
    (0xC0030D28, 56, "fc97da3d3f6f0333ff88daa68868d00a08470e2452be9519afd172bf57305eca"),
)


def validate_firmware(vsb):
    for address, length, expected in SPANS:
        offset = address - 0xC0000000 + 0x100
        if hashlib.sha256(vsb[offset:offset + length]).hexdigest() != expected:
            raise ValueError(f"native import context differs at {address:#010x}")



def source(current_task, lock, *, prepare_missing=False):
    values = dict(NI_NATIVE=NATIVE, NI_COMMAND_TASK=COMMAND_TASK, NI_TASK=current_task,
                  NI_TRANSPORT=TRANSPORT_PTR, NI_LOCK=lock)
    return "".join(f".equ {key}, {value:#x}\n" for key, value in values.items()) + SOURCE.replace("@LIBRARY_PROBE@", "persist_library_probe" if prepare_missing else "0xC0035440")


SOURCE = r"""
; The capture-start transition and the card import exclude each other before either can yield.
sample_admit:
    .word 0xE10F3000
    orr r1, r3, #0x80
    .word 0xE121F001
    ldr r2, =NI_LOCK
    ldr r1, [r2]
    cmp r1, #0
    streq r0, [r2]
    .word 0xE121F003
    mov r0, r1
    bx lr

sample_leave:
    ldr r12, =NI_LOCK
    mov r1, #0
    str r1, [r12]
    bx lr

native_library_path:
    push {r0-r3, lr}
    cmp r0, #0
    beq ni_library_done
    ldr r1, =PANEL
    ldr r1, [r1]
    cmp r1, #0
    beq ni_library_done
    ldr r1, [r1, #0x18]
    tst r1, #KILL
    bne ni_library_done
    ldr r1, =NATIVE_SCOPE
    ldr r1, [r1]
    cmn r1, #1
    bne ni_library_done
    ldr r1, =ST + PATH
    mov r2, #0
ni_copy:
    ldrb r3, [r0, r2]
    strb r3, [r1, r2]
    cmp r3, #0
    beq ni_library_done
    add r2, r2, #1
    cmp r2, #127
    blo ni_copy
    mov r3, #0
    strb r3, [r1]
ni_library_done:
    pop {r0-r3, lr}
    b @LIBRARY_PROBE@
.pool

native_wav_import:
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    beq ni_refuse
    ldr r12, [r12, #0x18]
    tst r12, #KILL
    bne NI_NATIVE
    push {r4-r8, r11, r12, lr}
    mov r4, r0
    mov r5, r1
    cmp r5, #500
    blo ni_factory
    ldr r0, =NI_TASK
    ldr r0, [r0]
    ldr r1, =NI_COMMAND_TASK
    cmp r0, r1
    bne ni_error
    ldr r0, =LAST_USER
    cmp r5, r0
    bhi ni_error
    cmp r4, #0
    beq ni_error
    mov r0, #0
ni_path:
    ldrb r1, [r4, r0]
    cmp r1, #0
    beq ni_path_end
    add r0, r0, #1
    cmp r0, #127
    blo ni_path
    b ni_error
ni_path_end:
    cmp r0, #0
    beq ni_error
    ldr r0, =PREVIEW
    ldr r0, [r0]
    sub r0, r0, #0x01000000
    cmp r0, #0x03000000
    blo ni_error
    mov r0, #1
    bl sample_admit
    cmp r0, #0
    bne ni_error
    ldr r0, =NI_TRANSPORT
    ldr r0, [r0]
    cmp r0, #0
    beq ni_busy
    ldr r0, [r0, #0x308]
    cmp r0, #0
    bne ni_busy
    mov r0, r5
    bl resident
    cmp r0, #0
    bne ni_busy
    ldr r11, =ST
    ldr r0, [r11, #MODE]
    cmn r0, #1
    bne ni_begin
    ldrb r0, [r11, #PATH]
    cmp r0, #0
    cmpne r0, #255
    beq ni_busy
    bl native_scope_init
    bl swap_reset
    cmp r0, #0
    bne ni_busy
ni_begin:
    bl catalogue_begin_import
    cmp r0, #0
    bne ni_busy
    mov r6, r1
    mov r7, r3
    mov r8, #0
    cmp r2, #0
    beq ni_checked
    mov r0, r5
    bl indexed
    cmp r0, #0
    movne r8, #4
ni_checked:
    mov r0, r6
    mov r1, r8
    mov r3, r7
    bl catalogue_end_update
    cmp r0, #0
    bne ni_left
; Korg's import puts the sample into the DSP alone, above the swap's cursor; preview_frame opens SAMPLE EDIT on it.
    mov r0, r4
    mov r1, r5
    bl NI_NATIVE
    cmp r0, #0
    ldreq r1, =PREVIEW
    orreq r2, r5, #0x01000000
    streq r2, [r1]
    beq ni_left
; No room in the DSP: the card library takes the sample and the swap loads it on selection.
    bl catalogue_begin_import
    cmp r0, #0
    bne ni_left
    mov r6, r1
    mov r7, r3
    mov r0, r4
    mov r1, r5
    ldr r2, =ST + PATH
    bl store_import_new
    mov r1, r0
    mov r0, r6
    mov r2, r5
    mov r3, r7
    bl catalogue_end_import
ni_left:
    bl sample_leave
    pop {r4-r8, r11, r12, pc}
; A factory slot is not in the card library: Korg's import puts it into the DSP above the swap's cursor.
ni_factory:
    mov r0, r4
    mov r1, r5
    pop {r4-r8, r11, r12, lr}
    b NI_NATIVE
ni_busy:
    bl sample_leave
ni_error:
    pop {r4-r8, r11, r12, lr}
ni_refuse:
    mov r0, #4
    bx lr
.pool

capture_start_admitted:
    push {r0-r2, lr}
    mov r0, #2
    bl sample_admit
    cmp r0, #0
    pop {r0-r2, lr}
    movne r0, #0
    bxne lr
    push {r4, lr}
    bl capture_start_resume
    bl sample_leave
    pop {r4, pc}
capture_start_resume:
    push {r3-r7, lr}
    b 0xC0082F20
.pool
"""


PREVIEW_SOURCE = r"""
; ------------------------------------------------------------- UI task: the preview of an imported sample
; PREVIEW: bits 0-9 the slot, 10-19 SAMPLE EDIT's slot before it, bit 20 set while that is held, bits 24-31 the phase:
; 1 imported, 2 SAMPLE EDIT open on it, 3 left, the command task discards it. Any other phase is no preview.
; Runs before ss_frame at the frame hook (r4 the frame's object), keeps r0 to r3 and r12 for it.
.equ PV_ENTRY, 37
.equ PV_EDIT, 38
.equ PV_BROWSER, 39
.equ PV_MENU, 45
.equ PV_SWITCH, 0xC0083D28
.equ PV_MODEL, 0xC0035AD8
preview_frame:
    push {r0-r7, r12, lr}
    ldr r4, =PREVIEW
    ldr r5, [r4]
    mov r6, r5, lsr #24
    sub r6, r6, #1
    cmp r6, #1
    bhi pf_out
    ldr r1, =SCREENS
    ldr r1, [r1]
    cmp r1, #0
    beq pf_out
    ldr r2, [r1, #0x24]
    cmp r2, #0
    bne pf_out
    ldr r7, [r1, #0x2c]
    cmp r7, #PV_EDIT
    beq pf_editing
    cmp r6, #0
    bne pf_open
    cmp r7, #PV_BROWSER
    bne pf_end
; SAMPLE EDIT plays its slot on all 16 parts and lights the pads (command 0x20 from screen 38's constructor).
    bl PV_MODEL
    tst r5, #0x100000
    ldreq r1, [r0, #0x3FC]
    ldreq r2, =0x3FF
    andeq r1, r1, r2
    orreq r5, r5, r1, lsl #10
    orreq r5, r5, #0x100000
    streq r5, [r4]
    mov r1, r5, lsl #22
    mov r1, r1, lsr #22
    str r1, [r0, #0x3FC]
    mov r0, #PV_EDIT
    mov r1, #0
    bl PV_SWITCH
    b pf_out
pf_editing:
    bic r5, r5, #0xFF000000
    orr r5, r5, #0x02000000
    str r5, [r4]
    b pf_out
pf_open:
    cmp r7, #PV_MENU
    beq pf_out
pf_end:
    tst r5, #0x100000
    beq pf_discard
    bl PV_MODEL
    mov r1, r5, lsl #12
    mov r1, r1, lsr #22
    str r1, [r0, #0x3FC]
    bic r5, r5, #0x100000
pf_discard:
    bic r5, r5, #0xFF000000
    orr r5, r5, #0x03000000
    str r5, [r4]
    mov r0, #MSG
    mov r1, #0
    mov r2, #0
    bl POST
    cmp r7, #PV_ENTRY
    moveq r0, #PV_BROWSER
    moveq r1, #0
    bleq PV_SWITCH
pf_out:
    pop {r0-r7, r12, lr}
    b ss_frame

; ------------------------------------------------------------- command task: the preview's end
; In order after SAMPLE EDIT's own EXIT (0x21 gives the parts back) and a WRITE: a slot WRITE put into the card library stays.
ss_msg:
    ldr r12, =PREVIEW
    ldr r12, [r12]
    mov r12, r12, lsr #24
    cmp r12, #3
    bne ss_step
    push {r0-r4, lr}
    bl preview_discard
    pop {r0-r4, lr}
    b ss_step

preview_discard:
    push {r4-r10, r11, r12, lr}
    ldr r4, =PREVIEW
    ldr r4, [r4]
    mov r4, r4, lsl #22
    mov r4, r4, lsr #22
    mov r0, r4
    bl persist_enter
    ldr r1, =PREVIEW
    cmp r0, #0
    ldrne r0, [r1]
    bicne r0, r0, #0xFF000000
    orrne r0, r0, #0x02000000
    strne r0, [r1]
    popne {r4-r10, r11, r12, pc}
    mvn r0, #0
    str r0, [r1]
    mov r5, #0
    mov r0, r4
    bl indexed
    cmp r0, #0
    beq persist_delete_row
    bl sample_leave
    pop {r4-r10, r11, r12, pc}
.pool
"""
