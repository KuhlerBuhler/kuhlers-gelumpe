// Gate Hold (idea 72): in Gate Arp mode the note stays where the finger first touched, and moving the finger along X picks
// the Gate Arp rhythm of the pattern (the Pattern menu's GATE ARP, 0 to 49, left to right). Y stays the firmware's. Letting
// go of the touchpad puts back the rhythm the pattern had, so nothing changes unsaved. The touchpad mode is the firmware's
// and stays on until another mode key comes (measured in the emulator): GATE ARP sets Gate Arp, MASTER FX and TOUCH SCALE
// leave it, with SHIFT GATE ARP and MASTER FX open their menu pages and keep the mode. The plugin follows those keys and only
// holds the touch X (korg.touchLockX) in Gate Arp mode. The page GATE HOLD in the BLECH menu switches it on (1) and off (0).
const GATE_ARP = 11;
let on = korg.store.get(0, 1);
let page = korg.menu.add("GATE HOLD", 0, 1, on);
let gate = 0;
let shift = 0;
let holding = 0;
let base = 0;
let rhythm = -1;

function letGo() {
  if (!holding) return;
  if (rhythm >= 0 && rhythm != base) korg.seq.setPatternValue(GATE_ARP, base);
  korg.touchLockX(-1);
  holding = 0;
}

korg.onEvent("buttonPress", (key) => {
  if (key == 10) shift = 1;
  if (key == 4 && !shift) gate = 1;
  if (key == 6 && !shift) gate = 0;
  if (key == 5) gate = 0;
  if (!gate) letGo();
});

korg.onEvent("buttonRelease", (key) => {
  if (key == 10) shift = 0;
  if (key == 34) letGo();
});

// The first position plays the note and fixes it (the firmware counts X in 128 steps), the ones after pick the rhythm.
korg.onEvent("touch", (x, y, first) => {
  if (!on || !gate) return;
  if (first || !holding) {
    letGo();
    base = korg.current.gateArp;
    rhythm = -1;
    korg.touchLockX(x >> 3);
    holding = 1;
    return;
  }
  const r = (x * 50) >> 10;
  if (r == rhythm) return;
  rhythm = r;
  korg.seq.setPatternValue(GATE_ARP, r);
});

// A new pattern brings its own rhythm: that one comes back on release.
korg.onEvent("patternChange", () => {
  if (!holding) return;
  base = korg.current.gateArp;
  rhythm = -1;
});

korg.onEvent("menu", (id, value) => {
  if (id != page) return;
  on = value;
  korg.store.set(0, on);
  korg.store.save();
  if (!on) letGo();
});
