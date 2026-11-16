/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "blackfin_hybrid.h"

void blech_hybrid_attach (SIM_DESC, const struct blech_qemu_ops *);
bool blech_hybrid_cec (int, uint32_t, uint32_t *);
bool blech_cec_fast (SIM_CPU *, int, bu32, bu32 *);

static const struct blech_qemu_ops *blech_qemu;
static bool blech_hybrid_gnu_next;
static SIM_CPU *blech_hybrid_cpu;
static uint64_t blech_hybrid_stats[4]; /* QEMU runs, QEMU cycles, GNU steps, delegations */

/* BLECH_HYBRID_STATS=PREFIX writes PREFIX.<pid> on every run request; the
   worker is terminated, not exited, so atexit would never run.  */
static void
blech_hybrid_report (void)
{
  const char *prefix = getenv ("BLECH_HYBRID_STATS");
  char path[512];
  FILE *file;

  if (!prefix)
    return;
  snprintf (path, sizeof path, "%s.%ld", prefix, (long) getpid ());
  file = fopen (path, "w");
  if (!file)
    return;
  fprintf (file, "%llu QEMU runs, %llu QEMU cycles, %llu GNU steps, %llu delegations\n",
           (unsigned long long) blech_hybrid_stats[0], (unsigned long long) blech_hybrid_stats[1],
           (unsigned long long) blech_hybrid_stats[2], (unsigned long long) blech_hybrid_stats[3]);
  fclose (file);
}

void
blech_hybrid_attach (SIM_DESC sd, const struct blech_qemu_ops *ops)
{
  sim_core_mapping *first = STATE_CORE (sd)->common.map[read_map].first;
  sim_core_mapping *map, *earlier;

  blech_qemu = ops;
  blech_hybrid_cpu = STATE_CPU (sd, 0);
  for (map = first; map; map = map->next)
    {
      /* The GNU core uses the first mapping that holds an address.  */
      for (earlier = first; earlier != map; earlier = earlier->next)
        if (earlier->base <= map->bound && map->base <= earlier->bound)
          break;
      if (earlier == map && map->buffer && !map->device
          && (map->mask & 0xFFFFFFFF) == 0xFFFFFFFF && map->base < 0xFFC00000
          && (map->bound < 0xEF000000 || map->base >= 0xF0000000))
        ops->map (map->base, map->nr_bytes, map->buffer);
    }
}

/* CLI and STI from QEMU, see blech_cec_fast in dv-bfin_cec.c.  */
bool
blech_hybrid_cec (int op, uint32_t value, uint32_t *result)
{
  return blech_cec_fast (blech_hybrid_cpu, op, value, result);
}

static void
blech_hybrid_put (SIM_CPU *cpu)
{
  bu32 r[BLECH_SYNC_WORDS];
  int i;

  for (i = 0; i < 16; ++i)
    r[i] = BFIN_CPU_STATE.dpregs[i];
  for (i = 0; i < 4; ++i)
    {
      r[16 + i] = IREG (i);
      r[20 + i] = MREG (i);
      r[24 + i] = BREG (i);
      r[28 + i] = LREG (i);
    }
  for (i = 0; i < 2; ++i)
    {
      r[32 + 2 * i] = AXREG (i) & 0xff;
      r[33 + 2 * i] = AWREG (i);
      r[38 + 3 * i] = LCREG (i);
      r[39 + 3 * i] = LTREG (i);
      r[40 + 3 * i] = LBREG (i);
    }
  r[36] = ASTAT;
  r[37] = RETSREG;
  r[44] = PCREG;
  blech_qemu->set (r);
}

static void
blech_hybrid_take (SIM_CPU *cpu)
{
  bu32 r[BLECH_SYNC_WORDS];
  int i;

  blech_qemu->get (r);
  for (i = 0; i < 16; ++i)
    BFIN_CPU_STATE.dpregs[i] = r[i];
  for (i = 0; i < 4; ++i)
    {
      IREG (i) = r[16 + i];
      MREG (i) = r[20 + i];
      BREG (i) = r[24 + i];
      LREG (i) = r[28 + i];
    }
  for (i = 0; i < 2; ++i)
    {
      /* GNU keeps A.X either as 8 bits or sign-extended; keep its form
         unless the value changed.  */
      if ((AXREG (i) & 0xff) != (r[32 + 2 * i] & 0xff))
        AXREG (i) = r[32 + 2 * i] & 0xff;
      AWREG (i) = r[33 + 2 * i];
      LCREG (i) = r[38 + 3 * i];
      LTREG (i) = r[39 + 3 * i];
      LBREG (i) = r[40 + 3 * i];
    }
  SET_ASTAT (r[36]);
  RETSREG = r[37];
  PCREG = r[44];
}

/* blech_bfin_engine with the instructions run by QEMU between two events.
   A run never crosses an event, so devices, interrupts and time stay with
   the GNU simulator and match its per-cycle loop.  */
static void
blech_hybrid_engine (SIM_DESC sd, SIM_CPU *cpu)
{
  sim_events *events = STATE_EVENTS (sd);

  if (!blech_qemu)
    {
      blech_bfin_engine (sd, cpu);
      return;
    }
  blech_hybrid_report ();
  /* A request ending at a guard stop leaves the flag set; QEMU stops at the
     guard target by itself, so a new request starts in QEMU.  */
  blech_hybrid_gnu_next = false;
  while (1)
    {
      if (!blech_clock.left)
        {
          blech_guard.active = 0;
          blech_guard.stopped = 1;
          sim_engine_halt (sd, cpu, cpu, PCREG, sim_stopped, SIM_SIGTRAP);
        }
      if (!blech_clock.remaining && blech_clock.idle)
        {
          int64_t next = events->work_pending ? 1 : events->time_from_event + 1;
          bu32 n = next < blech_clock.left ? next : blech_clock.left;
          blech_clock.cycles += n;
          blech_clock.left -= n;
          if (n == next)
            {
              if (n > 1)
                sim_events_tickn (sd, n - 1);
              if (sim_events_tick (sd))
                sim_events_process (sd);
            }
          else
            sim_events_tickn (sd, n);
          continue;
        }
      if (!blech_clock.remaining)
        {
          if (!blech_hybrid_gnu_next && blech_guard.active
              && !(STATE_ENVIRONMENT (sd) == OPERATING_ENVIRONMENT
                   && (SYSCFGREG & SYSCFG_SSSTEP)))
            {
              int64_t next = events->work_pending ? 1 : events->time_from_event + 1;
              int64_t budget = next < blech_clock.left ? next : blech_clock.left;
              struct blech_qemu_run run;
              bu32 used;

              if (budget > INT32_MAX)
                budget = INT32_MAX;
              run.cycles = budget;
              run.insns = blech_guard.left;
              run.stop = blech_guard.target;
              run.last = blech_guard.last;
              run.reason = 0;
              blech_hybrid_put (cpu);
              blech_qemu->run (&run);
              blech_hybrid_take (cpu);
              blech_guard.left = run.insns;
              blech_guard.last = run.last;
              blech_hybrid_gnu_next = run.reason != BLECH_STOP_TIME;
              blech_hybrid_stats[3] += run.reason == BLECH_STOP_GNU;
              used = run.cycles > 0 ? budget - run.cycles : budget;
              if (used)
                {
                  ++blech_hybrid_stats[0];
                  blech_hybrid_stats[1] += used;
                  cycles_inc (cpu, used);
                  blech_clock.cycles += used;
                  blech_clock.left -= used;
                  blech_clock.remaining = run.cycles < 0 ? -run.cycles : 0;
                  if (used == next)
                    {
                      if (used > 1)
                        sim_events_tickn (sd, used - 1);
                      if (sim_events_tick (sd))
                        sim_events_process (sd);
                    }
                  else
                    sim_events_tickn (sd, used);
                  continue;
                }
            }
          blech_bfin_check (sd, cpu);
          step_once (cpu);
          ++blech_hybrid_stats[2];
          blech_clock.remaining = CYCLE_DELAY;
          blech_hybrid_gnu_next = false;
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
