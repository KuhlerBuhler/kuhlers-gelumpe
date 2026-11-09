"""Native PCM results at the sample helper and parser continuation points."""
import hashlib

HOOKS = (
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
