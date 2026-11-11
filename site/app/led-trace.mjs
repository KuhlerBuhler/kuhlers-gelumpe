/**
 * Plays the emulator's LED changes at the device's pace (tools/emu/panel_leds.py, event `ledtrace`).
 *
 * Each change comes with the device time the panel lights it. The service sends them in steps of about
 * 20 ms of device time; the player puts each one on the page clock a short delay later, keeping the
 * distances between them. A drawn frame shows each LED as the mean of its values over the frame, the
 * way an eye sees a PWM LED: a pad that goes dark for 5 ms inside a 17 ms frame is a visibly dimmer
 * frame, not a frame that never happened.
 */

/** Page time a change is shown after the device time it lights: room for one step of the service and its jitter. */
export const DELAY_MS = 60;
/** Further off than this, the device clock is laid onto the page clock again (a paused tab, a slow or unpaced service). */
export const DRIFT_MS = 250;

export class LedPlayer {
  constructor() {
    this.value = new Map();       // led -> value the controller shows now (0 to 255)
    this.shown = new Map();       // led -> level last given to the drawing
    this.queue = [];              // { at: page ms, led, v }, in order
    this.offset = null;           // page ms = device ms + offset
    this.at = null;               // page ms of the last frame
  }

  /** The whole table (event `leds`): shown at once, nothing waits any more. Unlisted LEDs are dark. */
  table(leds) {
    this.queue = [];
    this.offset = null;
    this.value = new Map(Object.entries(leds).map(([led, v]) => [Number(led), v]));
    this.shown = new Map(this.value);
  }

  /** One `ledtrace` event: { now, changes: [[device us got, device us lit, led, value]] }; `page` is the page clock in ms. */
  trace(batch, page) {
    const now = batch.now / 1000;
    if (this.offset === null || Math.abs(now + this.offset - (page + DELAY_MS)) > DRIFT_MS || now + this.offset < page) {
      this.offset = page + DELAY_MS - now;
    }
    let last = this.queue.length ? this.queue[this.queue.length - 1].at : -Infinity;
    for (const [, lit, led, v] of batch.changes) {
      last = Math.max(last, lit / 1000 + this.offset);   // never before one already waiting: the order is the firmware's
      this.queue.push({ at: last, led, v });
    }
  }

  /** Whether a frame may still change something. */
  get busy() {
    return this.queue.length > 0 || [...this.value].some(([led, v]) => (this.shown.get(led) ?? 0) !== v);
  }

  /** The levels to draw at page time `page`, only the ones that changed since the last frame: { led: 0 to 255 }. */
  frame(page) {
    const from = this.at ?? page;
    this.at = page;
    const span = page - from;
    const sum = new Map(), since = new Map();
    while (this.queue.length && this.queue[0].at <= page) {
      const { at, led, v } = this.queue.shift();
      const t = Math.max(at, from);
      if (!since.has(led)) { since.set(led, from); sum.set(led, 0); }
      sum.set(led, sum.get(led) + (this.value.get(led) ?? 0) * (t - since.get(led)));
      since.set(led, t);
      this.value.set(led, v);
    }
    const out = {};
    for (const [led, v] of this.value) {
      let level = v;
      if (since.has(led)) {
        const total = sum.get(led) + v * (page - since.get(led));
        level = span > 0 ? total / span : v;
      }
      if ((this.shown.get(led) ?? 0) !== level) {
        out[led] = level;
        this.shown.set(led, level);
      }
    }
    return out;
  }
}
