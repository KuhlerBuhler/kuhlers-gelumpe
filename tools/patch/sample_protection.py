"""Sticky physical-row protection and resumable signature scans."""
import hashlib
import struct

import arm
import sample_seek

SIZE = 160
REV, SCAN_REV, SCAN_GEN, NEXT, READY, EXHAUSTED = range(128, 152, 4)

# Entry, replayable push, label, argument kind, zero-delta getter, length, hash.
MUTATIONS = (
    (0xC004E558, 0xE92D4008, 'protect_delete', 'import', False, 0x68,
     'dbf2300087233dba96787b8a3f74659ae678fffe2f61d538ea12df6a87185ddf'),
    (0xC004EDF0, 0xE92D4FF7, 'protect_reserve', 'descriptor', False, 0x138,
     '36124f994fd586bc90f4507abc1802a0b1ad07435a7634520c86aec280c129b9'),
    (0xC004E63C, 0xE92D40F8, 'protect_start', 'import', True, 0xD4,
     'ab40ff106f55ce223a2002877e0b041dbe565f00b37d2e1bda87fe05838da0e5'),
    (0xC004E710, 0xE92D41F0, 'protect_end', 'import', True, 0xD8,
     'ba224ab9d517894af6ac75f2579420e19b2d337975527bc84b07585925260824'),
    (0xC004E7E8, 0xE92D4038, 'protect_loop', 'import', True, 0xA8,
     '77418e7acf8125de83946a8bebe933ce253c87317621d2b44647cca32f5613bc'),
    (0xC004E8C8, 0xE92D4010, 'protect_rename', 'import', False, 0x58,
     'b84a9ef8733e279222927a3943206a765730b6b68d48bbacbbe6ed7d74e34a62'),
    (0xC004E93C, 0xE92D4038, 'protect_slice', 'import', False, 0x88,
     'a56570ef12aeb9f26b3e5950cb10614eda1f39490401d19e782a4e2c3b87e952'),
    (0xC004EFF4, 0xE92D4FF0, 'protect_restore', 'descriptor', False, 0x134,
     '75792709759c5bc6566dab7d8cccbbe6b108e571ec3e8a3c73ad01a2282c3d04'),
)


# Store, original instruction, label, row register, value register, offset, width,
# row-pointer bias, native function, length, hash.
STORES = (
    (0xC007F9F0, 0xE1C321B4, 'protect_tune', 'r3', 'r2', 20, 2, 0, 0xC007F980, 0xC4,
     '29806b8c5cdb20b4bd3a39700fe9750c8ce1539d7ec1be2090f212b250ad2dc3'),
    (0xC007F94C, 0xE5C6500A, 'protect_level', 'r6', 'r5', 10, 1, 0, 0xC007F8A8, 0xD8,
     'db8d91c07a4e7084e82851f96468b720d02e30e3b2d7f842c45c645e0e3c4b16'),
    (0xC007F0EC, 0xE1C630B4, 'protect_tune_increment', 'r6', 'r3', 4, 2, 16, 0xC007F02C, 0x104,
     'aa6fae001c46067062159225fe661e12de824de51f0e0e56256c4a3c2a68add0'),
    (0xC007EFE8, 0xE5C65002, 'protect_level_increment', 'r6', 'r5', 2, 1, 8, 0xC007EF44, 0xE8,
     'b2d8774a54c73ccff8492876fc90a8344b53b1a47cee6f2be5941262965e0636'),
)


def validate_firmware(vsb):
    parser = sample_seek.PARSER - 0xC0000000 + 0x100
    if hashlib.sha256(vsb[parser:parser + 0x8F0]).hexdigest() != '2c1b1b3abf5a7454f90f511112e8b68b653f4a93d50d210e75a61ca2a1b287e3':
        raise ValueError('native sample parser frame differs')
    loop = 0xC00364F0 - 0xC0000000 + 0x100
    if hashlib.sha256(vsb[loop:loop + 0x280]).hexdigest() != 'c2bb96cbed1fe904bc44ac1f0c123907472cd4f9b3b167cf5a52d94ba0fd13be':
        raise ValueError('native sample collection loop differs')
    for at, _, label, _, _, length, expected in MUTATIONS:
        off = at - 0xC0000000 + 0x100
        if hashlib.sha256(vsb[off:off + length]).hexdigest() != expected:
            raise ValueError(f'native sample mutation differs: {label}')

    for _, _, label, _, _, _, _, _, entry, length, expected in STORES:
        off = entry - 0xC0000000 + 0x100
        if hashlib.sha256(vsb[off:off + length]).hexdigest() != expected:
            raise ValueError(f'native sample store differs: {label}')


