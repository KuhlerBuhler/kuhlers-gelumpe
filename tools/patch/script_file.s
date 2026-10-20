; korg.file.frame: one frame of a picture file on the card (SCRIPT_GIF in data/script/contract.mjs) into a plugin's array.
.equ FS_LSEEK, 0xC009E404
.equ GIF_FRAME_BYTES, 1024
.equ GIF_PATH_DIGITS, 26        ; offset of the two digits in gif_path
.equ GIF_HEAD, 36               ; on the stack: the path (33 bytes), then the 8 byte header, later the frame's 4 bytes

; r0 array handle (checked by the VM), r1 file 0 to 99, r2 frame. Reads that frame of SD:KORG/blechtribe/Gif/GIFnn.E2G into
; the array, one byte to a slot -> r0 its delay in ms (at least 1), 0 past the last frame, -1 no file, a bad file or not the
; main screen (the firmware may use the card elsewhere). The bytes land in the last quarter of the array's 1024 slots and are
; spread forward from the first slot; slot i never overwrites a byte not yet read. Uses the loader's file object.
script_file_frame_glue:
    mov r3, r0, lsr #16
    cmp r3, #GIF_FRAME_BYTES
    blo file_bad_arg
    push {r4-r9, lr}
    sub sp, sp, #48
    ldr r4, =HOOK_RUNTIME
    ldr r4, [r4, #RT_ENTRY]
    ldr r4, [r4, #SCRIPT_ENTRY_VARS]
    mov r3, r0, lsl #16
    add r4, r4, r3, lsr #14
    mov r8, r2
    mvn r9, #0
    ldr r3, =SCREEN_MANAGER
    ldr r3, [r3]
    cmp r3, #0
    beq file_return
    cmn r3, #1
    beq file_return
    ldr r3, [r3, #0x2c]
    cmp r3, #1
    bne file_return
    ldr r2, =gif_path
    mov r3, #0
file_path_copy:
    ldrb r0, [r2, r3]
    strb r0, [sp, r3]
    add r3, r3, #1
    cmp r0, #0
    bne file_path_copy
    mov r0, #0
file_tens:
    cmp r1, #10
    subhs r1, r1, #10
    addhs r0, r0, #1
    bhs file_tens
    add r0, r0, #0x30
    strb r0, [sp, #GIF_PATH_DIGITS]
    add r1, r1, #0x30
    strb r1, [sp, #GIF_PATH_DIGITS+1]
    ldr r5, =HOOK_CARD
    add r6, r5, #CARD_FIL
    mov r0, r6
    mov r1, sp
    mov r2, #1
    ldr r12, =FS_OPEN
    blx r12
    cmp r0, #0
    bne file_return
    mov r0, #8
    add r1, sp, #GIF_HEAD
    bl file_read
    cmp r0, #0
    bne file_close
    ldr r0, [sp, #GIF_HEAD]
    ldr r1, =SCRIPT_GIF_MAGIC
    cmp r0, r1
    bne file_close
    ldrb r0, [sp, #GIF_HEAD+4]
    ldrb r1, [sp, #GIF_HEAD+5]
    orr r0, r0, r1, lsl #8
    cmp r0, #SCRIPT_GIF_VERSION
    bne file_close
    ldrb r0, [sp, #GIF_HEAD+6]
    ldrb r1, [sp, #GIF_HEAD+7]
    orr r0, r0, r1, lsl #8
    cmp r8, r0
    movhs r9, #0
    bhs file_close
    mov r1, r8, lsl #10
    add r1, r1, r8, lsl #2
    add r1, r1, #8
    mov r0, r6
    ldr r12, =FS_LSEEK
    blx r12
    cmp r0, #0
    bne file_close
    mov r0, #4
    add r1, sp, #GIF_HEAD
    bl file_read
    cmp r0, #0
    bne file_close
    mov r0, #GIF_FRAME_BYTES
    add r1, r4, #GIF_FRAME_BYTES*3
    bl file_read
    cmp r0, #0
    bne file_close
    add r1, r4, #GIF_FRAME_BYTES*3
    mov r2, #0
file_spread:
    ldrb r0, [r1, r2]
    str r0, [r4, r2, lsl #2]
    add r2, r2, #1
    cmp r2, #GIF_FRAME_BYTES
    blo file_spread
    ldrb r9, [sp, #GIF_HEAD]
    ldrb r0, [sp, #GIF_HEAD+1]
    orr r9, r9, r0, lsl #8
    cmp r9, #0
    moveq r9, #1
file_close:
    mov r0, r6
    ldr r12, =FS_CLOSE
    blx r12
file_return:
    mov r0, r9
    mov r1, #ERR_OK
    add sp, sp, #48
    pop {r4-r9, pc}
file_bad_arg:
    mov r0, #0
    mov r1, #ERR_API_ARG
    bx lr

; r0 bytes, r1 destination; reads from the open file r6 -> r0 0 when all of them came, else not 0.
file_read:
    push {r4, lr}
    mov r4, r0
    mov r2, r0
    mov r0, r6
    add r3, r5, #CARD_BR
    ldr r12, =FS_READ
    blx r12
    cmp r0, #0
    bne file_read_done
    ldr r0, [r5, #CARD_BR]
    subs r0, r0, r4
file_read_done:
    pop {r4, pc}
gif_path:
    .asciz "SD:KORG/blechtribe/Gif/GIF00.E2G"
.align 4
.pool
