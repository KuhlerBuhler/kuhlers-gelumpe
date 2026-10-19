/**
 * Starting points for the scripts page and the cards of its catalog. Snake is the reference script the tests run
 * (test/fixtures/scripts); a test keeps the source here equal to that file.
 */
export const PRESETS = Object.freeze([
  Object.freeze({
    id: "blechclicker",
    title: "BLECH Clicker",
    description: "App in GAMES: ein Kristall in der Mitte, jeder Pad-Druck zählt eins hoch, der Stand bleibt über das Ausschalten.",
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
    description: "App in TOOLS: große Uhr für die Länge des Sets. Startet mit dem ersten PLAY oder [1], zählt auch bei geschlossener App weiter, [4] zweimal setzt zurück.",
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
  korg.display.clearRect(90, 0, 38, 8);
  korg.display.clearRect(0, 52, 128, 8);
  if (s == 0) {
    korg.display.text("WAIT", 98, 0);
    korg.display.text("PLAY OR KEY 1 STARTS", 0, 56);
  } else if (s == 1) {
    korg.display.text("RUN", 104, 0);
    korg.display.text("KEY 4 = RESET", 0, 56);
  } else {
    korg.display.text("RESET?", 92, 0);
    korg.display.text("KEY 4 AGAIN = RESET", 0, 56);
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
  korg.display.text("SET TIMER", 0, 0);
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
    description: "App in GAMES: das Spiel auf dem Display. Tippe aufs Touchpad oben, unten, links oder rechts, dorthin läuft die Schlange.",
    source: `// Snake on a 16 x 8 grid of 8 x 8 pixel cells, an app under GAMES: it opens from the BLECH menu, starts anew
// on every open and leaves with EXIT. The body is a ring buffer, \`cell\` marks occupied cells. A tap on the
// touchpad steers: above, below, left or right of its centre is the new direction, never straight back.
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

korg.onEvent("frame", () => {
  frames += 1;
  if (frames >= 3) {
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
    description: "App in GAMES: fallende Blöcke auf einem Feld von 10 mal 16. [◄ PART] und [PART ►] bewegen, [EDIT ►] dreht, [◄ EDIT] gehalten lässt schneller fallen.",
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
  korg.display.clearRect(100, 10, 16, 12);
  for (let i = 0; i < 16; i++) {
    if ((m >> i) & 1) korg.display.rect(100 + (i & 3) * 4, 10 + (i >> 2) * 4, 3, 3);
  }
}

function drawHud() {
  korg.display.clearRect(54, 9, 42, 7);
  korg.display.number(score, 54, 9);
  korg.display.clearRect(54, 29, 42, 7);
  korg.display.number(lines, 54, 29);
  korg.display.clearRect(54, 49, 42, 7);
  korg.display.number(level, 54, 49);
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
    korg.display.text("SCORE", 54, 0);
    korg.display.text("LINES", 54, 20);
    korg.display.text("LEVEL", 54, 40);
    korg.display.text("NEXT", 100, 0);
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
    korg.display.clearRect(54, 56, 70, 8);
    korg.display.text("GAME OVER", 54, 56);
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
    description: "App in GAMES: das Touchpad zeichnet Zellen. [1] Start und Pause, [2] ein Schritt, [3] löschen, [4] zufällig füllen.",
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
    description: "App in GAMES: Pong gegen den Bot bis 9. Das Paddel folgt dem Finger auf dem Touchpad, oder [◄ PART] hoch und [PART ►] runter.",
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
    description: "App in GAMES: vier Pads in der Mitte leuchten eine Folge vor, du spielst sie nach, jede Runde wird sie länger. [TAP] startet neu.",
    source: `// Simon, an app under GAMES, on the four middle pads (3, 4, 11 and 12 counted from 0). The pads light up in a
// sequence, repeat it on the pads, and the sequence grows by one step every round. A wrong pad ends the game and
// shows the number of rounds you got through. While the app is open it holds the panel LEDs (korg.ledHold) so the
// firmware does not paint over the pads; the four squares on the display follow the pads. TAP or any pad starts anew.
korg.app("Simon", "GAMES");
const PADI = [3, 4, 11, 12];
const SX = [38, 66, 38, 66];
const SY = [10, 10, 33, 33];
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

function square(i, on) {
  korg.display.rect(SX[i], SY[i], 24, 20);
  if (!on) korg.display.clearRect(SX[i] + 2, SY[i] + 2, 20, 16);
}

function setPad(i, on) {
  korg.led(korg.led.PAD_1_RED + PADI[i] * 2, on ? 255 : 0);
  square(i, on);
}

function light(i) {
  if (lit >= 0) setPad(lit, 0);
  lit = i;
  if (i >= 0) setPad(i, 1);
}

function setAll(on) {
  for (let i = 0; i < 4; i++) setPad(i, on);
}

function status(which) {
  korg.display.clearRect(0, 56, 128, 8);
  if (which == 0) korg.display.text("GET READY", 0, 57);
  else if (which == 1) korg.display.text("WATCH", 0, 57);
  else if (which == 2) korg.display.text("YOUR TURN", 0, 57);
  else if (which == 3) korg.display.text("WELL DONE", 0, 57);
  else korg.display.text("GAME OVER, TAP OR PAD", 0, 57);
}

function header() {
  korg.display.clearRect(60, 0, 68, 8);
  korg.display.textNumber("ROUND ", len, 70, 0);
}

function newGame() {
  len = 0;
  pos = 0;
  score = 0;
  lit = -1;
  state = 0;
  timer = 25;
  korg.display.clear();
  korg.display.text("SIMON", 0, 0);
  for (let i = 0; i < 4; i++) square(i, 0);
  status(0);
}

function addStep() {
  seq[len] = rnd() & 3;
  len += 1;
  pos = 0;
  timer = 10;
  state = 1;
  header();
  status(1);
}

function padIndex(index) {
  for (let i = 0; i < 4; i++) {
    if (PADI[i] == index) return i;
  }
  return -1;
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
  if (!isOpen) return;
  if (state == 5) {
    if (down) newGame();
    return;
  }
  const i = padIndex(index);
  if (i < 0) return;
  if (!down) {
    if (lit == i && (state == 2 || state == 4)) light(-1);
    return;
  }
  if (state != 2) return;
  light(i);
  if (seq[pos] != i) {
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
  }
});

korg.onEvent("buttonPress", (key) => {
  if (isOpen && state == 5 && key == korg.key.TAP) newGame();
});

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
      }
      timer = 5;
    } else {
      light(seq[pos]);
      timer = 12 - len / 4;
      if (timer < 5) timer = 5;
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
      korg.display.clearRect(60, 0, 68, 8);
      korg.display.textNumber("SCORE ", score, 70, 0);
    }
  }
});
`,
  }),
  Object.freeze({
    id: "mandelbrot",
    title: "Mandelbrot",
    description: "App in GAMES: rechnet die Mandelbrot-Menge Stück für Stück. Touchpad verschiebt, [PART ►] zoomt hinein, [◄ PART] hinaus, [1] und [2] stellen die Iterationen, [TAP] setzt zurück.",
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
  korg.display.clearRect(78, 56, 50, 8);
  korg.display.textNumber("Z", zoom, 80, 57);
  korg.display.textNumber("I", maxIter, 104, 57);
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
    id: "lauflicht",
    title: "Lauflicht",
    description: "Ein Licht läuft über die Pads.",
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
    description: "Alle roten Pad-LEDs werden heller und dunkler.",
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
]);
