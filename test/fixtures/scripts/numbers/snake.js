// Snake on a 16 x 8 grid of 8 x 8 pixel cells, an app under GAMES: it opens from the BLECH menu, starts anew
// on every open and leaves with EXIT. The body is a ring buffer, `cell` marks occupied cells. A tap on the
// touchpad steers: above, below, left or right of its centre is the new direction, never straight back. PART left
// and right turn it left and right. It starts at one cell every 6 frames (about 4 a second) and gets a frame
// faster with every fourth food, down to every 3 frames.
korg.app("Snake", "GAMES");
const W = 16;
const H = 8;
const MAXLEN = 32;
const bx = new Array(MAXLEN);
const by = new Array(MAXLEN);
const cell = new Array(W * H);
let head = 0;
let tail = 0;
let len = 3;
let dir = 0;
let moved = 0;
let fx = 12;
let fy = 2;
let score = 0;
let seed = 12345;
let frames = 0;
let speed = 6;

function rnd() {
  seed = seed * 1103515245 + 12345;
  return (seed >> 16) & 0x7fff;
}

function put(x, y) {
  head = (head + 1) % MAXLEN;
  bx[head] = x;
  by[head] = y;
  cell[y * W + x] = 1;
}

function reset() {
  for (let i = 0; i < W * H; i++) cell[i] = 0;
  tail = 0;
  len = 3;
  dir = 0;
  moved = 0;
  score = 0;
  speed = 6;
  head = MAXLEN - 1;
  put(5, 4);
  put(6, 4);
  put(7, 4);
}

function newFood() {
  fx = rnd() % W;
  fy = rnd() % H;
  while (cell[fy * W + fx]) {
    fx = (fx + 1) % W;
    if (fx == 0) fy = (fy + 1) % H;
  }
}

function step() {
  let nx = bx[head];
  let ny = by[head];
  if (dir == 0) nx = (nx + 1) % W;
  else if (dir == 1) ny = (ny + 1) % H;
  else if (dir == 2) nx = (nx + W - 1) % W;
  else ny = (ny + H - 1) % H;
  moved = dir;
  const eat = nx == fx && ny == fy;
  if (!eat) {
    cell[by[tail] * W + bx[tail]] = 0;
    tail = (tail + 1) % MAXLEN;
  }
  if (cell[ny * W + nx]) {
    reset();
    return;
  }
  put(nx, ny);
  if (eat) {
    len += 1;
    score += 1;
    if (score % 4 == 0 && speed > 3) speed -= 1;
    newFood();
  }
}

function draw() {
  korg.display.clear();
  let k = tail;
  for (let i = 0; i < len; i++) {
    korg.display.rect(bx[k] * 8, by[k] * 8, 8, 8);
    k = (k + 1) % MAXLEN;
  }
  korg.display.rect(fx * 8 + 2, fy * 8 + 2, 4, 4);
}

korg.onEvent("open", () => {
  reset();
  frames = 0;
  draw();
});

korg.onEvent("touch", (x, y, first) => {
  if (!first) return;
  // distances from the centre without negative numbers
  let ax = 512 - x;
  if (x > 512) ax = x - 512;
  let ay = 512 - y;
  if (y > 512) ay = y - 512;
  let want = 1;
  if (ax > ay) {
    want = 2;
    if (x > 512) want = 0;
  } else if (y > 512) {
    want = 3;
  }
  // never straight back over the last step, also with two taps between steps
  if ((want + 2) % 4 != moved) dir = want;
});

// PART left and right: a quarter turn from the direction of the last step
korg.onEvent("buttonPress", (key) => {
  if (key == 11) dir = (moved + 3) % 4;
  if (key == 15) dir = (moved + 1) % 4;
});

korg.onEvent("frame", () => {
  frames += 1;
  if (frames >= speed) {
    frames = 0;
    step();
  }
  draw();
});
