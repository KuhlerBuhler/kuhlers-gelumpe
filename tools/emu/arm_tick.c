/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Per-instruction device clock for the ARM/DSP coupled machine (machine.py, _dsp_arm_tick).
   A Unicorn code hook in C: the same arithmetic as the Python hook, in doubles like Python floats,
   without a Python call per instruction. */
#include <stdint.h>

struct arm_tick {
    double time_ns;       /* device time; machine.py keeps whether it holds an int */
    double fraction;      /* the part of a ns carried to the next instruction */
    double ns_per_insn;   /* the rate of the current slice */
    uint64_t count;       /* instructions since machine.py last cleared it */
};

void blech_arm_tick(void *uc, uint64_t address, uint32_t size, void *user)
{
    struct arm_tick *tick = user;
    double elapsed = tick->fraction + tick->ns_per_insn;
    double whole = (double)(int64_t)elapsed;
    (void)uc; (void)address; (void)size;
    tick->time_ns += whole;
    tick->fraction = elapsed - whole;
    tick->count++;
}
