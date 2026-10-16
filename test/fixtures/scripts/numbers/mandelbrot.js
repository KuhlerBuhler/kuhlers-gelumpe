// Mandelbrot renderer, an app under TOOLS. Fixed point with 14 fractional bits (1.0 is 16384), the picture comes in
// four passes of blocks 8, 4, 2 and 1 pixel wide and every frame draws only as many pixels as fit a small budget,
// so the controls stay responsive. A finger dragging on the touchpad pans, Part right and the encoder zoom in,
// Part left zooms out, keys 1 and 2 lower and raise the iteration limit, TAP resets the view. Each change starts the
// picture again from the coarse pass.
korg.app("Mandelbrot", "TOOLS");
const BUDGET = 26;
let cx = -8192;
let cy = 0;
let zoom = 0;
let ds = 384;
let maxIter = 24;
let lvl = 0;
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

function startX(y) {
  const s = 8 >> lvl;
  if (lvl > 0 && (y & (2 * s - 1)) == 0) return s;
  return 0;
}

function restart() {
  lvl = 0;
  sx = 0;
  sy = 0;
  done = 0;
  active = 0;
}

function plot(x, y, s, on) {
  if (s == 1) korg.display.pixel(x, y, on);
  else if (on) korg.display.rect(x, y, s, s);
  else korg.display.clearRect(x, y, s, s);
}

function advance() {
  const s = 8 >> lvl;
  if (lvl > 0 && (sy & (2 * s - 1)) == 0) sx += 2 * s;
  else sx += s;
  if (sx >= 128) {
    sy += s;
    if (sy >= 64) {
      lvl += 1;
      sy = 0;
    }
    if (lvl < 4) sx = startX(sy);
  }
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
  korg.display.clear();
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

// A pixel is iterated across frames when it needs more than the frame's budget: zx, zy and n stay between frames.
korg.onEvent("frame", () => {
  used = 0;
  while (used < BUDGET && lvl < 4) {
    if (!active) {
      cr = cx + (sx - 64) * ds;
      ci = cy + (sy - 32) * ds;
      zx = 0;
      zy = 0;
      n = 0;
      active = 1;
      used += 4;
      if (inside(cr, ci)) n = maxIter;
    }
    let esc = 0;
    while (n < maxIter && used < BUDGET && !esc) {
      if (zx > 32768 || zx < -32768 || zy > 32768 || zy < -32768) {
        esc = 1;
      } else {
        const zx2 = (zx * zx) >> 14;
        const zy2 = (zy * zy) >> 14;
        if (zx2 + zy2 > 65536) {
          esc = 1;
        } else {
          zy = ((zx * zy) >> 13) + ci;
          zx = zx2 - zy2 + cr;
          n += 1;
          used += 1;
        }
      }
    }
    if (esc || n >= maxIter) {
      let ink = 0;
      if (n == maxIter) ink = 1;
      else if (n > 2 && (n & 3) == 0) ink = 1;
      plot(sx, sy, 8 >> lvl, ink);
      active = 0;
      used += 3;
      advance();
    }
  }
  if (lvl >= 4 && !done) {
    done = 1;
    hud();
  }
});
