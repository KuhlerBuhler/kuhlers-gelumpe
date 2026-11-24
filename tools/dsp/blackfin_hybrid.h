/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * Interface between the QEMU worker board (tools/dsp/qemu/bfin_worker.c) and
 * the GNU simulator library (tools/dsp/blackfin_hybrid.c.inc). QEMU executes
 * the Blackfin instructions; the GNU simulator keeps the devices, the CEC,
 * the event queue and the worker protocol, and owns the CPU state between
 * runs.
 */
#ifndef BLACKFIN_HYBRID_H
#define BLACKFIN_HYBRID_H

#include <stdint.h>

#define BLECH_HYBRID_ABI 1

/* Why a run returned. */
enum {
  BLECH_STOP_TIME = 1,  /* cycle budget spent */
  BLECH_STOP_GUARD,     /* insn budget spent or stop address reached */
  BLECH_STOP_ROM,       /* fetch from the on-chip ROM */
  BLECH_STOP_GNU        /* the next insn needs the GNU simulator */
};

/* R0-R7 P0-P7 I0-I3 M0-M3 B0-B3 L0-L3 A0.X A0.W A1.X A1.W ASTAT RETS
   LC0 LT0 LB0 LC1 LT1 LB1 PC */
#define BLECH_SYNC_WORDS 45

struct blech_qemu_run {
  int32_t cycles;   /* in: cycles to run; out: left, negative when the last
                       insn needs more cycles than were left */
  uint32_t insns;   /* in: insn budget; out: left */
  uint32_t stop;    /* stop before the insn at this address, -1 for none */
  uint32_t last;    /* in/out: address of the last issued insn */
  int reason;       /* out: BLECH_STOP_* */
};

struct blech_qemu_ops {
  int abi;
  void (*map) (uint32_t address, uint32_t length, void *host);
  void (*get) (uint32_t *regs);
  void (*set) (const uint32_t *regs);
  void (*run) (struct blech_qemu_run *run);
  void (*written) (uint32_t address, uint32_t length);
  void (*watch) (uint32_t begin, uint64_t end);
};

typedef int (*blech_hybrid_main_fn) (const struct blech_qemu_ops *, int, char **);

#endif
