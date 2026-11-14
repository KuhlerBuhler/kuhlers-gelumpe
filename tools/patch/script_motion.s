; korg.motion (API 28): the 24 motion lanes of the pattern being edited and the firmware's motion engine.
; A lane in the pattern object: its part at +0x104 + lane (0 none, 1 to 16 a part, 17 the master effect), its destination at
; +0x11C + lane, its 64 values at +0x134 + 0x40 * lane + step (0 empty, else the value 0 to 127 plus 1; the firmware records
; a knob's 0 to 255 halved).
; Clearing goes through the firmware's own functions, the ones Part Util CLEAR MOTION and CLEAR MFX MOTION call, so the engine
; and the lanes-in-use counter follow (docs/messungen/2026-11-11-plugin-api28-motion.md).
.equ MOTION_LANES, 24
.equ MOTION_STEPS, 64
.equ MOTION_PART_AT, 0x104
.equ MOTION_DEST_AT, 0x11C
.equ MOTION_VALUES_AT, 0x134
.equ MOTION_ENGINE, 0xC068DB0C     ; the engine's lane table, 0x24 a lane: +0 in use, +4 part, +5 destination, +0x10 output
.equ MOTION_ENGINE_STRIDE, 0x24
.equ MOTION_CLEAR_LANE, 0xC0058BD4 ; (lane): resets the engine's lane and empties the lane in the pattern; nothing when unused
.equ MOTION_CLEAR_OF, 0xC0058CA8   ; (owner 1 to 17): clear_lane for every lane in use with that owner
.equ MOTION_OWNER_MFX, 17
.align 4

; korg.motion.lane(lane) -> its part byte: 0 none, 1 to 16 part 1 to 16, 17 the master effect
script_motion_lane_glue:
    mov r1, #MOTION_PART_AT
    b motion_byte
; korg.motion.destination(lane) -> the destination byte the firmware recorded
script_motion_destination_glue:
    mov r1, #MOTION_DEST_AT
motion_byte:
    cmp r0, #MOTION_LANES
    bhs hw_bad_arg
    ldr r2, =HW_PATTERN_OBJECT
    add r2, r2, r1
    ldrb r0, [r2, r0]
    mov r1, #ERR_OK
    bx lr

; r0 lane, r1 step -> r12 the value's address (r0 to r1 checked by the caller)
motion_value_address:
    ldr r12, =HW_PATTERN_OBJECT+MOTION_VALUES_AT
    add r12, r12, r0, lsl #6
    add r12, r12, r1
    bx lr

; korg.motion.value(lane, step) -> -1 empty, else 0 to 127
script_motion_value_glue:
    cmp r0, #MOTION_LANES
    cmplo r1, #MOTION_STEPS
    bhs hw_bad_arg
    push {lr}
    bl motion_value_address
    ldrb r0, [r12]
    cmp r0, #0
    mvneq r0, #0
    subne r0, r0, #1
    mov r1, #ERR_OK
    pop {pc}

; korg.motion.setValue(lane, step, value): -1 empties the step, 0 to 127 records it; only on a lane that has a part
script_motion_set_value_glue:
    cmp r0, #MOTION_LANES
    cmplo r1, #MOTION_STEPS
    bhs hw_bad_arg
    push {lr}
    ldr r3, =HW_PATTERN_OBJECT+MOTION_PART_AT
    ldrb r3, [r3, r0]
    cmp r3, #0
    beq motion_done
    bl motion_value_address
    add r2, r2, #1                  ; -1 (empty) is 0; the VM has checked -1 to 127
    strb r2, [r12]
motion_done:
    mov r0, #0
    mov r1, #ERR_OK
    pop {pc}

; korg.motion.output(lane) -> what the engine sends now for the lane: -1 silent (not playing, or no motion there)
script_motion_output_glue:
    cmp r0, #MOTION_LANES
    bhs hw_bad_arg
    mov r1, #MOTION_ENGINE_STRIDE
    mul r2, r0, r1
    ldr r1, =MOTION_ENGINE+0x10
    ldr r0, [r1, r2]
    mov r1, #ERR_OK
    bx lr

; korg.motion.clearLane(lane)
script_motion_clear_lane_glue:
    cmp r0, #MOTION_LANES
    bhs hw_bad_arg
    ldr r12, =MOTION_CLEAR_LANE
    b motion_call
; korg.motion.clearPart(part 0 to 15): every lane of the part, as Part Util CLEAR MOTION
script_motion_clear_part_glue:
    cmp r0, #16
    bhs hw_bad_arg
    add r0, r0, #1
    ldr r12, =MOTION_CLEAR_OF
    b motion_call
; korg.motion.clearMfx(): every lane of the master effect, as CLEAR MFX MOTION
script_motion_clear_mfx_glue:
    mov r0, #MOTION_OWNER_MFX
    ldr r12, =MOTION_CLEAR_OF
; r0 the argument, r12 the firmware function: called on an 8 byte aligned stack
motion_call:
    push {r4, lr}
    mov r4, sp
    bic sp, sp, #7
    blx r12
    mov sp, r4
    mov r0, #0
    mov r1, #ERR_OK
    pop {r4, pc}
.pool
