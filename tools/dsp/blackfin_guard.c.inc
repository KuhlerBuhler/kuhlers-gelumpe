/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "sim-signal.h"

void blech_bfin_guard (bu32, bu32);
bu32 blech_bfin_count (void);
bu32 blech_bfin_last (void);
int blech_bfin_stopped (void);
void blech_bfin_time_guard (bu32);
bu64 blech_bfin_time (void);
bu32 blech_bfin_remaining (void);
int blech_bfin_sleeping (void);
void blech_bfin_idle (SIM_DESC);
void blech_bfin_wake (SIM_DESC);
void blech_bfin_wake_level (SIM_DESC, bool);
extern void cycles_inc (SIM_CPU *, bu32);

static struct {
  bu32 left, total, target, last;
  int active, stopped;
} blech_guard = { 0, 0, 0, (bu32)-1, 0, 0 };

static struct {
  bu64 cycles;
  bu32 remaining, left;
  bool idle, wake_level;
} blech_clock;

void
blech_bfin_guard (bu32 budget, bu32 target)
{
  blech_guard.left = blech_guard.total = budget;
  blech_guard.target = target;
  blech_guard.active = 1;
  blech_guard.stopped = 0;
  blech_clock.left = 40000000;
}

void blech_bfin_time_guard (bu32 cycles) {
  blech_bfin_guard (1000000, (bu32)-1);
  blech_clock.left = cycles;
}
bu64 blech_bfin_time (void) { return blech_clock.cycles; }
bu32 blech_bfin_remaining (void) { return blech_clock.remaining; }
int blech_bfin_sleeping (void) { return blech_clock.idle; }
void blech_bfin_idle (SIM_DESC sd) { blech_clock.idle = !blech_clock.wake_level; }
void blech_bfin_wake (SIM_DESC sd) { blech_clock.idle = false; }
void blech_bfin_wake_level (SIM_DESC sd, bool level) {
  blech_clock.wake_level = level;
  if (level) blech_bfin_wake (sd);
}

bu32 blech_bfin_count (void) { return blech_guard.total - blech_guard.left; }
bu32 blech_bfin_last (void) { return blech_guard.last; }
int blech_bfin_stopped (void) { return blech_guard.stopped; }

static void
blech_bfin_check (SIM_DESC sd, SIM_CPU *cpu)
{
  if (!blech_guard.active)
    return;
  if (!blech_guard.left || PCREG == blech_guard.target
      || (PCREG >= 0xEF000000 && PCREG < 0xF0000000))
    {
      blech_guard.active = 0;
      blech_guard.stopped = 1;
      sim_engine_halt (sd, cpu, cpu, PCREG, sim_stopped, SIM_SIGTRAP);
    }
  blech_guard.last = PCREG;
  --blech_guard.left;
}

static void
blech_bfin_engine (SIM_DESC sd, SIM_CPU *cpu)
{
  while (1)
    {
      if (!blech_clock.left)
        {
          blech_guard.active = 0;
          blech_guard.stopped = 1;
          sim_engine_halt (sd, cpu, cpu, PCREG, sim_stopped, SIM_SIGTRAP);
        }
      if (!blech_clock.remaining && !blech_clock.idle)
        {
          blech_bfin_check (sd, cpu);
          step_once (cpu);
          blech_clock.remaining = CYCLE_DELAY;
        }
      if (blech_clock.remaining)
        {
          --blech_clock.remaining;
          cycles_inc (cpu, 1);
        }
      ++blech_clock.cycles;
      --blech_clock.left;
      if (sim_events_tick (sd))
        sim_events_process (sd);
    }
}
