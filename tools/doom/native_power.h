/* SPDX-License-Identifier: AGPL-3.0-or-later */
#ifndef GELUMPE_DOOM_NATIVE_POWER_H
#define GELUMPE_DOOM_NATIVE_POWER_H

#include <stdint.h>

/* The panel reports the power key after a 2 s hold. Doom switches off only when the key (GPIO 7.15, low while held) stays
   down 5 s more, as the start does (tools/patch/script_hooks.s); let go earlier, the game goes on. A tick count that stands
   still ends the wait after a fixed number of reads, so the key always switches off in the end. */
static inline int doom_power_held(void)
{
    const uint32_t start = *(volatile uint32_t *)0xC06A2930u;
    for (uint32_t reads = 0; (uint32_t)(*(volatile uint32_t *)0xC06A2930u - start) < 5000u && reads < 20000000u; ++reads)
        if (*(volatile uint32_t *)0x01E26098u & 0x80000000u) return 0;
    return 1;
}

static inline int doom_power_message(const unsigned char message[5])
{
    if (message[0] != 6) return 0;
    if (message[1] == 1 && doom_power_held()) {
        ((void (*)(void *, int))0xC001734Cu)((void *)0x01E26000u, 1);
        for (;;) __asm__ volatile ("nop");
    }
    return 1;
}
static inline void doom_power_poll_initializing(void)
{
    unsigned char message[5];
    for (unsigned int i = 0; i < 32; ++i) {
        if (!((int (*)(void *, void *))0xC0024B6Cu)((void *)0xC033E57Cu, message)) return;
        doom_power_message(message);
    }
}
__attribute__((noreturn)) static inline void doom_power_idle(void)
{
    for (;;) doom_power_poll_initializing();
}
#endif
