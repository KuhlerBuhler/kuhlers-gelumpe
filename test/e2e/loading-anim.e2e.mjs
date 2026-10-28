import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { setUp, go } from "./harness.mjs";
import { decodeAnimation, validateAnimation, MAX_BYTES } from "../../src/loading-anim.mjs";

let h;
before(async () => { h = await setUp(); });
after(async () => { await h.tearDown(); });

const GIF = new URL("../fixtures/gif/ffmpeg-moving.gif", import.meta.url).pathname;
const KEY = "cee.loading.anim";

async function designPage() {
  const page = await h.page();
  await page.goto(h.url);
  await go(page, "splash");
  await page.locator("#cee-anim-file").waitFor({ state: "attached" });
  return page;
}

/** Pictures made in the page, one PNG per entry: "black" fills it, "white" leaves it empty, a number draws a bar that wide. */
async function dropPictures(page, list) {
  await page.evaluate(async list => {
    const dt = new DataTransfer();
    for (const [name, what] of list) {
      const c = document.createElement("canvas");
      c.width = 128;
      c.height = 64;
      const g = c.getContext("2d");
      g.fillStyle = "#fff";
      g.fillRect(0, 0, 128, 64);
      g.fillStyle = "#000";
      if (what === "black") g.fillRect(0, 0, 128, 64);
      else if (typeof what === "number") g.fillRect(0, 24, what, 16);
      const blob = await new Promise(r => c.toBlob(r, "image/png"));
      dt.items.add(new File([blob], name, { type: "image/png" }));
    }
    const input = document.getElementById("cee-anim-file");
    input.files = dt.files;
    input.dispatchEvent(new Event("change"));
  }, list);
  await page.locator("#cee-anim-frames > li").nth(list.length - 1).waitFor();
}

const stored = page => page.evaluate(key => {
  const text = localStorage.getItem(key);
  return text ? Array.from(atob(text), c => c.charCodeAt(0)) : null;
}, KEY);

test("Design: the tab is called Design, a GIF becomes the animation with its size, the preview follows the slider", async () => {
  const page = await designPage();
  assert.equal(await page.locator("#cee-tab-splash").textContent(), "Design");
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Design");
  assert.match(await page.locator("#cee-anim-state").textContent(), /Blechy/, "without an own file the default");
  await page.setInputFiles("#cee-anim-file", GIF);
  await page.locator("#cee-anim-work:not([hidden])").waitFor();
  assert.equal(await page.locator("#cee-anim-frames > li").count(), 3, "every frame of the GIF");
  assert.deepEqual(await page.locator("#cee-anim-frames select").evaluateAll(s => s.map(x => x.value)), ["progress", "progress", "progress"], "all progress by default");
  assert.match(await page.locator("#cee-anim-size-text").textContent(), /^\d+,\d von 16 KB$/);
  const shot = () => page.locator("#cee-anim-preview").evaluate(c => c.toDataURL());
  await page.locator("#cee-anim-progress").fill("0");
  const start = await shot();
  await page.locator("#cee-anim-progress").fill("100");
  assert.notEqual(await shot(), start, "the last picture at 100 percent");
  assert.equal(await page.locator("#cee-anim-progress-value").textContent(), "100");
  await page.click("#cee-anim-use");
  const bytes = Uint8Array.from(await stored(page));
  assert.equal(validateAnimation(bytes), null);
  assert.equal(decodeAnimation(bytes).progress.length, 3);
  assert.match(await page.locator("#cee-anim-state").textContent(), /deine Animation/);
  assert.deepEqual(page.errors, []);
});

