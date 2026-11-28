; korg.audio (API 31): the output level as the level meter of the bottom LEDs shows it. The firmware smooths the two levels
; every 40 ms (0xC0088220) and keeps the state at METER_SMOOTH, 128 times the level 0 to 254; led_meter_hook keeps it going
; while the meter is off or a plugin holds the LEDs (docs/messungen/2026-11-11-plugin-api31-audio-level.md).
.equ METER_SMOOTH, 0xC06913A8
.align 4

; korg.audio.level(channel 0 or 1) -> 0 to 254
script_audio_level_glue:
    cmp r0, #2
    bhs hw_bad_arg
    ldr r1, =METER_SMOOTH
    ldr r0, [r1, r0, lsl #2]
    movs r0, r0, asr #7
    movmi r0, #0
    cmp r0, #254
    movgt r0, #254
    mov r1, #ERR_OK
    bx lr
.pool
