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
  const context = await h.browser.newContext({ reducedMotion: "reduce" });
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
