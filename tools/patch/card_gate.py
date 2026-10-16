"""Assembler guards for the card switch or the Sampler's mounted volume."""
SD_INPUT = 0x01E26070
SD_DETECT = 2


def source(build, off):
    if build == 'synth':
        return f'''    ldr r12, ={SD_INPUT:#x}
    ldr r12, [r12]
    tst r12, #{SD_DETECT}
    bne {off}
'''
    return f'''    ldr r12, =FATFS
    ldr r12, [r12]
    cmp r12, #0
    beq {off}
    ldrb r12, [r12]
    cmp r12, #0
    beq {off}
'''
