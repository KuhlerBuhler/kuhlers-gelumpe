"""ARM recovery for the single-slot journal of src/sample-transaction.mjs.

The caller owns the command task and supplies 0x13000 bytes of scratch RAM.
This builder installs no hooks and reserves no firmware RAM on its own.
"""
import struct
import re

import arm

API = dict(OPEN=0xC009DB60, READ=0xC009DD74, WRITE=0xC009DFB8,
           CLOSE=0xC009E3DC, SEEK=0xC009E404, UNLINK=0xC009E9B8)


def _constants(state):
    return dict(CTX=state, FIL=state, GOT=state + 0x240, LIB_PATH=state + 0x250,
                JOURNAL=state + 0x300, TXN_PATH=state + 0x1340,
                HEAD=state + 0x1400, BUFFER=state + 0x3000,
                **{f"FS_{name}": address for name, address in API.items()})


def _render(code):
    magic = struct.unpack("<2I", b"BLECHTX1")
    header = struct.unpack("<4I", b"e2s sample all\x1a\0")
    code = code.replace("MAGIC0", str(magic[0])).replace("MAGIC1", str(magic[1]))
    for i, value in enumerate(header):
        code = code.replace(f"HEADER{i}", str(value))
    code = re.sub(r"\b(" + "|".join(_constants(0)) + r")\b", lambda match: "STORE_" + match.group(), code)
    return re.sub(r"\b(?:sr|sj|sv|sl|sw|sf|sc|sp|si|ss)_[a-z0-9_]+\b", lambda match: "store_" + match.group(), code)


def source(state, include_writer=True):
    if state & 3:
        raise ValueError("scratch must be word aligned")
    constants = _constants(state)
    equs = "".join(f".equ {name}, {value:#x}\n" for name, value in constants.items())
    return _render(equs + SOURCE + (WRITE_SOURCE if include_writer else ""))


def writer_source():
    return _render(WRITE_SOURCE)


def build_code(origin, state):
    if origin & 3:
        raise ValueError("code must be word aligned")
    result = arm.assemble(source(state), origin=origin)
    return result.bytes, result.symbols


