/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Per-instruction device clock for the ARM/DSP coupled machine (machine.py, _dsp_arm_tick).
   A Unicorn code hook in C: the same arithmetic as the Python hook, in doubles like Python floats,
   without a Python call per instruction. It also ends a slice after `budget` instructions, the way
   emu_start's count does (that count costs a second per-instruction hook in Unicorn, about 25 times
   the run time of this one). blech_arm_ahead gives the clock of a poll loop ahead (Machine._poll_ahead). */
#include <stdint.h>

struct arm_tick {
    double time_ns;       /* device time; machine.py keeps whether it holds an int */
    double fraction;      /* the part of a ns carried to the next instruction */
    double ns_per_insn;   /* the rate of the current slice */
    uint64_t count;       /* instructions since machine.py last cleared it */
    uint64_t budget;      /* stop in front of the instruction after this many; ~0: no limit */
    int (*stop)(void *);  /* uc_emu_stop */
};

void blech_arm_tick(void *uc, uint64_t address, uint32_t size, void *user)
{
    struct arm_tick *tick = user;
    if (tick->count >= tick->budget) {
        tick->stop(uc);   /* as Unicorn's own count: this instruction does not run and is not counted */
        return;
    }
    double elapsed = tick->fraction + tick->ns_per_insn;
    double whole = (double)(int64_t)elapsed;
    (void)size;
    tick->time_ns += whole;
    tick->fraction = elapsed - whole;
    tick->count++;
}

/* The clock at the next `n` reads of a loop from the state in `tick`, which is left as it is: read i (from 1)
   comes gaps[(i-1) % m] instructions after the one before. For each read the time and fraction (times[i-1],
   fractions[i-1]) and the DSP cycles the ARM time then stands for, as the step from the read before
   (steps[i-1]; the first from `cycles`). The cycles are BlackfinPort.advance_to's:
   (int(time) - origin) * hz // 1e9. */
void blech_arm_ahead(const struct arm_tick *tick, const uint32_t *gaps, uint32_t m, uint32_t n, int64_t origin_ns,
                     int64_t hz, int64_t cycles, uint32_t *steps, double *times, double *fractions)
{
    double time = tick->time_ns, fraction = tick->fraction;
    for (uint32_t i = 0; i < n; ++i) {
        for (uint32_t j = 0; j < gaps[i % m]; ++j) {
            double elapsed = fraction + tick->ns_per_insn;
            double whole = (double)(int64_t)elapsed;
            time += whole;
            fraction = elapsed - whole;
        }
        __int128 span = (__int128)((int64_t)time - origin_ns) * hz;
        int64_t target = (int64_t)(span / 1000000000);
        steps[i] = target > cycles ? (uint32_t)(target - cycles) : 0;
        if (target > cycles) cycles = target;
        times[i] = time;
        fractions[i] = fraction;
    }
}
