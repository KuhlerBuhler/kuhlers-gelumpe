.syntax unified
.arm
@ fills [START, END) with addr ^ KEY, returns
    push {r4, lr}
    ldr r0, start
    ldr r1, end
    ldr r2, key
1:  eor r3, r0, r2
    str r3, [r0], #4
    cmp r0, r1
    blo 1b
    pop {r4, pc}
start: .word 0xC1010000
end:   .word 0xC4000000
key:   .word 0x5A5AA5A5
