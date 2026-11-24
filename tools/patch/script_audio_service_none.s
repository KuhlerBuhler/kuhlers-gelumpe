; Plugin capture, spectrum and wave are unavailable on the synth; native recording owns its separate 0x37 adapter.
script_audio_capture_glue:
script_audio_spectrum_glue:
script_audio_wave_glue:
    mov r0, #6
    mov r1, #ERR_OK
    bx lr

audio_service:
    bx lr
audio_service_end:
