/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE   /* fopencookie */
#endif
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <signal.h>
#include <unistd.h>
#include <string.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/un.h>
#include "bfd.h"
#include "sim/sim.h"
#include "sim/callback.h"

extern void blech_bfin_guard(uint32_t, uint32_t);
extern uint32_t blech_bfin_count(void);
extern uint32_t blech_bfin_last(void);
extern int blech_bfin_stopped(void);
extern void blech_bfin_time_guard(uint32_t);
extern uint64_t blech_bfin_time(void);
extern uint32_t blech_bfin_remaining(void);
extern int blech_bfin_sleeping(void);
extern int blech_bfin_hostdp_event(SIM_DESC, unsigned);
extern int blech_bfin_hostdp_bus(SIM_DESC, unsigned, uint32_t *);
extern int blech_bfin_sport_config(SIM_DESC, uint32_t, uint32_t, uint32_t, uint32_t);
extern int blech_bfin_sport_report(SIM_DESC, uint32_t *);
extern int blech_bfin_memory_window(uint32_t, uint32_t);
extern void blech_bfin_memory_report(uint64_t *, uint32_t *);

extern uint64_t blech_channel_size(void);
extern void *blech_channel_ring(void *, int);
extern int blech_ring_write(void *, const void *, uint64_t, int);
extern int64_t blech_ring_read(void *, void *, uint64_t, uint64_t, int, int64_t, int64_t);

/* Little-endian requests: opcode, address/register/budget, byte count/value/PC. */
#define LIMIT (1024 * 1024)
#define CHANNEL_SPIN_NS 200000
static FILE *reply, *request, *pipe_reply;
static int pipe_request = -1;

/* --channel: the same byte streams over shared memory (blackfin_channel.c); the pipes ring the bell. */
struct channel_end { void *ring; int bell; };

static ssize_t channel_read(void *cookie, char *data, size_t size)
{
    struct channel_end *end = cookie;
    int64_t n = blech_ring_read(end->ring, data, 1, size, end->bell, CHANNEL_SPIN_NS, -1);
    return n < 0 ? -1 : (ssize_t)n;
}

static ssize_t channel_write(void *cookie, const char *data, size_t size)
{
    struct channel_end *end = cookie;
    return blech_ring_write(end->ring, data, size, end->bell) ? -1 : (ssize_t)size;
}

#ifdef __APPLE__
static int apple_read(void *cookie, char *data, int size) { return (int)channel_read(cookie, data, size); }
static int apple_write(void *cookie, const char *data, int size) { return (int)channel_write(cookie, data, size); }
static FILE *channel_file(struct channel_end *end, int writing)
{
    return writing ? funopen(end, NULL, apple_write, NULL, NULL) : funopen(end, apple_read, NULL, NULL, NULL);
}
#else
static FILE *channel_file(struct channel_end *end, int writing)
{
    cookie_io_functions_t io = {writing ? NULL : channel_read, writing ? channel_write : NULL, NULL, NULL};
    return fopencookie(end, writing ? "w" : "r", io);
}
#endif

static int open_channel(const char *path, int in_bell, int out_bell, FILE **in, FILE **out)
{
    static struct channel_end ends[2];
    static char buffers[2][1 << 16];
    int fd = open(path, O_RDWR);
    if (fd < 0) return 0;
    void *shared = mmap(NULL, blech_channel_size(), PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);
    if (shared == MAP_FAILED) return 0;
    ends[0] = (struct channel_end){blech_channel_ring(shared, 0), in_bell};
    ends[1] = (struct channel_end){blech_channel_ring(shared, 1), out_bell};
    FILE *reader = channel_file(&ends[0], 0), *writer = channel_file(&ends[1], 1);
    if (!reader || !writer || setvbuf(reader, buffers[0], _IOFBF, sizeof(buffers[0]))
        || setvbuf(writer, buffers[1], _IOFBF, sizeof(buffers[1]))) return 0;
    *in = reader;
    *out = writer;   /* the pipe behind the old *out stays open as the bell */
    return 1;
}

