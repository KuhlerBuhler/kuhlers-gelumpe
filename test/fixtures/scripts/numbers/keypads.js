// Key Pads (idea 85): KEYBOARD held, a pad sets the KEY of the pattern, like TRANSPOSE on the old Electribes. The pads lie
// like a piano: the lower row C D E F G A B C, the upper row the black keys above them (C#, D#, F#, G#, A#); the other upper
// pads do nothing. The KEY goes through the Pattern menu's setter, so the firmware reacts as on its KEY page. KEYBOARD stays
// the plugin's (korg.keyHold): a short press without a pad goes on to the firmware on release (korg.pressKey) and switches
// to KEYBOARD mode as always; with a pad it does not. SHIFT + KEYBOARD stays the firmware's. The page KEY PADS in the BLECH
// menu switches it on (1) and off (0).
const KEY = 4;
// Per pad the KEY it sets, -1 none. Pads 1 to 8 are the upper row.
const NOTES = [-1, 1, 3, -1, 6, 8, 10, -1, 0, 2, 4, 5, 7, 9, 11, 0];
let on = korg.store.get(0, 1);
let page = korg.menu.add("KEY PADS", 0, 1, on);
let shift = 0;
let held = 0;
let used = 0;

function hold() {
  korg.keyHold(23, on && !shift ? 1 : 0);
}

korg.onEvent("ready", hold);

korg.onEvent("buttonPress", (key) => {
  if (key == 10) { shift = 1; hold(); }
  if (key != 23 || !on || shift) return;
  held = 1;
  used = 0;
  korg.padHold(1);
});

korg.onEvent("buttonRelease", (key) => {
  if (key == 10) { shift = 0; hold(); }
  if (key != 23 || !held) return;
  held = 0;
  korg.padHold(0);
  if (!used) korg.pressKey(23);
});

korg.onEvent("pad", (index, down) => {
  if (!held || !down) return;
  used = 1;
  if (NOTES[index] >= 0) korg.seq.setPatternValue(KEY, NOTES[index]);
});

// Closing an app gives the pads back to the firmware, so the hold is set again each frame while KEYBOARD is down.
korg.onEvent("frame", () => {
  if (held) korg.padHold(1);
});

korg.onEvent("menu", (id, value) => {
  if (id != page) return;
  on = value;
  korg.store.set(0, on);
  korg.store.save();
  hold();
});
