"""Build a bounded, explicitly fallible DSP sample transport for Sampler 2.02.

transfer(op, ARM pointer, DSP byte offset, halfword count) returns status in r0
and completed halfwords in r1. r4-r11 are preserved. State is one word: zero
is ready; every other value refuses traffic. A partial protocol timeout latches
one until cold boot. This module installs no hooks into native void functions.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import arm
import ramdecl

CODE_AT, CODE_END = 0xC019E000, 0xC019E800
STATE, STATE_END = 0xC019EFF0, 0xC019EFF4
PORT, GPIO, TIMER = 0x60000000, 0x01E26098, 0x01F0D000
SEMA, RELEASE = 0xC06A2480, 0xC0000CA8
IRQ_DEPTH, STARTED = 0xC06A2894, 0xC06A2928
ARM_MIN, ARM_END = 0xC274F000, 0xC4000000
DSP_MIN, DSP_END, CURSOR = 0x365EC0, 0x1C65EC0, 0xC00F9C80
OK, INVALID, BUSY, CONTEXT, BAD_TIMER, TIMEOUT, FAULT = range(7)
TIMER_HZ, DEADLINE_TICKS, POLL_BUDGET = 150000000, 15000000, 1000000


def build_code(origin=CODE_AT, state=STATE, poll_budget=POLL_BUDGET):
    if origin & 3 or state & 3 or not 0 < poll_budget <= 0xffffffff:
        raise ValueError('aligned origin/state and positive poll budget required')
    protected = ''
    for lo, hi in ((origin, 'end_code'), (state, str(state+4))):
        if ARM_MIN <= lo < ARM_END:
            protected += f"""
    ldr r2, ={lo}
    cmp r1, r2
    bls safe_{lo:x}
    ldr r2, ={hi}
    cmp r4, r2
    blo done
