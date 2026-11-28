; BPM GLIDE (FEATURES > GLIDE CHAIN and GLIDE SWITCH, both OFF by default): the tempo glides to the stored tempo of the pattern
; that comes next, so the change does not jump. The same rules as the catalog plugin bpmglide (data/script/presets.mjs), which
; it replaces on this firmware:
; GLIDE CHAIN: while the pattern in RAM chains on to another one (Chain To, CHAIN MODE on in Global), the tempo glides from where
; it started over the steps the pattern plays (its length times Chain Repeat); the last step reaches the new tempo. STOP gives the
; pattern the tempo it started with.
; GLIDE SWITCH: once MENU confirms a pattern turned to on the dial while playing (NEXT:, script_read_next_pattern_glue), the tempo
; glides from where it is to that pattern's tempo over the steps left until the sequence end. A confirmed pattern wins over the
; chain; EXIT takes it back (the chain glides on, or the tempo returns to where it was); STOP sets that pattern's tempo, as the
; firmware loads it at STOP. A new confirmation starts again from the tempo of that moment.
; Once a frame it compares transport, the playing pattern and part 1's step with the last frame, the way script_events.s finds the plugin
; events, and sets the tempo through the call korg.tempo uses (script_tempo_glue), so the tempo is an unsaved change of the
; pattern in RAM until STOP. The pattern values come from script_read_pattern_value_glue (PATTERN_FIELDS of data/script/contract.mjs).
; With EXIT held at power-on menu_arm never runs and nothing of this runs.
.equ GL_INIT, 0                 ; 1 once the first frame took the transport, pattern and step; FF at power-on
.equ GL_TR, 4                   ; the transport, pattern and step of the last frame
.equ GL_PAT, 8
.equ GL_STEP, 12
.equ GL_FLAGS, 16               ; the bits FLAGS2_GLIDE_* of the last frame
.equ GL_PENDING, 20             ; 1: read the pattern in RAM at the next step (after PLAY or a pattern change)
.equ GL_LENGTH, 24              ; the steps of the pattern in RAM
.equ GL_LAPS, 28                ; the times the step counter went back to the start
.equ GL_LAST, 32                ; the step of the last step handled, -1 none
.equ GL_CHAIN, 36               ; 1 while the chain glides
.equ GL_BASE, 40                ; the chain: the tempo at its start, the target, the steps it takes, the laps at its start
.equ GL_TARGET, 44
.equ GL_TOTAL, 48
.equ GL_CHAIN_LAP, 52
.equ GL_NEXT, 56                ; the switch: the confirmed pattern (-1 none), 1 once the sequence end passed, the tempo at the
.equ GL_LANDED, 60              ; confirmation and that pattern's, the step of the confirmation, the steps it takes, the laps then
.equ GL_FROM, 64
.equ GL_TO, 68
.equ GL_FIRST, 72
.equ GL_SPAN, 76
.equ GL_SWITCH_LAP, 80
.equ GLIDE_SIZE, 84
.equ GL_FIELD_TEMPO, 0          ; PATTERN_FIELDS: tempo, length (bars), chainTo (-1 none), chainRepeat (at least 1)
.equ GL_FIELD_LENGTH, 2
.equ GL_FIELD_CHAIN_TO, 9
.equ GL_FIELD_REPEAT, 10

; Once a frame, past the first main screen. Keeps r4 to r11.
glide_frame:
    push {r4-r9, lr}
    ldr r0, =MENU_STATE
    ldr r1, [r0, #M_ON]
    cmp r1, #1
    bne glide_out
    ldrb r9, [r0, #MX_FLAGS2]
    and r9, r9, #FLAGS2_GLIDE
    ldr r4, =GLIDE
    ldr r5, =HW_TRANSPORT
    ldr r5, [r5]
    ldr r0, =SC_PLAYER_PTR          ; the pattern that plays (the player SC_PLAYER returns), not HW_PATTERN: that one follows the
    ldr r0, [r0]                    ; dial and EXIT; no player yet keeps the last one
    cmp r0, #0
    ldrne r6, [r0, #0x318]
    ldreq r6, [r4, #GL_PAT]
    ldr r7, =HW_STEP
    ldr r7, [r7]
    ldr r0, [r4, #GL_INIT]
    cmp r0, #1
    beq glide_menu
    mov r0, #0
    mov r1, #GL_PENDING
glide_clear:
    str r0, [r4, r1]
    add r1, r1, #4
    cmp r1, #GLIDE_SIZE
    blo glide_clear
    mov r0, #1
    str r0, [r4, #GL_INIT]
    str r0, [r4, #GL_PENDING]
    mov r0, #16
    str r0, [r4, #GL_LENGTH]
    str r0, [r4, #GL_TOTAL]
    str r0, [r4, #GL_SPAN]
    mvn r0, #0
    str r0, [r4, #GL_LAST]
    str r0, [r4, #GL_NEXT]
    b glide_store
glide_menu:
    ldr r8, [r4, #GL_FLAGS]
    eor r8, r8, r9
    tst r8, #FLAGS2_GLIDE_CHAIN
    beq glide_menu_switch
    tst r9, #FLAGS2_GLIDE_CHAIN     ; GLIDE CHAIN switched: OFF while the chain glides (no confirmation) gives back its start tempo
    bne glide_menu_rearm
    ldr r0, [r4, #GL_CHAIN]
    ldr r1, [r4, #GL_NEXT]
    cmp r0, #0
    beq glide_menu_rearm
    cmn r1, #1
    ldreq r0, [r4, #GL_BASE]
    bleq glide_set
glide_menu_rearm:
    mov r0, #0
    str r0, [r4, #GL_CHAIN]
    mov r0, #1
    str r0, [r4, #GL_PENDING]
glide_menu_switch:
    tst r8, #FLAGS2_GLIDE_SWITCH
    beq glide_transport
    tst r9, #FLAGS2_GLIDE_SWITCH
    bne glide_transport
    ldr r0, [r4, #GL_NEXT]
    cmn r0, #1
    blne glide_drop
glide_transport:
    ldr r0, [r4, #GL_TR]
    cmp r5, r0
    beq glide_pattern
    cmp r5, #1
    moveq r0, #1
    streq r0, [r4, #GL_PENDING]
    beq glide_pattern
    cmp r5, #0
    cmpne r5, #2
    bleq glide_stop
glide_pattern:
    ldr r0, [r4, #GL_PAT]
    cmp r6, r0
    beq glide_step
    mov r0, #1
    str r0, [r4, #GL_PENDING]
    mvn r0, #0
    str r0, [r4, #GL_NEXT]
    mov r0, #0
    str r0, [r4, #GL_LANDED]
glide_step:
    ldr r0, [r4, #GL_STEP]
    cmp r7, r0
    blne glide_on_step
glide_store:
    str r5, [r4, #GL_TR]
    str r6, [r4, #GL_PAT]
    str r7, [r4, #GL_STEP]
    str r9, [r4, #GL_FLAGS]
glide_out:
    pop {r4-r9, pc}

; STOP: a confirmed pattern's tempo, else the chain's start tempo; everything reads the pattern again at the next step.
glide_stop:
    push {lr}
    ldr r1, [r4, #GL_NEXT]
    ldr r2, [r4, #GL_CHAIN]
    cmn r1, #1
    ldrne r0, [r4, #GL_TO]
    bne glide_stop_set
    cmp r2, #0
    beq glide_stop_reset
    ldr r0, [r4, #GL_BASE]
glide_stop_set:
    bl glide_set
glide_stop_reset:
    mov r0, #0
    str r0, [r4, #GL_CHAIN]
    str r0, [r4, #GL_LANDED]
    mvn r0, #0
    str r0, [r4, #GL_NEXT]
    str r0, [r4, #GL_LAST]
    mov r0, #1
    str r0, [r4, #GL_PENDING]
    pop {pc}

; r7 = the new step of part 1, r9 = the switches. Counts the laps, reads the pattern in RAM when it is due, follows the
; confirmation and glides: the switch first, else the chain.
glide_on_step:
    push {r8, lr}
    ldr r0, [r4, #GL_LAST]
    mov r8, #0
    cmp r0, #0
    blt glide_laps
    cmp r7, r0
    movlt r8, #1
glide_laps:
    ldr r0, [r4, #GL_LAPS]
    add r0, r0, r8
    str r0, [r4, #GL_LAPS]
    str r7, [r4, #GL_LAST]
    ldr r0, [r4, #GL_PENDING]
    cmp r0, #0
    blne glide_arm
    tst r9, #FLAGS2_GLIDE_SWITCH
    blne glide_follow
    ldr r0, [r4, #GL_NEXT]
    cmn r0, #1
    beq glide_on_chain
    ldr r1, [r4, #GL_LAPS]          ; switch: done = this lap ? step - first + 1 : span, at most span
    ldr r2, [r4, #GL_SWITCH_LAP]
    ldr r3, [r4, #GL_SPAN]
    cmp r1, r2
    movne r0, r3
    ldreq r0, [r4, #GL_FIRST]
    subeq r0, r7, r0
    addeq r0, r0, #1
    ldr r1, [r4, #GL_FROM]
    ldr r2, [r4, #GL_TO]
    bl glide_between
    pop {r8, pc}
glide_on_chain:
    ldr r0, [r4, #GL_CHAIN]
    cmp r0, #0
    popeq {r8, pc}
    ldr r0, [r4, #GL_LAPS]          ; chain: done = (laps - lap at its start) * length + step + 1, at most total
    ldr r1, [r4, #GL_CHAIN_LAP]
    sub r0, r0, r1
    ldr r1, [r4, #GL_LENGTH]
    mul r2, r0, r1
    add r0, r2, r7
    add r0, r0, #1
    ldr r3, [r4, #GL_TOTAL]
    ldr r1, [r4, #GL_BASE]
    ldr r2, [r4, #GL_TARGET]
    bl glide_between
    pop {r8, pc}

; r0 = steps done (at most r3), r1 = the tempo at the start, r2 = the tempo at the end, r3 = the steps it takes: sets
; start + (end - start) * done / steps, the quotient cut toward 0 as the plugin's division does.
glide_between:
    push {r4, r5, lr}
    cmp r0, r3
    movgt r0, r3
    mov r4, r1
    sub r1, r2, r1
    mul r5, r1, r0
    mov r0, r5
    mov r1, r3
    bl glide_divide
    add r0, r4, r0
    pop {r4, r5, lr}

; r0 tempo in tenths of a BPM: set unless it already is (korg.tempo's call). Keeps r4 to r11.
glide_set:
    ldr r1, =HW_TEMPO
    ldr r1, [r1]
    cmp r0, r1
    bxeq lr
    b script_tempo_glue

; r0 numerator, r1 denominator above 0 -> r0 the quotient cut toward 0. Clobbers r1 to r3 and r12.
glide_divide:
    mov r12, r0
    cmp r0, #0
    rsblt r0, r0, #0
    mov r2, #0
    mov r3, #32
glide_divide_bit:
    movs r0, r0, lsl #1
    adc r2, r2, r2
    cmp r2, r1
    subhs r2, r2, r1
    adcs r0, r0, #0
    subs r3, r3, #1
    bne glide_divide_bit
    cmp r12, #0
    rsblt r0, r0, #0
    bx lr

; r0 pattern (-1 the one in RAM), r1 the field (GL_FIELD_*) -> its value.
glide_value:
    mov r2, r1
    mvn r1, #0
    b script_read_pattern_value_glue

; The first step after PLAY or a pattern change: the firmware has the pattern in RAM now. Its length, and with GLIDE CHAIN on,
; CHAIN MODE on and a Chain To, the chain from the tempo now to that pattern's over length times Chain Repeat.
glide_arm:
    push {r5, r6, lr}
    mov r0, #0
    str r0, [r4, #GL_PENDING]
    str r0, [r4, #GL_CHAIN]
    mvn r0, #0
    mov r1, #GL_FIELD_LENGTH
    bl glide_value
    mov r0, r0, lsl #4
    str r0, [r4, #GL_LENGTH]
    tst r9, #FLAGS2_GLIDE_CHAIN
    beq glide_arm_out
    ldr r0, =HW_GLOBAL
    ldrb r0, [r0, #HW_GLOBAL_CHAIN_MODE]
    cmp r0, #0
    beq glide_arm_out
    mvn r0, #0
    mov r1, #GL_FIELD_CHAIN_TO
    bl glide_value
    cmp r0, #0
    blt glide_arm_out
    mov r1, #GL_FIELD_TEMPO
    bl glide_value
    str r0, [r4, #GL_TARGET]
    ldr r5, =HW_TEMPO
    ldr r5, [r5]
    str r5, [r4, #GL_BASE]
    mvn r0, #0
    mov r1, #GL_FIELD_REPEAT
    bl glide_value
    ldr r1, [r4, #GL_LENGTH]
    mul r2, r0, r1
    str r2, [r4, #GL_TOTAL]
    ldr r0, [r4, #GL_LAPS]
    str r0, [r4, #GL_CHAIN_LAP]
    ldr r0, [r4, #GL_TARGET]
    cmp r0, r5
    movne r0, #1
    moveq r0, #0
    str r0, [r4, #GL_CHAIN]
glide_arm_out:
    pop {r5, r6, pc}

; r7 = the step, r8 = 1 when the counter went back to the start. A new confirmed number starts the glide from the tempo now over
; this step and the ones left in the pattern; a confirmation gone before the sequence end was taken back (EXIT).
glide_follow:
    push {lr}
    bl script_read_next_pattern_glue
    cmp r0, #0
    blt glide_follow_none
    ldr r1, [r4, #GL_NEXT]
    cmp r0, r1
    popeq {pc}
    str r0, [r4, #GL_NEXT]
    mov r1, #GL_FIELD_TEMPO
    bl glide_value
    str r0, [r4, #GL_TO]
    mov r0, #0
    str r0, [r4, #GL_LANDED]
    ldr r0, =HW_TEMPO
    ldr r0, [r0]
    str r0, [r4, #GL_FROM]
    str r7, [r4, #GL_FIRST]
    ldr r0, [r4, #GL_LENGTH]
    sub r0, r0, r7
    cmp r0, #1
    movlt r0, #1
    str r0, [r4, #GL_SPAN]
    ldr r0, [r4, #GL_LAPS]
    str r0, [r4, #GL_SWITCH_LAP]
    pop {pc}
glide_follow_none:
    ldr r0, [r4, #GL_NEXT]
    cmn r0, #1
    popeq {pc}
    ldr r0, [r4, #GL_LANDED]
    cmp r0, #0
    popne {pc}
    cmp r8, #0
    movne r0, #1
    strne r0, [r4, #GL_LANDED]
    popne {pc}
    pop {lr}

; The confirmation is gone: without a chain the tempo goes back to where it was at the confirmation.
glide_drop:
    push {lr}
    ldr r0, [r4, #GL_CHAIN]
    cmp r0, #0
    ldreq r0, [r4, #GL_FROM]
    bleq glide_set
    mvn r0, #0
    str r0, [r4, #GL_NEXT]
    pop {pc}
.pool
glide_end:
