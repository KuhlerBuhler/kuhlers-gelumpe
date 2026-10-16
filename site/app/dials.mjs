/**
 * How the rotary controls of the device front move. No DOM, so it can be
 * tested. Click counts and ranges were measured on the device.
 */

export const DETENTS_PER_TURN = 24;
export const DETENT_DEG = 360 / DETENTS_PER_TURN;

/** Free controls show 0 to 127; the panel message carries 0 to 255. */
export const FREE_MAX = 127;
export const FREE_CENTER = 64;
export const CATCH_UNITS = 3;
export const SWEEP_DEG = 270;

export const DRAG_PX_PER_DETENT = 14;
export const DRAG_PX_FULL_RANGE = 240;
/** A Chrome wheel notch is 100 px. */
export const WHEEL_PX_PER_DETENT = 100;
export const WHEEL_PX_FULL_RANGE = 5000;
export const WHEEL_MIN_MS = 70;
export const CLICK_MAX_MS = 350;
export const CLICK_MAX_PX = 4;

export const clamp = (v, low, high) => Math.max(low, Math.min(high, v));

export function wheelPixels(e) {
  const unit = e.deltaMode === 1 ? 40 : e.deltaMode === 2 ? 800 : 1;
  return e.deltaY * unit;
}

/** Hands out whole units and keeps the remainder, so a slow drag still arrives. */
export class Accumulator {
  constructor(pxPerUnit) {
    this.pxPerUnit = pxPerUnit;
    this.rest = 0;
  }

  add(px) {
    this.rest += px / this.pxPerUnit;
    const whole = Math.trunc(this.rest);
    this.rest -= whole;
    return whole;
  }

  reset() { this.rest = 0; }
}

/** One click per 100 px of wheel, never faster than WHEEL_MIN_MS; distance inside the pause is dropped. */
export class WheelGovernor {
  constructor(pxPerUnit, minMs = WHEEL_MIN_MS) {
    this.acc = new Accumulator(pxPerUnit);
    this.minMs = minMs;
    this.last = -Infinity;
  }

  /** @returns {number} -1, 0 or 1; positive is clockwise (wheel up) */
  step(px, now) {
    if (now - this.last < this.minMs) {
      this.acc.reset();
      return 0;
    }
    const whole = this.acc.add(-px);
    if (!whole) return 0;
    this.last = now;
    return Math.sign(whole);
  }
}

/** The panel number for a shown value; 127 reaches the top stop, 255. */
export const rawOf = value => (value >= FREE_MAX ? 255 : value * 2);

/** Inside CATCH_UNITS either side of the centre a moving control reads the centre. */
export function withCatch(position, center = FREE_CENTER, width = CATCH_UNITS) {
  const v = clamp(Math.round(position), 0, FREE_MAX);
  return Math.abs(v - center) <= width ? center : v;
}

/** Marker angle of a free control in degrees, 0 pointing up. */
export const angleOfValue = value => (value / FREE_MAX - 0.5) * SWEEP_DEG;
