; The native sender takes three u16 arguments and owns no DSP lock.
RR_FW_BEGIN:
    mov r0, #1
    b rec_reader_blue_command
RR_FW_END:
    mov r0, #0
rec_reader_blue_command:
    push {r4, lr}
    mov r4, r0
    mov r0, #1
    ldr r12, =RR_FW_LOCK
    blx r12
    mov r0, #0x37
    mov r1, r4
    mov r2, #0
    ldr r12, =RR_FW_SEND
    blx r12
    mov r0, #1
    ldr r12, =RR_FW_UNLOCK
    blx r12
    pop {r4, pc}
.pool
