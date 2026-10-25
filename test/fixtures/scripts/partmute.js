// Part Mute on PART ERASE, for an Electribe whose PART MUTE key no longer works: PART ERASE reaches the firmware as
// PART MUTE, so the pads mute parts the way the firmware does it. PART ERASE's own pad mode and SHIFT + PART ERASE are not
// there while the plugin runs. The firmware lights the broken key's LED; the PART ERASE LED shows the mute mode instead.
korg.remapKey(korg.key.PART_ERASE, korg.key.PART_MUTE);
const OTHER_MODES = [korg.key.TRIGGER, korg.key.SEQUENCER, korg.key.KEYBOARD, korg.key.CHORD, korg.key.STEP_JUMP, korg.key.PATTERN_SET];
let muting = 0;
let ticks = 0;

function show() {
  korg.led(korg.led.PART_ERASE, muting ? 255 : 0);
}

// The pad modes are one choice: PART MUTE is on until another mode key is pressed.
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.PART_MUTE) muting = 1;
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
