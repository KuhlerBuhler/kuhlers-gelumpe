; The blue Electribe has no native capture start (docs/messungen/2026-11-07-spettro.md): korg.audio.capture, spectrum and wave
; return 6 (not on this Electribe) and leave the array as it is.
script_audio_capture_glue:
script_audio_spectrum_glue:
script_audio_wave_glue:
    mov r0, #6
    mov r1, #ERR_OK
    bx lr
