; CATEGORY: the page of the BLECH menu (level 9, M_LEVEL_SE) that shows itself as page 3 of the firmware's SAMPLE EDIT, behind
; RENAME. The dial sets the category of the sample SAMPLE EDIT edits in the name table; EXPORT ALL SAMPLE writes it to e2sSample.all
; as it writes RENAME's name (docs/messungen/2026-11-21-sample-kategorie.md). The Sampler's builds only, the synth has
; script_sample_edit_none.s.
.equ SE_PAGE, 0xC0691278      ; the page SAMPLE EDIT shows (0 SELECT SAMPLE, 1 RENAME, 2 START POINT .. 9; above 9 its windows)
.equ SE_RESUME, 0xC0691280    ; byte: 1 makes screen 38 open on SE_PAGE, as after RENAME; 0 makes it start over
.equ SE_NAMES, 0xC047B08C     ; the name table, 32 bytes a slot: +0x10 the category (0 to 17), +0x12 the wave number (u16)
.equ SE_CATEGORIES, 18        ; the categories the firmware has texts for (se_cat_texts)
.equ SE_LEVEL, 8               ; our pages behind PLAY LEVEL (SE_PAGE SE_LEVEL), before DELETE SAMPLE (SE_DELETE): ONE SHOT, REVERSE,
.equ SE_DELETE, 9              ; DECLICK and TURN MONO for a stereo sample (se_tail)
.equ SE_REVERSE, 2             ; the page REVERSE of level 9
.equ SE_DECLICK, 3             ; the page DECLICK of level 9
.equ SE_MONO, 4                ; the page TURN MONO of level 9
.equ SE_SNAP15, 0xC0345A61     ; byte 15 of the play table in the firmware's snapshot of SAMPLE EDIT (0xC0345A2C, esli layout: +0x35)
.equ SE_META, 0xC036AD88       ; the firmware's metadata, 0x45C a physical index: +0 DSP byte offset, +4 PCM bytes, +9 stereo, +11 loaded
.equ SE_PLAY, 0xC0362EE8       ; its play table, 16 bytes a physical index: +0 DSP start, +4 loop and +8 end from the start, in bytes
.equ SE_FREE, 0xC00F9C80       ; its DSP allocation pointer; only the last physical sample gives space back (docs/hintergrund/sample-swap.md)
.equ SE_CHUNK, 0x10000         ; TURN MONO reads this many bytes at a time, the most the firmware's export reads (0x8000 words)
.equ SE_SURE, 0xC00A5A8B       ; the firmware's texts, the same places in red and Hacktribe: "Are You Sure ?" (DELETE SAMPLE's)
.equ SE_TEXT_MONO, 0xC00A7337  ; "Mono"
.equ SE_TEXT_STEREO, 0xC00A733C ; "Stereo"
.equ SE_BUSY, 0xC0345EC4       ; byte: the firmware's SAMPLE EDIT is busy (its WRITE waits for it, as ONE SHOT's does)
.align 4
; 0xC0069BB8 and 0xC0069C88, slots 4 and 5 (EDIT left and right) of SAMPLE EDIT's pages (screen 38): both start with
; `push {r4, r5, r6, lr}`. With the menu armed EDIT right on RENAME (page 1) and EDIT left on START POINT (page 2) go to the page
; CATEGORY (level 9); a sliced sample skips START POINT to LOOP START (page 5) in the firmware, so there EDIT left on page 5 does.
; EDIT right on PLAY LEVEL (page 8) and EDIT left on DELETE SAMPLE (page 9) go to ONE SHOT (level 9, pages 1 to SE_TAIL).
; Every other page and the windows above page 9 stay the firmware's.
se_prev:
    ldr r2, =MENU_STATE
    ldr r3, [r2, #M_ON]
    cmp r3, #1
    bne se_prev_go
    ldr r3, =SE_PAGE
    ldr r3, [r3]
    cmp r3, #2
    beq se_out
    cmp r3, #SE_DELETE
    beq se_prev_tail
    cmp r3, #5
    bne se_prev_go
    push {r0, lr}
    bl se_sliced
    mov r3, r0
    pop {r0, lr}
    cmp r3, #0
    bne se_out
se_prev_go:
    push {r4, r5, r6, lr}
    ldr pc, =0xC0069BBC
se_prev_tail:                   ; DELETE SAMPLE, EDIT left: the last of our pages behind PLAY LEVEL
    push {r0, lr}
    bl se_tail
    mov r1, r0
    pop {r0, lr}
    b se_out_page
se_next:
    ldr r2, =MENU_STATE
    ldr r3, [r2, #M_ON]
    cmp r3, #1
    bne se_next_go
    ldr r3, =SE_PAGE
    ldr r3, [r3]
    cmp r3, #1
    beq se_out
    cmp r3, #SE_LEVEL
    moveq r1, #1
    beq se_out_page
se_next_go:
    push {r4, r5, r6, lr}
    ldr pc, =0xC0069C8C
se_out:
    mov r1, #0
se_out_page:                    ; r1 = the page of level 9: 0 CATEGORY, 1 to SE_TAIL behind PLAY LEVEL
    ldr r2, =MENU_STATE
    mov r3, #M_LEVEL_SE
    str r3, [r2, #M_LEVEL]
    str r1, [r2, #M_PAGE]
    str r1, [r2, #M_ENTER]          ; the menu opens on M_ENTER
    mov r3, #0
    str r3, [r2, #M_STATUS]
    mov r0, #MENU_SCREEN
    mov r1, #0
    ldr pc, =SWITCH_SCREEN
; -> r0 nonzero when SAMPLE EDIT's sample is sliced: a mono user sample with slice steps (the firmware's own test, 0xC007DE74 on
; the model, which goes to 0xC004FF44: not factory, META+9 != 1, step count META+0x458 != 0). Clobbers r1 to r3, r12.
se_sliced:
    push {r4, lr}
    bl 0xC0035AD8
    bl 0xC007DE74
    pop {r4, pc}
; -> r0 = the name table entry of SAMPLE EDIT's sample, 0 when the slot holds no sample or an oscillator (wave number up to 49,
; the slots the loader refuses too). Clobbers r1 to r3, r12.
se_slot:
    push {r4, lr}
    bl 0xC0035AD8
    ldr r1, [r0, #0x3FC]
    ldr r2, =999
    cmp r1, r2
    movhi r0, #0
    pophi {r4, pc}
    mov r4, r1
    bl 0xC007DEAC               ; the firmware's own test (SELECT SAMPLE steps by it): 1 when slot r1 holds a sample
    cmp r0, #0
    popeq {r4, pc}
    mov r1, r4
    ldr r0, =SE_NAMES
    add r0, r0, r1, lsl #5
    ldrb r2, [r0, #0x12]
    ldrb r3, [r0, #0x13]
    orr r2, r2, r3, lsl #8
    cmp r2, #49
    movls r0, #0
    pop {r4, pc}
; -> r0 = the row of the firmware's metadata of SAMPLE EDIT's sample when it is a loaded stereo sample, else 0; r1 = its physical index.
; Clobbers r2, r3, r12.
se_stereo:
    push {r4, lr}
    bl se_slot
    cmp r0, #0
    popeq {r4, pc}
    ldrb r2, [r0, #0x12]
    ldrb r3, [r0, #0x13]
    orr r0, r2, r3, lsl #8
    sub r0, r0, #50
    bl 0xC004E2F0               ; (wave number minus 50) -> the physical index, as the point functions resolve it
    mov r1, r0
    ldr r2, =0x45C
    ldr r3, =SE_META
    mla r0, r2, r1, r3
    ldrb r2, [r0, #11]
    cmp r2, #1
    ldrbeq r2, [r0, #9]
    cmpeq r2, #1
    movne r0, #0
    pop {r4, pc}
; -> r0 = our pages behind PLAY LEVEL: 3 (ONE SHOT, REVERSE, DECLICK), 4 with TURN MONO for a stereo sample. Clobbers r1 to r3, r12.
se_tail:
    push {r4, lr}
    bl se_stereo
    cmp r0, #0
    movne r0, #4
    moveq r0, #3
    pop {r4, pc}
; the same on level 9: TURN MONO stays a page while it shows that it converted, until EDIT or EXIT leaves it
se_tail_menu:
    ldr r0, =MENU_STATE
    ldr r1, [r0, #M_PAGE]
    cmp r1, #SE_MONO
    ldreq r1, [r0, #M_STATUS]
    cmpeq r1, #SE_DONE
    moveq r0, #4
    bxeq lr
    b se_tail
; -> r0 = the play table row (SE_PLAY) of SAMPLE EDIT's sample when the slot holds a loaded sample, else 0; r1 = its physical
; index, resolved as the firmware's point functions do (0xC004E2F0 of se_index). Clobbers r2, r3, r12.
se_row:
    push {r4, lr}
    bl se_slot
    cmp r0, #0
    popeq {r4, pc}
    bl se_index
    bl 0xC004E2F0
    mov r1, r0
    ldr r2, =0x45C
    ldr r3, =SE_META
    mla r0, r2, r1, r3
    ldrb r2, [r0, #11]
    cmp r2, #1
    ldreq r0, =SE_PLAY
    addeq r0, r0, r1, lsl #4
    movne r0, #0
    pop {r4, pc}
; -> r0 = the index of SAMPLE EDIT's sample that the firmware's point functions take (0xC004E4EC of the slot). Clobbers r1 to r3, r12.
se_index:
    push {r4, lr}
    bl 0xC0035AD8
    ldr r0, [r0, #0x3FC]
    mov r0, r0, lsl #16
    mov r0, r0, lsr #16
    bl 0xC004E4EC
    mov r0, r0, lsl #16
    mov r0, r0, lsr #16
    pop {r4, pc}
.pool
; SAMPLE EDIT's "n/10" (only on its screen 38, other screens count to 10 as well): CATEGORY is page 3, ONE SHOT the page behind
; PLAY LEVEL, TURN MONO behind it for a stereo sample, the pages behind them move up.
; Coming back from CATEGORY, screen 38's constructor sets the counter while the menu is still the screen shown: that case is
; the menu screen with the level CATEGORY (the menu's own counter there counts to 11, never to 10).
menu_counter_se:
    mov r0, #SE_SCREEN
    cmp r0, #0
    bxeq lr
    push {r1, r2, lr}
    bl 0xC002D048
    ldr r0, [r0, #0x2C]
    pop {r1, r2, lr}
    cmp r0, #MENU_SCREEN
    ldreq r3, =MENU_STATE
    ldreq r0, [r3, #M_LEVEL]
    cmpeq r0, #M_LEVEL_SE
    moveq r0, #SE_SCREEN
    cmp r0, #SE_SCREEN
    bxne lr
    push {r1, r2, lr}
    bl se_tail                  ; screen 38's own pages: TURN MONO counts for a stereo sample only
    mov r3, r0
    pop {r1, r2, lr}
    add r2, r2, #1
    add r2, r2, r3
    cmp r1, #2
    addge r1, r1, #1
    cmp r1, #SE_DELETE+1
    addge r1, r1, r3
    bx lr
; the counter on level 9 (r3 = MENU_STATE): CATEGORY page 3, ONE SHOT and TURN MONO behind PLAY LEVEL (menu_counter_args)
menu_counter_se_level:
    bl se_tail_menu
    add r2, r0, #SE_PAGES+1
    ldr r3, =MENU_STATE
    ldr r1, [r3, #M_PAGE]
    cmp r1, #0
    moveq r1, #2
    addne r1, r1, #SE_LEVEL+1
    pop {pc}
; level 9 has CATEGORY and our pages behind PLAY LEVEL (menu_page_count)
menu_count_se:
    bl se_tail_menu
    add r0, r0, #1
    pop {r4, pc}
.pool
; level 9, EDIT left (r1 = M_PAGE, r2 = MENU_STATE): CATEGORY to RENAME, the first page behind PLAY LEVEL to it, a later one to the
; page before it
menu_se_prev:
    cmp r1, #1
    bhi menu_prev_step
    moveq r1, #SE_LEVEL
    movne r1, #1
    b menu_se_page
; level 9, EDIT right (r2 = MENU_STATE): the last page behind PLAY LEVEL to DELETE SAMPLE, the others to the page behind them;
; CATEGORY to START POINT, or LOOP START for a sliced sample, as the firmware steps from RENAME
menu_se_next:
    ldr r1, [r2, #M_PAGE]
    cmp r1, #0
    beq menu_se_start
    push {r1, r2}
    bl se_tail_menu
    pop {r1, r2}
    cmp r1, r0
    addlo r1, r1, #1
    blo menu_next_step
    mov r1, #SE_DELETE
    b menu_se_page
menu_se_start:
    bl se_sliced
    cmp r0, #0
    movne r1, #5
    moveq r1, #2
; r1 = the page of SAMPLE EDIT to open: screen 38 opens on it as it does after RENAME
menu_se_page:
    ldr r0, =SE_PAGE
    str r1, [r0]
    ldr r0, =SE_RESUME
    mov r1, #1
    strb r1, [r0]
    mov r0, #SE_SCREEN
    b menu_leave
.pool
; CATEGORY (r0 = 67): the category of SAMPLE EDIT's sample in the firmware's own text, as the Part screen shows it; "---" where
; the slot holds no sample or an oscillator (wave number up to 49)
menu_text_se:
    ldr r0, [r5, #M_PAGE]
    cmp r0, #SE_MONO
    beq menu_text_se_mono
    cmp r0, #SE_DECLICK
    beq menu_text_se_declick
    cmp r0, #SE_REVERSE
    beq menu_text_se_reverse
    cmp r0, #0
    bne menu_text_se_oneshot
    add r0, r5, #M_TITLE
    ldr r1, =str_category
    bl menu_copy
    bl se_slot
    ldr r1, =str_se_none
    cmp r0, #0
    beq menu_text_se_put
    ldrb r2, [r0, #0x10]
    cmp r2, #SE_CATEGORIES
    ldrlo r1, =se_cat_texts
    ldrlo r1, [r1, r2, lsl #2]
menu_text_se_put:
    add r0, r5, #M_VALUE
    bl menu_copy
    b menu_text_look_line3
; ONE SHOT: ON when the sample's LOOP START POINT is its END POINT, the firmware's one-shot (play table +14, set by its point
; functions): the note plays to the end of the sample, a pad released early does not stop it. "---" as on CATEGORY
menu_text_se_oneshot:
    add r0, r5, #M_TITLE
    ldr r1, =str_ue_oneshot
    bl menu_copy
    bl se_slot
    ldr r1, =str_se_none
    cmp r0, #0
    beq menu_text_se_put
    bl se_index
    bl 0xC004EA38               ; (index) -> the one-shot byte
    cmp r0, #0
    ldreq r1, =str_off
    ldrne r1, =str_on
    b menu_text_se_put
; DECLICK: ON when bit 0 of the play table's byte 15 is set (esli byte 53, which the firmware only copies: import, EXPORT ALL SAMPLE,
; the snapshot of SAMPLE EDIT); "---" as on CATEGORY
menu_text_se_declick:
    add r0, r5, #M_TITLE
    ldr r1, =str_se_declick
    bl menu_copy
    bl se_row
    ldr r1, =str_se_none
    cmp r0, #0
    beq menu_text_se_put
    ldrb r0, [r0, #15]
    tst r0, #1
    ldreq r1, =str_off
    ldrne r1, =str_on
    b menu_text_se_put
; REVERSE: ON when bit 1 of the play table's byte 15 is set (esli byte 53): the sample's PCM lies reversed in the DSP and on the card
; after EXPORT ALL SAMPLE; "---" as on CATEGORY
menu_text_se_reverse:
    add r0, r5, #M_TITLE
    ldr r1, =str_ue_reverse
    bl menu_copy
    bl se_row
    ldr r1, =str_se_none
    cmp r0, #0
    beq menu_text_se_put
    ldrb r0, [r0, #15]
    tst r0, #2
    ldreq r1, =str_off
    ldrne r1, =str_on
    b menu_text_se_put
; TURN MONO (only for a stereo sample, se_tail): "Stereo", after ENTER "Are You Sure ?", after the second ENTER "Mono"; while the
; sequencer runs ENTER only says "stop PLAY"
menu_text_se_mono:
    add r0, r5, #M_TITLE
    ldr r1, =str_se_mono
    bl menu_copy
    ldr r0, [r5, #M_STATUS]
    ldr r1, =SE_SURE
    cmp r0, #SE_ASK
    beq menu_text_se_mono_put
    ldr r1, =str_se_play
    cmp r0, #SE_PLAYING
    beq menu_text_se_mono_put
    bl se_stereo
    ldr r1, =SE_TEXT_STEREO
    cmp r0, #0
    ldreq r1, =SE_TEXT_MONO
menu_text_se_mono_put:
    add r0, r5, #M_VALUE
    bl menu_copy
    pop {r4, r5, r6, r7, pc}
; CATEGORY: the dial steps the category byte in the name table, 0 to 17, and stops at the ends; the slot keeps it in RAM, EXPORT
; ALL SAMPLE writes it to e2sSample.all as RENAME's name. Nothing for a slot without a sample or an oscillator.
menu_value_se:
    ldr r0, [r6, #M_PAGE]
    cmp r0, #SE_MONO                ; TURN MONO: the dial changes nothing
    beq menu_value_done
    cmp r0, #SE_DECLICK
    beq menu_value_se_declick
    cmp r0, #SE_REVERSE
    beq menu_value_se_reverse
    cmp r0, #0
    bne menu_value_se_oneshot
    bl se_slot
    cmp r0, #0
    beq menu_value_done
    ldrb r1, [r0, #0x10]
    add r1, r1, r5
    cmp r1, #0
    movlt r1, #0
    cmp r1, #SE_CATEGORIES-1
    movgt r1, #SE_CATEGORIES-1
    strb r1, [r0, #0x10]
    mov r1, #0
    strb r1, [r0, #0x11]
    b menu_value_done
; ONE SHOT, the dial: up ON, LOOP START POINT to END POINT; down OFF, LOOP START POINT to START POINT. Through the firmware's own
; LOOP START POINT (0xC007F630 with the model and a value object of frames): its undo, the parts that play the sample, the screen.
; The loop point before ON is not kept.
menu_value_se_oneshot:
    bl se_slot
    cmp r0, #0
    beq menu_value_done
    push {r7, r8}
    bl se_index
    mov r8, r0
    bl 0xC004EA38               ; (index) -> the one-shot byte
    cmp r0, #0
    movne r0, #1
    cmp r5, #0
    movgt r1, #1
    movle r1, #0
    cmp r0, r1
    beq menu_value_se_kept
    mov r0, r8
    mov r1, #0
    cmp r5, #0
    ble menu_value_se_start
    bl 0xC004E710               ; (index, frames to add) -> END POINT in frames
    b menu_value_se_loop
menu_value_se_start:
    bl 0xC004E63C               ; (index, frames to add) -> START POINT in frames
menu_value_se_loop:
    ldr r1, =MENU_STATE
    mov r2, #0
    str r2, [r1, #M_STATUS]
    sub sp, sp, #16
    str r0, [sp, #12]
    add r1, sp, #8
    str r1, [sp]
    bl 0xC0035AD8
    mov r1, sp
    mov r2, #0
    bl 0xC007F630
    add sp, sp, #16
menu_value_se_kept:
    pop {r7, r8}
    b menu_value_done
; DECLICK, the dial: up ON, down OFF, bit 0 of the play table's byte 15. ON computes the points it plays at once (dc_update), so
; the next pad already plays them. Like ONE SHOT a preview: WRITE keeps it, EXIT without WRITE gives the old byte back (the
; firmware's restore 0xC004EFF4 writes byte 15 from its snapshot; it runs only when the "edited" byte 0xC0345A20 is set).
menu_value_se_declick:
    bl se_row
    cmp r0, #0
    beq menu_value_done
    ldrb r3, [r0, #15]
    cmp r5, #0
    orrgt r2, r3, #1
    bicle r2, r3, #1
    strb r2, [r0, #15]
    cmp r2, r3                      ; changed: the firmware's "edited" byte, else EXIT skips its restore (0xC0039420)
    ldrne r3, =0xC0345A20
    movne r2, #1
    strbne r2, [r3]
    ldr r2, =MENU_STATE
    mov r3, #0
    str r3, [r2, #M_STATUS]
    push {r7, r8}
    mov r7, r1
    mov r0, r1
    bl dc_check
    movs r1, r0
    movne r0, r7
    blne dc_update
    pop {r7, r8}
    b menu_value_done
; REVERSE, the dial: up ON, down OFF. A change turns the sample's PCM round in the DSP at once (se_reverse); it stays without
; WRITE, as TURN MONO's change does. Not while the firmware's SAMPLE EDIT is busy.
menu_value_se_reverse:
    bl se_row
    cmp r0, #0
    beq menu_value_done
    ldrb r2, [r0, #15]
    and r2, r2, #2
    cmp r5, #0
    movgt r3, #2
    movle r3, #0
    cmp r2, r3
    beq menu_value_done
    ldr r2, =SE_BUSY
    ldrb r2, [r2]
    cmp r2, #0
    bne menu_value_done
    ldr r2, =MENU_STATE
    mov r3, #0
    str r3, [r2, #M_STATUS]
    bl se_reverse
    b menu_value_done
; level 9, a key (r6, menu_slot_keys): WRITE on ONE SHOT and DECLICK does what WRITE does on SAMPLE EDIT's own pages (0xC006F094 on screens
; 37 to 39): it posts the firmware's command 0x25, which keeps the points; EXIT without it gives the old ones back. Not while the
; firmware's byte 0xC0345EC4 says it is busy, as there. WRITE on CATEGORY saves the settings as before.
menu_keys_se:
    ldr r0, =MENU_STATE
    ldr r0, [r0, #M_PAGE]
    cmp r0, #SE_MONO
    beq menu_keys_se_mono
    cmp r6, #0x0E
    bne menu_keys_done
    cmp r0, #0
    beq menu_keys_save
    bl se_slot
    cmp r0, #0
    beq menu_keys_done
    ldr r0, =0xC0345EC4
    ldrb r0, [r0]
    cmp r0, #0
    bne menu_keys_done
    mov r0, #0x25
    mov r1, #0
    mov r2, #0
    bl POST_COMMAND
    ldr r0, =MENU_STATE             ; "saved" in the third line until the dial moves
    mov r1, #1
    str r1, [r0, #M_STATUS]
    b menu_keys_done
; TURN MONO, ENTER or WRITE: the first asks "Are You Sure ?" as DELETE SAMPLE does, the second converts (EXIT in between takes
; the question back, menu_exit_se). Not while the sequencer runs or the firmware's SAMPLE EDIT is busy.
menu_keys_se_mono:
    ldr r5, =MENU_STATE
    bl se_stereo
    cmp r0, #0
    beq menu_keys_done
    ldr r0, =HW_TRANSPORT
    ldr r0, [r0]
    cmp r0, #0
    movne r0, #SE_PLAYING
    strne r0, [r5, #M_STATUS]
    bne menu_keys_done
    ldr r0, [r5, #M_STATUS]
    cmp r0, #SE_ASK
    movne r0, #SE_ASK
    strne r0, [r5, #M_STATUS]
    bne menu_keys_done
    ldr r0, =SE_BUSY
    ldrb r0, [r0]
    cmp r0, #0
    bne menu_keys_done
    bl se_mono
    cmp r0, #0
    movne r0, #SE_DONE
    str r0, [r5, #M_STATUS]
    b menu_keys_done
.pool
; TURN MONO: SAMPLE EDIT's stereo sample becomes mono in the DSP's memory, (L+R)/2 rounded down as the loader, the app and the blue
; mix (asr, no clipping). The firmware keeps a stereo sample as one block of interleaved frames, 4 bytes each; the mono frame i goes
; to the start + 2i, so the writes never pass the reads and blocks in rising order are safe in place. Reads and writes go through
; the firmware's own DSP transfers (0xC004EDDC, 0xC004EF28) and its work buffer (0xC00369F0), as EXPORT ALL SAMPLE does. The points
; stay on the same frame: start, loop and end in the play table halve against the sample's DSP offset; the metadata gets half the
; PCM bytes and stereo 0. The freed half is lost until the next start, unless the sample is the last one in the DSP: then the
; allocation pointer moves back, as the firmware's DELETE SAMPLE does. Last the firmware's own snapshot of SAMPLE EDIT is taken
; again (0xC0039514, as on opening it), so EXIT without WRITE does not put the stereo metadata back over the mono PCM. The card
; keeps the stereo file until EXPORT ALL SAMPLE, as with every page of SAMPLE EDIT.
; -> r0 1 when it converted, 0 when the sample is not a loaded stereo sample.
se_mono:
    push {r4, r5, r6, r7, r8, r9, r10, lr}
    bl se_stereo
    cmp r0, #0
    beq se_mono_out
    mov r4, r0                      ; the metadata row
    mov r5, r1                      ; the physical index
    ldr r6, [r4]                    ; the DSP byte offset
    ldr r7, [r4, #4]
    bic r7, r7, #3                  ; its PCM bytes, whole frames
    sub sp, sp, #8
    mov r0, sp
    bl 0xC00369F0                   ; -> the work buffer
    add sp, sp, #8
    mov r8, r0
    mov r9, #0                      ; bytes done
se_mono_block:
    subs r10, r7, r9
    beq se_mono_points
    cmp r10, #SE_CHUNK
    movhi r10, #SE_CHUNK
    mov r0, r8
    add r1, r6, r9
    mov r2, r10, lsr #1
    bl 0xC004EDDC                   ; (buffer, DSP byte address, words)
    mov r0, r8
    mov r1, r8
    mov r2, r10, lsr #2
se_mono_mix:
    ldrsh r3, [r0]
    ldrsh r12, [r0, #2]
    add r0, r0, #4
    add r3, r3, r12
    mov r3, r3, asr #1
    strh r3, [r1]
    add r1, r1, #2
    subs r2, r2, #1
    bne se_mono_mix
    mov r0, r8
    add r1, r6, r9, lsr #1
    mov r2, r10, lsr #2
    bl 0xC004EF28                   ; (buffer, DSP byte address, words)
    add r9, r9, r10
    b se_mono_block
se_mono_points:
    bl 0xC0036A08                   ; the work buffer back
    ldr r0, =SE_PLAY
    add r0, r0, r5, lsl #4
    ldr r1, [r0]
    sub r1, r1, r6
    add r1, r6, r1, lsr #1
    str r1, [r0]
    ldr r1, [r0, #4]
    mov r1, r1, lsr #1
    str r1, [r0, #4]
    ldr r1, [r0, #8]
    mov r1, r1, lsr #1
    str r1, [r0, #8]
    ldr r0, =SE_FREE
    ldr r1, [r0]
    add r2, r6, r7
    cmp r1, r2
    addeq r2, r6, r7, lsr #1
    streq r2, [r0]
    mov r7, r7, lsr #1
    str r7, [r4, #4]
    mov r0, #0
    strb r0, [r4, #9]
    bl 0xC0039514                   ; the snapshot of SAMPLE EDIT's sample, again
    mov r0, #1
se_mono_out:
    pop {r4, r5, r6, r7, r8, r9, r10, pc}
.pool
; REVERSE: SAMPLE EDIT's sample turns round in the DSP's memory, frame by frame (a stereo frame keeps L before R), and bit 1 of its
; play table byte 15 flips: set means the PCM lies reversed. The points stay as they are, as on the blue: they now play the reversed
; PCM, the loop runs through it backwards to the original. Twice gives the sample back bit for bit. Pairs of SE_CHUNK blocks from
; both ends swap (each read, turned round, written to the other end), the rest in the middle turns round in place; reads and writes
; go through the firmware's own DSP transfers and its work buffer, as TURN MONO's. The firmware's snapshot of SAMPLE EDIT gets the
; same bit, so EXIT without WRITE does not set the bit back over reversed PCM; DECLICK's entry of the sample is dropped, it is
; computed again on the new PCM. The card gets the reversed PCM and the bit with EXPORT ALL SAMPLE (Korg copies byte 15 through);
; the blue reads only bit 0 of that byte and plays the PCM as it lies.
; r0 = the play table row, r1 = the physical index (se_row). Clobbers r0 to r3, r12.
se_reverse:
    push {r4, r5, r6, r7, r8, r9, r10, r11, lr}
    mov r4, r0
    mov r5, r1
    ldr r2, =0x45C
    ldr r3, =SE_META
    mla r6, r2, r5, r3
    ldrb r0, [r6, #9]
    cmp r0, #1
    moveq r9, #4                    ; the frame's bytes: stereo 4, mono 2
    movne r9, #2
    ldr r7, [r6]                    ; the DSP byte offset
    ldr r8, [r6, #4]
    sub r0, r9, #1
    bic r8, r8, r0                  ; the PCM's end, whole frames
    sub sp, sp, #8
    mov r0, sp
    bl 0xC00369F0                   ; -> the work buffer
    add sp, sp, #8
    mov r10, r0
    mov r11, #0                     ; r11 the low end, r8 the high end, in bytes from the offset
se_rev_pair:
    sub r0, r8, r11
    cmp r0, #SE_CHUNK*2
    bls se_rev_middle
    mov r0, r10                     ; the block at the low end
    add r1, r7, r11
    mov r2, #SE_CHUNK
    bl se_rev_read
    add r0, r10, #SE_CHUNK          ; the block at the high end
    add r1, r7, r8
    sub r1, r1, #SE_CHUNK
    mov r2, #SE_CHUNK
    bl se_rev_read
    add r0, r10, #SE_CHUNK
    add r1, r7, r11
    mov r2, #SE_CHUNK
    bl se_rev_write
    mov r0, r10
    add r1, r7, r8
    sub r1, r1, #SE_CHUNK
    mov r2, #SE_CHUNK
    bl se_rev_write
    add r11, r11, #SE_CHUNK
    sub r8, r8, #SE_CHUNK
    b se_rev_pair
se_rev_middle:
    subs r2, r8, r11
    beq se_rev_done
    mov r0, r10
    add r1, r7, r11
    bl se_rev_read
    mov r0, r10
    add r1, r7, r11
    sub r2, r8, r11
    bl se_rev_write
se_rev_done:
    bl 0xC0036A08                   ; the work buffer back
    ldrb r0, [r4, #15]
    eor r0, r0, #2
    strb r0, [r4, #15]
    ldr r1, =SE_SNAP15
    ldrb r2, [r1]
    bic r2, r2, #2
    and r0, r0, #2
    orr r2, r2, r0
    strb r2, [r1]
    ldr r0, =DC_ENTRIES
    mov r1, #DC_COUNT
    mvn r2, #0
se_rev_declick:
    ldr r3, [r0]
    cmp r3, r5
    streq r2, [r0]
    add r0, r0, #32
    subs r1, r1, #1
    bne se_rev_declick
    pop {r4, r5, r6, r7, r8, r9, r10, r11, pc}
; r0 = the buffer, r1 = a DSP byte address, r2 = bytes (whole frames, r9 the frame's bytes): read in SE_CHUNK steps, then the frames
; turned round in the buffer. Clobbers r0 to r3, r12.
se_rev_read:
    push {r4, r5, r6, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r12, #0
se_rev_read_step:
    subs r2, r6, r12
    beq se_rev_turn
    cmp r2, #SE_CHUNK
    movhi r2, #SE_CHUNK
    push {r2, r12}
    add r0, r4, r12
    add r1, r5, r12
    mov r2, r2, lsr #1
    bl 0xC004EDDC                   ; (buffer, DSP byte address, words)
    pop {r2, r12}
    add r12, r12, r2
    b se_rev_read_step
se_rev_turn:
    mov r0, r4
    add r1, r4, r6
    sub r1, r1, r9
se_rev_swap:
    cmp r0, r1
    pophs {r4, r5, r6, pc}
    cmp r9, #4
    ldreq r2, [r0]
    ldreq r3, [r1]
    streq r3, [r0]
    streq r2, [r1]
    ldrhne r2, [r0]
    ldrhne r3, [r1]
    strhne r3, [r0]
    strhne r2, [r1]
    add r0, r0, r9
    sub r1, r1, r9
    b se_rev_swap
; r0 = the buffer, r1 = a DSP byte address, r2 = bytes: written in SE_CHUNK steps. Clobbers r0 to r3, r12.
se_rev_write:
    push {r4, r5, r6, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r12, #0
se_rev_write_step:
    subs r2, r6, r12
    popeq {r4, r5, r6, pc}
    cmp r2, #SE_CHUNK
    movhi r2, #SE_CHUNK
    push {r2, r12}
    add r0, r4, r12
    add r1, r5, r12
    mov r2, r2, lsr #1
    bl 0xC004EF28                   ; (buffer, DSP byte address, words)
    pop {r2, r12}
    add r12, r12, r2
    b se_rev_write_step
.pool
; DECLICK: a sample with bit 0 of its play table byte 15 set plays from START POINT, LOOP START and END POINT moved to the nearest
; frame where all its channels cross zero within DC_WIN frames either side; where they share no crossing there, to the frame
; with the smallest |L| + |R| (|x| for mono), the nearer one on a tie. Nothing is written to the sample: the play table keeps the
; points, the firmware's pages show and export them, OFF plays them again. A sliced sample's slices are not moved.
; The moved points sit in a table of DC_COUNT entries in RAM (DECLICK, script_hooks.py), 32 bytes each: +0 the physical index
; (FFFFFFFF none, as at power-on), +4 start, +8 loop and +12 end of the play table and +16 the metadata's PCM bytes they were
; computed for, +20 the moved start (DSP bytes), +24 loop and +28 end from it. An entry counts only while all four still match,
; so a point moved on Korg's pages, TURN MONO or another sample in the slot plays the stored points until the entry is new.
; least-code: one table of DC_COUNT samples, not one entry per physical index (999 x 32 bytes do not fit the reserve); a sample
; with DECLICK beyond the first DC_COUNT plays its stored points. More would need a bigger table or a compact one per index.
.equ DC_WIN, 7                 ; the search window: 1 << 7 = 128 frames either side of a point (2.7 ms at 48 kHz)
.equ DC_COUNT, 64
.equ DC_ROWS, 256              ; play table rows declick_frame looks at in one frame
.equ DC_PHYS, 999              ; the physical indexes, rows 0 to 998 (the voice start clamps to 0x3E6)
.equ DC_ENTRIES, DECLICK+16    ; behind the word of the scan's next row
.equ DC_BUF, DECLICK+16+DC_COUNT*32+4   ; the window as read, 2 * 128 + 2 frames of 4 bytes; the frame before it at DC_BUF - 4
; 0xC0099BC8 in the voice start (0xC0099A40, every note of a sample), `sub r0, r0, #1` in front of the jump on the voice's mode:
; r7 the physical index, r6 the start (DSP bytes), r3 the loop and r2 the end from it, as read from the play table. With DECLICK
; and a matching entry they become the moved points. Only ip and lr are free here (nothing behind uses them).
dc_note_hook:
    sub r0, r0, #1
    ldr ip, =SE_PLAY
    add ip, ip, r7, lsl #4
    ldrb lr, [ip, #15]
    tst lr, #1
    beq dc_note_out
    push {r0, r1, r4, r5}
    ldr r4, =DC_ENTRIES
    mov r5, #DC_COUNT
dc_note_find:
    ldr r0, [r4]
    cmp r0, r7
    beq dc_note_mine
    add r4, r4, #32
    subs r5, r5, #1
    bne dc_note_find
    b dc_note_done
dc_note_mine:
    ldr r0, [r4, #4]
    cmp r0, r6
    ldreq r0, [r4, #8]
    cmpeq r0, r3
    ldreq r0, [r4, #12]
    cmpeq r0, r2
    bne dc_note_done
    ldr r1, =0x45C
    ldr lr, =SE_META
    mla lr, r1, r7, lr
    ldr lr, [lr, #4]
    ldr r0, [r4, #16]
    cmp r0, lr
    ldreq r6, [r4, #20]
    ldreq r3, [r4, #24]
    ldreq r2, [r4, #28]
dc_note_done:
    pop {r0, r1, r4, r5}
dc_note_out:
    b 0xC0099BCC
; EXIT on a page of this level (menu_exit_se): the firmware's EXIT on its own SAMPLE EDIT pages runs 0xC0039420 before it goes
; back to screen 37. When its "edited" byte 0xC0345A20 is set, that gives back what WRITE did not keep (0xC004EFF4), so
; ONE SHOT and DECLICK left without WRITE are undone as on the firmware's pages. Clobbers r0 to r3, r12.
se_leave:
    push {r4, r5, r6, lr}
    bl se_slot
    movs r4, r0
    ldrhne r5, [r4, #0x10]          ; CATEGORY is kept without WRITE, as before (it is saved with the settings)
    bl 0xC0039420
    cmp r4, #0
    strhne r5, [r4, #0x10]
    pop {r4, r5, r6, pc}
; Called from the frame hook (UI task, as SAMPLE EDIT's pages): up to DC_ROWS rows from where the last frame stopped; the first
; row with DECLICK whose entry is missing or old is computed (dc_update) and ends this frame's look. Clobbers r0 to r3, r12.
declick_frame:
    push {r4, r5, r6, lr}
    ldr r4, =DECLICK
    ldr r5, [r4]
    ldr r0, =DC_PHYS
    cmp r5, r0
    movhs r5, #0
    mov r6, #DC_ROWS
dc_frame_row:
    mov r0, r5
    bl dc_check
    movs r1, r0
    beq dc_frame_next
    mov r0, r5
    bl dc_update
    mov r6, #1
dc_frame_next:
    add r5, r5, #1
    ldr r0, =DC_PHYS
    cmp r5, r0
    movhs r5, #0
    subs r6, r6, #1
    bne dc_frame_row
    str r5, [r4]
    pop {r4, r5, r6, pc}
; r0 = a physical index -> r0 = the entry to compute it into: its own when that no longer matches, else the first free one (none,
; or one whose sample lost DECLICK); 0 when it needs none (no DECLICK, not loaded, its entry matches) or no entry is free.
; Clobbers r1 to r3, r12.
dc_check:
    push {r4, r5, r6, r7, r8, lr}
    mov r4, r0
    ldr r5, =SE_PLAY
    add r5, r5, r4, lsl #4
    ldrb r0, [r5, #15]
    tst r0, #1
    beq dc_check_none
    ldr r1, =0x45C
    ldr r6, =SE_META
    mla r6, r1, r4, r6
    ldrb r0, [r6, #11]
    cmp r0, #1
    bne dc_check_none
    ldr r7, =DC_ENTRIES
    mov r8, #DC_COUNT
    mov r12, #0
dc_check_entry:
    ldr r0, [r7]
    cmp r0, r4
    beq dc_check_mine
    cmp r12, #0
    bne dc_check_next
    ldr r1, =DC_PHYS
    cmp r0, r1
    movhs r12, r7
    bhs dc_check_next
    ldr r1, =SE_PLAY
    add r1, r1, r0, lsl #4
    ldrb r1, [r1, #15]
    tst r1, #1
    moveq r12, r7
dc_check_next:
    add r7, r7, #32
    subs r8, r8, #1
    bne dc_check_entry
    mov r0, r12
    pop {r4, r5, r6, r7, r8, pc}
dc_check_mine:
    ldr r0, [r7, #4]
    ldr r1, [r5]
    cmp r0, r1
    ldreq r0, [r7, #8]
    ldreq r1, [r5, #4]
    cmpeq r0, r1
    ldreq r0, [r7, #12]
    ldreq r1, [r5, #8]
    cmpeq r0, r1
    ldreq r0, [r7, #16]
    ldreq r1, [r6, #4]
    cmpeq r0, r1
    movne r0, r7
    popne {r4, r5, r6, r7, r8, pc}
dc_check_none:
    mov r0, #0
    pop {r4, r5, r6, r7, r8, pc}
; r0 = a physical index with DECLICK, loaded; r1 = its entry: the moved points into it. START POINT between the sample's first
; frame and END POINT, END POINT between the moved start and the last frame, LOOP START between the two moved ones; a loop on the
; start or the end (one shot) stays there. The entry is marked unused while it changes, the note-on hook skips it then.
dc_update:
    push {r4, r5, r6, r7, r8, r9, r10, r11, lr}
    mov r4, r0
    mov r10, r1
    mvn r0, #0
    str r0, [r10]
    ldr r5, =SE_PLAY
    add r5, r5, r4, lsl #4
    ldr r1, =0x45C
    ldr r6, =SE_META
    mla r6, r1, r4, r6
    ldrb r0, [r6, #9]
    cmp r0, #1
    moveq r11, #4                   ; the frame's bytes: stereo 4, mono 2
    movne r11, #2
    ldr r7, [r5]
    ldr r8, [r5, #4]
    ldr r9, [r5, #8]
    str r7, [r10, #4]
    str r8, [r10, #8]
    str r9, [r10, #12]
    ldr r0, [r6, #4]
    str r0, [r10, #16]
    mov r0, r7                      ; the start
    ldr r1, [r6]
    add r2, r7, r9
    mov r3, r11
    bl dc_snap
    str r0, [r10, #20]
    mov r1, r0                      ; the end, up to the last frame
    ldr r2, [r6]
    ldr r3, [r6, #4]
    sub r12, r11, #1
    bic r3, r3, r12
    add r2, r2, r3
    sub r2, r2, r11
    add r0, r7, r9
    mov r3, r11
    bl dc_snap
    ldr r1, [r10, #20]
    sub r2, r0, r1
    str r2, [r10, #28]
    cmp r8, #0                      ; the loop
    moveq r0, r1
    beq dc_update_loop
    cmp r8, r9
    beq dc_update_loop
    mov r2, r0
    add r0, r7, r8
    mov r3, r11
    bl dc_snap
dc_update_loop:
    ldr r1, [r10, #20]
    sub r0, r0, r1
    str r0, [r10, #24]
    str r4, [r10]
    pop {r4, r5, r6, r7, r8, r9, r10, r11, pc}
; r0 = a point (DSP bytes), r1 the lowest and r2 the highest frame it may move to, r3 the frame's bytes -> r0 the frame it moves
; to. Reads the window through the firmware's DSP read (0xC004EDDC, the lock of its DSP port as the voice start's writes).
dc_snap:
    push {r4, r5, r6, r7, r8, r9, r10, r11, lr}
    sub sp, sp, #8
    mov r4, r0
    mov r11, r3
    sub r5, r4, r11, lsl #DC_WIN    ; r5 = the window's first frame
    cmp r5, r1
    movlt r5, r1
    add r6, r4, r11, lsl #DC_WIN    ; r6 = its last
    cmp r6, r2
    movgt r6, r2
    cmp r5, r6
    bgt dc_snap_keep
    cmp r5, r1                      ; r7: read from the frame before the window, unless that is outside the sample
    subgt r7, r5, r11
    movle r7, r5
    ldr r8, =DC_BUF
    sub r0, r8, r5
    add r0, r0, r7
    mov r1, r7
    add r2, r6, r11
    sub r2, r2, r7
    mov r2, r2, lsr #1
    bl 0xC004EDDC                   ; (buffer, DSP byte address, words)
    cmp r7, r5
    bne dc_snap_scan
    cmp r11, #4                     ; no frame before: the first frame stands for it, no sign change there
    ldreq r0, [r8]
    streq r0, [r8, #-4]
    ldrhne r0, [r8]
    strhne r0, [r8, #-2]
dc_snap_scan:
    mov r7, r8                      ; r7 the frame in the buffer, r5 its DSP address
    mvn r9, #0                      ; r9 the distance of the nearest crossing, r8 its frame
    mvn r10, #0                     ; r10 the smallest level, [sp] its frame, [sp, #4] its distance
    str r4, [sp]
    str r9, [sp, #4]
dc_snap_frame:
    ldrsh r0, [r7]
    sub r12, r7, r11
    ldrsh r1, [r12]
    cmp r11, #4
    ldrsheq r2, [r7, #2]
    ldrsheq r3, [r12, #2]
    movne r2, #0                    ; mono: the second channel is 0, it always crosses and adds nothing
    movne r3, #0
    eor r1, r1, r0                  ; negative: the sign changed from the frame before, or the frame is 0
    cmp r0, #0
    mvneq r1, #0
    eor r3, r3, r2
    cmp r2, #0
    mvneq r3, #0
    and r1, r1, r3
    subs r12, r5, r4
    rsblt r12, r12, #0
    cmp r1, #0
    bge dc_snap_level
    cmp r12, r9
    movlo r9, r12
    movlo r8, r5
dc_snap_level:
    cmp r0, #0
    rsblt r0, r0, #0
    cmp r2, #0
    rsblt r2, r2, #0
    add r0, r0, r2
    cmp r0, r10
    bhi dc_snap_next
    blo dc_snap_quiet
    ldr r1, [sp, #4]
    cmp r12, r1
    bhs dc_snap_next
dc_snap_quiet:
    mov r10, r0
    str r5, [sp]
    str r12, [sp, #4]
dc_snap_next:
    add r5, r5, r11
    add r7, r7, r11
    cmp r5, r6
    ble dc_snap_frame
    cmn r9, #1
    movne r0, r8
    ldreq r0, [sp]
    add sp, sp, #8
    pop {r4, r5, r6, r7, r8, r9, r10, r11, pc}
dc_snap_keep:
    mov r0, r4
    add sp, sp, #8
    pop {r4, r5, r6, r7, r8, r9, r10, r11, pc}
.pool
str_se_mono:
    .asciz "TURN MONO"
str_se_play:
    .asciz "stop PLAY"
str_se_declick:
    .asciz "DECLICK"
.align 4
se_tab:                         ; the firmware's tab text of SAMPLE EDIT, "Sample"
    .word 0xC00A5BBE
se_cat_texts:                   ; CATEGORY: the firmware's texts of the categories 0 to 17, the same places in red and Hacktribe
    .word 0xC00A6E06, 0xC00A6E0F, 0xC00A6E1A, 0xC00A6E21, 0xC00A6E29, 0xC00A6E30, 0xC00A6E38, 0xC00A6E41, 0xC00A6E48
    .word 0xC00A6E50, 0xC00A6E58, 0xC00A6E5D, 0xC00A6E62, 0xC00A6E68, 0xC00A6E70, 0xC00A6E79, 0xC00A6E80, 0xC00A6E86
