/* SPDX-License-Identifier: AGPL-3.0-or-later */
ENTRY(probe_start)
SECTIONS {
    . = 0x01000000;
    .text : { *(.text*) *(.rodata*) }
    .data : { *(.data*) }
    .bss (NOLOAD) : { *(.bss*) *(COMMON) }
    . = ALIGN(16);
    __heap_start = .;
    __heap_limit = . + 32M;
    /DISCARD/ : { *(.comment) *(.note*) }
}
