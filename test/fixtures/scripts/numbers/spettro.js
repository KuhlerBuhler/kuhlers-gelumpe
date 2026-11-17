// Spettro, an app under TOOLS: the spectrum of the selected part, 64 bars from 20 Hz to 20 kHz (BAR 2: 20 Hz to 2 kHz),
// 0 to 96 dB. The firmware's capture service computes it (korg.audio.capture and korg.audio.spectrum, API 31); capture,
// FFT and the first Spettro are by Luigi (GitHub reflectiveboi, PR #429). BAR 1 holds the picture. Sampler only: on the
// blue Electribe the app says so.
korg.app("Spettro", "TOOLS");
const bins = new Array(64);
let opened = 0;
let hold = 0;
let bass = 0;

korg.onEvent("open", () => { opened = 1; hold = 0; });
korg.onEvent("close", () => { opened = 0; korg.audio.capture(0); });

korg.onEvent("buttonPress", (key) => {
  if (!opened) return;
  if (key == 28) hold = 1 - hold;
  if (key == 29) bass = 1 - bass;
});

korg.onEvent("frame", () => {
  if (!opened) return;
  const status = korg.audio.capture(korg.read.part() + 1);
  if (hold && status == 0) return;
  korg.display.clear();
  korg.display.text("PART", 0, 0);
  korg.display.number(korg.read.part() + 1, 26, 0);
  if (hold) korg.display.text("HOLD", 100, 0);
  korg.display.text("20", 0, 57);
  if (bass) korg.display.text("2k", 116, 57);
  else korg.display.text("20k", 110, 57);
  if (status == 2) korg.display.text("CAPTURE BUSY", 16, 27);
  if (status == 3) korg.display.text("WAIT", 16, 27);
  if (status == 4) korg.display.text("GAP", 16, 27);
  if (status == 5) korg.display.text("NO MEMORY", 16, 27);
  if (status == 6) korg.display.text("NOT ON THIS UNIT", 16, 27);
  if (status != 0) return;
  korg.audio.spectrum(bins, 64, bass);
  for (let i = 0; i < 64; i++) {
    const h = bins[i] >> 1;
    if (h > 0) korg.display.rect(i * 2, 56 - h, 1, h);
  }
});
