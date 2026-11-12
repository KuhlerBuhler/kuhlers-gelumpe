"""Connect confirmed sample WRITE and deletion to the checked card catalogue."""
import hashlib

SPANS = (
    (0xC0035440, 0x18, "55c79a162a736ecb03f7319ff3ed1f76bab357c734c5e9355169985bfd327fac"),
    (0xC004E4EC, 0x6C, "6ba4ecc9ff657a23aaf7be4eee7c7f35f96fe2ca72bfcffe37643487c074a4ea"),
    (0xC004EF94, 0x60, "3a2938dcab2fc052947b2b1e5529c81ace6c9a37dbb91431e1db3bf93195e67c"),
    (0xC00396D8, 0x12C, "35edb7652cb89e270c9fffd2c5dc9231d38893c50c84759f4731b06dbcf99daa"),
    (0xC0039588, 0x5C, "0244a60f4cf0543038992d6f6a936bccfff33b541251927913b1d6104bdd09f5"),
    (0xC0035994, 0x4C, "1bef0e907af08b9a3ced2daed9d01edb592422f6eb060e3b473d5dbe7ff35a7d"),
    (0xC004EBD4, 0x1B4, "73572bc9b58dee2afb4a4735f386a57986db1c6fc1a7d7bcd026ffd6347d5b2f"),
)


def validate_firmware(vsb):
    for at, size, expected in SPANS:
        offset = at - 0xC0000000 + 0x100
        if hashlib.sha256(vsb[offset:offset + size]).hexdigest() != expected:
            raise ValueError(f"native sample persistence context differs at {at:#x}")


def source(raw_descriptor):
    return f".equ PS_RAW, {raw_descriptor:#x}\n.equ PS_MAGIC, 0x20733265\n" + SOURCE + CLEAN_SOURCE


