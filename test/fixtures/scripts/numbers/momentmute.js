// Momentary Mute, a wish from the community: mutes change only while PART MUTE is held. PART MUTE held, a pad switches its
// part on or off and the pads show the mutes; PART MUTE released, the pads trigger as in TRIGGER mode. All of it is the
// firmware's: PART MUTE switches the pad mode on its press and keeps it after the release (measured in the emulator), so
// the plugin only presses TRIGGER for the firmware when PART MUTE comes up (korg.pressKey). SHIFT + PART MUTE stays the
// firmware's, and another mode key pressed while PART MUTE is held keeps its mode. The page MOMENT MUTE in the BLECH menu
// switches it on (1) and off (0: PART MUTE stays a mode as without the plugin).
const MODES = [17, 19, 21, 23, 24, 25, 27];
let on = korg.store.get(0, 1);
let page = korg.menu.add("MOMENT MUTE", 0, 1, on);
let shift = 0;
let held = 0;

korg.onEvent("buttonPress", (key) => {
  if (key == 10) shift = 1;
  if (key == 16) held = on && !shift ? 1 : 0;
  for (let i = 0; i < MODES.length; i++) {
    if (key == MODES[i]) held = 0;
  }
});

korg.onEvent("buttonRelease", (key) => {
  if (key == 10) shift = 0;
  if (key != 16 || !held) return;
  held = 0;
  if (on) korg.pressKey(19);
});

korg.onEvent("menu", (id, value) => {
  if (id != page) return;
  on = value;
  korg.store.set(0, on);
  korg.store.save();
});