test("Design: single pictures in the order of their names, one as waiting loop from a percent on", async () => {
  const page = await designPage();
  await dropPictures(page, [["b-2.png", 64], ["b-10.png", "black"], ["b-1.png", 32]]);
  assert.deepEqual(await page.locator("#cee-anim-frames .cee-anim-frame-name").allTextContents(), ["b-1", "b-2", "b-10"]);
  await page.locator("#cee-anim-frames select").nth(2).selectOption("loop");
  await page.locator("#cee-anim-loop-from-percent").check();
  await page.locator("#cee-anim-loop-percent").fill("80");
  await page.locator("#cee-anim-loop-percent").dispatchEvent("change");
  await page.click("#cee-anim-use");
  const anim = decodeAnimation(Uint8Array.from(await stored(page)));
  assert.equal(anim.progress.length, 2);
  assert.equal(anim.loop.length, 1);
  assert.equal(anim.loopFrom, 80);
  // the loop picture is all black: on the reversed display nothing is lit
  assert.ok(anim.loop[0].every(b => b === 0));
  await page.reload();
  await go(page, "splash");
  await page.locator("#cee-anim-work:not([hidden])").waitFor();
  assert.equal(await page.locator("#cee-anim-frames > li").count(), 3, "the kept animation comes back after a reload");
  assert.equal(await page.locator("#cee-anim-loop-percent").inputValue(), "80");
  assert.deepEqual(page.errors, []);
});

test("Design: an animation over 16 KB is refused with its most expensive pictures, thinning brings it under", async () => {
  const page = await designPage();
  // every picture the inverse of the one before: about 1 KB each
  const list = Array.from({ length: 24 }, (_, i) => [`f-${String(i).padStart(2, "0")}.png`, i % 2 ? "black" : "white"]);
  await dropPictures(page, list);
  assert.match(await page.locator("#cee-anim-size-text").textContent(), /^2\d,\d von 16 KB$/);
  assert.equal(await page.locator("#cee-anim-use").isDisabled(), true, "too big is not taken");
  const toast = await page.locator("#app-toasts .cee-toast", { hasText: "zu groß" }).textContent();
  assert.match(toast, /f-\d\d \(1,0 KB\)/, "names the most expensive pictures");
  assert.equal(await page.locator("#cee-anim-thin").isVisible(), true);
  await page.click("#cee-anim-thin");
  assert.equal(await page.locator("#cee-anim-frames > li").count(), 13, "0, 2, 4 ... 22 and the last");
  const size = await page.locator("#cee-anim-size-text").textContent();
  assert.ok(Number(size.split(" ")[0].replace(",", ".")) * 1024 <= MAX_BYTES, size);
  assert.equal(await page.locator("#cee-anim-use").isDisabled(), false);
  assert.equal(await page.locator("#cee-anim-thin").isVisible(), false);
  await page.click("#cee-anim-use");
  assert.ok((await stored(page)).length <= MAX_BYTES);
  assert.deepEqual(page.errors, []);
});

test("Design: the default comes back, also after a reload", async () => {
  const page = await designPage();
  assert.equal(await page.locator("#cee-anim-reset").isDisabled(), true, "nothing to restore without an own animation");
  await dropPictures(page, [["a.png", 10], ["b.png", 100]]);
  await page.click("#cee-anim-use");
  assert.notEqual(await stored(page), null);
  await page.click("#cee-anim-reset");
  assert.equal(await stored(page), null);
  assert.match(await page.locator("#cee-anim-state").textContent(), /Blechy/);
  assert.equal(await page.locator("#cee-anim-work").isHidden(), true);
  await page.reload();
  await go(page, "splash");
  await page.locator("#cee-anim-state").waitFor();
  assert.match(await page.locator("#cee-anim-state").textContent(), /Blechy/);
  assert.equal(await page.locator("#cee-anim-work").isHidden(), true);
  assert.deepEqual(page.errors, []);
});

test("Design: a file that is no picture is told, not taken", async () => {
  const page = await designPage();
  await page.setInputFiles("#cee-anim-file", h.file("broken.gif", readFileSync(GIF).subarray(0, 20)));
  await page.locator("#app-toasts .cee-toast", { hasText: "broken.gif" }).waitFor();
  assert.equal(await page.locator("#cee-anim-work").isHidden(), true);
  assert.deepEqual(page.errors, []);
});
