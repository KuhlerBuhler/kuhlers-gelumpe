// Experimental spectrum companion; native worker is required.
korg.app("SPETTRO", "TOOLS");
let opened = 0;
let freeze = 0;
let shift = 11;
let bass = 0;
function requests() {
  korg.store.set(0, freeze);
  korg.store.set(1, shift);
  korg.store.set(3, bass);
}
korg.onEvent("open", () => {
  opened = 1;
  freeze = 0;
  requests();
  korg.store.set(4, 3);
  korg.store.set(2, 0);
});
korg.onEvent("close", () => { opened = 0; });
korg.onEvent("buttonPress", (key) => {
  if (!opened) return;
  if (key == korg.key.BAR_1) freeze = 1 - freeze;
  if (key == korg.key.BAR_2) bass = 1 - bass;
  if (key == korg.key.BAR_3 && shift > 9) shift -= 1;
  if (key == korg.key.BAR_4 && shift < 15) shift += 1;
  requests();
});
korg.onEvent("frame", () => {
  if (!opened) return;
  korg.display.clear();
  korg.display.text("SPETTRO", 0, 0);
  korg.display.number(korg.selectedPart + 1, 48, 0);
  korg.display.number((11 - shift) * 6, 70, 0);
  korg.display.text("dB", 90, 0);
  if (freeze) korg.display.text("H", 120, 0);
  let status = korg.store.get(4, 3);
  if (status == 2) korg.display.text("CAPTURE BUSY", 18, 27);
  if (status == 3) korg.display.text("WAIT", 48, 27);
  if (status == 4 || status == 5) korg.display.text("GAP", 48, 27);
  if (status == 7) korg.display.text("NO MEMORY", 30, 27);
  korg.display.text("20Hz", 0, 57);
  if (bass) {
    korg.display.text("200", 56, 57);
    korg.display.text("2k", 116, 57);
  }
  if (!bass) {
    korg.display.text("1k", 68, 57);
    korg.display.text("20k", 110, 57);
  }
});
