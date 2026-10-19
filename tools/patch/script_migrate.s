; First start of BLECH on a card that has a hacktribe or electribe sampler folder but no blechtribe folder (device wish 19.10.):
; before the samples load, the display asks whether the old folder is to be copied to KORG/blechtribe, so the samples stay. The
; wheel, EDIT or PART < > choose between the two folders when both are there, MENU copies, EXIT starts as before (nothing is
; written). The copy takes every file and folder (up to MG_DEPTH levels; names that start with a dot are left out), then the
; firmware loads the samples from the new folder.
;
; migrate_start runs in the early hook in front of the sample loader and waits there: the input hook gives it the keys
; (migrate_input), the frame hook draws the question and the progress (migrate_frame). Not with EXIT held at power-on, not on the
; synth (MG_WORK 0). Firmware addresses that come with the build (script_hooks.py): MG_WORK (the work area, RAM only), MG_MKDIR
; (f_mkdir), MG_ALLOC and MG_FREE (the firmware's operator new and delete).
.equ MG_ACTIVE, 0               ; 1 while the question or the copy is up (the input and frame hooks act only then)
.equ MG_CHOICE, 4               ; 0 hacktribe, 1 electribe sampler
.equ MG_HAVE, 8                 ; bit 0: KORG/hacktribe is there, bit 1: KORG/electribe sampler
.equ MG_KEY, 12                 ; set by the input hook: 1 EXIT, 2 MENU, 3 the other folder
.equ MG_PHASE, 16               ; 0 the question, 1 copying, 2 done, 3 failed
.equ MG_BYTES, 20               ; bytes copied
.equ MG_BUF, 24                 ; the copy buffer from the firmware's heap
.equ MG_DEPTHNOW, 28
.equ MG_NAME, 0x20              ; the name of the file being copied, 21 characters and a zero
.equ MG_INFO, 0x40              ; FILINFO: attribute +8, short name +9, long name pointer +0x18 and its size +0x1C
.equ MG_LFN, 0x80               ; the long name, 256 bytes
.equ MG_SRCF, 0x180             ; the FIL being read
.equ MG_DSTF, 0x400             ; the FIL being written
.equ MG_DIRS, 0x680             ; a DIR per level, 0x40 each
.equ MG_SLEN, 0x7C0             ; per level: the length of the source path
.equ MG_DLEN, 0x7E0             ; per level: the length of the destination path
.equ MG_SRC, 0x800              ; the source path
.equ MG_DST, 0xA00              ; the destination path
.equ MG_PATH_MAX, 0x1F0
.equ MG_DEPTH, 5
.equ MG_BUFSIZE, 0x8000
.equ MG_COUNT, 0xC00            ; the bytes written by the last f_read and f_write

; Called from the early hook. Keeps r4 to r11.
migrate_start:
    push {r4-r11, lr}
    ldr r4, =MG_WORK
    cmp r4, #0
    beq mg_out
    ldr r0, =PANEL
    ldr r0, [r0]
    cmp r0, #0
    cmnne r0, #1
    beq mg_out
    ldr r0, [r0, #0x18]
    tst r0, #0x2000
    bne mg_out
    mov r0, #0
    str r0, [r4, #MG_ACTIVE]
    ldr r1, =mg_new_folder
    bl mg_exists
    cmp r0, #0
    bne mg_out
    mov r5, #0
    ldr r1, =mg_hack_folder
    bl mg_exists
    cmp r0, #0
    orrne r5, r5, #1
    ldr r1, =mg_sampler_folder
    bl mg_exists
    cmp r0, #0
    orrne r5, r5, #2
    cmp r5, #0
    beq mg_out
    str r5, [r4, #MG_HAVE]
    tst r5, #1
    moveq r0, #1
    movne r0, #0
    str r0, [r4, #MG_CHOICE]
    mov r0, #0
    str r0, [r4, #MG_KEY]
    str r0, [r4, #MG_PHASE]
    str r0, [r4, #MG_BYTES]
    mov r0, #1
    str r0, [r4, #MG_ACTIVE]
mg_ask:
    mov r0, #20
    ldr r12, =OS_WAIT
    blx r12
    ldr r0, [r4, #MG_KEY]
    mov r1, #0
    str r1, [r4, #MG_KEY]
    cmp r0, #1
    beq mg_done
    cmp r0, #3
    bne mg_ask_menu
    ldr r1, [r4, #MG_HAVE]
    cmp r1, #3
    ldreq r1, [r4, #MG_CHOICE]
    eoreq r1, r1, #1
    streq r1, [r4, #MG_CHOICE]
    b mg_ask
mg_ask_menu:
    cmp r0, #2
    bne mg_ask
    mov r0, #1
    str r0, [r4, #MG_PHASE]
    bl mg_copy
    cmp r0, #0
    moveq r0, #2
    movne r0, #3
    str r0, [r4, #MG_PHASE]
    ldr r0, =1500
    ldr r12, =OS_WAIT
    blx r12
mg_done:
    mov r0, #0
    str r0, [r4, #MG_ACTIVE]
mg_out:
    pop {r4-r11, pc}

; r1 = path, r4 = the work area -> r0 = 1 when the folder can be opened. Clobbers r0 to r3 and r12.
mg_exists:
    push {lr}
    add r0, r4, #MG_DIRS
    ldr r12, =FS_OPENDIR
    blx r12
    cmp r0, #0
    movne r0, #0
    popne {pc}
    add r0, r4, #MG_DIRS
    ldr r12, =FS_CLOSEDIR
    blx r12
    mov r0, #1
    pop {pc}

; r0 = the base of a path, r1 = its length, r2 = a string -> r0 = the new length (r1 unchanged when it does not fit). Clobbers r3, r12.
mg_append:
    mov r12, r1
mg_append_loop:
    ldrb r3, [r2], #1
    strb r3, [r0, r12]
    cmp r3, #0
    beq mg_append_end
    add r12, r12, #1
    cmp r12, #MG_PATH_MAX
    blo mg_append_loop
    mov r3, #0                  ; too long: the old path again
    strb r3, [r0, r1]
    mov r0, r1
    bx lr
mg_append_end:
    mov r0, r12
    bx lr

; Copies the chosen folder into KORG/blechtribe. r4 = the work area -> r0 = 0 when everything went across.
mg_copy:
    push {r5-r11, lr}
    mov r0, #MG_BUFSIZE
    ldr r12, =MG_ALLOC
    blx r12
    str r0, [r4, #MG_BUF]
    cmp r0, #0
    beq mg_copy_fail_nobuf
    add r0, r4, #MG_SRC
    mov r1, #0
    ldr r2, [r4, #MG_CHOICE]
    cmp r2, #0
    ldreq r2, =mg_hack_folder
    ldrne r2, =mg_sampler_folder
    bl mg_append
    str r0, [r4, #MG_SLEN]
    add r0, r4, #MG_DST
    mov r1, #0
    ldr r2, =mg_new_folder
    bl mg_append
    str r0, [r4, #MG_DLEN]
    add r0, r4, #MG_DST
    ldr r12, =MG_MKDIR
    blx r12
    cmp r0, #0
    bne mg_copy_fail
    mov r5, #0                  ; the level
    add r0, r4, #MG_DIRS
    add r1, r4, #MG_SRC
    ldr r12, =FS_OPENDIR
    blx r12
    cmp r0, #0
    bne mg_copy_fail
mg_copy_next:
    add r6, r4, #MG_DIRS
    add r6, r6, r5, lsl #6      ; this level's DIR
    add r7, r4, #MG_INFO
    add r8, r4, #MG_LFN
    str r8, [r7, #0x18]
    mov r0, #255
    str r0, [r7, #0x1C]
    mov r0, #0
    strb r0, [r8]
    mov r0, r6
    mov r1, r7
    ldr r12, =FS_READDIR
    blx r12
    cmp r0, #0
    bne mg_copy_fail_open
    ldrb r0, [r7, #9]
    cmp r0, #0
    beq mg_copy_level_done
    ldrb r0, [r8]
    cmp r0, #0
    addeq r9, r7, #9
    movne r9, r8                ; the name
    ldrb r0, [r9]
    cmp r0, #0x2E               ; ".", "..", and the dot files of other computers
    beq mg_copy_next
    add r10, r4, #MG_SLEN
    ldr r1, [r10, r5, lsl #2]
    add r0, r4, #MG_SRC
    ldr r2, =mg_slash
    bl mg_append
    mov r1, r0
    add r0, r4, #MG_SRC
    mov r2, r9
    bl mg_append
    mov r11, r0                 ; the new source length
    add r10, r4, #MG_DLEN
    ldr r1, [r10, r5, lsl #2]
    add r0, r4, #MG_DST
    ldr r2, =mg_slash
    bl mg_append
    mov r1, r0
    add r0, r4, #MG_DST
    mov r2, r9
    bl mg_append
    mov r10, r0                 ; the new destination length
    ldrb r0, [r7, #8]
    tst r0, #0x10
    bne mg_copy_folder
    mov r0, r9
    bl mg_show_name
    bl mg_copy_file
    cmp r0, #0
    bne mg_copy_fail_open
    b mg_copy_next
mg_copy_folder:
    add r0, r5, #1
    cmp r0, #MG_DEPTH
    bhs mg_copy_next            ; too deep: left out
    add r0, r4, #MG_DST
    ldr r12, =MG_MKDIR
    blx r12
    cmp r0, #0
    bne mg_copy_fail_open
    add r5, r5, #1
    add r0, r4, #MG_SLEN
    str r11, [r0, r5, lsl #2]
    add r0, r4, #MG_DLEN
    str r10, [r0, r5, lsl #2]
    add r0, r4, #MG_DIRS
    add r0, r0, r5, lsl #6
    add r1, r4, #MG_SRC
    ldr r12, =FS_OPENDIR
    blx r12
    cmp r0, #0
    subne r5, r5, #1
    bne mg_copy_fail_open
    b mg_copy_next
mg_copy_level_done:
    mov r0, r6
    ldr r12, =FS_CLOSEDIR
    blx r12
    cmp r5, #0
    beq mg_copy_ok
    sub r5, r5, #1
    b mg_copy_next
mg_copy_ok:
    bl mg_free
    mov r0, #0
    pop {r5-r11, pc}
mg_copy_fail_open:              ; close every level still open
    add r0, r4, #MG_DIRS
    add r0, r0, r5, lsl #6
    ldr r12, =FS_CLOSEDIR
    blx r12
    subs r5, r5, #1
    bpl mg_copy_fail_open
mg_copy_fail:
    bl mg_free
mg_copy_fail_nobuf:
    mov r0, #1
    pop {r5-r11, pc}

mg_free:
    push {lr}
    ldr r0, [r4, #MG_BUF]
    cmp r0, #0
    ldrne r12, =MG_FREE
    blxne r12
    mov r0, #0
    str r0, [r4, #MG_BUF]
    pop {pc}

; r0 = a name: the first 21 characters go to MG_NAME for the display. Clobbers r0 to r3.
mg_show_name:
    add r1, r4, #MG_NAME
    mov r2, #21
mg_show_loop:
    ldrb r3, [r0], #1
    cmp r3, #0
    beq mg_show_end
    strb r3, [r1], #1
    subs r2, r2, #1
    bne mg_show_loop
mg_show_end:
    mov r3, #0
    strb r3, [r1]
    bx lr

; Copies the file MG_SRC to MG_DST (made anew). r4 = the work area -> r0 = 0 when it went across. Clobbers r0 to r3 and r12.
mg_copy_file:
    push {r5, r6, lr}
    add r0, r4, #MG_SRCF
    add r1, r4, #MG_SRC
    mov r2, #1                  ; read
    ldr r12, =FS_OPEN
    blx r12
    cmp r0, #0
    bne mg_file_out
    add r0, r4, #MG_DSTF
    add r1, r4, #MG_DST
    mov r2, #0x0A               ; create always, write
    ldr r12, =FS_OPEN
    blx r12
    cmp r0, #0
    bne mg_file_close_src
mg_file_loop:
    add r0, r4, #MG_SRCF
    ldr r1, [r4, #MG_BUF]
    mov r2, #MG_BUFSIZE
    add r3, r4, #MG_COUNT
    ldr r12, =FS_READ
    blx r12
    cmp r0, #0
    bne mg_file_close_both
    ldr r5, [r4, #MG_COUNT]
    cmp r5, #0
    beq mg_file_close_both
    add r0, r4, #MG_DSTF
    ldr r1, [r4, #MG_BUF]
    mov r2, r5
    add r3, r4, #MG_COUNT
    ldr r12, =FS_WRITE
    blx r12
    cmp r0, #0
    bne mg_file_close_both
    ldr r0, [r4, #MG_COUNT]
    cmp r0, r5
    movne r0, #7                ; the card is full
    bne mg_file_close_both
    ldr r0, [r4, #MG_BYTES]
    add r0, r0, r5
    str r0, [r4, #MG_BYTES]
    cmp r5, #MG_BUFSIZE
    beq mg_file_loop
    mov r0, #0
mg_file_close_both:
    mov r6, r0
    add r0, r4, #MG_DSTF
    ldr r12, =FS_CLOSE
    blx r12
    orr r6, r6, r0
    add r0, r4, #MG_SRCF
    ldr r12, =FS_CLOSE
    blx r12
    mov r0, r6
    pop {r5, r6, pc}
mg_file_close_src:
    mov r6, r0
    add r0, r4, #MG_SRCF
    ldr r12, =FS_CLOSE
    blx r12
    mov r0, r6
mg_file_out:
    pop {r5, r6, pc}

; r0 = the panel message (type at +0x0C). While the question is up every key, the wheel, the knobs, the pads and the touch pad
; are taken (r0 = 1); EXIT, MENU and a step to the other folder are left for migrate_start. Clobbers r0 to r3.
migrate_input:
    ldr r1, =MG_WORK
    cmp r1, #0
    beq mg_in_pass
    ldr r2, [r1, #MG_ACTIVE]
    cmp r2, #1
    bne mg_in_pass
    ldrb r2, [r0, #0x0c]
    cmp r2, #5
    bhi mg_in_pass              ; power key and mains: as always
    ldr r3, [r1, #MG_PHASE]
    cmp r3, #0
    bne mg_in_take
    cmp r2, #1
    beq mg_in_wheel
    cmp r2, #0
    bne mg_in_take
    ldrb r3, [r0, #0x0e]
    cmp r3, #0
    beq mg_in_take
    ldrb r3, [r0, #0x0d]
    cmp r3, #0x0D
    moveq r2, #1
    beq mg_in_key
    cmp r3, #0x09
    moveq r2, #2
    beq mg_in_key
    cmp r3, #0x08               ; EDIT <, EDIT >, PART <, PART >
    cmpne r3, #0x0C
    cmpne r3, #0x0B
    cmpne r3, #0x0F
    bne mg_in_take
    mov r2, #3
mg_in_key:
    str r2, [r1, #MG_KEY]
mg_in_take:
    mov r0, #1
    bx lr
mg_in_wheel:
    ldrb r3, [r0, #0x0d]
    cmp r3, #0                  ; the main wheel
    bne mg_in_take
    mov r2, #3
    b mg_in_key
mg_in_pass:
    mov r0, #0
    bx lr

; From the frame hook (UI task, before the flush): while the question or the copy is up, the runtime's picture gets their text
; and goes over the firmware's frame buffer. Keeps r4 to r11.
migrate_frame:
    ldr r1, =MG_WORK
    cmp r1, #0
    bxeq lr
    ldr r2, [r1, #MG_ACTIVE]
    cmp r2, #1
    bxne lr
    push {r4-r8, lr}
    mov r8, r1
    bl display_clear
    ldr r7, [r8, #MG_PHASE]
    cmp r7, #0
    bne mg_frame_copy
    ldr r4, =mg_t_title
    mov r5, #1
    mov r6, #0
    bl display_draw_text
    ldr r4, =mg_t_copy
    mov r5, #1
    mov r6, #12
    bl display_draw_text
    ldr r0, [r8, #MG_CHOICE]
    cmp r0, #0
    ldreq r4, =mg_t_hack
    ldrne r4, =mg_t_sampler
    mov r5, #13
    mov r6, #26
    bl display_draw_text
    ldr r0, [r8, #MG_HAVE]
    cmp r0, #3                  ; both folders: arrows say the wheel chooses
    bne mg_frame_keys
    ldr r4, =mg_t_left
    mov r5, #1
    mov r6, #26
    bl display_draw_text
    ldr r4, =mg_t_right
    mov r5, #121
    mov r6, #26
    bl display_draw_text
mg_frame_keys:
    ldr r4, =mg_t_menu
    mov r5, #1
    mov r6, #44
    bl display_draw_text
    ldr r4, =mg_t_exit
    mov r5, #1
    mov r6, #54
    bl display_draw_text
    b mg_frame_show
mg_frame_copy:
    cmp r7, #2
    ldrlo r4, =mg_t_copying
    ldreq r4, =mg_t_done
    ldrhi r4, =mg_t_failed
    mov r5, #1
    mov r6, #8
    bl display_draw_text
    add r4, r8, #MG_NAME
    mov r5, #1
    mov r6, #26
    bl display_draw_text
    ldr r0, [r8, #MG_BYTES]
    mov r0, r0, lsr #20
    mov r5, #1
    mov r6, #44
    bl display_draw_number
    ldr r4, =mg_t_mb
    mov r6, #44
    bl display_draw_text
mg_frame_show:
    ldr r0, =DISPLAY_FB
    ldr r1, =MG_VRAM
    mov r2, #1024
mg_frame_copy_fb:
    subs r2, r2, #4
    ldr r3, [r0, r2]
    str r3, [r1, r2]
    bne mg_frame_copy_fb
    mov r0, #0
    mov r1, #0
    mov r2, #127
    mov r3, #63
    ldr r12, =MG_MARK
    blx r12
    pop {r4-r8, pc}
.align 4
.pool
mg_new_folder:
    .asciz "SD:KORG/blechtribe"
mg_hack_folder:
    .asciz "SD:KORG/hacktribe"
mg_sampler_folder:
    .asciz "SD:KORG/electribe sampler"
mg_slash:
    .asciz "/"
mg_t_title:
    .asciz "NEW: BLECHTRIBE"
mg_t_copy:
    .asciz "COPY YOUR SAMPLES?"
mg_t_hack:
    .asciz "HACKTRIBE"
mg_t_sampler:
    .asciz "ELECTRIBE SAMPLER"
mg_t_left:
    .asciz "<"
mg_t_right:
    .asciz ">"
mg_t_menu:
    .asciz "MENU: COPY"
mg_t_exit:
    .asciz "EXIT: START WITHOUT"
mg_t_copying:
    .asciz "COPYING..."
mg_t_done:
    .asciz "DONE"
mg_t_failed:
    .asciz "COPY FAILED"
mg_t_mb:
    .asciz " MB"
.align 4
migrate_end:
