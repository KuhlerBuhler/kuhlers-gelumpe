; korg.file.count, korg.file.name and korg.file.picture (API 38): start images (.bmp, kind 0) and loading animations (.blla,
; kind 1) in SD:KORG/blechtribe/Media/ (SCRIPT_MEDIA in data/script/contract.mjs). The reference is src/script/media.mjs.
; count walks the folder with the BLECH menu's walker (menu_dir_open, menu_dir_next, LIST_WORK) and keeps a list per kind in
; MEDIA_LIST; name and picture read only that list. picture opens a file by its short name with the loader's file object.
.equ MS_COUNT, 0                ; from MEDIA_STATE: a byte per kind, the files count listed; above SCRIPT_MEDIA_MAX_FILES (FF) none
.equ MS_KEY, 4                  ; the place of the .blla whose header below is checked (all its lists), FF none
.equ MS_BUILT, 8                ; the progress picture of that file in MEDIA_WORK, FF none
.equ MS_N, 12                   ; its progress pictures, loop pictures, list table, size and the progress picture the loop
.equ MS_M, 16                   ; lists are taken against (loopBase in src/loading-anim.mjs)
.equ MS_TABLE, 20
.equ MS_SIZE, 24
.equ MS_BASE, 28
.equ MS_RD, 32                  ; the reader of the lists: file position of its first byte, bytes in it, the buffer, its size
.equ MS_TD, 48                  ; the reader of the list table, the same four words
.equ MD_AT, 0
.equ MD_LEN, 4
.equ MD_BUF, 8
.equ MD_CAP, 12
.equ MEDIA_ENTRY_SHORT, 0       ; in a list entry (SCRIPT_MEDIA_ENTRY_BYTES): the short name (8.3 and a zero), the length of
.equ MEDIA_ENTRY_LEN, 13        ; the name korg.file.name gives, then that name
.equ MEDIA_ENTRY_NAME, 14
.equ MEDIA_KIND_BYTES, SCRIPT_MEDIA_MAX_FILES*SCRIPT_MEDIA_ENTRY_BYTES
.equ MEDIA_PREFIX_LEN, 25       ; "SD:KORG/blechtribe/Media/"
.equ BLLA_MAGIC, 0x414C4C42     ; "BLLA"
.equ BLLA_HEADER, 16
.equ BLLA_MAX_BYTES, 16384
.equ BLLA_LOOP_MAX, 100

