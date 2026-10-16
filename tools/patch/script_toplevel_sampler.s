menu_toplevel:
    cmp r1, #MENU_SCREEN
    beq menu_toplevel_hit
    cmp r1, #10
    ldr pc, =0xC006E8DC
menu_toplevel_hit:
    ldr pc, =0xC006E930
.pool
