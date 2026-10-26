; Persistent script values on the card: store.a.bin and store.b.bin alternate,
; the newer valid one is read at boot into the image at HOOK_INPUT and every
; save rewrites the image into the other file. Whole file is one write, so a
; torn write leaves the previous generation intact.
.equ STORE_IMAGE, HOOK_INPUT
.equ STORE_OTHER, HOOK_INPUT+0x4000
.equ STORE_CAPACITY, 0x3FF0     ; STORE_OTHER + STORE_CAPACITY ends at the end of the block buffer, 0xC01FFFF0
.equ STORE_MAX_RECORDS, (STORE_CAPACITY-STORE_HEADER_SIZE)/STORE_RECORD_SIZE

; r0 slot, r1 fallback -> saved value, or the fallback when the slot never held one.
script_store_get_glue:
    cmp r0, #STORE_SLOTS
    bhs store_bad_arg
    ldr r2, =HOOK_RUNTIME
    ldr r2, [r2, #RT_ENTRY]
    ldr r3, [r2, #SCRIPT_ENTRY_STORE_MASK]
    mov r12, #1
    tst r3, r12, lsl r0
    beq store_fallback
    add r2, r2, #SCRIPT_ENTRY_STORE
    ldr r0, [r2, r0, lsl #2]
    mov r1, #ERR_OK
    bx lr
store_fallback:
    mov r0, r1
    mov r1, #ERR_OK
    bx lr

; r0 slot, r1 value.
script_store_set_glue:
    cmp r0, #STORE_SLOTS
    bhs store_bad_arg
    ldr r2, =HOOK_RUNTIME
    ldr r2, [r2, #RT_ENTRY]
    add r3, r2, #SCRIPT_ENTRY_STORE
    str r1, [r3, r0, lsl #2]
    ldr r3, [r2, #SCRIPT_ENTRY_STORE_MASK]
    mov r12, #1
    orr r3, r3, r12, lsl r0
    str r3, [r2, #SCRIPT_ENTRY_STORE_MASK]
    mov r0, #0
    mov r1, #ERR_OK
    bx lr

script_store_save_glue:
    ldr r2, =HOOK_RUNTIME
    mov r3, #1
    str r3, [r2, #SCRIPT_CONTROL_STORE_PENDING]
    mov r0, #0
    mov r1, #ERR_OK
    bx lr

store_bad_arg:
    mov r0, #0
    mov r1, #ERR_API_ARG
    bx lr
.pool

; r0 path, r1 destination (STORE_CAPACITY bytes) -> r0 file size when it is a valid store file, else 0.
; Uses the loader's scratch (r5) and file object (r6), which the caller sets up.
store_read_file:
    push {r4, r7, lr}
    mov r7, r1
    mov r1, r0
    mov r0, r6
    mov r2, #1
    ldr r12, =FS_OPEN
    blx r12
    cmp r0, #0
    bne store_read_fail
    mov r0, r6
    mov r1, r7
    ldr r2, =STORE_CAPACITY
    add r3, r5, #CARD_BR
    ldr r12, =FS_READ
    blx r12
    mov r4, r0
    mov r0, r6
    ldr r12, =FS_CLOSE
    blx r12
    cmp r4, #0
    bne store_read_fail
    ldr r4, [r5, #CARD_BR]
    cmp r4, #STORE_HEADER_SIZE
    blo store_read_fail
    ldr r0, [r7]
    ldr r1, =STORE_MAGIC
    cmp r0, r1
    bne store_read_fail
    ldrb r0, [r7, #4]
    ldrb r1, [r7, #5]
    orr r0, r0, r1, lsl #8
    cmp r0, #STORE_VERSION
    bne store_read_fail
    ldrb r2, [r7, #6]
    ldrb r1, [r7, #7]
    orr r2, r2, r1, lsl #8
    cmp r2, #STORE_MAX_RECORDS
    bhi store_read_fail
    mov r0, r2, lsl #6
    add r0, r0, r2, lsl #4
    add r0, r0, r2, lsl #2
    add r0, r0, #STORE_HEADER_SIZE
    cmp r0, r4
    bhi store_read_fail
    mov r4, r0
    mvn r0, #0
    str r0, [r5, #CARD_CRC]
    add r0, r7, #STORE_HEADER_SIZE
    sub r1, r4, #STORE_HEADER_SIZE
    bl card_crc
    ldr r0, [r5, #CARD_CRC]
    mvn r0, r0
    ldr r1, [r7, #12]
    cmp r0, r1
    bne store_read_fail
    mov r0, r4
    pop {r4, r7, pc}
store_read_fail:
    mov r0, #0
    pop {r4, r7, pc}
.pool

; r0 runtime, r1 0 or a script entry. Reads the newer valid store file into the image and hands each loaded script (with r1 only
; that one, 1 none) its saved values. The image shares its buffer with the import of a .blech, which reads it back this way.
script_store_load:
    push {r1, r4-r11, lr}
    mov r4, r0
    ldr r5, =HOOK_CARD
    add r6, r5, #CARD_FIL
    ldr r7, =STORE_IMAGE
    mov r0, #0
    str r0, [r7]
    str r0, [r7, #4]
    str r0, [r7, #8]
    str r0, [r7, #12]
    ldr r0, =store_path_a
    mov r1, r7
    bl store_read_file
    mov r8, r0
    ldr r0, =store_path_b
    ldr r1, =STORE_OTHER
    bl store_read_file
    mov r9, r0
    cmp r9, #0
    beq store_choose_done
    ldr r1, =STORE_OTHER
    cmp r8, #0
    beq store_take_other
    ldr r2, [r7, #8]
    ldr r3, [r1, #8]
    cmp r3, r2
    bls store_choose_done
store_take_other:
    mov r8, r9
    mov r2, #0
store_copy:
    ldr r3, [r1, r2]
    str r3, [r7, r2]
    add r2, r2, #4
    cmp r2, r8
    blo store_copy
store_choose_done:
    cmp r8, #0
    bne store_chosen
    ldr r8, =STORE_MAGIC
    str r8, [r7]
    mov r8, #1
    str r8, [r7, #4]
    mov r8, #STORE_HEADER_SIZE
store_chosen:
    ldr r0, [r7, #8]
    str r0, [r4, #SCRIPT_CONTROL_STORE_GENERATION]
    str r8, [r4, #SCRIPT_CONTROL_STORE_BYTES]
    ldrb r9, [r7, #6]
    ldrb r0, [r7, #7]
    orr r9, r9, r0, lsl #8
    ldr r10, [r4, #RT_HEAD]
store_entry:
    cmp r10, #0
    beq store_load_done
    ldr r0, [sp]
    cmp r0, #0
    cmpne r0, r10
    bne store_next_entry
    ldr r11, [r10, #SCRIPT_ENTRY_BLOB]
    mov r3, #0
    add r2, r7, #STORE_HEADER_SIZE
store_record:
    cmp r3, r9
    bhs store_next_entry
    ldr r0, [r2]
    ldr r1, [r11, #HDR_NAME]
    cmp r0, r1
    ldreq r0, [r2, #4]
    ldreq r1, [r11, #HDR_NAME+4]
    cmpeq r0, r1
    ldreq r0, [r2, #8]
    ldreq r1, [r11, #HDR_NAME+8]
    cmpeq r0, r1
    ldreq r0, [r2, #12]
    ldreq r1, [r11, #HDR_NAME+12]
    cmpeq r0, r1
    beq store_apply
    add r2, r2, #STORE_RECORD_SIZE
    add r3, r3, #1
    b store_record
store_apply:
    ldr r0, [r2, #STORE_NAME_BYTES]
    str r0, [r10, #SCRIPT_ENTRY_STORE_MASK]
    add r1, r2, #STORE_NAME_BYTES+4
    add r2, r10, #SCRIPT_ENTRY_STORE
    mov r3, #0
store_apply_loop:
    ldr r0, [r1, r3]
    str r0, [r2, r3]
    add r3, r3, #4
    cmp r3, #STORE_SLOTS*4
    blo store_apply_loop
store_next_entry:
    ldr r10, [r10, #SCRIPT_ENTRY_NEXT]
    b store_entry
store_load_done:
    pop {r1, r4-r11, pc}
.pool

; r0 runtime. Writes the image when a script asked to save, the main screen is open and the pause since the last write is over.
script_store_flush:
    push {r4-r11, lr}
    mov r4, r0
    ldr r1, [r4, #SCRIPT_CONTROL_STORE_PENDING]
    cmp r1, #1
    bne store_flush_return
    ldr r1, =SCREEN_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    beq store_flush_return
    cmn r1, #1
    beq store_flush_return
    ldr r1, [r1, #0x2c]
    cmp r1, #1
    bne store_flush_return
    ldr r2, [r4, #SCRIPT_CONTROL_STORE_FRAME]
    cmp r2, #0
    beq store_flush_go
    ldr r3, [r4, #SCRIPT_CONTROL_FRAMES]
    sub r3, r3, r2
    cmp r3, #STORE_MIN_PAUSE_FRAMES
    blo store_flush_return
store_flush_go:
    mov r1, #0
    str r1, [r4, #SCRIPT_CONTROL_STORE_PENDING]
    ldr r1, [r4, #SCRIPT_CONTROL_FRAMES]
    str r1, [r4, #SCRIPT_CONTROL_STORE_FRAME]
    ldr r5, =HOOK_CARD
    add r6, r5, #CARD_FIL
    ldr r7, =STORE_IMAGE
    ldr r0, [r7]
    ldr r1, =STORE_MAGIC
    cmp r0, r1
    movne r9, #0
    bne store_flush_header
    ldrb r9, [r7, #6]
    ldrb r0, [r7, #7]
    orr r9, r9, r0, lsl #8
    cmp r9, #STORE_MAX_RECORDS
    movhi r9, #0
store_flush_header:
    ldr r10, [r4, #RT_HEAD]
store_flush_entry:
    cmp r10, #0
    beq store_flush_write
    ldr r11, [r10, #SCRIPT_ENTRY_BLOB]
    ldr r0, =HOOK_POOL
    cmp r11, r0
    blo store_flush_next
    mov r3, #0
    add r2, r7, #STORE_HEADER_SIZE
store_flush_find:
    cmp r3, r9
    bhs store_flush_append
    ldr r0, [r2]
    ldr r1, [r11, #HDR_NAME]
    cmp r0, r1
    ldreq r0, [r2, #4]
    ldreq r1, [r11, #HDR_NAME+4]
    cmpeq r0, r1
    ldreq r0, [r2, #8]
    ldreq r1, [r11, #HDR_NAME+8]
    cmpeq r0, r1
    ldreq r0, [r2, #12]
    ldreq r1, [r11, #HDR_NAME+12]
    cmpeq r0, r1
    beq store_flush_copy
    add r2, r2, #STORE_RECORD_SIZE
    add r3, r3, #1
    b store_flush_find
store_flush_append:
    cmp r9, #STORE_MAX_RECORDS
    bhs store_flush_next
    add r9, r9, #1
    ldr r0, [r11, #HDR_NAME]
    str r0, [r2]
    ldr r0, [r11, #HDR_NAME+4]
    str r0, [r2, #4]
    ldr r0, [r11, #HDR_NAME+8]
    str r0, [r2, #8]
    ldr r0, [r11, #HDR_NAME+12]
    str r0, [r2, #12]
store_flush_copy:
    ldr r0, [r10, #SCRIPT_ENTRY_STORE_MASK]
    str r0, [r2, #STORE_NAME_BYTES]
    add r1, r2, #STORE_NAME_BYTES+4
    add r3, r10, #SCRIPT_ENTRY_STORE
    mov r0, #0
store_flush_values:
    ldr r8, [r3, r0]
    str r8, [r1, r0]
    add r0, r0, #4
    cmp r0, #STORE_SLOTS*4
    blo store_flush_values
store_flush_next:
    ldr r10, [r10, #SCRIPT_ENTRY_NEXT]
    b store_flush_entry
store_flush_write:
    ldr r0, =STORE_MAGIC
    str r0, [r7]
    mov r0, #STORE_VERSION
    strb r0, [r7, #4]
    mov r0, #0
    strb r0, [r7, #5]
    strb r9, [r7, #6]
    mov r0, r9, lsr #8
    strb r0, [r7, #7]
    ldr r8, [r4, #SCRIPT_CONTROL_STORE_GENERATION]
    add r8, r8, #1
    str r8, [r4, #SCRIPT_CONTROL_STORE_GENERATION]
    str r8, [r7, #8]
    mov r0, r9, lsl #6
    add r0, r0, r9, lsl #4
    add r0, r0, r9, lsl #2
    add r9, r0, #STORE_HEADER_SIZE
    str r9, [r4, #SCRIPT_CONTROL_STORE_BYTES]
    mvn r0, #0
    str r0, [r5, #CARD_CRC]
    add r0, r7, #STORE_HEADER_SIZE
    sub r1, r9, #STORE_HEADER_SIZE
    bl card_crc
    ldr r0, [r5, #CARD_CRC]
    mvn r0, r0
    str r0, [r7, #12]
    ldr r1, =store_path_a
    tst r8, #1
    ldrne r1, =store_path_b
    mov r0, r6
    bl card_create
    cmp r0, #0
    bne store_flush_error
    mov r0, r6
    mov r1, r7
    mov r2, r9
    add r3, r5, #CARD_BR
    ldr r12, =FS_WRITE
    blx r12
    mov r8, r0
    mov r0, r6
    ldr r12, =FS_CLOSE
    blx r12
    cmp r8, #0
    bne store_flush_error
    ldr r0, [r5, #CARD_BR]
    cmp r0, r9
    bne store_flush_error
    ldr r0, [r4, #SCRIPT_CONTROL_STORE_WRITES]
    add r0, r0, #1
    str r0, [r4, #SCRIPT_CONTROL_STORE_WRITES]
    b store_flush_return
store_flush_error:
    ldr r0, [r4, #SCRIPT_CONTROL_STORE_ERRORS]
    add r0, r0, #1
    str r0, [r4, #SCRIPT_CONTROL_STORE_ERRORS]
store_flush_return:
    pop {r4-r11, pc}
store_path_a:
    .asciz "SD:KORG/blechtribe/Plugin/store.a.bin"
store_path_b:
    .asciz "SD:KORG/blechtribe/Plugin/store.b.bin"
.align 4
.pool
