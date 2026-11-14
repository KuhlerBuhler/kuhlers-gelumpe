/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <signal.h>
#include <unistd.h>
#include <string.h>
#include "bfd.h"
#include "sim/sim.h"
#include "sim/callback.h"

extern void blech_bfin_guard(uint32_t, uint32_t);
extern uint32_t blech_bfin_count(void);
extern uint32_t blech_bfin_last(void);
extern int blech_bfin_stopped(void);
extern int blech_bfin_hostdp_event(SIM_DESC, unsigned);

/* Little-endian requests: opcode, address/register/budget, byte count/value/PC. */
#define LIMIT (1024 * 1024)
static FILE *reply;

static int get32(uint32_t *value) {
    unsigned char b[4];
    if (fread(b, 1, 4, stdin) != 4) return 0;
    *value = b[0] | (uint32_t)b[1] << 8 | (uint32_t)b[2] << 16 | (uint32_t)b[3] << 24;
    return 1;
}

static void put32(uint32_t value) {
    unsigned char b[] = {value, value >> 8, value >> 16, value >> 24};
    fwrite(b, 1, 4, reply);
}

static void answer(uint32_t status, const void *data, uint32_t count) {
    put32(status);
    put32(count);
    if (count) fwrite(data, 1, count, reply);
    fflush(reply);
}

static int reg_get(SIM_DESC sd, unsigned reg, uint32_t *value) {
    unsigned char b[4];
    if (sim_fetch_register(sd, reg, b, 4) != 4) return 0;
    *value = b[0] | (uint32_t)b[1] << 8 | (uint32_t)b[2] << 16 | (uint32_t)b[3] << 24;
    return 1;
}

static int rom_snapshot(SIM_DESC sd, uint32_t steps, uint32_t caller) {
    unsigned char data[4 * 56];
    for (unsigned i = 0; i < 56; ++i) {
        uint32_t value = i == 0 ? steps : caller;
        if (i >= 2 && !reg_get(sd, i - 2, &value)) return 0;
        for (unsigned b = 0; b < 4; ++b) data[4 * i + b] = value >> (8 * b);
    }
    answer(3, data, sizeof(data));
    return 1;
}

int main(int argc, char **argv) {
    unsigned char *buffer = malloc(LIMIT);
    uint32_t op, address, count;
    char *args[] = {"blackfin-worker", "--environment=virtual", "--model=bf527",
        "--memory-region=0,0x4000000", "--memory-region=0xFF800000,0x8000",
        "--memory-region=0xFF900000,0x8000", "--memory-region=0xFFA00000,0x14000",
        "--memory-region=0xFFC00000,0x3FF000", NULL};
    char *empty[] = {NULL};
    if (argc == 2 && strcmp(argv[1], "--operating") == 0) {
        args[1] = "--environment=operating";
        args[4] = NULL;
    } else if (argc != 1) return 2;
    reply = fdopen(dup(STDOUT_FILENO), "wb");
    if (!buffer || !reply || dup2(STDERR_FILENO, STDOUT_FILENO) < 0) return 2;
    default_callback.init(&default_callback);
    SIM_DESC sd = sim_open(SIM_OPEN_DEBUG, &default_callback, NULL, args);
    if (!sd || sim_create_inferior(sd, NULL, empty, empty) != SIM_RC_OK) return 3;
    answer(0, "BFIN4", 5);
    while (get32(&op) && get32(&address) && get32(&count)) {
        if (op == 0) break;
        if (op == 1 || op == 2) {
            if (count > LIMIT || (uint64_t)address + count > 0x100000000ULL) break;
            if (op == 2 && fread(buffer, 1, count, stdin) != count) break;
            uint64_t n = op == 1 ? sim_read(sd, address, buffer, count)
                                 : sim_write(sd, address, buffer, count);
            if (n != count) { answer(1, NULL, 0); break; }
            answer(0, buffer, op == 1 ? count : 0);
        } else if (op == 6) {
            if (count || !blech_bfin_hostdp_event(sd, address)) { answer(1, NULL, 0); break; }
            answer(0, NULL, 0);
        } else if (op == 3 || op == 4) {
            if (address > 53) { answer(1, NULL, 0); break; }
            uint32_t value;
            if (op == 3) {
                if (!reg_get(sd, address, &value)) { answer(1, NULL, 0); break; }
                answer(0, NULL, 0);
                put32(value); fflush(reply);
            } else {
                unsigned char b[] = {count, count >> 8, count >> 16, count >> 24};
                if (sim_store_register(sd, address, b, 4) != 4) { answer(1, NULL, 0); break; }
                answer(0, NULL, 0);
            }
        } else if (op == 5) {
            uint32_t steps = 0, pc = 0;
            int sig = 0;
            enum sim_stop reason = sim_stopped;
            if (!address || address > 1000000) { answer(1, NULL, 0); break; }
            blech_bfin_guard(address, count);
            sim_resume(sd, 0, 0);
            steps = blech_bfin_count();
            sim_stop_reason(sd, &reason, &sig);
            if (!reg_get(sd, 53, &pc)) { answer(1, NULL, 0); break; }
            if (reason != sim_stopped || sig != SIGTRAP || !blech_bfin_stopped()) {
                answer(2, NULL, 0); break;
            }
            if (pc >= 0xEF000000 && pc < 0xF0000000) {
                if (!rom_snapshot(sd, steps, blech_bfin_last())) { answer(1, NULL, 0); break; }
                continue;
            }
            answer(0, NULL, 0);
            put32(steps); put32(pc); fflush(reply);
        } else { answer(1, NULL, 0); break; }
    }
    sim_close(sd, 1);
    free(buffer);
    fclose(reply);
    return 0;
}
