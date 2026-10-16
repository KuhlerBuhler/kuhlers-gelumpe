/* SPDX-License-Identifier: AGPL-3.0-or-later */
#include <stddef.h>
#include <stdint.h>
#include "d_player.h"

__attribute__((used, section(".doom_layout")))
const uint32_t doom_layout[] = {
    1,
    sizeof(player_t),
    offsetof(player_t, mo),
    offsetof(player_t, ammo),
    offsetof(player_t, readyweapon),
    offsetof(player_t, health),
    offsetof(mobj_t, x),
    offsetof(mobj_t, y),
    sizeof(((player_t *)0)->ammo[0]),
    offsetof(player_t, usedown),
    sizeof(((player_t *)0)->readyweapon),
    sizeof(((player_t *)0)->usedown),
    sizeof(boolean)
};
