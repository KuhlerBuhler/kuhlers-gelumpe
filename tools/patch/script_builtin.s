; Blechy, the app built into BLECH. His compiled block (data/script/blechy-block.hex, made by tools/blechy-build.mjs) lies in the
; firmware image at BLECHY_BLOCK and stays there: the loader (script_load_block_ex) keeps it out of the pool and only his entry and
; his variables take room in it. He is the first entry of the runtime's list and record 0 of the app table, in a group no menu lists.
; A block that lies outside the pool is how everything else tells him from a plugin of the card (the PLUGINS pages, EXPORT ALL, the
; counts, the store, the LED hold), so the card never sees him and he cannot be switched off or exported.
; He has no screen of his own: the page after Event in the menu ring is level 3 of the BLECH screen, and blechy_follow opens him
; while the firmware shows it and closes him when it shows anything else, the way EXIT closes an app.

; r0 = runtime -> r0 = 1 when the menu is armed (EXIT was not held at power-on) and he was set up, 0 when nothing was done.
; Sets the runtime up from nothing, loads his block, registers him as app 0, runs his start body and arms the runtime, so he
; lives with no card and no plugin file. Called from the card hook wrapper before the loader reads the card, and again where the
; loader throws away everything it loaded (a damaged file): then the runtime starts over with him alone.
blechy_boot:
    push {r4, r5, lr}
    mov r4, r0
    ldr r0, =MENU_STATE
    ldr r0, [r0, #M_ON]
    cmp r0, #1
    movne r0, #0
    bne boot_out
    mov r0, r4
    ldr r1, =HOOK_POOL
    ldr r2, =SCRIPT_POOL_BYTES
    ldr r12, =VM_SCRIPT_RUNTIME_INIT
    blx r12
    mov r0, r4
    ldr r1, =BLECHY_BLOCK
    ldr r2, =BLECHY_SIZE
    mov r3, #1
    ldr r12, =VM_SCRIPT_LOAD_BLOCK_EX
    blx r12
    cmp r0, #0
    bne boot_failed
    mov r5, r1
    ldr r2, =APP_STATE
    add r0, r2, #SCRIPT_APPS_TABLE
    str r5, [r0, #SCRIPT_APP_ENTRY]
    ldr r1, [r5, #SCRIPT_ENTRY_BLOB]
    add r1, r1, #HDR_NAME
    str r1, [r0, #SCRIPT_APP_NAME]
    mov r1, #SCRIPT_APPS_BUILTIN_GROUP
    str r1, [r0, #SCRIPT_APP_GROUP]
    mov r1, #1
    str r1, [r2, #SCRIPT_APPS_COUNT]
    mov r0, r4
    mov r1, r5
    mov r2, #EV_START
    ldr r3, =HOOK_INPUT
    ldr r12, =VM_SCRIPT_RUN_EVENT
    blx r12
    mov r0, #1
    str r0, [r4, #RT_ARMED]
    b boot_out
boot_failed:
    mov r0, r4
    ldr r1, =HOOK_POOL
    ldr r2, =SCRIPT_POOL_BYTES
    ldr r12, =VM_SCRIPT_RUNTIME_INIT
    blx r12
    mov r0, #1
boot_out:
    pop {r4, r5, pc}
.pool
blechy_boot_end:

; r4 = runtime, kept. Once per frame, from the frame hook before the apps are looked at: opens him (script_app_open, so he draws
; and gets the open event) when the firmware shows his page, and closes him (the close event, the display is the firmware's again)
; when it shows anything else. A plugin app that is open is none of its business. Clobbers r0 to r3.
blechy_follow:
    push {r5, lr}
    ldr r5, =APP_STATE
    ldr r0, =MENU_STATE
    ldr r1, [r0, #M_ON]
    cmp r1, #1
    bne follow_away
    ldr r1, =SCREEN_MANAGER
    ldr r1, [r1]
    cmp r1, #0
    beq follow_away
    cmn r1, #1
    beq follow_away
    ldr r1, [r1, #0x2c]
    cmp r1, #MENU_SCREEN
    bne follow_away
    ldr r1, [r0, #M_LEVEL]
    cmp r1, #M_LEVEL_BLECHY
    bne follow_away
    ldr r1, [r5, #SCRIPT_APPS_OPEN]
    cmp r1, #0
    bne follow_out
    ldr r1, [r5, #SCRIPT_APPS_TABLE+SCRIPT_APP_GROUP]
    cmp r1, #SCRIPT_APPS_BUILTIN_GROUP
    bne follow_out
    mov r0, #0
    bl script_app_open
    b follow_out
follow_away:
    bl blechy_leave
follow_out:
    pop {r5, pc}
.pool

; Closes him when he is the open app (a plugin app that is open is none of its business); the close asks the firmware for a whole
; new frame. The menu calls it too, the moment EDIT leaves his page and before the next page draws: without it that page drew only its
; widgets over his last picture, and his head and feet stayed on SYNC GROUP on a blue with BLECH 1.3.3 (Discord report 26.10.).
; Clobbers r0 to r3.
blechy_leave:
    ldr r1, =APP_STATE
    ldr r1, [r1, #SCRIPT_APPS_OPEN]
    cmp r1, #0
    bxeq lr
    ldr r2, [r1, #SCRIPT_ENTRY_BLOB]
    ldr r3, =HOOK_POOL
    cmp r2, r3
    bxhs lr
    b script_app_close
.pool
