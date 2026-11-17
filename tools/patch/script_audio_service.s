; korg.audio.capture, korg.audio.spectrum and korg.audio.wave (API 31) on the Sampler builds. The capture, ring reader and FFT
; (tools/patch/spectrum/) come from Spettro by Luigi (GitHub reflectiveboi, PR #429). They run in CommandTask behind its call at
; AUDIO_COMMAND_AT, never in the frame hook; the calls only post a request and copy what the worker published
; (docs/messungen/2026-11-12-plugin-api31-spektrum.md).
.equ AUDIO_COMMAND_AT, 0xC002A628    ; CommandTask's call of AUDIO_COMMAND_FN, replaced by a branch to audio_command_hook
.equ AUDIO_COMMAND_FN, 0xC002D844
.equ AU_REQUEST, 4                   ; from AUDIO_SERVICE: the source asked for, 1 to 24, anything else off (FF at power-on)
.equ AU_LEASE_TICK, 8                ; the tick of the last call; a request older than AU_LEASE is dropped
.equ AU_STATUS, 12                   ; the worker's last status (capture.s), FF before its first run
.equ AU_LEASE, 2048                 ; ticks of 1 ms (docs/messungen/2026-10-29-plugin-timer.md)
.equ AU_OOM, 7
.equ AU_WAVE, 256
.align 4

; The replaced bl: the native call first, then the service with all registers and the condition flags kept.
audio_command_hook:
    ldr lr, =AUDIO_COMMAND_AT+4
    push {r4, lr}
    bl AUDIO_COMMAND_FN
    pop {r4, lr}
    push {r0-r12, lr}
    .word 0xE10FC000                 ; mrs r12, cpsr
    push {r12, lr}
    bl audio_service
    pop {r12, lr}
    .word 0xE128F00C                 ; msr cpsr_f, r12
    pop {r0-r12, lr}
    bx lr
.pool

; One step of the service: the context is taken from the heap on the first request and kept until power-off.
audio_service:
    push {r4-r8, lr}
    ldr r4, =AUDIO_SERVICE
    ldr r5, [r4, #AU_REQUEST]
    sub r6, r5, #1
    cmp r6, #24
    bhs audio_service_off
    ldr r0, =OS_TICKS
    ldr r0, [r0]
    ldr r1, [r4, #AU_LEASE_TICK]
    sub r0, r0, r1
    cmp r0, #AU_LEASE
    bhs audio_service_expired
    ldr r7, [r4]
    cmn r7, #1
    bne audio_service_have
    ldr r0, =CTX_SIZE
    bl MG_ALLOC
    str r0, [r4]
    cmp r0, #0
    beq audio_service_have
    mov r7, r0
    mov r1, #0
    ldr r2, =CTX_SIZE / 4
audio_service_zero:
    str r1, [r0], #4
    subs r2, r2, #1
    bne audio_service_zero
audio_service_have:
    cmp r7, #0
    moveq r0, #AU_OOM
    beq audio_service_status
    ; 1 to 16 a part (mono, the left word), 17 to 24 a part pair (both words, powers added)
    mov r0, #1
    str r0, [r7, #36]
    cmp r6, #16
    movlo r1, r6
    movlo r2, #0
    movlo r3, #0
    subhs r1, r6, #16
    movhs r1, r1, lsl #1
    movhs r2, #1
    movhs r3, #2
    str r1, [r7, #40]
    str r2, [r7, #44]
    str r3, [r7, #48]
    mov r0, #11
    str r0, [r7, #52]
    mov r0, #0
    str r0, [r7, #60]
    str r0, [r7, #108]
    mov r0, r7
    bl scope_service
    b audio_service_status
audio_service_expired:
    mvn r0, #0
    str r0, [r4, #AU_REQUEST]
audio_service_off:
    ldr r7, [r4]
    cmn r7, #1
    beq audio_service_idle
    cmp r7, #0
    beq audio_service_idle
    ldr r0, [r7, #4]
    cmp r0, #0
    beq audio_service_idle
    mov r0, #0                       ; not 1: the worker closes the capture
    str r0, [r7, #36]
    mov r0, r7
    bl scope_service
audio_service_idle:
    mov r0, #OFF
audio_service_status:
    str r0, [r4, #AU_STATUS]
    pop {r4-r8, pc}
.pool

; audio_columns(powers[2049], out[128] bytes, column table): per column the power (peak of its bins, or interpolated), as
; dB above -96 dB of a full-scale sine, 0 to 96. Log2 in Q8 as Spettro's display: 7680 is 2^30, a full-scale sine.
audio_columns:
    push {r4-r10, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r7, #0
audio_column:
    ldmia r6!, {r0, r1}
    tst r1, #0x80000000
    bne audio_column_mix
    mov r10, #0
audio_column_peak:
    ldr r2, [r4, r0, lsl #2]
    cmp r2, r10
    movhi r10, r2
    add r0, r0, #1
    cmp r0, r1
    blo audio_column_peak
    b audio_column_level
audio_column_mix:
    and r1, r1, #255
    ldr r2, [r4, r0, lsl #2]
    add r0, r0, #1
    ldr r3, [r4, r0, lsl #2]
    rsb r0, r1, #256
    .word 0xE089A092                 ; umull r10, r9, r2, r0
    .word 0xE0A9A193                 ; umlal r10, r9, r3, r1
    mov r10, r10, lsr #8
    orr r10, r10, r9, lsl #24
audio_column_level:
    cmp r10, #0
    moveq r9, #0
    beq audio_column_store
    mov r0, r10
    mvn r1, #0
audio_column_exponent:
    add r1, r1, #1
    movs r0, r0, lsr #1
    bne audio_column_exponent
    subs r0, r1, #4
    movge r2, r10, lsr r0
    rsblt r0, r0, #0
    movlt r2, r10, lsl r0
    sub r2, r2, #16
    ldr r0, =spectrum_log_fraction
    ldr r0, [r0, r2, lsl #2]
    add r0, r0, r1, lsl #8
    sub r0, r0, #7680
    ldr r1, =771                     ; 10 log10(2) / 256 in 1/65536
    mul r2, r0, r1
    mov r2, r2, asr #16
    adds r9, r2, #96
    movmi r9, #0
    cmp r9, #96
    movgt r9, #96
audio_column_store:
    strb r9, [r5, r7]
    add r7, r7, #1
    cmp r7, #128
    blo audio_column
    pop {r4-r10, pc}
.pool

; audio_wave(window of 4096 packed frames, out[256] bytes, channel 0 left or 2 both): the newest 256 frames, top 8 bits.
audio_wave:
    push {r4, lr}
    add r0, r0, #(4096 - AU_WAVE) * 4
    mov r4, #AU_WAVE
audio_wave_frame:
    ldr r3, [r0], #4
    mov r12, r3, lsl #16
    mov r12, r12, asr #16
    cmp r2, #2
    bne audio_wave_store
    mov r3, r3, asr #16
    add r12, r12, r3
    mov r12, r12, asr #1
audio_wave_store:
    mov r12, r12, asr #8
    strb r12, [r1], #1
    subs r4, r4, #1
    bne audio_wave_frame
    pop {r4, pc}
.pool

; r2 = AUDIO_SERVICE: renews the lease of a running request.
audio_lease:
    ldr r2, =AUDIO_SERVICE
    ldr r3, [r2, #AU_REQUEST]
    sub r3, r3, #1
    cmp r3, #24
    bxhs lr
    ldr r3, =OS_TICKS
    ldr r3, [r3]
    str r3, [r2, #AU_LEASE_TICK]
    bx lr

; r2 = AUDIO_SERVICE -> r0 the status of the API, r1 ERR_OK
audio_status:
    ldr r0, [r2, #AU_STATUS]
    cmp r0, #8
    movhs r0, #OFF
    ldr r1, =audio_status_api
    ldrb r0, [r1, r0]
    mov r1, #ERR_OK
    bx lr
audio_status_api:
    ; ok, off, busy, wait, gap (lost), gap (stale), off (bad argument), no memory
    .byte 0, 1, 2, 3, 4, 4, 1, 5
.align 4

; korg.audio.capture(source 1 to 16 part, 17 to 24 part pair, -1 or 0 off) -> status
script_audio_capture_glue:
    ldr r2, =AUDIO_SERVICE
    sub r1, r0, #1
    cmp r1, #24
    bhs audio_capture_off
    ldr r1, [r2, #AU_REQUEST]
    cmp r1, r0
    strne r0, [r2, #AU_REQUEST]
    movne r1, #FILLING
    strne r1, [r2, #AU_STATUS]
    ldr r3, =OS_TICKS
    ldr r3, [r3]
    str r3, [r2, #AU_LEASE_TICK]
    b audio_status
audio_capture_off:
    mvn r1, #0
    str r1, [r2, #AU_REQUEST]
    mov r0, #1
    mov r1, #ERR_OK
    bx lr

; r0 -> r3 the published frame of the worker, or 0; keeps r0 to r2
audio_frame:
    ldr r3, =AUDIO_SERVICE
    ldr r12, [r3, #AU_STATUS]
    cmp r12, #OK
    bne audio_frame_none
    ldr r12, [r3]
    cmn r12, #1
    beq audio_frame_none
    cmp r12, #0
    beq audio_frame_none
    ldr r3, [r12, #56]
    sub r3, r3, r12
    cmp r3, #FRAME_A
    cmpne r3, #FRAME_B
    addeq r3, r3, r12
    bxeq lr
audio_frame_none:
    mov r3, #0
    bx lr
.pool

; korg.audio.spectrum(array, bins 1 to 128, range 0 full 20 Hz to 20 kHz, 1 bass to 2 kHz) -> status; with 0 (ok) the first
; bins slots get dB 0 to 96 per band, the loudest of the 128 columns in it
script_audio_spectrum_glue:
    push {r4-r8, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    bl audio_lease
    bl audio_frame
    cmp r3, #0
    beq audio_glue_status
    add r3, r3, r6, lsl #7
    mov r7, r4, lsr #16
    cmp r5, r7
    movhi r5, r7
    cmp r5, #0
    beq audio_glue_status
    ldr r2, =HOOK_RUNTIME
    ldr r2, [r2, #RT_ENTRY]
    ldr r2, [r2, #SCRIPT_ENTRY_VARS]
    mov r4, r4, lsl #16
    add r4, r2, r4, lsr #14
    mov r0, #0
    mov r1, #0
audio_spectrum_clear:
    str r1, [r4, r0, lsl #2]
    add r0, r0, #1
    cmp r0, r5
    blo audio_spectrum_clear
    mov r0, #0
audio_spectrum_column:
    mul r1, r0, r5
    mov r1, r1, lsr #7
    ldrb r2, [r3, r0]
    ldr r12, [r4, r1, lsl #2]
    cmp r2, r12
    strgt r2, [r4, r1, lsl #2]
    add r0, r0, #1
    cmp r0, #128
    blo audio_spectrum_column
audio_glue_status:
    ldr r2, =AUDIO_SERVICE
    pop {r4-r8, lr}
    b audio_status

; korg.audio.wave(array) -> status; with 0 (ok) the slots get the newest frames, -128 to 127, at most 256, the last slot newest
script_audio_wave_glue:
    push {r4-r8, lr}
    mov r4, r0
    bl audio_lease
    bl audio_frame
    cmp r3, #0
    beq audio_glue_status
    add r3, r3, #AU_WAVE
    mov r5, r4, lsr #16
    cmp r5, #AU_WAVE
    movhi r5, #AU_WAVE
    ldr r2, =HOOK_RUNTIME
    ldr r2, [r2, #RT_ENTRY]
    ldr r2, [r2, #SCRIPT_ENTRY_VARS]
    mov r4, r4, lsl #16
    add r4, r2, r4, lsr #14
    rsb r0, r5, #AU_WAVE
    add r3, r3, r0
    mov r0, #0
audio_wave_copy:
    cmp r0, r5
    bhs audio_glue_status
    ldrb r1, [r3, r0]
    mov r1, r1, lsl #24
    mov r1, r1, asr #24
    str r1, [r4, r0, lsl #2]
    add r0, r0, #1
    b audio_wave_copy
.pool
