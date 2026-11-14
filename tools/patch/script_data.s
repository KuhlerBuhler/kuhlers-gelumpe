; korg.file.read and korg.file.write (API 32): one data file per plugin, SD:KORG/blechtribe/Plugin/Data/<name>.bin, at most
; SCRIPT_DATA_FILE_BYTES (SCRIPT_DATA_FILE in data/script/contract.mjs). The file of one plugin at a time sits in a block of the
; firmware heap, taken at the first call and kept until power-off: the plugin's name (16 bytes), then the file. A write changes
; the block; script_data_flush writes it to the card as script_store_flush writes the store: while the main screen or BLECH is
; up and STORE_MIN_PAUSE_FRAMES after the last write. Uses the loader's file object.
.equ DF_BLOCK, DATA_FILE        ; -> the block, FF none
.equ DF_SIZE, 4                 ; from DATA_FILE: the bytes of the file in the block
.equ DF_PENDING, 8              ; 1 while the block differs from the card
.equ DF_FRAME, 12               ; the frame count of the last card write
.equ DF_DATA, 16                ; in the block: the name, then the file from here
.equ DF_PATH, 64                ; stack bytes for the path: 31 folder, 16 name, 4 extension, the zero
.equ DF_NEW, 0xC0028DCC         ; the firmware's operator new
.equ FR_NO_FILE, 4

