/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "sim-signal.h"

void blech_bfin_guard (bu32, bu32);
bu32 blech_bfin_count (void);
bu32 blech_bfin_last (void);
int blech_bfin_stopped (void);

static struct {
  bu32 left, total, target, last;
  int active, stopped;
} blech_guard = { 0, 0, 0, (bu32)-1, 0, 0 };

void
blech_bfin_guard (bu32 budget, bu32 target)
{
  blech_guard.left = blech_guard.total = budget;
  blech_guard.target = target;
  blech_guard.active = 1;
  blech_guard.stopped = 0;
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
