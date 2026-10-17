/* SPDX-License-Identifier: AGPL-3.0-or-later */
#include "runtime_abi.h"
#include "sha256.h"
#include "expected_program.h"
#include "status_display.h"
#include "native_power.h"
extern unsigned char __bss_start[], __bss_end[];
extern void doom_enter(struct doom_shared *) __attribute__((noreturn));
static uint32_t fil[0x240 / 4];
static volatile struct doom_shared *const state = (void *)DOOM_SHARED_ADDRESS;
static void zero(void *p, unsigned int n) { unsigned char *b=p; while (n--) *b++=0; }
static void failed(uint32_t error) __attribute__((noreturn));
static void failed(uint32_t error)
{
    state->error = error;
    state->stage = DOOM_STAGE_ERROR;
    doom_status_display("DOOM ERROR","POWER OFF",error,1);
    doom_power_idle();
}
void doom_load(void)
{
    zero(__bss_start, (unsigned int)(__bss_end-__bss_start));
    zero((void *)state, sizeof(*state));
    state->magic=DOOM_BOOT_MAGIC; state->version=DOOM_BOOT_VERSION;
    state->stage=DOOM_STAGE_SELECTED;
    ((void (*)(int))0xC0025754u)(1);
    ((void (*)(int))0xC00005A0u)(8);
    ((void (*)(int))0xC0025A14u)(1);
    ((void (*)(void))0xC003FD20u)();
    /* The firmware has just mounted the card (its own FatFs volume, as the plugins read it). Mounting it again this early
       failed on the device with FR_DISK_ERR (0x101). Its volume entry is 0 or its type byte 0 when there is no card. */
    const unsigned char *volume = *(const unsigned char *const *)0xC06A010Cu;
    if (!volume || !volume[0]) failed(0x100u);
    state->stage=DOOM_STAGE_MOUNTED;
    int result=((int (*)(void *,const char *,int))0xC009DB60u)(fil,DOOM_PROGRAM_PATH,1);
    if (result) failed(0x200u+(unsigned int)result);
    if (fil[3] != EXPECTED_PROGRAM_BYTES) {
        ((int (*)(void *))0xC009E3DCu)(fil);
        failed(0x300);
    }
    struct sha256 hash;
    unsigned char digest[32];
    sha256_init(&hash);
    unsigned char *at=(void *)DOOM_ENGINE_BASE;
    for (unsigned int left=EXPECTED_PROGRAM_BYTES; left;) {
        unsigned int count=left>4096?4096:left, done=0;
        result=((int (*)(void *,void *,unsigned int,unsigned int *))0xC009DD74u)(fil,at,count,&done);
        if (result || done != count) {
            ((int (*)(void *))0xC009E3DCu)(fil);
            failed(0x400u+(unsigned int)result);
        }
        sha256_add(&hash,at,count);
        doom_power_poll_initializing();
        left-=count; at+=count;
    }
    result=((int (*)(void *))0xC009E3DCu)(fil);
    if (result) failed(0x600u+(unsigned int)result);
    sha256_finish(&hash,digest);
    static const unsigned char expected[32]=EXPECTED_PROGRAM_SHA256;
    for (unsigned int i=0; i<32; ++i) if (digest[i]!=expected[i]) failed(0x500);
    state->stage=DOOM_STAGE_VERIFIED;
    doom_enter((void *)state);
}
