/* SPDX-License-Identifier: AGPL-3.0-or-later */
ENTRY(doom_boot)
SECTIONS {
    . = 0xC017CC00;
    .text : { KEEP(*(.text.entry)) *(.text*) *(.rodata*) }
    .data : { *(.data*) }
    .ARM.exidx : { *(.ARM.exidx*) }
    ASSERT(. <= 0xC017DC00, "Doom bootstrap exceeds code arena")
    . = 0xC017DC00;
    __bss_start = .;
    .bss (NOLOAD) : { *(.bss*) *(COMMON) }
    __bss_end = .;
    ASSERT(. <= 0xC017F000, "Doom bootstrap exceeds state arena")
    /DISCARD/ : { *(.comment) *(.note*) }
}
