// Pulsieren: alle roten Pad-LEDs werden im Dreieck heller und dunkler.
const FIRST_RED_PAD = 44;
let phase = 0;

korg.onEvent("frame", () => {
  phase = (phase + 8) % 512;
  const level = phase < 256 ? phase : 511 - phase;
  for (let pad = 0; pad < 16; pad++) korg.led(FIRST_RED_PAD + pad * 2, level);
});
