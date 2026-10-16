/* SPDX-License-Identifier: AGPL-3.0-or-later */
ENTRY(doom_runtime_start)
SECTIONS {
    . = 0xC1000000;
    .text : { KEEP(*(.text.entry)) *(.text*) *(.rodata*) }
    .data : { *(.data*) }
    .ARM.exidx : { *(.ARM.exidx*) }
    __file_end = .;
    . = ALIGN(16);
    __bss_start = .;
    .bss (NOLOAD) : { *(.bss*) *(COMMON) }
    . = ALIGN(16);
    __bss_end = .;
    __heap_start = .;
    __heap_limit = 0xC17F0000;
    __stack_bottom = __heap_limit;
    __stack_top = 0xC1800000;
    ASSERT(__heap_start + 6M + 256K <= __heap_limit, "Doom zone and working heap exceed RAM arena")
    ASSERT(doom_runtime_start == 0xC1000000, "Entry must be first instruction")
    /DISCARD/ : { *(.comment) *(.note*) }
}
