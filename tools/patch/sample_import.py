"""A streaming canonical entry from the firmware parser's descriptor and an open WAV file."""
def source(*, state, file, descriptor, normalizer, prep, bits, file_bytes):
    values = dict(IMP_STATE=state, IMP_FIL=file, IMP_DESC=descriptor, IMP_NORMAL=normalizer,
                  IMP_PREP=state + prep, IMP_BITS=state + bits, IMP_BYTES=state + file_bytes,
                  IMP_OPEN=0xC009DB60, IMP_READ=0xC009DD74, IMP_CLOSE=0xC009E3DC,
                  IMP_SEEK=0xC009E404, IMP_PARSER=0xC0035B10, IMP_INIT=0xC004E1F4)
    return "".join(f".equ {name}, {value:#x}\n" for name, value in values.items()) + SOURCE


SOURCE = r"""
; r0 source WAV path, r1 chosen slot or -1, r2 library path. Returns status in r0, chosen slot in r1.
; Caller owns the command task, closed the swap file and dropped its cache; it refreshes the catalogue after success.
store_import:
    push {r3-r11, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r0, r6
    mov r1, r5
    bl store_select
    cmp r0, #0
    bne imp_error
    mov r5, r1
    ldr r0, =IMP_FIL
    mov r1, r4
    mov r2, #1
    bl IMP_OPEN
    cmp r0, #0
    bne imp_error
    ldr r0, =IMP_DESC
    bl IMP_INIT
    ldr r0, =IMP_PREP
    mov r1, #1
    str r1, [r0]
    ldr r0, =IMP_FIL
    ldr r1, =IMP_DESC
    mov r2, r5
    mov r3, r4
    bl IMP_PARSER
    mov r7, r0
    ldr r0, =IMP_PREP
    mov r1, #0
    str r1, [r0]
    cmp r7, #0x7E
    bne imp_close_error
    ldr r8, =IMP_NORMAL
    ldr r0, =import_read
    str r0, [r8]
    add r0, r8, #8
    str r0, [r8, #4]
    ldr r0, =IMP_FIL
    str r0, [r8, #8]
    ldr r0, [r0, #8]
    str r0, [r8, #12]
    ldr r0, =IMP_BYTES
    ldr r7, [r0]
    str r7, [r8, #16]
    and r0, r7, #1
    adds r9, r7, r0
    bcs imp_close_error
    ldr r0, =1232
    adds r9, r9, r0
    bcs imp_close_error
    str r9, [r8, #20]
    ldr r0, =IMP_DESC
    str r0, [r8, #24]
    strb r5, [r0]
    mov r1, r5, lsr #8
    strb r1, [r0, #1]
    strb r5, [r0, #78]
    strb r1, [r0, #79]
    ldr r2, =0x46464952
    str r2, [r8, #32]
    sub r2, r9, #8
    str r2, [r8, #36]
    ldr r2, =0x45564157
    str r2, [r8, #40]
    ldr r2, =0x20746D66
    str r2, [r8, #44]
    mov r2, #16
    str r2, [r8, #48]
    ldrb r1, [r0, #65]
    add r1, r1, #1
    cmp r1, #2
    bhi imp_close_error
    mov r2, r1, lsl #16
    orr r2, r2, #1
    str r2, [r8, #52]
    ldr r2, [r0, #72]
    str r2, [r8, #56]
    ldr r0, =IMP_BITS
    ldr r0, [r0]
    mov r3, r0, lsr #3
    mul r10, r1, r3
    mul r3, r2, r10
    str r3, [r8, #60]
    orr r10, r10, r0, lsl #16
    str r10, [r8, #64]
    ldr r0, =0x61746164
    str r0, [r8, #68]
    str r7, [r8, #72]
    ldr r0, =0x67726F6B
    str r0, [r8, #80]
    ldr r0, =1180
    str r0, [r8, #84]
    ldr r0, =0x696C7365
    str r0, [r8, #88]
    ldr r0, =1172
    str r0, [r8, #92]
    mov r0, #0
    str r0, [r8, #96]
    mov r0, r6
    mov r1, r8
    mov r2, r5
    mov r3, r9
    bl store_put
    mov r7, r0
    ldr r0, =IMP_FIL
    bl IMP_CLOSE
    orrs r7, r7, r0
    bne imp_error
    mov r0, #0
    mov r1, r5
    pop {r3-r11, pc}
imp_close_error:
    ldr r0, =IMP_FIL
    bl IMP_CLOSE
imp_error:
    mov r0, #4
    mvn r1, #0
    pop {r3-r11, pc}
.pool

; Context: file, PCM offset, file PCM bytes, total bytes, descriptor, four reserved bytes, WAV header, KORG header, padding, count.
import_read:
    push {r3-r11, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r7, r3
    mov r8, #0
    ldr r0, [r4, #12]
    cmp r5, r0
    bhs ir_ok
    sub r0, r0, r5
    cmp r7, r0
    movhi r7, r0
ir_piece:
    cmp r7, #0
    beq ir_ok
    cmp r5, #44
    bhs ir_pcm
    add r0, r4, #24
    add r0, r0, r5
    rsb r9, r5, #44
    b ir_copy
ir_pcm:
    ldr r0, [r4, #8]
    add r10, r0, #44
    cmp r5, r10
    bhs ir_padding
    sub r9, r10, r5
    cmp r9, r7
    movhi r9, r7
    sub r1, r5, #44
    ldr r0, [r4, #4]
    add r1, r1, r0
    ldr r0, [r4]
    bl IMP_SEEK
    cmp r0, #0
    bne ir_error
    ldr r0, [r4]
    mov r1, r6
    mov r2, r9
    add r3, r4, #92
    bl IMP_READ
    cmp r0, #0
    bne ir_error
    ldr r0, [r4, #92]
    cmp r0, r9
    bne ir_error
    b ir_moved
ir_padding:
    and r0, r0, #1
    add r10, r10, r0
    cmp r5, r10
    bhs ir_metadata
    add r0, r4, #88
    mov r9, #1
    b ir_copy
ir_metadata:
    sub r1, r5, r10
    cmp r1, #16
    bhs ir_descriptor
    add r0, r4, #72
    add r0, r0, r1
    rsb r9, r1, #16
    b ir_copy
ir_descriptor:
    sub r1, r1, #16
    ldr r0, [r4, #16]
    add r0, r0, r1
    ldr r9, =1172
    sub r9, r9, r1
ir_copy:
    cmp r9, r7
    movhi r9, r7
    mov r2, r9
    mov r3, r6
ir_byte:
    ldrb r1, [r0], #1
    strb r1, [r3], #1
    subs r2, r2, #1
    bne ir_byte
ir_moved:
    add r5, r5, r9
    add r6, r6, r9
    add r8, r8, r9
    sub r7, r7, r9
    b ir_piece
ir_ok:
    mov r0, #0
    mov r1, r8
    pop {r3-r11, pc}
ir_error:
    mov r0, #1
    mov r1, r8
    pop {r3-r11, pc}
.pool
"""
