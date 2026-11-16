/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * Machine "bf-electribe": a bare Blackfin core for the BFIN9 worker. The GNU
 * simulator library (BLECH_HYBRID_LIB) runs the worker protocol and owns
 * devices, CEC and time; this board executes instructions for it.
 * Worker arguments arrive as BLECH_ARGC / BLECH_ARG1..n.
 */
#include "qemu/osdep.h"
#include <dlfcn.h>
#include "qemu/error-report.h"
#include "qemu/main-loop.h"
#include "qemu-main.h"
#include "hw/boards.h"
#include "hw/core/cpu.h"
#include "exec/address-spaces.h"
#include "exec/exec-all.h"
#include "exec/memory.h"
#include "cpu.h"
#include "blackfin_hybrid.h"

#define ROM_BEGIN 0xEF000000u
#define ROM_END 0xF0000000u

static BlackfinCPU *worker_cpu;
static struct {
    uint32_t base, length;
} worker_ram[16];
static int worker_rams;
static uint32_t watch_begin;
static uint64_t watch_end;

static bool worker_tlb_fill(CPUState *cs, vaddr address, int size,
                            MMUAccessType access_type, int mmu_idx,
                            bool probe, uintptr_t retaddr)
{
    uint32_t page = address & TARGET_PAGE_MASK;
    int i;

    for (i = 0; i < worker_rams; i++) {
        if (page - worker_ram[i].base < worker_ram[i].length) {
            int prot = PAGE_READ | PAGE_WRITE | PAGE_EXEC;
            /* Watched data stays with the GNU simulator, which records it. */
            if (page < watch_end && page + TARGET_PAGE_SIZE > watch_begin) {
                prot = PAGE_EXEC;
            }
            if (prot & (1 << access_type)) {
                tlb_set_page(cs, page, page, prot, mmu_idx, TARGET_PAGE_SIZE);
                return true;
            }
            break;
        }
    }
    if (probe) {
        return false;
    }
    cs->exception_index = access_type == MMU_INST_FETCH &&
                          address >= ROM_BEGIN && address < ROM_END
                          ? EXCP_BLECH_ROM : EXCP_BLECH_GNU;
    cpu_loop_exit_restore(cs, retaddr);
}

static void worker_map(uint32_t address, uint32_t length, void *host)
{
    MemoryRegion *region = g_new0(MemoryRegion, 1);
    char name[32];

    if (worker_rams == ARRAY_SIZE(worker_ram)) {
        error_report("bf-electribe: too many memory regions");
        exit(1);
    }
    snprintf(name, sizeof(name), "gnu-%08x", address);
    memory_region_init_ram_ptr(region, NULL, name, length, host);
    memory_region_add_subregion(get_system_memory(), address, region);
    worker_ram[worker_rams].base = address;
    worker_ram[worker_rams].length = length;
    worker_rams++;
    tlb_flush(CPU(worker_cpu));
}

static void worker_get(uint32_t *r)
{
    CPUArchState *env = &worker_cpu->env;
    int i;

    for (i = 0; i < 8; i++) {
        r[i] = env->dreg[i];
        r[8 + i] = env->preg[i];
    }
    for (i = 0; i < 4; i++) {
        r[16 + i] = env->ireg[i];
        r[20 + i] = env->mreg[i];
        r[24 + i] = env->breg[i];
        r[28 + i] = env->lreg[i];
    }
    for (i = 0; i < 2; i++) {
        r[32 + 2 * i] = (env->areg[i] >> 32) & 0xff;
        r[33 + 2 * i] = (uint32_t)env->areg[i];
    }
    r[36] = bfin_astat_read(env);
    r[37] = env->rets;
    for (i = 0; i < 2; i++) {
        r[38 + 3 * i] = env->lcreg[i];
        r[39 + 3 * i] = env->ltreg[i];
        r[40 + 3 * i] = env->lbreg[i];
    }
    r[44] = env->pc;
}

static void worker_set(const uint32_t *r)
{
    CPUArchState *env = &worker_cpu->env;
    int i;

    for (i = 0; i < 8; i++) {
        env->dreg[i] = r[i];
        env->preg[i] = r[8 + i];
    }
    for (i = 0; i < 4; i++) {
        env->ireg[i] = r[16 + i];
        env->mreg[i] = r[20 + i];
        env->breg[i] = r[24 + i];
        env->lreg[i] = r[28 + i];
    }
    for (i = 0; i < 2; i++) {
        uint64_t acc = ((uint64_t)(r[32 + 2 * i] & 0xff) << 32) | r[33 + 2 * i];
        env->areg[i] = (uint64_t)((int64_t)(acc << 24) >> 24);
    }
    bfin_astat_write(env, r[36]);
    env->astat_op = ASTAT_OP_NONE;
    env->rets = r[37];
    for (i = 0; i < 2; i++) {
        env->lcreg[i] = r[38 + 3 * i];
        env->ltreg[i] = r[39 + 3 * i];
        env->lbreg[i] = r[40 + 3 * i];
    }
    env->pc = r[44];
}