SOURCE = r"""
; r0 library path ending in .all. Returns 0 for no journal or completed recovery, 1 on a refused or failed recovery.
store_recover:
    push {r3-r11, lr}
    ldr r11, =CTX
    ldr r4, =LIB_PATH
    ldr r5, =TXN_PATH
    mov r3, #0
sr_path:
    ldrb r1, [r0, r3]
    strb r1, [r4, r3]
    strb r1, [r5, r3]
    cmp r1, #0
    beq sr_suffix
    add r3, r3, #1
    cmp r3, #127
    blo sr_path
    b sr_bad
sr_suffix:
    cmp r3, #4
    blo sr_bad
    sub r0, r3, #4
    ldrb r1, [r4, r0]
    cmp r1, #46
    bne sr_bad
    add r0, r5, r3
    sub r0, r0, #3
    mov r1, #116
    strb r1, [r0]
    mov r1, #120
    strb r1, [r0, #1]
    mov r1, #110
    strb r1, [r0, #2]
    bl store_read_journal
    cmp r0, #2
    beq sr_ok
    cmp r0, #0
    bne sr_bad
    bl store_validate
    cmp r0, #0
    bne sr_bad
    bl store_check_library
    cmp r0, #2
    beq sr_bad
    mov r7, r0
    ldr r4, =JOURNAL + 64
    ldr r5, =HEAD
    mov r6, #1024
sr_copy:
    ldr r0, [r4], #4
    str r0, [r5], #4
    subs r6, r6, #1
    bne sr_copy
    cmp r7, #0
    bne sr_write
    ldr r4, =JOURNAL
    ldr r0, [r4, #16]
    ldr r1, =HEAD + 16
    add r1, r1, r0, lsl #2
    ldr r0, [r4, #28]
    str r0, [r1]
sr_write:
    bl store_write_header
    cmp r0, #0
    bne sr_bad
    bl store_verify_header
    cmp r0, #0
    bne sr_bad
    ldr r0, =TXN_PATH
    bl FS_UNLINK
    cmp r0, #0
    bne sr_bad
sr_ok:
    mov r0, #0
    pop {r3-r11, pc}
sr_bad:
    mov r0, #1
    pop {r3-r11, pc}
.pool

; r0 library path, r1 preferred slot or -1. Returns status in r0 and selected slot in r1, -1 on failure.
store_select:
    push {r4-r8, lr}
    mov r4, r1
    bl store_recover
    cmp r0, #0
    bne store_select_bad
    ldr r0, =FIL
    ldr r1, =LIB_PATH
    mov r2, #1
    bl FS_OPEN
    cmp r0, #4
    cmpne r0, #5
    beq store_select_missing
    cmp r0, #0
    bne store_select_bad
    ldr r0, =FIL
    ldr r7, [r0, #12]
    ldr r1, =HEAD
    mov r2, #4096
    bl store_read
    cmp r0, #0
    bne store_select_close
    ldr r0, =HEAD
    mov r1, r7
    bl store_header_valid
store_select_close:
    bl store_close
    cmp r0, #0
    bne store_select_bad
    cmp r4, #0
    bge store_select_preferred
    mov r4, #500
    ldr r5, =HEAD + 16
    ldr r6, =998
store_select_scan:
    ldr r0, [r5, r4, lsl #2]
    cmp r0, #0
    beq store_select_ok
    add r4, r4, #1
    cmp r4, r6
    bls store_select_scan
    mov r0, #2
    b store_select_out
store_select_missing:
    cmp r4, #0
    movlt r4, #500
store_select_preferred:
    cmp r4, #500
    blo store_select_bad
    ldr r0, =998
    cmp r4, r0
    bhi store_select_bad
store_select_ok:
    mov r0, #0
    mov r1, r4
    pop {r4-r8, pc}
store_select_bad:
    mov r0, #1
store_select_out:
    mvn r1, #0
    pop {r4-r8, pc}
.pool

; r0 header, r1 file size. Validates every offset without reading sample payloads.
store_header_valid:
    push {r4-r6, lr}
    mov r4, r0
    mov r5, r1
    cmp r5, #4096
    blo store_header_bad
    ldr r0, [r4]
    ldr r1, =HEADER0
    cmp r0, r1
    bne store_header_bad
    ldr r0, [r4, #4]
    ldr r1, =HEADER1
    cmp r0, r1
    bne store_header_bad
    ldr r0, [r4, #8]
    ldr r1, =HEADER2
    cmp r0, r1
    bne store_header_bad
    ldr r0, [r4, #12]
    ldr r1, =HEADER3
    cmp r0, r1
    bne store_header_bad
    mov r6, #16
store_header_offset:
    ldr r0, [r4, r6]
    cmp r0, #0
    beq store_header_next
    cmp r0, #4096
    blo store_header_bad
    adds r0, r0, #12
    bcs store_header_bad
    cmp r0, r5
    bhi store_header_bad
store_header_next:
    add r6, r6, #4
    cmp r6, #4096
    blo store_header_offset
    mov r0, #0
    pop {r4-r6, pc}
store_header_bad:
    mov r0, #1
    pop {r4-r6, pc}
.pool

store_read_journal:
    push {r4, lr}
    ldr r0, =FIL
    ldr r1, =TXN_PATH
    mov r2, #1
    bl FS_OPEN
    cmp r0, #4
    cmpne r0, #5
    moveq r0, #2
    popeq {r4, pc}
    cmp r0, #0
    movne r0, #1
    popne {r4, pc}
    ldr r0, =FIL
    ldr r0, [r0, #12]
    ldr r1, =4160
    cmp r0, r1
    movne r0, #1
    bne sj_close
    ldr r1, =JOURNAL
    mov r2, r0
    bl store_read
sj_close:
    bl store_close
    pop {r4, pc}

store_validate:
    push {r4-r10, lr}
    ldr r4, =JOURNAL
    ldr r0, [r4]
    ldr r1, =MAGIC0
    cmp r0, r1
    bne sv_bad
    ldr r0, [r4, #4]
    ldr r1, =MAGIC1
    cmp r0, r1
    bne sv_bad
    ldr r0, [r4, #8]
    cmp r0, #1
    bne sv_bad
    ldr r0, [r4, #48]
    ldr r1, [r4, #52]
    orr r0, r0, r1
    ldr r1, [r4, #56]
    orrs r0, r0, r1
    bne sv_bad
    ldr r5, [r4, #60]
    mov r0, #0
    str r0, [r4, #60]
    mov r0, r4
    ldr r1, =4160
    mvn r2, #0
    bl store_crc
    mvn r0, r0
    str r5, [r4, #60]
    cmp r0, r5
    bne sv_bad
    ldr r6, [r4, #16]
    cmp r6, #500
    blo sv_bad
    ldr r1, =998
    cmp r6, r1
    bhi sv_bad
    ldr r7, [r4, #20]
    cmp r7, #4096
    blo sv_bad
    ldr r8, [r4, #12]
    ldr r0, [r4, #28]
    ldr r1, [r4, #32]
    ldr r9, [r4, #24]
    cmp r8, #1
    bne sv_delete
    cmp r0, r7
    bne sv_bad
    cmp r1, #12
    blo sv_bad
    adds r0, r7, r1
    bcs sv_bad
    cmp r0, r9
    bne sv_bad
    b sv_header
sv_delete:
    cmp r8, #2
    bne sv_bad
    orrs r0, r0, r1
    bne sv_bad
    ldr r0, [r4, #36]
    cmp r0, #0
    bne sv_bad
    cmp r7, r9
    bne sv_bad
sv_header:
    add r5, r4, #64
    mov r0, r5
    mov r1, r7
    bl store_header_valid
    cmp r0, #0
    bne sv_bad
    mov r0, r5
    mov r1, #4096
    mvn r2, #0
    bl store_crc
    mvn r0, r0
    ldr r1, [r4, #40]
    cmp r0, r1
    bne sv_bad
    add r5, r5, #16
    add r5, r5, r6, lsl #2
    ldr r7, [r5]
    ldr r0, [r4, #28]
    str r0, [r5]
    add r0, r4, #64
    mov r1, #4096
    mvn r2, #0
    bl store_crc
    mvn r0, r0
    str r7, [r5]
    ldr r1, [r4, #44]
    cmp r0, r1
    bne sv_bad
    mov r0, #0
    pop {r4-r10, pc}
sv_bad:
    mov r0, #1
    pop {r4-r10, pc}
.pool

store_check_library:
    push {r4-r10, lr}
    ldr r0, =FIL
    ldr r1, =LIB_PATH
    mov r2, #1
    bl FS_OPEN
    cmp r0, #0
    bne sl_abort
    ldr r0, =FIL
    ldr r10, [r0, #12]
    ldr r4, =JOURNAL
    ldr r0, [r4, #20]
    cmp r10, r0
    blo sl_error
    ldr r1, =HEAD
    mov r2, #4096
    bl store_read
    cmp r0, #0
    bne sl_error
    add r5, r4, #64
    ldr r6, [r4, #16]
    mov r6, r6, lsl #2
    add r6, r6, #16
    mov r6, r6, lsr #9
    mov r6, r6, lsl #9
    add r7, r6, #512
    mov r8, #0
    ldr r9, =HEAD
sl_header:
    cmp r8, r6
    blo sl_compare
    cmp r8, r7
    blo sl_next
sl_compare:
    ldr r0, [r5, r8]
    ldr r1, [r9, r8]
    cmp r0, r1
    bne sl_error
sl_next:
    add r8, r8, #4
    cmp r8, #4096
    blo sl_header
    ldr r0, [r4, #12]
    cmp r0, #2
    beq sl_complete
    ldr r0, [r4, #24]
    cmp r10, r0
    blo sl_incomplete
    ldr r0, =FIL
    ldr r1, [r4, #28]
    bl FS_SEEK
    cmp r0, #0
    bne sl_error
    ldr r8, [r4, #32]
    mvn r9, #0
sl_payload:
    mov r6, r8
    cmp r6, #65536
    movhi r6, #65536
    ldr r1, =BUFFER
    mov r2, r6
    bl store_read
    cmp r0, #0
    bne sl_error
    ldr r0, =BUFFER
    mov r1, r6
    mov r2, r9
    bl store_crc
    mov r9, r0
    subs r8, r8, r6
    bne sl_payload
    mvn r0, r9
    ldr r1, [r4, #36]
    cmp r0, r1
    bne sl_incomplete
sl_complete:
    mov r10, #0
    b sl_close
sl_incomplete:
    mov r10, #1
sl_close:
    mov r0, #0
    bl store_close
    cmp r0, #0
    bne sl_abort
    mov r0, r10
    pop {r4-r10, pc}
sl_error:
    mov r0, #1
    bl store_close
sl_abort:
    mov r0, #2
    pop {r4-r10, pc}
.pool

store_write_header:
    push {r4, lr}
    ldr r0, =FIL
    ldr r1, =LIB_PATH
    mov r2, #3
    bl FS_OPEN
    cmp r0, #0
    movne r0, #1
    popne {r4, pc}
    ldr r0, =FIL
    mov r1, #0
    bl FS_SEEK
    cmp r0, #0
    movne r0, #1
    bne sw_close
    ldr r0, =FIL
    ldr r1, =HEAD
    mov r2, #4096
    ldr r3, =GOT
    bl FS_WRITE
    cmp r0, #0
    movne r0, #1
    bne sw_close
    ldr r0, =GOT
    ldr r0, [r0]
    cmp r0, #4096
    moveq r0, #0
    movne r0, #1
sw_close:
    bl store_close
    pop {r4, pc}

store_verify_header:
    push {r4, lr}
    ldr r0, =FIL
    ldr r1, =LIB_PATH
    mov r2, #1
    bl FS_OPEN
    cmp r0, #0
    movne r0, #1
    popne {r4, pc}
    ldr r1, =BUFFER
    mov r2, #4096
    bl store_read
    bl store_close
    cmp r0, #0
    popne {r4, pc}
    ldr r1, =HEAD
    ldr r2, =BUFFER
    mov r4, #1024
sf_word:
    ldr r0, [r1], #4
    ldr r3, [r2], #4
    cmp r0, r3
    movne r0, #1
    popne {r4, pc}
    subs r4, r4, #1
    bne sf_word
    mov r0, #0
    pop {r4, pc}

; r1 destination, r2 length; the file is already open.
store_read:
    push {r4, lr}
    mov r4, r2
    ldr r0, =FIL
    ldr r3, =GOT
    bl FS_READ
    cmp r0, #0
    movne r0, #1
    popne {r4, pc}
    ldr r0, =GOT
    ldr r0, [r0]
    cmp r0, r4
    moveq r0, #0
    movne r0, #1
    pop {r4, pc}

; r0 an earlier error flag; closing must succeed as well.
store_close:
    push {r4, lr}
    mov r4, r0
    ldr r0, =FIL
    bl FS_CLOSE
    cmp r0, #0
    movne r4, #1
    mov r0, r4
    pop {r4, pc}

; r0 bytes, r1 length, r2 uncomplemented running CRC. Returns the uncomplemented CRC.
store_crc:
    push {r4-r6, lr}
    ldr r6, =0xEDB88320
sc_byte:
    cmp r1, #0
    beq sc_done
    ldrb r3, [r0], #1
    eor r2, r2, r3
    mov r5, #8
sc_bit:
    tst r2, #1
    mov r2, r2, lsr #1
    eorne r2, r2, r6
    subs r5, r5, #1
    bne sc_bit
    subs r1, r1, #1
    bne sc_byte
sc_done:
    mov r0, r2
    pop {r4-r6, pc}
.pool
"""


