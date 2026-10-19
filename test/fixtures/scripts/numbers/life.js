// Conway's Game of Life on a 32 x 16 torus of 4 x 4 pixel cells, an app under GAMES. The touchpad draws: a touch
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
  korg.led(40, 255);
});

korg.onEvent("close", () => {
  isOpen = 0;
  korg.led(40, 0);
});

korg.onEvent("touch", (x, y) => {
  if (isOpen) touchCell(x, y);
});

korg.onEvent("buttonPress", (key) => {
  if (!isOpen) return;
  if (key == 28) {
    running = !running;
    korg.led(40, running ? 255 : 0);
  }
  if (key == 29) stepReq = 1;
  if (key == 30) wipe();
  if (key == 31) {
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
