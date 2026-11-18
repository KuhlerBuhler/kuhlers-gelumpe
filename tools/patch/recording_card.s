; Pending SD settings requests contain no view pointer and keep their SD destination.
nr_defer:
    push {r4-r6, lr}
    mov r4, r0
    bl nr_init
    mov r5, r0
    .word 0xE10F6000                 ; mrs r6, cpsr
    orr r1, r6, #0xC0
    .word 0xE121F001                 ; msr cpsr_c, r1
    ldr r1, [r5, #NR_DEFERRED]
    orr r1, r1, r4
    str r1, [r5, #NR_DEFERRED]
    .word 0xE121F006                 ; msr cpsr_c, r6
    pop {r4-r6, pc}

; UI task, after the recorder releases its resources and the card's normal screen guard permits access.
nr_card_flush:
    push {r4-r6, lr}
    bl nr_init
    mov r4, r0
    ldr r0, [r4, #NR_DEFERRED]
    cmp r0, #0
    beq nr_card_flush_done
    bl data_screen
    bne nr_card_flush_done
    .word 0xE10F6000                 ; mrs r6, cpsr
    orr r1, r6, #0xC0
    .word 0xE121F001                 ; msr cpsr_c, r1
    ldr r5, [r4, #NR_DEFERRED]
    mov r0, #0
    str r0, [r4, #NR_DEFERRED]
    .word 0xE121F006                 ; msr cpsr_c, r6
    tst r5, #NR_DEFER_SETTINGS
    blne menu_settings_save_card
    tst r5, #NR_DEFER_CUSTOM
    movne r0, #1
    blne menu_settings_write
nr_card_flush_done:
    pop {r4-r6, pc}
.pool

nr_card_code_end:
