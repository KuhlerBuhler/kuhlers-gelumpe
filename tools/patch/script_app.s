; Apps (korg.app): a plugin with a screen of its own. The runtime keeps a small table behind its other areas
; (APP_STATE): the open app (its script entry, 0 when none), the count and one record per app (script entry,
; pointer to its name text in the block, group). Only the open app draws on the display and gets `frame`;
; the BLECH menu lists the apps by group and opens one; EXIT always closes it, in the input filter, before any
; plugin sees the key.
.equ APP_STATE, HOOK_RUNTIME+RT_APPS
; The screen tick (0xC006F178, called with 0xC06C2220) clears and redraws the whole screen when the byte at +0x4c is set. The
; firmware draws its widgets only where something changed, so when the display is given back this byte makes the main
; screen whole again at once (measured: the display is then equal to one that never had an app).
.equ UI_REDRAW, 0xC06C226C

; korg.app(name, group): r0 = name text, r1 = group text -> r0 = the app's id, -1 when all places are taken,
; r1 = error code. Declared twice by one script it is the same app. A group other than GAMES or TOOLS and an
; empty name end the script with API_ARG (the compiler refuses both before).
script_app_glue:
    push {r4-r8, lr}
    mov r4, r0
    mov r5, r1
    ldr r6, =APP_STATE
    ldr r7, =HOOK_RUNTIME
    ldr r7, [r7, #RT_ENTRY]
    ldr r2, [r6, #SCRIPT_APPS_COUNT]
    mov r3, #0
app_glue_find:
    cmp r3, r2
    bhs app_glue_new
    add r0, r6, #SCRIPT_APPS_TABLE
    add r0, r0, r3, lsl #3
    add r0, r0, r3, lsl #2
    ldr r1, [r0]
    cmp r1, r7
    moveq r0, r3
    beq app_glue_done
    add r3, r3, #1
    b app_glue_find
app_glue_new:
    mov r0, r5
    ldr r1, =str_group_games
    bl menu_streq
    cmp r0, #0
    movne r8, #SCRIPT_APP_GROUP_GAMES
    bne app_glue_group_ok
    mov r0, r5
    ldr r1, =str_group_tools
    bl menu_streq
    cmp r0, #0
    beq app_glue_bad
    mov r8, #SCRIPT_APP_GROUP_TOOLS
app_glue_group_ok:
    ldrb r0, [r4]
    cmp r0, #0
    beq app_glue_bad
    ldr r2, [r6, #SCRIPT_APPS_COUNT]
    mov r3, #SCRIPT_APPS_MAX
    ldr r1, [r6, #SCRIPT_APPS_TABLE+SCRIPT_APP_GROUP]
    cmp r1, #SCRIPT_APPS_BUILTIN_GROUP
    addeq r3, r3, #SCRIPT_APPS_BUILTIN
    cmp r2, r3
    bhs app_glue_full
    add r0, r6, #SCRIPT_APPS_TABLE
    add r0, r0, r2, lsl #3
    add r0, r0, r2, lsl #2
    str r7, [r0]
    str r4, [r0, #4]
    str r8, [r0, #8]
    mov r3, r2
    add r2, r2, #1
    str r2, [r6, #SCRIPT_APPS_COUNT]
    push {r3}
    bl menu_recount
    pop {r0}
    b app_glue_done
; all places are taken: the import page says so (M_STATUS 0x37, menu_import keeps it)
app_glue_full:
    ldr r1, =MENU_STATE
    mov r0, #0x37
    str r0, [r1, #M_STATUS]
    mvn r0, #0
app_glue_done:
    mov r1, #ERR_OK
    pop {r4-r8, pc}
app_glue_bad:
    mov r0, #0
    mov r1, #ERR_API_ARG
    pop {r4-r8, pc}
.pool

; korg.display.take() -> r0 = 1 when the running plugin owns the display now. Only a plugin that is no app, only while the main
; screen shows and nobody owns the display; EXIT ends it like it closes an app. The picture is cleared for it.
script_display_take_glue:
    push {r4, lr}
    ldr r4, =APP_STATE
    ldr r0, =HOOK_RUNTIME
    ldr r0, [r0, #RT_ENTRY]
    ldr r1, [r4, #SCRIPT_APPS_OPEN]
    cmp r1, r0
    moveq r0, #1
    beq display_take_done
    cmp r1, #0
    bne display_take_refuse
    bl script_app_closed
    cmp r0, #0
    bne display_take_refuse
    ldr r1, =SCREEN_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    beq display_take_refuse
    cmn r1, #1
    beq display_take_refuse
    ldr r1, [r1, #0x2c]
    cmp r1, #1
    bne display_take_refuse
    ldr r0, =HOOK_RUNTIME
    ldr r1, [r0, #RT_ENTRY]
    str r1, [r4, #SCRIPT_APPS_OPEN]
    bl display_clear
    ldr r0, =HOOK_RUNTIME
    mov r1, #1
    str r1, [r0, #SCRIPT_CONTROL_DISPLAY_ACTIVE]
    mov r0, #1
    b display_take_done
display_take_refuse:
    mov r0, #0
display_take_done:
    mov r1, #ERR_OK
    pop {r4, pc}
.pool

; korg.display.release(): the owner gives the display back (no `close` event for its own call).
script_display_release_glue:
    ldr r0, =HOOK_RUNTIME
    ldr r1, [r0, #RT_ENTRY]
    ldr r2, =APP_STATE
    ldr r3, [r2, #SCRIPT_APPS_OPEN]
    cmp r3, r1
    moveq r3, #0
    streq r3, [r2, #SCRIPT_APPS_OPEN]
    ldreq r2, =UI_REDRAW
    moveq r3, #1
    strbeq r3, [r2]
    mov r0, #0
    mov r1, #ERR_OK
    bx lr
.pool

; r0 = script entry -> r0 = 1 when it is an app and not the open one (it gets no `frame`), else 0. Clobbers r1 to r3, r12.
script_app_closed:
    ldr r1, =APP_STATE
    ldr r2, [r1, #SCRIPT_APPS_COUNT]
    mov r3, #0
app_closed_loop:
    cmp r3, r2
    movhs r0, #0
    bxhs lr
    add r12, r1, #SCRIPT_APPS_TABLE
    add r12, r12, r3, lsl #3
    add r12, r12, r3, lsl #2
    ldr r12, [r12]
    cmp r12, r0
    beq app_closed_found
    add r3, r3, #1
    b app_closed_loop
app_closed_found:
    ldr r2, [r1, #SCRIPT_APPS_OPEN]
    cmp r2, r0
    movne r0, #1
    moveq r0, #0
    bx lr
.pool

; r0 = index in the app table -> r0 = 1 when the app is open now. The display is cleared for it and it gets `open`;
; the caller then switches the firmware to its main screen. Needs an armed plugin and no app open.
script_app_open:
    push {r4-r6, lr}
    ldr r4, =APP_STATE
    ldr r2, [r4, #SCRIPT_APPS_COUNT]
    cmp r0, r2
    bhs app_open_fail
    ldr r1, [r4, #SCRIPT_APPS_OPEN]
    cmp r1, #0
    bne app_open_fail
    add r5, r4, #SCRIPT_APPS_TABLE
    add r5, r5, r0, lsl #3
    add r5, r5, r0, lsl #2
    ldr r5, [r5]
    ldr r1, [r5, #SCRIPT_ENTRY_STATE]
    cmp r1, #SCRIPT_STATE_ARMED
    bne app_open_fail
    str r5, [r4, #SCRIPT_APPS_OPEN]
    mov r0, #SCRIPT_APPS_OPEN_GRACE
    str r0, [r4, #SCRIPT_APPS_GRACE]
    bl display_clear
    ldr r6, =HOOK_RUNTIME
    mov r0, #1
    str r0, [r6, #SCRIPT_CONTROL_DISPLAY_ACTIVE]
    mov r0, #EV_OPEN
    mov r1, r5
    bl app_post
    mov r0, #1
    pop {r4-r6, pc}
app_open_fail:
    mov r0, #0
    pop {r4-r6, pc}
.pool

; Closes the open app, if any: it gets `close` and the display is the firmware's again. Called from the input filter
; (EXIT), the frame hook (the main screen is gone) and blechy_leave (the menu leaves his page). Preserves r4 to r11.
script_app_close:
    push {r4, lr}
    ldr r4, =APP_STATE
    ldr r1, [r4, #SCRIPT_APPS_OPEN]
    cmp r1, #0
    beq app_close_done
    mov r0, #0
    str r0, [r4, #SCRIPT_APPS_OPEN]
    ldr r2, =UI_REDRAW
    mov r3, #1
    strb r3, [r2]
    mov r0, #EV_CLOSE
    bl app_post
app_close_done:
    pop {r4, pc}
.pool

; r0 = event (open or close), r1 = the app's script entry: puts it in the ring for that script only.
app_post:
    push {lr}
    sub sp, sp, #16
    str r0, [sp]
    str r1, [sp, #4]
    mov r0, #0
    str r0, [sp, #8]
    str r0, [sp, #12]
    ldr r0, =HOOK_RUNTIME
    mov r1, sp
    bl script_ring_post
    add sp, sp, #16
    pop {pc}
.pool

; r1 = j -> r1 = the table index of the j-th app in menu order (GAMES first, then TOOLS, each as declared).
app_nth:
    push {r2-r5}
    ldr r2, =APP_STATE
    ldr r3, [r2, #SCRIPT_APPS_COUNT]
    cmp r3, #SCRIPT_APPS_SLOTS
    movhi r3, #0
    mov r4, #0
app_nth_group:
    mov r5, #0
app_nth_loop:
    cmp r5, r3
    bhs app_nth_next
    add r12, r2, #SCRIPT_APPS_TABLE
    add r12, r12, r5, lsl #3
    add r12, r12, r5, lsl #2
    ldr r12, [r12, #SCRIPT_APP_GROUP]
    cmp r12, r4
    bne app_nth_skip
    cmp r1, #0
    moveq r1, r5
    beq app_nth_done
    sub r1, r1, #1
app_nth_skip:
    add r5, r5, #1
    b app_nth_loop
app_nth_next:
    add r4, r4, #1
    cmp r4, #2
    blo app_nth_group
    mov r1, #0
app_nth_done:
    pop {r2-r5}
    bx lr
.pool

; r0 = group (0 GAMES, 1 TOOLS) -> r0 = how many apps it has (0 while the runtime is not set up: its area reads FF then). Clobbers r1 to r3, r12.
app_count:
    push {r4}
    ldr r1, =APP_STATE
    ldr r2, [r1, #SCRIPT_APPS_COUNT]
    cmp r2, #SCRIPT_APPS_SLOTS
    movhi r2, #0
    mov r3, #0
    mov r4, #0
app_count_loop:
    cmp r3, r2
    bhs app_count_done
    add r12, r1, #SCRIPT_APPS_TABLE
    add r12, r12, r3, lsl #3
    add r12, r12, r3, lsl #2
    ldr r12, [r12, #SCRIPT_APP_GROUP]
    cmp r12, r0
    addeq r4, r4, #1
    add r3, r3, #1
    b app_count_loop
app_count_done:
    mov r0, r4
    pop {r4}
    bx lr
.pool

str_group_games:
    .asciz "GAMES"
str_group_tools:
    .asciz "TOOLS"
.align 4
.pool