SOURCE = r"""
persist_library_probe:
    push {r4, r5, r11, lr}
    bl 0xC0035440
    mov r4, r0
    cmp r0, #0
    bne persist_probe_out
    ldr r0, =ST
    ldr r0, [r0, #MODE]
    cmn r0, #1
    bne persist_probe_out
    ldr r0, =NATIVE_SCOPE
    ldr r0, [r0]
    cmn r0, #1
    bne persist_probe_out
    mov r0, #500
    bl persist_enter
    cmp r0, #0
    bne persist_probe_out
    bl catalogue_begin_import
    cmp r0, #0
    bne persist_probe_release
    mov r0, r1
    mov r1, #0
    bl catalogue_end_update
persist_probe_release:
    bl sample_leave
persist_probe_out:
    mov r0, r4
    pop {r4, r5, r11, pc}
.pool
native_save_command:
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    beq persist_save_command
    ldr r12, [r12, #0x18]
    tst r12, #KILL
    movne r6, r6, lsr #16
    bne 0xC003970C
persist_save_command:
    mov r0, r5
    bl persist_save
    mov r6, r0
    cmp r1, #0
    beq persist_command_status
    ldr r0, =PS_RAW
    ldr r1, =0xC0345A2C
    ldr r2, =293
persist_rollback:
    ldr r3, [r0], #4
    str r3, [r1], #4
    subs r2, r2, #1
    bne persist_rollback
    ldr r1, =0xC0345A20
    mov r0, #1
    strb r0, [r1]
persist_command_status:
    strb r6, [r4, #0x18]
    mov r6, r5
    b 0xC0039748

native_delete_command:
    ldr r12, =PANEL
    ldr r12, [r12]
    cmp r12, #0
    beq persist_delete_command
    ldr r12, [r12, #0x18]
    tst r12, #KILL
    beq persist_delete_command
    bl 0xC0035994
    b 0xC00395BC
persist_delete_command:
    bl persist_delete
    strb r0, [r5, #0x18]
    cmp r0, #0
    bne 0xC00395D8
    b 0xC00395C0
.pool

; r0 logical slot. A successful admission retains the sample lock until sample_leave.
persist_enter:
    push {r4-r6, lr}
    cmp r0, #500
    blo persist_enter_bad
    ldr r1, =LAST_USER
    cmp r0, r1
    bhi persist_enter_bad
    ldr r1, =NI_TASK
    ldr r1, [r1]
    ldr r2, =NI_COMMAND_TASK
    cmp r1, r2
    bne persist_enter_bad
    mov r0, #1
    bl sample_admit
    cmp r0, #0
    bne persist_enter_bad
    ldr r0, =NI_TRANSPORT
    ldr r0, [r0]
    cmp r0, #0
    beq persist_enter_release
    ldr r1, [r0, #0x308]
    cmp r1, #0
    cmpne r1, #12
    bne persist_enter_release
    ldr r11, =ST
    ldr r0, [r11, #MODE]
    cmn r0, #1
    bne persist_enter_ready
    ldrb r0, [r11, #PATH]
    cmp r0, #0
    cmpne r0, #255
    beq persist_enter_release
    bl native_scope_init
    bl swap_reset
    cmp r0, #0
    bne persist_enter_release
persist_enter_ready:
    mov r0, #0
    pop {r4-r6, pc}
persist_enter_release:
    bl sample_leave
persist_enter_bad:
    mov r0, #4
    pop {r4-r6, pc}
.pool

; r0 logical slot. Returns menu status and whether the snapshot is confirmed on card.
persist_save:
    push {r4-r10, r11, r12, lr}
    mov r4, r0
    bl persist_enter
    cmp r0, #0
    bne persist_save_bad
    mov r0, r4
    bl resident
    cmp r0, #0
    beq persist_save_release_bad
    bl catalogue_begin_import
    cmp r0, #0
    bne persist_save_release_bad
    mov r6, r1
    mov r7, r3
    mov r9, #0
    cmp r2, #0
    ldrne r0, =HDR + 16
    ldrne r9, [r0, r4, lsl #2]
    ldr r0, =NI_TRANSPORT
    ldr r0, [r0]
    ldr r0, [r0, #0x308]
    cmp r0, #12
    bne persist_snapshot
    cmp r9, #0
    movne r0, #4
    bne persist_save_finish
persist_snapshot:
    ldr r10, =PROTECTION_REV
    ldr r10, [r10]
    add r0, r11, #PATH
    mov r1, r4
    bl store_snapshot
    cmp r0, #0
    movne r0, #4
persist_save_finish:
    mov r1, r0
    mov r0, r6
    mov r3, r7
    bl catalogue_end_update
    mov r5, r0
    mov r8, #0
    ldr r0, =FILE_OWNER + 8
    ldr r0, [r0]
    cmp r0, #0
    bne persist_save_return
    ldr r0, [r11, #TSTATE]
    cmp r0, #1
    bhi persist_save_return
    cmp r5, #0
    moveq r8, #1
    beq persist_save_return
    cmp r2, #4096
    blo persist_save_return
    ldr r0, =HDR + 16
    ldr r0, [r0, r4, lsl #2]
    cmp r0, r9
    movne r8, #1
persist_save_return:
    cmp r8, #0
    movne r0, r4
    movne r1, r10
    blne persist_mark_clean
    bl sample_leave
    mov r0, r5
    mov r1, r8
    pop {r4-r10, r11, r12, pc}
persist_save_release_bad:
    bl sample_leave
persist_save_bad:
    mov r0, #4
    mov r1, #0
    pop {r4-r10, r11, r12, pc}
.pool

; r0 logical slot. Capture EXIT discards only its unconfirmed native row.
persist_delete:
    push {r4-r10, r11, r12, lr}
    mov r4, r0
    bl persist_enter
    cmp r0, #0
    bne persist_delete_bad
    mov r0, r4
    bl persist_has_alias
    cmp r0, #0
    bne persist_delete_release_bad
    mov r5, #0
    ldr r0, =NI_TRANSPORT
    ldr r0, [r0]
    ldr r0, [r0, #0x308]
    cmp r0, #12
    beq persist_delete_row
    bl catalogue_begin_import
    cmp r0, #0
    bne persist_delete_release_bad
    mov r6, r1
    mov r7, r3
    mov r9, #0
    cmp r2, #0
    ldrne r0, =HDR + 16
    ldrne r9, [r0, r4, lsl #2]
    add r0, r11, #PATH
    mov r1, r4
    bl store_delete
    cmp r0, #0
    movne r0, #4
    mov r1, r0
    mov r0, r6
    mov r3, r7
    bl catalogue_end_update
    mov r5, r0
    ldr r0, =FILE_OWNER + 8
    ldr r0, [r0]
    cmp r0, #0
    bne persist_delete_return
    cmp r5, #0
    beq persist_delete_row
    cmp r9, #0
    beq persist_delete_return
    cmp r2, #4096
    blo persist_delete_return
    ldr r0, =HDR + 16
    ldr r0, [r0, r4, lsl #2]
    cmp r0, #0
    bne persist_delete_return
persist_delete_row:
    mov r0, r4
    bl 0xC004E4EC
    cmp r0, #0
    blt persist_delete_name
    bl 0xC004E558
persist_delete_name:
    ldr r0, =NAMES + 12
    add r0, r0, r4, lsl #5
    mov r1, #0
    mov r2, #4
persist_delete_zero:
    str r1, [r0], #4
    subs r2, r2, #1
    bne persist_delete_zero
    ldr r0, =SIG
    str r1, [r0, r4, lsl #2]
persist_delete_return:
    bl sample_leave
    mov r0, r5
    pop {r4-r10, r11, r12, pc}
persist_delete_release_bad:
    bl sample_leave
persist_delete_bad:
    mov r0, #4
    pop {r4-r10, r11, r12, pc}
.pool
"""


CLEAN_SOURCE = r"""
; Only a uniquely named native row can lose its dirty protection after this slot is saved.
persist_mark_clean:
    push {r4-r6, lr}
    mov r4, r0
    mov r5, r1
    bl persist_has_alias
    cmp r0, #0
    bne persist_clean_out
    mov r0, r4
    mov r1, r5
    bl mark_clean
persist_clean_out:
    pop {r4-r6, pc}
.pool

; r0 logical slot. A loaded alias retains ownership of the physical row.
persist_has_alias:
    push {r4-r8, lr}
    mov r4, r0
    bl physical
    mov r6, r0
    ldr r1, =SAMPLE_COUNT
    cmp r6, r1
    bhs persist_no_alias
    mov r7, #0
persist_alias:
    cmp r7, r4
    beq persist_alias_next
    mov r0, r7
    bl physical
    cmp r0, r6
    bne persist_alias_next
    mov r0, r7
    bl resident
    cmp r0, #0
    movne r0, #1
    popne {r4-r8, pc}
persist_alias_next:
    add r7, r7, #1
    ldr r0, =SAMPLE_COUNT
    cmp r7, r0
    blo persist_alias
persist_no_alias:
    mov r0, #0
    pop {r4-r8, pc}
.pool

; The native capture row is also its proposed logical slot.
persist_capture_slot:
    push {r4-r8, lr}
    ldr r0, =PANEL
    ldr r0, [r0]
    cmp r0, #0
    beq persist_slot_mode
    ldr r0, [r0, #0x18]
    tst r0, #KILL
    bne persist_slot_native
persist_slot_mode:
    ldr r8, =ST
    ldr r0, [r8, #MODE]
    cmp r0, #2
    beq persist_slot_missing
    ldr r0, =FILE_OWNER + 8
    ldr r0, [r0]
    cmp r0, #0
    bne persist_slot_missing
    mov r4, #500
    mov r8, #0
    ldr r0, =HDR
    ldr r0, [r0]
    ldr r1, =PS_MAGIC
    cmp r0, r1
    moveq r8, #1
    ldr r5, =HDR + 16
    ldr r6, =META
    ldr r7, =0x45C
persist_slot_scan:
    cmp r8, #0
    ldrne r0, [r5, r4, lsl #2]
    cmpne r0, #0
    bne persist_slot_next
    mla r0, r4, r7, r6
    ldrb r0, [r0, #11]
    cmp r0, #0
    bne persist_slot_next
    mov r0, r4
    mov r1, r8
    bl persist_mapping_owner
    cmp r0, #1
    bhi persist_slot_missing
    beq persist_slot_next
    mov r0, r4
    bl resident
    cmp r0, #0
    moveq r0, r4
    popeq {r4-r8, pc}
persist_slot_next:
    add r4, r4, #1
    ldr r0, =LAST_USER
    cmp r4, r0
    bls persist_slot_scan
persist_slot_missing:
    mvn r0, #0
    pop {r4-r8, pc}
persist_slot_native:
    pop {r4-r8, lr}
    b 0xC004EF94

; r0 capture row. Returns 1 if an owner traverses a mapping this row initializes, 2 for an invalid indexed mapping.
persist_mapping_owner:
    push {r4-r8, lr}
    mov r4, r0
    mov r8, r1
    mov r5, #0
    ldr r6, =HDR + 16
    ldr r7, =SAMPLE_COUNT
persist_owner_slot:
    cmp r8, #0
    beq persist_owner_live
    cmp r5, #500
    blo persist_owner_live
    ldr r0, =LAST_USER
    cmp r5, r0
    bhi persist_owner_live
    ldr r0, [r6, r5, lsl #2]
    cmp r0, #0
    bne persist_owner_path
persist_owner_live:
    mov r0, r5
    bl resident
    cmp r0, #0
    beq persist_owner_next
persist_owner_path:
    ldr r0, =NAMES
    add r0, r0, r5, lsl #5
    ldrh r0, [r0, #30]
    subs r0, r0, #50
    bmi persist_owner_invalid
    cmp r0, r7
    bhs persist_owner_invalid
    cmp r0, r4
    beq persist_owner_yes
    ldr r1, =MAP_A
    add r1, r1, r0, lsl #5
    ldrh r0, [r1, #16]
    cmp r0, r7
    bhs persist_owner_invalid
    cmp r0, r4
    beq persist_owner_yes
    ldr r1, =MAP_B
    add r1, r1, r0, lsl #4
    ldrh r0, [r1, #8]
    cmp r0, r7
    bhs persist_owner_invalid
    cmp r0, r4
    beq persist_owner_yes
    ldr r1, =MAP_C
    add r1, r1, r0, lsl #3
    ldrh r0, [r1, #2]
    cmp r0, r7
    bhs persist_owner_invalid
    cmp r0, r4
    beq persist_owner_yes
persist_owner_next:
    add r5, r5, #1
    cmp r5, r7
    blo persist_owner_slot
    mov r0, #0
    pop {r4-r8, pc}
persist_owner_yes:
    mov r0, #1
    pop {r4-r8, pc}
persist_owner_invalid:
    mov r0, #2
    pop {r4-r8, pc}
.pool
"""
