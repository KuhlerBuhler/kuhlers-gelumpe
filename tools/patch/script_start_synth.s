script_card_hook:
    push {r0-r12, lr}
    .word 0xE10FC000
    push {r12, lr}
    ldr r0, =PANEL
    ldr r0, [r0]
    cmp r0, #0
    beq synth_start_native
    cmn r0, #1
    beq synth_start_native
    ldr r1, [r0, #0x18]
    tst r1, #KILL_MASK
    bne synth_start_native
    ldrb r1, [r0, #0x22]
    cmp r1, #0
    bne synth_start_native
    ldrb r1, [r0, #0x20]
    cmp r1, #0
    bne synth_start_native
    bl menu_arm_load
    bl migrate_start
    ldr r0, =HOOK_RUNTIME
    bl blechy_boot
    ldr r0, =HOOK_RUNTIME
    bl script_card_load
    bl menu_recount
synth_start_native:
    pop {r12, lr}
    .word 0xE12FF00C
    pop {r0-r12, lr}
    ldrb r3, [r4, #4]
    ldr pc, =0xC0028174
.pool
script_card_wrapper_end:


; ---- the backlight colour at power-on: the hook of this build, the rest is script_boot_light.s
.equ FLASH_GET, 0xC0026DAC      ; the flash object (it exists from about 62 ms)
.equ FLASH_READ, 0xC0026DE0     ; (object, destination, address, length)

; 0xC0025E48 in the start, `cmp r0, r3`: right behind the firmware's first flash read (the mark at 0x220000, about 65 ms) on the
; way of the normal start. The blue draws its start image earlier (45 ms) and keeps it until about 396 ms, so the colour comes
; while it is shown. With EXIT held, a panel update or no valid Globals in the flash nothing happens.
boot_light_hook:
    push {lr}
    bl boot_light_set
    pop {lr}
    cmp r0, r3
    ldr pc, =0xC0025E4C
.pool
