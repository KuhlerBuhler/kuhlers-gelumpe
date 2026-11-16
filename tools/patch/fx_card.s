; The collection of presets and modulation types on the card, SD:KORG/blechtribe/Presets/e2sFx.all (src/fx-collection.mjs).
; Runs at power-on right after the plugin loader. Two passes over the file: the first checks every byte (header,
; build, each entry, length, CRC-32) and writes nothing; only a file that passed is read again and its records go
; into RAM, where the firmware's getters find them. Nothing is written to the flash. No card, no file, a broken file
; or EXIT held at power-on: the presets of the firmware stay.
; An insert or master entry may name any slot up to 100, also one past the menu: with the preset tables each of the first
; 100 slots has a record of its own, so the menu grows in RAM to the highest slot the file fills (fx_grow). Never shorter.
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
.equ FX_SLOTS, 100              ; slots with a record of their own once the preset tables are in (preset_tables.py OLD_SLOTS)
.equ FX_CLAMP_IFX, 0xC003E73C   ; the getters' clamp, cmp r0, #127 with the preset tables
.equ FX_CLAMP_MFX, 0xC003E754
.equ FX_CMP_127, 0xE350007F
.equ FX_KNOB_RESET, 0xC00980AC  ; the insert knob memory: every part's row back to 0x40
.equ FX_KNOB_STORE, 0xC009816C  ; r0 part: its insert knob value into its row, at its insert type

