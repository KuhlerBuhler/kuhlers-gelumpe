// Lauflicht: ein rotes Pad-Licht wandert über die 16 Pads.
const FIRST_RED_PAD = 44;
let pos = 0;
let ticks = 0;

korg.onEvent("ready", () => korg.led(FIRST_RED_PAD, 255));

korg.onEvent("frame", () => {
  ticks += 1;
  if (ticks >= 2) {
    ticks = 0;
    korg.led(FIRST_RED_PAD + pos * 2, 0);
    pos = (pos + 1) % 16;
    korg.led(FIRST_RED_PAD + pos * 2, 255);
  }
});