safe_{lo:x}:
"""
    source = f'''
transfer:
    push {{r4-r12, lr}}
    mov r7, r0
    mov r4, r1
    mov r5, r2
    mov r6, r3
    mov r8, #0
    mov r0, #{INVALID}
    cmp r7, #1
    bhi done
    cmp r6, #0
    beq done
    cmp r6, #32768
    bhi done
    tst r6, #15
    bne done
    tst r4, #1
    bne done
    ldr r1, ={ARM_MIN}
    cmp r4, r1
    blo done
    adds r1, r4, r6, lsl #1
    bcs done
    ldr r2, ={ARM_END}
    cmp r1, r2
    bhi done
{protected}
    tst r5, #31
    bne done
    ldr r1, ={DSP_MIN}
    cmp r5, r1
    blo done
    adds r1, r5, r6, lsl #1
    bcs done
    ldr r2, ={CURSOR}
    ldr r2, [r2]
    cmp r1, r2
    bhi done
    ldr r1, ={DSP_END}
    cmp r2, r1
    bhi done
    .word 0xe10f0000
    tst r0, #0x80
    bne context
    and r1, r0, #31
    cmp r1, #0x13
    cmpne r1, #0x1f
    bne context
    ldr r1, ={IRQ_DEPTH}
    ldr r1, [r1]
    cmp r1, #0
    bne context
    ldr r1, ={STARTED}
    ldr r1, [r1]
    cmp r1, #0
    beq context
    ldr r1, ={state}
    ldr r1, [r1]
    cmp r1, #0
    movne r0, #{FAULT}
    bne done
    ldr r10, ={TIMER}
    ldr r1, [r10, #0x18]
    ldr r2, ={TIMER_HZ-1}
    cmp r1, r2
    blo bad_timer
    ldr r1, [r10, #0x20]
    and r1, r1, #0xc0
    cmp r1, #0x80
    bne bad_timer
    ldr r1, [r10, #0x24]
    tst r1, #1
    beq bad_timer
    ldr r2, ={SEMA}
    .word 0xe10f0000
    orr r1, r0, #0x80
    .word 0xe121f001
    ldr r1, [r2]
    cmp r1, #1
    moveq r1, #0
    streq r1, [r2]
    .word 0xe121f000
    movne r0, #{BUSY}
    bne done
acquired:
    ldr r1, ={state}
    ldr r1, [r1]
    cmp r1, #0
    movne r0, #{FAULT}
    bne release
    ldr r9, ={PORT}
    ldr r11, [r10, #0x10]
    ldr r12, ={poll_budget}
    mov r0, #0
    bl wait
    bne pre_timeout
    mov r0, #1
    bl wait
    bne pre_timeout
    mov r0, #1
    ldr r1, ={state}
    str r0, [r1]
    cmp r7, #0
    moveq r0, #0xa9
    movne r0, #0xab
    .word 0xe1c900b2 ; strh r0, [r9, #2]
    .word 0xe1c950b2 ; strh r5, [r9, #2]
    mov r0, r5, lsr #16
    .word 0xe1c900b2 ; strh r0, [r9, #2]
    .word 0xe1c960b2 ; strh r6, [r9, #2]
    mov r0, #2
    .word 0xe1c900b2 ; strh r0, [r9, #2]
    mov r0, #0
    .word 0xe1c900b2 ; strh r0, [r9, #2]
    .word 0xe1c900b2 ; strh r0, [r9, #2]
    mov r0, #2
    bl wait
    bne pre_timeout
next_group:
    mov r0, #3
    bl wait
    bne pre_timeout
    mov r3, #16
next_word:
    cmp r7, #0
    .word 0x01d900b0 ; ldrheq r0, [r9]
    .word 0x00c400b2 ; strheq r0, [r4], #2
    .word 0x10d400b2 ; ldrhne r0, [r4], #2
    .word 0x11c900b0 ; strhne r0, [r9]
    add r8, r8, #1
    subs r3, r3, #1
    bne next_word
    subs r6, r6, #16
    bne next_group
    mov r0, #0
    ldr r1, ={state}
    str r0, [r1]
    b release
pre_timeout:
    mov r0, #{TIMEOUT}
release:
    mov r4, r0
    mov r0, #1
    ldr r1, ={RELEASE}
    blx r1
    cmp r0, #0
    movne r4, #{FAULT}
    ldrne r1, ={state}
    movne r2, #1
    strne r2, [r1]
    mov r0, r4
    b done
context:
    mov r0, #{CONTEXT}
    b done
bad_timer:
    mov r0, #{BAD_TIMER}
done:
    mov r1, r8
    pop {{r4-r12, pc}}

; r0 selects GPIO set, status ready, header acknowledgement, or GPIO clear.
; Z means ready; non-Z means the shared deadline or poll bound expired.
wait:
    subs r12, r12, #1
    beq wait_failed
    ldr r1, [r10, #0x10]
    cmp r1, r11
    sub r1, r1, r11
    ldrlo r2, [r10, #0x18]
    addlo r1, r1, r2
    addlo r1, r1, #1
    ldr r2, ={DEADLINE_TICKS}
    cmp r1, r2
    bhs wait_failed
    cmp r0, #1
    bne wait_gpio
    .word 0xe1d910b2 ; ldrh r1, [r9, #2]
    tst r1, #0x80
    bne wait_ready
    b wait_clock
wait_gpio:
    cmp r0, #2
    bne gpio_only
    .word 0xe1d910b2 ; ldrh r1, [r9, #2]
    tst r1, #1
    bne wait_ready
gpio_only:
    ldr r1, ={GPIO}
    ldr r1, [r1]
    tst r1, #2
    beq gpio_clear
    cmp r0, #0
    beq wait_ready
    b wait_clock
gpio_clear:
    cmp r0, #0
    bne wait_ready
wait_clock:
    b wait
wait_failed:
    mov r1, #1
    cmp r1, #0
    bx lr
wait_ready:
    cmp r0, r0
    bx lr
.pool
end_code:
'''
    assembled = arm.assemble(source, origin=origin)
    if origin < state+4 and state < origin+len(assembled.bytes):
        raise ValueError('transport code and fault state overlap')
    return assembled.bytes, assembled.symbols


def file_offset(address):
    return address - 0xC0000000 + 0x100


NATIVE_SPANS = (
    (RELEASE, 0xD8, '6881f74d45dcb2f1ae7092dddedb7bd15d6dd7a08319f95a66354b287a25b561'),
    (0xC0000D80, 0xC4, '0702b54d3f0e8b0ae907de7ddf65a470cfde090af570ab24e7c4e018d1af9c57'),
    (0xC00141F8, 0xD10, 'ee4f027dbafd07bbcd0ca3d6ee3bcace06f74e81b9f9a810623938005393dd7a'),
    (0xC004EDDC, 0x14, '426f600b1d005b62cf80b254add060252e6bb5c4096d5256043fa52e0cbb30af'),
    (0xC004EF28, 0x6C, '525aa75f66cd027e04964d6fdfcecc81c7fc2dde118d212bf0a6c92c978d711a'),
)


def validate_firmware(vsb):
    if len(vsb) != 0x200100:
        raise ValueError('a VSB has 0x200100 bytes')
    for at, length, digest in NATIVE_SPANS:
        offset = file_offset(at)
        if hashlib.sha256(vsb[offset:offset+length]).hexdigest() != digest:
            raise ValueError(f'unmapped or modified Sampler code at {at:#x}')
    sys.path.insert(0, str(Path(__file__).parent.parent / 'emu'))
    import firmware
    return firmware.build_of(vsb[0x100:])


def build_patch(vsb, build=None):
    actual = validate_firmware(vsb)
    if build is None:
        build = actual
    if build != actual or build not in ('stock','hacktribe'):
        raise ValueError('only mapped Sampler stock/hacktribe builds are supported')
    code, _ = build_code()
    if CODE_AT+len(code)>CODE_END:
        raise ValueError('transport exceeds its reserved code range')
    reserved=vsb[file_offset(CODE_AT):file_offset(CODE_END)]
    if reserved != b'\xff' * (CODE_END-CODE_AT):
        raise ValueError('transport reservation is not erased space')
    changes=[]
    for at,data in ((CODE_AT,code),(STATE,b'\x00'*4)):
        old=vsb[file_offset(at):file_offset(at)+len(data)]
        if old!=b'\xff'*len(data):
            raise ValueError(f'{at:#x} is not erased space in this image')
        changes.append(dict(file=file_offset(at),bytes=data.hex(),expect=hashlib.sha256(old).hexdigest(),note='bounded DSP sample transport' if at==CODE_AT else 'DSP protocol fault state'))
    tail_at = CODE_AT + len(code)
    tail = [ramdecl.area(tail_at, CODE_END-tail_at, 'unused transport code budget', 'tools/patch/sample_swap_io.py:CODE_END')] if tail_at < CODE_END else []
    return dict(format='gelumpe-patch',version=1,id='sample-swap-io',builds=[build],name='Begrenzter DSP-Sampletransfer',changes=changes,hooks=[],ram=tail)


def main():
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--vsb',required=True,type=Path)
    parser.add_argument('--build',choices=('hacktribe','stock'))
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    result=json.dumps(build_patch(args.vsb.read_bytes(),args.build),indent=1)+'\n'
    if args.out:args.out.write_text(result)
    else:print(result,end='')


if __name__=='__main__':main()