def source(state):
    if state & 3 or not 0 <= state <= 0x100000000 - SIZE:
        raise ValueError('word aligned protection state required')
    return (f'.equ P_STATE, {state:#x}\n.equ PARSER_FRAME, {sample_seek.FRAME}\n'
            f'.equ ANCHOR_FRAME, {sample_seek.ANCHOR_FRAME}\n'
            f'.equ ANCHOR_LR, {sample_seek.ANCHOR_CALLER_LR}\n'
            f'.equ ANCHOR_RETURN, {sample_seek.ANCHOR_RETURN}\n'
            + SOURCE + wrappers() + store_wrappers())


def wrappers():
    result = []
    for at, original, label, kind, delta, _, _ in MUTATIONS:
        result.append(f'{label}:')
        bypass = {'protect_reserve': 'pub_reserved', 'protect_delete': 'evict_deleted'}.get(label)
        if bypass:
            result.append(f'push {{r0, r12}}\nldr r12, ={bypass}\ncmp lr, r12\npop {{r0, r12}}\nbeq {label}_native')
        if delta:
            result.append(f'cmp r1, #0\nbeq {label}_native')
        result.append(f'push {{r0-r3, r12, lr}}\nldr r12, =ST\nldr r12, [r12, #MODE]\ncmp r12, #2\nbhi {label}_out')
        if kind == 'descriptor':
            result.append('ldrh r0, [r0]\nbl protection_touch')
        else:
            result.append('bl protection_import')
        if label == 'protect_reserve':
            result.append(boot_stamp())
        result.append(f'{label}_out:\npop {{r0-r3, r12, lr}}\n{label}_native:\n.word {original:#x}\nb {at + 4:#x}\n.pool')
    pattern = arm.assemble(sample_seek.parser_source(0), origin=0).bytes[:sample_seek.ANCHOR_RETURN]
    result.append('protection_anchor_pattern:\n' + '\n'.join(f'.word {word:#x}' for word in struct.unpack('<8I', pattern)))
    return '\n'.join(result) + '\n'


def store_wrappers():
    result = []
    for at, original, label, pointer, value, offset, width, bias, *_ in STORES:
        shift = 32 - width * 8
        load = 'ldrh' if width == 2 else 'ldrb'
        saved = '\n    '.join(f'ldr {reg}, [sp, #{4 + int(reg[1:]) * 4}]'
                              for reg in dict.fromkeys((pointer, value)) if reg in ('r2', 'r3'))
        unbias = f'sub r0, r0, #{bias}' if bias else ''
        result.append(f'''{label}:
    push {{r0-r4, r12, lr}}
    .word 0xE10F4000
    push {{r4}}
    ldr r0, =ST
    ldr r0, [r0, #MODE]
    cmp r0, #2
    bhi {label}_store
    mov r0, {pointer}
    {unbias}
    bl protection_row_index
    orr r1, r4, #0x80
    .word 0xE121F001
    cmn r0, #1
    beq {label}_store
    {saved}
    mov r1, {value}, lsl #{shift}
    mov r1, r1, lsr #{shift}
    {load} r2, [{pointer}, #{offset}]
    cmp r1, r2
    beq {label}_store
    mov r1, #1
    bl protection_bit
{label}_store:
    {saved}
    .word {original:#x}
    pop {{r4}}
    .word 0xE121F004
    .word 0xE128F004
    pop {{r0-r4, r12, lr}}
    b {at + 4:#x}
    .pool
''')
    return '\n'.join(result)


def boot_stamp():
    return r'''
    ldr r0, [sp, #20]
    ldr r1, =0xC00362A0
    cmp r0, r1
    bne protect_reserve_out
    add r0, sp, #24
    bl protection_boot_frame
    cmp r0, #0
    beq protect_reserve_out
    ldr r1, =P_STATE
    ldr r1, [r1, #128]
    str r1, [r0]
    mov r1, #1
    str r1, [r0, #4]
'''


