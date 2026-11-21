/* SPDX-License-Identifier: GPL-3.0-or-later */
/* blackfin_worker.c inside the QEMU worker: built with -Dmain=blech_worker_main,
   -Dsim_open=blech_hybrid_sim_open, -Dsim_write=blech_hybrid_sim_write and
   -Dblech_bfin_memory_window=blech_hybrid_memory_window. */
#include <stdint.h>
#include <stdio.h>
#include "bfd.h"
#include "sim/sim.h"
#include "sim/callback.h"
#include "blackfin_hybrid.h"

extern int blech_worker_main (int, char **);
extern int blech_bfin_memory_window (uint32_t, uint32_t);
extern void blech_hybrid_attach (SIM_DESC, const struct blech_qemu_ops *);

int blech_hybrid_main (const struct blech_qemu_ops *, int, char **);
SIM_DESC blech_hybrid_sim_open (SIM_OPEN_KIND, host_callback *, struct bfd *, char * const *);
uint64_t blech_hybrid_sim_write (SIM_DESC, uint64_t, const void *, uint64_t);
int blech_hybrid_memory_window (uint32_t, uint32_t);

static const struct blech_qemu_ops *ops;

SIM_DESC
blech_hybrid_sim_open (SIM_OPEN_KIND kind, host_callback *callback, struct bfd *abfd,
                       char * const *argv)
{
  SIM_DESC sd = sim_open (kind, callback, abfd, argv);
  if (sd)
    blech_hybrid_attach (sd, ops);
  return sd;
}

uint64_t
blech_hybrid_sim_write (SIM_DESC sd, uint64_t address, const void *data, uint64_t length)
{
  uint64_t n = sim_write (sd, address, data, length);
  if (n && address < 0x100000000ULL)
    ops->written (address, n);
  return n;
}

int
blech_hybrid_memory_window (uint32_t address, uint32_t length)
{
  if (!blech_bfin_memory_window (address, length))
    return 0;
  ops->watch (address, (uint64_t) address + length);
  return 1;
}

int
blech_hybrid_main (const struct blech_qemu_ops *qemu, int argc, char **argv)
{
  if (qemu->abi != BLECH_HYBRID_ABI)
    {
      fprintf (stderr, "blackfin hybrid: ABI %d, expected %d\n", qemu->abi, BLECH_HYBRID_ABI);
      return 2;
    }
  ops = qemu;
  return blech_worker_main (argc, argv);
}
