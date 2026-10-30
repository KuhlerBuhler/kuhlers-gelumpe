"""Stream a native sample snapshot into the journalled slot writer.

The caller owns the file lease, pins the sample and supplies 0x10600 bytes
of scratch separate from sample_store's scratch and its output buffer.
No hooks or firmware RAM are installed by this module.
"""
SIZE = 0x10600


def source(context, *, native=0xC004EBD4, transfer='transfer'):
    if context & 3 or not 0 <= context <= 0xFFFFFFFF - SIZE:
        raise ValueError('word aligned snapshot scratch required')
    values = dict(SNAP_CTX=context, SNAP_STREAM=context + 8,
                  SNAP_DESC=context + 0xA0, SNAP_BUFFER=context + 0x600,
                  SNAP_NATIVE=native)
    if isinstance(transfer, int):
        values['SNAP_TRANSFER'] = transfer
        target = 'SNAP_TRANSFER'
    elif isinstance(transfer, str) and transfer.isidentifier():
        target = transfer
    else:
        raise ValueError('transfer address or assembly label required')
    return (''.join(f'.equ {name}, {value:#x}\n' for name, value in values.items())
            + SOURCE.replace('SNAP_TRANSFER_CALL', target))


SOURCE = r'''
; r0 library path, r1 logical slot. The caller retains its sample and file leases.
store_snapshot:
    push {r4-r6, lr}
    mov r4, r0
    mov r5, r1
    mov r0, r5
    bl snapshot_prepare
    cmp r0, #0
    popne {r4-r6, pc}
    mov r0, r4
    ldr r1, =SNAP_CTX
    mov r2, r5
    ldr r3, =SNAP_STREAM
    ldr r3, [r3, #8]
    bl store_put
    pop {r4-r6, pc}

; r0 logical slot. Returns zero with a complete descriptor and canonical header.
snapshot_prepare:
    push {r4-r8, lr}
    sub sp, sp, #8
    cmp r0, #500
    blo snap_bad
    ldr r1, =998
    cmp r0, r1
    bhi snap_bad
    ldr r4, =SNAP_STREAM
    ldr r5, =SNAP_DESC
    str r0, [sp, #4]
    mov r1, #0
    str r1, [sp]
    mov r1, r5
    mov r2, r4
    add r3, r4, #4
    bl SNAP_NATIVE
    cmp r0, #1
    bne snap_bad
    ldr r0, [sp, #4]
    strb r0, [r5]
    strb r0, [r5, #78]
    add r1, r0, #50
    strb r1, [r5, #20]
    mov r1, r1, lsr #8
    strb r1, [r5, #21]
    mov r0, r0, lsr #8
    strb r0, [r5, #1]
    strb r0, [r5, #79]
    ldr r6, [r4]
    tst r6, #1
    bne snap_bad
    ldr r0, =0x365EC0
    cmp r6, r0
    blo snap_bad
    ldr r7, [r4, #4]
    cmp r7, #0
    beq snap_bad
    tst r7, #1
    bne snap_bad
    adds r0, r6, r7
    bcs snap_bad
    ldr r1, =0x1C65EC0
    cmp r0, r1
    bhi snap_bad
    ldrb r8, [r5, #65]
    cmp r8, #1
    bhi snap_bad
    add r8, r8, #1
    mov r6, r8, lsl #1
    sub r0, r6, #1
    tst r7, r0
    bne snap_bad
    ldr r2, [r5, #72]
    cmp r2, #0
    beq snap_bad
    cmp r6, #2
    moveq r1, r2, lsr #31
    movne r1, r2, lsr #30
    cmp r1, #0
    bne snap_bad
    mul r0, r2, r6
    str r5, [r4, #12]
    ldr r1, =1232
    add r1, r7, r1
    str r1, [r4, #8]
    ldr r3, =0x46464952
    str r3, [r4, #16]
    sub r1, r1, #8
    str r1, [r4, #20]
    ldr r1, =0x45564157
    str r1, [r4, #24]
    ldr r1, =0x20746D66
    str r1, [r4, #28]
    mov r1, #16
    str r1, [r4, #32]
    mov r3, r8, lsl #16
    orr r3, r3, #1
    str r3, [r4, #36]
    str r2, [r4, #40]
    str r0, [r4, #44]
    orr r6, r6, r1, lsl #16
    str r6, [r4, #48]
    ldr r0, =0x61746164
    str r0, [r4, #52]
    str r7, [r4, #56]
    ldr r0, =0x67726F6B
    str r0, [r4, #60]
    ldr r0, =1180
    str r0, [r4, #64]
    ldr r0, =0x696C7365
    str r0, [r4, #68]
    ldr r0, =1172
    str r0, [r4, #72]
    ldr r0, =SNAP_CTX
    ldr r1, =snapshot_read
    str r1, [r0]
    str r4, [r0, #4]
    mov r0, #0
    b snap_out
snap_bad:
    mov r0, #1
snap_out:
    add sp, sp, #8
    pop {r4-r8, pc}
.pool

; r0 stream, r1 entry byte offset, r2 destination, r3 requested bytes.
; Returns status and completed bytes in r0/r1, including on partial failure.
snapshot_read:
    push {r3-r11, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r7, r3
    mov r8, #0
    ldr r0, [r4, #8]
    cmp r5, r0
    bhs snr_ok
    sub r0, r0, r5
    cmp r7, r0
    movhi r7, r0
snr_piece:
    cmp r7, #0
    beq snr_ok
    cmp r5, #44
    bhs snr_pcm
    add r0, r4, #16
    add r0, r0, r5
    rsb r9, r5, #44
    b snr_copy
snr_pcm:
    ldr r0, [r4, #4]
    add r10, r0, #44
    cmp r5, r10
    bhs snr_metadata
    sub r9, r10, r5
    cmp r9, r7
    movhi r9, r7
    sub r10, r5, #44
    and r11, r10, #1
    ldr r0, =65536
    sub r0, r0, r11
    cmp r9, r0
    movhi r9, r0
    bic r10, r10, #1
    ldr r2, [r4]
    add r2, r2, r10
    add r3, r9, r11
    add r3, r3, #1
    mov r3, r3, lsr #1
    mov r0, #0
    ldr r1, =SNAP_BUFFER
    bl SNAP_TRANSFER_CALL
    cmp r0, #0
    bne snr_error
    add r2, r9, r11
    add r2, r2, #1
    mov r2, r2, lsr #1
    cmp r1, r2
    bne snr_error
    ldr r0, =SNAP_BUFFER
    add r0, r0, r11
    b snr_copy
snr_metadata:
    sub r1, r5, r10
    cmp r1, #16
    bhs snr_descriptor
    add r0, r4, #60
    add r0, r0, r1
    rsb r9, r1, #16
    b snr_copy
snr_descriptor:
    sub r1, r1, #16
    ldr r0, [r4, #12]
    add r0, r0, r1
    ldr r9, =1172
    sub r9, r9, r1
snr_copy:
    cmp r9, r7
    movhi r9, r7
    mov r2, r9
    mov r3, r6
snr_byte:
    ldrb r1, [r0], #1
    strb r1, [r3], #1
    subs r2, r2, #1
    bne snr_byte
    add r5, r5, r9
    add r6, r6, r9
    add r8, r8, r9
    sub r7, r7, r9
    b snr_piece
snr_ok:
    mov r0, #0
    b snr_return
snr_error:
    mov r0, #1
snr_return:
    mov r1, r8
    pop {r3-r11, pc}
.pool
'''
