/* SPDX-License-Identifier: AGPL-3.0-or-later */
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <unistd.h>
#include "doomgeneric.h"
#include "doomkeys.h"
#include "doomstat.h"
#include "m_controls.h"
#include "runtime_abi.h"
#include "status_display.h"
#include "native_power.h"

extern unsigned char __bss_start[], __bss_end[], __heap_start[], __heap_limit[];
static volatile struct doom_shared *shared;
static unsigned char *heap_end;
static uint32_t clock_start;
static unsigned char display[1024];
struct native_file { uint32_t fil[0x240 / 4]; uint32_t used; };
static struct native_file files[4];

static uint32_t native_ticks(void) { return *(volatile uint32_t *)0xC06A2930u; }
static int fs_open(void *fil, const char *path) { return ((int (*)(void *, const char *, int))0xC009DB60u)(fil, path, 1); }
static int fs_close(void *fil) { return ((int (*)(void *))0xC009E3DCu)(fil); }
static struct native_file *file_for(int fd)
{
    if (fd < 3 || fd >= 7 || !files[fd - 3].used) { errno = EBADF; return NULL; }
    return &files[fd - 3];
}

void *_sbrk(ptrdiff_t size)
{
    unsigned char *old = heap_end;
    if (size < 0 || (size_t)size > (size_t)(__heap_limit - heap_end)) { errno = ENOMEM; return (void *)-1; }
    heap_end += size;
    shared->heap_used = (uint32_t)(heap_end - __heap_start);
    return old;
}
int _open(const char *path, int flags, int mode)
{
    (void)mode;
    if ((flags & O_ACCMODE) != O_RDONLY || (flags & (O_CREAT | O_TRUNC | O_APPEND))) { errno = EROFS; return -1; }
    if (strcmp(path, DOOM_WAD_PATH)) { errno = ENOENT; return -1; }
    for (unsigned int i = 0; i < 4; ++i) {
        if (!files[i].used) {
            memset(files[i].fil, 0, sizeof(files[i].fil));
            if (fs_open(files[i].fil, DOOM_WAD_PATH)) { errno = EIO; return -1; }
            files[i].used = 1;
            return (int)i + 3;
        }
    }
    errno = EMFILE;
    return -1;
}
int _close(int fd)
{
    struct native_file *f = file_for(fd);
    if (!f) return -1;
    int result = fs_close(f->fil);
    f->used = 0;
    if (result) { errno = EIO; return -1; }
    return 0;
}
int _read(int fd, void *buffer, size_t count)
{
    struct native_file *f = file_for(fd);
    uint32_t done = 0;
    if (!f) return -1;
    if (count > INT_MAX) { errno = EINVAL; return -1; }
    int result = ((int (*)(void *, void *, uint32_t, uint32_t *))0xC009DD74u)(f->fil, buffer, count, &done);
    if (shared->stage == DOOM_STAGE_ENGINE) doom_power_poll_initializing();
    ++shared->file_reads;
    shared->bytes_read += done;
    if (result) { errno = EIO; return -1; }
    return (int)done;
}
int _write(int fd, const void *buffer, size_t count)
{
    const unsigned char *text = buffer;
    if (fd != 1 && fd != 2) { errno = EROFS; return -1; }
    if (count > INT_MAX) { errno = EINVAL; return -1; }
    for (size_t i = 0; i < count; ++i) {
        uint32_t at = shared->console_head;
        shared->console[at % sizeof(shared->console)] = text[i];
        shared->console_head = at + 1;
    }
    return (int)count;
}
int _lseek(int fd, int offset, int whence)
{
    struct native_file *f = file_for(fd);
    if (!f) return -1;
    int64_t base;
    if (whence == SEEK_SET) base = 0;
    else if (whence == SEEK_CUR) base = f->fil[2];
    else if (whence == SEEK_END) base = f->fil[3];
    else { errno = EINVAL; return -1; }
    int64_t target = base + offset;
    if (target < 0 || target > f->fil[3] || target > INT_MAX) { errno = EINVAL; return -1; }
    if (((int (*)(void *, uint32_t))0xC009E404u)(f->fil, (uint32_t)target)) { errno = EIO; return -1; }
    if (f->fil[2] != (uint32_t)target) { errno = EIO; return -1; }
    return (int)target;
}
int _fstat(int fd, struct stat *st)
{
    memset(st, 0, sizeof(*st));
    if (fd >= 0 && fd < 3) { st->st_mode = S_IFCHR; return 0; }
    struct native_file *f = file_for(fd);
    if (!f) return -1;
    st->st_mode = S_IFREG | S_IRUSR;
    st->st_size = f->fil[3];
    st->st_blksize = 512;
    return 0;
}
int _stat(const char *path, struct stat *st)
{
    int fd = _open(path, O_RDONLY, 0);
    if (fd < 0) return -1;
    int result = _fstat(fd, st);
    if (_close(fd)) return -1;
    return result;
}
int _isatty(int fd) { return fd >= 0 && fd < 3; }
int _getpid(void) { return 1; }
int _kill(int pid, int sig) { (void)pid; (void)sig; errno = EINVAL; return -1; }
int _gettimeofday(struct timeval *tv, void *tz)
{
    (void)tz;
    uint32_t ms = native_ticks() - clock_start;
    tv->tv_sec = ms / 1000;
    tv->tv_usec = (ms % 1000) * 1000;
    return 0;
}
int _unlink(const char *path) { (void)path; errno = EROFS; return -1; }
int mkdir(const char *path, mode_t mode) { (void)path; (void)mode; errno = EROFS; return -1; }
int _link(const char *a, const char *b) { (void)a; (void)b; errno = EROFS; return -1; }
int _rename(const char *a, const char *b) { (void)a; (void)b; errno = EROFS; return -1; }
void _init(void) {}
void _fini(void) {}
void _exit(int status)
{
    shared->exit_status = (uint32_t)status;
    shared->error = (uint32_t)status;
    shared->stage = status ? DOOM_STAGE_ERROR : DOOM_STAGE_STOPPED;
    doom_status_display(status ? "DOOM ERROR" : "DOOM STOP", "POWER OFF", (uint32_t)status, status != 0);
    doom_power_idle();
}
void __real_I_Quit(void);
void __wrap_I_Quit(void)
{
    __real_I_Quit();
    _exit(0);
}
void DG_Init(void) {}
uint32_t DG_GetTicksMs(void)
{
    uint32_t elapsed = native_ticks() - clock_start;
    shared->clock_millis = elapsed;
    return elapsed;
}
void DG_SleepMs(uint32_t ms)
{
    uint32_t start = native_ticks();
    while ((uint32_t)(native_ticks() - start) < ms) __asm__ volatile ("nop");
}
int DG_GetKey(int *pressed, unsigned char *key)
{
    unsigned char message[5];
    for (unsigned int i = 0; i < 32; ++i) {
        if (!((int (*)(void *, void *))0xC0024B6Cu)((void *)0xC033E57Cu, message)) return 0;
        if (doom_power_message(message)) continue;
        if (message[0] != 0) continue;
        switch (message[1]) {
        case 11: *key = KEY_UPARROW; break;
        case 15: *key = KEY_DOWNARROW; break;
        case 8: *key = KEY_LEFTARROW; break;
        case 12: *key = KEY_RIGHTARROW; break;
        case 2: *key = KEY_FIRE; break;
        case 3: *key = KEY_USE; break;
        case 0: *key = KEY_ENTER; break;
        case 9: case 13: *key = KEY_ESCAPE; break;
        default: continue;
        }
        *pressed = message[2] != 0;
        ++shared->key_events;
        shared->last_key = *key;
        shared->last_down = *pressed;
        return 1;
    }
    return 0;
}
void DG_SetWindowTitle(const char *title) { (void)title; }
void DG_DrawFrame(void)
{
    static const unsigned char bayer[16] = {0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5};
    memset(display, 0, sizeof(display));
    for (unsigned int y = 0; y < 64; ++y) {
        for (unsigned int x = 0; x < 128; ++x) {
            uint32_t pixel = DG_ScreenBuffer[(y * 200 / 64) * 320 + x * 320 / 128];
            uint32_t luma = (((pixel >> 16) & 255) * 77 + ((pixel >> 8) & 255) * 150 + (pixel & 255) * 29) >> 8;
            if (luma <= (uint32_t)bayer[(y & 3) * 4 + (x & 3)] * 16 + 8)
                display[(y >> 3) * 128 + x] |= 1u << (y & 7);
        }
    }
    memcpy((void *)0xC031B310u, display, sizeof(display));
    ((void (*)(void *, int, int))0xC0015DD0u)((void *)0xC031BB2Cu, 2, 0);
    ((void (*)(void *, int, int))0xC0015DD0u)((void *)0xC031BB2Cu, 3, 0);
    shared->gametic = gametic;
    shared->gamestate = gamestate;
    if (players[consoleplayer].mo) shared->viewangle = players[consoleplayer].mo->angle;
    ++shared->frames;
    if (gametic > 0 && gamestate == GS_LEVEL) shared->stage = DOOM_STAGE_PLAYING;
}
__attribute__((section(".text.entry"), noreturn))
void doom_runtime_start(struct doom_shared *state)
{
    memset(__bss_start, 0, (size_t)(__bss_end - __bss_start));
    shared = state;
    if ((uintptr_t)state != DOOM_SHARED_ADDRESS || state->magic != DOOM_BOOT_MAGIC || state->version != DOOM_BOOT_VERSION) for (;;) __asm__ volatile ("nop");
    heap_end = __heap_start;
    clock_start = native_ticks();
    shared->stage = DOOM_STAGE_ENGINE;
    static char *argv[] = {"doom", "-iwad", DOOM_WAD_PATH, "-warp", "1", "1", "-nosound", "-nogui", "-mb", "6", NULL};
    doomgeneric_Create(sizeof(argv) / sizeof(argv[0]) - 1, argv);
    key_menu_confirm = KEY_ENTER;
    key_menu_abort = KEY_ESCAPE;
    for (;;) doomgeneric_Tick();
}
