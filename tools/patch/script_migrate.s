; First start of BLECH on a card whose KORG/blechtribe lacks Sample/e2sSample.all or the pattern backup
; (electribe_sampler_allpattern.e2sallpat, what EXPORT ALL PATTERN writes directly into the folder) while an old hacktribe or
; electribe sampler folder has what it lacks (device wish 19.10.; the folder alone is no sign of samples, plugins, Doom and the
; settings land there too): the display asks whether the old folder is to be copied to KORG/blechtribe, for the samples before
; they load, for the backup alone right after. The wheel, EDIT or PART < > choose between the two folders when both are there,
; MENU copies, EXIT starts as before (nothing is written). The copy takes every file and folder (up to MG_DEPTH levels; names that
; start with a dot are left out), so the samples and the pattern backup both, and leaves every file that is already in
; KORG/blechtribe as it is, then the firmware loads the samples from the new folder.
;
; migrate_start runs in the early hook in front of the sample loader (migrate_folders in the card hook after it) and waits there:
; the input hook gives it the keys (migrate_input), the frame hook draws the question and the progress (migrate_frame). Not with
; EXIT held at power-on. Firmware addresses that come with the build (script_hooks.py): MG_WORK (the work area, RAM only),
; MG_MKDIR (f_mkdir), MG_GETFREE (f_getfree), MG_ALLOC and MG_FREE (the firmware's operator new and delete).
;
; The blue Electribe (MG_BLUE 1) has no samples and Korg's synth keeps its files in KORG/electribe: there the card hook calls
; migrate_start, and the question comes when KORG/electribe holds a pattern backup (a file ending in .e2allpat, what EXPORT ALL
; PATTERN writes) while KORG/blechtribe holds none (choice 2, one folder). The blue never looks for a sample file; Hacktribe on a
; blue unit is the sampler build and keeps the sample rule.
;
; Every start reads KORG/blechtribe once (mg_folders): a card without it gets it with the folders BLECH reads and writes in it, a
; card with it gets the folders of that list it lacks (a folder that is there is never made again), and the same pass notes the
; blue's pattern backup in it. On the blue mg_folders runs in migrate_start, before the question. On the red it runs in the first
; frame hook on the main screen (mg_frame_later): the start has no time for a f_readdir of every entry, nor for the f_mkdir
; (about 16 ms each in the emulator, once). The red's pattern backup is looked for by the name the firmware gives it, in the card
; hook after the sample loader (migrate_folders): in front of the loader each f_open costs 3 to 5 ms the start does not have.
; The blue's card hook runs in the start before the scheduler, where the OS sleep never returns: it only sets the question up and
; goes on. The frame hook (UI task) then draws it and takes EXIT or MENU (mg_blue_key); the copy runs there.
.equ MG_ACTIVE, 0               ; 1 while the question or the copy is up (the input and frame hooks act only then)
.equ MG_CHOICE, 4               ; 0 hacktribe, 1 electribe sampler, 2 electribe (blue)
.equ MG_HAVE, 8                 ; bit 0: KORG/hacktribe is there, bit 1: KORG/electribe sampler, bit 2: KORG/electribe (blue)
.equ MG_KEY, 12                 ; set by the input hook: 1 EXIT, 2 MENU, 3 the other folder
.equ MG_PHASE, 16               ; 0 the question, 1 copying, 2 done, 3 failed, 4 not room enough on the card
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
.equ MG_DRY, 0xC04              ; 1: the walk only counts the clusters the copy needs (MG_NEED), nothing is written
.equ MG_NEED, 0xC08             ; clusters the copy needs: every file rounded up to whole clusters, one for every folder
.equ MG_SHIFT, 0xC0C            ; log2 of the card's cluster size in bytes
.equ MG_FREE_CL, 0xC10          ; free clusters on the card (f_getfree)
.equ MG_FS, 0xC20               ; the volume f_getfree names
.equ MG_NEWPAT, 0xC24           ; 1: a pattern backup of the build lies directly in KORG/blechtribe (mg_folders)
.equ MG_LATER, 0xC28            ; the red: MG_LATER_WAIT, then MG_LATER_ON (card hook, or a question), 0 once the frame hook looked
.equ MG_LATER_WAIT, 0x574C4F46  ; "FOLW" and "FOLD", so that RAM after power-on is not taken for either
.equ MG_LATER_ON, 0x444C4F46
.equ MG_FR_EXIST, 8            ; FatFs: the name is taken (f_mkdir, f_open with create new)

; Called from the early hook. Keeps r4 to r11.
migrate_start:
    push {r4-r11, lr}
    ldr r4, =MG_WORK
    cmp r4, #0
    beq mg_out
    mov r0, #0
    str r0, [r4, #MG_LATER]
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
    mov r0, #MG_BLUE
    cmp r0, #0
    blne mg_folders             ; the blue: here, in the card hook after the start's own card work
    mov r0, #MG_BLUE
    cmp r0, #0
    bne mg_blue
    ldr r0, =MG_LATER_WAIT      ; the red: the pattern backup and the folders come later (migrate_folders, mg_frame_later)
    str r0, [r4, #MG_LATER]
    ldr r1, =mg_new_samples
    bl mg_exists
    cmp r0, #0
    bne mg_out
    mov r5, #0
    ldr r1, =mg_hack_samples
    bl mg_exists
    cmp r0, #0
    orrne r5, r5, #1
    ldr r1, =mg_sampler_samples
    bl mg_exists
    cmp r0, #0
    orrne r5, r5, #2
    cmp r5, #0
    beq mg_out
    ldr r0, =MG_LATER_ON        ; one question a start: the card hook does not ask again for the backup
    str r0, [r4, #MG_LATER]
mg_red_choice:
    tst r5, #1
    moveq r0, #1
    movne r0, #0
mg_have:
    str r5, [r4, #MG_HAVE]
    str r0, [r4, #MG_CHOICE]
    mov r0, #0
    str r0, [r4, #MG_KEY]
    str r0, [r4, #MG_PHASE]
    str r0, [r4, #MG_BYTES]
    mov r0, #1
    str r0, [r4, #MG_ACTIVE]
    mov r0, #MG_BLUE
    cmp r0, #0
    bne mg_out                  ; the blue: the frame hook takes the keys (mg_blue_key)
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
    bl mg_run
    b mg_out
mg_done:
    mov r0, #0
    str r0, [r4, #MG_ACTIVE]
mg_out:
    pop {r4-r11, pc}
mg_blue:
    ldr r0, [r4, #MG_NEWPAT]    ; mg_folders looked
    cmp r0, #0
    bne mg_out
    ldr r1, =mg_blue_folder
    bl mg_allpat
    cmp r0, #0
    beq mg_out
    mov r5, #4
    mov r0, #2
    b mg_have

; The red: from the card hook, after the sample loader and before the plugins. When migrate_start ran this start (not with EXIT
; held at power-on) and asked nothing: KORG/blechtribe without the pattern backup while an old folder has it asks here, as in
; front of the loader (the backup need not be there before the samples load, and the start in front of the loader has no time
; for the f_open). Then the next frame hook on the main screen looks at the folders (mg_frame_later). Keeps r4 to r11.
; r0 is the loader's result (0: the samples loaded or there was no file). Anything else is a card the loader could not read: then
; neither the backup nor the folders, each f_open on that card takes seconds and the firmware's "Card Error" box comes that much later.
migrate_folders:
    cmp r0, #0
    bxne lr
    push {r4-r11, lr}
    ldr r4, =MG_WORK
    cmp r4, #0
    beq mg_out
    ldr r0, [r4, #MG_LATER]
    ldr r1, =MG_LATER_WAIT
    cmp r0, r1
    bne mg_out
    ldr r0, =MG_LATER_ON
    str r0, [r4, #MG_LATER]
    mov r5, #0
    ldr r1, =mg_hack_pat
    bl mg_exists
    cmp r0, #0
    orrne r5, r5, #1
    ldr r1, =mg_sampler_pat
    bl mg_exists
    cmp r0, #0
    orrne r5, r5, #2
    cmp r5, #0
    beq mg_out
    ldr r1, =mg_new_pat         ; KORG/blechtribe only when an old folder has one: a name that is not there costs the most
    bl mg_exists
    cmp r0, #0
    bne mg_out
    b mg_red_choice

; MENU: checks the room, copies, shows how it went for 1.5 s and takes the question away. r4 = the work area. Clobbers r0 to r3
; and r12.
mg_run:
    push {lr}
    mov r0, #1
    str r0, [r4, #MG_PHASE]
    bl mg_room                  ; room on the card for all of it? (device wish 19.10.: no half copied folder)
    cmp r0, #0
    movne r0, #4
    bne mg_phase
    mov r0, #0
    str r0, [r4, #MG_DRY]
    bl mg_copy
    cmp r0, #0
    moveq r0, #2
    movne r0, #3
mg_phase:
    str r0, [r4, #MG_PHASE]
    bl mg_draw
    ldr r0, =1500
    ldr r12, =OS_WAIT
    blx r12
    mov r0, #0
    str r0, [r4, #MG_ACTIVE]
    pop {pc}

; The blue: EXIT or MENU from the input hook, taken in the UI task after the start. r8 = the work area. Clobbers r0 to r3 and r12.
mg_blue_key:
    push {r4, lr}
    mov r4, r8
    ldr r0, [r4, #MG_KEY]
    mov r1, #0
    str r1, [r4, #MG_KEY]
    cmp r0, #1
    streq r1, [r4, #MG_ACTIVE]
    cmp r0, #2
    bleq mg_run
    ldr r0, [r4, #MG_ACTIVE]
    cmp r0, #0
    ldreq r1, =UI_REDRAW        ; the firmware draws its own screen again
    moveq r2, #1
    strbeq r2, [r1]
    pop {r4, pc}

; The blue: the copy blocks the UI task, so the progress goes to the display here (MG_LCD, MG_FLUSH). Clobbers r0 to r3 and r12.
mg_draw:
    mov r0, #MG_BLUE
    cmp r0, #0
    bxeq lr
    push {r4, lr}
    bl migrate_frame
    ldr r0, =MG_LCD
    mov r1, #2
    mov r2, #0
    ldr r12, =MG_FLUSH
    blx r12
    ldr r0, =MG_LCD
    mov r1, #3
    mov r2, #0
    ldr r12, =MG_FLUSH
    blx r12
    pop {r4, pc}

; Looks at KORG/blechtribe once: makes it with KORG and every folder of the build's list when it is not there, else makes only the
; folders of the list it lacks (many cards get the folder before BLECH, made by hand, with some folders or none). Sets MG_NEWPAT
; when a pattern backup of the blue lies directly in it. One f_opendir and a f_readdir for each entry; f_mkdir only for a missing
; folder (about 16 ms each in the emulator, once). r4 = the work area. Clobbers r0 to r3 and r12.
mg_folders:
    push {r5-r9, lr}
    mov r5, #0                  ; bit n: name n of the list is there
    str r5, [r4, #MG_NEWPAT]
    mov r0, #MG_BLUE
    cmp r0, #0
    ldreq r8, =mg_red_folders
    ldrne r8, =mg_blue_folders
    add r0, r4, #MG_DIRS
    ldr r1, =mg_new_folder
    ldr r12, =FS_OPENDIR
    blx r12
    cmp r0, #0
    beq mg_folders_read
    ldr r0, =mg_korg
    ldr r12, =MG_MKDIR
    blx r12
    ldr r0, =mg_new_folder
    ldr r12, =MG_MKDIR
    blx r12
    b mg_folders_make
mg_folders_read:
    bl mg_entry
    cmp r0, #0
    beq mg_folders_close
    mov r6, r0                  ; the name
    tst r1, #0x10
    bne mg_folders_dir
    bl mg_pat_name
    cmp r0, #0
    movne r0, #1
    strne r0, [r4, #MG_NEWPAT]
    b mg_folders_read
mg_folders_dir:
    mov r7, #0                  ; the index in the list
    mov r9, r8
mg_folders_cmp:
    ldrb r0, [r9]
    cmp r0, #0
    beq mg_folders_read
    mov r0, r6
    mov r1, r9
    bl mg_suffix
    cmp r0, #2                  ; the whole name, upper or lower case
    moveq r0, #1
    orreq r5, r5, r0, lsl r7
    beq mg_folders_read
mg_folders_cmp_skip:
    ldrb r0, [r9], #1
    cmp r0, #0
    bne mg_folders_cmp_skip
    add r7, r7, #1
    b mg_folders_cmp
mg_folders_close:
    add r0, r4, #MG_DIRS
    ldr r12, =FS_CLOSEDIR
    blx r12
mg_folders_make:
    mov r7, #0
    mov r9, r8
mg_folders_next:
    ldrb r0, [r9]
    cmp r0, #0
    beq mg_folders_out
    mov r0, #1
    tst r5, r0, lsl r7
    bne mg_folders_skip         ; there: left as it is
    add r0, r4, #MG_DST
    mov r1, #0
    ldr r2, =mg_new_folder
    bl mg_append
    mov r1, r0
    add r0, r4, #MG_DST
    ldr r2, =mg_slash
    bl mg_append
    mov r1, r0
    add r0, r4, #MG_DST
    mov r2, r9
    bl mg_append
    add r0, r4, #MG_DST
    ldr r12, =MG_MKDIR
    blx r12
mg_folders_skip:
    ldrb r0, [r9], #1
    cmp r0, #0
    bne mg_folders_skip
    add r7, r7, #1
    b mg_folders_next
mg_folders_out:
    pop {r5-r9, pc}

; The next entry of the open folder MG_DIRS; names that start with a dot (".", "..", the dot files of other computers) are left
; out. r4 = the work area -> r0 = its name (0 at the end or on an error), r1 = its attribute. Clobbers r2, r3 and r12.
mg_entry:
    push {r5, r6, lr}
mg_entry_next:
    add r5, r4, #MG_INFO
    add r6, r4, #MG_LFN
    str r6, [r5, #0x18]
    mov r0, #255
    str r0, [r5, #0x1C]
    mov r0, #0
    strb r0, [r6]
    add r0, r4, #MG_DIRS
    mov r1, r5
    ldr r12, =FS_READDIR
    blx r12
    cmp r0, #0
    bne mg_entry_end
    ldrb r0, [r5, #9]
    cmp r0, #0
    beq mg_entry_end
    ldrb r0, [r6]
    cmp r0, #0
    addeq r6, r5, #9            ; no long name: the short one
    ldrb r0, [r6]
    cmp r0, #0x2E
    beq mg_entry_next
    mov r0, r6
    ldrb r1, [r5, #8]
    pop {r5, r6, pc}
mg_entry_end:
    mov r0, #0
    pop {r5, r6, pc}

; r1 = a folder, r4 = the work area -> r0 = 1 when a pattern backup of the build lies directly in it. Clobbers r1 to r3 and r12.
mg_allpat:
    push {r5, lr}
    add r0, r4, #MG_DIRS
    ldr r12, =FS_OPENDIR
    blx r12
    cmp r0, #0
    movne r0, #0
    popne {r5, pc}
    mov r5, #0
mg_allpat_next:
    bl mg_entry
    cmp r0, #0
    beq mg_allpat_done
    tst r1, #0x10
    bne mg_allpat_next          ; a folder
    bl mg_pat_name
    cmp r0, #0
    beq mg_allpat_next
    mov r5, #1
mg_allpat_done:
    add r0, r4, #MG_DIRS
    ldr r12, =FS_CLOSEDIR
    blx r12
    mov r0, r5
    pop {r5, pc}

; r0 = a name -> r0 not 0 when it ends in .e2allpat, the blue's pattern backup, upper or lower case. Clobbers r1 to r3 and r12.
mg_pat_name:
    ldr r1, =mg_allpat_ext
    b mg_suffix

; r0 = a name, r1 = a string -> r0 = 0 when the name does not end in the string (upper and lower case alike), 1 when it does, 2 when
; the string is the whole name. Clobbers r1 to r3 and r12.
mg_suffix:
    push {r4, r5, lr}
    mov r4, r0
    mov r2, r0
mg_sf_name:
    ldrb r3, [r2], #1
    cmp r3, #0
    bne mg_sf_name
    mov r5, r1
mg_sf_str:
    ldrb r3, [r5], #1
    cmp r3, #0
    bne mg_sf_str
    sub r5, r5, r1              ; the string's length and its zero
    sub r2, r2, r5              ; where it starts in the name
    cmp r2, r4
    blo mg_sf_no
    mov r5, r2
mg_sf_loop:
    ldrb r3, [r1], #1
    cmp r3, #0
    beq mg_sf_yes
    cmp r3, #0x41
    blo mg_sf_low
    cmp r3, #0x5A
    orrls r3, r3, #0x20
mg_sf_low:
    ldrb r12, [r2], #1
    cmp r12, #0x41
    blo mg_sf_cmp
    cmp r12, #0x5A
    orrls r12, r12, #0x20
mg_sf_cmp:
    cmp r12, r3
    beq mg_sf_loop
mg_sf_no:
    mov r0, #0
    pop {r4, r5, pc}
mg_sf_yes:
    cmp r5, r4
    moveq r0, #2
    movne r0, #1
    pop {r4, r5, pc}

; r1 = path, r4 = the work area -> r0 = 1 when the file can be opened for reading. Clobbers r0 to r3 and r12.
mg_exists:
    push {lr}
    add r0, r4, #MG_SRCF
    mov r2, #1
    ldr r12, =FS_OPEN
    blx r12
    cmp r0, #0
    movne r0, #0
    popne {pc}
    add r0, r4, #MG_SRCF
    ldr r12, =FS_CLOSE
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
    mov r0, #0
    str r0, [r4, #MG_BUF]
    ldr r0, [r4, #MG_DRY]
    cmp r0, #0
    bne mg_copy_paths
    mov r0, #MG_BUFSIZE
    ldr r12, =MG_ALLOC
    blx r12
    str r0, [r4, #MG_BUF]
    cmp r0, #0
    beq mg_copy_fail_nobuf
mg_copy_paths:
    add r0, r4, #MG_SRC
    mov r1, #0
    ldr r2, [r4, #MG_CHOICE]
    cmp r2, #1
    ldrlo r2, =mg_hack_folder
    ldreq r2, =mg_sampler_folder
    ldrhi r2, =mg_blue_folder
    bl mg_append
    str r0, [r4, #MG_SLEN]
    add r0, r4, #MG_DST
    mov r1, #0
    ldr r2, =mg_new_folder
    bl mg_append
    str r0, [r4, #MG_DLEN]
    ldr r0, [r4, #MG_DRY]
    cmp r0, #0
    bne mg_copy_root
    add r0, r4, #MG_DST
    ldr r12, =MG_MKDIR
    blx r12
    cmp r0, #0
    cmpne r0, #MG_FR_EXIST      ; the folder is there already: copy into it
    bne mg_copy_fail
mg_copy_root:
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
    ldr r0, [r4, #MG_DRY]
    cmp r0, #0
    bne mg_copy_count
    mov r0, r9
    bl mg_show_name
    bl mg_draw
    bl mg_copy_file
    cmp r0, #0
    bne mg_copy_fail_open
    b mg_copy_next
mg_copy_count:                  ; the file in whole clusters
    ldr r0, [r7]                ; FILINFO: the size
    ldr r1, [r4, #MG_SHIFT]
    mov r2, r0, lsr r1
    mov r3, #1
    mov r3, r3, lsl r1
    sub r3, r3, #1
    tst r0, r3
    addne r2, r2, #1
    ldr r0, [r4, #MG_NEED]
    add r0, r0, r2
    str r0, [r4, #MG_NEED]
    b mg_copy_next
mg_copy_folder:
    add r0, r5, #1
    cmp r0, #MG_DEPTH
    bhs mg_copy_next            ; too deep: left out
    ldr r0, [r4, #MG_DRY]
    cmp r0, #0
    ldrne r0, [r4, #MG_NEED]
    addne r0, r0, #1
    strne r0, [r4, #MG_NEED]
    bne mg_copy_down
    add r0, r4, #MG_DST
    ldr r12, =MG_MKDIR
    blx r12
    cmp r0, #0
    cmpne r0, #MG_FR_EXIST
    bne mg_copy_fail_open
mg_copy_down:
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

; r4 = the work area -> r0 = 0 when the card has room for the copy, 1 when not (or the free space could not be read).
mg_room:
    push {lr}
    ldr r0, =mg_drive
    add r1, r4, #MG_FREE_CL
    add r2, r4, #MG_FS
    ldr r12, =MG_GETFREE
    blx r12
    cmp r0, #0
    bne mg_room_no
    ldr r0, [r4, #MG_FS]
    ldrb r0, [r0, #2]           ; sectors a cluster
    mov r1, #9                  ; 512 bytes a sector
mg_room_shift:
    movs r0, r0, lsr #1
    addne r1, r1, #1
    bne mg_room_shift
    str r1, [r4, #MG_SHIFT]
    mov r0, #1
    str r0, [r4, #MG_DRY]
    str r0, [r4, #MG_NEED]      ; the new folder itself
    bl mg_copy
    cmp r0, #0
    bne mg_room_no
    ldr r0, [r4, #MG_NEED]
    ldr r1, [r4, #MG_FREE_CL]
    cmp r0, r1
    movls r0, #0
    popls {pc}
mg_room_no:
    mov r0, #1
    pop {pc}

mg_free:
    push {lr}
    ldr r0, [r4, #MG_BUF]
    cmp r0, #0
    ldrne r12, =MG_FREE
    blxne r12
    mov r0, #0
    str r0, [r4, #MG_BUF]
    pop {pc}

; r0 = a name: the first 20 characters go to MG_NAME for the display (120 pixels from x 4). Clobbers r0 to r3.
mg_show_name:
    add r1, r4, #MG_NAME
    mov r2, #20
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

; Copies the file MG_SRC to MG_DST (made anew; a file already there is left as it is). r4 = the work area -> r0 = 0 when it went
; across or was there. Clobbers r0 to r3 and r12.
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
    mov r2, #0x06               ; create new, write: never over a file of the user
    ldr r12, =FS_OPEN
    blx r12
    cmp r0, #MG_FR_EXIST        ; already there: left as it is, nothing open on the destination
    moveq r0, #0
    beq mg_file_close_src
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
    bne mg_frame_later
    push {r4-r8, lr}
    mov r8, r1
    mov r0, #MG_BLUE
    cmp r0, #0
    blne mg_blue_key
    ldr r0, [r8, #MG_ACTIVE]
    cmp r0, #1
    bne mg_frame_out
    bl display_clear
    ldr r7, [r8, #MG_PHASE]
    cmp r7, #0
    bne mg_frame_copy
    ldr r4, =mg_t_title
    mov r5, #4                  ; 4 pixels from the sides, 2 from top and bottom, as the firmware's menus
    mov r6, #2
    bl display_draw_text
    ldr r0, [r8, #MG_CHOICE]
    cmp r0, #2
    ldrlo r4, =mg_t_copy
    ldrhs r4, =mg_t_files
    mov r5, #4
    mov r6, #13
    bl display_draw_text
    ldr r0, [r8, #MG_CHOICE]
    cmp r0, #1
    ldrlo r4, =mg_t_hack
    ldreq r4, =mg_t_sampler
    ldrhi r4, =mg_t_blue
    mov r5, #14
    mov r6, #27
    bl display_draw_text
    ldr r0, [r8, #MG_HAVE]
    cmp r0, #3                  ; both folders: arrows say the wheel chooses
    bne mg_frame_keys
    ldr r4, =mg_t_left
    mov r5, #4
    mov r6, #27
    bl display_draw_text
    ldr r4, =mg_t_right
    mov r5, #119
    mov r6, #27
    bl display_draw_text
mg_frame_keys:
    ldr r4, =mg_t_menu
    mov r5, #4
    mov r6, #45
    bl display_draw_text
    ldr r4, =mg_t_exit
    mov r5, #4
    mov r6, #55
    bl display_draw_text
    b mg_frame_show
mg_frame_copy:
    cmp r7, #2
    ldrlo r4, =mg_t_copying
    ldreq r4, =mg_t_done
    cmp r7, #3
    ldreq r4, =mg_t_failed
    ldrhi r4, =mg_t_full
    mov r5, #4
    mov r6, #8
    bl display_draw_text
    add r4, r8, #MG_NAME
    mov r5, #4
    mov r6, #27
    bl display_draw_text
    ldr r0, [r8, #MG_BYTES]
    mov r0, r0, lsr #20
    mov r5, #4
    mov r6, #45
    bl display_draw_number
    ldr r4, =mg_t_mb
    mov r6, #45
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
mg_frame_out:
    pop {r4-r8, pc}
mg_frame_later:                 ; the red, once on the main screen, in the UI task like the writes of the settings file: the folders
    ldr r2, [r1, #MG_LATER]
    ldr r3, =MG_LATER_ON
    cmp r2, r3
    bxne lr
    ldr r2, =SCREEN_MANAGER     ; on the main screen, after the start
    ldr r2, [r2]
    cmp r2, #0
    cmnne r2, #1
    bxeq lr
    ldr r2, [r2, #0x2c]
    cmp r2, #1
    bxne lr
    push {r4, lr}
    mov r4, r1
    mov r0, #0
    str r0, [r4, #MG_LATER]
    bl mg_folders
    pop {r4, pc}
.align 4
.pool
mg_new_folder:
    .asciz "SD:KORG/blechtribe"
mg_new_samples:
    .asciz "SD:KORG/blechtribe/Sample/e2sSample.all"
mg_hack_samples:
    .asciz "SD:KORG/hacktribe/Sample/e2sSample.all"
mg_sampler_samples:
    .asciz "SD:KORG/electribe sampler/Sample/e2sSample.all"
mg_hack_folder:
    .asciz "SD:KORG/hacktribe"
mg_sampler_folder:
    .asciz "SD:KORG/electribe sampler"
mg_blue_folder:
    .asciz "SD:KORG/electribe"
mg_slash:
    .asciz "/"
mg_korg:
    .asciz "SD:KORG"
mg_allpat_ext:
    .asciz ".e2allpat"
mg_new_pat:                     ; the red and Hacktribe: what EXPORT ALL PATTERN writes, directly into the folder
    .asciz "SD:KORG/blechtribe/electribe_sampler_allpattern.e2sallpat"
mg_hack_pat:
    .asciz "SD:KORG/hacktribe/electribe_sampler_allpattern.e2sallpat"
mg_sampler_pat:
    .asciz "SD:KORG/electribe sampler/electribe_sampler_allpattern.e2sallpat"
mg_red_folders:                 ; the folders BLECH reads and writes in KORG/blechtribe, an empty name ends the list
    .asciz "Plugin"
    .asciz "Presets"
    .asciz "Gif"
    .asciz "Doom"
    .asciz "Sample"
    .asciz "System"
    .asciz ""
mg_blue_folders:                ; the blue: no samples, no FX collection, no Doom
    .asciz "Plugin"
    .asciz "Gif"
    .asciz "System"
    .asciz ""
mg_t_title:
    .asciz "NEW: BLECHTRIBE"
mg_t_copy:
    .asciz "COPY YOUR SAMPLES?"
mg_t_files:
    .asciz "COPY YOUR FILES?"
mg_t_blue:
    .asciz "ELECTRIBE"
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
mg_t_full:
    .asciz "CARD FULL, NOT COPIED"
mg_drive:
    .asciz "SD:"
mg_t_mb:
    .asciz " MB"
.align 4
migrate_end:
