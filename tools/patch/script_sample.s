; korg.read.sampleName and korg.read.sampleInfo (API 33): the sampler's tables of one sample (data/map/sample.mjs), slot = table
; index = the number on the display minus 1, as the part's sample field holds it. The start is kept as audio offset plus start in
; the playback table; minus the metadata's audio offset it is the start of the sample file
; (docs/messungen/2026-11-11-plugin-api33-samples.md).
.equ SAMPLE_NAMES, 0xC047B08C   ; +12 of the name table, 0x20 each
.equ SAMPLE_PLAY, 0xC0362EE8    ; 0x10 each: +0 start, +4 loop, +8 end, +14 one shot
.equ SAMPLE_META, 0xC036AD88    ; 0x45C each: +0 audio offset, +4 PCM bytes, +9 stereo, +16 rate, +21 tune (s8)
.align 4

; r0 array handle (checked by the VM), r1 slot -> r0 the characters of the name, one to a slot, up to the first zero, 16 or the end
; of the array.
script_read_sample_name_glue:
    ldr r2, =SAMPLE_INFO_SLOTS
    cmp r1, r2
    bhs hw_bad_arg
    push {r4, r5, lr}
    mov r4, r0, lsr #16
    cmp r4, #16
    movhi r4, #16
    mov r5, r0, lsl #16
    ldr r2, =HOOK_RUNTIME
    ldr r2, [r2, #RT_ENTRY]
    ldr r2, [r2, #SCRIPT_ENTRY_VARS]
    add r5, r2, r5, lsr #14
    ldr r2, =SAMPLE_NAMES
    add r2, r2, r1, lsl #5
    mov r0, #0
sample_name_copy:
    cmp r0, r4
    bhs sample_name_done
    ldrb r3, [r2, r0]
    cmp r3, #0
    beq sample_name_done
    str r3, [r5, r0, lsl #2]
    add r0, r0, #1
    b sample_name_copy
sample_name_done:
    mov r1, #ERR_OK
    pop {r4, r5, pc}

; r0 slot, r1 field (SAMPLE_INFO.fields: 0 start, 1 end, 2 loop, 3 tune, 4 stereo, 5 length, 6 oneShot, 7 rate) -> r0 the value
script_read_sample_info_glue:
    ldr r2, =SAMPLE_INFO_SLOTS
    cmp r0, r2
    bhs hw_bad_arg
    cmp r1, #8
    bhs hw_bad_arg
    ldr r2, =SAMPLE_PLAY
    add r2, r2, r0, lsl #4
    ldr r3, =0x45C
    mul r12, r0, r3
    ldr r3, =SAMPLE_META
    add r3, r3, r12
    cmp r1, #1
    ldrlo r0, [r2]
    ldrlo r12, [r3]
    sublo r0, r0, r12
    ldreq r0, [r2, #8]
    blo sample_info_done
    beq sample_info_done
    cmp r1, #3
    ldrlo r0, [r2, #4]
    blo sample_info_done
    bne sample_info_flags
    ldrb r0, [r3, #21]
    mov r0, r0, lsl #24
    mov r0, r0, asr #24
    b sample_info_done
sample_info_flags:
    cmp r1, #5
    ldrblo r0, [r3, #9]
    ldreq r0, [r3, #4]
    bls sample_info_done
    cmp r1, #6
    ldrbeq r0, [r2, #14]
    ldrne r0, [r3, #16]
sample_info_done:
    mov r1, #ERR_OK
    bx lr
.pool