SOURCE = r'''
; r0 parser locals. Returns its verified stamp address and saved logical slot.
protection_boot_frame:
    push {r4-r6, lr}
    mov r4, r0
    ldr r1, =0xC0000000
    cmp r4, r1
    blo pbf_no
    ldr r1, =0xC4000000 - PARSER_FRAME - ANCHOR_FRAME - 8
    cmp r4, r1
    bhi pbf_no
    tst r4, #3
    bne pbf_no
    add r5, r4, #PARSER_FRAME
    ldr r6, [r5, #-36]
    ldr r3, [r5, #-4]
    ldr r1, =boot_parse_done
    cmp r3, r1
    beq pbf_yes
    ldr r0, =PARSER
    ldr r0, [r0]
    and r1, r0, #0xFF000000
    cmp r1, #0xEA000000
    bne pbf_no
    mov r0, r0, lsl #8
    mov r0, r0, asr #6
    ldr r1, =PARSER + 8
    add r0, r0, r1
    add r1, r0, #ANCHOR_RETURN
    cmp r3, r1
    bne pbf_no
    ldr r1, =protection_anchor_pattern
    mov r2, #8
pbf_anchor:
    ldr r3, [r0], #4
    ldr r12, [r1], #4
    cmp r3, r12
    bne pbf_no
    subs r2, r2, #1
    bne pbf_anchor
    ldr r0, [r5, #ANCHOR_LR]
    ldr r1, =boot_parse_done
    cmp r0, r1
    bne pbf_no
    add r5, r5, #ANCHOR_FRAME
pbf_yes:
    mov r0, r5
    mov r1, r6
    pop {r4-r6, pc}
pbf_no:
    mov r0, #0
    pop {r4-r6, pc}
.pool

; r0 native FP, r1 return PC, r2 DSP destination, r3 bytes. Returns a row or -1.
protection_pcm_boot_row:
    push {r4-r9, r12, lr}
    mov r7, r8
    mov r8, r2
    mov r9, r3
    ldr r2, =0xC0014C88
    cmp r1, r2
    ldrne r2, =0xC0014CE0
    cmpne r1, r2
    bne pcb_no
    ldr r1, =0xC0000004
    cmp r0, r1
    blo pcb_no
    ldr r1, =0xC4000000
    cmp r0, r1
    bhs pcb_no
    tst r0, #3
    bne pcb_no
    ldr r4, [r0, #-4]
    ldr r1, =0xC0000000
    cmp r4, r1
    blo pcb_no
    ldr r1, =0xC4000000 - 52 - PARSER_FRAME - ANCHOR_FRAME - 8
    cmp r4, r1
    bhi pcb_no
    tst r4, #3
    bne pcb_no
    ldr r0, [r4]
    ldr r1, =0xC004EF8C
    cmp r0, r1
    bne pcb_no
    ldr r0, [r4, #48]
    ldr r1, =0xC0036320
    cmp r0, r1
    ldrne r1, =0xC00363E4
    cmpne r0, r1
    bne pcb_no
    add r0, r4, #52
    bl protection_boot_frame
    cmp r0, #0
    beq pcb_no
    mov r6, r1
    ldr r1, [r0, #4]
    cmp r1, #1
    bne pcb_no
    ldr r1, [r0]
    ldr r2, =P_STATE
    ldr r2, [r2, #128]
    cmp r1, r2
    bne pcb_no
    ldr r0, =ST
    ldr r1, [r0, #J_STATE]
    ldr r2, [r0, #J_STAGED]
    orrs r1, r1, r2
    bne pcb_no
    ldr r1, =0xC0000000
    cmp r7, r1
    blo pcb_no
    ldr r1, =0xC3FFFFFE
    cmp r7, r1
    bhi pcb_no
    tst r7, #1
    bne pcb_no
    ldrh r0, [r7]
    cmp r0, r6
    bne pcb_no
    bl physical
    cmp r0, #500
    blo pcb_no
    ldr r1, =SAMPLE_COUNT
    cmp r0, r1
    bhs pcb_no
    mov r6, r0
    bl protection_dirty
    cmp r0, #1
    bne pcb_no
    ldr r0, =0x45C
    mul r1, r6, r0
    ldr r0, =META
    add r4, r0, r1
    ldrb r0, [r4, #11]
    cmp r0, #1
    bne pcb_no
    ldr r0, [r4]
    cmp r8, r0
    blo pcb_no
    ldr r1, =DSP_MIN
    cmp r0, r1
    blo pcb_no
    ldr r1, [r4, #4]
    adds r1, r1, #31
    bcs pcb_no
    bic r1, r1, #31
    adds r0, r0, r1
    bcs pcb_no
    ldr r1, =DSP_END
    cmp r0, r1
    bhi pcb_no
    adds r1, r8, r9
    bcs pcb_no
    cmp r1, r0
    bhi pcb_no
    mov r0, r6
    pop {r4-r9, r12, pc}
pcb_no:
    mvn r0, #0
    pop {r4-r9, r12, pc}
.pool

; r0 DSP destination, r1 bytes, r2 qualified parser row or -1. IRQs are masked.
protection_pcm_range:
    push {r4-r10, lr}
    mov r4, r0
    adds r5, r0, r1
    movcs r4, #0
    mvncs r5, #0
    ldr r0, =DSP_END
    cmp r4, r0
    bhs pcr_out
    ldr r0, =DSP_MIN
    cmp r5, r0
    bls pcr_out
    mov r8, r2
    mov r9, #0
    cmp r8, #500
    blo pcr_invalidate
    ldr r0, =SAMPLE_COUNT
    cmp r8, r0
    blo pcr_begin
pcr_invalidate:
    mvn r0, #0
    mov r1, #1
    bl protection_bit
    mov r9, #1
pcr_begin:
    mov r6, #500
    ldr r7, =META + 500 * 0x45C
pcr_loop:
    ldrb r0, [r7, #11]
    cmp r0, #1
    bne pcr_next
    ldr r0, [r7]
    ldr r1, [r7, #4]
    adds r1, r0, r1
    bcs pcr_mark
    cmp r0, r5
    bhs pcr_next
    cmp r1, r4
    bls pcr_next
    cmp r6, r8
    beq pcr_next
pcr_mark:
    mov r0, r6
    cmp r9, #0
    moveq r1, #1
    movne r1, #2
    bl protection_bit
    mov r9, #1
pcr_next:
    ldr r0, =0x45C
    add r7, r7, r0
    add r6, r6, #1
    ldr r0, =SAMPLE_COUNT
    cmp r6, r0
    blo pcr_loop
pcr_out:
    pop {r4-r10, pc}
.pool

protection_init:
    ldr r0, =P_STATE
    mov r1, #0
    mov r2, #160
pi_loop:
    str r1, [r0], #4
    subs r2, r2, #4
    bne pi_loop
    ldr r0, =SIG
    ldr r2, =SAMPLE_COUNT
pi_signatures:
    str r1, [r0], #4
    subs r2, r2, #1
    bne pi_signatures
    bx lr

; r0 physical row. Returns its sticky dirty flag.
protection_dirty:
    ldr r1, =SAMPLE_COUNT
    cmp r0, r1
    movhs r0, #1
    bxhs lr
    ldr r1, =P_STATE
    mov r2, r0, lsr #5
    ldr r1, [r1, r2, lsl #2]
    and r2, r0, #31
    mov r0, r1, lsr r2
    and r0, r0, #1
    bx lr

; r0 logical slot. A native mutation invalidates all prepared decisions.
protection_touch:
    push {r4, lr}
    bl physical
    mov r1, #1
    bl protection_bit
    pop {r4, pc}

protection_import:
    push {r4, lr}
    add r0, r0, #50
    bl physical_import
    mov r1, #1
    bl protection_bit
    pop {r4, pc}

; r0 metadata row pointer. Returns its physical index, or -1.
protection_row_index:
    ldr r1, =META
    subs r0, r0, r1
    blo pr_invalid
    ldr r1, =SAMPLE_COUNT * 0x45C
    cmp r0, r1
    bhs pr_invalid
    mov r2, #0
    ldr r1, =0x45C
pr_divide:
    cmp r0, r1
    subhs r0, r0, r1
    addhs r2, r2, #1
    bhs pr_divide
    cmp r0, #0
    moveq r0, r2
    bxeq lr
pr_invalid:
    mvn r0, #0
    bx lr

; r0 physical row, r1 0 clean, 1 native mutation, 2 observed dirty.
protection_bit:
    push {r4-r6, lr}
    .word 0xE10F4000
    orr r2, r4, #0x80
    .word 0xE121F002
    ldr r5, =P_STATE
    mov r6, r1
    cmp r6, #1
    ldreq r2, =ST
    moveq r3, #0
    streq r3, [r2, #J_STATE]
    streq r3, [r2, #J_STAGED]
    ldr r2, =SAMPLE_COUNT
    cmp r0, #500
    blo pb_revision
    cmp r0, r2
    bhs pb_revision
    mov r2, r0, lsr #5
    add r2, r5, r2, lsl #2
    and r0, r0, #31
    mov r3, #1
    mov r3, r3, lsl r0
    ldr r0, [r2]
    cmp r6, #0
    biceq r0, r0, r3
    orrne r0, r0, r3
    str r0, [r2]
pb_revision:
    cmp r6, #2
    beq pb_out
    ldr r0, [r5, #128]
    cmn r0, #1
    moveq r1, #1
    streq r1, [r5, #148]
    addne r0, r0, #1
    strne r0, [r5, #128]
    mov r0, #0
    str r0, [r5, #140]
    str r0, [r5, #144]
pb_out:
    .word 0xE121F004
    pop {r4-r6, pc}

; r0 logical slot, r1 revision captured at verified publication. Returns success.
mark_clean:
    push {r4-r9, r12, lr}
    mov r4, r0
    mov r5, r1
    ldr r0, [r11, #TSTATE]
    cmp r0, #1
    bhi mc_no
    ldr r8, =P_STATE
    ldr r0, [r8, #148]
    cmp r0, #0
    bne mc_no
    ldr r0, [r8, #128]
    cmp r0, r5
    bne mc_no
    ldr r7, [r11, #GEN]
    mov r0, r4
    bl slot_sig
    movs r6, r0
    beq mc_no
    .word 0xE10F9000
    orr r0, r9, #0x80
    .word 0xE121F000
    ldr r0, [r11, #TSTATE]
    cmp r0, #1
    bhi mc_stale
    ldr r0, [r8, #148]
    cmp r0, #0
    bne mc_stale
    ldr r0, [r8, #128]
    cmp r0, r5
    ldreq r0, [r11, #GEN]
    cmpeq r0, r7
    bne mc_stale
    ldr r0, =SIG
    str r6, [r0, r4, lsl #2]
    mov r0, r4
    bl physical
    mov r1, #0
    bl protection_bit
    .word 0xE121F009
    mov r0, #1
    pop {r4-r9, r12, pc}
mc_stale:
    .word 0xE121F009
mc_no:
    mov r0, #0
    pop {r4-r9, r12, pc}

; Begin a new search, or resume an incomplete search in this generation.
protection_refresh:
    ldr r1, =P_STATE
    ldr r0, [r1, #144]
    cmp r0, #0
    strne r0, [r1, #140]
    mov r0, #0
    str r0, [r1, #144]
    b protection_scan

; Finish a deferred search before card parsing consumes this step's budget.
protection_resume:
    ldr r1, =P_STATE
    ldr r0, [r1, #140]
    cmp r0, #500
    movlo r0, #1
    bxlo lr
    ldr r0, [r1, #144]
    cmp r0, #0
    beq protection_scan
    mov r0, #1
    bx lr

; Returns one for a complete current view, zero for a deferred or invalid view.
protection_scan:
    push {r4-r8, lr}
    .word 0xE10F0000
    tst r0, #0x80
    bne ps_no
    ldr r0, [r11, #MODE]
    cmp r0, #1
    bne ps_no
    ldr r4, =P_STATE
    ldr r0, [r4, #148]
    cmp r0, #0
    bne ps_no
    ldr r5, [r4, #128]
    ldr r6, [r11, #GEN]
    ldr r0, [r4, #132]
    cmp r0, r5
    ldreq r0, [r4, #136]
    cmpeq r0, r6
    bne ps_start
    ldr r0, [r4, #144]
    cmp r0, #1
    beq ps_yes
    ldr r7, [r4, #140]
    cmp r7, #500
    bhs ps_loop
ps_start:
    str r5, [r4, #132]
    str r6, [r4, #136]
    mov r0, #0
    str r0, [r4, #144]
    mov r7, #500
ps_loop:
    str r7, [r4, #140]
    ldr r0, [r4, #128]
    cmp r0, r5
    ldreq r0, [r11, #GEN]
    cmpeq r0, r6
    bne ps_no
    ldr r0, [r11, #INSTEP]
    cmp r0, #0
    beq ps_slot
    ldr r0, [r11, #T0]
    bl since
    ldr r1, =BUDGET
    cmp r0, r1
    bhs ps_no
ps_slot:
    mov r0, r7
    bl resident
    cmp r0, #0
    beq ps_next
    mov r0, r7
    bl physical
    mov r8, r0
    cmp r8, #500
    blo ps_next
    bl protection_dirty
    cmp r0, #0
    bne ps_next
    mov r0, r7
    bl slot_clean
    cmp r0, #0
    bne ps_next
    mov r0, r8
    mov r1, #2
    bl protection_bit
ps_next:
    add r7, r7, #1
    ldr r0, =SAMPLE_COUNT
    cmp r7, r0
    blo ps_loop
    str r7, [r4, #140]
    ldr r0, [r4, #128]
    cmp r0, r5
    ldreq r0, [r11, #GEN]
    cmpeq r0, r6
    bne ps_no
    mov r0, #1
    str r0, [r4, #144]
ps_yes:
    mov r0, #1
    pop {r4-r8, pc}
ps_no:
    mov r0, #0
    pop {r4-r8, pc}

; r0 ARM buffer, r1 DSP destination, r2 halfwords, r3 file lease. Resource 1 is held.
transfer_job_ok:
    push {r4-r8, r11, r12, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r7, r3
    ldr r11, =ST
    .word 0xE10F8000
    orr r0, r8, #0x80
    .word 0xE121F000
    ldr r0, =STAGE
    cmp r4, r0
    bne tj_no
    ldr r0, =FILE_OWNER
    ldr r1, [r0]
    cmp r7, #0
    beq tj_no
    cmp r1, r7
    bne tj_no
    ldr r1, [r0, #8]
    cmp r1, #0
    bne tj_no
    ldr r1, [r0, #12]
    cmp r1, #1
    bne tj_no
    ldr r0, [r11, #MODE]
    cmp r0, #1
    bne tj_no
    ldr r0, [r11, #TSTATE]
    cmp r0, #0
    bne tj_no
    ldr r0, [r11, #J_STATE]
    cmp r0, #1
    bne tj_no
    ldr r0, [r11, #J_DST]
    cmp r0, #0
    bne tj_no
    ldr r0, [r11, #J_GEN]
    ldr r1, [r11, #GEN]
    cmp r0, r1
    bne tj_no
    ldr r0, [r11, #J_BASE]
    ldr r1, [r11, #J_DONE]
    adds r0, r0, r1
    bcs tj_no
    cmp r0, r5
    bne tj_no
    ldr r0, [r11, #J_LEN]
    cmp r1, r0
    bhs tj_no
    sub r0, r0, r1
    ldr r1, [r11, #J_STAGED]
    cmp r1, #0
    beq tj_no
    cmp r1, r0
    bhi tj_no
    cmp r1, #CHUNK
    bhi tj_no
    add r1, r1, #31
    bic r1, r1, #31
    cmp r1, r6, lsl #1
    bne tj_no
    bl swap_ok
    cmp r0, #0
    beq tj_no
    ldr r0, [r11, #J_SLOT]
    bl resident
    cmp r0, #0
    moveq r0, #1
    movne r0, #0
    b tj_out
tj_no:
    mov r0, #0
tj_out:
    .word 0xE121F008
    pop {r4-r8, r11, r12, pc}

; r0 setup revision. Returns whether the fully prepared job was activated.
job_activate:
    push {r4-r6, lr}
    mov r5, r0
    .word 0xE10F4000
    orr r0, r4, #0x80
    .word 0xE121F000
    ldr r0, [r11, #J_GEN]
    ldr r1, [r11, #GEN]
    cmp r0, r1
    bne ja_no
    ldr r0, =P_STATE
    ldr r1, [r0, #148]
    cmp r1, #0
    bne ja_no
    ldr r0, [r0, #128]
    cmp r0, r5
    bne ja_no
    ldr r0, [r11, #MODE]
    cmp r0, #1
    bne ja_no
    ldr r0, [r11, #TSTATE]
    cmp r0, #1
    bhi ja_no
    bl swap_ok
    cmp r0, #0
    beq ja_no
    ldr r0, [r11, #J_DST]
    cmp r0, #0
    bne ja_yes
    ldr r0, [r11, #J_SLOT]
    bl resident
    cmp r0, #0
    bne ja_no
ja_yes:
    mov r0, #1
    str r0, [r11, #J_STATE]
    b ja_out
ja_no:
    mov r0, #0
    str r0, [r11, #J_STATE]
ja_out:
    .word 0xE121F004
    pop {r4-r6, pc}

; r0 slot, r1 placement revision. Called inside the allocation IRQ commit.
allocation_ok:
    push {r4-r6, lr}
    mov r4, r0
    mov r5, r1
    ldr r0, [r11, #MODE]
    cmp r0, #1
    bne ao_no
    ldr r0, [r11, #TSTATE]
    cmp r0, #1
    bhi ao_no
    bl swap_ok
    cmp r0, #0
    beq ao_no
    ldr r0, [r11, #J_GEN]
    ldr r1, [r11, #GEN]
    cmp r0, r1
    bne ao_no
    ldr r0, =P_STATE
    ldr r1, [r0, #148]
    cmp r1, #0
    bne ao_no
    ldr r0, [r0, #128]
    cmp r0, r5
    bne ao_no
    mov r0, r4
    bl resident
    cmp r0, #0
    moveq r0, #1
    movne r0, #0
    pop {r4-r6, pc}
ao_no:
    mov r0, #0
    pop {r4-r6, pc}

; A prepared view remains valid after deleting one checked clean row.
protection_removed:
    ldr r1, =P_STATE
    ldr r0, [r1, #128]
    cmn r0, #1
    moveq r0, #1
    streq r0, [r1, #148]
    bxeq lr
    add r0, r0, #1
    str r0, [r1, #128]
    str r0, [r1, #132]
    bx lr

protection_current:
    ldr r0, [r11, #TSTATE]
    cmp r0, #1
    movhi r0, #0
    bxhi lr
    ldr r0, [r11, #MODE]
    cmp r0, #1
    movne r0, #0
    bxne lr
    ldr r1, =P_STATE
    ldr r0, [r1, #148]
    cmp r0, #0
    movne r0, #0
    bxne lr
    ldr r0, [r1, #144]
    cmp r0, #1
    movne r0, #0
    bxne lr
    ldr r0, [r1, #128]
    ldr r2, [r1, #132]
    cmp r0, r2
    ldreq r0, [r11, #GEN]
    ldreq r2, [r1, #136]
    cmpeq r0, r2
    movne r0, #0
    moveq r0, #1
    bx lr
.pool

; The parser owns no part of this caller frame except the explicit revision stamp.
ss_boot_parse:
    push {r4-r6, r11, r12, lr}
    sub sp, sp, #8
    sub r4, r8, r5
    sub r4, r4, #0x14
    mov r4, r4, lsr #2
    mov r5, r1
    mov r12, #0
    str r12, [sp, #4]
    bl PARSER
boot_parse_done:
    mov r6, r0
    cmp r6, #0
    bne boot_parse_out
    ldr r0, [sp, #4]
    cmp r0, #1
    bne boot_parse_out
    ldrh r0, [r5]
    cmp r0, r4
    bne boot_parse_out
    ldr r11, =ST
    ldr r1, [sp]
    bl mark_clean
boot_parse_out:
    mov r0, r6
    add sp, sp, #8
    pop {r4-r6, r11, r12, pc}
.pool
'''