; -> r0 FF when the display is reversed (the BLECH menu armed and DISPLAY INVERT ON, so the controller got 0xA7), else 0. A
; picture is built with a drawn pixel set and turned by this, so a drawn pixel is dark either way, as the start image at
; power-on and the loading animation show it (readMediaPicture in src/script/media.mjs). Clobbers r1.
media_reversed:
    ldr r1, =MENU_STATE
    ldr r0, [r1, #M_ON]
    cmp r0, #1
    ldreq r0, [r1, #M_INV]
    movne r0, #0
    cmp r0, #0
    movne r0, #0xFF
    bx lr

; -> EQ when the main screen is up (the firmware may use the card elsewhere), as script_file_frame_glue checks. Clobbers r12.
media_screen:
    push {r4, lr}
    bl nr_card_busy
    pop {r4, lr}
    bxne lr
    ldr r12, =SCREEN_MANAGER
    ldr r12, [r12]
    cmp r12, #0
    beq media_screen_no
    cmn r12, #1
    beq media_screen_no
    ldr r12, [r12, #0x2c]
    cmp r12, #1
    bx lr
media_screen_no:
    cmp r12, #1
    bx lr

; r0 kind -> r0 the files of that kind listed anew from the folder, 0 without the folder, -1 when the card cannot be read or not
; the main screen (the list stays then).
script_file_count_glue:
    push {r4-r9, lr}
    mov r4, r0
    mvn r9, #0
    bl media_screen
    bne media_count_out
    ldr r8, =MEDIA_STATE
    mov r5, #0
    add r0, r8, #MS_COUNT
    strb r5, [r0, r4]
    cmp r4, #1
    mvneq r0, #0
    streq r0, [r8, #MS_KEY]
    streq r0, [r8, #MS_BUILT]
    ldr r0, =media_folder
    bl menu_dir_open
    cmp r0, #FR_NO_FILE
    cmpne r0, #FR_NO_PATH
    moveq r9, #0
    beq media_count_out
    cmp r0, #0
    bne media_count_out
    ldr r6, =MEDIA_LIST
    mov r0, #MEDIA_KIND_BYTES
    mla r6, r4, r0, r6
    cmp r4, #0
    ldreq r7, =str_bmp
    ldrne r7, =media_str_blla
media_count_next:
    cmp r5, #SCRIPT_MEDIA_MAX_FILES
    beq media_count_close
    mov r0, r7
    bl menu_dir_next
    cmp r0, #0
    beq media_count_close
    ldr r1, =LIST_INFO+9
    mov r2, #0
media_count_short:
    ldrb r3, [r1, r2]
    strb r3, [r6, r2]
    add r2, r2, #1
    cmp r2, #13
    blo media_count_short
    mov r1, #0
media_count_len:
    ldrb r2, [r0, r1]
    cmp r2, #0
    addne r1, r1, #1
    bne media_count_len
    mov r2, #0
media_count_suffix:
    ldrb r3, [r7, r2]
    cmp r3, #0
    subne r1, r1, #1
    addne r2, r2, #1
    bne media_count_suffix
    mov r3, r1
    cmp r1, #SCRIPT_MEDIA_NAME_MAX
    movhi r3, #SCRIPT_MEDIA_NAME_MAX-2
    movhi r1, #SCRIPT_MEDIA_NAME_MAX
    strb r1, [r6, #MEDIA_ENTRY_LEN]
    add r12, r6, #MEDIA_ENTRY_NAME
    mov r2, #0
media_count_name:
    cmp r2, r1
    bhs media_count_named
    cmp r2, r3
    ldrblo r14, [r0, r2]
    movhs r14, #0x2E
    cmp r14, #0x80
    movhs r14, #0x3F
    strb r14, [r12, r2]
    add r2, r2, #1
    b media_count_name
media_count_named:
    add r5, r5, #1
    add r6, r6, #SCRIPT_MEDIA_ENTRY_BYTES
    b media_count_next
media_count_close:
    ldr r0, =LIST_DIR
    ldr r12, =FS_CLOSEDIR
    blx r12
    add r0, r8, #MS_COUNT
    strb r5, [r0, r4]
    mov r9, r5
media_count_out:
    mov r0, r9
    mov r1, #ERR_OK
    pop {r4-r9, pc}

; r0 kind, r1 place -> r0 the list entry of that file, 0 when the last count of that kind did not list it. Clobbers r1 to r2.
media_entry:
    ldr r2, =MEDIA_STATE+MS_COUNT
    ldrb r2, [r2, r0]
    cmp r2, #SCRIPT_MEDIA_MAX_FILES
    movhi r2, #0
    cmp r1, r2
    movhs r0, #0
    bxhs lr
    ldr r2, =MEDIA_LIST
    add r2, r2, r1, lsl #5
    mov r1, #MEDIA_KIND_BYTES
    mla r0, r1, r0, r2
    bx lr

; r0 array handle, r1 kind, r2 place -> r0 the length of the name (one character to a slot, then a 0 where there is room), 0 when
; the place is not listed.
script_file_name_glue:
    push {r4, lr}
    mov r4, r0
    mov r0, r1
    mov r1, r2
    bl media_entry
    cmp r0, #0
    beq media_name_out
    ldr r1, =HOOK_RUNTIME
    ldr r1, [r1, #RT_ENTRY]
    ldr r1, [r1, #SCRIPT_ENTRY_VARS]
    mov r2, r4, lsl #16
    add r1, r1, r2, lsr #14
    mov r4, r4, lsr #16
    ldrb r3, [r0, #MEDIA_ENTRY_LEN]
    add r0, r0, #MEDIA_ENTRY_NAME
    mov r2, #0
media_name_copy:
    cmp r2, r4
    bhs media_name_done
    cmp r2, r3
    bhi media_name_done
    ldrblo r12, [r0, r2]
    movhs r12, #0
    str r12, [r1, r2, lsl #2]
    add r2, r2, #1
    b media_name_copy
media_name_done:
    mov r0, r3
media_name_out:
    mov r1, #ERR_OK
    pop {r4, pc}

; r0 array handle (at least SCRIPT_MEDIA_PICTURE_BYTES slots), r1 kind, r2 place, r3 picture -> r0 the pictures of the file,
; 0 past the last (the array stays), -1 when the place is not listed, the file is missing or none of its kind, or not the
; main screen. The picture goes to the array one byte to a slot, in the layout of korg.display.bitmap(array, 0, 0, 128).
script_file_picture_glue:
    mov r12, r0, lsr #16
    cmp r12, #SCRIPT_MEDIA_PICTURE_BYTES
    blo media_bad_arg
    push {r4-r11, lr}
    sub sp, sp, #48
    ldr r4, =HOOK_RUNTIME
    ldr r4, [r4, #RT_ENTRY]
    ldr r4, [r4, #SCRIPT_ENTRY_VARS]
    mov r12, r0, lsl #16
    add r4, r4, r12, lsr #14
    mov r5, r1
    mov r6, r2
    mov r7, r3
    mvn r9, #0
    ldr r8, =MEDIA_STATE
    bl media_screen
    bne media_picture_out
    mov r0, r5
    mov r1, r6
    bl media_entry
    cmp r0, #0
    beq media_picture_out
    mov r10, r0
    ldr r1, =media_prefix
    mov r2, #0
media_picture_path:
    ldrb r3, [r1, r2]
    strb r3, [sp, r2]
    add r2, r2, #1
    cmp r2, #MEDIA_PREFIX_LEN
    blo media_picture_path
    add r1, sp, #MEDIA_PREFIX_LEN
    mov r2, #0
media_picture_short:
    ldrb r3, [r10, r2]
    strb r3, [r1, r2]
    add r2, r2, #1
    cmp r2, #13
    blo media_picture_short
    mov r0, #0
    strb r0, [r1, r2]
    mov r0, #0
    str r0, [r8, #MS_RD+MD_LEN]
    str r0, [r8, #MS_TD+MD_LEN]
    ldr r0, =MEDIA_BUF
    str r0, [r8, #MS_RD+MD_BUF]
    mov r0, #MEDIA_BUF_BYTES
    str r0, [r8, #MS_RD+MD_CAP]
    ldr r0, =MEDIA_TBUF
    str r0, [r8, #MS_TD+MD_BUF]
    mov r0, #MEDIA_TBUF_BYTES
    str r0, [r8, #MS_TD+MD_CAP]
    ldr r0, =HOOK_CARD+CARD_FIL
    mov r1, sp
    mov r2, #1
    ldr r12, =FS_OPEN
    blx r12
    cmp r0, #0
    bne media_picture_out
    cmp r5, #0
    bne media_picture_blla
    bl media_bmp
    b media_picture_close
media_picture_blla:
    ldr r0, [r8, #MS_KEY]
    cmp r0, r6
    beq media_blla_checked
    mvn r0, #0
    str r0, [r8, #MS_KEY]
    str r0, [r8, #MS_BUILT]
    bl blla_check
    cmp r0, #0
    bne media_picture_close
    str r6, [r8, #MS_KEY]
media_blla_checked:
    ldr r0, [r8, #MS_N]
    ldr r1, [r8, #MS_M]
    add r10, r0, r1
    cmp r7, r10
    movhs r9, #0
    bhs media_picture_close
    cmp r7, r0
    movlo r0, r7
    ldrhs r0, [r8, #MS_BASE]
    bl blla_progress
    cmp r0, #0
    bne media_blla_broken
    bl media_reversed
    eor r2, r0, #0xFF           ; the file's bits are lit, not drawn: turned unless the display is reversed
    ldr r0, =MEDIA_WORK
    mov r1, #0
media_blla_spread:
    ldrb r3, [r0, r1]
    eor r3, r3, r2
    str r3, [r4, r1, lsl #2]
    add r1, r1, #1
    cmp r1, #SCRIPT_MEDIA_PICTURE_BYTES
    blo media_blla_spread
    ldr r0, [r8, #MS_N]
    cmp r7, r0
    blo media_blla_done
    sub r0, r7, #1
    mov r1, r4
    orr r2, r2, #0x100
    bl blla_apply
    cmp r0, #0
    bne media_blla_broken
media_blla_done:
    mov r9, r10
    b media_picture_close
media_blla_broken:
    mvn r0, #0
    str r0, [r8, #MS_KEY]
    str r0, [r8, #MS_BUILT]
media_picture_close:
    ldr r0, =HOOK_CARD+CARD_FIL
    ldr r12, =FS_CLOSE
    blx r12
media_picture_out:
    mov r0, r9
    mov r1, #ERR_OK
    add sp, sp, #48
    pop {r4-r11, pc}
media_bad_arg:
    mov r0, #0
    mov r1, #ERR_API_ARG
    bx lr

; r0 file position, r1 bytes needed (at most the buffer), r2 a reader (MS_RD, MS_TD) -> r0 those bytes in its buffer, 0 when the
; file has fewer or cannot be read. Reads the buffer full from the position when it does not hold them. Clobbers r1 to r3, r12.
media_get:
    push {r4-r6, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    ldr r0, [r6, #MD_AT]
    ldr r1, [r6, #MD_LEN]
    subs r2, r4, r0
    blo media_get_fill
    add r3, r2, r5
    cmp r3, r1
    bhi media_get_fill
    ldr r0, [r6, #MD_BUF]
    add r0, r0, r2
    pop {r4-r6, pc}
media_get_fill:
    str r4, [r6, #MD_AT]
    mov r0, #0
    str r0, [r6, #MD_LEN]
    ldr r0, =HOOK_CARD+CARD_FIL
    mov r1, r4
    ldr r12, =FS_LSEEK
    blx r12
    cmp r0, #0
    bne media_get_fail
    ldr r0, =HOOK_CARD+CARD_FIL
    ldr r1, [r6, #MD_BUF]
    ldr r2, [r6, #MD_CAP]
    ldr r3, =HOOK_CARD+CARD_BR
    ldr r12, =FS_READ
    blx r12
    cmp r0, #0
    bne media_get_fail
    ldr r1, =HOOK_CARD+CARD_BR
    ldr r1, [r1]
    str r1, [r6, #MD_LEN]
    cmp r5, r1
    bhi media_get_fail
    ldr r0, [r6, #MD_BUF]
    pop {r4-r6, pc}
media_get_fail:
    mov r0, #0
    pop {r4-r6, pc}

; r0 file position, r2 a reader -> r0 the 16-bit word there, -1 when it cannot be read. Clobbers r1 to r3, r12.
media_u16:
    push {lr}
    mov r1, #2
    bl media_get
    cmp r0, #0
    mvneq r0, #0
    popeq {pc}
    ldrb r1, [r0, #1]
    ldrb r0, [r0]
    orr r0, r0, r1, lsl #8
    pop {pc}

; r0 a pointer -> r0 the little endian word there, read by bytes (a header field need not be aligned). Clobbers r1, r2.
media_le32:
    mov r1, r0
    ldrb r0, [r1]
    ldrb r2, [r1, #1]
    orr r0, r0, r2, lsl #8
    ldrb r2, [r1, #2]
    orr r0, r0, r2, lsl #16
    ldrb r2, [r1, #3]
    orr r0, r0, r2, lsl #24
    bx lr

; The open file is a .bmp, r7 the picture asked for: its picture into the array at r4 -> r9 1, 0 when r7 is not 0 (the array
; stays), or r9 as it was (-1) when it is none of the kind. The checks
; are decodeBmp's (src/splash-bmp.mjs): "BM", width 128, height 64 (rows from the bottom) or -64 (from the top), one plane, 1 bit,
; no compression, the palette before the pixels, the pixels from byte 54 to 0x200 and all 1024 bytes of them in the file. The
; darker palette entry is drawn. The pixels go through MEDIA_WORK, so the built .blla picture there is gone.
media_bmp:
    push {r4-r11, lr}
    mvn r0, #0
    str r0, [r8, #MS_BUILT]
    mov r0, #0
    mov r1, #54
    add r2, r8, #MS_RD
    bl media_get
    cmp r0, #0
    beq media_bmp_out
    mov r10, r0
    ldrb r1, [r10]
    ldrb r2, [r10, #1]
    cmp r1, #0x42
    cmpeq r2, #0x4D
    bne media_bmp_out
    add r0, r10, #18
    bl media_le32
    cmp r0, #128
    bne media_bmp_out
    add r0, r10, #22
    bl media_le32
    mov r11, #0
    cmp r0, #64
    beq media_bmp_height
    cmn r0, #64
    bne media_bmp_out
    mov r11, #1
media_bmp_height:
    add r0, r10, #28
    bl media_le32
    cmp r0, #1
    bne media_bmp_out
    ldrb r1, [r10, #32]
    ldrb r2, [r10, #33]
    orrs r1, r1, r2
    bne media_bmp_out
    ldrb r1, [r10, #26]
    cmp r1, #1
    bne media_bmp_out
    add r0, r10, #14
    bl media_le32
    mov r5, r0
    add r0, r10, #10
    bl media_le32
    mov r6, r0
    cmp r6, #54
    blo media_bmp_out
    cmp r6, #0x200
    bhi media_bmp_out
    sub r0, r6, #22             ; info + 22 > off without the sum, which could wrap in 32 bits
    cmp r5, r0
    bhi media_bmp_out
    add r0, r5, #14
    mov r1, #8
    add r2, r8, #MS_RD
    bl media_get
    cmp r0, #0
    beq media_bmp_out
    ldrb r1, [r0]
    ldrb r2, [r0, #1]
    add r1, r1, r2
    ldrb r2, [r0, #2]
    add r5, r1, r2
    ldrb r1, [r0, #4]
    ldrb r2, [r0, #5]
    add r1, r1, r2
    ldrb r2, [r0, #6]
    add r1, r1, r2
    cmp r1, r5
    movlo r7, #0
    movhs r7, #0xFF
    bl media_reversed
    eor r7, r7, r0
    ldr r0, =HOOK_CARD+CARD_FIL
    mov r1, r6
    ldr r12, =FS_LSEEK
    blx r12
    cmp r0, #0
    bne media_bmp_out
    ldr r0, =HOOK_CARD+CARD_FIL
    ldr r1, =MEDIA_WORK
    mov r2, #SCRIPT_MEDIA_PICTURE_BYTES
    ldr r3, =HOOK_CARD+CARD_BR
    ldr r12, =FS_READ
    blx r12
    cmp r0, #0
    bne media_bmp_out
    ldr r0, =HOOK_CARD+CARD_BR
    ldr r0, [r0]
    cmp r0, #SCRIPT_MEDIA_PICTURE_BYTES
    bne media_bmp_out
    ldr r0, [sp, #12]           ; the picture asked for (r7 of the caller): past the one there is, the array stays
    cmp r0, #0
    movne r9, #0
    bne media_bmp_out
    ldr r5, =MEDIA_WORK
    mov r6, #0                  ; the slot: page in bits 7 to 9, x in bits 0 to 6
media_bmp_slot:
    and r1, r6, #127
    add r2, r5, r1, lsr #3      ; the byte of column x in row 0
    and r1, r1, #7
    rsb r1, r1, #7              ; its bit
    mov r3, r6, lsr #7
    mov r3, r3, lsl #3          ; the slot's first row
    mov r0, #0
    mov r12, #7
media_bmp_bit:
    add r14, r3, r12            ; row y = page * 8 + bit
    cmp r11, #0
    rsbeq r14, r14, #63         ; rows from the bottom
    ldrb r14, [r2, r14, lsl #4]
    mov r14, r14, lsr r1
    and r14, r14, #1
    orr r0, r14, r0, lsl #1
    subs r12, r12, #1
    bpl media_bmp_bit
    eor r0, r0, r7
    str r0, [r4, r6, lsl #2]
    add r6, r6, #1
    cmp r6, #SCRIPT_MEDIA_PICTURE_BYTES
    blo media_bmp_slot
    mov r9, #1
media_bmp_out:
    mov r0, r9
    pop {r4-r11, lr}
    mov r9, r0
    bx lr

; The open file is a .blla: checks it as validateAnimation (src/loading-anim.mjs) does, every list of it, and keeps its header in
; MEDIA_STATE -> r0 0 when it is good. Clobbers r1 to r3, r12.
blla_check:
    push {r4-r11, lr}
    mov r0, #0
    mov r1, #BLLA_HEADER
    add r2, r8, #MS_RD
    bl media_get
    cmp r0, #0
    beq blla_bad
    ldr r1, [r0]
    ldr r2, =BLLA_MAGIC
    cmp r1, r2
    bne blla_bad
    ldrb r1, [r0, #4]
    cmp r1, #1
    bne blla_bad
    ldrb r9, [r0, #5]
    cmp r9, #BLLA_LOOP_MAX
    bhi blla_bad
    ldrb r4, [r0, #6]
    ldrb r1, [r0, #7]
    orr r4, r4, r1, lsl #8      ; N
    ldrb r5, [r0, #8]
    ldrb r1, [r0, #9]
    orr r5, r5, r1, lsl #8      ; M
    ldrb r6, [r0, #10]
    ldrb r1, [r0, #11]
    orr r6, r6, r1, lsl #8      ; the list table
    ldrb r7, [r0, #12]
    ldrb r1, [r0, #13]
    orr r7, r7, r1, lsl #8      ; the size
    cmp r7, #BLLA_MAX_BYTES
    bhi blla_bad
    sub r0, r7, #1
    mov r1, #1
    add r2, r8, #MS_RD
    bl media_get                ; the file holds its size
    cmp r0, #0
    beq blla_bad
    cmp r4, #0
    beq blla_bad
    sub r10, r4, #1
    add r10, r10, r5            ; the lists
    cmp r6, #BLLA_HEADER+SCRIPT_MEDIA_PICTURE_BYTES
    blo blla_bad
    add r0, r6, r10, lsl #1
    cmp r0, r7
    bhi blla_bad
    str r4, [r8, #MS_N]
    str r5, [r8, #MS_M]
    str r6, [r8, #MS_TABLE]
    str r7, [r8, #MS_SIZE]
    sub r0, r4, #1
    mul r0, r9, r0
    mov r1, #100
    bl glide_divide
    str r0, [r8, #MS_BASE]
    mov r11, #0
blla_check_list:
    cmp r11, r10
    bhs blla_good
    add r0, r6, r11, lsl #1
    add r2, r8, #MS_TD
    bl media_u16
    cmn r0, #1
    beq blla_bad
    mov r4, r0                  ; p
    add r0, r4, #2
    cmp r0, r7
    bhi blla_bad
    mov r0, r4
    add r2, r8, #MS_RD
    bl media_u16
    cmn r0, #1
    beq blla_bad
    mov r5, r0                  ; runs
    add r4, r4, #2
blla_check_run:
    subs r5, r5, #1
    blo blla_check_listed
    add r0, r4, #2
    cmp r0, r7
    bhi blla_bad
    mov r0, r4
    add r2, r8, #MS_RD
    bl media_u16
    cmn r0, #1
    beq blla_bad
    mov r1, r0, lsl #22
    mov r1, r1, lsr #22         ; the offset
    mov r0, r0, lsr #10
    add r0, r0, #1              ; the length
    add r1, r1, r0
    cmp r1, #SCRIPT_MEDIA_PICTURE_BYTES
    bhi blla_bad
    add r4, r4, #2
    add r4, r4, r0
    cmp r4, r7
    bhi blla_bad
    b blla_check_run
blla_check_listed:
    add r11, r11, #1
    b blla_check_list
blla_good:
    mov r0, #0
    pop {r4-r11, pc}
blla_bad:
    mvn r0, #0
    pop {r4-r11, pc}

; r0 a progress picture of the checked .blla -> MEDIA_WORK holds it, r0 0; not 0 when the file cannot be read (MS_BUILT is then
; none). Goes on from the picture there when it is not past r0, else starts at picture 0. Clobbers r1 to r3, r12.
blla_progress:
    push {r4-r6, lr}
    mov r4, r0
    ldr r5, =MEDIA_STATE
    ldr r6, [r5, #MS_BUILT]
    cmp r6, r4
    bls blla_progress_next
    mvn r0, #0
    str r0, [r5, #MS_BUILT]
    ldr r0, =HOOK_CARD+CARD_FIL
    mov r1, #BLLA_HEADER
    ldr r12, =FS_LSEEK
    blx r12
    cmp r0, #0
    bne blla_progress_fail
    ldr r0, =HOOK_CARD+CARD_FIL
    ldr r1, =MEDIA_WORK
    mov r2, #SCRIPT_MEDIA_PICTURE_BYTES
    ldr r3, =HOOK_CARD+CARD_BR
    ldr r12, =FS_READ
    blx r12
    cmp r0, #0
    bne blla_progress_fail
    ldr r0, =HOOK_CARD+CARD_BR
    ldr r0, [r0]
    cmp r0, #SCRIPT_MEDIA_PICTURE_BYTES
    bne blla_progress_fail
    mov r6, #0
    str r6, [r5, #MS_BUILT]
blla_progress_next:
    cmp r6, r4
    moveq r0, #0
    popeq {r4-r6, pc}
    mov r0, r6
    ldr r1, =MEDIA_WORK
    mov r2, #0
    bl blla_apply
    cmp r0, #0
    bne blla_progress_fail
    add r6, r6, #1
    str r6, [r5, #MS_BUILT]
    b blla_progress_next
blla_progress_fail:
    mvn r0, #0
    str r0, [r5, #MS_BUILT]
    pop {r4-r6, pc}

; r0 a list of the checked .blla (0 to N - 2 the progress pictures 1 to N - 1, then the loop pictures), r1 the picture, r2 0 for
; bytes (MEDIA_WORK), 0x100 plus a mask for the slots of an array, each byte turned by the mask -> r0 0 when it is written, not 0
; when the file cannot be read or a run would leave the picture or the file. Clobbers r1 to r3, r12.
blla_apply:
    push {r4-r11, lr}
    mov r4, r1
    mov r5, r2
    ldr r8, =MEDIA_STATE
    ldr r1, [r8, #MS_TABLE]
    add r0, r1, r0, lsl #1
    add r2, r8, #MS_TD
    bl media_u16
    cmn r0, #1
    beq blla_apply_bad
    mov r7, r0                  ; p
    ldr r10, [r8, #MS_SIZE]
    add r0, r7, #2
    cmp r0, r10
    bhi blla_apply_bad
    mov r0, r7
    add r2, r8, #MS_RD
    bl media_u16
    cmn r0, #1
    beq blla_apply_bad
    mov r6, r0                  ; runs
    add r7, r7, #2
blla_apply_run:
    subs r6, r6, #1
    blo blla_apply_done
    add r0, r7, #2
    cmp r0, r10
    bhi blla_apply_bad
    mov r0, r7
    add r2, r8, #MS_RD
    bl media_u16
    cmn r0, #1
    beq blla_apply_bad
    mov r9, r0, lsl #22
    mov r9, r9, lsr #22         ; the offset
    mov r11, r0, lsr #10
    add r11, r11, #1            ; the length
    add r0, r9, r11
    cmp r0, #SCRIPT_MEDIA_PICTURE_BYTES
    bhi blla_apply_bad
    add r0, r7, #2
    add r0, r0, r11
    cmp r0, r10
    bhi blla_apply_bad
    mov r0, r7
    add r1, r11, #2
    add r2, r8, #MS_RD
    bl media_get
    cmp r0, #0
    beq blla_apply_bad
    add r0, r0, #2
    mov r1, #0
    and r2, r5, #0xFF
blla_apply_copy:
    ldrb r3, [r0, r1]
    add r12, r9, r1
    cmp r5, #0
    strbeq r3, [r4, r12]
    eorne r3, r3, r2
    strne r3, [r4, r12, lsl #2]
    add r1, r1, #1
    cmp r1, r11
    blo blla_apply_copy
    add r7, r7, #2
    add r7, r7, r11
    b blla_apply_run
blla_apply_done:
    mov r0, #0
    pop {r4-r11, pc}
blla_apply_bad:
    mvn r0, #0
    pop {r4-r11, pc}

;  The card reads of the plugin API (CARD_READS in data/script/contract.mjs) go through card_timed: the clock of the frame
; budget stops while the glue runs, so a read of the card does not count against SCRIPT_FRAME_TICKS nor the handler's ticks.
script_file_frame_timed:
    ldr r12, =script_file_frame_glue
    b card_timed
script_file_read_timed:
    ldr r12, =script_file_read_glue
    b card_timed
script_file_write_timed:
    ldr r12, =script_file_write_glue
    b card_timed
script_file_count_timed:
    ldr r12, =script_file_count_glue
    b card_timed
script_file_name_timed:
    ldr r12, =script_file_name_glue
    b card_timed
script_file_picture_timed:
    ldr r12, =script_file_picture_glue
    b card_timed

; r0 to r3 the arguments, r12 the glue -> what the glue returns (r0, r1). The ticks it took move RT_FRAME_START and RT_STARTED
; forward, up to SCRIPT_CARD_TICKS in one frame (CARD_CLOCK, set to 0 at the start of each frame); beyond that the time counts,
; so a card that answers slowly ends in TIME instead of holding every frame.
card_timed:
    push {r4-r6, lr}
    ldr r4, =SCRIPT_TIMER_ADDRESS
    ldr r5, [r4]
    blx r12
    push {r0, r1}
    ldr r0, [r4]
    cmp r0, r5
    sub r0, r0, r5
    ldrlo r1, =SCRIPT_TIMER_PERIOD
    addlo r0, r0, r1
    ldr r6, =CARD_CLOCK
    ldr r1, [r6]
    ldr r2, =SCRIPT_CARD_TICKS
    cmp r1, r2
    bhs card_timed_done
    sub r2, r2, r1
    cmp r0, r2
    movhi r0, r2
    add r1, r1, r0
    str r1, [r6]
    ldr r6, =HOOK_RUNTIME
    ldr r3, =SCRIPT_TIMER_PERIOD
    ldr r1, [r6, #RT_FRAME_START]
    add r1, r1, r0
    cmp r1, r3
    subhs r1, r1, r3
    str r1, [r6, #RT_FRAME_START]
    ldr r1, [r6, #RT_STARTED]
    add r1, r1, r0
    cmp r1, r3
    subhs r1, r1, r3
    str r1, [r6, #RT_STARTED]
card_timed_done:
    pop {r0, r1}
    pop {r4-r6, pc}
.pool

media_folder:
    .asciz "SD:KORG/blechtribe/Media"
media_prefix:
    .asciz "SD:KORG/blechtribe/Media/"
media_str_blla:
    .asciz ".blla"
.align 4
.pool