static void worker_invalidate(uint32_t address)
{
    if (address != (uint32_t)-1) {
        tb_invalidate_phys_range(address, address + 7);
    }
}

static void worker_run(struct blech_qemu_run *run)
{
    CPUState *cs = CPU(worker_cpu);
    CPUArchState *env = &worker_cpu->env;
    int ret;

    if (run->stop != bfin_blech_stop) {
        uint32_t old = bfin_blech_stop;
        bfin_blech_stop = run->stop;
        worker_invalidate(old);
        worker_invalidate(run->stop);
    }
    env->blech_cycles = run->cycles;
    env->blech_insns = run->insns;
    env->blech_last = run->last;
    current_cpu = cs;
    cs->halted = 0;
    for (;;) {
        bql_unlock();
        cpu_exec_start(cs);
        ret = cpu_exec(cs);
        cpu_exec_end(cs);
        bql_lock();
        if (ret >= EXCP_BLECH_TIME && ret <= EXCP_BLECH_GNU) {
            break;
        }
        /* tb_flush and other safe work queued by the TCG core */
        process_queued_cpu_work(cs);
        cs->halted = 0;
    }
    run->cycles = env->blech_cycles;
    run->insns = env->blech_insns;
    run->last = env->blech_last;
    run->reason = ret - EXCP_BLECH_TIME + BLECH_STOP_TIME;
}

static void worker_written(uint32_t address, uint32_t length)
{
    if (length) {
        tb_invalidate_phys_range(address, address + length - 1);
    }
}

static void worker_watch(uint32_t begin, uint64_t end)
{
    watch_begin = begin;
    watch_end = end;
    tlb_flush(CPU(worker_cpu));
}

static const struct blech_qemu_ops worker_ops = {
    .abi = BLECH_HYBRID_ABI,
    .map = worker_map,
    .get = worker_get,
    .set = worker_set,
    .run = worker_run,
    .written = worker_written,
    .watch = worker_watch,
};

static int worker_main(void)
{
    const char *path = getenv("BLECH_HYBRID_LIB");
    const char *count = getenv("BLECH_ARGC");
    int argc = count ? atoi(count) : 0, i;
    char **argv = g_new0(char *, argc + 2);
    blech_hybrid_main_fn entry;
    void *library;

    /* QEMU's handlers only request a shutdown from its main loop, which never
       runs here; the backend ends a worker with SIGTERM. */
    signal(SIGTERM, SIG_DFL);
    signal(SIGINT, SIG_DFL);
    signal(SIGHUP, SIG_DFL);
    argv[0] = (char *)"blackfin-worker";
    for (i = 1; i <= argc; i++) {
        char name[32];
        snprintf(name, sizeof(name), "BLECH_ARG%d", i);
        argv[i] = getenv(name) ? getenv(name) : (char *)"";
    }
    library = path ? dlopen(path, RTLD_NOW | RTLD_LOCAL) : NULL;
    entry = library ? (blech_hybrid_main_fn)dlsym(library, "blech_hybrid_main")
                    : NULL;
    bfin_blech_cec = library ? dlsym(library, "blech_hybrid_cec") : NULL;
    if (!entry || !bfin_blech_cec) {
        fprintf(stderr, "bf-electribe: cannot load BLECH_HYBRID_LIB: %s\n",
                path ? dlerror() : "unset");
        return 1;
    }
    return entry(&worker_ops, argc + 1, argv);
}

static void worker_init(MachineState *machine)
{
    worker_cpu = BFIN_CPU(cpu_create(machine->cpu_type));
    bfin_blech_tlb_fill = worker_tlb_fill;
    qemu_main = worker_main;
}

static void worker_machine_init(MachineClass *mc)
{
    mc->desc = "Electribe DSP core for the BFIN9 worker";
    mc->init = worker_init;
    mc->max_cpus = 1;
    mc->default_cpu_type = BLACKFIN_CPU_TYPE_NAME("bf537");
}
DEFINE_MACHINE("bf-electribe", worker_machine_init)
