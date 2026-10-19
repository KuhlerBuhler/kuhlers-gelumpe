// Mandelbrot in Q14 fixed point. A bounded worklist holds unresolved rectangles. Proven interior rectangles are
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
  if (key == 15) zoom += 1;
  if (key == 11) zoom -= 1;
  if (key == 28) maxIter -= 8;
  if (key == 29) maxIter += 8;
  if (key == 3) {
    cx = -8192;
    cy = 0;
    zoom = 0;
  }
  if (key == 15 || key == 11 || key == 28 || key == 29 || key == 3) changed();
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