; r0 array handle (checked by the VM), r1 offset -> r0 the bytes copied into the array, one to a slot, from the offset on: up to the
; end of the array or the file, -1 when the card cannot be read (not the main screen or BLECH, no card, a write of another plugin
; that still waits for the card).
script_file_read_glue:
    push {r4-r7, lr}
    bl data_args
    bl data_take
    cmp r0, #0
    mvneq r0, #0
    beq data_done
    ldr r1, =DATA_FILE
    ldr r1, [r1, #DF_SIZE]
    subs r1, r1, r7
    movlo r1, #0
    cmp r1, r4
    movhi r1, r4
    add r0, r0, #DF_DATA
    add r0, r0, r7
    mov r2, #0
data_read_copy:
    cmp r2, r1
    ldrblo r3, [r0, r2]
    strlo r3, [r5, r2, lsl #2]
    addlo r2, r2, #1
    blo data_read_copy
    mov r0, r1
data_done:
    mov r1, #ERR_OK
    pop {r4-r7, pc}

; r0 array handle, r1 offset -> r0 the bytes taken from the array (the low byte of each slot) into the file from the offset on, up
; to the end of the array or SCRIPT_DATA_FILE_BYTES; -1 as korg.file.read. A gap behind the old end of the file reads as 0.
script_file_write_glue:
    push {r4-r7, lr}
    bl data_args
    bl data_take
    cmp r0, #0
    mvneq r0, #0
    beq data_done
    ldr r1, =SCRIPT_DATA_FILE_BYTES
    sub r1, r1, r7
    cmp r1, r4
    movhi r1, r4
    add r0, r0, #DF_DATA
    add r0, r0, r7
    mov r2, #0
data_write_copy:
    cmp r2, r1
    ldrlo r3, [r5, r2, lsl #2]
    strblo r3, [r0, r2]
    addlo r2, r2, #1
    blo data_write_copy
    ldr r2, =DATA_FILE
    add r3, r7, r1
    ldr r0, [r2, #DF_SIZE]
    cmp r3, r0
    strhi r3, [r2, #DF_SIZE]
    mov r0, #1
    str r0, [r2, #DF_PENDING]
    mov r0, r1
    b data_done

; r0 array handle, r1 offset -> r0 the plugin's name, r4 the slots of the array, r5 its first slot, r7 the offset.
data_args:
    mov r4, r0, lsr #16
    mov r5, r0, lsl #16
    mov r7, r1
    ldr r6, =HOOK_RUNTIME
    ldr r6, [r6, #RT_ENTRY]
    ldr r0, [r6, #SCRIPT_ENTRY_BLOB]
    add r0, r0, #HDR_NAME
    ldr r6, [r6, #SCRIPT_ENTRY_VARS]
    add r5, r6, r5, lsr #14
    bx lr

; -> EQ when the card is free for us: the main screen or BLECH is up. Clobbers r12.
data_screen:
    ldr r12, =SCREEN_MANAGER
    ldr r12, [r12]
    cmp r12, #0
    beq data_screen_no
    cmn r12, #1
    beq data_screen_no
    ldr r12, [r12, #0x2c]
    cmp r12, #1
    cmpne r12, #MENU_SCREEN
    bx lr
data_screen_no:
    cmp r12, #1
    bx lr

; r0 the plugin's name -> r0 the block with that plugin's file, 0 when it cannot be had. Takes the block from the heap at the
; first call; reads the file from the card when the block holds another plugin's (or none) and no write waits for the card.
data_take:
    push {r4-r8, lr}
    mov r4, r0
    ldr r5, =DATA_FILE
    ldr r6, [r5]
    cmn r6, #1
    bne data_take_have
    ldr r0, =DF_DATA+SCRIPT_DATA_FILE_BYTES
    bl DF_NEW
    cmp r0, #0
    beq data_take_fail
    mov r6, r0
    str r6, [r5]
    mvn r0, #0
    str r0, [r6]
    mov r0, #0
    str r0, [r5, #DF_PENDING]
data_take_have:
    mov r1, #0
data_take_compare:
    ldr r2, [r4, r1]
    ldr r3, [r6, r1]
    cmp r2, r3
    bne data_take_load
    add r1, r1, #4
    cmp r1, #DF_DATA
    blo data_take_compare
    mov r0, r6
    pop {r4-r8, pc}
data_take_load:
    ldr r0, [r5, #DF_PENDING]
    cmp r0, #1
    beq data_take_fail
    bl data_screen
    bne data_take_fail
    mov r1, #0
data_take_name:
    ldr r2, [r4, r1]
    str r2, [r6, r1]
    add r1, r1, #4
    cmp r1, #DF_DATA
    blo data_take_name
    sub sp, sp, #DF_PATH
    mov r0, sp
    mov r1, r6
    bl data_path
    ldr r7, =HOOK_CARD
    add r0, r7, #CARD_FIL
    mov r1, sp
    mov r2, #1
    ldr r12, =FS_OPEN
    blx r12
    mov r1, #0
    cmp r0, #FR_NO_FILE
    cmpne r0, #FR_NO_PATH
    beq data_take_size
    cmp r0, #0
    bne data_take_unknown
    add r0, r7, #CARD_FIL
    add r1, r6, #DF_DATA
    ldr r2, =SCRIPT_DATA_FILE_BYTES
    add r3, r7, #CARD_BR
    ldr r12, =FS_READ
    blx r12
    mov r8, r0
    add r0, r7, #CARD_FIL
    ldr r12, =FS_CLOSE
    blx r12
    cmp r8, #0
    bne data_take_unknown
    ldr r1, [r7, #CARD_BR]
data_take_size:
    str r1, [r5, #DF_SIZE]
    add r0, r6, #DF_DATA
    ldr r2, =SCRIPT_DATA_FILE_BYTES
    mov r3, #0
data_take_zero:
    cmp r1, r2
    strblo r3, [r0, r1]
    addlo r1, r1, #1
    blo data_take_zero
    add sp, sp, #DF_PATH
    mov r0, r6
    pop {r4-r8, pc}
data_take_unknown:
    mvn r0, #0
    str r0, [r6]
    add sp, sp, #DF_PATH
data_take_fail:
    mov r0, #0
    pop {r4-r8, pc}

; r0 destination, r1 the name (16 bytes, zero ends it early): SD:KORG/blechtribe/Plugin/Data/<name>.bin, every character other
; than A to Z, a to z, 0 to 9 and "-" as "_" (dataFileName in data/script/contract.mjs).
data_path:
    ldr r2, =data_folder
data_path_folder:
    ldrb r3, [r2], #1
    cmp r3, #0
    strbne r3, [r0], #1
    bne data_path_folder
    mov r2, #0
data_path_name:
    ldrb r3, [r1, r2]
    cmp r3, #0
    beq data_path_end
    sub r12, r3, #0x30
    cmp r12, #10
    blo data_path_keep
    orr r12, r3, #0x20
    sub r12, r12, #0x61
    cmp r12, #26
    blo data_path_keep
    cmp r3, #0x2D
    movne r3, #0x5F
data_path_keep:
    strb r3, [r0], #1
    add r2, r2, #1
    cmp r2, #16
    blo data_path_name
data_path_end:
    cmp r2, #0
    moveq r3, #0x5F
    strbeq r3, [r0], #1
    ldr r2, =data_extension
data_path_extension:
    ldrb r3, [r2], #1
    strb r3, [r0], #1
    cmp r3, #0
    bne data_path_extension
    bx lr

; r0 runtime. Writes the block to its file when a plugin changed it, the card is free for us and the pause since the last write is
; over; a failed write is tried again after the next pause.
script_data_flush:
    push {r4-r7, lr}
    ldr r5, =DATA_FILE
    ldr r1, [r5, #DF_PENDING]
    cmp r1, #1
    bne data_flush_return
    bl data_screen
    bne data_flush_return
    ldr r1, [r0, #SCRIPT_CONTROL_FRAMES]
    ldr r2, [r5, #DF_FRAME]
    sub r2, r1, r2
    cmp r2, #STORE_MIN_PAUSE_FRAMES
    blo data_flush_return
    str r1, [r5, #DF_FRAME]
    ldr r6, [r5]
    sub sp, sp, #DF_PATH
    mov r0, sp
    mov r1, r6
    bl data_path
    ldr r7, =HOOK_CARD
    add r0, r7, #CARD_FIL
    mov r1, sp
    bl card_create
    cmp r0, #0
    bne data_flush_done
    add r0, r7, #CARD_FIL
    add r1, r6, #DF_DATA
    ldr r2, [r5, #DF_SIZE]
    add r3, r7, #CARD_BR
    ldr r12, =FS_WRITE
    blx r12
    mov r4, r0
    add r0, r7, #CARD_FIL
    ldr r12, =FS_CLOSE
    blx r12
    cmp r4, #0
    bne data_flush_done
    ldr r0, [r7, #CARD_BR]
    ldr r1, [r5, #DF_SIZE]
    cmp r0, r1
    moveq r0, #0
    streq r0, [r5, #DF_PENDING]
data_flush_done:
    add sp, sp, #DF_PATH
data_flush_return:
    pop {r4-r7, pc}
data_folder:
    .asciz "SD:KORG/blechtribe/Plugin/Data/"
data_extension:
    .asciz ".bin"
.align 4
.pool
