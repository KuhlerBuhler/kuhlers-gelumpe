// Tetris on a 10 x 16 board of 4 x 4 pixel cells, an app under GAMES: it opens from the BLECH menu, starts anew on
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
  if (key == 11) dx = -1;
  if (key == 15) dx = 1;
  if (key == 12) turn = 1;
  if (key == 8) soft = 1;
});

korg.onEvent("buttonRelease", (key) => {
  if (key == 8) soft = 0;
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