static void answer(uint32_t status, const void *data, uint32_t count);

/* Op 19: this worker forks; the copy goes on from exactly this state for another host. `spec` is
   "<socket path>\0<channel path>": the copy connects to the socket the host listens on and carries
   its streams over that socket, or over the channel file with the socket as the bell when one is
   named. The original answers with the copy's pid and goes on serving its own host. */
static int fork_copy(const char *spec, uint32_t count, pid_t *pid)
{
    const char *channel = memchr(spec, 0, count);
    struct sockaddr_un address = {.sun_family = AF_UNIX};
    if (!channel || channel == spec || (size_t)(channel - spec) >= sizeof(address.sun_path)
        || spec[count - 1]) return 0;
    ++channel;
    memcpy(address.sun_path, spec, strlen(spec));
    fflush(NULL);
    *pid = fork();
    if (*pid < 0) return 0;
    if (*pid) return 1;
    /* The copy: drop the original's pipes, so its host still sees the original's end alone. */
    close(pipe_request);
    close(fileno(pipe_reply));
    int link = socket(AF_UNIX, SOCK_STREAM, 0);
    if (link < 0 || connect(link, (struct sockaddr *)&address, sizeof(address))) _exit(5);
    if (*channel) {
        if (!open_channel(channel, link, link, &request, &reply)) _exit(5);
    } else {
        request = fdopen(link, "rb");
        reply = fdopen(dup(link), "wb");
        if (!request || !reply) _exit(5);
    }
    answer(0, "BFIN9 copy", 10);
    return 1;
}

static int get32(uint32_t *value) {
    unsigned char b[4];
    if (fread(b, 1, 4, request) != 4) return 0;
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
    const char *channel = NULL;
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--operating") == 0) {
            args[1] = "--environment=operating";
            args[4] = NULL;
        } else if (strcmp(argv[i], "--channel") == 0 && i + 1 < argc) channel = argv[++i];
        else return 2;
    }
    /* The simulated UART reads the simulator's stdin (dv-bfin_uart.c), so the requests move off fd 0:
       a request byte there would reach the DSP as UART input, depending on when it arrived. */
    int quiet = open("/dev/null", O_RDONLY);
    pipe_request = dup(STDIN_FILENO);
    if (quiet < 0 || pipe_request < 0 || dup2(quiet, STDIN_FILENO) < 0) return 2;
    close(quiet);
    request = fdopen(pipe_request, "rb");
    reply = pipe_reply = fdopen(dup(STDOUT_FILENO), "wb");
    if (!buffer || !request || !reply || dup2(STDERR_FILENO, STDOUT_FILENO) < 0) return 2;
    /* Map the channel before the handshake, so the host may remove its file once answered. */
    FILE *channel_in = request, *channel_out = reply;
    if (channel && !open_channel(channel, pipe_request, fileno(reply), &channel_in, &channel_out)) return 4;
    default_callback.init(&default_callback);
    SIM_DESC sd = sim_open(SIM_OPEN_DEBUG, &default_callback, NULL, args);
    if (!sd || sim_create_inferior(sd, NULL, empty, empty) != SIM_RC_OK) return 3;
    signal(SIGCHLD, SIG_IGN);   /* copies (op 19) are reaped by the system */
    if (channel) answer(0, "BFIN9 channel", 13);
    else answer(0, "BFIN9", 5);
    /* The handshake went over the pipe; from here on the rings carry the streams. */
    request = channel_in;
    reply = channel_out;
    while (get32(&op) && get32(&address) && get32(&count)) {
        if (op == 0) break;
        if (op == 1 || op == 2) {
            if (count > LIMIT || (uint64_t)address + count > 0x100000000ULL) break;
            if (op == 2 && fread(buffer, 1, count, request) != count) break;
            uint64_t n = op == 1 ? sim_read(sd, address, buffer, count)
                                 : sim_write(sd, address, buffer, count);
            if (n != count) { answer(1, NULL, 0); break; }
            answer(0, buffer, op == 1 ? count : 0);
        } else if (op == 19) {
            pid_t pid;
            if (address || !count || count > 4096 || fread(buffer, 1, count, request) != count) break;
            if (!fork_copy((const char *)buffer, count, &pid)) { answer(1, NULL, 0); break; }
            if (pid) {
                unsigned char value[] = {pid, pid >> 8, pid >> 16, pid >> 24};
                answer(0, value, 4);
            }
        } else if (op == 20) {
            /* A poll loop of the ARM, ahead: `address` runs, each advancing the next of the cycle steps that
               follow a ready address and word (4 bytes each, as op 18 would), as long as the HOSTDP status
               stays `count` and, with a ready address, the 4 bytes there stay the word. Answers the runs
               done, whether something changed in the last of them, and the status. A ROM entry ends the
               request with the ROM diagnostic instead (rom_snapshot); the host finds the run from the clock. */
            uint32_t n = address, done = 0, changed = 0, status = count, ready, word;
            int failed = 0, rom = 0;
            if (!n || n > LIMIT / 4 - 2 || fread(buffer, 1, 4 * n + 8, request) != 4 * n + 8) break;
            memcpy(&ready, buffer, 4);
            memcpy(&word, buffer + 4, 4);
            for (; done < n; ++done) {
                const unsigned char *at = buffer + 8 + 4 * done;
                uint32_t cycles = at[0] | (uint32_t)at[1] << 8 | (uint32_t)at[2] << 16 | (uint32_t)at[3] << 24;
                if (cycles > 1000000) { failed = 1; break; }
                if (cycles) {
                    uint32_t pc, executed;
                    int sig = 0;
                    enum sim_stop reason = sim_stopped;
                    blech_bfin_time_guard(cycles);
                    sim_resume(sd, 0, 0);
                    executed = blech_bfin_count();
                    sim_stop_reason(sd, &reason, &sig);
                    if (!reg_get(sd, 53, &pc)) { failed = 1; break; }
                    if (reason != sim_stopped || sig != SIGTRAP || !blech_bfin_stopped()) { failed = 2; break; }
                    if (pc >= 0xEF000000 && pc < 0xF0000000) {
                        if (!rom_snapshot(sd, executed, blech_bfin_last())) failed = 1;
                        rom = 1;
                        break;
                    }
                }
                if (!blech_bfin_hostdp_bus(sd, 0, &status)) { failed = 1; break; }
                if (status != count) { ++done; changed = 1; break; }
                if (ready) {
                    uint32_t now;
                    if (sim_read(sd, ready, (unsigned char *)&now, 4) != 4) { failed = 1; break; }
                    if (now != word) { ++done; changed = 1; break; }
                }
            }
            if (failed) { answer(failed, NULL, 0); break; }
            if (rom) continue;
            unsigned char data[12];
            uint32_t out[3] = {done, changed, status};
            for (unsigned i = 0; i < 3; ++i)
                for (unsigned b = 0; b < 4; ++b) data[4 * i + b] = out[i] >> (8 * b);
            answer(0, data, sizeof(data));
        } else if (op == 16) {
            if (!blech_bfin_memory_window(address, count)) { answer(1, NULL, 0); break; }
            answer(0, NULL, 0);
        } else if (op == 17) {
            uint64_t counts[8];
            uint32_t locations[16];
            if (address || count) { answer(1, NULL, 0); break; }
            blech_bfin_memory_report(counts, locations);
            answer(0, NULL, 0);
            for (unsigned i = 0; i < 8; ++i) { put32(counts[i]); put32(counts[i] >> 32); }
            for (unsigned i = 0; i < 16; ++i) put32(locations[i]);
            fflush(reply);
        } else if (op == 14) {
            if (address || count) { answer(1, NULL, 0); break; }
            uint64_t ticks = blech_bfin_time();
            answer(0, NULL, 0);
            put32(ticks); put32(ticks >> 32);
            put32(blech_bfin_remaining()); put32(blech_bfin_sleeping()); fflush(reply);
        } else if ((op >= 9 && op <= 12) || op == 15) {
            uint32_t word = count;
            if (address || ((op == 9 || op == 12) && count)
                || (op == 15 && count)
                || !blech_bfin_hostdp_bus(sd, op == 15 ? 4 : op - 9, &word)) {
                answer(1, NULL, 0); break;
            }
            answer(0, NULL, 0);
            if (op == 9 || op == 12 || op == 15) { put32(word); fflush(reply); }
        } else if (op == 7) {
            uint32_t hz, rate, mode, seed;
            if (address || count != 16 || !get32(&hz) || !get32(&rate)
                || !get32(&mode) || !get32(&seed)
                || !blech_bfin_sport_config(sd, hz, rate, mode, seed)) {
                answer(1, NULL, 0); break;
            }
            answer(0, NULL, 0);
        } else if (op == 8) {
            uint32_t report[12];
            if (address || count || !blech_bfin_sport_report(sd, report)) {
                answer(1, NULL, 0); break;
            }
            answer(0, NULL, 0);
            for (unsigned i = 0; i < 12; ++i) put32(report[i]);
            fflush(reply);
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
        } else if (op == 18) {
            /* One round trip per ARM sync: advance `address` cycles (0: none), then report the time
               advanced, steps, PC, idle, the HOSTDP status and the word at `count` (0: none). */
            uint32_t out[6] = {0}, word = 0;
            int sig = 0;
            enum sim_stop reason = sim_stopped;
            if (address > 1000000) { answer(1, NULL, 0); break; }
            if (address) {
                uint64_t before = blech_bfin_time();
                blech_bfin_time_guard(address);
                sim_resume(sd, 0, 0);
                out[1] = blech_bfin_count();
                sim_stop_reason(sd, &reason, &sig);
                if (!reg_get(sd, 53, &out[2])) { answer(1, NULL, 0); break; }
                if (reason != sim_stopped || sig != SIGTRAP || !blech_bfin_stopped()) {
                    answer(2, NULL, 0); break;
                }
                if (out[2] >= 0xEF000000 && out[2] < 0xF0000000) {
                    if (!rom_snapshot(sd, out[1], blech_bfin_last())) { answer(1, NULL, 0); break; }
                    continue;
                }
                out[0] = blech_bfin_time() - before;
            } else if (!reg_get(sd, 53, &out[2])) { answer(1, NULL, 0); break; }
            out[3] = blech_bfin_sleeping();
            if (!blech_bfin_hostdp_bus(sd, 0, &word)) { answer(1, NULL, 0); break; }
            out[4] = word;
            if (count && sim_read(sd, count, (unsigned char *)&out[5], 4) != 4) { answer(1, NULL, 0); break; }
            unsigned char data[24];
            for (unsigned i = 0; i < 5; ++i)
                for (unsigned b = 0; b < 4; ++b) data[4 * i + b] = out[i] >> (8 * b);
            memcpy(data + 20, &out[5], 4);
            answer(0, data, sizeof(data));
        } else if (op == 5 || op == 13) {
            uint32_t steps = 0, pc = 0;
            int sig = 0;
            enum sim_stop reason = sim_stopped;
            if (!address || address > 1000000) { answer(1, NULL, 0); break; }
            uint64_t before = blech_bfin_time();
            if (op == 13) blech_bfin_time_guard(address);
            else blech_bfin_guard(address, count);
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
            if (op == 13) put32(blech_bfin_time() - before);
            put32(steps); put32(pc); fflush(reply);
            if (op == 13) { put32(blech_bfin_sleeping()); fflush(reply); }
        } else { answer(1, NULL, 0); break; }
    }
    sim_close(sd, 1);
    free(buffer);
    fclose(reply);
    return 0;
}
