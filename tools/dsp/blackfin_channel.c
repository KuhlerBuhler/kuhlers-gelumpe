/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Shared-memory byte channel between blackfin_backend.py and the Blackfin worker.
   Two single-producer rings carry the same byte stream as the request and reply pipes. A reader
   spins for a short while and then sleeps on the old pipe, which now only rings a bell: the writer
   sends one byte when the reader said it sleeps. A closed pipe still reports a dead peer.
   Built into the worker and, as a shared library, loaded by the Python side. */
#include <errno.h>
#include <poll.h>
#include <stdalign.h>
#include <stdatomic.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define BLECH_RING (4u << 20)   /* larger than any request or answer: one message never waits for room */

struct blech_ring {
    alignas(64) _Atomic uint64_t head;      /* bytes written, by the producer */
    alignas(64) _Atomic uint64_t tail;      /* bytes read, by the consumer */
    alignas(64) _Atomic uint32_t sleeping;  /* the consumer waits on its bell */
    alignas(64) unsigned char data[BLECH_RING];
};

struct blech_channel {
    struct blech_ring to_worker, to_host;
};

static int64_t now_ns(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (int64_t)t.tv_sec * 1000000000 + t.tv_nsec;
}

uint64_t blech_channel_size(void)
{
    return sizeof(struct blech_channel);
}

void *blech_channel_ring(void *channel, int to_host)
{
    struct blech_channel *c = channel;
    return to_host ? (void *)&c->to_host : (void *)&c->to_worker;
}

/* Writes all `count` bytes; rings `bell` when the reader sleeps. 0 on success, -1 on error. */
int blech_ring_write(void *ring, const void *data, uint64_t count, int bell)
{
    struct blech_ring *r = ring;
    const unsigned char *p = data;
    uint64_t head = atomic_load_explicit(&r->head, memory_order_relaxed);
    while (count) {
        uint64_t room = BLECH_RING - (head - atomic_load_explicit(&r->tail, memory_order_acquire));
        if (!room) {
            struct timespec pause = {0, 10000};
            nanosleep(&pause, NULL);
            continue;
        }
        uint64_t n = count < room ? count : room;
        uint64_t at = head % BLECH_RING, first = BLECH_RING - at < n ? BLECH_RING - at : n;
        memcpy(r->data + at, p, first);
        memcpy(r->data, p + first, n - first);
        head += n;
        p += n;
        count -= n;
        atomic_store_explicit(&r->head, head, memory_order_release);
    }
    atomic_thread_fence(memory_order_seq_cst);
    if (atomic_load_explicit(&r->sleeping, memory_order_relaxed)) {
        ssize_t sent;
        do sent = write(bell, "", 1); while (sent < 0 && errno == EINTR);
        if (sent < 0 && errno != EAGAIN) return -1;
    }
    return 0;
}

/* Reads at least `least` and at most `most` bytes. Spins `spin_ns`, then sleeps on `bell`.
   Returns the count, 0 when the peer closed its bell, -1 after `timeout_ms` (< 0: none), -2 on error. */
int64_t blech_ring_read(void *ring, void *data, uint64_t least, uint64_t most, int bell,
                        int64_t spin_ns, int64_t timeout_ms)
{
    struct blech_ring *r = ring;
    unsigned char *p = data;
    uint64_t got = 0, tail = atomic_load_explicit(&r->tail, memory_order_relaxed);
    int64_t start = now_ns();
    while (got < least) {
        uint64_t ready = atomic_load_explicit(&r->head, memory_order_acquire) - tail;
        if (!ready) {
            int64_t waited = now_ns() - start;
            if (timeout_ms >= 0 && waited >= timeout_ms * 1000000) return -1;
            if (waited < spin_ns) continue;
            atomic_store_explicit(&r->sleeping, 1, memory_order_relaxed);
            atomic_thread_fence(memory_order_seq_cst);
            if (atomic_load_explicit(&r->head, memory_order_relaxed) == tail) {
                struct pollfd wait = {bell, POLLIN, 0};
                int limit = timeout_ms < 0 ? -1 : (int)(timeout_ms - waited / 1000000) + 1;
                int woke = poll(&wait, 1, limit);
                if (woke < 0 && errno != EINTR) {
                    atomic_store_explicit(&r->sleeping, 0, memory_order_relaxed);
                    return -2;
                }
                if (woke > 0) {
                    unsigned char drain[64];
                    ssize_t n = read(bell, drain, sizeof(drain));
                    if (n == 0) {
                        atomic_store_explicit(&r->sleeping, 0, memory_order_relaxed);
                        if (atomic_load_explicit(&r->head, memory_order_acquire) == tail) return 0;
                    }
                }
            }
            atomic_store_explicit(&r->sleeping, 0, memory_order_relaxed);
            continue;
        }
        uint64_t n = most - got < ready ? most - got : ready;
        uint64_t at = tail % BLECH_RING, first = BLECH_RING - at < n ? BLECH_RING - at : n;
        memcpy(p + got, r->data + at, first);
        memcpy(p + got + first, r->data, n - first);
        tail += n;
        got += n;
        atomic_store_explicit(&r->tail, tail, memory_order_release);
    }
    return (int64_t)got;
}
