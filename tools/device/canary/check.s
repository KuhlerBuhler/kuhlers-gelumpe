.syntax unified
.arm
@ for each 4 KiB block of [START, END): byte in MAP = number of words that differ from addr ^ KEY (saturated at 255)
    push {r4-r7, lr}
    ldr r0, start
    ldr r1, end
    ldr r2, key
    ldr r4, map
1:  mov r5, #0
    add r6, r0, #4096
2:  ldr r3, [r0]
    eor r7, r0, r2
    cmp r3, r7
    addne r5, r5, #1
    add r0, r0, #4
    cmp r0, r6
    blo 2b
    cmp r5, #255
    movhi r5, #255
    strb r5, [r4], #1
    cmp r0, r1
    blo 1b
    pop {r4-r7, pc}
start: .word 0xC1010000
end:   .word 0xC4000000
key:   .word 0x5A5AA5A5
map:   .word 0xC1001000
