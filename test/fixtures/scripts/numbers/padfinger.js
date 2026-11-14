korg.app("Pad Finger", "TOOLS");
// PAD FINGER (Touch Pad Tester) by nic0crank, from the BLECH Discord: shows the touchpad X and Y (raw, 0 to 1023) and
// a crosshair where the finger is. TAP switches LOCK and FREE: with LOCK the firmware sees the X where the finger landed
// (korg.touchLockX), Y stays the finger's; lifting the finger, FREE or closing the app lets go.

let isOpen = 0;
let touching = 0;
let locked = 0;
let lock = 1;
let rx = 0;
let ry = 0;
let px = 0;
let py = 0;
let dirty = 1;

function release() {
  if (locked) {
    korg.touchLockX(-1);
    locked = 0;
  }
  touching = 0;
  dirty = 1;
}

function draw() {
  korg.display.clear();
  if (touching) {
    korg.display.rect(0, py, 128, 1);
    korg.display.rect(px, 0, 1, 64);
  }
  korg.display.clearRect(0, 0, 48, 16);
  korg.display.textNumber("X ", rx, 0, 0);
  korg.display.textNumber("Y ", ry, 0, 8);
  korg.display.clearRect(98, 0, 30, 8);
  if (lock) korg.display.text("LOCK", 100, 0);
  else korg.display.text("FREE", 100, 0);
}

korg.onEvent("open", () => {
  isOpen = 1;
  dirty = 1;
});

korg.onEvent("close", () => {
  isOpen = 0;
  release();
});

korg.onEvent("buttonPress", (key) => {
  if (!isOpen) return;
  if (key == 3) {
    lock = 1 - lock;
    if (!lock) release();
    dirty = 1;
  }
});

korg.onEvent("buttonRelease", (key) => {
  if (key == 34) release();
});

// Pad X/Y run 0-1023, Y counts upward: 1023 / 8 = 127 columns, 1023 / 16 = 63 rows.
korg.onEvent("touch", (x, y, first) => {
  if (!isOpen) return;
  rx = x;
  ry = y;
  px = x >> 3;
  if (px > 127) px = 127;
  py = 63 - (y >> 4);
  if (py < 0) py = 0;
  if (py > 63) py = 63;
  if (first || !touching) {
    touching = 1;
    if (lock) {
      korg.touchLockX(px);
      locked = 1;
    }
  }
  dirty = 1;
});

korg.onEvent("frame", () => {
  if (!dirty) return;
  dirty = 0;
  draw();
});
