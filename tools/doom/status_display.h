/* SPDX-License-Identifier: AGPL-3.0-or-later */
#ifndef GELUMPE_DOOM_STATUS_DISPLAY_H
#define GELUMPE_DOOM_STATUS_DISPLAY_H
#include <stdint.h>

static inline const unsigned char *doom_status_glyph(char letter)
{
    static const struct { char letter; unsigned char columns[5]; } glyphs[] = {
        {'0',{0x3e,0x51,0x49,0x45,0x3e}}, {'1',{0x00,0x42,0x7f,0x40,0x00}},
        {'2',{0x42,0x61,0x51,0x49,0x46}}, {'3',{0x21,0x41,0x45,0x4b,0x31}},
        {'4',{0x18,0x14,0x12,0x7f,0x10}}, {'5',{0x27,0x45,0x45,0x45,0x39}},
        {'6',{0x3c,0x4a,0x49,0x49,0x30}}, {'7',{0x01,0x71,0x09,0x05,0x03}},
        {'8',{0x36,0x49,0x49,0x49,0x36}}, {'9',{0x06,0x49,0x49,0x29,0x1e}},
        {'A',{0x7e,0x11,0x11,0x11,0x7e}}, {'B',{0x7f,0x49,0x49,0x49,0x36}},
        {'C',{0x3e,0x41,0x41,0x41,0x22}}, {'D',{0x7f,0x41,0x41,0x22,0x1c}},
        {'E',{0x7f,0x49,0x49,0x49,0x41}}, {'F',{0x7f,0x09,0x09,0x09,0x01}},
        {'L',{0x7f,0x40,0x40,0x40,0x40}},
        {'M',{0x7f,0x02,0x0c,0x02,0x7f}}, {'O',{0x3e,0x41,0x41,0x41,0x3e}},
        {'P',{0x7f,0x09,0x09,0x09,0x06}}, {'R',{0x7f,0x09,0x19,0x29,0x46}},
        {'S',{0x46,0x49,0x49,0x49,0x31}}, {'T',{0x01,0x01,0x7f,0x01,0x01}},
        {'W',{0x3f,0x40,0x38,0x40,0x3f}}, {' ',{0,0,0,0,0}}
    };
    for (unsigned int i = 0; i < sizeof(glyphs) / sizeof(glyphs[0]); ++i)
        if (glyphs[i].letter == letter) return glyphs[i].columns;
    return glyphs[sizeof(glyphs) / sizeof(glyphs[0]) - 1].columns;
}
static inline void doom_status_line(unsigned char *frame, unsigned int page, const char *text)
{
    unsigned int x = 4;
    while (*text && x + 5 <= 128) {
        const unsigned char *glyph = doom_status_glyph(*text++);
        for (unsigned int col = 0; col < 5; ++col) frame[page * 128 + x++] = glyph[col];
        ++x;
    }
}
static inline void doom_status_send(const unsigned char *frame)
{
    volatile unsigned char *lcd = (volatile unsigned char *)0xC031B310u;
    for (unsigned int i = 0; i < 1024; ++i) lcd[i] = frame[i];
    ((void (*)(void *, int, int))0xC0015DD0u)((void *)0xC031BB2Cu, 2, 0);
    ((void (*)(void *, int, int))0xC0015DD0u)((void *)0xC031BB2Cu, 3, 0);
}
/* While the engine reads the WAD before its first frame: DOOM, LADE WAD and the megabytes read, a bar of read / size. */
static inline void doom_status_loading(uint32_t read, uint32_t size)
{
    unsigned char frame[1024];
    char line[16] = "LADE WAD ";
    unsigned int n = 9, mb = read >> 20, fill = size ? (unsigned int)((uint64_t)read * 118 / size) : 0;
    for (unsigned int i = 0; i < sizeof(frame); ++i) frame[i] = 0;
    if (mb >= 10) line[n++] = (char)('0' + mb / 10 % 10);
    line[n++] = (char)('0' + mb % 10);
    line[n++] = ' '; line[n++] = 'M'; line[n++] = 'B'; line[n] = 0;
    doom_status_line(frame, 1, "DOOM");
    doom_status_line(frame, 3, line);
    if (fill > 118) fill = 118;
    for (unsigned int x = 4; x < 124; ++x) frame[5 * 128 + x] = (x == 4 || x == 123) ? 0x7e : (x - 5 < fill ? 0x7e : 0x42);
    doom_status_send(frame);
}
static inline void doom_status_display(const char *title, const char *detail, uint32_t code, int show_code)
{
    unsigned char frame[1024];
    for (unsigned int i = 0; i < sizeof(frame); ++i) frame[i] = 0;
    doom_status_line(frame, 1, title);
    doom_status_line(frame, 3, detail);
    if (show_code) {
        char digits[9];
        static const char hex[] = "0123456789ABCDEF";
        for (unsigned int i = 0; i < 8; ++i) digits[i] = hex[(code >> (28 - i * 4)) & 15];
        digits[8] = 0;
        doom_status_line(frame, 5, digits);
    }
    doom_status_send(frame);
}
#endif
