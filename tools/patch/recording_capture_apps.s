; Validated bytecode is scanned by instruction boundaries, including calls behind branches.
nr_requires_capture:
    ldr r0, [r0, #SCRIPT_ENTRY_BLOB]
    add r1, r0, #HDR_SIZE
    ldrb r2, [r0, #HDR_HANDLER_COUNT]
    ldrb r3, [r0, #HDR_HANDLER_COUNT+1]
    orr r2, r2, r3, lsl #8
    add r1, r1, r2, lsl #2
    ldrb r2, [r0, #HDR_CONST_COUNT]
    ldrb r3, [r0, #HDR_CONST_COUNT+1]
    orr r2, r2, r3, lsl #8
    add r1, r1, r2, lsl #2
    ldrb r2, [r0, #HDR_STRING_COUNT]
    ldrb r3, [r0, #HDR_STRING_COUNT+1]
    orr r2, r2, r3, lsl #8
    add r1, r1, r2, lsl #5
    ldrb r2, [r0, #HDR_CODE_SIZE]
    ldrb r3, [r0, #HDR_CODE_SIZE+1]
    orr r2, r2, r3, lsl #8
    add r2, r1, r2
    ldr r12, =NR_OP_SIZE
nr_capture_scan:
    cmp r1, r2
    bhs nr_capture_absent
    ldrb r0, [r1]
    cmp r0, #SCRIPT_OPCODE_COUNT
    bhs nr_capture_present
    ldrb r3, [r12, r0]
    cmp r3, #0
    beq nr_capture_present
    add r3, r1, r3
    cmp r3, r2
    bhi nr_capture_present
    cmp r0, #OP_CALLAPI
    bne nr_capture_next
    ldrb r0, [r1, #1]
    cmp r0, #API_KORG_AUDIO_CAPTURE
    beq nr_capture_present
nr_capture_next:
    mov r1, r3
    b nr_capture_scan
nr_capture_absent:
    mov r0, #0
    bx lr
nr_capture_present:
    mov r0, #1
    bx lr
.pool

nr_app_allowed:
    push {r4, lr}
    mov r4, r0
    bl nr_busy
    cmp r0, #0
    moveq r0, #1
    beq nr_app_allowed_done
    mov r0, r4
    bl nr_requires_capture
    eor r0, r0, #1
nr_app_allowed_done:
    pop {r4, pc}

nr_close_capture_app:
    push {r4, lr}
    ldr r0, =APP_STATE
    ldr r0, [r0, #SCRIPT_APPS_OPEN]
    cmp r0, #0
    beq nr_close_app_done
    bl nr_requires_capture
    cmp r0, #0
    blne script_app_close
nr_close_app_done:
    pop {r4, pc}
.pool

nr_capture_apps_end:
