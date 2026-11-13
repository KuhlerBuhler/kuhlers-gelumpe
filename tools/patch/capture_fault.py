"""Refuse native capture completion after a latched DSP error, on red 2.02."""
import hashlib

import arm
import sample_swap_io

HOOKS = ((0xC004F128, 'capture_finish_entry'), (0xC004F15C, 'capture_finish_read'),
         (0xC0082DA8, 'capture_stop_record'), (0xC0082DD8, 'capture_stop_command'),
         (0xC0082E5C, 'capture_stop_finish'), (0xC004F20C, 'capture_poll_entry'),
         (0xC0082F1C, 'capture_start_entry'))
ORIGINALS = {0xC004F128: 0xE92D4FF0, 0xC004F15C: 0xE0080897,
             0xC0082DD8: 0xE3A00000, 0xC0082E5C: 0xE3570001,
             0xC004F20C: 0xE92D4013, 0xC0082F1C: 0xE92D40F8}
SPANS = ((0x4F128, 224, '503ec21ea8709a9ebd6c1eca8d0cb21c40af7ab98fffb5ce0cf1371dd17437f2'),
         (0x82D40, 476, '8a1af5c474476a1f643f1f1e6bbcf3e7d5adce02565f5f62a069e3f267b3a2fe'),
         (0x4F20C, 100, 'c7074da00de7c6fb52b512acb328491ad9f21bc05df4a20bbbe1dae794598535'),
         (0x82F1C, 36, 'de7be2c841692fe71288ceccdf79bf57b698267037a9254d0d5ace4f1f1c4370'))


def validate_firmware(vsb):
    sample_swap_io.validate_firmware(vsb)
    for at, length, expected in SPANS:
        if hashlib.sha256(vsb[256 + at:256 + at + length]).hexdigest() != expected:
            raise ValueError('native capture completion differs')


def build_code(origin, *, fault):
    if origin & 3 or fault & 3:
        raise ValueError('word aligned capture code and fault required')
    code = arm.assemble(source(fault), origin=origin)
    return code.bytes, code.symbols


def source(fault, *, admit_import=False, protect_publication=False, card_slot=False):
    start = 'b capture_start_admitted' if admit_import else 'push {r3-r7, lr}\n    b 0xc0082f20'
    publish = ('b capture_protect_publication' if protect_publication else
               'mul r8, r7, r8\n    b 0xc004f160')
    stop = ('''bl 0xc004f270
    push {r0-r3, r12, lr}
    bl persist_capture_slot
    mov r5, r0
    pop {r0-r3, r12, lr}
    cmn r5, #1
    b 0xc0082de4''' if card_slot else 'b 0xc0082ddc')
    return (f'.equ CF_FAULT, {fault:#x}\n' + SOURCE.replace('@START@', start)
            .replace('@PUBLISH@', publish).replace('@STOP_COMMAND@', stop))


SOURCE = r'''
capture_start_entry:
    ldr r12, =CF_FAULT
    ldr r12, [r12]
    cmp r12, #0
    cmnne r12, #1
    cmpne r12, #1
    movne r0, #0
    bxne lr
    @START@

capture_poll_entry:
    ldr r12, =CF_FAULT
    ldr r12, [r12]
    cmp r12, #0
    cmnne r12, #1
    cmpne r12, #1
    movne r0, #0
    bxne lr
    push {r0, r1, r4, lr}
    b 0xc004f210

capture_finish_entry:
    ldr r12, =CF_FAULT
    ldr r12, [r12]
    cmp r12, #0
    cmnne r12, #1
    cmpne r12, #1
    movne r0, #0
    bxne lr
    push {r4-r11, lr}
    b 0xc004f12c

capture_finish_read:
    ldr r12, =CF_FAULT
    ldr r12, [r12]
    cmp r12, #0
    cmnne r12, #1
    cmpne r12, #1
    movne r0, #0
    bne 0xc004f1f4
    @PUBLISH@

capture_stop_record:
    ldr r12, =CF_FAULT
    ldr r12, [r12]
    cmp r12, #0
    cmnne r12, #1
    cmpne r12, #1
    movne r0, #0
    bne 0xc0082f08
    bl 0xc004ef94
    b 0xc0082dac

capture_stop_command:
    ldr r12, =CF_FAULT
    ldr r12, [r12]
    cmp r12, #0
    cmnne r12, #1
    cmpne r12, #1
    mov r0, #0
    bne 0xc0082f08
    @STOP_COMMAND@

capture_stop_finish:
    ldr r12, =CF_FAULT
    ldr r12, [r12]
    cmp r12, #0
    cmnne r12, #1
    cmpne r12, #1
    movne r0, #0
    bne 0xc0082f08
    cmp r7, #1
    b 0xc0082e60
.pool
'''


PUBLICATION = r'''
; The DSP end read has succeeded; the native continuation has not changed the sample tables.
capture_protect_publication:
    push {r0-r3, r12, lr}
    ldr r0, =NATIVE_SCOPE
    ldr r0, [r0]
    cmn r0, #1
    movne r0, r7
    movne r1, #1
    blne protection_bit
    pop {r0-r3, r12, lr}
    mul r8, r7, r8
    b 0xC004F160
.pool
'''