WRITE_SOURCE = r"""
; r0 library path, r1 {read callback, context}, r2 slot, r3 canonical entry length. Caller owns the parent directory.
; The callback receives context, offset, destination, length and returns status, completed count in r0, r1.
store_put:
    push {r3-r11, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r7, r3
    cmp r5, #0
    beq sp_bad
    ldr r0, =1232
    cmp r7, r0
    blo sp_bad
    b sp_start

store_delete:
    push {r3-r11, lr}
    mov r4, r0
    mov r6, r1
    mov r5, #0
    mov r7, #0
sp_start:
    cmp r6, #500
    blo sp_bad
    ldr r0, =998
    cmp r6, r0
    bhi sp_bad
    mov r0, r4
    bl store_recover
    cmp r0, #0
    bne sp_bad
    ldr r11, =CTX
    cmp r5, #0
    beq sp_open
    bl store_validate_source
    cmp r0, #0
    bne sp_bad
sp_open:
    ldr r0, =FIL
    ldr r1, =LIB_PATH
    cmp r5, #0
    moveq r2, #3
    movne r2, #0x13
    bl FS_OPEN
    cmp r0, #0
    beq sp_opened
    cmp r5, #0
    bne sp_bad
    cmp r0, #4
    cmpne r0, #5
    beq sp_ok
    b sp_bad
sp_opened:
    ldr r0, =FIL
    ldr r8, [r0, #12]
    cmp r8, #0
    bne sp_have_file
    ldr r1, =JOURNAL + 64
    mov r2, #1024
    mov r0, #0
sp_empty:
    str r0, [r1], #4
    subs r2, r2, #1
    bne sp_empty
    ldr r1, =JOURNAL + 64
    ldr r0, =HEADER0
    str r0, [r1]
    ldr r0, =HEADER1
    str r0, [r1, #4]
    ldr r0, =HEADER2
    str r0, [r1, #8]
    ldr r0, =HEADER3
    str r0, [r1, #12]
    mov r2, #4096
    bl store_write
    cmp r0, #0
    bne sp_close_error
    mov r8, #4096
sp_have_file:
    cmp r8, #4096
    blo sp_close_error
    ldr r0, =FIL
    mov r1, #0
    bl FS_SEEK
    cmp r0, #0
    bne sp_close_error
    ldr r1, =JOURNAL + 64
    mov r2, #4096
    bl store_read
    cmp r0, #0
    bne sp_close_error
    ldr r0, =JOURNAL + 64
    mov r1, r8
    bl store_header_valid
    cmp r0, #0
    bne sp_close_error
    cmp r5, #0
    beq sp_changed
    bl store_same_source
    cmp r0, #2
    beq sp_close_error
    cmp r0, #1
    bne sp_changed
    mov r0, #0
    bl store_close
    pop {r3-r11, pc}
sp_changed:
    adds r0, r8, r7
    bcs sp_close_error
    ldr r4, =JOURNAL
    mov r0, #0
    mov r1, r4
    mov r2, #16
sp_prefix:
    str r0, [r1], #4
    subs r2, r2, #1
    bne sp_prefix
    ldr r0, =MAGIC0
    str r0, [r4]
    ldr r0, =MAGIC1
    str r0, [r4, #4]
    mov r0, #1
    str r0, [r4, #8]
    cmp r5, #0
    moveq r0, #2
    str r0, [r4, #12]
    str r6, [r4, #16]
    str r8, [r4, #20]
    add r0, r8, r7
    str r0, [r4, #24]
    cmp r5, #0
    movne r0, r8
    moveq r0, #0
    str r0, [r4, #28]
    str r7, [r4, #32]
    bl store_seal
    bl store_validate
    cmp r0, #0
    bne sp_close_error
    ldr r0, =FIL
    mov r1, r8
    bl FS_SEEK
    cmp r0, #0
    bne sp_close_error
    mov r10, #0
    mvn r9, #0
sp_append:
    sub r4, r7, r10
    cmp r4, #0
    beq sp_appended
    cmp r4, #65536
    movhi r4, #65536
    mov r0, r10
    ldr r1, =BUFFER
    mov r2, r4
    bl store_source
    cmp r0, #0
    bne sp_close_error
    ldr r1, =BUFFER
    mov r2, r4
    bl store_write
    cmp r0, #0
    bne sp_close_error
    ldr r0, =BUFFER
    mov r1, r4
    mov r2, r9
    bl store_crc
    mov r9, r0
    add r10, r10, r4
    b sp_append
sp_appended:
    mov r0, #0
    bl store_close
    cmp r0, #0
    bne sp_bad
    mvn r0, r9
    ldr r4, =JOURNAL
    str r0, [r4, #36]
    bl store_seal
    bl store_check_library
    cmp r0, #0
    bne sp_bad
    ldr r0, =FIL
    ldr r1, =TXN_PATH
    mov r2, #0xA
    bl FS_OPEN
    cmp r0, #0
    bne sp_bad
    ldr r1, =JOURNAL
    ldr r2, =4160
    bl store_write
    bl store_close
    cmp r0, #0
    bne sp_bad
    ldr r10, [r4, #60]
    bl store_read_journal
    cmp r0, #0
    bne sp_bad
    bl store_validate
    cmp r0, #0
    bne sp_bad
    ldr r0, [r4, #60]
    cmp r0, r10
    bne sp_bad
    add r0, r4, #64
    ldr r1, =HEAD
    mov r2, #1024
sp_head:
    ldr r3, [r0], #4
    str r3, [r1], #4
    subs r2, r2, #1
    bne sp_head
    ldr r1, =HEAD + 16
    add r1, r1, r6, lsl #2
    ldr r0, [r4, #28]
    str r0, [r1]
    bl store_write_index
    cmp r0, #0
    bne sp_bad
    bl store_verify_header
    cmp r0, #0
    bne sp_bad
    ldr r0, =TXN_PATH
    bl FS_UNLINK
    cmp r0, #0
    bne sp_bad
sp_ok:
    mov r0, #0
    pop {r3-r11, pc}
sp_close_error:
    mov r0, #1
    bl store_close
sp_bad:
    mov r0, #1
    pop {r3-r11, pc}
.pool

store_seal:
    push {r4-r8, lr}
    ldr r4, =JOURNAL
    add r0, r4, #64
    mov r1, #4096
    mvn r2, #0
    bl store_crc
    mvn r0, r0
    str r0, [r4, #40]
    ldr r5, [r4, #16]
    add r6, r4, #64
    add r6, r6, #16
    add r6, r6, r5, lsl #2
    ldr r7, [r6]
    ldr r0, [r4, #28]
    str r0, [r6]
    add r0, r4, #64
    mov r1, #4096
    mvn r2, #0
    bl store_crc
    str r7, [r6]
    mvn r0, r0
    str r0, [r4, #44]
    mov r0, #0
    str r0, [r4, #60]
    mov r0, r4
    ldr r1, =4160
    mvn r2, #0
    bl store_crc
    mvn r0, r0
    str r0, [r4, #60]
    pop {r4-r8, pc}

store_write_index:
    push {r4, lr}
    ldr r0, =FIL
    ldr r1, =LIB_PATH
    mov r2, #3
    bl FS_OPEN
    cmp r0, #0
    movne r0, #1
    popne {r4, pc}
    mov r4, r6, lsl #2
    add r4, r4, #16
    ldr r0, =FIL
    mov r1, r4
    bl FS_SEEK
    cmp r0, #0
    movne r0, #1
    bne si_close
    ldr r1, =HEAD
    add r1, r1, r4
    mov r2, #4
    bl store_write
si_close:
    bl store_close
    pop {r4, pc}

store_write:
    push {r4, lr}
    mov r4, r2
    ldr r0, =FIL
    ldr r3, =GOT
    bl FS_WRITE
    cmp r0, #0
    movne r0, #1
    popne {r4, pc}
    ldr r0, =GOT
    ldr r0, [r0]
    cmp r0, r4
    moveq r0, #0
    movne r0, #1
    pop {r4, pc}

store_source:
    push {r4, r6, r12, lr}
    mov r4, r0
    mov r6, r2
    mov r2, r1
    mov r1, r4
    mov r3, r6
    ldr r12, [r5]
    ldr r0, [r5, #4]
    mov lr, pc
    bx r12
    cmp r0, #0
    movne r0, #1
    popne {r4, r6, r12, pc}
    cmp r1, r6
    moveq r0, #0
    movne r0, #1
    pop {r4, r6, r12, pc}

; r5 source, r6 slot, r7 length, r8 file size. Returns 0 different, 1 equal, 2 failed.
store_same_source:
    push {r4, r6-r11, lr}
    ldr r0, =JOURNAL + 80
    ldr r4, [r0, r6, lsl #2]
    cmp r4, #0
    beq same_different
    adds r0, r4, r7
    bcs same_different
    cmp r0, r8
    bhi same_different
    ldr r0, =FIL
    mov r1, r4
    bl FS_SEEK
    cmp r0, #0
    bne same_error
    ldr r1, =HEAD
    mov r2, #8
    bl store_read
    cmp r0, #0
    bne same_error
    ldr r0, =HEAD
    ldr r1, [r0]
    ldr r2, =0x46464952
    cmp r1, r2
    bne same_different
    ldr r0, [r0, #4]
    adds r0, r0, #8
    bcs same_different
    cmp r0, r7
    bne same_different
    mov r9, #0
same_block:
    sub r10, r7, r9
    cmp r10, #0
    beq same_equal
    cmp r10, #4096
    movhi r10, #4096
    ldr r0, =FIL
    add r1, r4, r9
    bl FS_SEEK
    cmp r0, #0
    bne same_error
    ldr r1, =HEAD
    mov r2, r10
    bl store_read
    cmp r0, #0
    bne same_error
    mov r0, r9
    ldr r1, =BUFFER
    mov r2, r10
    bl store_source
    cmp r0, #0
    bne same_error
    ldr r0, =HEAD
    ldr r1, =BUFFER
    mov r12, r10
same_byte:
    ldrb r2, [r0], #1
    ldrb r3, [r1], #1
    cmp r2, r3
    bne same_different
    subs r12, r12, #1
    bne same_byte
    add r9, r9, r10
    b same_block
same_equal:
    mov r0, #1
    b same_return
same_different:
    mov r0, #0
    b same_return
same_error:
    mov r0, #2
same_return:
    pop {r4, r6-r11, pc}
.pool

store_validate_source:
    push {r4, lr}
    mov r0, #0
    ldr r1, =BUFFER
    mov r2, #44
    bl store_source
    cmp r0, #0
    bne ss_bad
    ldr r4, =BUFFER
    ldr r0, [r4]
    ldr r1, =0x46464952
    cmp r0, r1
    bne ss_bad
    ldr r0, [r4, #8]
    ldr r1, =0x45564157
    cmp r0, r1
    bne ss_bad
    ldr r0, [r4, #12]
    ldr r1, =0x20746D66
    cmp r0, r1
    bne ss_bad
    ldr r0, [r4, #16]
    cmp r0, #16
    bne ss_bad
    ldr r0, [r4, #20]
    mov r1, r0, lsr #16
    mov r0, r0, lsl #16
    mov r0, r0, lsr #16
    cmp r0, #1
    bne ss_bad
    cmp r1, #1
    cmpne r1, #2
    bne ss_bad
    ldr r0, [r4, #32]
    mov r0, r0, lsr #16
    cmp r0, #16
    cmpne r0, #24
    bne ss_bad
    ldr r0, [r4, #24]
    cmp r0, #0
    beq ss_bad
    ldr r0, [r4, #36]
    ldr r1, =0x61746164
    cmp r0, r1
    bne ss_bad
    ldr r0, [r4, #4]
    adds r0, r0, #8
    bcs ss_bad
    cmp r0, r7
    bne ss_bad
    ldr r0, [r4, #40]
    and r1, r0, #1
    adds r0, r0, #44
    bcs ss_bad
    adds r4, r0, r1
    bcs ss_bad
    ldr r1, =1188
    adds r0, r4, r1
    bcs ss_bad
    cmp r0, r7
    bne ss_bad
    mov r0, r4
    ldr r1, =BUFFER
    ldr r2, =1188
    bl store_source
    cmp r0, #0
    bne ss_bad
    ldr r4, =BUFFER
    ldr r0, [r4]
    ldr r1, =0x67726F6B
    cmp r0, r1
    bne ss_bad
    ldr r0, [r4, #8]
    ldr r1, =0x696C7365
    cmp r0, r1
    bne ss_bad
    ldr r0, [r4, #4]
    ldr r1, =1180
    cmp r0, r1
    bne ss_bad
    ldr r0, [r4, #12]
    ldr r1, =1172
    cmp r0, r1
    bne ss_bad
    ldr r0, [r4, #16]
    mov r0, r0, lsl #16
    mov r0, r0, lsr #16
    cmp r0, r6
    bne ss_bad
    ldrb r0, [r4, #94]
    ldrb r1, [r4, #95]
    orr r0, r0, r1, lsl #8
    cmp r0, r6
    bne ss_bad
    mov r0, #0
    pop {r4, pc}
ss_bad:
    mov r0, #1
    pop {r4, pc}
.pool
"""
