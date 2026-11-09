"""Names from canonical sample metadata, independent of DSP residency."""

READS = (0xC0035B3C, 0xC0035BA4, 0xC0035C08, 0xC0035CF8, 0xC0035DA8,
         0xC0035DE8, 0xC0035E18)


def source():
    return SOURCE


SOURCE = r'''
names_parser_read:
    push {r4-r6, lr}
    mov r4, r3
    mov r5, r2
    bl F_READ
    cmp r0, #0
    bne names_read_return
    ldr r6, =ST
    ldr r6, [r6, #PREP]
    cmp r6, #1
    bne names_read_return
    ldr r6, [r4]
    cmp r6, r5
    movne r0, #1
names_read_return:
    pop {r4-r6, pc}
.pool

; The native name getter keeps its candidate string in r4 and only tests r0's sign.
ss_name:
    push {r1-r3, r5, r12, lr}
    bl NAME_LOADED
    cmp r0, #0
    bge name_out
    mov r5, r0
    ldr r12, =ST
    ldr r1, [r12, #MODE]
    cmp r1, #1
    bne name_native
    ldr r1, =FILE_OWNER + 8
    ldr r1, [r1]
    cmp r1, #0
    bne name_native
    ldr r1, =NAMES + 12
    sub r0, r4, r1
    mov r0, r0, lsr #5
    bl loadable
    cmp r0, #0
    movne r0, #0
    bne name_out
name_native:
    mov r0, r5
name_out:
    pop {r1-r3, r5, r12, pc}
.pool

; The collection loader has finished its PCM reads; r0 is its still-open FIL.
names_close:
    push {r4-r6, r11, r12, lr}
    mov r4, r0
    mov r5, #0
    ldr r11, =ST
    ldr r0, [r11, #MODE]
    cmp r0, #1
    cmpeq r7, #0
    bne names_close_file
    mov r0, r4
    mov r1, #0
    bl F_LSEEK
    cmp r0, #0
    bne names_close_bad_index
    mov r0, r4
    ldr r1, =HDR
    mov r2, #4096
    add r3, r11, #GOT
    bl F_READ
    cmp r0, #0
    bne names_close_bad_index
    ldr r0, [r11, #GOT]
    cmp r0, #4096
    bne names_close_bad_index
    ldr r0, =HDR
    ldr r1, [r4, #12]
    bl store_header_valid
    cmp r0, #0
    movne r5, #4
    bne names_close_file
    mov r0, r4
    bl names_read
    mov r5, r0
    b names_close_file
names_close_bad_index:
    mov r5, #4
names_close_file:
    mov r0, r4
    bl F_CLOSE
    orrs r5, r5, r0
    beq names_closed
    ldr r0, [r11, #MODE]
    cmp r0, #1
    moveq r0, #2
    streq r0, [r11, #MODE]
    ldr r0, =BOOT_LEASE
    ldr r0, [r0]
    cmp r0, #0
    blne owner_uncertain
names_closed:
    mov r0, r5
    pop {r4-r6, r11, r12, pc}
.pool

; r0 open FIL under its caller's library lease, r11 state. Returns 0 or I/O status 4.
names_read:
    push {r4-r8, lr}
    mov r4, r0
    mov r5, #500
    ldr r6, [r11, #GEN]
names_slot:
    mov r0, r5
    bl indexed
    cmp r0, #0
    beq names_next
    mov r0, r5
    bl resident
    cmp r0, #0
    bne names_next
    ldr r1, =HDR + 16
    ldr r1, [r1, r5, lsl #2]
    mov r0, r4
    bl F_LSEEK
    cmp r0, #0
    bne names_io_error
    mov r0, #1
    str r0, [r11, #PREP]
    mov r0, r4
    ldr r1, =DESC
    mvn r2, #0
    mov r3, #0
    bl PARSER
    mov r7, r0
    mov r0, #0
    str r0, [r11, #PREP]
    ldr r0, [r11, #GEN]
    cmp r0, r6
    bne names_io_error
    cmp r7, #4
    beq names_io_error
    cmp r7, #0x7e
    bne names_bad_record
    ldr r1, =DESC
    ldrh r0, [r1]
    cmp r0, r5
    bne names_bad_record
    .word 0xE10F8000
    orr r0, r8, #0x80
    .word 0xE121F000
    ldr r0, [r11, #GEN]
    cmp r0, r6
    bne names_stale
    mov r0, r5
    bl resident
    cmp r0, #0
    bne names_published
    ldr r0, =NAMES + 12
    add r0, r0, r5, lsl #5
    ldr r1, =DESC + 2
    mov r2, #16
names_copy:
    ldrb r3, [r1], #1
    strb r3, [r0], #1
    subs r2, r2, #1
    bne names_copy
names_published:
    .word 0xE121F008
    b names_next
names_stale:
    .word 0xE121F008
    b names_io_error
names_bad_record:
    mov r0, r5
    bl set_failed
names_next:
    add r5, r5, #1
    ldr r0, =LAST_USER
    cmp r5, r0
    bls names_slot
    mov r0, #0
    pop {r4-r8, pc}
names_io_error:
    mov r0, #4
    pop {r4-r8, pc}
.pool
'''
