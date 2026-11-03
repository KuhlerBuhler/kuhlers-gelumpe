// Momentary Mute, a wish from the community: like on the Korg ESX, a pad in PART MUTE mode changes its part only while it
// is held. The press flips the part (a playing part goes quiet, a muted one plays), the release puts it back. PART MUTE is
// a pad mode of the firmware that stays on until another mode key is pressed; the plugin follows the mode keys and keeps
// the pads from the firmware (korg.padHold) only in that mode and only while SHIFT is up, so every other mode and
// SHIFT + pad stay the firmware's. The page MOMENT MUTE in the BLECH menu switches it on (1) and off (0: the pads latch
// as without the plugin).
const OTHER_MODES = [17, 19, 21, 23, 24, 25, 27];
// Per pad: 0 not held by the plugin, 1 held and the part played before, 2 held and the part was muted before.
const held = new Array(16);
let on = korg.store.get(0, 1);
let page = korg.menu.add("MOMENT MUTE", 0, 1, on);
let muting = 0;
let shift = 0;

function active() {
  return on && muting && !shift ? 1 : 0;
}

korg.onEvent("buttonPress", (key) => {
  if (key == 10) shift = 1;
  if (key == 16) muting = 1;
  for (let i = 0; i < OTHER_MODES.length; i++) {
    if (key == OTHER_MODES[i]) muting = 0;
  }
  korg.padHold(active());
});

korg.onEvent("buttonRelease", (key) => {
  if (key == 10) shift = 0;
  korg.padHold(active());
});

// A release follows its press, so a pad the plugin held comes back here even when the mode changed meanwhile.
korg.onEvent("pad", (index, down) => {
  if (down) {
    if (!active() || held[index]) return;
    const was = korg.parts[index].muted;
    held[index] = was + 1;
    korg.parts[index].muted = 1 - was;
  } else if (held[index]) {
    korg.parts[index].muted = held[index] - 1;
    held[index] = 0;
  }
});

// Closing an app gives the pads back to the firmware, so the hold is set again each frame.
korg.onEvent("frame", () => {
  korg.padHold(active());
});

korg.onEvent("menu", (id, value) => {
  if (id != page) return;
  on = value;
  korg.store.set(0, on);
  korg.store.save();
  korg.padHold(active());
});
