.equ CARD_BR, 16
.equ CARD_CRC, 20
.equ CARD_USED, 24
.equ CARD_TOTAL, 28
.equ CARD_OPEN, 32
.equ CARD_FIL, 64
.equ FS_OPEN, 0xC009DB60
.equ FS_READ, 0xC009DD74
.equ FS_WRITE, 0xC009DFB8
.equ FS_CLOSE, 0xC009E3DC
.equ KILL_MASK, 0x2000

@START_WRAPPER@

; r0 runtime. Reads the collection, loads every block that passes, runs the
; start bodies and arms the runtime. Any failure leaves the runtime unarmed.
script_card_load:
    push {r4-r11, lr}
    sub sp, sp, #8
    mov r4, r0
    ldr r5, =HOOK_CARD
    add r6, r5, #CARD_FIL
    mov r7, #0
    mov r8, #0
    mov r9, #0
    mov r0, #0
    str r0, [r5, #CARD_OPEN]
    ldr r0, =PANEL
    ldr r0, [r0]
    cmp r0, #0
    beq card_no_panel
    cmn r0, #1
    beq card_no_panel
    ldr r0, [r0, #0x18]
    tst r0, #KILL_MASK
    bne card_kill
    ldr r0, =MENU_STATE
    ldr r0, [r0, #M_EFF_RUN]
    cmp r0, #0
    beq card_settings_off
    mov r0, r6
    ldr r1, =card_path
    mov r2, #1
    ldr r12, =FS_OPEN
    blx r12
    cmp r0, #0
    bne card_no_file
    mov r0, #1
    str r0, [r5, #CARD_OPEN]
    mov r0, r5
    mov r1, #ARCHIVE_HEADER_SIZE
    bl card_read
    cmp r0, #0
    bne card_read_error
    ldr r0, [r5, #ARCHIVE_AT_MAGIC]
    ldr r1, =ARCHIVE_MAGIC
    cmp r0, r1
    bne card_bad_header
    ldrb r0, [r5, #ARCHIVE_AT_VERSION]
    ldrb r1, [r5, #ARCHIVE_AT_VERSION+1]
    orr r0, r0, r1, lsl #8
    cmp r0, #ARCHIVE_VERSION
    bne card_bad_header
    ldrb r11, [r5, #ARCHIVE_AT_COUNT]
    ldrb r1, [r5, #ARCHIVE_AT_COUNT+1]
    orr r11, r11, r1, lsl #8
    ldr r0, =MENU_STATE
    ldr r0, [r0, #M_ON]
    cmp r0, #1
    beq card_pool_ready
    mov r0, r4
    ldr r1, =HOOK_POOL
    ldr r2, =SCRIPT_POOL_BYTES
    ldr r12, =VM_SCRIPT_RUNTIME_INIT
    blx r12
card_pool_ready:
    mvn r0, #0
    str r0, [r5, #CARD_CRC]
    mov r0, #0
    str r0, [r5, #CARD_USED]
    ldr r10, =HOOK_INPUT
card_block:
    cmp r11, #0
    beq card_blocks_done
    sub r11, r11, #1
    mov r0, r10
    mov r1, #HDR_SIZE
    bl card_read
    cmp r0, #0
    bne card_read_error
    mov r0, r10
    mov r1, #HDR_SIZE
    bl card_crc
    ldr r0, [r10, #HDR_TOTAL_SIZE]
    cmp r0, #HDR_SIZE
    blo card_block_size
    ldr r1, =ARCHIVE_MAX_BLOCK
    cmp r0, r1
    bhi card_block_size
    tst r0, #3
    bne card_block_size
    str r0, [r5, #CARD_TOTAL]
    ldr r1, [r5, #CARD_USED]
    add r1, r1, r0
    str r1, [r5, #CARD_USED]
    subs r1, r0, #HDR_SIZE
    beq card_load_block
    add r0, r10, #HDR_SIZE
    bl card_read
    cmp r0, #0
    bne card_read_error
    ldr r1, [r5, #CARD_TOTAL]
    sub r1, r1, #HDR_SIZE
    add r0, r10, #HDR_SIZE
    bl card_crc
card_load_block:
    mov r0, r4
    mov r1, r10
    ldr r2, [r5, #CARD_TOTAL]
    ldr r12, =VM_SCRIPT_LOAD_BLOCK
    blx r12
    cmp r0, #0
    beq card_block_ok
    add r8, r8, #1
    cmp r9, #0
    moveq r9, r0
    b card_block
card_block_ok:
    add r7, r7, #1
    b card_block
card_blocks_done:
    ldr r0, [r5, #CARD_USED]
    add r0, r0, #ARCHIVE_HEADER_SIZE
    ldr r1, [r5, #ARCHIVE_AT_TOTAL_SIZE]
    cmp r0, r1
    bne card_bad_header
    ldr r0, [r5, #CARD_CRC]
    mvn r0, r0
    ldr r1, [r5, #ARCHIVE_AT_CHECKSUM]
    cmp r0, r1
    bne card_bad_checksum
    bl card_close
    mov r0, r4
    bl script_store_load
    ldr r10, [r4, #RT_HEAD]
card_start:
    cmp r10, #0
    beq card_armed
    mov r0, r10
    bl menu_needs_confirm
    cmp r0, #0
    bne card_start_next
    mov r0, r4
    mov r1, r10
    mov r2, #EV_START
    ldr r3, =HOOK_INPUT
    ldr r12, =VM_SCRIPT_RUN_EVENT
    blx r12
card_start_next:
    ldr r10, [r10, #SCRIPT_ENTRY_NEXT]
    b card_start
card_armed:
    mov r0, #CARD_LOADED
    str r0, [sp]
    cmp r7, #0
    movne r0, #1
    strne r0, [r4, #RT_ARMED]
    b card_done
card_no_panel:
    mov r0, #CARD_NO_PANEL
    b card_status
card_kill:
    mov r0, #CARD_KILL_SWITCH
    b card_status
card_settings_off:
    mov r0, #CARD_SETTINGS_OFF
    b card_status
card_no_file:
    mov r0, #CARD_NO_FILE
    b card_status
card_bad_header:
    mov r0, #CARD_BAD_HEADER
    b card_reset
card_bad_checksum:
    mov r0, #CARD_BAD_CHECKSUM
    b card_reset
card_read_error:
    mov r0, #CARD_READ_ERROR
    b card_reset
card_block_size:
    mov r0, #CARD_BLOCK_SIZE
card_reset:
    str r0, [sp]
    mov r0, r4
    bl blechy_boot
    cmp r0, #0
    bne card_reset_done
    mov r0, r4
    ldr r1, =HOOK_POOL
    ldr r2, =SCRIPT_POOL_BYTES
    ldr r12, =VM_SCRIPT_RUNTIME_INIT
    blx r12
card_reset_done:
    mov r7, #0
    mov r8, #0
    mov r9, #0
    b card_done
card_status:
    str r0, [sp]
card_done:
    ldr r0, [r5, #CARD_OPEN]
    cmp r0, #0
    blne card_close
    ldr r0, [sp]
    str r0, [r4, #SCRIPT_CONTROL_CARD_STATUS]
    str r7, [r4, #SCRIPT_CONTROL_CARD_LOADED]
    str r8, [r4, #SCRIPT_CONTROL_CARD_REJECTED]
    str r9, [r4, #SCRIPT_CONTROL_CARD_FIRST_ERROR]
    add sp, sp, #8
    pop {r4-r11, pc}
.pool

; r0 destination, r1 length -> r0 0 when exactly that many bytes were read.
card_read:
    push {r4, lr}
    mov r4, r1
    mov r2, r1
    mov r1, r0
    mov r0, r6
    add r3, r5, #CARD_BR
    ldr r12, =FS_READ
    blx r12
    cmp r0, #0
    bne card_read_fail
    ldr r0, [r5, #CARD_BR]
    cmp r0, r4
    bne card_read_fail
    mov r0, #0
    pop {r4, pc}
card_read_fail:
    mov r0, #1
    pop {r4, pc}

; r0 pointer, r1 length: CRC-32 (IEEE) running state in the scratch area.
card_crc:
    ldr r2, [r5, #CARD_CRC]
    ldr r12, =0xEDB88320
    add r1, r0, r1
card_crc_byte:
    cmp r0, r1
    bhs card_crc_done
    ldrb r3, [r0], #1
    eor r2, r2, r3
    mov r3, #8
card_crc_bit:
    movs r2, r2, lsr #1
    eorcs r2, r2, r12
    subs r3, r3, #1
    bne card_crc_bit
    b card_crc_byte
card_crc_done:
    str r2, [r5, #CARD_CRC]
    bx lr

card_close:
    push {lr}
    mov r0, #0
    str r0, [r5, #CARD_OPEN]
    mov r0, r6
    ldr r12, =FS_CLOSE
    blx r12
    pop {pc}
.pool
card_path:
    .asciz "SD:KORG/blechtribe/Plugin/e2sPlugin.all"
.align 4
script_card_load_end:
