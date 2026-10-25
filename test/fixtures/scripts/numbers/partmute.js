// Part Mute on PART ERASE, for an Electribe whose PART MUTE key no longer works: PART ERASE reaches the firmware as
// PART MUTE, so the pads mute parts the way the firmware does it. PART ERASE's own pad mode and SHIFT + PART ERASE are not
// there while the plugin runs. The firmware lights the broken key's LED; the PART ERASE LED shows the mute mode instead.
korg.remapKey(17, 16);
const OTHER_MODES = [19, 21, 23, 24, 25, 27];
let muting = 0;
let ticks = 0;

function show() {
  korg.led(33, muting ? 255 : 0);
}

// The pad modes are one choice: PART MUTE is on until another mode key is pressed.
korg.onEvent("buttonPress", (key) => {
  if (key == 16) muting = 1;
  for (let i = 0; i < OTHER_MODES.length; i++) {
    if (key == OTHER_MODES[i]) muting = 0;
  }
  show();
});

// The firmware sends its own LED states now and then, so the LED is set again twice a second.
korg.onEvent("frame", () => {
  ticks += 1;
  if (ticks >= 12) {
    ticks = 0;
    show();
  }
});
