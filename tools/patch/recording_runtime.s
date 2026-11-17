.equ NR_MAGIC, 0x3152434E
.equ NR_SIZE, 64
.equ NR_RING_BYTES, 2097152
.equ NR_DISABLED, 32
.equ NR_OOM, 33

; Public state contains no pointers that the input or frame task dereferences.
nr_init:
    .word 0xE10F3000                 ; mrs r3, cpsr
    orr r1, r3, #0xC0
    .word 0xE121F001                 ; msr cpsr_c, r1
    ldr r2, =NATIVE_RECORDING
    ldr r0, [r2]
    ldr r1, =NR_MAGIC
    cmp r0, r1
    beq nr_init_done
    mov r0, #0
    mov r1, #NR_SIZE-4
nr_init_zero:
    str r0, [r2, r1]
    subs r1, r1, #4
    bne nr_init_zero
    ldr r0, =NR_MAGIC
    str r0, [r2]
nr_init_done:
    mov r0, r2
    .word 0xE121F003                 ; msr cpsr_c, r3
    bx lr
.pool

nr_enabled:
    ldr r1, =MENU_STATE
    ldr r0, [r1, #M_ON]
    cmp r0, #1
    movne r0, #0
    bxne lr
    ldrb r0, [r1, #MX_FLAGS2]
    tst r0, #FLAGS2_NATIVE_RECORDING
    moveq r0, #0
    movne r0, #1
    bx lr

nr_busy:
    push {r4, lr}
    bl nr_init
    ldr r1, [r0, #NR_PHASE]
    ldr r2, [r0, #NR_REQUEST]
    cmp r2, #1
    orreq r1, r1, #1
    cmp r1, #0
    movne r0, #1
    moveq r0, #0
    pop {r4, pc}

; r0 = 1 start, 0 stop. Only memory operations run under the interrupt mask.
nr_post:
    push {r4-r6, lr}
    mov r4, r0
    cmp r4, #1
    movhi r0, #RW_BAD_ARG
    bhi nr_post_return
    bl nr_init
    mov r5, r0
    cmp r4, #0
    beq nr_post_lock
    bl nr_enabled
    cmp r0, #0
    moveq r0, #NR_DISABLED
    beq nr_post_return
nr_post_lock:
    .word 0xE10F6000                 ; mrs r6, cpsr
    orr r1, r6, #0xC0
    .word 0xE121F001                 ; msr cpsr_c, r1
    bl nr_busy
    cmp r4, #0
    beq nr_post_stop
    cmp r0, #0
    movne r0, #RW_BAD_STATE
    bne nr_post_unlock
    mov r0, #1
    str r0, [r5, #NR_REQUEST]
    mov r0, #0
    b nr_post_unlock
nr_post_stop:
    cmp r0, #0
    movne r0, #2
    strne r0, [r5, #NR_REQUEST]
    mov r0, #0
nr_post_unlock:
    .word 0xE121F006                 ; msr cpsr_c, r6
nr_post_return:
    pop {r4-r6, pc}
.pool

; r0 = the request claimed by CommandTask.
nr_take_request:
    .word 0xE10F2000                 ; mrs r2, cpsr
    orr r1, r2, #0xC0
    .word 0xE121F001                 ; msr cpsr_c, r1
    ldr r3, =NATIVE_RECORDING
    ldr r0, [r3, #NR_REQUEST]
    mov r1, #0
    str r1, [r3, #NR_REQUEST]
    .word 0xE121F002                 ; msr cpsr_c, r2
    bx lr

; CommandTask owns the allocation from the start claim through both close retries.
nr_service:
    push {r4-r8, lr}
    bl nr_init
    mov r4, r0
    bl nr_enabled
    cmp r0, #0
    bne nr_service_context
    mov r0, #0
    bl nr_post
    mov r0, #0
    str r0, [r4, #NR_SELECTED]
nr_service_context:
    ldr r5, [r4, #NR_CONTEXT]
    cmp r5, #0
    bne nr_service_command
    .word 0xE10F8000                 ; mrs r8, cpsr
    orr r1, r8, #0xC0
    .word 0xE121F001                 ; msr cpsr_c, r1
    ldr r0, [r4, #NR_REQUEST]
nr_service_claim_loaded:
    cmp r0, #1
    mov r0, #0
    str r0, [r4, #NR_REQUEST]
    moveq r1, #3
    streq r1, [r4, #NR_PHASE]
    .word 0xE121F008                 ; msr cpsr_c, r8
    bne nr_service_return
    str r0, [r4, #NR_ERROR]
    str r0, [r4, #NR_BYTES]
    str r0, [r4, #NR_DROPPED]
    str r0, [r4, #NR_ELAPSED]
    str r0, [r4, #NR_CAPACITY]
    mov r6, #NR_RING_BYTES
nr_service_allocate:
    add r0, r6, #RC_SIZE
    ldr r12, =MG_ALLOC
    blx r12
    cmp r0, #0
    bne nr_service_allocated
    cmp r6, #131072
    movls r0, #NR_OOM
    bls nr_service_start_error
    mov r6, r6, lsr #1
    b nr_service_allocate
nr_service_allocated:
    str r6, [r4, #NR_CAPACITY]
    mov r5, r0
    mov r1, #0
    mov r2, #RC_SIZE/4
nr_service_zero:
    str r1, [r0], #4
    subs r2, r2, #1
    bne nr_service_zero
    add r0, r5, #RC_SIZE
    str r0, [r5, #RC_RING]
    str r6, [r5, #RC_CAPACITY]
    mov r0, #2
    str r0, [r5, #RC_CHANNELS]
    ldr r0, [r4, #NR_NUMBER]
    str r0, [r5, #RW_NUMBER]
    ldr r0, =OS_TICKS
    ldr r0, [r0]
    str r0, [r4, #NR_START]
    str r5, [r4, #NR_CONTEXT]
    mov r0, r5
    mov r1, #1
    bl recorder_command
nr_service_command:
    bl nr_take_request
    cmp r0, #2
    bne nr_service_pump
    mov r0, r5
    mov r1, #0
    bl recorder_command
nr_service_pump:
    mov r0, r5
    bl recorder_pump
    str r0, [r4, #NR_ERROR]
    ldr r0, [r5, #RC_FILE_BYTES]
    str r0, [r4, #NR_BYTES]
    ldr r0, [r5, #RC_DROPPED]
    str r0, [r4, #NR_DROPPED]
    ldr r0, [r5, #RW_NUMBER]
    str r0, [r4, #NR_NUMBER]
    ldr r0, =OS_TICKS
    ldr r0, [r0]
    ldr r1, [r4, #NR_START]
    sub r0, r0, r1
    str r0, [r4, #NR_ELAPSED]
    ldr r0, [r5, #RC_ACTIVE]
    cmp r0, #0
    moveq r0, #2
    str r0, [r4, #NR_PHASE]
    mov r0, r5
    bl recorder_busy
    cmp r0, #0
    bne nr_service_return
    mov r0, r5
    ldr r12, =MG_FREE
    blx r12
    b nr_service_clear
nr_service_start_error:
    str r0, [r4, #NR_ERROR]
nr_service_clear:
    .word 0xE10F8000                 ; mrs r8, cpsr
    orr r1, r8, #0xC0
    .word 0xE121F001                 ; msr cpsr_c, r1
    mov r0, #0
    str r0, [r4, #NR_PHASE]
    str r0, [r4, #NR_REQUEST]
    str r0, [r4, #NR_CONTEXT]
    .word 0xE121F008                 ; msr cpsr_c, r8
nr_service_return:
    ldr r0, [r4, #NR_ERROR]
    pop {r4-r8, pc}
.pool

nr_runtime_end:
