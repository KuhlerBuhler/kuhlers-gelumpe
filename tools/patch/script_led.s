; r0 index, r1 level; native API result r0 value, r1 error.
script_led_glue:
    mov r2, r1
    mov r1, r0
    ldr r0, =HOOK_RUNTIME
    b script_led_request

script_led_request:
    cmp r1, #SCRIPT_LED_COUNT
    bhs led_bad_arg
    cmp r2, #SCRIPT_LED_LEVEL_MAX
    bhi led_bad_arg
    ldr r3, =RT_LED
    add r0, r0, r3
    add r3, r0, #SCRIPT_LED_DESIRED
    strb r2, [r3, r1]
    add r3, r0, #SCRIPT_LED_VALID
    ldrb r12, [r3, r1]
    orr r12, r12, #SCRIPT_LED_VALID_DESIRED
    strb r12, [r3, r1]
    tst r12, #SCRIPT_LED_VALID_DELIVERED
    mov r12, #1
    beq led_pending
    add r3, r0, #SCRIPT_LED_DELIVERED
    ldrb r3, [r3, r1]
    cmp r3, r2
    moveq r12, #0
led_pending:
    add r3, r0, #SCRIPT_LED_PENDING
    strb r12, [r3, r1]
    mov r0, #0
    mov r1, #ERR_OK
    bx lr
led_bad_arg:
    mov r0, #0
    mov r1, #ERR_API_ARG
    bx lr
.pool

script_led_begin_frame:
    mov r1, #0
    str r1, [r0, #SCRIPT_CONTROL_LED_SENT]
    ldr r2, =RT_LED+SCRIPT_LED_VALID
    add r2, r0, r2
led_begin_loop:
    ldrb r3, [r2, r1]
    bic r3, r3, #SCRIPT_LED_VALID_DELIVERED
    strb r3, [r2, r1]
    add r1, r1, #1
    cmp r1, #SCRIPT_LED_COUNT
    blo led_begin_loop
    bx lr
.pool

; r0 runtime; returns accepted packet count.
script_led_flush:
    push {r4-r11, lr}
    sub sp, sp, #4
    mov r4, r0
    ldr r5, =RT_LED
    add r5, r4, r5
    ldr r6, [r5, #SCRIPT_LED_NEXT_INDEX]
    cmp r6, #SCRIPT_LED_COUNT
    movhs r6, #0
    mov r7, #0
    mov r8, #0
led_flush_loop:
    ldr r0, [r4, #SCRIPT_CONTROL_LED_SENT]
    cmp r0, #SCRIPT_LED_PER_FRAME
    bhs led_flush_done
    cmp r7, #SCRIPT_LED_COUNT
    bhs led_flush_done
    add r7, r7, #1
    mov r9, r6
    add r6, r6, #1
    cmp r6, #SCRIPT_LED_COUNT
    moveq r6, #0
    add r0, r5, #SCRIPT_LED_PENDING
    ldrb r0, [r0, r9]
    cmp r0, #0
    beq led_flush_loop
    ldr r0, [r4, #RT_FRAME_ACTIVE]
    cmp r0, #1
    bne led_flush_send
    ldr r0, =SCRIPT_TIMER_ADDRESS
    ldr r0, [r0]
    ldr r1, [r4, #RT_FRAME_START]
    sub r0, r0, r1
    ldr r1, [r4, #RT_MAXTICKS]
    cmp r0, r1
    bhi led_flush_retry
led_flush_send:
    mov r0, r9
    add r1, r5, #SCRIPT_LED_DESIRED
    ldrb r10, [r1, r9]
    mov r1, r10
    bl script_led_try_send
    cmp r0, #0
    beq led_flush_retry
    mov r0, #0
    add r1, r5, #SCRIPT_LED_PENDING
    strb r0, [r1, r9]
    add r1, r5, #SCRIPT_LED_DELIVERED
    strb r10, [r1, r9]
    add r1, r5, #SCRIPT_LED_VALID
    ldrb r0, [r1, r9]
    orr r0, r0, #SCRIPT_LED_VALID_DELIVERED
    strb r0, [r1, r9]
    add r8, r8, #1
    ldr r0, [r4, #SCRIPT_CONTROL_LED_SENT]
    add r0, r0, #1
    str r0, [r4, #SCRIPT_CONTROL_LED_SENT]
    b led_flush_loop
led_flush_retry:
    mov r6, r9
led_flush_done:
    str r6, [r5, #SCRIPT_LED_NEXT_INDEX]
    mov r0, r8
    add sp, sp, #4
    pop {r4-r11, pc}
.pool

; r0 index, r1 level; returns 1 only after atomic enqueue.
script_led_try_send:
    push {r4-r11, lr}
    sub sp, sp, #4
    mov r4, r0
    mov r5, r1
    ldr r0, =objects_test_mode      ; the test mode keeps every LED dark, whatever a plugin set
    ldrb r0, [r0]
    cmp r0, #0
    movne r5, #0
    .word 0xE10F6000 ; mrs r6, cpsr
    tst r6, #0x80
    bne led_send_reject
    cmp r4, #SCRIPT_LED_COUNT
    bhs led_send_reject
    cmp r5, #SCRIPT_LED_LEVEL_MAX
    bhi led_send_reject
    orr r12, r6, #0x80
    .word 0xE121F00C ; msr cpsr_c, r12
led_send_critical:
    ldr r0, =0xC033E6FC
    ldr r0, [r0]
    ldr r1, =0xC0000000
    cmp r0, r1
    blo led_send_reject
    ldr r1, =0xC07FFFF8
    cmp r0, r1
    bhi led_send_reject
    ldrb r0, [r0, #4]
    cmp r0, #0
    bne led_send_reject
    ldr r7, =0xC033E648
    ldr r0, [r7, #8]
    cmp r0, #5
    bne led_send_reject
    ldr r0, =0xC06A24C0
    ldr r0, [r0]
    cmp r0, #1
    bne led_send_reject
    ldrb r0, [r7, #0x0e]
    ldrb r12, [r7, #15]
    orr r0, r0, r12, lsl #8
    cmp r0, #1
    bne led_send_reject
    ldrb r0, [r7, #0x16]
    ldrb r12, [r7, #23]
    orr r0, r0, r12, lsl #8
    cmp r0, #1024
    bne led_send_reject
    ldrb r0, [r7, #0x18]
    ldrb r12, [r7, #25]
    orr r0, r0, r12, lsl #8
    ldr r1, =0x13FF
    cmp r0, r1
    bne led_send_reject
    ldrb r8, [r7, #0x14]
    ldrb r12, [r7, #21]
    orr r8, r8, r12, lsl #8
    ldr r0, =1024-SCRIPT_LED_RESERVE_BYTES-SCRIPT_LED_PACKET_BYTES
    cmp r8, r0
    bhi led_send_reject
    ldrb r9, [r7, #0x10]
    ldrb r12, [r7, #17]
    orr r9, r9, r12, lsl #8
    cmp r9, #1024
    bhs led_send_reject
    ldrb r0, [r7, #0x12]
    ldrb r12, [r7, #19]
    orr r0, r0, r12, lsl #8
    cmp r0, #1024
    bhs led_send_reject
    sub r0, r9, r0
    ldr r12, =1023
    and r0, r0, r12
    cmp r0, r8
    bne led_send_reject
    ldr r10, [r7, #4]
    ldr r0, =0xC0000000
    cmp r10, r0
    blo led_send_reject
    ldr r0, =0xC07FFC00
    cmp r10, r0
    bhi led_send_reject
    ldr r0, [r7, #0x20]
    ldr r1, =0xC002548C
    cmp r0, r1
    bne led_send_reject
    ldr r0, =0xC033E644
    ldr r0, [r0]
    ldr r1, =0x01C42000
    cmp r0, r1
    bne led_send_reject
    mov r11, #0
led_send_bytes:
    mov r0, #0
    cmp r11, #1
    moveq r0, r4
    cmp r11, #2
    moveq r0, r5
    strb r0, [r10, r9]
    add r9, r9, #1
    ldr r1, =1023
    and r9, r9, r1
    add r11, r11, #1
    cmp r11, #SCRIPT_LED_PACKET_BYTES
    blo led_send_bytes
    strb r9, [r7, #0x10]
    mov r12, r9, lsr #8
    strb r12, [r7, #17]
    add r0, r8, #SCRIPT_LED_PACKET_BYTES
    strb r0, [r7, #0x14]
    mov r12, r0, lsr #8
    strb r12, [r7, #21]
    cmp r8, #0
    bne led_send_accept
    ldr r12, [r7, #0x20]
    blx r12
led_send_accept:
    mov r0, #1
    b led_send_restore
led_send_reject:
    mov r0, #0
led_send_restore:
    .word 0xE12FF006 ; msr cpsr_cxsf, r6
    add sp, sp, #4
    pop {r4-r11, pc}
.pool
