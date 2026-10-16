/* SPDX-License-Identifier: AGPL-3.0-or-later */
#include <errno.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <unistd.h>
#include "doomgeneric.h"

#ifndef PROBE_ZONE_MIB
#define PROBE_ZONE_MIB "16"
#endif

extern unsigned char __heap_start[], __heap_limit[];
unsigned char *probe_heap_end = __heap_start;
unsigned char probe_display[1024];
unsigned int probe_frames;
unsigned int probe_ticks;

static int host(unsigned int op, unsigned int a, unsigned int b, unsigned int c)
{
    register unsigned int r0 __asm__("r0") = op;
    register unsigned int r1 __asm__("r1") = a;
    register unsigned int r2 __asm__("r2") = b;
    register unsigned int r3 __asm__("r3") = c;
    __asm__ volatile ("svc #0x123456" : "+r"(r0) : "r"(r1), "r"(r2), "r"(r3) : "memory", "cc");
    return (int)r0;
}

void *_sbrk(ptrdiff_t size)
{
    unsigned char *old = probe_heap_end;
    if (size < 0 || size > __heap_limit - probe_heap_end) {
        errno = ENOMEM;
        return (void *)-1;
    }
    probe_heap_end += size;
    return old;
}
int _open(const char *path, int flags, int mode) { (void)mode; return host(1, (uintptr_t)path, flags, 0); }
int _close(int fd) { return host(2, fd, 0, 0); }
int _read(int fd, void *buf, size_t count) { return host(3, fd, (uintptr_t)buf, count); }
int _write(int fd, const void *buf, size_t count) { return host(4, fd, (uintptr_t)buf, count); }
int _lseek(int fd, int offset, int whence) { return host(5, fd, offset, whence); }
int _isatty(int fd) { return fd < 3; }
int _fstat(int fd, struct stat *st) { (void)fd; st->st_mode = S_IFREG; st->st_blksize = 4096; return 0; }
int _stat(const char *path, struct stat *st) { int size = host(6, (uintptr_t)path, 0, 0); if (size < 0) { errno=ENOENT; return -1; } st->st_mode=S_IFREG; st->st_size=size; return 0; }
int _getpid(void) { return 1; }
int _kill(int pid, int sig) { (void)pid; (void)sig; errno=EINVAL; return -1; }
int _gettimeofday(struct timeval *tv, void *tz) { (void)tz; tv->tv_sec=probe_ticks/1000; tv->tv_usec=(probe_ticks%1000)*1000; return 0; }
int _unlink(const char *path) { (void)path; errno=EROFS; return -1; }
int mkdir(const char *path, mode_t mode) { (void)path; (void)mode; errno=EROFS; return -1; }
int _link(const char *a, const char *b) { (void)a; (void)b; errno=EROFS; return -1; }
int _rename(const char *a, const char *b) { (void)a; (void)b; errno=EROFS; return -1; }
void _init(void) {}
void _fini(void) {}
void _exit(int status) { host(7, status, 0, 0); for (;;) {} }

void DG_Init(void) {}
void DG_SleepMs(uint32_t ms) { probe_ticks += ms; }
uint32_t DG_GetTicksMs(void) { return probe_ticks++; }
int DG_GetKey(int *pressed, unsigned char *key) { return host(9, (uintptr_t)pressed, (uintptr_t)key, 0); }
void DG_SetWindowTitle(const char *title) { (void)title; }

void DG_DrawFrame(void)
{
    static const unsigned char bayer[16] = {0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5};
    for (unsigned int i=0; i<sizeof(probe_display); ++i) probe_display[i]=0;
    for (unsigned int y=0; y<64; ++y) {
        for (unsigned int x=0; x<128; ++x) {
            unsigned int pixel=DG_ScreenBuffer[(y*200/64)*320+(x*320/128)];
            unsigned int luma=(((pixel>>16)&255)*77+((pixel>>8)&255)*150+(pixel&255)*29)>>8;
            if (luma > (unsigned int)bayer[(y&3)*4+(x&3)]*16+8)
                probe_display[(y>>3)*128+x] |= 1u<<(y&7);
        }
    }
    ++probe_frames;
    host(8, (uintptr_t)probe_display, (uintptr_t)DG_ScreenBuffer, probe_frames);
}

void probe_start(void)
{
    static char *argv[]={"doom", "-iwad", "/freedoom1.wad", "-warp", "1", "1",
#ifndef PROBE_MONSTERS
        "-nomonsters",
#endif
        "-nosound", "-mb", PROBE_ZONE_MIB, NULL};
    doomgeneric_Create(sizeof(argv)/sizeof(argv[0])-1, argv);
    for (;;) doomgeneric_Tick();
}
