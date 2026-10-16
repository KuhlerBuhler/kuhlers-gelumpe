/* SPDX-License-Identifier: AGPL-3.0-or-later */
#ifndef GELUMPE_DOOM_SHA256_H
#define GELUMPE_DOOM_SHA256_H
#include <stddef.h>
#include <stdint.h>
struct sha256 { uint32_t h[8]; uint64_t bytes; unsigned int used; unsigned char block[64]; };
void sha256_init(struct sha256 *s);
void sha256_add(struct sha256 *s, const void *data, size_t length);
void sha256_finish(struct sha256 *s, unsigned char digest[32]);
#endif
