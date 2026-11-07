; UI_* constants are generated from the exact official runtime and companion blob.
; Hook the original display blit: prepare overlay, then execute its original first instruction.
scope_ui_hook:
    push {r0-r12, lr}
    .word 0xE10FC000
    push {r12, lr}
    bl scope_ui_frame
    pop {r12, lr}
    .word 0xE128F00C
    pop {r0-r12, lr}
    mov r12, #0
    b UI_BLIT + 4
.pool

scope_ui_frame:
    push {r4-r8, lr}
    ldr r4, =scope_control
    mov r0, #0
    str r0, [r4]
    str r0, [r4, #36]
    ldr r0, =UI_SCREEN_MANAGER
    ldr r0, [r0]
    ldr r1, =0xC0000000
    cmp r0, r1
    blo ui_done
    ldr r1, =0xC0FFFF00
    cmp r0, r1
    bhi ui_done
    ldr r1, [r0, #0x2c]
    cmp r1, #1
    bne ui_done
    ; Main-screen parameter popups are normal during knob/part edits. The original
    ; app blit owns the picture there too; do not stop capture for that popup.
    bl scope_find_app
    cmp r0, #0
    beq ui_done
    mov r5, r0
    ldr r0, =UI_PART
    ldr r6, [r0]
    cmp r6, #15
    bhi ui_done
    ; Native pairing query takes the current part record in r1 and part index in r2.
    ldr r0, =0xC033E6A4
    ldr r1, [r0]
    ldr r0, =0xC0200000
    cmp r1, r0
    blo ui_done
    ldr r0, =0xC0FFF000
    cmp r1, r0
    bhi ui_done
    ldr r0, =0x330
    mul r2, r6, r0
    add r1, r1, r2
    add r1, r1, #0x800
    add r1, r1, #4
    ldrb r8, [r1, #8]
    ldrb r0, [r1, #9]
    orr r8, r8, r0, lsl #8
    mov r2, r6
    bl 0xC007DDCC
    cmp r0, #1
    moveq r0, #1
    movne r0, #0
    str r0, [r4, #8]
    str r6, [r4, #4]
    ; Sample stereo metadata is independent of native one/two-pad pairing.
    mov r0, r8
    bl 0xC004E41C
    cmp r0, #0
    movne r0, #2
    str r0, [r4, #12]
    add r7, r5, #UI_ENTRY_STORE
    str r0, [r7, #8]
    ldr r0, [r7, #0]
    str r0, [r4, #20]
    ldr r0, [r7, #4]
    str r0, [r4, #16]
    ldr r0, [r7, #12]
    str r0, [r4, #40]
    ldr r0, =OS_TICKS
    ldr r0, [r0]
    str r0, [r4, #32]
    mov r0, #1
    str r0, [r4, #36]
    str r0, [r4]
    ldr r0, [r4, #28]
    str r0, [r7, #16]
    cmp r0, #OK
    bne ui_done
    ldr r0, =UI_DISPLAY
    bl scope_ui_overlay
ui_done:
    pop {r4-r8, pc}
.pool

; overlay(display1024): copy only y=10..54, retaining plugin title and footer pixels.
scope_ui_overlay:
    push {r4-r8, lr}
    mov r4, r0
    ldr r0, =scope_control
    ldr r0, [r0, #24]
    cmp r0, #0
    beq overlay_done
    cmn r0, #1
    beq overlay_done
    ldr r2, [r0, #56]
    ldr r1, =FRAME_A
    add r1, r0, r1
    cmp r2, r1
    beq overlay_ready
    ldr r1, =FRAME_B
    add r1, r0, r1
    cmp r2, r1
    bne overlay_done
overlay_ready:
    add r2, r2, #128
    add r4, r4, #128
    mov r5, #128
overlay_first:
    ldrb r0, [r2], #1
    ldrb r1, [r4]
    and r0, r0, #0xfc
    and r1, r1, #3
    orr r0, r0, r1
    strb r0, [r4], #1
    subs r5, r5, #1
    bne overlay_first
    mov r5, #128
overlay_middle:
    ldr r0, [r2], #4
    str r0, [r4], #4
    subs r5, r5, #1
    bne overlay_middle
    mov r5, #128
overlay_last:
    ldrb r0, [r2], #1
    ldrb r1, [r4]
    and r0, r0, #0x7f
    and r1, r1, #0x80
    orr r0, r0, r1
    strb r0, [r4], #1
    subs r5, r5, #1
    bne overlay_last
overlay_done:
    pop {r4-r8, pc}
.pool

; Return the open, armed companion entry, or 0. All other apps keep their original behavior.
scope_find_app:
    push {r4-r6, lr}
    ldr r0, =UI_APP_STATE
    ldr r4, [r0]
    ldr r1, =UI_POOL
    cmp r4, r1
    blo find_none
    ldr r1, =UI_POOL_END - UI_ENTRY_SIZE
    cmp r4, r1
    bhi find_none
    ldr r1, [r4, #UI_ENTRY_STATE]
    cmp r1, #UI_ARMED
    bne find_none
    ldr r0, [r4, #UI_ENTRY_BLOB]
    ldr r1, =UI_POOL
    cmp r0, r1
    blo find_none
    ldr r1, =UI_POOL_END - UI_BLOB_SIZE
    cmp r0, r1
    bhi find_none
    ldr r1, [r0, #0]
    ldr r2, =UI_BLOB_MAGIC
    cmp r1, r2
    bne find_none
    ldr r1, [r0, #8]
    ldr r2, =UI_BLOB_SIZE
    cmp r1, r2
    bne find_none
    ldr r1, [r0, #12]
    ldr r2, =UI_BLOB_CRC
    cmp r1, r2
    bne find_none
    add r0, r0, #36
    ldr r2, =ui_name
    mov r3, #4
find_name:
    ldr r1, [r0], #4
    ldr r6, [r2], #4
    cmp r1, r6
    bne find_none
    subs r3, r3, #1
    bne find_name
    mov r0, r4
    pop {r4-r6, pc}
find_none:
    mov r0, #0
    pop {r4-r6, pc}
.pool

; For this companion only, reserve BAR 1..4; other controls keep the native path.
; Original r5 = message object, r6 = kind. Preserve registers/flags around identity checking.
scope_input_hook:
    push {r0-r12, lr}
    .word 0xE10FC000
    push {r12, lr}
    bl scope_find_app
    cmp r0, #0
    beq input_original
    cmp r6, #0
    bne input_original
    ldrb r0, [r5, #0x0d]
    cmp r0, #28
    blo input_normal_mask
    cmp r0, #31
    bls input_original
input_normal_mask:
    pop {r12, lr}
    .word 0xE128F00C
    pop {r0-r12, lr}
    b UI_INPUT_MASK_GO
input_original:
    pop {r12, lr}
    .word 0xE128F00C
    pop {r0-r12, lr}
    orr r1, r1, #1
    b UI_INPUT_MASK_GO
.pool
ui_name:
    .asciz "Spettro"
    .space 8
.align 4
