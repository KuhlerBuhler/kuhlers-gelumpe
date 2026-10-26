"""A read-only FatFs cursor checkpoint owned by one sample parser frame."""

PARSER = 0xC0035B10
LSEEK = 0xC009E404
SITES = (0xC0035C74, 0xC0035C94, 0xC0035D68, 0xC0035DCC, 0xC0035DFC, 0xC00363C0)
FRAME = 0x4F0  # Nine saved registers and 0x4CC bytes of parser locals.


def parser_source(body, prefix='sample_anchor'):
    return f'''
{prefix}_entry:
    push {{r4, lr}}
    sub sp, sp, #16
    str r0, [sp]
    ldr r12, [r0, #8]
    str r12, [sp, #4]
    ldr r12, [r0, #0x14]
    str r12, [sp, #8]
    bl {prefix}_body
    add sp, sp, #16
    pop {{r4, pc}}
{prefix}_body:
    push {{r4-r11, lr}}
    b {body}
'''


def seek_source(callee=LSEEK, prefix='sample_anchor', killed=None):
    guard = f'bl {killed}\ncmp r12, #0\nbne {prefix}_plain' if killed else ''
    return f'''
{prefix}_seek:
    push {{r4-r6, lr}}
    {guard}
    add r4, sp, #{FRAME}
    add r4, r4, #16
    ldr r5, [r4]
    cmp r0, r5
    bne {prefix}_plain
    ldrb r5, [r0, #7]
    cmp r5, #0
    bne {prefix}_plain
    ldrb r5, [r0, #6]
    tst r5, #2
    bne {prefix}_plain
    tst r5, #1
    beq {prefix}_plain
    ldr r5, [r0, #8]
    cmp r1, r5
    bhs {prefix}_plain
    ldr r5, [r4, #4]
    cmp r1, r5
    blo {prefix}_plain
    str r5, [r0, #8]
    ldr r5, [r4, #8]
    str r5, [r0, #0x14]
{prefix}_plain:
    bl {callee}
    pop {{r4-r6, pc}}
'''