; -> r1 = the text behind the firmware in BLECH > VERSION, what the start did with e2sFx.all; 0 when it found no file. Clobbers r2.
fx_status_text:
    ldr r1, =HOOK_CARD+FX_STATE_AT
    ldr r2, [r1, #FX_STATUS]
    mov r1, #0
    cmp r2, #FX_OK
    ldreq r1, =str_fx_loaded
    cmp r2, #FX_KILLED
    ldreq r1, =str_fx_skipped
    cmp r2, #FX_BAD_BUILD
    ldreq r1, =str_fx_build
    cmp r2, #FX_BAD_HEADER
    cmpne r2, #FX_BAD_ENTRY
    cmpne r2, #FX_BAD_CHECKSUM
    cmpne r2, #FX_READ_ERROR
    ldreq r1, =str_fx_tag_bad
    bx lr

fx_card_load:
    push {r4-r11, lr}
    mov r0, #0                  ; [sp] the insert slots the file fills, [sp, #4] the master slots
    push {r0}
    push {r0}
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
    blo fx_entry_slots
    cmp r1, #FX_SLOTS
    bhs fx_bad_entry
    bl fx_can_grow
    cmp r0, #0
    bne fx_bad_entry
    ldr r1, [r4, #FX_INDEX]
fx_entry_slots:
    ldr r0, [r4, #FX_KIND]
    sub r0, r0, #1
    add r1, r1, #1
    ldr r2, [sp, r0, lsl #2]
    cmp r1, r2
    strhi r1, [sp, r0, lsl #2]
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
    cmp r8, #0
    beq fx_done_status
    ldr r0, [sp]
    ldr r1, [sp, #4]
    bl fx_grow
    bl fx_reapply
fx_done_status:
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
    add sp, sp, #8
    pop {r4-r11, pc}
.pool

; The menu lengths, as the firmware has them in its code: the address (bit 1 set for the master menu, bit 0 for a site that
; holds the last index instead of the count) and the instruction without its low byte (docs/messungen/2026-09-14-fx-ram-write.md;
; 0xC0098084 is the row length of the knob memory, preset_tables.py). The same in Hacktribe's and Korg's build.
fx_sites:
    .word 0xC003EFDC, 0xE3A00000, 0xC0098150, 0xD3A03000, 0xC0098194, 0xE3A01000, 0xC00980EC, 0xD3A03000
    .word 0xC009809C, 0xE3530000, 0xC009811C, 0xE3A02000, 0xC0098138, 0xE3530000, 0xC0098084, 0xE3A02000
    .word 0xC0048F81, 0xE3500000, 0xC0049EF1, 0xE3520000, 0xC004A1F9, 0xE3520000, 0xC009814D, 0xD3510000
    .word 0xC0098189, 0xE3520000, 0xC00980E9, 0xE3550000, 0xC003EFE6, 0xE3A00000, 0

; -> r0 0 when the menus can grow past their length: the preset tables are in (both clamps 127) and every site of fx_sites
; holds the instruction and the length the firmware has. Anything else (another build, a firmware without the tables) and a
; slot past the menu stays refused.
fx_can_grow:
    push {r4-r6, lr}
    ldr r2, =FX_CMP_127
    ldr r1, =FX_CLAMP_IFX
    ldr r0, [r1]
    cmp r0, r2
    ldreq r1, =FX_CLAMP_MFX
    ldreq r0, [r1]
    cmpeq r0, r2
    bne fx_can_grow_no
    ldr r12, =FX_COUNT_IFX
    blx r12
    mov r5, r0
    ldr r12, =FX_COUNT_MFX
    blx r12
    mov r6, r0
    ldr r4, =fx_sites
fx_can_grow_site:
    ldr r0, [r4], #4
    cmp r0, #0
    beq fx_can_grow_yes
    ldr r1, [r4], #4
    tst r0, #2
    moveq r2, r5
    movne r2, r6
    tst r0, #1
    subne r2, r2, #1
    bic r0, r0, #3
    ldr r3, [r0]
    bic r12, r3, #0xFF
    cmp r12, r1
    bne fx_can_grow_no
    and r3, r3, #0xFF
    cmp r3, r2
    beq fx_can_grow_site
fx_can_grow_no:
    mov r0, #1
    pop {r4-r6, pc}
fx_can_grow_yes:
    mov r0, #0
    pop {r4-r6, pc}

; r0 the insert slots the file fills, r1 the master slots: a menu shorter than that gets that length at every site, in RAM
; only (gone at power-off, the next start reads the file again). The code changed is cleaned out of the data cache and the
; instruction cache cleared before the firmware runs it again; then every part's row of the insert knob memory, whose
; length is the menu's, is laid out again and gets the part's knob value back.
fx_grow:
    push {r4-r8, lr}
    mov r7, r0
    mov r8, r1
    ldr r12, =FX_COUNT_IFX
    blx r12
    cmp r7, r0
    movls r7, #0
    ldr r12, =FX_COUNT_MFX
    blx r12
    cmp r8, r0
    movls r8, #0
    orrs r0, r7, r8
    beq fx_grow_done
    bl fx_can_grow
    cmp r0, #0
    bne fx_grow_done
    ldr r4, =fx_sites
fx_grow_site:
    ldr r0, [r4], #8
    cmp r0, #0
    beq fx_grow_written
    tst r0, #2
    moveq r1, r7
    movne r1, r8
    cmp r1, #0
    beq fx_grow_site
    tst r0, #1
    subne r1, r1, #1
    bic r0, r0, #3
    strb r1, [r0]
    .word 0xEE070F3A            ; mcr p15, 0, r0, c7, c10, 1: clean the data cache line of r0
    b fx_grow_site
fx_grow_written:
    mov r0, #0
    .word 0xEE070F9A            ; mcr p15, 0, r0, c7, c10, 4: drain the write buffer
    .word 0xEE070F15            ; mcr p15, 0, r0, c7, c5, 0: clear the instruction cache
    cmp r7, #0
    beq fx_grow_done
    ldr r12, =FX_KNOB_RESET
    blx r12
    mov r5, #0
fx_grow_knob:
    mov r0, r5
    ldr r12, =FX_KNOB_STORE
    blx r12
    add r5, r5, #1
    cmp r5, #16
    blo fx_grow_knob
fx_grow_done:
    pop {r4-r8, pc}
.pool

; The pattern of the start set its effects before the loader ran, from the records of the firmware. Each type goes to the next
; one and back through the setter the device's own edit calls, with the report: a setter given the type it holds does nothing,
; and without the report nothing reaches the DSP (measured in the emulator). The master effect, then the insert of each part.
.equ FX_PART_IFX, 26            ; the part edit's number of the insert effect (docs/messungen/2026-11-03-live-schreibwege.md)
.equ FX_PART_SIZE, 0x330
fx_reapply:
    push {r4-r7, lr}
    ldr r12, =FX_COUNT_MFX
    blx r12
    mov r6, r0
    ldr r4, =SC_PATPTR
    ldr r4, [r4]
    ldrb r5, [r4, #4+61]
    add r1, r5, #1
    cmp r1, r6
    movhs r1, #0
    bl fx_set_mfx
    mov r1, r5
    bl fx_set_mfx
    ldr r12, =FX_COUNT_IFX
    blx r12
    mov r6, r0
    mov r7, #0
fx_reapply_part:
    mov r0, #FX_PART_SIZE
    mul r0, r7, r0
    add r0, r0, r4
    add r0, r0, #0x800
    ldrb r5, [r0, #4+33]
    add r1, r5, #1
    cmp r1, r6
    movhs r1, #0
    mov r0, r7
    bl fx_set_ifx
    mov r0, r7
    mov r1, r5
    bl fx_set_ifx
    add r7, r7, #1
    cmp r7, #16
    blo fx_reapply_part
    pop {r4-r7, pc}

; r1 the master effect's type, set with the report
fx_set_mfx:
    push {lr}
    ldr r0, =HW_PATTERN_OBJECT+PV_ARG_8
    mov r2, #1
    ldr r12, =PV_SET_8
    blx r12
    pop {pc}

; r0 part, r1 its insert effect's type, through the part edit the knobs call, with the report
fx_set_ifx:
    push {lr}
    sub sp, sp, #12
    str r1, [sp]
    mov r1, #1
    str r1, [sp, #4]
    orr r1, r0, #0x10
    ldr r0, =HW_PART_EDITOR
    ldr r0, [r0]
    mov r2, #0
    mov r3, #FX_PART_IFX
    ldr r12, =HW_PART_EDIT
    blx r12
    add sp, sp, #12
    pop {pc}
.pool
fx_path:
    .asciz "SD:KORG/blechtribe/Presets/e2sFx.all"
.align 4
fx_card_load_end:

; EXPORT ALL EFFECTS (DATA UTILITY, script_menu.s): the collection on the card gets the records the firmware holds in RAM now,
; each entry where it is, with its header and its .e2fx text as they are (the text is what the editor reads back; for an
; entry without text the page reads the record), and the header's CRC-32 again. Only the file that was loaded at power-on: its CRC still has
; to be the one the loader read (FX_WANT), else the RAM does not belong to that file and nothing is written. A first pass
; checks every entry as the loader does, the second writes. With no file on the card a new one is made (fx_export_new).
; -> M_STATUS 0x53 written, 0x54 not the loaded file or not one the loader takes, 0x20 + the FatFs code of a failing call.
.equ FX_OPEN_RW, 3              ; FA_READ | FA_WRITE, the file has to be there
.equ FX_CHUNK, 0x400
menu_export_fx:
    push {r4-r11, lr}
    ldr r5, =HOOK_CARD
    add r6, r5, #CARD_FIL
    ldr r9, =HOOK_INPUT
    add r4, r5, #FX_STATE_AT
    mov r0, r6
    ldr r1, =fx_path
    mov r2, #FX_OPEN_RW
    ldr r12, =FS_OPEN
    blx r12
    cmp r0, #4                  ; FR_NO_FILE
    cmpne r0, #FR_NO_PATH
    beq fx_export_new
    cmp r0, #0
    addne r0, r0, #0x20
    bne fx_export_status
    ldr r0, [r4, #FX_STATUS]    ; a file the start did not load (broken, another build, EXIT held) stays as it is
    cmp r0, #FX_OK
    movne r0, #0x34
    bne fx_export_fail
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

; No e2sFx.all on the card: a new one with every insert and master preset and every modulation type the firmware holds in
; RAM now, each entry without text (the page makes the text from the record), then the CRC-32 and the state of a file the
; start loaded, so the next export writes into it. A failing write removes the file again, the loader would refuse it.
fx_export_new:
    mov r0, r6
    ldr r1, =fx_path
    bl card_create              ; makes KORG/blechtribe/Presets on the way
    cmp r0, #0
    addne r0, r0, #0x20
    bne fx_export_status
    ldr r12, =FX_COUNT_IFX
    blx r12
    cmp r0, #256                ; the index of an entry is one byte
    movhi r0, #256
    mov r10, r0
    ldr r12, =FX_COUNT_MFX
    blx r12
    cmp r0, #256
    movhi r0, #256
    mov r11, r0
    add r0, r10, r11
    ldr r1, =FX_HEAD+FX_RECORD
    mul r2, r0, r1
    ldr r1, =FX_HEADER+FX_MOD_COUNT*(FX_HEAD+FX_MOD_RECORD)
    add r2, r2, r1
    ldr r0, =FX_MAGIC
    str r0, [r9]
    add r0, r10, r11
    add r0, r0, #FX_MOD_COUNT
    mov r0, r0, lsl #16
    orr r0, r0, #1              ; version 1, the count
    str r0, [r9, #4]
    str r2, [r9, #8]
    mov r0, #0
    str r0, [r9, #12]
    str r0, [r9, #20]
    mov r0, #FX_BUILD
    str r0, [r9, #16]
    mov r0, r9
    mov r1, #FX_HEADER
    bl fx_put
    cmp r0, #0
    bne fx_new_fail
    mvn r0, #0                  ; the CRC covers what follows the header
    str r0, [r5, #CARD_CRC]
    mov r7, #1                  ; kind: 1 insert, 2 master, 3 modulation
    mov r8, #0
fx_new_entry:
    cmp r7, #1
    moveq r0, r10
    cmp r7, #2
    moveq r0, r11
    cmp r7, #3
    moveq r0, #FX_MOD_COUNT
    cmp r8, r0
    bhs fx_new_kind_done
    orr r0, r7, r8, lsl #8      ; kind, index, text length 0
    str r0, [r9]
    cmp r7, #3
    moveq r0, #FX_MOD_RECORD
    ldrne r0, =FX_RECORD
    str r0, [r9, #4]
    mov r0, r9
    mov r1, #FX_HEAD
    bl fx_put
    cmp r0, #0
    bne fx_new_fail
    cmp r7, #3
    beq fx_new_mod
    mov r0, r8
    cmp r7, #1
    ldreq r12, =FX_GET_IFX
    ldrne r12, =FX_GET_MFX
    blx r12
    ldr r1, =FX_RECORD
    b fx_new_put
fx_new_mod:
    mov r1, #FX_MOD_RECORD
    mul r2, r8, r1
    ldr r0, =FX_MODS
    add r0, r0, r2
fx_new_put:
    bl fx_put
    cmp r0, #0
    bne fx_new_fail
    add r8, r8, #1
    b fx_new_entry
fx_new_kind_done:
    mov r8, #0
    add r7, r7, #1
    cmp r7, #3
    bls fx_new_entry
    ldr r0, [r5, #CARD_CRC]
    mvn r0, r0
    str r0, [r9]
    str r0, [r4, #FX_WANT]
    mov r0, r6
    mov r1, #12
    ldr r12, =FS_LSEEK
    blx r12
    cmp r0, #0
    bne fx_new_fail
    mov r0, r6
    mov r1, r9
    mov r2, #4
    add r3, r5, #CARD_BR
    ldr r12, =FS_WRITE
    blx r12
    cmp r0, #0
    bne fx_new_fail
    mov r0, r6
    ldr r12, =FS_CLOSE
    blx r12
    cmp r0, #0
    bne fx_new_unlink
    mov r0, #FX_OK
    str r0, [r4, #FX_STATUS]
    mov r0, #0x53
    b fx_export_status
fx_new_fail:
    mov r7, r0
    mov r0, r6
    ldr r12, =FS_CLOSE
    blx r12
    mov r0, r7
fx_new_unlink:
    add r7, r0, #0x20
    ldr r0, =fx_path
    ldr r12, =FS_UNLINK
    blx r12
    mov r0, r7
    b fx_export_status

; r0 pointer, r1 length: written to the open file and added to the CRC -> r0 0, or the FatFs code (2 when short)
fx_put:
    push {r4, r7, r8, lr}
    mov r4, r0
    mov r7, r1
    bl card_crc
    mov r0, r6
    mov r1, r4
    mov r2, r7
    add r3, r5, #CARD_BR
    ldr r12, =FS_WRITE
    blx r12
    cmp r0, #0
    bne fx_put_done
    ldr r0, [r5, #CARD_BR]
    cmp r0, r7
    movne r0, #2
    moveq r0, #0
fx_put_done:
    pop {r4, r7, r8, pc}
.pool
