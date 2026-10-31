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
static int open_file(void *file, const char *path) { return ((int (*)(void *,const char *,int))0xC009DB60u)(file,path,1); }
static int close_file(void *file) { return ((int (*)(void *))0xC009E3DCu)(file); }
/* FatFs answers for a card that has no such file or folder, or no card or no file system at all. */
static int absent(int result) { return result==4 || result==5 || result==11 || result==13; }
/* Returns 0 when doom.bin or doom.wad is not on the card: nothing of the start is changed yet, the sampler starts as without
   SHIFT + TAP. The card is readable here, the start has registered the volume and run the SD task before this hook. */
int doom_load(void)
{
    zero(__bss_start, (unsigned int)(__bss_end-__bss_start));
    zero((void *)state, sizeof(*state));
    /* FatFs registers the volume before mounting it lazily on the first file access. */
    const unsigned char *volume = *(const unsigned char *const *)0xC06A010Cu;
    if (!volume) return 0;
    int result=open_file(fil,DOOM_WAD_PATH);
    if (absent(result)) return 0;
    if (!result) close_file(fil);
    int opened=!result && !(result=open_file(fil,DOOM_PROGRAM_PATH));
    if (absent(result)) return 0;
    state->magic=DOOM_BOOT_MAGIC; state->version=DOOM_BOOT_VERSION;
    state->stage=DOOM_STAGE_SELECTED;
    doom_status_display("DOOM", "BOOT", 0, 0);
    ((void (*)(int))0xC0025754u)(1);
    ((void (*)(int))0xC00005A0u)(8);
    ((void (*)(int))0xC0025A14u)(1);
    ((void (*)(void))0xC003FD20u)();
    for (unsigned int attempt=0; !opened && attempt<6; ++attempt) {
        result=open_file(fil,DOOM_PROGRAM_PATH);
        if (!result) break;
        doom_power_poll_initializing();
        ((void (*)(unsigned int))0xC0000B78u)(500);
    }
    if (result) failed((volume[0] ? 0x200u : 0x100u)+(unsigned int)result);
    state->stage=DOOM_STAGE_MOUNTED;
    doom_status_display("DOOM", "READ", 0, 1);
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
        if (!((EXPECTED_PROGRAM_BYTES-left) & 0x7fffu) || !left)
            doom_status_display("DOOM", "READ", EXPECTED_PROGRAM_BYTES-left, 1);
    }
    result=((int (*)(void *))0xC009E3DCu)(fil);
    if (result) failed(0x600u+(unsigned int)result);
    sha256_finish(&hash,digest);
    static const unsigned char expected[32]=EXPECTED_PROGRAM_SHA256;
    for (unsigned int i=0; i<32; ++i) if (digest[i]!=expected[i]) failed(0x500);
    state->stage=DOOM_STAGE_VERIFIED;
    doom_status_display("DOOM", "START", 0, 0);
    doom_enter((void *)state);
}
