; The collection of presets and modulation types on the card, SD:KORG/blechtribe/Presets/e2sFx.all (src/fx-collection.mjs).
; Runs at power-on right after the plugin loader. Two passes over the file: the first checks every byte (header,
; build, each entry, length, CRC-32) and writes nothing; only a file that passed is read again and its records go
; into RAM, where the firmware's getters find them. Nothing is written to the flash. No card, no file, a broken file
; or EXIT held at power-on: the presets of the firmware stay.
.equ FX_GET_IFX, 0xC003E738
.equ FX_GET_MFX, 0xC003E750
.equ FX_COUNT_IFX, 0xC003EFDC
.equ FX_COUNT_MFX, 0xC003EFE4
.equ FX_MAGIC, 0x41584647
.equ FX_HEADER, 24
.equ FX_HEAD, 8
.equ FX_RECORD, 0x20C
.equ FX_MOD_RECORD, 0x58
.equ FX_MOD_COUNT, 72
.equ FX_MAX_TEXT, 0x2000
.equ FX_BUF, 16
; state at the end of the card work area: what the last start did, for the checks and the editor
.equ FX_STATE_AT, 0xFE0
.equ FX_STATUS, 0
.equ FX_LOADED, 4
.equ FX_TOTAL, 8
.equ FX_WANT, 12
.equ FX_USED, 16
.equ FX_KIND, 20
.equ FX_INDEX, 24
.equ FX_SIZE, 28
.equ FX_RUN, 1
.equ FX_OK, 2
.equ FX_NO_PANEL, 3
.equ FX_KILLED, 4
.equ FX_NO_FILE, 5
.equ FX_BAD_HEADER, 6
.equ FX_BAD_BUILD, 7
.equ FX_BAD_ENTRY, 8
.equ FX_BAD_CHECKSUM, 9
.equ FX_READ_ERROR, 10

fx_card_load:
    push {r4-r11, lr}
    ldr r5, =HOOK_CARD
    add r6, r5, #CARD_FIL
    ldr r9, =HOOK_INPUT
    add r4, r5, #FX_STATE_AT
    mov r0, #FX_RUN
    str r0, [r4, #FX_STATUS]
    mov r8, #0
    str r8, [r4, #FX_LOADED]
    str r8, [r5, #CARD_OPEN]
    ldr r0, =PANEL
    ldr r0, [r0]
    cmp r0, #0
    beq fx_no_panel
    cmn r0, #1
    beq fx_no_panel
    ldr r0, [r0, #0x18]
    tst r0, #KILL_MASK
    bne fx_killed
    mov r10, #0
fx_pass:
    mov r0, r6
    ldr r1, =fx_path
    mov r2, #1
    ldr r12, =FS_OPEN
    blx r12
    cmp r0, #0
    bne fx_no_file
    mov r0, #1
    str r0, [r5, #CARD_OPEN]
    mov r0, r9
    mov r1, #FX_HEADER
    bl card_read
    cmp r0, #0
    bne fx_read_error
    ldr r0, [r9]
    ldr r1, =FX_MAGIC
    cmp r0, r1
    bne fx_bad_header
    ldrb r0, [r9, #4]
    ldrb r1, [r9, #5]
    orr r0, r0, r1, lsl #8
    cmp r0, #1
    bne fx_bad_header
    ldr r0, [r9, #16]
    cmp r0, #FX_BUILD
    bne fx_bad_build
    ldrb r7, [r9, #6]
    ldrb r1, [r9, #7]
    orr r7, r7, r1, lsl #8
    ldr r0, [r9, #8]
    str r0, [r4, #FX_TOTAL]
    ldr r0, [r9, #12]
    str r0, [r4, #FX_WANT]
    mvn r0, #0
    str r0, [r5, #CARD_CRC]
    mov r0, #FX_HEADER
    str r0, [r4, #FX_USED]
fx_entry:
    cmp r7, #0
    beq fx_entries_done
    sub r7, r7, #1
    mov r0, r9
    mov r1, #FX_HEAD
    bl card_read
    cmp r0, #0
    bne fx_read_error
    mov r0, r9
    mov r1, #FX_HEAD
    bl card_crc
    ldrb r0, [r9]
    str r0, [r4, #FX_KIND]
    ldrb r0, [r9, #1]
    str r0, [r4, #FX_INDEX]
    ldrb r2, [r9, #2]
    ldrb r1, [r9, #3]
    orr r2, r2, r1, lsl #8
    ldrb r3, [r9, #4]
    ldrb r1, [r9, #5]
    orr r3, r3, r1, lsl #8
    ldr r1, =FX_MAX_TEXT
    cmp r2, r1
    bhi fx_bad_entry
    ldr r0, [r4, #FX_KIND]
    cmp r0, #3
    beq fx_entry_mod
    cmp r0, #1
    blo fx_bad_entry
    cmp r0, #2
    bhi fx_bad_entry
    ldr r1, =FX_RECORD
    cmp r3, r1
    bne fx_bad_entry
    add r11, r2, r3
    cmp r0, #1
    ldreq r12, =FX_COUNT_IFX
    ldrne r12, =FX_COUNT_MFX
    blx r12
    ldr r1, [r4, #FX_INDEX]
    cmp r1, r0
    bhs fx_bad_entry
    b fx_entry_size
fx_entry_mod:
    cmp r3, #FX_MOD_RECORD
    bne fx_bad_entry
    ldr r1, [r4, #FX_INDEX]
    cmp r1, #FX_MOD_COUNT
    bhs fx_bad_entry
    add r11, r2, r3
fx_entry_size:
    add r11, r11, #FX_HEAD+3
    bic r11, r11, #3
    ldr r0, [r4, #FX_USED]
    add r0, r0, r11
    ldr r1, [r4, #FX_TOTAL]
    cmp r0, r1
    bhi fx_bad_entry
    str r0, [r4, #FX_USED]
    sub r11, r11, #FX_HEAD
    str r11, [r4, #FX_SIZE]
    add r0, r9, #FX_BUF
    mov r1, r11
    bl card_read
    cmp r0, #0
    bne fx_read_error
    cmp r10, #0
    bne fx_apply
    add r0, r9, #FX_BUF
    ldr r1, [r4, #FX_SIZE]
    bl card_crc
    b fx_entry
; the second pass: the record goes where the firmware's getter points, a modulation type into the table this build reads
fx_apply:
    ldr r1, [r4, #FX_KIND]
    ldr r0, [r4, #FX_INDEX]
    cmp r1, #3
    beq fx_apply_mod
    cmp r1, #1
    ldreq r12, =FX_GET_IFX
    ldrne r12, =FX_GET_MFX
    blx r12
    ldr r2, =FX_RECORD
    b fx_copy
fx_apply_mod:
    mov r1, #FX_MOD_RECORD
    mul r2, r0, r1
    ldr r0, =FX_MODS
    add r0, r0, r2
    mov r2, #FX_MOD_RECORD
fx_copy:
    add r1, r9, #FX_BUF
fx_copy_byte:
    ldrb r3, [r1], #1
    strb r3, [r0], #1
    subs r2, r2, #1
    bne fx_copy_byte
    add r8, r8, #1
    b fx_entry
fx_entries_done:
    ldr r0, [r4, #FX_USED]
    ldr r1, [r4, #FX_TOTAL]
    cmp r0, r1
    bne fx_bad_header
    bl card_close
    cmp r10, #0
    bne fx_done_ok
    ldr r0, [r5, #CARD_CRC]
    mvn r0, r0
    ldr r1, [r4, #FX_WANT]
    cmp r0, r1
    bne fx_bad_checksum
    mov r10, #1
    b fx_pass
fx_done_ok:
    mov r0, #FX_OK
    b fx_status
fx_no_panel:
    mov r0, #FX_NO_PANEL
    b fx_status
fx_killed:
    mov r0, #FX_KILLED
    b fx_status
fx_no_file:
    mov r0, #FX_NO_FILE
    b fx_status
fx_bad_header:
    mov r0, #FX_BAD_HEADER
    b fx_status
fx_bad_build:
    mov r0, #FX_BAD_BUILD
    b fx_status
fx_bad_entry:
    mov r0, #FX_BAD_ENTRY
    b fx_status
fx_bad_checksum:
    mov r0, #FX_BAD_CHECKSUM
    b fx_status
fx_read_error:
    mov r0, #FX_READ_ERROR
fx_status:
    str r0, [r4, #FX_STATUS]
    str r8, [r4, #FX_LOADED]
    ldr r0, [r5, #CARD_OPEN]
    cmp r0, #0
    blne card_close
    pop {r4-r11, pc}
.pool
fx_path:
    .asciz "SD:KORG/blechtribe/Presets/e2sFx.all"
.align 4
fx_card_load_end:

; EXPORT ALL EFFECTS (DATA UTILITY, script_menu.s): the collection on the card gets the records the firmware holds in RAM now,
; each entry where it is, with its header and its .e2fx text as they are (the text is what the editor reads back; an entry
; without text is left as it is), and the header's CRC-32 again. Only the file that was loaded at power-on: its CRC still has
; to be the one the loader read (FX_WANT), else the RAM does not belong to that file and nothing is written. A first pass
; checks every entry as the loader does, the second writes. -> M_STATUS 0x53 written, 0x52 no file, 0x54 not the loaded file
; or not one the loader takes, 0x20 + the FatFs code of a failing call.
.equ FX_OPEN_RW, 3              ; FA_READ | FA_WRITE, the file has to be there
.equ FX_CHUNK, 0x400
menu_export_fx:
    push {r4-r11, lr}
    ldr r5, =HOOK_CARD
    add r6, r5, #CARD_FIL
    ldr r9, =HOOK_INPUT
    add r4, r5, #FX_STATE_AT
    ldr r0, [r4, #FX_STATUS]
    cmp r0, #FX_OK
    movne r0, #0x52
    bne fx_export_status
    mov r0, r6
    ldr r1, =fx_path
    mov r2, #FX_OPEN_RW
    ldr r12, =FS_OPEN
    blx r12
    cmp r0, #4                  ; FR_NO_FILE
    cmpne r0, #FR_NO_PATH
    moveq r0, #0x52
    beq fx_export_status
    cmp r0, #0
    addne r0, r0, #0x20
    bne fx_export_status
    mov r8, #0                  ; pass: 0 checks, 1 writes
fx_export_pass:
    mov r0, r6
    mov r1, #0
    ldr r12, =FS_LSEEK
    blx r12
    cmp r0, #0
    bne fx_export_fail
    mov r0, r9
    mov r1, #FX_HEADER
    bl card_read
    cmp r0, #0
    bne fx_export_bad
    ldr r0, [r9]
    ldr r1, =FX_MAGIC
    cmp r0, r1
    bne fx_export_bad
    ldrb r0, [r9, #4]
    ldrb r1, [r9, #5]
    orr r0, r0, r1, lsl #8
    cmp r0, #1
    bne fx_export_bad
    ldr r0, [r9, #16]
    cmp r0, #FX_BUILD
    bne fx_export_bad
    ldr r0, [r9, #12]
    ldr r1, [r4, #FX_WANT]
    cmp r0, r1
    bne fx_export_bad
    ldrb r7, [r9, #6]
    ldrb r1, [r9, #7]
    orr r7, r7, r1, lsl #8
    ldr r10, [r9, #8]
    mov r11, #FX_HEADER
fx_export_entry:
    cmp r7, #0
    beq fx_export_entries_done
    sub r7, r7, #1
    mov r0, r6
    mov r1, r11
    ldr r12, =FS_LSEEK
    blx r12
    cmp r0, #0
    bne fx_export_fail
    mov r0, r9
    mov r1, #FX_HEAD
    bl card_read
    cmp r0, #0
    bne fx_export_bad
    ldrb r0, [r9]
    ldrb r1, [r9, #1]
    ldrb r2, [r9, #2]
    ldrb r12, [r9, #3]
    orr r2, r2, r12, lsl #8
    ldrb r3, [r9, #4]
    ldrb r12, [r9, #5]
    orr r3, r3, r12, lsl #8
    str r2, [r4, #FX_SIZE]      ; the text's length, for the second pass
    ldr r12, =FX_MAX_TEXT
    cmp r2, r12
    bhi fx_export_bad
    cmp r0, #3
    beq fx_export_mod
    cmp r0, #1
    blo fx_export_bad
    cmp r0, #2
    bhi fx_export_bad
    ldr r12, =FX_RECORD
    cmp r3, r12
    bne fx_export_bad
    str r0, [r4, #FX_KIND]
    str r1, [r4, #FX_INDEX]
    add r2, r2, r3
    str r2, [r4, #FX_USED]
    cmp r0, #1
    ldreq r12, =FX_COUNT_IFX
    ldrne r12, =FX_COUNT_MFX
    blx r12
    ldr r1, [r4, #FX_INDEX]
    cmp r1, r0
    bhs fx_export_bad
    ldr r0, [r4, #FX_KIND]
    cmp r0, #1
    ldreq r12, =FX_GET_IFX
    ldrne r12, =FX_GET_MFX
    mov r0, r1
    blx r12
    ldr r2, [r4, #FX_USED]
    ldr r3, =FX_RECORD
    b fx_export_size
fx_export_mod:
    cmp r3, #FX_MOD_RECORD
    bne fx_export_bad
    cmp r1, #FX_MOD_COUNT
    bhs fx_export_bad
    add r2, r2, r3
    mov r0, #FX_MOD_RECORD
    mul r12, r1, r0
    ldr r0, =FX_MODS
    add r0, r0, r12
fx_export_size:                 ; r0 = the record in RAM, r2 = text + data, r3 = data
    add r2, r2, #FX_HEAD+3
    bic r2, r2, #3
    add r1, r11, r2
    cmp r1, r10
    bhi fx_export_bad
    cmp r8, #0
    beq fx_export_next
    ldr r12, [r4, #FX_SIZE]
    cmp r12, #0
    beq fx_export_next
    push {r0-r3}
    mov r0, r6
    add r1, r11, #FX_HEAD
    ldr r12, =FS_LSEEK
    blx r12
    mov r12, r0
    pop {r0-r3}
    cmp r12, #0
    movne r0, r12
    bne fx_export_fail
    mov r1, r0
    mov r0, r6
    push {r2, r3}
    mov r2, r3
    add r3, r5, #CARD_BR
    ldr r12, =FS_WRITE
    blx r12
    pop {r2, r3}
    cmp r0, #0
    bne fx_export_fail
    ldr r0, [r5, #CARD_BR]
    cmp r0, r3
    movne r0, #2
    bne fx_export_fail
fx_export_next:
    add r11, r11, r2
    b fx_export_entry
fx_export_entries_done:
    cmp r11, r10
    bne fx_export_bad
    cmp r8, #0
    moveq r8, #1
    beq fx_export_pass
    mov r0, r6                  ; the CRC-32 of everything behind the header, read back as it is now on the card
    mov r1, #FX_HEADER
    ldr r12, =FS_LSEEK
    blx r12
    cmp r0, #0
    bne fx_export_fail
    mvn r0, #0
    str r0, [r5, #CARD_CRC]
    sub r11, r10, #FX_HEADER
fx_export_crc:
    cmp r11, #0
    beq fx_export_crc_done
    mov r7, r11
    cmp r7, #FX_CHUNK
    movhi r7, #FX_CHUNK
    sub r11, r11, r7
    add r0, r9, #FX_BUF
    mov r1, r7
    bl card_read
    cmp r0, #0
    bne fx_export_bad
    add r0, r9, #FX_BUF
    mov r1, r7
    bl card_crc
    b fx_export_crc
fx_export_crc_done:
    ldr r0, [r5, #CARD_CRC]
    mvn r0, r0
    str r0, [r9]
    str r0, [r4, #FX_WANT]      ; the file on the card is still the one in RAM
    mov r0, r6
    mov r1, #12
    ldr r12, =FS_LSEEK
    blx r12
    cmp r0, #0
    bne fx_export_fail
    mov r0, r6
    mov r1, r9
    mov r2, #4
    add r3, r5, #CARD_BR
    ldr r12, =FS_WRITE
    blx r12
    cmp r0, #0
    bne fx_export_fail
    mov r0, r6
    ldr r12, =FS_CLOSE
    blx r12
    cmp r0, #0
    addne r0, r0, #0x20
    moveq r0, #0x53
    b fx_export_status
fx_export_bad:
    mov r0, #0x34               ; not the loaded file, or not one the loader takes (0x54 once 0x20 is added)
fx_export_fail:
    mov r7, r0
    mov r0, r6
    ldr r12, =FS_CLOSE
    blx r12
    add r0, r7, #0x20
fx_export_status:
    ldr r1, =MENU_STATE
    str r0, [r1, #M_STATUS]
    pop {r4-r11, pc}
.pool
