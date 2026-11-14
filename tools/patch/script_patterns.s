
; ---- the Patterns folder (red and Hacktribe; plan 2026-11-14-patterns-ordner)
; EXPORT PATTERN and EXPORT ALL PATTERN build their path as drive + 0xC0035720(type) + name + "." + extension, where 0xC0035720
; puts "KORG/blechtribe/" into a std::string (the folder string of the blechtribe patch). Both calls of it are sent here instead:
; the same string with "Patterns/" behind it. The folder is made first (f_mkdir, "exists" is no error to us), so a card whose
; KORG/blechtribe has no Patterns yet exports too. Nothing else of the firmware's export changes.
.equ PF_STRING, 0xC00A324C      ; std::string(this, const char *, allocator *), what 0xC0035720 calls
.equ PF_EXPORT_AT, 0xC00371B0   ; EXPORT PATTERN: bl 0xC0035720
.equ PF_EXPORT_ALL_AT, 0xC002E084   ; EXPORT ALL PATTERN: bl 0xC0035720

pat_export_hook:
    ldr lr, =PF_EXPORT_AT+4
    b pat_folder
pat_export_all_hook:
    ldr lr, =PF_EXPORT_ALL_AT+4
; r0 = the std::string to construct, r1 = the device type (unused: the folder string is the same for both). Returns r0 as 0xC0035720.
pat_folder:
    push {r0, r1, r4, lr}
    mov r4, r0
    ldr r0, =pf_dir
    ldr r12, =FS_MKDIR
    blx r12
    mov r0, r4
    ldr r1, =pf_path
    add r2, sp, #4
    ldr r12, =PF_STRING
    blx r12
    mov r0, r4
    add sp, sp, #4
    pop {r1, r4, pc}
.pool
pf_dir:
    .asciz "SD:KORG/blechtribe/Patterns"
pf_path:
    .asciz "KORG/blechtribe/Patterns/"
.align 4

; ---- IMPORT PATTERN and IMPORT ALL PATTERN open in the Patterns folder (red and Hacktribe)
; Korg's file browser is one object ([0xC03405CC]) that keeps its folder, a std::string at +0x18, from one import to the next.
; The import's browser step 0xC00313B8 opens that folder (+8 of the browser's vtable, 0xC003D978) when the import starts and
; again after each MENU on a folder or on Upper Folder. Its ldr r0, [r6] in front of that call is sent here: when the folder is
; still the one the last open read (same string and length, so nothing was walked since), the import starts anew and the folder
; becomes SD:/KORG/blechtribe/Patterns. A walk changes the string, so it is left as it is. A card without the folder: the open
; fails with FR_NO_PATH and Korg's browser goes back to SD: on its own. Not after IMPORT SAMPLE's browser moved the folder (it
; shares the object but not this step): then the import opens where that browser was.
.equ PB_AT, 0xC0031400          ; ldr r0, [r6]: the browser object, in front of its open
.equ PB_ASSIGN, 0xC00A26C0      ; std::string::assign(this, const char *), as Korg's browser takes SD: with it
.equ PB_PTR, 4                  ; in KNOB_HOLD, the two words unused since API 19: the folder string of the last open
.equ PB_LEN, 8                  ; and its length; FF from power-on, so the first import after it opens in Patterns too

