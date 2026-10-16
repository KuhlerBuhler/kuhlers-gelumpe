/* SPDX-License-Identifier: AGPL-3.0-or-later */
#ifndef GELUMPE_DOOM_NATIVE_POWER_H
#define GELUMPE_DOOM_NATIVE_POWER_H

static inline int doom_power_message(const unsigned char message[5])
{
    if (message[0] != 6) return 0;
    if (message[1] == 1) {
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
