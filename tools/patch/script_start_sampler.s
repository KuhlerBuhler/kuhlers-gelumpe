; Boot loader for e2sPlugin.all (SD:KORG/blechtribe/Plugin). The wrapper replaces
; `add r0, sp, #4` at 0xC0038D68, right after the method that loads e2sSample.all.

; The first instruction of the command that loads e2sSample.all (0xC0038D34, `mov r3, #0`): runs before the sample loader, which is
; the 1.1 seconds of the start in which the window "Loading" is up. The card is mounted long before (the start's question for the file,
; 0xC0035440 at 0xC002AE60, mounts it at about 86 ms) and the panel object exists, so the menu is armed and its settings are read here:
; the look (backlight colour, bottom LEDs, display polarity) holds from about 350 ms on and through the samples loading, not only after
; them. Reading the card earlier, behind that question in the start task (0xC002AE68, about 123 ms), was tried and does not work: the
; first file open there waits for the card driver forever (measured, docs/messungen/2026-10-16-blech-look-frueh.md).
script_early_hook:
    push {r0-r12, lr}
    .word 0xE10FC000 ; mrs r12, cpsr
    push {r12, lr}
    bl menu_arm_load
    bl migrate_start
    pop {r12, lr}
    .word 0xE12FF00C ; msr cpsr_cxsf, r12
    pop {r0-r12, lr}
    mov r3, #0
    ldr pc, =0xC0038D38
.pool
script_early_end:

script_card_hook:
    push {r0-r12, lr}
    .word 0xE10FC000 ; mrs r12, cpsr
    push {r12, lr}
    bl menu_arm_load
    ldr r0, =HOOK_RUNTIME
    bl blechy_boot
    ldr r0, =HOOK_RUNTIME
    bl script_card_load
    bl fx_card_load
    bl menu_recount
    pop {r12, lr}
    .word 0xE12FF00C ; msr cpsr_cxsf, r12
    pop {r0-r12, lr}
    add r0, sp, #4
    ldr pc, =0xC0038D6C
.pool
script_card_wrapper_end:


; ---- the backlight colour at power-on (docs/messungen/2026-10-29-hintergrundlicht-beim-start.md)
; The pins the colour lights (M_BL_ON) are kept in Global byte 250 (BOOT_SLOT, the numbering of bytes 247 and 248; in the flash it is byte 246 of the block): 0x80 plus the pins, 0 (or any other
; value) is the stock white. The firmware saves the Globals itself (switch-off, WRITE on Global); BLECH only sets the byte in RAM, when
; the settings are read and when they are written. A colour between the levels needs the PWM of the armed menu: until then the pins
; of the colour light fully.
.equ BOOT_SLOT, 250             ; *GLOBALS_PTR + 250 is byte 246 of the block in the flash (the object has a word in front)
.equ BOOT_FLASH, 0x2300F4       ; Global bytes 244 to 255 in the flash, the last word is the mark GLED
.equ BOOT_GLED, 0x44454C47
.equ FLASH_GET, 0xC0029A40      ; the flash object (it exists from about 56 ms)
.equ FLASH_READ, 0xC0029A74     ; (object, destination, address, length)

; 0xC00289D8 in the start, `cmp r0, #0x124`: right behind the firmware's first flash read (the mark at 0x220000, about 59 ms) on the
; way of the normal start (the start modes branch off before). The held keys are known and the flash answers; the start image is not
; drawn yet (59.3 ms). With EXIT held, a panel update or no valid Globals in the flash nothing happens.
boot_light_hook:
    push {r0-r5, r12, lr}
    sub sp, sp, #16
    ldr r4, =PANEL
    ldr r4, [r4]
    cmp r4, #0
    beq boot_light_out
    cmn r4, #1
    beq boot_light_out
    ldr r1, [r4, #0x18]
    tst r1, #KILL_MASK
    bne boot_light_out
    ldrb r1, [r4, #0x22]
    cmp r1, #0
    bne boot_light_out
    bl FLASH_GET
    mov r1, sp
    ldr r2, =BOOT_FLASH
    mov r3, #12
    bl FLASH_READ
    ldr r0, [sp, #8]
    ldr r1, =BOOT_GLED
    cmp r0, r1
    bne boot_light_out
    ldrb r0, [sp, #2]
    and r1, r0, #0xC7
    cmp r1, #0x80
    bne boot_light_out
    ldr r1, =BL_DIM_FLAG
    ldrb r1, [r1]
    cmp r1, #0
    bne boot_light_out
    and r4, r0, #0x38
    ldr r0, =GPIO_BASE
    mov r1, #0
    mov r2, #3
    eor r3, r4, #0x38
    bl GPIO_WRITE
    ldr r0, =GPIO_BASE
    mov r1, #1
    mov r2, #3
    mov r3, r4
    bl GPIO_WRITE
boot_light_out:
    add sp, sp, #16
    pop {r0-r5, r12, lr}
    cmp r0, #0x124
    ldr pc, =0xC00289DC
.pool

; The firmware's light calls before the menu is armed (about 143 and 304 ms, bl_set_red and the others): a channel the boot colour
; keeps dark stays off. r1 = 1 on, r2 = the channel's pin -> r1; clobbers r3, r12.
boot_light_keep:
    cmp r1, #0
    bxeq lr
    ldr r3, =BL_DIM_FLAG
    ldrb r3, [r3]
    cmp r3, #0
    bxne lr
    ldr r3, =PANEL
    ldr r3, [r3]
    cmp r3, #0
    bxeq lr
    cmn r3, #1
    bxeq lr
    ldr r12, [r3, #0x18]
    tst r12, #KILL_MASK
    bxne lr
    ldrb r12, [r3, #0x22]
    cmp r12, #0
    bxne lr
    ldr r3, =GLOBALS_PTR
    ldr r3, [r3]
    cmp r3, #0
    bxeq lr
    ldrb r3, [r3, #BOOT_SLOT]
    and r12, r3, #0xC7
    cmp r12, #0x80
    bxne lr
    tst r3, r2
    moveq r1, #0
    bx lr
bl_red_boot:
    push {lr}
    mov r2, #0x08
    bl boot_light_keep
    pop {lr}
    b bl_red_go
bl_green_boot:
    push {lr}
    mov r2, #0x10
    bl boot_light_keep
    pop {lr}
    b bl_green_go
bl_blue_boot:
    push {lr}
    mov r2, #0x20
    bl boot_light_keep
    pop {lr}
    b bl_blue_go

; The menu is armed without a settings file: a colour the start set goes back to the stock white (the menu's M_BL_ON is 0x38).
boot_light_settle:
    ldr r1, =GLOBALS_PTR
    ldr r1, [r1]
    cmp r1, #0
    bxeq lr
    ldrb r0, [r1, #BOOT_SLOT]
    and r1, r0, #0xC7
    cmp r1, #0x80
    bxne lr
    cmp r0, #0xB8
    bxeq lr
    b menu_backlight_now

; r0 = the pins the backlight colour lights (M_BL_ON): into Global byte 250. Clobbers r0, r1.
boot_light_save:
    ldr r1, =GLOBALS_PTR
    ldr r1, [r1]
    cmp r1, #0
    bxeq lr
    and r0, r0, #0x38
    orr r0, r0, #0x80
    strb r0, [r1, #BOOT_SLOT]
    bx lr
.pool
boot_light_end:
