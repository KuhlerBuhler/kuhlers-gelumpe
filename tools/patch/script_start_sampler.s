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
    bl menu_recount
    pop {r12, lr}
    .word 0xE12FF00C ; msr cpsr_cxsf, r12
    pop {r0-r12, lr}
    add r0, sp, #4
    ldr pc, =0xC0038D6C
.pool
script_card_wrapper_end:

