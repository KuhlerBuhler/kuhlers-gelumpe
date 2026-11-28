# SPDX-License-Identifier: GPL-2.0-only
"""Free sample memory on the sampling window's Memory line, one count for the swap and the display.

Korg's line ("Memory", German "Speicher") estimates the seconds still free: 0xC007DE80 takes Korg's free count
0xC004E218 (DSP end minus the DSP cursor), halves it, divides by 48000 and halves again in stereo. It now shows the free
sample memory in MB with one decimal, rounded down, for example "12.3 [MB]" (docs/hintergrund/sample-speicher.md).

`ss_free` is the one count behind it:
- swap off: Korg's own free count 0xC004E218.
- swap on: the user bank the swap places into (from DSP_MIN + DSP_GUARD, ss_cap long, the budget of `first_fit`)
  minus the active samples in it. The gaps the swap's evictions leave below the cursor count as free, which Korg's
  count misses, because Korg's delete lowers the cursor only for the last sample.

A recording still starts at Korg's cursor. Korg's own checks (the sampling entry 0xC006F71C, the loader 0xC0036234) and
the swap's reservation keep the native count.
"""

FREE_NATIVE = 0xC004E218        # Korg's free count: DSP end minus cursor, 0 when 4 or less
SECONDS = 0xC007DE80            # Korg's seconds estimate, called only by the Memory line
FORMAT = 0xC0090BA0             # (string, value, width, zero pad): the number as text
SPRINTF = 0xC000A588
STRING_FROM = 0xC00A324C        # (string, C string, allocator): constructs a string
APPEND = 0xC00A2B70             # (string, C string): appends

# (site, the bl's target, stub, note); the sites are the Memory line, case 3 of the sampling window's text switch.
HOOKS = (
    (0xC008C698, SECONDS, 'ss_mem_value', "the sampling window's Memory line counts the free sample memory, the swap's gaps included"),
    (0xC008C6AC, FORMAT, 'ss_mem_text', 'the Memory line shows MB with one decimal instead of seconds'),
    (0xC008C6C4, APPEND, 'ss_mem_unit', "the Memory line's unit is MB in every language"),
)

# Native code the stubs call, compared byte for byte in both red builds.
CALLED = (
    (FREE_NATIVE, 0x24, "Korg's free sample memory count"),
    (SPRINTF, 0x40, 'sprintf'),
    (STRING_FROM, 0x20, 'string from a C string'),
    (APPEND, 0x20, 'string append'),
)
CALLED_SHA = {
    FREE_NATIVE: 'f22538da7eef86fb3bbbc3594c5e45bb2183641208cde66f11fac73759b127c2',
    SPRINTF: 'ff89f6b92c4b340f2ee9683f8478c0df5b22866acf0f6402b4527ac8af0468a7',
    STRING_FROM: 'ee26d0dd5fb175e15aa48eb366cdb3ce1715b05c20a33d61ec1ddeab18df0777',
    APPEND: '8dbfc39e80c1c2d1bd5939c060b1c4a7b6e57da308d9299d7798afe503c84c6d',
}


def source():
    return SOURCE.replace('FREE_NATIVE', f'{FREE_NATIVE:#x}').replace('SPRINTF', f'{SPRINTF:#x}') \
        .replace('STRING_FROM', f'{STRING_FROM:#x}').replace('APPEND', f'{APPEND:#x}')


SOURCE = r'''
; r0 = free sample memory in bytes: Korg's count while the swap is off, else the swap's budget minus its active samples.
ss_free:
    ldr r0, =ST
    ldr r0, [r0, #MODE]
    cmp r0, #1
    bne FREE_NATIVE
    push {r4-r8, lr}
    ldr r4, =DSP_MIN + DSP_GUARD
    ldr r5, =ss_cap
    ldr r5, [r5]
    ldr r0, =CAP_DEFAULT
    cmp r5, r0
    movhi r5, r0
    add r5, r5, r4
    sub r6, r5, r4
    ldr r7, =META
    mov r8, #0
sf_scan:
    ldrb r0, [r7, #11]
    cmp r0, #1
    bne sf_next
    ldr r0, [r7]
    ldr r1, [r7, #4]
    add r1, r0, r1
    cmp r0, r4
    movlo r0, r4
    cmp r1, r5
    movhi r1, r5
    cmp r1, r0
    subhi r1, r1, r0
    subhi r6, r6, r1
sf_next:
    ldr r0, =0x45C
    add r7, r7, r0
    add r8, r8, #1
    ldr r0, =SAMPLE_COUNT
    cmp r8, r0
    blo sf_scan
    mov r0, r6
    pop {r4-r8, pc}

; The Memory line's value: r0 = the sampling manager, unused.
ss_mem_value:
    b ss_free

; r0 = the string to construct, r1 = free bytes: "12.3", MB (2^20 bytes) with one decimal, rounded down.
ss_mem_text:
    push {r4, lr}
    sub sp, sp, #24
    mov r4, r0
    add r1, r1, r1, lsl #2
    lsr r3, r1, #19
    mov r2, #0
smt_div:
    cmp r3, #10
    subhs r3, r3, #10
    addhs r2, r2, #1
    bhs smt_div
    mov r0, sp
    ldr r1, =smt_format
    bl SPRINTF
    mov r0, r4
    mov r1, sp
    add r2, sp, #20
    bl STRING_FROM
    mov r0, r4
    add sp, sp, #24
    pop {r4, pc}

; r0 = the line's string, r1 = Korg's unit (" [secs]" or lang-de's " [Sek]"): " [MB]" instead.
ss_mem_unit:
    ldr r1, =smt_unit
    b APPEND

smt_format:
    .asciz "%u.%u"
smt_unit:
    .asciz " [MB]"
.align 2
.pool
'''
