; The setup lifetime is signalled by its constructor and destructor, without retaining a view pointer.
nr_setup_enter:
    push {r0-r3, r12, lr}
    .word 0xE10FC000                 ; mrs r12, cpsr
    push {r12, lr}
    bl nr_init
    mov r1, #1
    str r1, [r0, #NR_SETUP]
    pop {r12, lr}
    .word 0xE128F00C                 ; msr cpsr_f, r12
    pop {r0-r3, r12, lr}
    ldr r3, =0xC00E3AA8
    ldr pc, =0xC006B698
nr_setup_leave:
    push {r0-r3, r12, lr}
    .word 0xE10FC000                 ; mrs r12, cpsr
    push {r12, lr}
    bl nr_init
    mov r1, #0
    str r1, [r0, #NR_SETUP]
    pop {r12, lr}
    .word 0xE128F00C                 ; msr cpsr_f, r12
    pop {r0-r3, r12, lr}
    ldr r3, =0xC00E3AA8
    ldr pc, =0xC006B5A0
.pool

; r0 panel packet -> r0 1 swallowed, 0 native. REC is key 0; PLAY never enters this path.
nr_input:
    push {r4-r6, lr}
    mov r4, r0
    ldrb r1, [r4, #12]
    ldrb r2, [r4, #13]
    orrs r1, r1, r2
    bne nr_input_pass
    bl nr_init
    mov r5, r0
    ldrb r0, [r4, #14]
    cmp r0, #0
    bne nr_input_press
    ldr r0, [r5, #NR_HELD]
    mov r1, #0
    str r1, [r5, #NR_HELD]
    pop {r4-r6, pc}
nr_input_press:
    ldr r0, [r5, #NR_HELD]
    cmp r0, #0
    bne nr_input_take
    ldr r0, [r5, #NR_SETUP]
    cmp r0, #0
    beq nr_input_pass
    bl nr_busy
    mov r6, r0
    bl nr_enabled
    cmp r0, #0
    bne nr_input_enabled
    cmp r6, #0
    bne nr_input_take
    b nr_input_pass
nr_input_enabled:
    ldr r0, [r5, #NR_SELECTED]
    cmp r0, #0
    beq nr_input_sampling
    eor r0, r6, #1
    bl nr_post
    b nr_input_take
nr_input_sampling:
    cmp r6, #0
    beq nr_input_pass
nr_input_take:
    mov r0, #1
    str r0, [r5, #NR_HELD]
    pop {r4-r6, pc}
nr_input_pass:
    mov r0, #0
    pop {r4-r6, pc}
.pool

; Logical choices 0 Audio In, 1 Resampling, 2 Record keep the native engine's source boolean valid.
nr_source_hook:
    push {r0-r6, lr}
    mov r4, r0
    mov r5, r1
    bl nr_enabled
    cmp r0, #0
    beq nr_source_native
    bl nr_busy
    cmp r0, #0
    bne nr_source_done
    bl nr_init
    mov r6, r0
    ldr r0, [r4, #0x24]
    ldr r2, [r0, #0x708]
    ldr r3, [r6, #NR_SELECTED]
    cmp r3, #0
    movne r2, #2
    add r1, r2, r5
    cmp r1, #0
    movlt r1, #0
    cmp r1, #2
    movgt r1, #2
    cmp r1, #2
    moveq r2, #1
    movne r2, #0
    str r2, [r6, #NR_SELECTED]
    cmp r1, #0
    movne r1, #1
    ldr r4, [r0, #0x708]
    cmp r1, r4
    bne nr_source_notify
    cmp r2, r3
    beq nr_source_done
nr_source_notify:
    str r1, [r0, #0x708]
    sub sp, sp, #8
    mov r3, #1
    str r3, [sp]
    str r1, [sp, #4]
    add r0, r0, #0x400
    mov r1, sp
    ldr r12, =0xC0070688
    blx r12
    add sp, sp, #8
nr_source_done:
    pop {r0-r6, pc}
nr_source_native:
    pop {r0-r6, lr}
    push {r0-r2, lr}
    ldr pc, =0xC006B444
.pool

nr_source_label:
    push {r0, r1, r4, lr}
    mov r4, r0
    bl nr_enabled
    cmp r0, #0
    beq nr_source_label_native
    bl nr_init
    ldr r0, [r0, #NR_SELECTED]
    cmp r0, #0
    beq nr_source_label_native
    mov r0, r4
    ldr r1, =nr_record_text
    add r2, sp, #4
    ldr r12, =0xC00A324C
    blx r12
    mov r0, r4
    add sp, sp, #8
    pop {r4, pc}
nr_source_label_native:
    ldr r0, [sp]
    ldr r1, [sp, #4]
    ldr pc, =0xC008C2A4
.pool

; The native string compare avoids allocating a replacement when the text is unchanged.
nr_assign_text:
    push {r4-r6, lr}
    mov r4, r0
    mov r5, r1
    ldr r12, =0xC00A2034
    blx r12
    cmp r0, #0
    beq nr_assign_done
    mov r0, r4
    mov r1, r5
    ldr r12, =0xC00A26C0
    blx r12
    mov r0, #1
nr_assign_done:
    pop {r4-r6, pc}
.pool

nr_view_draw:
    push {r0-r6, lr}
    mov r4, r0
    bl nr_enabled
    cmp r0, #0
    beq nr_view_native
    bl nr_init
    ldr r6, [r0, #NR_SELECTED]
    ldr r0, =0xC00F9CD4
    ldr r0, [r0]
    cmp r0, #2
    bne nr_view_native
    cmp r6, #0
    beq nr_view_source
    sub sp, sp, #64
    mov r0, sp
    add r1, sp, #32
    bl nr_format
    add r0, r4, #0x48
    mov r1, sp
    bl nr_assign_text
    mov r5, r0
    add r0, r4, #0x4C
    add r1, sp, #32
    bl nr_assign_text
    orrs r0, r0, r5
    movne r0, #1
    strbne r0, [r4, #0x14]
    add sp, sp, #64
    b nr_view_native
nr_view_source:
    add r0, r4, #0x48
    ldr r1, =nr_source_text
    bl nr_assign_text
    cmp r0, #0
    movne r0, #1
    strbne r0, [r4, #0x14]
nr_view_native:
    pop {r0-r6, lr}
    push {r0-r6, lr}
    ldr pc, =0xC008C2E8
.pool

nr_source_text: .asciz "Sampling Source"
.align 4
nr_view_frame:
    bx lr
nr_ui_end:
