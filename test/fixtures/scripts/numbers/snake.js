// Snake on a 16 x 8 grid of 8 x 8 pixel cells, an app under GAMES: it opens from the BLECH menu, starts anew
// on every open and leaves with EXIT. The body is a ring buffer, `cell` marks occupied cells.
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
let fx = 10;
let fy = 4;
let score = 0;
let seed = 12345;
let frames = 0;

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
  score = 0;
  head = MAXLEN - 1;
  put(0, 0);
  put(1, 0);
  put(2, 0);
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

korg.onEvent("buttonPress", (key) => {
  if (key == 11) dir = (dir + 3) % 4;
  if (key == 15) dir = (dir + 1) % 4;
});

korg.onEvent("frame", () => {
  frames += 1;
  if (frames >= 3) {
    frames = 0;
    step();
  }
  draw();
});
