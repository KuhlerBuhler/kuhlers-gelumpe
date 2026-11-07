; CommandTask hook, experimental. Requires the core in the same assembly.
; Retains native call results, caller registers and flags. No IRQ/UI DSP calls.
.equ FW_COMMAND, 0xC002D844
.equ FW_ALLOC, 0xC0028DCC
scope_command_hook:
    push {r4, lr}
    bl FW_COMMAND
    pop {r4, lr}
    push {r0-r12, lr}
    .word 0xE10FC000 ; mrs r12,cpsr
    push {r12, lr}
    bl scope_adapter_service
    pop {r12, lr}
    .word 0xE128F00C ; msr cpsr_f,r12 (do not change interrupt masks or mode)
    pop {r0-r12, lr}
    bx lr
.pool

scope_adapter_service:
    push {r4-r8, lr}
    ldr r4, =scope_control
    ldr r0, [r4, #36]
    cmp r0, #1
    bne adapter_lease_ok
    ldr r0, =OS_TICKS
    ldr r0, [r0]
    ldr r1, [r4, #32]
    sub r0, r0, r1
    cmp r0, #200
    blo adapter_lease_ok
    mov r0, #0
    str r0, [r4]
    str r0, [r4, #36]
adapter_lease_ok:
    ldr r5, [r4, #24]
    cmn r5, #1
    bne adapter_pointer
    ldr r0, [r4]
    cmp r0, #0
    bne adapter_return
    str r0, [r4, #24]
    str r0, [r4, #28]
    b adapter_return
adapter_pointer:
    cmp r5, #0
    bne adapter_requests
    ldr r0, [r4]
    cmp r0, #1
    bne adapter_return
    ldr r0, =CTX_SIZE
    bl FW_ALLOC
    cmp r0, #0
    beq adapter_oom
    mov r5, r0
    mov r1, #0
    ldr r2, =CTX_SIZE / 4
adapter_zero:
    str r1, [r0], #4
    subs r2, r2, #1
    bne adapter_zero
    str r5, [r4, #24]
adapter_requests:
    ldr r0, [r4]
    str r0, [r5, #36]
    ldr r0, [r4, #4]
    str r0, [r5, #40]
    ldr r0, [r4, #8]
    str r0, [r5, #44]
    ldr r0, [r4, #12]
    str r0, [r5, #48]
    ldr r0, [r4, #16]
    str r0, [r5, #52]
    ldr r0, [r4, #20]
    str r0, [r5, #60]
    ldr r0, [r4, #40]
    str r0, [r5, #108]
    mov r0, r5
    bl scope_service
    str r0, [r4, #28]
adapter_return:
    pop {r4-r8, pc}
adapter_oom:
    mvn r0, #0
    str r0, [r4, #24]
    mov r0, #7
    str r0, [r4, #28]
    b adapter_return
.pool

; UI helper: copy(destinationBitmap1024). Only reads a published bitmap.
scope_adapter_copy:
    mov r1, r0
    ldr r2, =scope_control
    ldr r0, [r2, #24]
    cmp r0, #0
    beq adapter_copy_off
    cmn r0, #1
    beq adapter_copy_off
    b scope_copy
adapter_copy_off:
    mov r0, #OFF
    bx lr
.pool
.align 4
scope_control:
    .word 0, 0, 0, 0, 11, 0, 0, 0
; enable, part, stereo, channel, verticalShift, freeze, ownedHeapPointer, lastStatus
    .word 0, 0
; last UI lease tick, UI lease armed. A missing UI frame closes capture after 200 ms.
    .word 0
; frequency view: 0 full range, 1 bass range.
