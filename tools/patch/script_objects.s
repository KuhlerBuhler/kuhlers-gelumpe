; The object tree of the plugin API (data/script/objects.mjs): korg.get and korg.set reach every leaf through one table,
; a value outside its range is clamped and counted, and the stored ones are checked once the menu has read its settings.
; In the code area at MORE3_START. A row (OBJ_ROW_SIZE bytes): offset, min, max, factory (words), base, type, apply, flags.
.align 4
; korg.get(leaf, index) -> r0 = the value; no such leaf: API_ARG
script_object_get_glue:
    push {r4, lr}
    bl objects_row
    cmp r4, #0
    beq objects_bad
    ldrb r1, [r4, #17]
    cmp r1, #0
    ldrbeq r0, [r0]
    ldrne r0, [r0]
    mov r1, #ERR_OK
    pop {r4, pc}
; korg.set(leaf, index, value): clamps to the leaf's range (counted), writes, applies; no such leaf or read only: API_ARG
script_object_set_glue:
    push {r4-r6, lr}
    mov r5, r2
    bl objects_row
    cmp r4, #0
    beq objects_bad_set
    ldrb r1, [r4, #19]
    tst r1, #1
    beq objects_bad_set
    mov r6, r0
    mov r0, r5
    bl objects_clamp
    ldrb r1, [r4, #17]
    cmp r1, #0
    strbeq r0, [r6]
    strne r0, [r6]
    bl objects_apply
    mov r0, #0
    mov r1, #ERR_OK
    pop {r4-r6, pc}
objects_bad_set:
    mov r0, #0
    mov r1, #ERR_API_ARG
    pop {r4-r6, pc}
objects_bad:
    mov r0, #0
    mov r1, #ERR_API_ARG
    pop {r4, pc}

; r0 = leaf -> r4 = its row (0: no such leaf), r0 = the address of its value
objects_row:
    mov r4, #0
    cmp r0, #OBJ_COUNT
    bxhs lr
    ldr r4, =objects_table
    add r1, r0, r0, lsl #2
    add r4, r4, r1, lsl #2
    ldrb r1, [r4, #16]
    ldr r2, =objects_bases
    ldr r2, [r2, r1, lsl #2]
    ldr r0, [r4]
    add r0, r2, r0
    bx lr

; r0 = value, r4 = row -> r0 inside min and max; one more in objects_repairs when it was outside (r1 to r3 change)
objects_clamp:
    ldr r1, [r4, #4]
    ldr r2, [r4, #8]
    cmp r0, r1
    movlt r0, r1
    blt objects_count
    cmp r0, r2
    bxle lr
    mov r0, r2
objects_count:
    ldr r3, =objects_state
    ldr r1, [r3]
    add r1, r1, #1
    str r1, [r3]
    bx lr

; r4 = row: makes the written value take effect
objects_apply:
    ldrb r0, [r4, #18]
    cmp r0, #1
    beq menu_look_apply
    bx lr

; Every stored leaf outside its range goes to the nearest valid value, or to its factory value with the reset flag; each
; one counts. Called once the menu has read its settings (menu_arm_load), whatever left the value there.
objects_repair:
    push {r4-r7, lr}
    mov r5, #0
objects_repair_next:
    cmp r5, #OBJ_COUNT
    bhs objects_repair_out
    mov r0, r5
    bl objects_row
    add r5, r5, #1
    ldrb r1, [r4, #19]
    tst r1, #4
    beq objects_repair_next
    mov r6, r0
    ldrb r1, [r4, #17]
    cmp r1, #0
    ldrbeq r0, [r6]
    ldrne r0, [r6]
    mov r7, r0
    bl objects_clamp
    cmp r0, r7
    beq objects_repair_next
    ldrb r1, [r4, #19]
    tst r1, #2
    ldrne r0, [r4, #12]
    ldrb r1, [r4, #17]
    cmp r1, #0
    strbeq r0, [r6]
    strne r0, [r6]
    bl objects_apply
    b objects_repair_next
objects_repair_out:
    pop {r4-r7, pc}
.pool

.align 4
objects_bases:
    .word MENU_STATE, objects_state
objects_state:
objects_repairs:
    .word 0                         ; values clamped or reset since start (korg.system.repairs)
objects_table:
@OBJECT_ROWS@
.align 4
objects_end:
