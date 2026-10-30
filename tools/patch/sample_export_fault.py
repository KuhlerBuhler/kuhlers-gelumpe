"""Propagate latched DSP errors through native single-sample export on red 2.02."""
import hashlib

import arm
import sample_swap_io

HOOKS = ((0xC0039CC4, 'export_sample_entry'), (0xC0039B2C, 'export_writer_entry'),
         (0xC0039C30, 'export_sample_read'))
ORIGINALS = {0xC0039CC4: 0xE92D47F0, 0xC0039B2C: 0xE92D4FF0, 0xC0039C30: 0xE1A00006}
SPANS = ((0x39B2C, 408, '186292ed68eca1a25178fbb29f8510615873d9d0f98cab90952ec34f37d21f36'),
         (0x39CC4, 396, 'fdb619cfee251d51a995c783ba38fa9ce92250065990b5aa6ffe6bd73077ed46'),
         (0x35428, 48, '397f0cfbf4f9c6ab6e3700d98ee334faa4e7f2ef4357cf381b99b6330e63f638'))


def validate_firmware(vsb):
    sample_swap_io.validate_firmware(vsb)
    for at, length, expected in SPANS:
        if hashlib.sha256(vsb[256 + at:256 + at + length]).hexdigest() != expected:
            raise ValueError('native sample export differs')


def build_code(origin, *, fault):
    if origin & 3 or fault & 3:
        raise ValueError('word aligned export code and fault required')
    result = arm.assemble(source(fault), origin=origin)
    return result.bytes, result.symbols


def source(fault):
    return f'.equ EF_FAULT, {fault:#x}\n' + SOURCE


SOURCE = r'''
export_sample_entry:
    ldr r12, =EF_FAULT
    ldr r12, [r12]
    cmp r12, #0
    cmnne r12, #1
    movne r0, #1
    bne 0xc0035428
    push {r4-r10, lr}
    b 0xc0039cc8

export_writer_entry:
    ldr r12, =EF_FAULT
    ldr r12, [r12]
    cmp r12, #0
    cmnne r12, #1
    movne r0, #1
    bxne lr
    push {r4-r11, lr}
    b 0xc0039b30

export_sample_read:
    ldr r12, =EF_FAULT
    ldr r12, [r12]
    cmp r12, #0
    cmnne r12, #1
    movne r5, #1
    bne 0xc0039c58
    mov r0, r6
    b 0xc0039c34
.pool
'''
