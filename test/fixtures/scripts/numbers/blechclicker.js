// BLECH Clicker, an app under GAMES: a crystal in the middle, the number of pad presses below it. Every pad press
// while the app is open adds one and shakes the crystal, korg.store keeps the count over power off. The crystal is one
// bitmap of 40 x 40 pixels (5 bands of 40 columns), the screen is only drawn again when something changed.
korg.app("BLECH Clicker", "GAMES");
const GEM = [0,0,0,0,0,0,128,192,32,24,12,116,132,4,4,4,4,132,100,28,28,100,132,4,4,4,4,132,244,28,24,48,192,128,0,0,0,0,0,0,0,192,224,88,76,66,65,192,192,64,64,64,67,92,224,120,78,67,64,64,64,64,67,78,120,224,124,199,64,192,64,192,192,193,67,204,88,240,192,0,0,0,1,3,12,24,48,64,131,14,56,224,128,0,1,62,224,0,0,0,0,0,0,224,126,171,85,170,245,186,95,171,85,58,25,12,3,1,0,0,0,0,0,0,0,0,0,0,1,3,4,24,51,102,152,96,131,62,192,0,0,192,126,171,117,186,119,51,25,4,3,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,3,7,14,63,124,124,63,15,7,3,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0];
let count = korg.store.get(0, 0);
let shake = 0;
let dirty = 1;
let isOpen = 0;

function digits(n) {
  let d = 1;
  while (n >= 10) {
    n = n / 10;
    d += 1;
  }
  return d;
}

function draw() {
  let x = 44;
  if (shake > 0) x += shake & 1 ? 2 : -2;
  korg.display.clear();
  korg.display.bitmap(GEM, x, 4, 40);
  korg.display.number(count, 64 - digits(count) * 3, 50);
}

korg.onEvent("open", () => {
  isOpen = 1;
  shake = 0;
  draw();
});

korg.onEvent("close", () => {
  isOpen = 0;
});

korg.onEvent("pad", (index, down) => {
  if (!isOpen || !down) return;
  count += 1;
  korg.store.set(0, count);
  korg.store.save();
  shake = 4;
  dirty = 1;
});

korg.onEvent("frame", () => {
  if (shake > 0) {
    shake -= 1;
    dirty = 1;
  }
  if (dirty) {
    dirty = 0;
    draw();
  }
});
