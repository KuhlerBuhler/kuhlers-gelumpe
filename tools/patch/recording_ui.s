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

; r0 panel packet -> r0 1 swallowed, 0 native. Keys of class 0: REC 0, PLAY 2. NR_HELD holds the key number + 1 of a swallowed
; press, so its release is swallowed too. In the sampling setup with RECORD chosen, PLAY starts a take bound to the transport
; (nr_transport_frame ends it with STOP), closes the setup first and goes on to the firmware, which then plays the pattern on the
; main screen instead of starting its own sampling (Korg's PLAY in the setup starts RESAMPLING, transport 11). The setup closes
; as with the firmware's own REC: the PLAY press goes on as REC (NR_HELD_AS_REC, its release too) and a PLAY of our own follows
; through the panel queue once the setup is gone (nr_play_inject_frame; NR_PLAY_INJECT lets it pass). While a take runs, PLAY in the setup does the
; same: no second take, no native sampling. REC in the setup stops a running take; idle it is the firmware's (it closes the
; setup, measured in the emulator). Outside the setup REC and PLAY stay the firmware's.
.equ NR_HELD_AS_REC, 4
nr_input:
    push {r4-r7, lr}
    mov r4, r0
    ldrb r1, [r4, #12]
    cmp r1, #0
    bne nr_input_pass
    ldrb r7, [r4, #13]
    cmp r7, #0
    cmpne r7, #2
    bne nr_input_pass
    bl nr_init
    mov r5, r0
    cmp r7, #2                       ; the PLAY handed on below goes to the firmware untouched
    bne nr_input_own
    ldrb r0, [r4, #0x13]
    cmp r0, #PK_MARK
    bne nr_input_own
    ldrb r0, [r5, #NR_PLAY_INJECT]
    sub r0, r0, #1
    cmp r0, #1
    strbls r0, [r5, #NR_PLAY_INJECT]
    bls nr_input_pass
nr_input_own:
    ldrb r0, [r4, #14]
    cmp r0, #0
    bne nr_input_press
    ldr r0, [r5, #NR_HELD]
    cmp r0, #NR_HELD_AS_REC
    cmpeq r7, #2
    bne nr_input_release
    mov r0, #0                       ; the release of a PLAY the firmware got as REC goes on as REC's
    str r0, [r5, #NR_HELD]
    strb r0, [r4, #13]
    b nr_input_return
nr_input_release:
    sub r0, r0, #1
    cmp r0, r7
    movne r0, #0
    bne nr_input_return
    mov r0, #0
    str r0, [r5, #NR_HELD]
    mov r0, #1
    b nr_input_return
nr_input_press:
    ldr r0, [r5, #NR_HELD]
    sub r0, r0, #1
    cmp r0, r7
    beq nr_input_take
    ldr r0, [r5, #NR_SETUP]
    cmp r0, #0
    beq nr_input_pass
    bl nr_busy
    mov r6, r0
    cmp r7, #2
    beq nr_input_play
    cmp r6, #0
    beq nr_input_pass
    bl nr_enabled
    cmp r0, #0
    beq nr_input_take
    ldr r0, [r5, #NR_SELECTED]
    cmp r0, #0
    beq nr_input_take
    mov r0, #0
    bl nr_post
    b nr_input_take
nr_input_play:
    cmp r6, #0
    bne nr_input_close
    bl nr_enabled
    cmp r0, #0
    beq nr_input_pass
    ldr r0, [r5, #NR_SELECTED]
    cmp r0, #0
    beq nr_input_pass
    mov r0, #1
    bl nr_post
    cmp r0, #0
    bne nr_input_take                ; refused (no card): the setup stays and shows why
    mov r0, #NR_PLAY_WAIT
    strb r0, [r5, #NR_PLAY_BOUND]
nr_input_close:
    mov r0, #0                       ; the firmware gets REC, which leaves its setup the way its own REC does (closing the window
    strb r0, [r4, #13]               ; from outside left the Sampler unable to open it again), and PLAY follows through the queue
    mov r0, #NR_HELD_AS_REC
    str r0, [r5, #NR_HELD]
    mov r0, #NR_PLAY_PENDING         ; nr_play_inject_frame sends it once the setup is gone
    strb r0, [r5, #NR_PLAY_INJECT]
    b nr_input_pass
nr_input_take:
    add r0, r7, #1
    str r0, [r5, #NR_HELD]
    mov r0, #1
    b nr_input_return
nr_input_pass:
    mov r0, #0
nr_input_return:
    pop {r4-r7, pc}
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
