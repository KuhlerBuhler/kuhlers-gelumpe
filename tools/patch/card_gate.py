"""Assembler guards for the card switch or the Sampler's mounted volume.

A feature is on once a card has been seen since power-on: the first time the guard finds a card it writes CARD_SEEN to
the patch's own latch word (in its RAM state, FF at power-on), and from then on the latch alone lets it through. Pulling
the card while the device runs no longer switches the features off (device 18.10.: TAP MOTION went off with the card).
Without a card since power-on everything stays the firmware's, as before.
"""
SD_INPUT = 0x01E26070
SD_DETECT = 2
CARD_SEEN = 0x5A
LATCH_OFFSET = 0x3C            # the last word of each gated patch's state (STATE + 0x3C, free in all four)


def source(build, off, latch):
    """The guard: branches to `off` while no card has been seen since power-on. Clobbers r0 and r12."""
    seen = f'{off}_seen'
    head = f'''    ldr r12, ={latch:#x}
    ldr r0, [r12]
    cmp r0, #{CARD_SEEN:#x}
    beq {seen}
'''
    if build == 'synth':
        check = f'''    ldr r0, ={SD_INPUT:#x}
    ldr r0, [r0]
    tst r0, #{SD_DETECT}
    bne {off}
'''
    else:
        check = f'''    ldr r0, =FATFS
    ldr r0, [r0]
    cmp r0, #0
    beq {off}
    ldrb r0, [r0]
    cmp r0, #0
    beq {off}
'''
    return head + check + f'''    mov r0, #{CARD_SEEN:#x}
    str r0, [r12]
{seen}:
'''
