import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";

let h;
before(async () => { h = await setUp(); });
after(async () => { await h.tearDown(); });

/** Cell size on screen, how many pixels are lit, and a fingerprint of the frame. */
const frame = page => page.evaluate(() => {
  const c = document.getElementById("bg-canvas");
  const d = new Uint32Array(c.getContext("2d").getImageData(0, 0, c.width, c.height).data.buffer);
  let lit = 0, sum = 0, eye = 0;
  for (let i = 0; i < d.length; i++) {
    if (!d[i]) continue;
    lit++;
    sum = (sum * 31 + d[i] + i) >>> 0;
    if ((d[i] & 0xff) > 240 && ((d[i] >>> 8) & 0xff) > 240) eye++;
  }
  return { cols: c.width, rows: c.height, cell: parseFloat(c.style.width) / c.width, lit, sum, eye, rendering: getComputedStyle(c).imageRendering };
});

test("the background is a hard-edged cell grid with stars and dither, behind the page", async () => {
  const page = await h.page();
  await page.setViewportSize({ width: 1400, height: 900 });
  await page.goto(h.url);
  await page.waitForTimeout(400);
  const f = await frame(page);
  assert.equal(f.rendering, "pixelated");
  assert.equal(f.cell, 4);
  assert.equal(f.cols, 350);
  assert.equal(f.rows, 225);
  assert.ok(f.lit > 500, `only ${f.lit} pixels lit`);
  assert.ok(f.lit < f.cols * f.rows * 0.15, "the background stays sparse");
  assert.equal(await page.locator("#bg-canvas").evaluate(n => getComputedStyle(n).zIndex), "-1");
  assert.deepEqual(page.errors, []);
});

test("the sidebar covers most of the background, the navbar all of it", async () => {
  const page = await h.page();
  await page.setViewportSize({ width: 1400, height: 900 });
  await page.goto(h.url);
  const alpha = sel => page.locator(sel).evaluate(n => {
    const bg = getComputedStyle(n).backgroundColor;
    const a = bg.match(/\/\s*([\d.]+)\s*\)/) || bg.match(/rgba\([^)]*,\s*([\d.]+)\)/);
    return a ? Number(a[1]) : 1;
  });
  const sidebar = await alpha(".cee-sidebar");
  assert.ok(sidebar >= 0.75 && sidebar < 1, `the sidebar is ${sidebar} opaque, expected from 0.75 up to but not including 1`);
  assert.equal(await alpha(".cee-navbar"), 1);
});

test("the stars drift", async () => {
  const page = await h.page();
  await page.goto(h.url);
  await page.waitForTimeout(300);
  const a = await frame(page);
  await page.waitForTimeout(1500);
  const b = await frame(page);
  assert.notEqual(a.sum, b.sum, "nothing moved");
});

test("prefers-reduced-motion draws one static frame without eyes", async () => {
  const context = await h.browser.newContext({ reducedMotion: "reduce", locale: "de-DE" });
  const page = await context.newPage();
  await page.goto(`${h.url}?bg-eyes=now`);
  await page.waitForTimeout(300);
  const a = await frame(page);
  await page.waitForTimeout(2500);
  const b = await frame(page);
  assert.ok(a.lit > 500);
  assert.deepEqual(a, b);
  assert.equal(b.eye, 0);
  await context.close();
});

test("the eyes blink up out of the dither, and can be turned off", async () => {
  const page = await h.page();
  await page.setViewportSize({ width: 1400, height: 900 });
  await page.goto(`${h.url}?bg-eyes=now`);
  await page.waitForFunction(() => {
    const c = document.getElementById("bg-canvas");
    const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
    for (let i = 0; i < d.length; i += 4) if (d[i] > 240 && d[i + 1] > 240 && d[i + 3]) return true;
    return false;
  }, null, { timeout: 8000, polling: 100 });

  const off = await h.page();
  await off.setViewportSize({ width: 1400, height: 900 });
  await off.goto(`${h.url}?bg-eyes=off`);
  await off.waitForTimeout(3500);
  assert.equal((await frame(off)).eye, 0);
});

test("the variants: bands has no clouds, off hides the canvas", async () => {
  const page = await h.page();
  await page.goto(`${h.url}?bg=bands`);
  await page.waitForTimeout(300);
  const bands = await frame(page);
  await page.goto(h.url);
  await page.waitForTimeout(300);
  const dust = await frame(page);
  assert.ok(bands.lit < dust.lit, "dust adds pixels");
  await page.goto(`${h.url}?bg=off`);
  assert.equal(await page.locator("#bg-canvas").isHidden(), true);
});

// The page's clock is Playwright's here, so frame timing does not depend on how busy the machine is:
// runFor() lets frames come on time, fastForward() jumps ahead so the next frame comes late once. The first 5 s after the
// start do not count, so each test lets those pass first.

test("frames that come late again and again leave a still background", async () => {
  const page = await h.page();
  await page.clock.install();
  await page.goto(`${h.url}?bg-eyes=off`);
  await page.clock.runFor(5300);
  for (let i = 0; i < 3; i++) { await page.clock.fastForward(500); await page.clock.runFor(200); }
  assert.equal(await page.locator("#bg-canvas").getAttribute("data-still"), "stalled");
  const a = await frame(page);
  await page.clock.runFor(1500);
  assert.deepEqual(await frame(page), a, "nothing moves any more");
  assert.ok(a.lit > 500, "the still frame is drawn, not blank");
});

test("one late frame alone does not stop the background", async () => {
  const page = await h.page();
  await page.clock.install();
  await page.goto(h.url);
  await page.clock.runFor(5300);
  await page.clock.fastForward(500);
  await page.clock.runFor(300);
  assert.equal(await page.locator("#bg-canvas").getAttribute("data-still"), null);
  const a = await frame(page);
  await page.clock.runFor(1500);
  assert.notEqual((await frame(page)).sum, a.sum, "still drifting");
});

test("the background rests while the window is in the background and goes on when it comes back", async () => {
  const page = await h.page();
  await page.clock.install();
  await page.goto(`${h.url}?bg-eyes=off`);
  await page.clock.runFor(300);
  await page.evaluate(() => dispatchEvent(new Event("blur")));
  const a = await frame(page);
  await page.clock.runFor(1200);
  assert.deepEqual(await frame(page), a, "nothing drawn while away");
  await page.evaluate(() => dispatchEvent(new Event("focus")));
  await page.clock.runFor(1500);
  assert.notEqual((await frame(page)).sum, a.sum, "drawing again");
});

test("frames that come late while the page starts do not count", async () => {
  const page = await h.page();
  await page.clock.install();
  await page.goto(`${h.url}?bg-eyes=off`);
  for (let i = 0; i < 3; i++) { await page.clock.fastForward(500); await page.clock.runFor(200); }
  assert.equal(await page.locator("#bg-canvas").getAttribute("data-still"), null);
});
