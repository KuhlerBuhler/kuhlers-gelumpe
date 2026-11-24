"""Native PCM range protection and sample/parser result propagation."""
import hashlib

HOOKS = (
    (0xC00146B4, 0xE92D4800, 'protect_pcm_write'),
    (0xC004EF58, 0xE3A03000, 'protect_pcm_short_read'),
    (0xC0036320, 0xE085500A, 'protect_pcm_parser_write'),
    (0xC00363E4, 0xE085500A, 'protect_pcm_parser_tail'),
)
SPANS = (
    (0xC00141F8, 0x88, 'd3144d2cdf6f4facea90758c5e2ee0d9223d920a20cbbf71046c574fb76983b3'),
    (0xC0014284, 0x88, '66c9dc416ccb8b51a91d2e294cb4764de1ba8d6e6eb3c92eb17a52a19f600c6c'),
    (0xC004EF28, 0x6C, '525aa75f66cd027e04964d6fdfcecc81c7fc2dde118d212bf0a6c92c978d711a'),
)


def validate_firmware(vsb):
    for address, size, expected in SPANS:
        offset = address - 0xC0000000 + 0x100
        if hashlib.sha256(vsb[offset:offset + size]).hexdigest() != expected:
            raise ValueError(f'native PCM frame differs at {address:#x}')


def source():
    return SOURCE


SOURCE = r'''
protect_pcm_write:
    push {r0-r12, lr}
    .word 0xE10F4000
    push {r4, r5}
    orr r0, r4, #0x80
    .word 0xE121F000
    ldr r11, =ST
    ldr r0, [r11, #MODE]
    cmp r0, #2
    bhi pcm_write_out
    mov r3, r3, lsl #16
    mov r3, r3, lsr #16
    cmp r3, #0
    beq pcm_write_out
    mov r3, r3, lsl #1
    mov r2, r1
    ldr r0, [sp, #52]
    ldr r1, [sp, #60]
    bl protection_pcm_boot_row
    mov r2, r0
    ldr r0, [sp, #12]
    ldr r1, [sp, #20]
    mov r1, r1, lsl #16
    mov r1, r1, lsr #16
    mov r1, r1, lsl #1
    bl protection_pcm_range
pcm_write_out:
    pop {r4, r5}
    .word 0xE121F004
    .word 0xE128F004
    pop {r0-r12, lr}
    .word 0xE92D4800
    b 0xC00146B8
.pool

protect_pcm_short_read:
    cmp r0, #0
    beq pcm_short_ready
    add sp, sp, #32
    pop {r4-r6, pc}
pcm_short_ready:
    mov r3, #0
    b 0xC004EF5C

protect_pcm_parser_write:
    cmp r0, #0
    movne r3, #4
    bne 0xC003639C
    add r5, r5, r10
    b 0xC0036324

protect_pcm_parser_tail:
    cmp r0, #0
    movne r3, #4
    bne 0xC003639C
    add r5, r5, r10
    b 0xC00363E8
.pool
'''
