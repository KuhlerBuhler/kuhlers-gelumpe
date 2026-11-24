.equ AUDIO_COMMAND_AT, 0xC002A628
.equ AUDIO_COMMAND_FN, 0xC002D844
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
    bl nr_service
    pop {r12, lr}
    .word 0xE128F00C                 ; msr cpsr_f, r12
    pop {r0-r12, lr}
    bx lr
.pool

nr_command_end:
