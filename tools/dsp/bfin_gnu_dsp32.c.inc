/* SPDX-License-Identifier: GPL-3.0-or-later */
/* dsp32alu, dsp32shift and dsp32shiftimm with the GNU simulator's semantics
 * (gdb 15.2 sim/bfin), run on the QEMU CPU state.  build_qemu.py copies the
 * GNU decoders and their helpers into bfin-gnu-dsp32-gen.c.inc; the macros
 * below map GNU's register accessors onto CPUBfinState.  Legality is decided
 * at translation time by the GNU probe, so the decoders never see an
 * illegal encoding here.
 */

typedef uint8_t bu8;
typedef uint16_t bu16;
typedef uint32_t bu32;
typedef uint64_t bu40;
typedef uint64_t bu64;
typedef int8_t bs8;
typedef int16_t bs16;
typedef int32_t bs32;
typedef int64_t bs40;
typedef int64_t bs64;

/* GNU keeps the accumulators as A.X and A.W words and defers the writes of
   one instruction (STORE) to its end. */
typedef struct gnu_dsp32 {
    CPUBfinState *env;
    bu32 ax[2], aw[2];
    bu32 dis_algn_expt;
    bu32 v_internal;
    int n_stores;
    struct {
        bu32 *addr;
        bu32 val;
    } stores[20];
} SIM_CPU;

enum {
    GNU_ASTAT_az = ASTAT_AZ, GNU_ASTAT_an = ASTAT_AN,
    GNU_ASTAT_ac0_copy = ASTAT_AC0_COPY, GNU_ASTAT_v_copy = ASTAT_V_COPY,
    GNU_ASTAT_cc = ASTAT_CC, GNU_ASTAT_aq = ASTAT_AQ,
    GNU_ASTAT_rnd_mod = ASTAT_RND_MOD, GNU_ASTAT_ac0 = ASTAT_AC0,
    GNU_ASTAT_ac1 = ASTAT_AC1, GNU_ASTAT_av0 = ASTAT_AV0,
    GNU_ASTAT_av0s = ASTAT_AV0S, GNU_ASTAT_av1 = ASTAT_AV1,
    GNU_ASTAT_av1s = ASTAT_AV1S, GNU_ASTAT_v = ASTAT_V, GNU_ASTAT_vs = ASTAT_VS,
    GNU_ASTAT_v_internal = 32,
};
static const int GNU_ASTAT_av[2] = { ASTAT_AV0, ASTAT_AV1 };
static const int GNU_ASTAT_avs[2] = { ASTAT_AV0S, ASTAT_AV1S };

/* v_internal is GNU scratch state outside ASTAT. */
static inline bu32 *gnu_astat(SIM_CPU *cpu, int bit)
{
    return bit == GNU_ASTAT_v_internal ? &cpu->v_internal : &cpu->env->astat[bit];
}

#undef ATTRIBUTE_UNUSED
#define ATTRIBUTE_UNUSED G_GNUC_UNUSED
#define TRACE_INSN(...) do { } while (0)
#define TRACE_DECODE(...) do { } while (0)
#define TRACE_EXTRACT(...) do { } while (0)
#define PROFILE_COUNT_INSN(...) do { } while (0)
#define SIGNEXTEND(v, n) (((bs32)((bu32)(v) << (32 - (n)))) >> (32 - (n)))
#define REG_H_L(h, l) (((h) & 0xffff0000) | ((l) & 0x0000ffff))
#undef CLAMP
#define CLAMP(a, b, c) MIN(MAX(a, b), c)
#define min(a, b) MIN(a, b)
#define max(a, b) MAX(a, b)

#define DREG(x) (cpu->env->dreg[x])
#define PREG(x) (cpu->env->preg[x])
#define IREG(x) (cpu->env->ireg[x])
#define AXREG(x) (cpu->ax[x])
#define AWREG(x) (cpu->aw[x])
#define DIS_ALGN_EXPT (cpu->dis_algn_expt)
#define PARALLEL_GROUP BFIN_PARALLEL_NONE
#define BFIN_PARALLEL_NONE 0
#define ASTATREG(field) (*gnu_astat(cpu, GNU_ASTAT_##field))
#define CCREG ASTATREG(cc)
#define ASTAT bfin_astat_read(cpu->env)
#define SET_ASTAT(a) bfin_astat_write(cpu->env, a)

#define SET_DREG(x, val) (DREG(x) = (val))
#define SET_DREG_L_H(x, l, h) SET_DREG(x, REG_H_L(h, l))
#define SET_DREG_L(x, l) SET_DREG(x, REG_H_L(DREG(x), l))
#define SET_DREG_H(x, h) SET_DREG(x, REG_H_L(h, DREG(x)))
#define SET_AXREG(x, val) (AXREG(x) = (val))
#define SET_AWREG(x, val) (AWREG(x) = (val))
#define SET_AREG(x, val) \
    do { \
        bu40 __a = (val); \
        SET_AXREG(x, (__a >> 32) & 0xff); \
        SET_AWREG(x, __a); \
    } while (0)
#define SET_AREG32(x, val) \
    do { \
        SET_AWREG(x, val); \
        SET_AXREG(x, -(AWREG(x) >> 31)); \
    } while (0)
#define SET_ASTATREG(field, val) \
    do { \
        int __v = !!(val); \
        ASTATREG(field) = __v; \
        if (&ASTATREG(field) == &ASTATREG(ac0)) { \
            ASTATREG(ac0_copy) = __v; \
        } else if (&ASTATREG(field) == &ASTATREG(v)) { \
            ASTATREG(v_copy) = __v; \
        } \
    } while (0)
#define SET_CCREG(val) SET_ASTATREG(cc, val)
#define STORE(X, Y) \
    do { \
        cpu->stores[cpu->n_stores].addr = &(X); \
        cpu->stores[cpu->n_stores].val = (Y); \
        cpu->n_stores++; \
    } while (0)

static G_NORETURN void gnu_dsp32_illegal(void)
{
    /* The translator's GNU probe rejects these encodings. */
    g_assert_not_reached();
}
#define illegal_instruction(cpu) gnu_dsp32_illegal()
#define illegal_instruction_combination(cpu) gnu_dsp32_illegal()
#define unhandled_instruction(cpu, insn) gnu_dsp32_illegal()

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-variable"
#include "bfin-gnu-dsp32-gen.c.inc"
#pragma GCC diagnostic pop

static void gnu_dsp32(CPUBfinState *env, uint32_t insn)
{
    SIM_CPU c, *cpu = &c;
    bu16 iw0 = insn >> 16, iw1 = insn;
    int i;

    c.env = env;
    c.n_stores = 0;
    c.dis_algn_expt = 0;
    for (i = 0; i < 2; i++) {
        c.ax[i] = (env->areg[i] >> 32) & 0xff;
        c.aw[i] = env->areg[i];
    }
    if ((iw0 & 0xF7C0) == 0xC400) {
        decode_dsp32alu_0(cpu, iw0, iw1);
    } else if ((iw0 & 0xF7E0) == 0xC680) {
        decode_dsp32shiftimm_0(cpu, iw0, iw1);
    } else {
        decode_dsp32shift_0(cpu, iw0, iw1);
    }
    for (i = 0; i < c.n_stores; i++) {
        *c.stores[i].addr = c.stores[i].val;
    }
    for (i = 0; i < 2; i++) {
        uint64_t acc = ((uint64_t)(c.ax[i] & 0xff) << 32) | c.aw[i];
        env->areg[i] = (uint64_t)((int64_t)(acc << 24) >> 24);
    }
}
