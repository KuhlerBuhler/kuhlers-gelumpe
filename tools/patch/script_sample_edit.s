; CATEGORY: the page of the BLECH menu (level 9, M_LEVEL_SE) that shows itself as page 3 of 11 of the firmware's SAMPLE EDIT, behind
; RENAME. The dial sets the category of the sample SAMPLE EDIT edits in the name table; EXPORT ALL SAMPLE writes it to e2sSample.all
; as it writes RENAME's name (docs/messungen/2026-11-21-sample-kategorie.md). The Sampler's builds only, the synth has
; script_sample_edit_none.s.
.equ SE_PAGE, 0xC0691278      ; the page SAMPLE EDIT shows (0 SELECT SAMPLE, 1 RENAME, 2 START POINT .. 9; above 9 its windows)
.equ SE_RESUME, 0xC0691280    ; byte: 1 makes screen 38 open on SE_PAGE, as after RENAME; 0 makes it start over
.equ SE_NAMES, 0xC047B08C     ; the name table, 32 bytes a slot: +0x10 the category (0 to 17), +0x12 the wave number (u16)
.equ SE_CATEGORIES, 18        ; the categories the firmware has texts for (se_cat_texts)
.equ SE_TAIL, 1               ; our pages behind PLAY LEVEL (SE_PAGE SE_LEVEL), before DELETE SAMPLE (SE_DELETE): ONE SHOT
.equ SE_LEVEL, 8
.equ SE_DELETE, 9
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
    moveq r1, #SE_TAIL
    beq se_out_page
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
; PLAY LEVEL, the pages behind them move up.
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
    add r2, r2, #1+SE_TAIL
    cmp r1, #2
    addge r1, r1, #1
    cmp r1, #SE_DELETE+1
    addge r1, r1, #SE_TAIL
    bx lr
; the counter on level 9 (r3 = MENU_STATE): CATEGORY page 3, ONE SHOT behind PLAY LEVEL (menu_counter_args)
menu_counter_se_level:
    ldr r1, [r3, #M_PAGE]
    cmp r1, #0
    moveq r1, #2
    addne r1, r1, #SE_LEVEL+1
    mov r2, #SE_PAGES+1+SE_TAIL
    pop {pc}
; level 9 has CATEGORY and the SE_TAIL pages behind PLAY LEVEL (menu_page_count)
menu_count_se:
    mov r0, #1+SE_TAIL
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
    cmp r1, #SE_TAIL
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
; CATEGORY: the dial steps the category byte in the name table, 0 to 17, and stops at the ends; the slot keeps it in RAM, EXPORT
; ALL SAMPLE writes it to e2sSample.all as RENAME's name. Nothing for a slot without a sample or an oscillator.
menu_value_se:
    ldr r0, [r6, #M_PAGE]
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
; level 9, a key (r6, menu_slot_keys): WRITE on ONE SHOT does what WRITE does on SAMPLE EDIT's own pages (0xC006F094 on screens
; 37 to 39): it posts the firmware's command 0x25, which keeps the points; EXIT without it gives the old ones back. Not while the
; firmware's byte 0xC0345EC4 says it is busy, as there. WRITE on CATEGORY saves the settings as before.
menu_keys_se:
    cmp r6, #0x0E
    bne menu_keys_done
    ldr r0, =MENU_STATE
    ldr r0, [r0, #M_PAGE]
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
.pool
se_tab:                         ; the firmware's tab text of SAMPLE EDIT, "Sample"
    .word 0xC00A5BBE
se_cat_texts:                   ; CATEGORY: the firmware's texts of the categories 0 to 17, the same places in red and Hacktribe
    .word 0xC00A6E06, 0xC00A6E0F, 0xC00A6E1A, 0xC00A6E21, 0xC00A6E29, 0xC00A6E30, 0xC00A6E38, 0xC00A6E41, 0xC00A6E48
    .word 0xC00A6E50, 0xC00A6E58, 0xC00A6E5D, 0xC00A6E62, 0xC00A6E68, 0xC00A6E70, 0xC00A6E79, 0xC00A6E80, 0xC00A6E86
