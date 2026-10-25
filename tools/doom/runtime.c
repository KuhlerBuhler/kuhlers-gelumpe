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
#include "r_main.h"
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
static char console_lines[2][21];               /* the last two lines the engine printed, as the display can show them */
static unsigned int console_column;

/* Until the first frame the display shows where the engine is: DOOM, then its last two printed lines. */
static void console_show(void)
{
    unsigned char frame[1024];
    memset(frame, 0, sizeof(frame));
    doom_status_line(frame, 1, "DOOM");
    doom_status_line(frame, 3, console_lines[0]);
    doom_status_line(frame, 5, console_lines[1]);
    doom_status_send(frame);
}
static void console_put(char c)
{
    if (c == '\n') {
        memcpy(console_lines[0], console_lines[1], sizeof(console_lines[0]));
        memset(console_lines[1], 0, sizeof(console_lines[1]));
        console_column = 0;
        return;
    }
    if (c >= 'a' && c <= 'z') c = (char)(c - 'a' + 'A');
    if (console_column < sizeof(console_lines[1]) - 1) console_lines[1][console_column++] = c;
}

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
    if (shared->stage == DOOM_STAGE_ENGINE && !shared->frames) doom_status_display("DOOM", "OPEN WAD", 0, 0);
    for (unsigned int i = 0; i < 4; ++i) {
        if (!files[i].used) {
            memset(files[i].fil, 0, sizeof(files[i].fil));
            int result = fs_open(files[i].fil, DOOM_WAD_PATH);
            if (result) {
                if (shared->stage == DOOM_STAGE_ENGINE && !shared->frames) doom_status_display("DOOM", "WAD FEHLT", 0x800u + (uint32_t)result, 1);
                errno = EIO;
                return -1;
            }
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
    if (shared->stage == DOOM_STAGE_ENGINE && !shared->frames) {      /* the engine reads for a minute and more before its first frame */
        static uint32_t shown;
        uint32_t now = native_ticks();
        if (!shown || now - shown >= 200) { shown = now ? now : 1; doom_status_loading(shared->bytes_read, f->fil[3]); }
    }
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
        console_put((char)text[i]);
    }
    if (shared->stage == DOOM_STAGE_ENGINE && !shared->frames) console_show();
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
static const unsigned char pad_keys[16] = {
    KEY_STRAFE_L, KEY_UPARROW, KEY_STRAFE_R, 0, 0, 0, ']', KEY_USE,
    KEY_LEFTARROW, KEY_DOWNARROW, KEY_RIGHTARROW, 0, 0, 0, KEY_RSHIFT, KEY_FIRE
};
static const unsigned char panel_keys[16] = {
    KEY_ENTER, 0, KEY_FIRE, KEY_USE, 0, 0, 0, 0,
    KEY_LEFTARROW, KEY_ESCAPE, 0, KEY_UPARROW, KEY_RIGHTARROW, KEY_ESCAPE, 0, KEY_DOWNARROW
};
static uint16_t pads_down, panel_down;
static unsigned char led_values[32], led_cursor;
static uint32_t led_valid, led_tick;

static int action_held(unsigned char key)
{
    for (unsigned int i = 0; i < 16; ++i) {
        if (((pads_down >> i) & 1) && pad_keys[i] == key) return 1;
        if (((panel_down >> i) & 1) && panel_keys[i] == key) return 1;
    }
    return 0;
}
void doom_update_leds(void)
{
    uint32_t now = native_ticks();
    void *panel = *(void *volatile *)0xC033E6FCu;
    if ((uintptr_t)panel < 0xC0000000u || (uintptr_t)panel >= 0xC4000000u
        || ((volatile unsigned char *)panel)[4] || (uint32_t)(now - led_tick) < 10) return;
    led_tick = now;
    unsigned int sent = 0;
    for (unsigned int i = 0; i < 32 && sent < 4; ++i) {
        unsigned int index = led_cursor++ & 31, pad = index >> 1;
        unsigned char key = pad_keys[pad], value = 0;
        if (key) {
            int movement = key == KEY_UPARROW || key == KEY_DOWNARROW || key == KEY_LEFTARROW
                         || key == KEY_RIGHTARROW || key == KEY_STRAFE_L || key == KEY_STRAFE_R;
            int lit = (index & 1) ? key != KEY_FIRE : !movement;
            if (lit) value = ((pads_down >> pad) & 1) ? 255 : key == KEY_FIRE ? 96 : 64;
        }
        uint32_t bit = 1u << index;
        if ((led_valid & bit) && led_values[index] == value) continue;
        ((void (*)(void *, unsigned int, unsigned int))0xC0028600u)(panel, 0x2C + index, value);
        led_values[index] = value;
        led_valid |= bit;
        ++sent;
    }
}
int DG_GetKey(int *pressed, unsigned char *key)
{
    unsigned char message[5];
    for (unsigned int i = 0; i < 32; ++i) {
        if (!((int (*)(void *, void *))0xC0024B6Cu)((void *)0xC033E57Cu, message)) return 0;
        if (doom_power_message(message)) continue;
        if ((message[0] != 0 && message[0] != 4) || message[1] >= 16) continue;
        unsigned int index = message[1];
        *key = message[0] == 4 ? pad_keys[index] : panel_keys[index];
        if (!*key) continue;
        int before = action_held(*key);
        uint16_t *held = message[0] == 4 ? &pads_down : &panel_down;
        uint16_t bit = 1u << index;
        if (message[message[0] == 4 ? 4 : 2]) *held |= bit;
        else *held &= ~bit;
        *pressed = action_held(*key);
        if (*pressed == before) continue;
        ++shared->key_events;
        shared->last_key = *key;
        shared->last_down = *pressed;
        return 1;
    }
    return 0;
}
extern lighttable_t *colormaps;
extern fixed_t angleturn[3];
void doom_configure_controls(void)
{
    key_nextweapon = ']';
    key_menu_confirm = KEY_ENTER;
    key_menu_abort = KEY_ESCAPE;
    angleturn[0] = 320;
    angleturn[1] = 480;
    angleturn[2] = 240;
}
void __real_R_RenderPlayerView(player_t *player);
void __wrap_R_RenderPlayerView(player_t *player)
{
    lighttable_t *darkest = colormaps + 16 * 256;
    if (scalelight[0][0] > darkest) {
        for (unsigned int i = 0; i < LIGHTLEVELS; ++i)
            for (unsigned int j = 0; j < MAXLIGHTSCALE; ++j)
                if (scalelight[i][j] > darkest) scalelight[i][j] = darkest;
    }
    if (zlight[0][MAXLIGHTZ - 1] > darkest) {
        for (unsigned int i = 0; i < LIGHTLEVELS; ++i)
            for (unsigned int j = 0; j < MAXLIGHTZ; ++j)
                if (zlight[i][j] > darkest) zlight[i][j] = darkest;
    }
    __real_R_RenderPlayerView(player);
}
void DG_SetWindowTitle(const char *title) { (void)title; }
static inline unsigned int pixel_luma(uint32_t pixel)
{
    return ((pixel >> 16) & 255) * 77 + ((pixel >> 8) & 255) * 150 + (pixel & 255) * 29;
}
static const unsigned char display_levels[256] = {
    0, 28, 37, 43, 48, 53, 57, 61, 64, 67, 70, 73, 75, 78, 80, 82,
    84, 86, 88, 90, 92, 94, 96, 97, 99, 101, 102, 104, 105, 107, 108, 110,
    111, 113, 114, 115, 117, 118, 119, 120, 122, 123, 124, 125, 126, 127, 129, 130,
    131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146,
    147, 148, 149, 149, 150, 151, 152, 153, 154, 155, 155, 156, 157, 158, 159, 160,
    160, 161, 162, 163, 164, 164, 165, 166, 167, 167, 168, 169, 170, 170, 171, 172,
    173, 173, 174, 175, 175, 176, 177, 177, 178, 179, 179, 180, 181, 182, 182, 183,
    183, 184, 185, 185, 186, 187, 187, 188, 189, 189, 190, 190, 191, 192, 192, 193,
    194, 194, 195, 195, 196, 197, 197, 198, 198, 199, 199, 200, 201, 201, 202, 202,
    203, 203, 204, 205, 205, 206, 206, 207, 207, 208, 208, 209, 209, 210, 211, 211,
    212, 212, 213, 213, 214, 214, 215, 215, 216, 216, 217, 217, 218, 218, 219, 219,
    220, 220, 221, 221, 222, 222, 223, 223, 224, 224, 225, 225, 226, 226, 227, 227,
    228, 228, 229, 229, 230, 230, 230, 231, 231, 232, 232, 233, 233, 234, 234, 235,
    235, 235, 236, 236, 237, 237, 238, 238, 239, 239, 240, 240, 240, 241, 241, 242,
    242, 243, 243, 243, 244, 244, 245, 245, 246, 246, 246, 247, 247, 248, 248, 248,
    249, 249, 250, 250, 251, 251, 251, 252, 252, 253, 253, 253, 254, 254, 255, 255,
};
static void render_display(const uint32_t *pixels)
{
    int16_t errors[3][132] = {{0}};
    uint32_t horizontal[4][128];
    unsigned int next_row = 0;
    memset(display, 0, sizeof(display));
    for (unsigned int y = 0; y < 64; ++y) {
        unsigned int sy = y * 25 / 8;
        while (next_row < sy + 4) {
            const uint32_t *source = pixels + next_row * 320;
            uint32_t *row = horizontal[next_row & 3];
            for (unsigned int x = 0; x < 64; ++x) {
                unsigned int a = pixel_luma(source[0]), b = pixel_luma(source[1]);
                unsigned int c = pixel_luma(source[2]), d = pixel_luma(source[3]), e = pixel_luma(source[4]);
                row[2 * x] = 2 * a + 2 * b + c;
                row[2 * x + 1] = c + 2 * d + 2 * e;
                source += 5;
            }
            ++next_row;
        }
        const uint32_t *a = horizontal[sy & 3], *b = horizontal[(sy + 1) & 3];
        const uint32_t *c = horizontal[(sy + 2) & 3], *d = horizontal[(sy + 3) & 3];
        unsigned int first = 8 - (y & 7), last = 1 + (y & 7);
        int16_t *row = errors[y % 3], *next = errors[(y + 1) % 3], *last_row = errors[(y + 2) % 3];
        for (unsigned int x = 0; x < 128; ++x) {
            unsigned int sum = a[x] * first + (b[x] + c[x]) * 8 + d[x] * last;
            unsigned int at = x + 1;
            int value = display_levels[(sum + 16000) / 32000] + row[at];
            int white = value >= 128;
            if (!white) display[(y >> 3) * 128 + x] |= 1u << (y & 7);
            int error = (value - (white ? 255 : 0)) / 8;
            row[at + 1] += error;
            row[at + 2] += error;
            next[at - 1] += error;
            next[at] += error;
            next[at + 1] += error;
            last_row[at] += error;
        }
        memset(row, 0, sizeof(errors[0]));
    }
}
void DG_DrawFrame(void)
{
    render_display(DG_ScreenBuffer);
    memcpy((void *)0xC031B310u, display, sizeof(display));
    ((void (*)(void *, int, int))0xC0015DD0u)((void *)0xC031BB2Cu, 2, 0);
    ((void (*)(void *, int, int))0xC0015DD0u)((void *)0xC031BB2Cu, 3, 0);
    doom_update_leds();
    shared->gametic = gametic;
    shared->gamestate = gamestate;
    if (players[consoleplayer].mo) shared->viewangle = players[consoleplayer].mo->angle;
    ++shared->frames;
    if (gametic > 0 && gamestate == GS_LEVEL) shared->stage = DOOM_STAGE_PLAYING;
}
__attribute__((section(".text.entry"), noreturn))
void doom_runtime_start(struct doom_shared *state)
{
    doom_status_display("DOOM", "ENGINE", 0, 0);
    memset(__bss_start, 0, (size_t)(__bss_end - __bss_start));
    shared = state;
    if ((uintptr_t)state != DOOM_SHARED_ADDRESS || state->magic != DOOM_BOOT_MAGIC || state->version != DOOM_BOOT_VERSION) {
        doom_status_display("DOOM ERROR", "ABI", 0x700u, 1);
        for (;;) __asm__ volatile ("nop");
    }
    heap_end = __heap_start;
    clock_start = native_ticks();
    shared->stage = DOOM_STAGE_ENGINE;
    doom_status_display("DOOM", "ENGINE INIT", native_ticks(), 1);
    static char *argv[] = {"doom", "-iwad", DOOM_WAD_PATH, "-warp", "1", "1", "-nosound", "-nogui", "-mb", "6", NULL};
    doomgeneric_Create(sizeof(argv) / sizeof(argv[0]) - 1, argv);
    doom_configure_controls();
    for (;;) doomgeneric_Tick();
}
