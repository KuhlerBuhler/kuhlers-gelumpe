/* SPDX-License-Identifier: AGPL-3.0-or-later */
#ifndef GELUMPE_DOOM_RUNTIME_ABI_H
#define GELUMPE_DOOM_RUNTIME_ABI_H
#include <stdint.h>
#define DOOM_ENGINE_BASE 0xC1000000u
#define DOOM_ENGINE_END 0xC1800000u
#define DOOM_STACK_BYTES 65536u
#define DOOM_SHARED_ADDRESS 0xC017F000u
#define DOOM_BOOT_MAGIC 0x4D4F4F44u
#define DOOM_BOOT_VERSION 1u
#define DOOM_WAD_PATH "SD:/KORG/blechtribe/Doom/doom.wad"
#define DOOM_PROGRAM_PATH "SD:/KORG/blechtribe/Doom/doom.bin"
#define DOOM_STAGE_SELECTED 1u
#define DOOM_STAGE_MOUNTED 2u
#define DOOM_STAGE_VERIFIED 3u
#define DOOM_STAGE_ENGINE 4u
#define DOOM_STAGE_PLAYING 5u
#define DOOM_STAGE_STOPPED 6u
#define DOOM_STAGE_ERROR 0x80000000u
struct doom_shared {
    uint32_t magic, version, stage, error;
    uint32_t frames, gametic, gamestate, viewangle;
    uint32_t file_reads, bytes_read, heap_used, key_events;
    uint32_t last_key, last_down, console_head, exit_status;
    uint32_t clock_millis;
    char console[2048];
};
#endif