pat_browse_hook:
    push {r4-r7, lr}
    ldr r5, [r6]
    add r4, r5, #0x18
    ldr r7, =KNOB_HOLD
    ldr r0, [r4]
    ldr r1, [r0, #-12]          ; the length, in front of the characters (Korg's std::string keeps it there)
    ldr r2, [r7, #PB_PTR]
    ldr r3, [r7, #PB_LEN]
    cmn r2, #1
    beq pb_fresh
    cmp r0, r2
    cmpeq r1, r3
    bne pb_note
pb_fresh:
    mov r0, r4
    ldr r1, =pb_path
    ldr r12, =PB_ASSIGN
    blx r12
pb_note:
    ldr r0, [r4]
    ldr r1, [r0, #-12]
    str r0, [r7, #PB_PTR]
    str r1, [r7, #PB_LEN]
    pop {r4-r7, lr}
    ldr r0, [r6]
    ldr pc, =PB_AT+4
.pool
pb_path:
    .asciz "SD:/KORG/blechtribe/Patterns"
.align 4

; ---- the backup in the Patterns folder at power-on (red and Hacktribe): KORG/blechtribe/Patterns/
; electribe_sampler_allpattern.e2sallpat, the name EXPORT ALL PATTERN gives it, is read in the card hook, after the sample loader
; and before the first pattern selection loads the edit buffer (Emulator: card hook 576 ms, selection 597 ms), so the pattern the
; device opens is the one of the file. Every pattern of the file is compared with its slot in RAM (the firmware read all 250 from
; the flash at about 80 ms); one that differs and has its frame (PTST at 0, PTED at 15356) goes through the firmware's own pattern
; write 0xC004C28C, which copies it into the slot and writes its 16 KiB to the flash. A pattern that is the same writes nothing, so
; the file can stay on the card: the next start writes nothing again. A shorter file (fewer patterns) changes only the ones it has.
; Not with EXIT held at power-on, not after a start without a card (CARD_NEVER), once a start: the early hook arms it (pat_boot_arm).
.equ PL_ARMED, 0xC2C            ; in MG_WORK, behind the folder copy's words: PL_ARM_WORD from the early hook until the card hook
.equ PL_ARM_WORD, 0x4C544150    ; "PATL", so that RAM after power-on is not taken for it
.equ PL_BLOCK, 0x4000
.equ PL_HEAD, 0x100             ; the file header, "KORG" at 0
.equ PL_GLOBALS, 4              ; the globals area behind it, 0x10000 bytes, read over in blocks
.equ PL_COUNT, 250
.equ PL_END_AT, 15356
.equ PL_BANK, 0xC00263E0        ; the pattern bank object, as 0xC004C28C gets it
.equ PL_SLOT, 0xC004A350        ; (bank, n): the RAM slot of pattern n
.equ PL_WRITE, 0xC004C28C       ; (_, n, source, copy): copies source into the slot, writes the slot to the flash, 0 when written
.equ PL_MAGIC, 0x47524F4B       ; "KORG"
.equ PL_START, 0x54535450       ; "PTST"
.equ PL_END, 0x44455450         ; "PTED"
.equ PL_BAR, 0xC0181000         ; the loading animation's entry for the backup (tools/patch/load_bar.py, lb_patterns), behind
.equ PL_BAR_MAGIC, 0x4C424150   ; this word: (bytes read, size), FFFFFFFF read when done; a set without it has no such word
.equ PL_POS, 8                  ; in the file object (FatFs FIL): where it is
.equ PL_SIZE, 12                ; and its size

; From the early hook. Clobbers r0, r1.
pat_boot_arm:
    ldr r0, =MG_WORK
    ldr r1, =PL_ARM_WORD
    str r1, [r0, #PL_ARMED]
    bx lr

; From the card hook. Keeps r4 to r11.
pat_boot_load:
    push {r4-r11, lr}
    ldr r4, =MG_WORK
    ldr r0, [r4, #PL_ARMED]
    mov r1, #0
    str r1, [r4, #PL_ARMED]
    ldr r1, =PL_ARM_WORD
    cmp r0, r1
    bne pl_out
    ldr r0, =PANEL
    ldr r0, [r0]
    cmp r0, #0
    cmnne r0, #1
    beq pl_out
    ldr r0, [r0, #0x18]
    tst r0, #KILL_MASK
    bne pl_out
    ldr r0, =MENU_STATE
    ldr r0, [r0, #M_CARD]
    cmp r0, #CARD_NEVER
    beq pl_out
    ldr r5, =HOOK_CARD
    add r6, r5, #CARD_FIL
    mov r0, r6
    ldr r1, =pl_path
    mov r2, #1
    ldr r12, =FS_OPEN
    blx r12
    cmp r0, #0
    bne pl_out
    bl pl_tell
    mov r0, #PL_BLOCK
    ldr r12, =MG_ALLOC
    blx r12
    movs r7, r0
    beq pl_close
    mov r1, #PL_HEAD
    bl card_read
    cmp r0, #0
    bne pl_free
    ldr r0, [r7]
    ldr r1, =PL_MAGIC
    cmp r0, r1
    bne pl_free
    mov r8, #PL_GLOBALS
pl_globals:
    mov r0, r7
    mov r1, #PL_BLOCK
    bl card_read
    cmp r0, #0
    bne pl_free
    subs r8, r8, #1
    bne pl_globals              ; r8 is 0 now: the first pattern
pl_next:
    cmp r8, #PL_COUNT
    bhs pl_free
    mov r0, r7
    mov r1, #PL_BLOCK
    bl card_read
    cmp r0, #0
    bne pl_free                 ; the end of a shorter file, or a read that failed: the patterns so far are in
    bl pl_tell
    ldr r0, [r7]
    ldr r1, =PL_START
    cmp r0, r1
    bne pl_skip
    ldr r0, =PL_END_AT
    ldr r0, [r7, r0]
    ldr r1, =PL_END
    cmp r0, r1
    bne pl_skip
    ldr r12, =PL_BANK
    blx r12
    mov r1, r8
    ldr r12, =PL_SLOT
    blx r12
    mov r1, #0
pl_compare:
    ldr r2, [r7, r1]
    ldr r3, [r0, r1]
    cmp r2, r3
    bne pl_write
    add r1, r1, #4
    cmp r1, #PL_BLOCK
    blo pl_compare
    b pl_skip
pl_write:
    mov r0, #0
    mov r1, r8
    mov r2, r7
    mov r3, #1
    ldr r12, =PL_WRITE
    blx r12
pl_skip:
    add r8, r8, #1
    b pl_next
pl_free:
    mov r0, r7
    ldr r12, =MG_FREE
    blx r12
pl_close:
    mvn r0, #0
    bl pl_bar
    mov r0, r6
    ldr r12, =FS_CLOSE
    blx r12
pl_out:
    pop {r4-r11, pc}

; Tells the loading animation where the file is (pl_tell), or r0 = FFFFFFFF that it is done (pl_bar). Clobbers r0 to r3, r12.
pl_tell:
    ldr r0, [r6, #PL_POS]
pl_bar:
    ldr r1, [r6, #PL_SIZE]
    ldr r12, =PL_BAR
    ldr r2, [r12], #4
    ldr r3, =PL_BAR_MAGIC
    cmp r2, r3
    bxne lr
    bx r12
.pool
pl_path:
    .asciz "SD:KORG/blechtribe/Patterns/electribe_sampler_allpattern.e2sallpat"
.align 4
pat_boot_end:
