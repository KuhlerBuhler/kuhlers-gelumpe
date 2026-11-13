/**
 * The catalog of plugins, also the starting points of the plugins page. Each entry carries its category, who made it,
 * when it came in and what its keys do; a new plugin comes in by pull request on GitHub with its entry here. Snake is
 * the reference script the tests run (test/fixtures/scripts); a test keeps the source here equal to that file.
 */
import { text } from "../../src/text.mjs";
export const PRESETS = Object.freeze([
  Object.freeze({
    id: "blechclicker",
    title: "BLECH Clicker",
    description: text("catalog.blechclicker.description"),
    category: text("catalog.category.games"),
    creator: "Kuhler Buhler",
    added: "2026-10-16",
    controls: [text("catalog.blechclicker.control1")],
    source: `// BLECH Clicker, an app under GAMES: a crystal in the middle, the number of pad presses below it. Every pad press
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
`,
  }),
  Object.freeze({
    id: "settimer",
    title: "Set-Timer",
    description: text("catalog.settimer.description"),
    category: text("catalog.category.tools"),
    creator: "Kuhler Buhler",
    added: "2026-10-16",
    controls: [text("catalog.settimer.control1"), text("catalog.settimer.control2")],
    source: `// Set timer, an app under TOOLS: big mm:ss (h:mm:ss from one hour on) for how long the set has run.
// The first PLAY or key 1 starts it, then it only counts: PLAY and STOP change nothing, key 4 resets after a second press.
// The clock is korg.millis(), so it keeps counting with the app closed; closed, the app only reacts to \`play\` and keys.
korg.app("Set-Timer", "TOOLS");
// segments a b c d e f g as bits 0 to 6, one entry per digit
const SEG = [63, 6, 91, 79, 102, 109, 125, 7, 127, 111];
const DW = 16;
const DH = 32;
const DX = new Array(5);
const shown = new Array(5);
let started = 0;
let t0 = 0;
let confirmUntil = 0;
let isOpen = 0;
let longMode = 0;
let status = -1;

function drawDigit(slot, d) {
  const x = DX[slot];
  const m = SEG[d];
  korg.display.clearRect(x, 16, DW, DH);
  if (m & 1) korg.display.rect(x, 16, DW, 3);
  if (m & 2) korg.display.rect(x + DW - 3, 19, 3, 11);
  if (m & 4) korg.display.rect(x + DW - 3, 33, 3, 12);
  if (m & 8) korg.display.rect(x, 45, DW, 3);
  if (m & 16) korg.display.rect(x, 33, 3, 12);
  if (m & 32) korg.display.rect(x, 19, 3, 11);
  if (m & 64) korg.display.rect(x + 3, 30, DW - 6, 3);
}

function colon(x) {
  korg.display.rect(x, 24, 3, 3);
  korg.display.rect(x, 37, 3, 3);
}

function layout() {
  korg.display.clearRect(0, 16, 128, DH);
  if (longMode) {
    DX[0] = 11;
    DX[1] = 36;
    DX[2] = 56;
    DX[3] = 81;
    DX[4] = 101;
    colon(30);
    colon(75);
  } else {
    DX[1] = 22;
    DX[2] = 42;
    DX[3] = 70;
    DX[4] = 90;
    colon(62);
  }
  for (let i = 0; i < 5; i++) shown[i] = -1;
}

function elapsed() {
  if (!started) return 0;
  return (korg.millis() - t0) / 1000;
}

function showTime() {
  const secs = elapsed();
  const h = (secs / 3600) % 10;
  const m = (secs / 60) % 60;
  const s = secs % 60;
  const wantLong = secs >= 3600 ? 1 : 0;
  if (wantLong != longMode) {
    longMode = wantLong;
    layout();
  }
  const d0 = h;
  const d1 = m / 10;
  const d2 = m % 10;
  const d3 = s / 10;
  const d4 = s % 10;
  if (longMode && shown[0] != d0) { shown[0] = d0; drawDigit(0, d0); }
  if (shown[1] != d1) { shown[1] = d1; drawDigit(1, d1); }
  if (shown[2] != d2) { shown[2] = d2; drawDigit(2, d2); }
  if (shown[3] != d3) { shown[3] = d3; drawDigit(3, d3); }
  if (shown[4] != d4) { shown[4] = d4; drawDigit(4, d4); }
}

// 0 waiting for the start, 1 running, 2 reset asked
function wantStatus() {
  if (!started) return 0;
  if (confirmUntil > 0) return 2;
  return 1;
}

function showStatus() {
  const s = wantStatus();
  if (s == status) return;
  status = s;
  korg.display.clearRect(84, 0, 44, 10);
  korg.display.clearRect(0, 53, 128, 11);
  if (s == 0) {
    korg.display.text("WAIT", 101, 2);
    korg.display.text("PLAY OR KEY 1 STARTS", 4, 55);
  } else if (s == 1) {
    korg.display.text("RUN", 107, 2);
    korg.display.text("KEY 4 = RESET", 4, 55);
  } else {
    korg.display.text("RESET?", 89, 2);
    korg.display.text("KEY 4 AGAIN = RESET", 4, 55);
  }
}

function start() {
  if (started) return;
  started = 1;
  t0 = korg.millis();
}

korg.onEvent("open", () => {
  isOpen = 1;
  if (confirmUntil > 0 && korg.millis() > confirmUntil) confirmUntil = 0;
  korg.display.clear();
  korg.display.text("SET TIMER", 4, 2);
  status = -1;
  layout();
});

korg.onEvent("close", () => {
  isOpen = 0;
});

korg.onEvent("play", () => start());

korg.onEvent("buttonPress", (key) => {
  if (!isOpen) return;
  if (key == korg.key.BAR_1) start();
  if (key == korg.key.BAR_4) {
    if (confirmUntil > 0 && korg.millis() <= confirmUntil) {
      started = 0;
      confirmUntil = 0;
    } else {
      confirmUntil = korg.millis() + 3000;
    }
  }
});

korg.onEvent("frame", () => {
  if (confirmUntil > 0 && korg.millis() > confirmUntil) confirmUntil = 0;
  showStatus();
  showTime();
});
`,
  }),
  Object.freeze({
    id: "snake",
    title: "Snake",
    description: text("catalog.snake.description"),
    category: text("catalog.category.games"),
    creator: "Kuhler Buhler",
    added: "2026-10-16",
    controls: [text("catalog.snake.control1"), text("catalog.snake.control2")],
    source: `// Snake on a 16 x 8 grid of 8 x 8 pixel cells, an app under GAMES: it opens from the BLECH menu, starts anew
// on every open and leaves with EXIT. The body is a ring buffer, \`cell\` marks occupied cells. A tap on the
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
  if (key == korg.key.PART_LEFT) dir = (moved + 3) % 4;
  if (key == korg.key.PART_RIGHT) dir = (moved + 1) % 4;
});

korg.onEvent("frame", () => {
  frames += 1;
  if (frames >= speed) {
    frames = 0;
    step();
  }
  draw();
});
`,
  }),
  Object.freeze({
    id: "tetris",
    title: "Tetris",
    description: text("catalog.tetris.description"),
    category: text("catalog.category.games"),
    creator: "Kuhler Buhler",
    added: "2026-10-16",
    controls: [text("catalog.tetris.control1"), text("catalog.tetris.control2"), text("catalog.tetris.control3")],
    source: `// Tetris on a 10 x 16 board of 4 x 4 pixel cells, an app under GAMES: it opens from the BLECH menu, starts anew on
// every open and leaves with EXIT. Part left and right move the piece, Edit right turns it, Edit left drops it faster
// while it is held. A piece is a 4 x 4 mask (bit y * 4 + x), SHAPES holds the 4 rotations of 7 pieces. Only what
// changed is drawn, and a line clear is spread over several frames so that no frame gets long.
korg.app("Tetris", "GAMES");
const W = 10;
const H = 16;
const BX = 6;
const SHAPES = [
  0xf0, 0x4444, 0xf00, 0x2222,
  0x66, 0x66, 0x66, 0x66,
  0x72, 0x262, 0x270, 0x232,
  0x36, 0x462, 0x360, 0x231,
  0x63, 0x264, 0x630, 0x132,
  0x71, 0x226, 0x470, 0x322,
  0x74, 0x622, 0x170, 0x223
];
const board = new Array(W * H);
const full = new Array(H);
let kind = 0;
let nextKind = 0;
let rot = 0;
let px = 3;
let py = 0;
let score = 0;
let lines = 0;
let level = 0;
let timer = 0;
let state = 0;
let dx = 0;
let turn = 0;
let soft = 0;
let repaintTo = -1;
let repaintAt = 0;
let hud = 0;
let seed = 1;
let isOpen = 0;
let setup = 0;
let moving = 0;
let cr = 0;

function rnd() {
  seed = seed * 1103515245 + 12345;
  return (seed >> 16) & 0x7fff;
}

function cell(x, y, on) {
  if (y < 0) return;
  if (on) korg.display.rect(BX + x * 4, y * 4, 3, 3);
  else korg.display.clearRect(BX + x * 4, y * 4, 3, 3);
}

function fits(k, r, x, y) {
  const m = SHAPES[k * 4 + r];
  for (let i = 0; i < 16; i++) {
    if ((m >> i) & 1) {
      const cx = x + (i & 3);
      const cy = y + (i >> 2);
      if (cx < 0 || cx >= W || cy >= H) return 0;
      if (cy >= 0 && board[cy * W + cx]) return 0;
    }
  }
  return 1;
}

function paint(on) {
  const m = SHAPES[kind * 4 + rot];
  for (let i = 0; i < 16; i++) {
    if ((m >> i) & 1) cell(px + (i & 3), py + (i >> 2), on);
  }
}

function drawNext() {
  const m = SHAPES[nextKind * 4];
  korg.display.clearRect(100, 12, 16, 12);
  for (let i = 0; i < 16; i++) {
    if ((m >> i) & 1) korg.display.rect(100 + (i & 3) * 4, 12 + (i >> 2) * 4, 3, 3);
  }
}

function drawHud() {
  korg.display.clearRect(54, 10, 42, 7);
  korg.display.number(score, 54, 10);
  korg.display.clearRect(54, 28, 42, 7);
  korg.display.number(lines, 54, 28);
  korg.display.clearRect(54, 46, 42, 7);
  korg.display.number(level, 54, 46);
}

function drawRow(y) {
  korg.display.clearRect(BX, y * 4, W * 4, 4);
  for (let x = 0; x < W; x++) {
    if (board[y * W + x]) cell(x, y, 1);
  }
}

function newGame() {
  score = 0;
  lines = 0;
  level = 0;
  timer = 0;
  dx = 0;
  turn = 0;
  soft = 0;
  repaintTo = -1;
  moving = 0;
  nextKind = rnd() % 7;
  state = 4;
  setup = 0;
}

// The new game is set up over three frames: the board, the frame and labels, then the numbers and the first piece.
function setupStep() {
  if (setup == 0) {
    for (let i = 0; i < W * H; i++) board[i] = 0;
  } else if (setup == 1) {
    korg.display.clear();
    korg.display.rect(4, 0, 1, 64);
    korg.display.rect(47, 0, 1, 64);
    korg.display.text("SCORE", 54, 2);
    korg.display.text("LINES", 54, 20);
    korg.display.text("LEVEL", 54, 38);
    korg.display.text("NEXT", 100, 2);
  } else {
    hud = 1;
    state = 5;
  }
  setup += 1;
}

function spawn() {
  kind = nextKind;
  nextKind = rnd() % 7;
  rot = 0;
  px = 3;
  py = 0;
  drawNext();
  if (!fits(kind, rot, px, py)) {
    state = 2;
    korg.display.clearRect(54, 54, 70, 10);
    korg.display.text("GAME OVER", 54, 55);
    return;
  }
  paint(1);
}

function lock() {
  const m = SHAPES[kind * 4 + rot];
  let any = 0;
  for (let i = 0; i < 16; i++) {
    if ((m >> i) & 1) {
      const cy = py + (i >> 2);
      if (cy >= 0) board[cy * W + px + (i & 3)] = 1;
    }
  }
  for (let r = 0; r < 4; r++) {
    const y = py + r;
    if (y >= 0 && y < H) {
      full[y] = 0;
      let n = 0;
      for (let x = 0; x < W; x++) n += board[y * W + x];
      if (n == W) {
        full[y] = 1;
        any = 1;
      }
    }
  }
  if (any) {
    state = 3;
    repaintTo = -1;
  } else {
    state = 5;
  }
}

// Removes the topmost full row: the rows above it move down one by one, a few per frame.
function collapse() {
  if (!moving) {
    let r = 0;
    while (r < H && !full[r]) r += 1;
    if (r >= H) {
      state = 1;
      repaintAt = 0;
      return;
    }
    full[r] = 0;
    moving = 1;
    cr = r;
    if (r > repaintTo) repaintTo = r;
    lines += 1;
    score += 10 * (level + 1);
    level = lines / 10;
    hud = 1;
    return;
  }
  for (let n = 0; n < 4; n++) {
    if (cr > 0) {
      for (let x = 0; x < W; x++) board[cr * W + x] = board[(cr - 1) * W + x];
      cr -= 1;
    } else {
      for (let x = 0; x < W; x++) board[x] = 0;
      moving = 0;
      break;
    }
  }
}

function step() {
  const moved = dx != 0 || turn;
  if (moved) {
    paint(0);
    if (turn) {
      const r2 = (rot + 1) & 3;
      if (fits(kind, r2, px, py)) rot = r2;
      else if (fits(kind, r2, px - 1, py)) {
        rot = r2;
        px -= 1;
      } else if (fits(kind, r2, px + 1, py)) {
        rot = r2;
        px += 1;
      }
    }
    if (dx != 0 && fits(kind, rot, px + dx, py)) px += dx;
    paint(1);
    dx = 0;
    turn = 0;
  }
  timer += 1;
  let limit = 20 - level * 2;
  if (limit < 3) limit = 3;
  if (soft) limit = 2;
  if (timer >= limit && !moved) {
    timer = 0;
    if (fits(kind, rot, px, py + 1)) {
      paint(0);
      py += 1;
      paint(1);
      if (soft) score += 1;
    } else {
      lock();
    }
  }
}

korg.onEvent("open", () => {
  isOpen = 1;
  seed = korg.millis() + 7;
  newGame();
});

korg.onEvent("close", () => {
  isOpen = 0;
  soft = 0;
});

korg.onEvent("buttonPress", (key) => {
  if (!isOpen) return;
  if (state == 2) {
    newGame();
    return;
  }
  if (key == korg.key.PART_LEFT) dx = -1;
  if (key == korg.key.PART_RIGHT) dx = 1;
  if (key == korg.key.EDIT_RIGHT) turn = 1;
  if (key == korg.key.EDIT_LEFT) soft = 1;
});

korg.onEvent("buttonRelease", (key) => {
  if (key == korg.key.EDIT_LEFT) soft = 0;
});

// One kind of work per frame: the numbers, a move, a collapsing row, two redrawn rows, the next piece, a setup step.
korg.onEvent("frame", () => {
  if (hud && (state == 0 || state == 5 || state == 2)) {
    hud = 0;
    drawHud();
  } else if (state == 0) {
    step();
  } else if (state == 3) {
    collapse();
  } else if (state == 1) {
    drawRow(repaintAt);
    repaintAt += 1;
    if (repaintAt <= repaintTo) {
      drawRow(repaintAt);
      repaintAt += 1;
    }
    if (repaintAt > repaintTo) state = 5;
  } else if (state == 5) {
    state = 0;
    spawn();
  } else if (state == 4) {
    setupStep();
  }
});
`,
  }),
  Object.freeze({
    id: "life",
    title: "Game of Life",
    description: text("catalog.life.description"),
    category: text("catalog.category.games"),
    creator: "Kuhler Buhler",
    added: "2026-10-16",
    controls: [text("catalog.life.control1"), text("catalog.life.control2"), text("catalog.life.control3"), text("catalog.life.control4"), text("catalog.life.control5")],
    source: `// Conway's Game of Life on a 32 x 16 torus of 4 x 4 pixel cells, an app under GAMES. The touchpad draws: a touch
// sets the cell under the finger. Key 1 starts and pauses (its LED is lit while it runs), key 2 steps once, key 3
// clears, key 4 fills the grid with random cells. A row of the grid is one 32-bit number, a generation is computed
// for all 32 cells of a row at once with bit operations. Sparse changes are drawn as cells, dense pairs of rows
// as bitmaps. The next generation is computed alongside painting and swaps in after the picture has caught up.
korg.app("Life", "GAMES");
const H = 16;
const cur = new Array(H);
const nxt = new Array(H);
const shown = new Array(H);
const band = new Array(128);
let running = 1;
let stepReq = 0;
let computing = 0;
let genRow = 0;
let idle = 0;
let paintAt = 0;
let soupAt = 16;
let seed = 1;
let isOpen = 0;

function rnd() {
  seed = seed * 1103515245 + 12345;
  return (seed >> 16) & 0x7fff;
}

function cell(x, y, on) {
  if (on) korg.display.rect(x * 4, y * 4, 3, 3);
  else korg.display.clearRect(x * 4, y * 4, 3, 3);
}

function wrapW(v) {
  return (v << 1) | ((v >> 31) & 1);
}

function wrapE(v) {
  return ((v >> 1) & 0x7fffffff) | (v << 31);
}

// The next state of row y, all 32 cells at once: the neighbour count is added up bit by bit in n3 n2 n1 n0.
function nextRow(y) {
  const u = cur[(y + H - 1) % H];
  const c = cur[y];
  const d = cur[(y + 1) % H];
  const uw = wrapW(u);
  const ue = wrapE(u);
  const dw = wrapW(d);
  const de = wrapE(d);
  const cw = wrapW(c);
  const ce = wrapE(c);
  const u0 = uw ^ u ^ ue;
  const u1 = (uw & u) | (ue & (uw ^ u));
  const d0 = dw ^ d ^ de;
  const d1 = (dw & d) | (de & (dw ^ d));
  const x0 = cw ^ ce;
  const x1 = cw & ce;
  const t0 = u0 ^ d0;
  const k = u0 & d0;
  const t1 = u1 ^ d1 ^ k;
  const c1 = (u1 & d1) | (k & (u1 ^ d1));
  const n0 = t0 ^ x0;
  const k0 = t0 & x0;
  const n1 = t1 ^ x1 ^ k0;
  const k1 = (t1 & x1) | (k0 & (t1 ^ x1));
  const n2 = c1 ^ k1;
  return ~n2 & n1 & (n0 | c);
}

function firstBit(bits) {
  let x = 0;
  if ((bits & 65535) == 0) { bits >>= 16; x += 16; }
  if ((bits & 255) == 0) { bits >>= 8; x += 8; }
  if ((bits & 15) == 0) { bits >>= 4; x += 4; }
  if ((bits & 3) == 0) { bits >>= 2; x += 2; }
  if ((bits & 1) == 0) x += 1;
  return x;
}

function paintBand(y) {
  let u = cur[y];
  let d = cur[y + 1];
  let at = 0;
  for (let x = 0; x < 32; x++) {
    const bits = ((u & 1) * 7) | ((d & 1) * 112);
    band[at] = bits;
    band[at + 1] = bits;
    band[at + 2] = bits;
    u >>= 1;
    d >>= 1;
    at += 4;
  }
  korg.display.clearRect(0, y * 4, 128, 8);
  korg.display.bitmap(band, 0, y * 4, 128);
  shown[y] = cur[y];
  shown[y + 1] = cur[y + 1];
}

function paint(limit) {
  let work = 0;
  let n = 0;
  idle = 1;
  while (n < H) {
    const y = (paintAt + n) & 15;
    let diff = (cur[y] ^ shown[y]) | (cur[y + 1] ^ shown[y + 1]);
    let count = 0;
    while (diff != 0 && count < 8) {
      diff &= diff - 1;
      count += 1;
    }
    if (count >= 8) {
      if (work > 0) { idle = 0; break; }
      paintBand(y);
      work = 2300;
    } else {
      work += 100 + count * 25;
      for (let row = y; row < y + 2; row++) {
        diff = cur[row] ^ shown[row];
        while (diff != 0 && work < limit) {
          const x = firstBit(diff);
          cell(x, row, (cur[row] >> x) & 1);
          shown[row] ^= 1 << x;
          diff &= diff - 1;
          work += 180;
        }
      }
      if (cur[y] != shown[y] || cur[y + 1] != shown[y + 1]) {
        idle = 0;
        break;
      }
    }
    n += 2;
    if (work >= limit) { idle = 0; break; }
  }
  paintAt = (paintAt + n) & 15;
  return work;
}

function wipe() {
  for (let y = 0; y < H; y++) {
    cur[y] = 0;
    nxt[y] = 0;
    shown[y] = 0;
  }
  korg.display.clear();
  computing = 0;
  paintAt = 0;
  idle = 1;
  soupAt = 16;
}

function touchCell(x, y) {
  if (x > 1023) x = 1023;
  if (y > 1023) y = 1023;
  const col = (x * 32) >> 10;
  const row = 15 - ((y * 16) >> 10);
  cur[row] |= 1 << col;
  nxt[row] |= 1 << col;
  idle = 0;
}

korg.onEvent("open", () => {
  isOpen = 1;
  seed = korg.millis() + 3;
  wipe();
  running = 1;
  stepReq = 0;
  cur[0] = 2;
  cur[1] = 4;
  cur[2] = 7;
  cur[8] = (1 << 17) | (1 << 18);
  cur[9] = (1 << 16) | (1 << 17);
  cur[10] = 1 << 17;
  idle = 0;
  korg.led(korg.led.BAR_1, 255);
});

korg.onEvent("close", () => {
  isOpen = 0;
  korg.led(korg.led.BAR_1, 0);
});

korg.onEvent("touch", (x, y) => {
  if (isOpen) touchCell(x, y);
});

korg.onEvent("buttonPress", (key) => {
  if (!isOpen) return;
  if (key == korg.key.BAR_1) {
    running = !running;
    korg.led(korg.led.BAR_1, running ? 255 : 0);
  }
  if (key == korg.key.BAR_2) stepReq = 1;
  if (key == korg.key.BAR_3) wipe();
  if (key == korg.key.BAR_4) {
    wipe();
    soupAt = 0;
  }
});

korg.onEvent("frame", () => {
  if (soupAt < H) {
    const a = (rnd() << 17) ^ (rnd() << 2) ^ rnd();
    const b = (rnd() << 17) ^ (rnd() << 2) ^ rnd();
    cur[soupAt] = a & b;
    soupAt += 1;
    idle = 0;
    return;
  }
  let work = 0;
  if (!idle) work = paint(1200);
  if (computing == 0 && (running || stepReq)) {
    computing = 1;
    genRow = 0;
  }
  while (computing && genRow < H && work < 1700) {
    nxt[genRow] = nextRow(genRow);
    genRow += 1;
    work += 300;
  }
  if (computing && genRow >= H && idle) {
    for (let y = 0; y < H; y++) cur[y] = nxt[y];
    computing = 0;
    stepReq = 0;
    idle = 0;
  }
});
`,
  }),
  Object.freeze({
    id: "pong",
    title: "Pong",
    description: text("catalog.pong.description"),
    category: text("catalog.category.games"),
    creator: "Kuhler Buhler",
    added: "2026-10-16",
    controls: [text("catalog.pong.control1"), text("catalog.pong.control2")],
    source: `// Pong against a bot, an app under GAMES: first to 9 wins. Your paddle is on the left. Move it with a finger on the
// touchpad (the height of the finger is the height of the paddle), with Part left (up) and Part right (down), or
// with an encoder. The bot is slow on purpose: it only reacts to a ball that comes towards it, it misjudges the height
// a little after every return, and a steep return is faster than it can follow. The ball speeds up with every hit.
// Positions of the ball are in quarter pixels. Ball and bot move on every second frame (12.5 a second): the display is
// slow. Two previous ball positions stay lit as a short trail until the ball moves on.
korg.app("Pong", "GAMES");
const NET = [0x33, 0x33, 0x33, 0x33, 0x33, 0x33, 0x33, 0x33];
const trailX = new Array(2);
const trailY = new Array(2);
let trailCount = 0;
const PH = 14;
const PX = 4;
const BOTX = 121;
let bx = 0;
let by = 0;
let vx = 0;
let vy = 0;
let py = 25;
let boty = 25;
let botErr = 0;
let myScore = 0;
let botScore = 0;
let state = 0;
let wait = 0;
let serveDir = 1;
let up = 0;
let down = 0;
let seed = 1;
let isOpen = 0;
let tick = 0;

function rnd() {
  seed = seed * 1103515245 + 12345;
  return (seed >> 16) & 0x7fff;
}

function serve() {
  trailCount = 0;
  bx = 62 * 4;
  by = 30 * 4;
  vx = 12 * serveDir;
  vy = (rnd() % 9 - 4) * 2;
  botErr = rnd() % 11 - 5;
  state = 1;
}

function newGame() {
  trailCount = 0;
  myScore = 0;
  botScore = 0;
  serveDir = 1;
  state = 0;
  wait = 13;
}

function clampPaddle(y) {
  if (y < 0) return 0;
  if (y > 64 - PH) return 64 - PH;
  return y;
}

function point(mine) {
  trailCount = 0;
  if (mine) {
    myScore += 1;
    serveDir = 1;
  } else {
    botScore += 1;
    serveDir = -1;
  }
  if (myScore >= 9 || botScore >= 9) {
    state = 2;
  } else {
    state = 0;
    wait = 13;
  }
}

function moveBot() {
  let target = 25;
  if (vx > 0 && (bx >> 2) > 40) target = (by >> 2) - 6 + botErr;
  target = clampPaddle(target);
  if (boty < target) boty += 2;
  else if (boty > target) boty -= 2;
  if (boty > target - 2 && boty < target + 2) boty = target;
}

function moveBall() {
  trailX[1] = trailX[0];
  trailY[1] = trailY[0];
  trailX[0] = bx;
  trailY[0] = by;
  if (trailCount < 2) trailCount += 1;
  bx += vx;
  by += vy;
  if (by < 0) {
    by = 0 - by;
    vy = 0 - vy;
  }
  if (by > 60 * 4) {
    by = 120 * 4 - by;
    vy = 0 - vy;
  }
  const x = bx >> 2;
  const y = by >> 2;
  if (vx < 0 && x <= PX + 3 && x >= PX - 2 && y + 3 >= py && y <= py + PH) {
    bx = (PX + 4) * 4;
    vx = 0 - vx + 1;
    if (vx > 22) vx = 22;
    vy = (y + 1 - (py + 7)) * 2;
    botErr = rnd() % 11 - 5;
  } else if (vx > 0 && x + 3 >= BOTX && x <= BOTX + 3 && y + 3 >= boty && y <= boty + PH) {
    bx = (BOTX - 4) * 4;
    vx = 0 - vx - 1;
    if (vx < -22) vx = -22;
    vy = (y + 1 - (boty + 7)) * 2;
  } else if (x < 0) {
    point(0);
  } else if (x > 127) {
    point(1);
  }
}

function draw() {
  korg.display.clear();
  korg.display.bitmap(NET, 63, 0, 1);
  korg.display.rect(PX, py, 3, PH);
  korg.display.rect(BOTX, boty, 3, PH);
  korg.display.number(myScore, 52, 2);
  korg.display.number(botScore, 70, 2);
  if (state == 1) {
    for (let i = 0; i < trailCount; i++) korg.display.rect(trailX[i] >> 2, trailY[i] >> 2, 3, 3);
    korg.display.rect(bx >> 2, by >> 2, 3, 3);
  }
  if (state == 2) {
    if (myScore > botScore) korg.display.text("YOU WIN", 44, 30);
    else korg.display.text("BOT WINS", 40, 30);
  }
}

korg.onEvent("open", () => {
  isOpen = 1;
  seed = korg.millis() + 5;
  up = 0;
  down = 0;
  py = 25;
  boty = 25;
  newGame();
  draw();
});

korg.onEvent("close", () => {
  isOpen = 0;
});

korg.onEvent("touch", (x, y) => {
  if (!isOpen) return;
  if (y > 1023) y = 1023;
  py = clampPaddle(((1023 - y) * (65 - PH)) >> 10);
});

korg.onEvent("encoder", (index, delta) => {
  if (isOpen) py = clampPaddle(py + delta * 3);
});

korg.onEvent("buttonPress", (key) => {
  if (!isOpen) return;
  if (key == korg.key.PART_LEFT) up = 1;
  if (key == korg.key.PART_RIGHT) down = 1;
  if (state == 2) newGame();
});

korg.onEvent("buttonRelease", (key) => {
  if (key == korg.key.PART_LEFT) up = 0;
  if (key == korg.key.PART_RIGHT) down = 0;
});

korg.onEvent("frame", () => {
  if (up) py = clampPaddle(py - 3);
  if (down) py = clampPaddle(py + 3);
  tick = 1 - tick;
  if (tick == 0) {
    draw();
    return;
  }
  if (state == 0) {
    wait -= 1;
    if (wait <= 0) serve();
  } else if (state == 1) {
    moveBot();
    moveBall();
  }
  draw();
});
`,
  }),
  Object.freeze({
    id: "simon",
    title: "Simon",
    description: text("catalog.simon.description"),
    category: text("catalog.category.games"),
    creator: "Kuhler Buhler",
    added: "2026-10-16",
    controls: [text("catalog.simon.control1"), text("catalog.simon.control2")],
    source: `// Simon, an app under GAMES, on all 16 pads. The pads light up in a sequence, repeat it on the pads, and the sequence
// grows by one step every round. A wrong pad ends the game and shows the number of rounds you got through. While the app is
// open it holds the panel LEDs (korg.ledHold) so the firmware does not paint over the pads; the display shows the round, the
// step and what to do. TAP or any pad starts anew.
korg.app("Simon", "GAMES");
const seq = new Array(60);
let len = 0;
let pos = 0;
let state = 0;
let timer = 0;
let lit = -1;
let score = 0;
let flash = 0;
let seed = 1;
let isOpen = 0;

function rnd() {
  seed = seed * 1103515245 + 12345;
  return (seed >> 16) & 0x7fff;
}

function setPad(i, on) {
  korg.led(korg.led.PAD_1_RED + i * 2, on ? 255 : 0);
}

function light(i) {
  if (lit >= 0) setPad(lit, 0);
  lit = i;
  if (i >= 0) setPad(i, 1);
}

function setAll(on) {
  for (let i = 0; i < 16; i++) setPad(i, on);
}

function status(which) {
  korg.display.clearRect(0, 22, 128, 20);
  if (which == 0) korg.display.text("GET READY", 37, 28);
  else if (which == 1) korg.display.text("WATCH", 49, 28);
  else if (which == 2) korg.display.text("YOUR TURN", 37, 28);
  else if (which == 3) korg.display.text("WELL DONE", 37, 28);
  else korg.display.text("GAME OVER", 37, 28);
}

// the round (0) or the score (1), right-aligned 4 pixels from the edge
function header(which, n) {
  const x = n >= 10 ? 77 : 83;
  korg.display.clearRect(60, 0, 68, 10);
  if (which == 0) korg.display.textNumber("ROUND ", n, x, 2);
  else korg.display.textNumber("SCORE ", n, x, 2);
}

// the bottom line: nothing (0), the step to play (1, n), how to start anew (2)
function hint(which, n) {
  korg.display.clearRect(0, 53, 128, 11);
  if (which == 1) korg.display.textNumber("STEP ", n, 4, 55);
  else if (which == 2) korg.display.text("TAP OR PAD: NEW GAME", 4, 55);
}

function newGame() {
  len = 0;
  pos = 0;
  score = 0;
  lit = -1;
  state = 0;
  timer = 25;
  korg.display.clear();
  korg.display.text("SIMON", 4, 2);
  status(0);
  hint(0, 0);
}

function addStep() {
  seq[len] = rnd() & 15;
  len += 1;
  pos = 0;
  timer = 12;
  state = 1;
  header(0, len);
  status(1);
  hint(0, 0);
}

korg.onEvent("open", () => {
  isOpen = 1;
  seed = korg.millis() + 11;
  korg.ledHold(1);
  for (let i = 0; i < 32; i++) korg.led(korg.led.PAD_1_RED + i, 0);
  newGame();
});

korg.onEvent("close", () => {
  isOpen = 0;
  for (let i = 0; i < 32; i++) korg.led(korg.led.PAD_1_RED + i, 0);
  korg.ledHold(0);
});

korg.onEvent("pad", (index, down) => {
  if (!isOpen || index > 15) return;
  if (state == 5) {
    if (down) newGame();
    return;
  }
  if (!down) {
    if (lit == index && (state == 2 || state == 4)) light(-1);
    return;
  }
  if (state != 2) return;
  light(index);
  if (seq[pos] != index) {
    state = 3;
    flash = 0;
    timer = 8;
    return;
  }
  pos += 1;
  if (pos >= len) {
    score = len;
    state = 4;
    timer = 20;
    status(3);
  } else {
    hint(1, pos + 1);
  }
});

korg.onEvent("buttonPress", (key) => {
  if (isOpen && state == 5 && key == korg.key.TAP) newGame();
});

// A step of the sequence lights for 18 frames (0.72 s), a little shorter every fourth round, never below 10 (0.4 s).
korg.onEvent("frame", () => {
  if (state == 0) {
    timer -= 1;
    if (timer <= 0) addStep();
  } else if (state == 1) {
    timer -= 1;
    if (timer > 0) return;
    if (lit >= 0) {
      light(-1);
      pos += 1;
      if (pos >= len) {
        pos = 0;
        state = 2;
        status(2);
        hint(1, 1);
      }
      timer = 6;
    } else {
      light(seq[pos]);
      timer = 18 - len / 4;
      if (timer < 10) timer = 10;
    }
  } else if (state == 4) {
    timer -= 1;
    if (timer <= 0) {
      light(-1);
      addStep();
    }
  } else if (state == 3) {
    timer -= 1;
    if (timer > 0) return;
    if (flash < 6) {
      lit = -1;
      setAll(flash & 1 ? 0 : 1);
      flash += 1;
      timer = 6;
    } else {
      setAll(0);
      state = 5;
      status(4);
      header(1, score);
      hint(2, 0);
    }
  }
});
`,
  }),
  Object.freeze({
    id: "mandelbrot",
    title: "Mandelbrot",
    description: text("catalog.mandelbrot.description"),
    category: text("catalog.category.games"),
    creator: "Kuhler Buhler",
    added: "2026-10-16",
    controls: [text("catalog.mandelbrot.control1"), text("catalog.mandelbrot.control2"), text("catalog.mandelbrot.control3"), text("catalog.mandelbrot.control4")],
    source: `// Mandelbrot in Q14 fixed point. A bounded worklist holds unresolved rectangles. Proven interior rectangles are
// filled once; other rectangles split until their pixels can be iterated individually. Each frame has a small work
// budget. Touchpad pans, Part keys and encoder zoom, keys 1 and 2 change iterations, TAP resets the view.
korg.app("Mandelbrot", "GAMES");
const BUDGET = 1850;
// At most 2048 unresolved 2-by-2 leaves fit in the breadth-first frontier.
const todo = new Array(2048);
let head = 0;
let tail = 0;
let pending = 0;
let tile = 0;
let at = 0;
let px = 0;
let py = 0;
let cx = -8192;
let cy = 0;
let zoom = 0;
let ds = 384;
let maxIter = 24;
let sx = 0;
let sy = 0;
let used = 0;
let done = 0;
let lastX = 0;
let lastY = 0;
let isOpen = 0;
let active = 0;
let cr = 0;
let ci = 0;
let zx = 0;
let zy = 0;
let n = 0;

// True for a point in the main cardioid or the period 2 bulb: they are recognised by their equations, iterating them
// would eat the whole iteration limit.
function inside(cr, ci) {
  if (cr > -12288 && cr < 6144 && ci > -11000 && ci < 11000) {
    const xq = cr - 4096;
    const q = ((xq * xq) >> 14) + ((ci * ci) >> 14);
    if (((q * (q + xq)) >> 14) < ((ci * ci) >> 16)) return 1;
  }
  if (cr > -20480 && cr < -12288 && ci > -4096 && ci < 4096) {
    const xp = cr + 16384;
    if (((xp * xp) >> 14) + ((ci * ci) >> 14) < 1024) return 1;
  }
  return 0;
}

// Bounds of the Q14 predicates over a rectangle, including rounding. The coordinate guards keep products within signed 32 bits.
function insideBlock(x, y, w, h) {
  const r = x + (w - 1) * ds;
  const b = y + (h - 1) * ds;
  let ay = y < 0 ? -y : y;
  const by = b < 0 ? -b : b;
  if (by > ay) ay = by;
  if (x > -20480 && r < -12288 && y > -4096 && b < 4096) {
    let ax = x + 16384;
    if (ax < 0) ax = -ax;
    const bx = r + 16384;
    if (bx > ax) ax = bx;
    if (((ax * ax) >> 14) + ((ay * ay) >> 14) < 1024) return 1;
  }
  if (x > -12288 && r < 6144 && y > -11000 && b < 11000) {
    const lq = x - 4096;
    const rq = r - 4096;
    let ax = lq < 0 ? -lq : lq;
    const bx = rq < 0 ? -rq : rq;
    let nx = ax;
    if (bx > ax) ax = bx;
    if (bx < nx) nx = bx;
    if (lq <= 0 && rq >= 0) nx = 0;
    let ny = y < 0 ? -y : y;
    if (by < ny) ny = by;
    if (y <= 0 && b >= 0) ny = 0;
    const hi = ((ax * ax) >> 14) + ((ay * ay) >> 14);
    const lo = ((nx * nx) >> 14) + ((ny * ny) >> 14);
    let edge = ((lq * lq) >> 14) + lq;
    const right = ((rq * rq) >> 14) + rq;
    if (right > edge) edge = right;
    const factor = edge + ((ay * ay) >> 14);
    const product = factor < 0 ? lo * factor : hi * factor;
    if ((product >> 14) < ((ny * ny) >> 16)) return 1;
  }
  return 0;
}

function push(x, y, level) {
  todo[tail] = x | (y << 7) | (level << 13);
  tail = (tail + 1) & 2047;
  pending += 1;
}

function restart() {
  korg.display.clear();
  head = 0;
  tail = 0;
  pending = 0;
  tile = 0;
  active = 0;
  done = 0;
  push(0, 0, 6);
  push(64, 0, 6);
}

function hud() {
  korg.display.clearRect(76, 53, 52, 11);
  korg.display.textNumber("Z", zoom, 80, 55);
  korg.display.textNumber("I", maxIter, 104, 55);
}

function changed() {
  if (zoom < 0) zoom = 0;
  if (zoom > 7) zoom = 7;
  if (maxIter < 8) maxIter = 8;
  if (maxIter > 64) maxIter = 64;
  if (cx < -40960) cx = -40960;
  if (cx > 40960) cx = 40960;
  if (cy < -40960) cy = -40960;
  if (cy > 40960) cy = 40960;
  ds = 384 >> zoom;
  restart();
  hud();
}

korg.onEvent("open", () => {
  isOpen = 1;
  cx = -8192;
  cy = 0;
  zoom = 0;
  maxIter = 24;
  ds = 384;
  restart();
});

korg.onEvent("close", () => {
  isOpen = 0;
});

korg.onEvent("touch", (x, y, first) => {
  if (!isOpen) return;
  if (!first) {
    const dxp = (x - lastX) >> 3;
    const dyp = (y - lastY) >> 4;
    if (dxp != 0 || dyp != 0) {
      cx -= dxp * ds;
      cy += dyp * ds;
      lastX += dxp << 3;
      lastY += dyp << 4;
      changed();
    }
  } else {
    lastX = x;
    lastY = y;
  }
});

korg.onEvent("encoder", (index, delta) => {
  if (!isOpen) return;
  zoom += delta > 0 ? 1 : -1;
  changed();
});

korg.onEvent("buttonPress", (key) => {
  if (!isOpen) return;
  if (key == korg.key.PART_RIGHT) zoom += 1;
  if (key == korg.key.PART_LEFT) zoom -= 1;
  if (key == korg.key.BAR_1) maxIter -= 8;
  if (key == korg.key.BAR_2) maxIter += 8;
  if (key == korg.key.TAP) {
    cx = -8192;
    cy = 0;
    zoom = 0;
  }
  if (key == korg.key.PART_RIGHT || key == korg.key.PART_LEFT || key == korg.key.BAR_1 || key == korg.key.BAR_2 || key == korg.key.TAP) changed();
});

// An unfinished orbit remains in zx, zy and n until the following frame.
korg.onEvent("frame", () => {
  used = 0;
  while (used < BUDGET && !done) {
    if (active) {
      let esc = 0;
      while (n < maxIter && used < BUDGET && !esc) {
        if (zx > 32768 || zx < -32768 || zy > 32768 || zy < -32768) esc = 1;
        else {
          const zx2 = (zx * zx) >> 14;
          const zy2 = (zy * zy) >> 14;
          if (zx2 + zy2 > 65536) esc = 1;
          else {
            zy = ((zx * zy) >> 13) + ci;
            zx = zx2 - zy2 + cr;
            n += 1;
            used += 75;
          }
        }
      }
      if (esc || n >= maxIter) {
        let ink = 0;
        if (n == maxIter || (n > 2 && (n & 3) == 0)) ink = 1;
        korg.display.pixel(px, py, ink);
        active = 0;
        at += 1;
        if (at == 4) tile = 0;
        used += 60;
      }
    } else if (tile) {
      px = sx + (at & 1);
      py = sy + (at >> 1);
      cr = cx + (px - 64) * ds;
      ci = cy + (py - 32) * ds;
      zx = 0;
      zy = 0;
      n = 0;
      if (inside(cr, ci)) n = maxIter;
      active = 1;
      used += 140;
    } else if (pending > 0) {
      const task = todo[head];
      head = (head + 1) & 2047;
      pending -= 1;
      sx = task & 127;
      sy = (task >> 7) & 63;
      const level = task >> 13;
      const size = 1 << level;
      used += 350;
      if (insideBlock(cx + (sx - 64) * ds, cy + (sy - 32) * ds, size, size)) {
        korg.display.rect(sx, sy, size, size);
        used += 80;
      } else if (size > 2) {
        const h = size >> 1;
        push(sx, sy, level - 1);
        push(sx + h, sy, level - 1);
        push(sx, sy + h, level - 1);
        push(sx + h, sy + h, level - 1);
        used += 100;
      } else {
        tile = 1;
        at = 0;
      }
    } else {
      if (used > 1000) break;
      done = 1;
      hud();
    }
  }
});
`,
  }),
  Object.freeze({
    id: "gifplayer",
    title: "GIF Player",
    description: text("catalog.gifplayer.description"),
    category: text("catalog.category.tools"),
    creator: "Kuhler Buhler",
    added: "2026-10-20",
    controls: [text("catalog.gifplayer.control1"), text("catalog.gifplayer.control2"), text("catalog.gifplayer.control3")],
    source: `// GIF Player, an app under TOOLS: plays the picture files GIF00.E2G to GIF99.E2G from KORG/blechtribe/Gif/ on the card
// (tools/gif/gif2e2g.py makes one from a GIF). The encoder picks the file, Part left and right halve and double the speed
// (25 to 400 percent), TAP pauses. The runtime draws once per frame of 40 ms, so a picture stays at least that long.
korg.app("GIF Player", "TOOLS");
const pic = new Array(1024);
let file = 0;
let index = 0;
let speed = 100;
let paused = 0;
let due = 0;
let isOpen = 0;

function info(pause) {
  korg.display.clear();
  korg.display.textNumber("GIF ", file, 4, 14);
  if (pause == 1) korg.display.text("Paused", 4, 26);
  else korg.display.text("no file", 4, 26);
  korg.display.textNumber("Tempo % ", speed, 4, 38);
}

function next() {
  let delay = korg.file.frame(pic, file, index);
  if (delay == 0 && index > 0) {
    index = 0;
    delay = korg.file.frame(pic, file, 0);
  }
  if (delay <= 0) {
    info(0);
    due = korg.millis() + 500;
    return;
  }
  korg.display.clear();
  korg.display.bitmap(pic, 0, 0, 128);
  index += 1;
  due = korg.millis() + delay * 100 / speed;
}

korg.onEvent("open", () => {
  isOpen = 1;
  index = 0;
  due = 0;
  next();
});

korg.onEvent("close", () => {
  isOpen = 0;
});

korg.onEvent("frame", () => {
  if (paused == 0 && korg.millis() >= due) next();
});

korg.onEvent("encoder", (i, delta) => {
  if (isOpen == 0) return;
  file += delta;
  if (file < 0) file = 0;
  if (file > 99) file = 99;
  index = 0;
  due = 0;
  if (paused == 1) next();
});

korg.onEvent("buttonPress", (key) => {
  if (isOpen == 0) return;
  if (key == korg.key.PART_LEFT && speed > 25) speed = speed / 2;
  if (key == korg.key.PART_RIGHT && speed < 400) speed = speed * 2;
  if (key == korg.key.TAP) paused = 1 - paused;
  if (key == korg.key.TAP && paused == 1) info(1);
  if (key == korg.key.TAP && paused == 0) due = 0;
});
`,
  }),
  Object.freeze({
    id: "bmpviewer",
    title: "Image Viewer",
    description: text("catalog.bmpviewer.description"),
    category: text("catalog.category.tools"),
    creator: "Kuhler Buhler",
    added: "2026-11-03",
    controls: [text("catalog.bmpviewer.control1"), text("catalog.bmpviewer.control2"), text("catalog.bmpviewer.control3")],
    source: `// Image Viewer, an app under TOOLS: shows the pictures of a picture file GIF00.E2G to GIF99.E2G from KORG/blechtribe/Gif/
// on the card one at a time (tools/gif/gif2e2g.py puts several BMPs or other pictures into one file, one frame each).
// Part right and left show the next and the previous picture, the encoder picks the file. After each change the top left
// corner shows the number of the picture for two seconds, TAP keeps it there or hides it. Backwards past the first picture
// goes to the last one once the viewer has been through the file and knows how many there are.
korg.app("Image Viewer", "TOOLS");
const pic = new Array(1024);
let file = 0;
let index = 0;
let count = 0;
let shown = 0;
let label = 0;
let until = 0;
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
  korg.display.clear();
  korg.display.bitmap(pic, 0, 0, 128);
  if (label == 0 && until == 0) return;
  let width = digits(index + 1) * 6 + 3;
  if (count > 0) width += digits(count) * 6 + 6;
  korg.display.clearRect(0, 0, width, 9);
  korg.display.number(index + 1, 1, 1);
  if (count > 0) korg.display.textNumber("/", count, 1 + digits(index + 1) * 6, 1);
}

function show() {
  let delay = korg.file.frame(pic, file, index);
  if (delay == 0 && index > 0) {
    count = index;
    index = 0;
    delay = korg.file.frame(pic, file, 0);
  }
  if (delay <= 0) {
    shown = 0;
    korg.display.clear();
    korg.display.textNumber("GIF ", file, 4, 14);
    korg.display.text("no file", 4, 26);
    return;
  }
  shown = 1;
  until = korg.millis() + 2000;
  draw();
}

korg.onEvent("open", () => {
  isOpen = 1;
  show();
});

korg.onEvent("close", () => {
  isOpen = 0;
});

korg.onEvent("frame", () => {
  if (shown == 1 && until > 0 && korg.millis() >= until) {
    until = 0;
    draw();
  }
});

korg.onEvent("encoder", (i, delta) => {
  if (isOpen == 0) return;
  file += delta;
  if (file < 0) file = 0;
  if (file > 99) file = 99;
  index = 0;
  count = 0;
  show();
});

korg.onEvent("buttonPress", (key) => {
  if (isOpen == 0) return;
  if (key == korg.key.PART_RIGHT) {
    index += 1;
    show();
  }
  if (key == korg.key.PART_LEFT) {
    if (index > 0) index -= 1;
    else if (count > 0) index = count - 1;
    show();
  }
  if (key == korg.key.TAP && shown == 1) {
    label = 1 - label;
    until = 0;
    draw();
  }
});
`,
  }),
  Object.freeze({
    id: "bpmglide",
    title: "BPM Glide",
    description: text("catalog.bpmglide.description"),
    category: text("catalog.category.tools"),
    creator: "KrImZoR",
    added: "2026-10-25",
    controls: [text("catalog.bpmglide.control1")],
    source: `// BPM Glide, an idea of KrImZoR: while the pattern that plays chains on to another one (Chain To, with CHAIN MODE on in
// Global), the tempo glides from where it started to the stored tempo of the next pattern, over the time the pattern plays:
// its length times Chain Repeat. The last step reaches the new tempo, so the switch itself does not jump. STOP gives the
// pattern its own tempo back. The page BPM GLIDE in the BLECH menu switches it on (1) and off (0).
let on = korg.store.get(0, 1);
let page = korg.menu.add("BPM GLIDE", 0, 1, on);
let pending = 1;
let active = 0;
let base = 0;
let target = 0;
let length = 16;
let total = 16;
let laps = 0;
let last = -1;

// Reads the chain of the pattern in RAM once it has been loaded: the first step after PLAY or a pattern change.
function arm(step) {
  pending = 0;
  active = 0;
  const next = korg.current.chainTo;
  if (!on || !korg.chainMode || next < 0) return;
  base = korg.tempo;
  target = korg.patterns[next].tempo;
  length = korg.current.length * 16;
  total = length * korg.current.chainRepeat;
  laps = 0;
  last = step;
  active = base != target ? 1 : 0;
}

function glide(step) {
  if (step < last) laps += 1;
  last = step;
  let done = laps * length + step + 1;
  if (done > total) done = total;
  const tempo = base + (target - base) * done / total;
  if (tempo != korg.tempo) korg.tempo = tempo;
}

function giveBack() {
  if (active && korg.tempo != base) korg.tempo = base;
  active = 0;
}

korg.onEvent("play", () => { pending = 1; });
korg.onEvent("patternChange", () => { pending = 1; });
korg.onEvent("step", (step) => {
  if (pending) arm(step);
  if (active) glide(step);
});
korg.onEvent("stop", () => {
  giveBack();
  pending = 1;
});
korg.onEvent("menu", (id, value) => {
  if (id != page) return;
  on = value;
  korg.store.set(0, on);
  korg.store.save();
  if (!on) giveBack();
  pending = 1;
});
`,
  }),
  Object.freeze({
    id: "lauflicht",
    title: "Lauflicht",
    description: text("catalog.lauflicht.description"),
    category: text("catalog.category.light"),
    creator: "Kuhler Buhler",
    added: "2026-10-16",
    controls: [],
    source: `// Lauflicht: ein rotes Pad-Licht wandert über die 16 Pads.
const FIRST_RED_PAD = korg.led.PAD_1_RED;
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
`,
  }),
  Object.freeze({
    id: "pulsieren",
    title: "Pulsieren",
    description: text("catalog.pulsieren.description"),
    category: text("catalog.category.light"),
    creator: "Kuhler Buhler",
    added: "2026-10-16",
    controls: [],
    source: `// Pulsieren: alle roten Pad-LEDs werden im Dreieck heller und dunkler.
const FIRST_RED_PAD = korg.led.PAD_1_RED;
let phase = 0;

korg.onEvent("frame", () => {
  phase = (phase + 8) % 512;
  const level = phase < 256 ? phase : 511 - phase;
  for (let pad = 0; pad < 16; pad++) korg.led(FIRST_RED_PAD + pad * 2, level);
});
`,
  }),
  Object.freeze({
    id: "playtakt",
    title: "PLAY-Takt",
    description: text("catalog.playtakt.description"),
    category: text("catalog.category.light"),
    creator: "Kuhler Buhler",
    added: "2026-11-10",
    controls: [],
    source: `// PLAY-Takt: solange der Sequencer läuft, blinkt die PLAY-LED im Tempo des Patterns, bei STOP und Pause leuchtet sie
// ruhig. Dabei zeigt es die Timer der Plugin-API (API 11): \`beat\` kommt auf jede Viertel und macht die LED an,
// korg.afterSteps(2, off) macht sie zwei Schritte später wieder aus, so folgt das Blinken dem Tempo. STOP und Pause räumen
// den Timer mit korg.cancel ab. In der Pause blinkt die Firmware die PLAY-LED selbst, das Plugin setzt sie dort in jedem
// Rahmen wieder an.
let dark = -1;

function playLed(level) {
  korg.led(korg.led.PLAY, level);
  korg.led(korg.led.PLAY_BLUE, level);
}

function off() {
  playLed(0);
}

korg.onEvent("ready", () => { if (korg.transport == 0) playLed(255); });

korg.onEvent("beat", () => {
  korg.cancel(dark);
  playLed(255);
  dark = korg.afterSteps(2, off);
});

korg.onEvent("stop", () => {
  korg.cancel(dark);
  playLed(255);
});

korg.onEvent("frame", () => { if (korg.transport == 2) playLed(255); });
`,
  }),
  Object.freeze({
    id: "momentmute",
    title: "Momentary Mute",
    description: text("catalog.momentmute.description"),
    category: text("catalog.category.tools"),
    creator: "Kuhler Buhler",
    added: "2026-11-03",
    controls: [text("catalog.momentmute.control1"), text("catalog.momentmute.control2")],
    source: `// Momentary Mute, a wish from the community: mutes change only while PART MUTE is held. PART MUTE held, a pad switches its
// part on or off and the pads show the mutes; PART MUTE released, the pads trigger as in TRIGGER mode. All of it is the
// firmware's: PART MUTE switches the pad mode on its press and keeps it after the release (measured in the emulator), so
// the plugin only presses TRIGGER for the firmware when PART MUTE comes up (korg.pressKey). SHIFT + PART MUTE stays the
// firmware's, and another mode key pressed while PART MUTE is held keeps its mode. The page MOMENT MUTE in the BLECH menu
// switches it on (1) and off (0: PART MUTE stays a mode as without the plugin).
const MODES = [korg.key.PART_ERASE, korg.key.TRIGGER, korg.key.SEQUENCER, korg.key.KEYBOARD, korg.key.CHORD, korg.key.STEP_JUMP, korg.key.PATTERN_SET];
let on = korg.store.get(0, 1);
let page = korg.menu.add("MOMENT MUTE", 0, 1, on);
let shift = 0;
let held = 0;

korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.SHIFT) shift = 1;
  if (key == korg.key.PART_MUTE) held = on && !shift ? 1 : 0;
  for (let i = 0; i < MODES.length; i++) {
    if (key == MODES[i]) held = 0;
  }
});

korg.onEvent("buttonRelease", (key) => {
  if (key == korg.key.SHIFT) shift = 0;
  if (key != korg.key.PART_MUTE || !held) return;
  held = 0;
  if (on) korg.pressKey(korg.key.TRIGGER);
});

korg.onEvent("menu", (id, value) => {
  if (id != page) return;
  on = value;
  korg.store.set(0, on);
  korg.store.save();
});
`,
  }),
  Object.freeze({
    id: "gatehold",
    title: "Gate Hold",
    description: text("catalog.gatehold.description"),
    category: text("catalog.category.tools"),
    creator: "Kuhler Buhler",
    added: "2026-11-03",
    controls: [text("catalog.gatehold.control1"), text("catalog.gatehold.control2")],
    source: `// Gate Hold (idea 72): in Gate Arp mode the note stays where the finger first touched, and moving the finger along X picks
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
  if (key == korg.key.SHIFT) shift = 1;
  if (key == korg.key.GATE_ARP && !shift) gate = 1;
  if (key == korg.key.MASTER_FX && !shift) gate = 0;
  if (key == korg.key.TOUCH_SCALE) gate = 0;
  if (!gate) letGo();
});

korg.onEvent("buttonRelease", (key) => {
  if (key == korg.key.SHIFT) shift = 0;
  if (key == korg.key.TOUCHPAD) letGo();
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
`,
  }),
  Object.freeze({
    id: "stepcopy",
    title: "Step Copy",
    description: text("catalog.stepcopy.description"),
    category: text("catalog.category.tools"),
    creator: "Kuhler Buhler",
    added: "2026-11-06",
    controls: [text("catalog.stepcopy.control1"), text("catalog.stepcopy.control2")],
    source: `// Step Copy: copies the steps of one bar of the pattern in RAM into another bar, so a figure recorded once does not have
// to be played in again. The pages in the BLECH menu: STEP COPY FROM the source bar (1 to 4), STEP COPY TO the target bar
// (1 to 4, 0 all bars after the source up to the pattern's length), STEP COPY what to copy (0 nothing, 1 the selected
// part, 2 all 16 parts). The copy runs once the dial has rested on 1 or 2 for 0.6 s, so the values passed on the way
// copy nothing; 0 and back copies again. Steps are copied whole (on, gate, velocity, trigger, the four note places).
// A target bar beyond the pattern's length lengthens the pattern to that bar (the Pattern menu's LENGTH setter).
// A source bar beyond the length copies nothing. Motion data and the part values stay as they are.
const BAR = 192;
let from = korg.store.get(0, 1);
let to = korg.store.get(1, 2);
let mode = 0;
let timer = -1;
let pageFrom = korg.menu.add("STEP COPY FROM", 1, 4, from);
let pageTo = korg.menu.add("STEP COPY TO", 0, 4, to);
let pageGo = korg.menu.add("STEP COPY", 0, 2, 0);
const steps = new Array(BAR);

function copyBar(part, src, dst) {
  korg.read.patternBytes(steps, -1, 2048 + 816 * part + 48 + BAR * src);
  korg.seq.writeSteps(steps, part, 16 * dst);
}

function copyParts(src, dst) {
  if (mode == 2) {
    for (let p = 0; p < 16; p++) copyBar(p, src, dst);
  } else {
    const part = korg.read.part();
    if (part < 16) copyBar(part, src, dst);
  }
}

function run() {
  timer = -1;
  if (mode == 0) return;
  const src = from - 1;
  let bars = korg.current.length;
  if (src >= bars) return;
  if (to > bars) {
    korg.seq.setPatternValue(2, to);
    bars = to;
  }
  if (to == 0) {
    for (let dst = src + 1; dst < bars; dst++) copyParts(src, dst);
  } else if (to - 1 != src) {
    copyParts(src, to - 1);
  }
}

korg.onEvent("menu", (id, value) => {
  if (id == pageFrom) {
    from = value;
    korg.store.set(0, value);
    korg.store.save();
  }
  if (id == pageTo) {
    to = value;
    korg.store.set(1, value);
    korg.store.save();
  }
  if (id == pageGo) {
    mode = value;
    korg.cancel(timer);
    timer = korg.after(600, run);
  }
});
`,
  }),
  Object.freeze({
    id: "pattern303",
    title: "303Pattern",
    description: text("catalog.pattern303.description"),
    category: text("catalog.category.tools"),
    creator: "Crank",
    added: "2026-11-10",
    controls: [text("catalog.pattern303.control1"), text("catalog.pattern303.control2")],
    source: `// 303Pattern: generator (14 scales, accent / slide / tie), step locks, in-app menu
// writes to the sequencer and lights the pads of the steps with a note
korg.app("303Pattern", "TOOLS");

const CLEAR_FIRST = 0;  // 1 = always clearPart() before writing
                        // 0 = only after the density changed
const VEL = 100;        // velocity of a normal step
const VEL_ACC = 127;    // velocity of an accented step
const KNOB_GATE = 8;    // index of the decay knob (by the docs' knob order)
const DEBUG_KNOB = 0;   // 1 = show the index of the knob you turn, set back to 0 when done
const BOXES = 4;        // boxes drawn per frame (1, 2, 4 or 8); lower it if FUEL comes back
const NIT = 9;          // items in the in-app menu

// 14 scales x 12 semitones (1 = in scale), relative to the root
// 0 chromatic, 1 major, 2 nat minor, 3 harm minor, 4 dorian, 5 phrygian,
// 6 lydian, 7 mixolydian, 8 locrian, 9 min pent, 10 maj pent, 11 blues,
// 12 goa (phrygian dominant), 13 whole tone
const mask = [1,1,1,1,1,1,1,1,1,1,1,1,
              1,0,1,0,1,1,0,1,0,1,0,1,
              1,0,1,1,0,1,0,1,1,0,1,0,
              1,0,1,1,0,1,0,1,1,0,0,1,
              1,0,1,1,0,1,0,1,0,1,1,0,
              1,1,0,1,0,1,0,1,1,0,1,0,
              1,0,1,0,1,0,1,1,0,1,0,1,
              1,0,1,0,1,1,0,1,0,1,1,0,
              1,1,0,1,0,1,1,0,1,0,1,0,
              1,0,0,1,0,1,0,1,0,0,1,0,
              1,0,1,0,1,0,0,1,0,1,0,0,
              1,0,0,1,0,1,1,1,0,0,1,0,
              1,1,0,0,1,1,0,1,1,0,1,0,
              1,0,1,0,1,0,1,0,1,0,1,0];
const wt = [100,100,100,100,100,100,100,100,100,100,100,100];

// the notes of the current scale, built once per generation
const deg = new Array(12);
let ndeg = 0;
let total = 0;

// the 16 steps: pitch row (0-11), octave window (1-3), flags
const row = new Array(16);
const win = new Array(16);
const gate = new Array(16);
const acc = new Array(16);
const sld = new Array(16);
const tie = new Array(16);
const lock = new Array(16);  // 1 = step is locked, generation leaves it alone
const lit = new Array(16);   // pad LED state last sent: 0 off, 1 red, 2 blue, 3 dim blue, 9 unknown

let sc = 12;
let root = 6;      // F#
let dens = 100;    // percent chance that a step has a note
let slidePc = 25;
let tiePc = 0;
let accPc = 2;
let gateOn = 48;   // gate time 1-96, default until the knob is moved
let autoWrite = 0; // 1 = every new pattern is written at once, 0 = key 3 writes
let needClear = 0; // 1 = density changed since the last write
let seed = 1;
let pos = 0;
let isOpen = 0;
let drawIdx = 20;  // 0-15 next box, 16 = bottom line, 20 = nothing to draw
let ledIdx = 16;   // 0 or 8 = next group of 8 pads to send, 16 = nothing to send
let written = 0;   // 1 = the sequencer holds the pattern shown
let menuOn = 0;    // 1 = the in-app menu is shown
let menuDirty = 0; // 1 = the menu needs redrawing
let msel = 0;      // selected menu item
let mtop = 0;      // first visible menu item

let mScale = korg.menu.add("SCALE 0-13", 0, 13, 12);
let mRoot = korg.menu.add("ROOT 0-11", 0, 11, 6);
let mDens = korg.menu.add("DENS 0-100", 0, 100, 100);
let mSlide = korg.menu.add("SLIDE 0-100", 0, 100, 25);
let mTie = korg.menu.add("TIE 0-100", 0, 100, 0);
let mAcc = korg.menu.add("ACCENT 0-100", 0, 100, 2);

function rnd(n) {
  seed = seed * 1103515245 + 12345;
  // multiply-and-shift instead of % n: same range 0..n-1, no division
  return (((seed >> 16) & 0x7FFF) * n) >> 15;
}

function clamp(v, lo, hi) {
  if (v < lo) return lo;
  if (v > hi) return hi;
  return v;
}

function buildScale() {
  ndeg = 0;
  total = 0;
  let k = 0;
  while (k < 12) {
    if (mask[sc * 12 + k] == 1) {
      deg[ndeg] = k;
      ndeg += 1;
      total += wt[k];
    }
    k += 1;
  }
}

// weighted pick of a pitch row from the scale, then the octave:
// 70% window 2, 15% window 1, 15% window 3
function pickPitch(i) {
  let r = rnd(total);
  let k = 0;
  while (k < ndeg - 1) {
    let w = wt[deg[k]];
    if (r < w) break;
    r -= w;
    k += 1;
  }
  row[i] = deg[k];
  let o = rnd(100);
  win[i] = 2;
  if (o >= 70) win[i] = 1;
  if (o >= 85) win[i] = 3;
}

// a tie needs a gate on the step before and takes over its pitch
// (locked steps are never touched)
function fixTies() {
  let i = 0;
  while (i < 16) {
    if (tie[i] == 1 && lock[i] == 0) {
      if (i == 0) tie[i] = 0;
      else if (gate[i - 1] == 0) tie[i] = 0;
      else { row[i] = row[i - 1]; win[i] = win[i - 1]; }
    }
    i += 1;
  }
}

// new rhythm, new notes, new flags (one pass over the unlocked steps)
function generate() {
  seed = korg.millis() + 1;
  buildScale();
  let i = 0;
  while (i < 16) {
    if (lock[i] == 0) {
      gate[i] = 0;
      acc[i] = 0;
      sld[i] = 0;
      tie[i] = 0;
      row[i] = 0;
      win[i] = 2;
      if (rnd(100) < dens) {
        gate[i] = 1;
        pickPitch(i);
        if (rnd(100) < accPc) acc[i] = 1;
        if (i < 15) {
          if (rnd(100) < slidePc) sld[i] = 1;
        }
        if (i > 0 && tiePc > 0) {
          if (gate[i - 1] == 1) {
            if (rnd(100) < tiePc) tie[i] = 1;
          }
        }
      }
    }
    i += 1;
  }
  fixTies();
  written = 0;
  drawIdx = 0;
  ledIdx = 0;
}

// new notes, same rhythm (locked steps keep theirs)
function randomizeNotes() {
  seed = korg.millis() + 1;
  buildScale();
  let has = 0;
  let i = 0;
  while (i < 16) {
    if (gate[i] == 1) has = 1;
    i += 1;
  }
  if (has == 0) {
    i = 0;
    while (i < 16) {
      if (lock[i] == 0) {
        if (rnd(100) < dens) gate[i] = 1;
      }
      i += 1;
    }
  }
  i = 0;
  while (i < 16) {
    if (gate[i] == 1 && tie[i] == 0 && lock[i] == 0) pickPitch(i);
    i += 1;
  }
  fixTies();
  written = 0;
  drawIdx = 0;
  ledIdx = 0;
}

// moves the root and keeps the absolute pitch of the locked notes
function setRoot(r) {
  let d = root - r;
  let i = 0;
  while (i < 16) {
    if (lock[i] == 1) {
      let q = row[i] + d;
      let w = win[i];
      if (q < 0) { q += 12; w -= 1; }
      if (q > 11) { q -= 12; w += 1; }
      row[i] = q;
      win[i] = w;
    }
    i += 1;
  }
  root = r;
}

function unlockAll() {
  let i = 0;
  while (i < 16) {
    lock[i] = 0;
    i += 1;
  }
  drawIdx = 0;
  ledIdx = 0;
}

// gate time of step i: the knob value, or a full gate when the next step is tied
function gateFor(i) {
  let g = gateOn;
  if (i < 15) {
    if (tie[i + 1] == 1) g = 96;
  }
  return g;
}

// writes the 16 generated steps into the selected part;
// the part is cleared first when the density changed since the last write
function writeAll() {
  let part = korg.read.part();
  if (part > 15) part = 0;    // "all parts" (16) is not a part
  if (CLEAR_FIRST == 1 || needClear == 1) korg.seq.clearPart(part);
  needClear = 0;
  let i = 0;
  while (i < 16) {
    if (gate[i] == 1) {
      let note = 12 * (win[i] + 1) + root + row[i];
      let vel = VEL;
      if (acc[i] == 1) vel = VEL_ACC;
      korg.seq.setStep(part, i, note, vel);
      korg.seq.setGate(part, i, gateFor(i));
    } else {
      korg.seq.setGate(part, i, 0);
    }
    i += 1;
  }
  written = 1;
}

// only the gate times, for the knob: notes and velocities stay as they are
function writeGates() {
  let part = korg.read.part();
  if (part > 15) part = 0;
  let i = 0;
  while (i < 16) {
    if (gate[i] == 1) korg.seq.setGate(part, i, gateFor(i));
    i += 1;
  }
}

function regen() {
  generate();
  if (autoWrite == 1) writeAll();
}

function regenNotes() {
  randomizeNotes();
  if (autoWrite == 1) writeAll();
}

function scaleName(x, y) {
  if (sc == 0) korg.display.text("CHROMATIC", x, y);
  else if (sc == 1) korg.display.text("MAJOR", x, y);
  else if (sc == 2) korg.display.text("NAT MINOR", x, y);
  else if (sc == 3) korg.display.text("HARM MINOR", x, y);
  else if (sc == 4) korg.display.text("DORIAN", x, y);
  else if (sc == 5) korg.display.text("PHRYGIAN", x, y);
  else if (sc == 6) korg.display.text("LYDIAN", x, y);
  else if (sc == 7) korg.display.text("MIXOLYDIAN", x, y);
  else if (sc == 8) korg.display.text("LOCRIAN", x, y);
  else if (sc == 9) korg.display.text("MIN PENT", x, y);
  else if (sc == 10) korg.display.text("MAJ PENT", x, y);
  else if (sc == 11) korg.display.text("BLUES", x, y);
  else if (sc == 12) korg.display.text("GOA", x, y);
  else korg.display.text("WHOLE TONE", x, y);
}

function rootName(x, y) {
  if (root == 0) korg.display.text("C", x, y);
  else if (root == 1) korg.display.text("C#", x, y);
  else if (root == 2) korg.display.text("D", x, y);
  else if (root == 3) korg.display.text("D#", x, y);
  else if (root == 4) korg.display.text("E", x, y);
  else if (root == 5) korg.display.text("F", x, y);
  else if (root == 6) korg.display.text("F#", x, y);
  else if (root == 7) korg.display.text("G", x, y);
  else if (root == 8) korg.display.text("G#", x, y);
  else if (root == 9) korg.display.text("A", x, y);
  else if (root == 10) korg.display.text("A#", x, y);
  else korg.display.text("B", x, y);
}

// note name without octave, centred in a 15 px box
function pcName(p, bx, y) {
  if (p == 0) korg.display.text("C", bx + 5, y);
  else if (p == 1) korg.display.text("C#", bx + 2, y);
  else if (p == 2) korg.display.text("D", bx + 5, y);
  else if (p == 3) korg.display.text("D#", bx + 2, y);
  else if (p == 4) korg.display.text("E", bx + 5, y);
  else if (p == 5) korg.display.text("F", bx + 5, y);
  else if (p == 6) korg.display.text("F#", bx + 2, y);
  else if (p == 7) korg.display.text("G", bx + 5, y);
  else if (p == 8) korg.display.text("G#", bx + 2, y);
  else if (p == 9) korg.display.text("A", bx + 5, y);
  else if (p == 10) korg.display.text("A#", bx + 2, y);
  else korg.display.text("B", bx + 5, y);
}

// pad LEDs of 8 steps, only the ones that changed (max 16 packets):
// unlocked note = red, locked note = blue, locked rest = dim blue
function ledPads(a) {
  let i = a;
  while (i < a + 8) {
    let want = gate[i];
    if (lock[i] == 1) {
      if (gate[i] == 1) want = 2;
      else want = 3;
    }
    if (lit[i] != want) {
      lit[i] = want;
      let r = 0;
      if (want == 1) r = 255;
      let b = 0;
      if (want == 2) b = 255;
      if (want == 3) b = 40;
      korg.led(korg.led.PAD_1_RED + 2 * i, r);
      korg.led(korg.led.PAD_1_BLUE + 2 * i, b);
    }
    i += 1;
  }
}

// one step as a 15 x 20 box: note name on top, octave number below.
// locked = bold top and bottom edge, accent = block left of the octave,
// slide = block right of it, tie = mark in the gap to the left
function drawBox(i) {
  let bx = (i % 8) * 16;
  let by = 10;
  if (i >= 8) by = 32;
  if (gate[i] == 1 || lock[i] == 1) {
    korg.display.rect(bx, by, 15, 20);
    korg.display.clearRect(bx + 1, by + 1, 13, 18);
    if (lock[i] == 1) {
      korg.display.rect(bx, by, 15, 2);
      korg.display.rect(bx, by + 18, 15, 2);
    }
  }
  if (gate[i] == 1) {
    let n = 12 * (win[i] + 1) + root + row[i];
    pcName(n % 12, bx, by + 3);
    korg.display.number(n / 12 - 1, bx + 5, by + 11);
    if (acc[i] == 1) korg.display.rect(bx + 1, by + 13, 3, 4);
    if (sld[i] == 1) korg.display.rect(bx + 11, by + 15, 3, 2);
    if (tie[i] == 1 && i % 8 > 0) korg.display.rect(bx - 1, by + 9, 1, 2);
  } else {
    korg.display.rect(bx + 5, by + 9, 5, 2);
  }
}

// one box on its own, after a lock change
function redrawBox(i) {
  let bx = (i % 8) * 16;
  let by = 10;
  if (i >= 8) by = 32;
  korg.display.clearRect(bx, by, 15, 20);
  drawBox(i);
}

// the moving part: just the playhead bar (3 display calls)
function drawHead() {
  korg.display.clearRect(0, 30, 128, 2);
  korg.display.clearRect(0, 52, 128, 2);
  let bx = (pos % 8) * 16;
  if (pos < 8) korg.display.rect(bx, 30, 15, 2);
  else korg.display.rect(bx, 52, 15, 2);
}

function drawTop() {
  korg.display.clear();
  scaleName(4, 1);
  korg.display.text("ROOT", 70, 1);
  rootName(100, 1);
}

function drawBottom() {
  korg.display.textNumber("DENS ", dens, 4, 55);
  korg.display.text("TAP", 105, 55);
  drawHead();
}

// ---- in-app menu ----

function menuLabel(it, y) {
  if (it == 0) korg.display.text("SCALE", 12, y);
  else if (it == 1) korg.display.text("ROOT", 12, y);
  else if (it == 2) korg.display.text("DENS", 12, y);
  else if (it == 3) korg.display.text("SLIDE", 12, y);
  else if (it == 4) korg.display.text("TIE", 12, y);
  else if (it == 5) korg.display.text("ACCENT", 12, y);
  else if (it == 6) korg.display.text("GATE", 12, y);
  else if (it == 7) korg.display.text("AUTO", 12, y);
  else korg.display.text("UNLOCK", 12, y);
}

function menuValue(it, y) {
  if (it == 0) scaleName(54, y);
  else if (it == 1) rootName(54, y);
  else if (it == 2) korg.display.number(dens, 54, y);
  else if (it == 3) korg.display.number(slidePc, 54, y);
  else if (it == 4) korg.display.number(tiePc, 54, y);
  else if (it == 5) korg.display.number(accPc, 54, y);
  else if (it == 6) korg.display.number(gateOn, 54, y);
  else if (it == 7) {
    if (autoWrite == 1) korg.display.text("ON", 54, y);
    else korg.display.text("OFF", 54, y);
  } else korg.display.text("TAP", 54, y);
}

function drawMenu() {
  menuDirty = 0;
  korg.display.clear();
  korg.display.text("303 MENU", 4, 1);
  korg.display.text("MENU=BACK", 66, 1);
  let r = 0;
  while (r < 5) {
    let it = mtop + r;
    let y = 12 + 9 * r;
    if (it < NIT) {
      if (it == msel) korg.display.text(">", 4, y);
      menuLabel(it, y);
      menuValue(it, y);
    }
    r += 1;
  }
  // scrollbar (sized for 9 items, 5 visible)
  korg.display.rect(127, 12, 1, 43);
  korg.display.rect(125, 12 + 5 * mtop, 3, 23);
}

// d = -1 or +1
function menuAdjust(d) {
  if (msel == 0) { sc = (sc + 14 + d) % 14; regen(); }
  else if (msel == 1) { setRoot((root + 12 + d) % 12); regen(); }
  else if (msel == 2) { dens = clamp(dens + 5 * d, 0, 100); needClear = 1; regen(); }
  else if (msel == 3) { slidePc = clamp(slidePc + 5 * d, 0, 100); regen(); }
  else if (msel == 4) { tiePc = clamp(tiePc + 5 * d, 0, 100); regen(); }
  else if (msel == 5) { accPc = clamp(accPc + d, 0, 100); regen(); }
  else if (msel == 6) {
    gateOn = clamp(gateOn + 4 * d, 1, 96);
    if (written == 1) writeGates();
  }
  else if (msel == 7) autoWrite = 1 - autoWrite;
}

// ---- events ----

// all steps start unlocked
korg.onEvent("ready", () => {
  let i = 0;
  while (i < 16) {
    lock[i] = 0;
    i += 1;
  }
});

// the BLECH menu pages only preview, they never write
korg.onEvent("menu", (id, value) => {
  if (id == mScale) sc = value;
  if (id == mRoot) setRoot(value);
  if (id == mDens) { dens = value; needClear = 1; }
  if (id == mSlide) slidePc = value;
  if (id == mTie) tiePc = value;
  if (id == mAcc) accPc = value;
  generate();
});

// while the app is open it owns the panel LEDs
korg.onEvent("open", () => {
  isOpen = 1;
  menuOn = 0;
  menuDirty = 0;
  msel = 0;
  mtop = 0;
  korg.ledHold(1);
  let i = 0;
  while (i < 16) {
    lit[i] = 9;      // unknown, so all 16 pads are sent once
    i += 1;
  }
  generate();
});

korg.onEvent("close", () => {
  isOpen = 0;
  menuOn = 0;
  korg.ledHold(0);
});

// pressing a pad locks or unlocks that step
korg.onEvent("pad", (index, down) => {
  if (isOpen == 1 && menuOn == 0 && down == 1 && index < 16) {
    lock[index] = 1 - lock[index];
    redrawBox(index);
    ledIdx = 0;
  }
});

// the menu, or the screen built over several frames (top, BOXES boxes per
// frame, bottom), then the pad LEDs, 8 pads per frame
korg.onEvent("frame", () => {
  if (isOpen == 1) {
    if (menuOn == 1) {
      if (menuDirty == 1) {
        drawMenu();
      } else if (ledIdx < 16) {
        ledPads(ledIdx);
        ledIdx += 8;
      }
    } else if (drawIdx < 20) {
      if (drawIdx == 0) drawTop();
      if (drawIdx < 16) {
        let n = 0;
        while (n < BOXES) {
          drawBox(drawIdx + n);
          n += 1;
        }
        drawIdx += BOXES;
      } else {
        drawBottom();
        drawIdx = 20;
      }
    } else if (ledIdx < 16) {
      ledPads(ledIdx);
      ledIdx += 8;
    }
  }
});

// the knob sets the gate length, 0-1023 mapped to 1-96;
// it only goes to the sequencer after the shown pattern has been written
korg.onEvent("knob", (index, value) => {
  if (DEBUG_KNOB == 1 && isOpen == 1 && menuOn == 0) {
    korg.display.clearRect(58, 55, 42, 7);
    korg.display.textNumber("KNOB ", index, 58, 55);
  }
  if (index == KNOB_GATE) {
    gateOn = 1 + value * 95 / 1023;
    if (menuOn == 1) menuDirty = 1;
    if (isOpen == 1 && written == 1) writeGates();
  }
});

korg.onEvent("buttonPress", (key) => {
  if (isOpen == 1) {
    if (key == korg.key.MENU) {
      menuOn = 1 - menuOn;
      menuDirty = 1;
      if (menuOn == 0) drawIdx = 0;    // rebuild the main screen
    } else if (menuOn == 1) {
      if (key == korg.key.PART_LEFT) msel = (msel + NIT - 1) % NIT;
      if (key == korg.key.PART_RIGHT) msel = (msel + 1) % NIT;
      if (key == korg.key.EDIT_LEFT) menuAdjust(-1);
      if (key == korg.key.EDIT_RIGHT) menuAdjust(1);
      if (key == korg.key.TAP && msel == 8) unlockAll();
      if (msel < mtop) mtop = msel;
      if (msel > mtop + 4) mtop = msel - 4;
      menuDirty = 1;
    } else {
      if (key == korg.key.TAP) regen();
      if (key == korg.key.BAR_4) regenNotes();
      if (key == korg.key.BAR_3) writeAll();
      if (key == korg.key.PART_RIGHT) { sc = (sc + 1) % 14; regen(); }
      if (key == korg.key.PART_LEFT) { sc = (sc + 13) % 14; regen(); }
      if (key == korg.key.EDIT_RIGHT) { setRoot((root + 1) % 12); regen(); }
      if (key == korg.key.EDIT_LEFT) { setRoot((root + 11) % 12); regen(); }
      if (key == korg.key.BAR_2) { dens += 10; if (dens > 100) dens = 100; needClear = 1; regen(); }
      if (key == korg.key.BAR_1) { dens -= 10; if (dens < 0) dens = 0; needClear = 1; regen(); }
    }
  }
});

korg.onEvent("step", (s) => {
  pos = s % 16;
  if (isOpen == 1 && menuOn == 0 && drawIdx == 20) drawHead();
});
`,
  }),
  Object.freeze({
    id: "euclidflow",
    title: "EUCLID FLOW",
    description: text("catalog.euclidflow.description"),
    category: text("catalog.category.tools"),
    creator: "SLTK023",
    added: "2026-11-12",
    controls: [text("catalog.euclidflow.control1"), text("catalog.euclidflow.control2")],
    source: `/*
 * EUCLID FLOW V1
 * Euclidean Rhythm Generator
 * Korg Electribe 2 / BLECHTRIBE
 * API 9 minimum
 *
 * From SLTK023 on the BLECH Discord. In the catalog the keys act only while the app is open (opened): the handlers of an
 * app run from the start, and TAP with the app closed would otherwise write the rhythm into the part.
 */

korg.app("EUCLID FLOW", "TOOLS");

let opened = 0;
let part = 0;
let hits = 5;
let rotation = 0;
let steps = 16;
let velocity = 100;
let gate = 96;

// Actualise la longueur du pattern
function updateSteps() {
    steps = korg.current.length * 16;

    if (steps < 16) steps = 16;
    if (steps > 64) steps = 64;

    if (hits > steps) hits = steps;
    if (rotation >= steps) rotation = 0;
}

// Affichage sur l'écran de la Korg
function draw() {
    updateSteps();

    korg.display.clear();

    korg.display.text("EUCLID FLOW", 4, 2);

    korg.display.text("PART", 4, 14);
    korg.display.number(part + 1, 38, 14);

    korg.display.text("HITS", 68, 14);
    korg.display.number(hits, 100, 14);

    korg.display.text("STEPS", 4, 26);
    korg.display.number(steps, 44, 26);

    korg.display.text("ROT", 68, 26);
    korg.display.number(rotation, 96, 26);

    korg.display.text("VEL", 4, 38);
    korg.display.number(velocity, 36, 38);

    korg.display.text("GATE", 68, 38);
    korg.display.number(gate, 100, 38);

    korg.display.text("EDIT = HITS", 4, 50);
    korg.display.text("TAP = GENERATE", 4, 58);
}

// Générateur euclidien
function generate() {
    updateSteps();

    let bucket = 0;

    // Efface les déclenchements de cette piste
    korg.seq.clearPart(part);

    for (let i = 0; i < steps; i++) {

        bucket += hits;

        if (bucket >= steps) {
            bucket -= steps;

            let position = i + rotation;

            if (position >= steps) {
                position -= steps;
            }

            let note = 48 + korg.current.key;

            korg.seq.setStep(
                part,
                position,
                note,
                velocity
            );

            korg.seq.setGate(
                part,
                position,
                gate
            );
        }
    }

    draw();
}

// Ouverture de l'application
korg.onEvent("open", () => {
    opened = 1;
    part = korg.selectedPart;

    if (part > 15) {
        part = 0;
    }

    draw();
});

korg.onEvent("close", () => {
    opened = 0;
});

// Commandes physiques
korg.onEvent("buttonPress", (key) => {
    if (opened == 0) return;

    // Choix de la piste
    if (key == korg.key.PART_LEFT) {
        part--;

        if (part < 0) {
            part = 15;
        }

        korg.part(part);
    }

    if (key == korg.key.PART_RIGHT) {
        part++;

        if (part > 15) {
            part = 0;
        }

        korg.part(part);
    }

    // Nombre de coups
    if (key == korg.key.EDIT_LEFT) {
        hits--;

        if (hits < 1) {
            hits = 1;
        }
    }

    if (key == korg.key.EDIT_RIGHT) {
        hits++;

        if (hits > steps) {
            hits = steps;
        }
    }

    // Rotation du rythme
    if (key == korg.key.GATE_ARP) {
        rotation++;

        if (rotation >= steps) {
            rotation = 0;
        }
    }

    if (key == korg.key.MASTER_FX) {
        rotation--;

        if (rotation < 0) {
            rotation = steps - 1;
        }
    }

    // Génération
    if (key == korg.key.TAP) {
        generate();
    }

    draw();
});`,
  }),
  Object.freeze({
    id: "livereload",
    title: "LIVE RELOAD",
    description: text("catalog.livereload.description"),
    category: text("catalog.category.tools"),
    creator: "handst0n3",
    added: "2026-11-12",
    controls: [text("catalog.livereload.control1"), text("catalog.livereload.control2")],
    source: `// LIVE RELOAD v0.2 by handst0n3, from the BLECH Discord: restores the sound values of all 16 parts to the saved pattern
// without stopping playback. SHIFT + BAR 1 hard, SHIFT + BAR 2 smooth.
korg.app("LIVE RELOAD", "TOOLS");

const fields = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15, 16, 18];
const before = new Array(240);
const target = new Array(240);

let opened = 0;
let shiftHeld = 0;
let running = 0;
let stage = 0;
let position = 0;
let blendFrame = 0;
let sourcePattern = -1;
let result = 0;

function isSmooth(field) {
  return field == 2 || field == 3 || field == 4 ||
         field == 8 || field == 9 || field == 10 || field == 11;
}

function drawScreen() {
  if (opened == 0) return;
  korg.display.clear();
  korg.display.text("LIVE RELOAD V0.2", 4, 2);
  korg.display.text("SHIFT + BAR 1: HARD", 4, 17);
  korg.display.text("SHIFT + BAR 2: SOFT", 4, 30);

  if (running == 1) korg.display.text("RESTORING...", 4, 45);
  else if (running == 2) korg.display.text("MORPHING...", 4, 45);
  else if (result == 1) korg.display.text("DONE", 4, 45);
  else if (result == 2) korg.display.text("CANCELLED", 4, 45);
  else korg.display.text("READY", 4, 45);
}

function abortReload() {
  running = 0;
  result = 2;
  drawScreen();
}

function finishReload() {
  running = 0;
  result = 1;
  drawScreen();
}

function beginReload(which) {
  sourcePattern = korg.read.pattern();
  stage = 0;
  position = 0;
  blendFrame = 0;
  result = 0;
  running = which;
  drawScreen();
}

function hardFrame() {
  for (let n = 0; n < 2; n += 1) {
    if (position >= 16) break;

    for (let j = 0; j < 15; j += 1) {
      let field = fields[j];
      let savedValue = korg.read.patternValue(
        sourcePattern, position, field
      );
      let liveValue = korg.read.patternValue(
        -1, position, field
      );

      if (liveValue != savedValue) {
        korg.seq.setPartValue(position, field, savedValue);
      }
    }
    position += 1;
  }

  if (position >= 16) finishReload();
}

function softFrame() {
  if (stage == 0) {
    for (let n = 0; n < 4; n += 1) {
      if (position >= 16) break;

      for (let j = 0; j < 15; j += 1) {
        let idx = position * 15 + j;
        let field = fields[j];

        before[idx] = korg.read.patternValue(
          -1, position, field
        );
        target[idx] = korg.read.patternValue(
          sourcePattern, position, field
        );
      }
      position += 1;
    }

    if (position >= 16) {
      stage = 1;
      blendFrame = 0;
    }
    return;
  }

  let group = blendFrame % 4;
  let fraction = (blendFrame - group) / 4 + 1;
  let firstPart = group * 4;

  for (let part = firstPart; part < firstPart + 4; part += 1) {
    for (let j = 0; j < 15; j += 1) {
      let field = fields[j];
      let idx = part * 15 + j;
      let value = target[idx];

      if (isSmooth(field)) {
        value = before[idx] +
          (target[idx] - before[idx]) * fraction / 3;
      } else if (fraction != 3) {
        continue;
      }

      if (korg.read.patternValue(-1, part, field) != value) {
        korg.seq.setPartValue(part, field, value);
      }
    }
  }

  blendFrame += 1;
  if (blendFrame >= 12) finishReload();
}

korg.onEvent("open", () => {
  opened = 1;
  shiftHeld = 0;
  result = 0;
  drawScreen();
});

korg.onEvent("close", () => {
  opened = 0;
  shiftHeld = 0;
  running = 0;
});

korg.onEvent("patternChange", () => {
  if (running != 0) abortReload();
});

korg.onEvent("buttonPress", (key) => {
  if (opened == 0) return;

  if (key == korg.key.SHIFT) shiftHeld = 1;

  if (shiftHeld == 1 && key == korg.key.BAR_1) {
    beginReload(1);
  }

  if (shiftHeld == 1 && key == korg.key.BAR_2) {
    beginReload(2);
  }
});

korg.onEvent("buttonRelease", (key) => {
  if (key == korg.key.SHIFT) shiftHeld = 0;
});

korg.onEvent("frame", () => {
  if (running == 0) return;

  if (korg.read.pattern() != sourcePattern) {
    abortReload();
    return;
  }

  if (running == 1) hardFrame();
  else softFrame();
});
`,
  }),
  Object.freeze({
    id: "randomslot",
    title: "RANDOM SLOT",
    description: text("catalog.randomslot.description"),
    category: text("catalog.category.tools"),
    creator: "handst0n3",
    added: "2026-11-12",
    controls: [text("catalog.randomslot.control1"), text("catalog.randomslot.control2")],
    source: `korg.app("RANDOM SLOT", "TOOLS");

// RANDOM SLOT V0.5 by handst0n3, from the BLECH Discord
// BLECHTRIBE API 14+
// Single part randomizer
// No automatic mode

const soundFields = [
  1, 2, 3, 4, 5,
  6, 7, 8, 9, 10,
  11, 14, 15, 16, 18
];

const soundLow = [
  0, 0, 0, -63, 0,
  0, 0, 0, 0, 0,
  -63, 0, -63, 0, 0
];

const soundHigh = [
  16, 127, 127, 63, 71,
  127, 127, 127, 127, 127,
  63, 127, 63, 127, 127
];

const variationFields = [
  2, 3, 4, 6, 7, 8,
  9, 10, 11, 14, 15, 16, 18
];

const variationLow = [
  0, 0, -63, 0, 0, 0,
  0, 0, -63, 0, -63, 0, 0
];

const variationHigh = [
  127, 127, 63, 127, 127, 127,
  127, 127, 63, 127, 63, 127, 127
];

const savedMutes = new Array(16);

let opened = 0;
let selectedPart = 0;
let targetPart = 0;
let soloActive = 0;

let selectedMode = 1;
let activeMode = 0;

let spinFrame = 0;
let workIndex = 0;
let finished = 0;

let reelA = 0;
let reelB = 1;
let reelC = 2;

let sourcePattern = -1;
let seed = 1234567;
let frameCounter = 0;

// RANDOM ENGINE

function rnd(maximum) {
  seed = (
    seed * 1664525 + 1013904223
  ) & 2147483647;

  if (maximum <= 1) return 0;
  return seed % maximum;
}

function between(a, b) {
  return a + rnd(b - a + 1);
}

function clamp(value, a, b) {
  if (value < a) return a;
  if (value > b) return b;
  return value;
}

// DISPLAY

function outline(x, y, w, h) {
  korg.display.rect(x, y, w, 1);
  korg.display.rect(x, y + h - 1, w, 1);
  korg.display.rect(x, y, 1, h);
  korg.display.rect(x + w - 1, y, 1, h);
}

function drawStar(x, y) {
  korg.display.rect(x + 9, y, 2, 4);
  korg.display.rect(x + 8, y + 4, 4, 2);
  korg.display.rect(x + 3, y + 6, 14, 2);
  korg.display.rect(x + 5, y + 8, 10, 2);
  korg.display.rect(x + 6, y + 10, 8, 2);
  korg.display.rect(x + 4, y + 12, 4, 2);
  korg.display.rect(x + 12, y + 12, 4, 2);
  korg.display.rect(x + 3, y + 14, 3, 2);
  korg.display.rect(x + 14, y + 14, 3, 2);
}

function drawCherry(x, y) {
  korg.display.rect(x + 9, y, 2, 5);
  korg.display.rect(x + 5, y + 4, 5, 2);
  korg.display.rect(x + 10, y + 4, 5, 2);
  korg.display.rect(x + 3, y + 8, 6, 6);
  korg.display.rect(x + 11, y + 8, 6, 6);
  korg.display.rect(x + 4, y + 7, 4, 1);
  korg.display.rect(x + 12, y + 7, 4, 1);
}

function drawBell(x, y) {
  korg.display.rect(x + 8, y + 1, 4, 2);
  korg.display.rect(x + 5, y + 3, 10, 2);
  korg.display.rect(x + 4, y + 5, 12, 6);
  korg.display.rect(x + 2, y + 11, 16, 2);
  korg.display.rect(x + 7, y + 13, 6, 2);
  korg.display.rect(x + 8, y + 15, 4, 1);
}

function drawMoney(x, y) {
  outline(x + 1, y + 3, 19, 12);
  outline(x + 4, y + 5, 13, 8);
  korg.display.rect(x + 7, y + 8, 6, 3);
  korg.display.pixel(x + 3, y + 6, 1);
  korg.display.pixel(x + 17, y + 12, 1);
}

function drawJackpot(x, y) {
  korg.display.text("777", x + 1, y + 4);
  korg.display.rect(x + 1, y + 14, 19, 1);
}

function drawSymbol(kind, x, y) {
  if (kind == 0) drawStar(x, y);
  else if (kind == 1) drawCherry(x, y);
  else if (kind == 2) drawBell(x, y);
  else if (kind == 3) drawMoney(x, y);
  else drawJackpot(x, y);
}

function spinReels() {
  reelA = rnd(5);
  reelB = rnd(5);
  reelC = rnd(5);
}

function drawScreen() {
  if (opened == 0) return;

  korg.display.clear();
  korg.display.text("RANDOM SLOT", 30, 2);

  outline(4, 13, 38, 23);
  outline(45, 13, 38, 23);
  outline(86, 13, 38, 23);

  drawSymbol(reelA, 13, 16);
  drawSymbol(reelB, 54, 16);
  drawSymbol(reelC, 95, 16);

  if (selectedMode == 1) {
    korg.display.text("SOUND", 4, 39);
  } else if (selectedMode == 2) {
    korg.display.text("MELODY", 4, 39);
  } else if (selectedMode == 3) {
    korg.display.text("S-VAR", 4, 39);
  } else {
    korg.display.text("P-VAR", 4, 39);
  }

  korg.display.text("P:", 52, 39);
  korg.display.number(selectedPart + 1, 66, 39);

  if (soloActive == 1) {
    korg.display.text("SOLO", 96, 39);
  }

  if (activeMode != 0) {
    korg.display.text("SPINNING", 4, 54);
  } else if (finished == 1) {
    korg.display.text("DONE - READY", 4, 54);
  } else {
    korg.display.text("BAR 1-4 TO SPIN", 4, 54);
  }
}

// SOLO MODE

function soloOn() {
  if (soloActive == 1) return;

  for (let i = 0; i < 16; i += 1) {
    savedMutes[i] = korg.read.mute(i);
  }

  soloActive = 1;

  for (let i = 0; i < 16; i += 1) {
    if (i == selectedPart) {
      korg.mute(i, 0);
    } else {
      korg.mute(i, 1);
    }
  }

  drawScreen();
}

function soloOff() {
  if (soloActive == 0) return;

  soloActive = 0;

  for (let i = 0; i < 16; i += 1) {
    korg.mute(i, savedMutes[i]);
  }

  drawScreen();
}

function toggleSolo() {
  if (soloActive == 0) soloOn();
  else soloOff();
}

function selectPart(part) {
  if (part < 0 || part > 15) return;

  selectedPart = part;

  if (soloActive == 1) {
    for (let i = 0; i < 16; i += 1) {
      if (i == selectedPart) {
        korg.mute(i, 0);
      } else {
        korg.mute(i, 1);
      }
    }
  }

  drawScreen();
}

// SOUND RANDOM

function randomSoundField(part, slot) {
  let value = between(
    soundLow[slot],
    soundHigh[slot]
  );

  korg.seq.setPartValue(
    part,
    soundFields[slot],
    value
  );
}

// SOUND VARIATION

function randomSoundVariation(part) {
  let slot = rnd(13);
  let field = variationFields[slot];

  let current = korg.read.patternValue(
    -1, part, field
  );

  let change = between(-7, 7);

  let value = clamp(
    current + change,
    variationLow[slot],
    variationHigh[slot]
  );

  if (value != current) {
    korg.seq.setPartValue(
      part, field, value
    );
  }
}

// MELODY RANDOM

function randomMelodyChunk(part, firstStep) {
  for (let i = 0; i < 8; i += 1) {
    let step = firstStep + i;

    if (rnd(100) < 60) {
      let note = between(36, 84);
      let velocity = between(55, 127);
      let gate = between(25, 95);

      korg.seq.setGate(part, step, gate);

      korg.seq.setStep(
        part, step, note, velocity
      );
    } else {
      korg.seq.setStep(part, step, -1, 0);
    }
  }
}

// PATTERN VARIATION

function randomPatternVariation(part) {
  let step = rnd(64);

  if (rnd(100) < 30) {
    korg.seq.setStep(
      part,
      step,
      between(48, 76),
      between(65, 110)
    );
  } else {
    korg.seq.setGate(
      part,
      step,
      between(35, 96)
    );
  }
}

// START RANDOMIZATION

function startSpin(mode) {
  if (opened == 0) return;
  if (activeMode != 0) return;

  selectedMode = mode;
  activeMode = mode;

  targetPart = selectedPart;
  sourcePattern = korg.read.pattern();

  spinFrame = 0;
  workIndex = 0;
  finished = 0;

  seed = (
    seed +
    frameCounter * 7919 +
    mode * 1237 +
    selectedPart * 311
  ) & 2147483647;

  if (seed == 0) seed = 1234567;

  spinReels();
  drawScreen();
}

// SPIN PROCESS

function performSpin() {
  if (activeMode == 0) return;

  if (korg.read.pattern() != sourcePattern) {
    activeMode = 0;
    finished = 0;
    drawScreen();
    return;
  }

  spinFrame += 1;

  if (spinFrame % 2 == 0) {
    spinReels();
    drawScreen();
  }

  if (spinFrame <= 8) return;

  // BAR 1 : SOUND RANDOM

  if (activeMode == 1) {
    for (let i = 0; i < 3; i += 1) {
      if (workIndex < 15) {
        randomSoundField(
          targetPart,
          workIndex
        );
        workIndex += 1;
      }
    }
  }

  // BAR 2 : MELODY RANDOM

  if (activeMode == 2) {
    if (workIndex < 64) {
      randomMelodyChunk(
        targetPart,
        workIndex
      );
      workIndex += 8;
    }
  }

  // BAR 3 : SOUND VARIATION

  if (activeMode == 3) {
    if (workIndex < 2) {
      randomSoundVariation(targetPart);
      workIndex += 1;
    }
  }

  // BAR 4 : PATTERN VARIATION

  if (activeMode == 4) {
    if (workIndex < 2) {
      randomPatternVariation(targetPart);
      workIndex += 1;
    }
  }

  if (spinFrame >= 24) {
    activeMode = 0;
    finished = 1;
    drawScreen();
  }
}

// EVENTS

korg.onEvent("open", () => {
  opened = 1;
  activeMode = 0;
  finished = 0;

  let part = korg.read.part();

  if (part >= 0 && part < 16) {
    selectedPart = part;
  } else {
    selectedPart = 0;
  }

  korg.padHold(1);
  drawScreen();
});

korg.onEvent("close", () => {
  soloOff();

  opened = 0;
  activeMode = 0;

  korg.padHold(0);
});

korg.onEvent("patternChange", () => {
  activeMode = 0;
  finished = 0;
  soloActive = 0;
  drawScreen();
});

korg.onEvent("buttonPress", (key) => {
  if (opened == 0) return;

  if (key == korg.key.PART_MUTE) {
    toggleSolo();
  }

  if (key == korg.key.BAR_1) {
    startSpin(1);
  }

  if (key == korg.key.BAR_2) {
    startSpin(2);
  }

  if (key == korg.key.BAR_3) {
    startSpin(3);
  }

  if (key == korg.key.BAR_4) {
    startSpin(4);
  }
});

korg.onEvent("pad", (index, down, velocity) => {
  if (opened == 0) return;
  if (down == 0) return;

  selectPart(index);
});

korg.onEvent("frame", () => {
  frameCounter += 1;

  if (activeMode != 0) {
    performSpin();
  }
});
`,
  }),
  Object.freeze({
    id: "betteraccent",
    title: "Better Accent",
    description: text("catalog.betteraccent.description"),
    category: text("catalog.category.tools"),
    creator: "alarykko",
    added: "2026-11-13",
    controls: [text("catalog.betteraccent.control1"), text("catalog.betteraccent.control2")],
    source: `// BETTER ACCENT v2 by alarykko, from the BLECH Discord, inspired by the TD-3-MO: a step with velocity above 96 is an
// accent and opens the filter through EG INT, DECAY and LEVEL. SHIFT + EG INT, DECAY or LEVEL set the accent values of
// the selected part. It acts on parts 1 to 7 only (maxParts = 7): with all 16 the step handler tripped the watchdog.
const baseEgInt = new Array(8);
const baseDecay = new Array(8);
const baseLevel = new Array(8);
//const baseGlide = new Array(8);
const egIntAccAmount = new Array(8);
const decayAccAmount = new Array(8);
const levelAccAmount = new Array(8);
//const glideOnTies = 40;



const maxParts = 7;
const defaultVelocity = 96;
const stepCount = 64;


const levelKnobIndex = 0;
//const pitchGlideKnobIndex = 2;
const egIntKnobIndex = 4;
const decayKnobIndex = 8;


let shiftPress = 0;
let lastMillis = 0;




//setta le basi
function setNewBases(){
  for(let part = 0; part < maxParts; part++){
    baseEgInt[part] = korg.parts[part].egInt;
    baseDecay[part] = korg.parts[part].decay;
    baseLevel[part] = korg.parts[part].level;
    //baseGlide[part] = korg.parts[part].glide;
  }
}


function restoreBases(){
  for(let part = 0; part < maxParts; part++){
    korg.parts[part].egInt = baseEgInt[part];
    korg.parts[part].decay = baseDecay[part];
    korg.parts[part].level = baseLevel[part];
    //korg.parts[part].glide = baseGlide[part];
  }
}

function setAccentedAmounts(){
  for(let part = 0; part < maxParts; part++){
    egIntAccAmount[part] = korg.parts[part].egInt;
    decayAccAmount[part] = korg.parts[part].decay;
    levelAccAmount[part] = korg.parts[part].level;
  }
}



function applyAccent(){

  

  for(let part = 0; part < maxParts; part++){

    const currentStep = korg.read.step(part);
    const previousStep = ((currentStep - 1) % stepCount + stepCount) % stepCount;
    const isStepOn = korg.seq.getOn(part, currentStep);
    const stepVelocity = korg.seq.getVelocity(part, currentStep);
    const currentGate = korg.seq.getGate(part, currentStep);
    const previousGate = korg.seq.getGate(part, previousStep);

    //
    if(isStepOn == 1 && stepVelocity > defaultVelocity){ 
      korg.parts[part].egInt = egIntAccAmount[part];
      korg.parts[part].decay = decayAccAmount[part];
      korg.parts[part].level = levelAccAmount[part];
    }
    else if (isStepOn == 1 && stepVelocity <= defaultVelocity){
      korg.parts[part].egInt = baseEgInt[part];
      korg.parts[part].decay = baseDecay[part]; 
      korg.parts[part].level = baseLevel[part];
    }
    /*
    if (currentGate > 96  || previousGate > 96)   {
      korg.parts[part].glide = baseGlide[part] + glideOnTies; 
    }
    else korg.parts[part].glide = baseGlide[part];
    */
  }
}





korg.onEvent("ready", () => {
    setNewBases();
    setAccentedAmounts();
    korg.display.popups(0);
});

korg.onEvent("patternChange", () => {
    setNewBases();
    setAccentedAmounts();
});

korg.onEvent("buttonPress", (key) => {
    
    if(key == korg.key.SHIFT){ 
      shiftPress = 1;
      korg.knobHold(egIntKnobIndex, 1);
      korg.knobHold(decayKnobIndex, 1);
      korg.knobHold(levelKnobIndex, 1);
    }

    if(key == korg.key.STOP){
      restoreBases();
    } 

});


korg.onEvent("buttonRelease", (key) => {

    if(key == korg.key.SHIFT){
      shiftPress = 0;
      korg.knobHold(egIntKnobIndex, 0);
      korg.knobHold(decayKnobIndex, 0);
      korg.knobHold(levelKnobIndex, 0);
    }
});


korg.onEvent("frame", () => {
    if( (korg.millis() - lastMillis) > 50){
      korg.display.release();
    }
    
});




korg.onEvent("step", () => {

    applyAccent();
    
});


korg.onEvent("knob", (index, value) => {
    let currentPart = korg.read.part();


    //Aggiorna tutti i valori per gli step accentati/TIEati
    if(index == egIntKnobIndex && shiftPress == 0 && (currentPart >= 0) && (currentPart <= maxParts)) baseEgInt[currentPart] = (value/2)-63;
    if(index == decayKnobIndex && shiftPress == 0 && (currentPart >= 0) && (currentPart <= maxParts)) baseDecay[currentPart] = value/2;
    if(index == levelKnobIndex && shiftPress == 0 && (currentPart >= 0) && (currentPart <= maxParts)) baseLevel[currentPart] = value/2;
    //if(index == pitchGlideKnobIndex && shiftPress == 1) baseGlide[currentPart] = (value/2);
    


    //Aggiorna e mostra i valori per gli step accentati
    if(index == egIntKnobIndex && shiftPress == 1 && (currentPart >= 0) && (currentPart <= maxParts)){
      egIntAccAmount[currentPart] = (value/2)-64;
      korg.display.take();
      korg.display.clear();
      lastMillis = korg.millis();
      korg.display.text("AccentEgInt",10,22);
      korg.display.number(egIntAccAmount[currentPart],10, 32);
      
      
    }

    if(index == decayKnobIndex && shiftPress == 1 && (currentPart >= 0) && (currentPart <= maxParts)){
      decayAccAmount[currentPart] = value/2;
      korg.display.take();
      korg.display.clear();
      lastMillis = korg.millis();
      korg.display.text("AccentDecay",10,22);
      korg.display.number(decayAccAmount[currentPart],10,32);
      
      
    }
    
    if(index == levelKnobIndex && shiftPress == 1 && (currentPart >= 0) && (currentPart <= maxParts)){
      levelAccAmount[currentPart] = value/2;
      korg.display.take();
      korg.display.clear();
      lastMillis = korg.millis();
      korg.display.text("AccentLevel",10,22);
      korg.display.number(levelAccAmount[currentPart],10,32);
      
      
    }
    
});
`,
  }),
  Object.freeze({
    id: "easyslides",
    title: "Easy Slides",
    description: text("catalog.easyslides.description"),
    category: text("catalog.category.tools"),
    creator: "alarykko",
    added: "2026-11-13",
    controls: [text("catalog.easyslides.control1"), text("catalog.easyslides.control2")],
    source: `// EASY SLIDES v1 by alarykko, from the BLECH Discord: a TIE step (gate above 96) and the step after it get more glide,
// so the two notes slide. SHIFT + PITCH/GLIDE sets the base glide of the selected part. In the catalog the glide acts
// only on the parts whose glide it saved, 1 to 8 (maxParts), and STOP puts those back: the original also wrote parts 9
// to 16 on every step and set their glide to 0.
//Ancora da sistemare, implementare migliore logica per far si che glide rimanga attivo sia nello step con TIE e quello successivo così da dare il tempo alla nota di slideare

const baseGlide = new Array(16);
const pitchGlideKnobIndex = 2;
const maxParts = 8;
const glideOnTies = 35;
let shiftPressed = 0;


//Per evitare argomenti fuori da quelli ammessi
function limitUnsigned (value){
  if(value > 127) return 127;
  if(value < 0) return 0;
  return value;
}


function setNewBases(){
  for(let part = 0; part < maxParts; part++){
      baseGlide[part] = korg.parts[part].glide;
  }
}



function applySlide() {
  const stepCount = 64;
  
  //per ogni parte
  for (let part = 0; part < maxParts; part++) {

    const currentStep = korg.read.step(part);
    const previousStep = ((currentStep - 1) % stepCount + stepCount) % stepCount;
    const currentNote = korg.seq.getNote(part, currentStep, 1);
    const previousNote = korg.seq.getNote(part, previousStep, 1);
    
    
    //se lo step è tie oppure quello prima è tie applica il glide, in questo modo si da il tempo alla frequenza di glideare
    if (korg.seq.getGate(part, currentStep) > 96  || korg.seq.getGate(part, previousStep) > 96)   {
      korg.parts[part].glide = limitUnsigned(baseGlide[part] + glideOnTies); 
    }
    else korg.parts[part].glide = baseGlide[part];
  }
}






korg.onEvent("ready", () => {
    
    //registra i baseGlide all'accensione
    setNewBases();
    korg.display.popups(0);
    
});

korg.onEvent("patternChange", () => {
    setNewBases();
});


korg.onEvent("buttonPress", (key) => {
     
    //restora i glide correnti ai base, per evitare che se pausato proprio durante un accent cambino i baseGlide
    if(key == korg.key.STOP){
      for(let part = 0; part < maxParts; part++){
        korg.parts[part].glide = baseGlide[part];
      }
    }

    //semplice flag per shift premuto
    if(key == korg.key.SHIFT) shiftPressed = 1;
    
});



korg.onEvent("buttonRelease", (key) => {

  //idem come sopra con patate  
  if(key == korg.key.SHIFT) shiftPressed = 0;
    
});


korg.onEvent("step", () => {

    //applica lo slide ad ogni step
    applySlide();

});

//aggiorna i baseGlide quando giri il knob pitch tenendo premuto shift
korg.onEvent("knob", (index, value) => {
    
    let part = korg.read.part();    
    if(index == pitchGlideKnobIndex && shiftPressed == 1) baseGlide[part] = (value/2);
    
});
`,
  }),
  Object.freeze({
    id: "padfinger",
    title: "Pad Finger",
    description: text("catalog.padfinger.description"),
    category: text("catalog.category.tools"),
    creator: "nic0crank",
    added: "2026-11-13",
    controls: [text("catalog.padfinger.control1"), text("catalog.padfinger.control2")],
    source: `korg.app("Pad Finger", "TOOLS");
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
  if (key == korg.key.TAP) {
    lock = 1 - lock;
    if (!lock) release();
    dirty = 1;
  }
});

korg.onEvent("buttonRelease", (key) => {
  if (key == korg.key.TOUCHPAD) release();
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
`,
  }),
]);
