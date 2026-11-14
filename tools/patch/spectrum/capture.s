; From Spettro by Luigi (GitHub reflectiveboi, PR #429), taken into the BLECH runtime as the service behind korg.audio (API 31).
; Experimental Hacktribe Sampler 2.02 scope core. No hooks, flash writes or DSP program changes.
; Caller owns CTX_SIZE bytes of zeroed ARM RAM. Calls must run in CommandTask, never an IRQ/UI frame.
; ctx: magic, owned, source, startedTick, readTick, cursor, valid, status, followed by DSP state and PCM.
.equ MAGIC, 0x53434F50
.equ DSP_STATE, 0xFF9031D0
.equ DSP_BYTES, 19200
.equ DSP_BASE, 0x01C722A0
.equ DSP_END, 0x01C76DA0
.equ PCM_BYTES, 4096
.equ WINDOW_BACK, 5120
.equ OVERWRITE_LIMIT, 14080
.equ INFO, 64
.equ PCM, 128
.equ FRAME_A, PCM + PCM_BYTES
.equ FRAME_B, FRAME_A + 1024
.equ HISTORY, FRAME_B + 1024
.equ CTX_SIZE, 103424
.equ FW_READ, 0xC00141F8
.equ FW_BEGIN, 0xC0014368
.equ FW_END, 0xC00143E4
.equ OK, 0
.equ OFF, 1
.equ BUSY, 2
.equ FILLING, 3
.equ LOST, 4
.equ STALE, 5
.equ BAD_ARG, 6

scope_begin:
    push {r4-r8, lr}
    mov r4, r0
    cmp r1, #15
    bhi begin_bad
    cmp r2, #1
    bhi begin_bad
    mov r5, r1
    mov r6, r2
    ldr r0, [r4]
    ldr r1, =MAGIC
    cmp r0, r1
    bne begin_new
    ldr r0, [r4, #4]
    cmp r0, #0
    bne begin_busy
begin_new:
    str r1, [r4]
    mov r0, #0
    str r0, [r4, #4]
    str r0, [r4, #24]
    bl read_info
    ldr r0, [r4, #INFO]
    cmp r0, #0
    bne begin_busy
    ldr r0, [r4, #INFO+40]
    cmp r0, #0
    bne begin_busy
    cmp r6, #0
    bne begin_stereo
    add r7, r5, #1
    ldr r6, =0x118
    mul r8, r5, r6
    ldr r6, =0xFF90197C
    add r8, r8, r6
    b begin_call
begin_stereo:
    mov r5, r5, lsr #1
    add r7, r5, #17
    ldr r6, =0x230
    mul r8, r5, r6
    ldr r6, =0xFF901A98
    add r8, r8, r6
begin_call:
    mov r0, r7
    bl FW_BEGIN
    str r8, [r4, #8]
    ldr r0, =OS_TICKS
    ldr r0, [r0]
    str r0, [r4, #12]
    mov r0, #1
    str r0, [r4, #4]
    mov r0, #FILLING
    b status_return
begin_bad:
    mov r0, #BAD_ARG
    pop {r4-r8, pc}
begin_busy:
    mov r0, #BUSY
status_return:
    str r0, [r4, #28]
    pop {r4-r8, pc}
.pool

; read_info/owns_info: r4 ctx, preserve r4..r11. Only task-context firmware calls.
read_info:
    push {r3, lr}
    ldr r0, =DSP_STATE
    add r1, r4, #INFO
    mov r2, #22
    mov r3, #2
    bl FW_READ
    pop {r3, pc}
owns_info:
    ldr r0, [r4, #INFO]
    cmp r0, #1
    bne info_no
    ldr r0, [r4, #INFO+4]
    ldr r1, =DSP_BYTES
    cmp r0, r1
    bne info_no
    ldr r0, [r4, #INFO+12]
    ldr r1, [r4, #8]
    cmp r0, r1
    bne info_no
    ldr r0, [r4, #INFO+40]
    cmp r0, #0
    bne info_no
    ldr r0, [r4, #INFO+8]
    ldr r1, =DSP_BASE
    cmp r0, r1
    blo info_no
    ldr r1, =DSP_END
    cmp r0, r1
    bhs info_no
    tst r0, #3
    bne info_no
    mov r0, #1
    bx lr
info_no:
    mov r0, #0
    bx lr
.pool

; close(ctx): disable only while this instance still owns the same idle recording path.
scope_close:
    push {r4-r8, lr}
    mov r4, r0
    ldr r0, [r4]
    ldr r1, =MAGIC
    cmp r0, r1
    bne close_off
    ldr r0, [r4, #4]
    cmp r0, #1
    bne close_off
    bl read_info
    bl owns_info
    cmp r0, #1
    bne close_lost
    bl FW_END
    mov r0, #OK
    b close_clear
close_lost:
    mov r0, #LOST
    b close_clear
close_off:
    mov r0, #OFF
close_clear:
    mov r1, #0
    str r1, [r4, #4]
    str r1, [r4, #24]
    b status_return
.pool
