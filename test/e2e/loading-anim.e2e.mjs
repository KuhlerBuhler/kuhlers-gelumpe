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

/** The Design page on its Ladeanimation tab; `reduce` starts it with reduced motion, so the preview stands still. */
async function designPage({ reduce = true } = {}) {
  const page = await h.page();
  if (reduce) await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(h.url);
  await go(page, "splash");
  await page.click("#cee-design-tab-anim");
  await page.locator("#cee-anim-file").waitFor({ state: "attached" });
  return page;
}

/** Pictures made in the page, one PNG per entry: "black" fills it, "white" leaves it empty, a number draws a bar that wide. */
async function dropPictures(page, list, shown = Math.min(list.length, 24)) {
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
  await page.locator("#cee-anim-frames .cee-anim-thumb").nth(shown - 1).waitFor();
}

const stored = page => page.evaluate(key => {
  const text = localStorage.getItem(key);
  return text ? Array.from(atob(text), c => c.charCodeAt(0)) : null;
}, KEY);
const thumbs = page => page.locator("#cee-anim-frames .cee-anim-thumb");

test("Design: two tabs, Startbild and Ladeanimation, each its own section", async () => {
  const page = await h.page();
  await page.goto(h.url);
  await go(page, "splash");
  assert.deepEqual(await page.locator("#cee-design-tabs [role=tab]").allTextContents(), ["Startbild", "Ladeanimation"]);
  assert.equal(await page.locator("#cee-design-panel-splash").isVisible(), true, "Startbild first");
  assert.equal(await page.locator("#cee-design-panel-anim").isVisible(), false);
  await page.click("#cee-design-tab-anim");
  assert.equal(await page.locator("#cee-design-panel-anim .ui-section-title").textContent(), "Ladeanimation");
  assert.equal(await page.locator("#cee-design-panel-splash").isVisible(), false);
  assert.equal(await page.locator("#cee-anim-work").isHidden(), true, "nothing to show before a file");
  assert.deepEqual(page.errors, []);
});

test("Design: a GIF becomes the animation with its size, the preview follows the slider, saving clears the dirty state", async () => {
  const page = await designPage();
  assert.equal(await page.locator("#cee-tab-splash").textContent(), "Design");
  assert.match(await page.locator("#cee-anim-state").textContent(), /Blechy/, "without an own file the default");
  assert.equal(await page.locator("#cee-anim-use").isVisible(), false, "no save button without pictures");
  await page.setInputFiles("#cee-anim-file", GIF);
  await page.locator("#cee-anim-work:not([hidden])").waitFor();
  assert.equal(await thumbs(page).count(), 3, "every frame of the GIF");
  assert.equal(await page.locator("#cee-anim-loop-at").inputValue(), "", "no loop by default");
  assert.equal(await page.locator("#cee-anim-loop-mode").isHidden(), true, "no loop settings without loop pictures");
  assert.match(await page.locator("#cee-anim-size-text").textContent(), /^\d+,\d von 16 KB$/);
  assert.equal(await page.locator("#cee-anim-dirty").isVisible(), true, "a new animation is not saved yet");
  const shot = () => page.locator("#cee-anim-preview").evaluate(c => c.toDataURL());
  await page.locator("#cee-anim-progress").fill("0");
  const start = await shot();
  assert.equal(await thumbs(page).first().getAttribute("aria-current"), "true", "the shown picture is marked");
  await page.locator("#cee-anim-progress").fill("100");
  assert.notEqual(await shot(), start, "the last picture at 100 percent");
  assert.equal(await page.locator("#cee-anim-progress-value").textContent(), "100 %");
  assert.equal(await thumbs(page).last().getAttribute("aria-current"), "true");
  await thumbs(page).first().click();
  assert.equal(await page.locator("#cee-anim-progress").inputValue(), "0", "a click on a picture jumps to it");
  assert.equal(await shot(), start);
  await page.click("#cee-anim-use");
  const bytes = Uint8Array.from(await stored(page));
  assert.equal(validateAnimation(bytes), null);
  assert.equal(decodeAnimation(bytes).progress.length, 3);
  assert.match(await page.locator("#cee-anim-state").textContent(), /deine Animation/);
  assert.equal(await page.locator("#cee-anim-dirty").isVisible(), false, "saved");
  await page.locator("#cee-anim-convert summary").click();
  await page.locator("#cee-anim-invert").setChecked(true, { force: true });
  assert.equal(await page.locator("#cee-anim-dirty").isVisible(), true, "a change after saving is not saved");
  await page.locator("#cee-anim-invert").setChecked(false, { force: true });
  assert.equal(await page.locator("#cee-anim-dirty").isVisible(), false, "back to what is saved");
  assert.equal(await page.locator("#cee-anim-patcher-link").getAttribute("href"), "#patcher");
  assert.deepEqual(page.errors, []);
});

test("Design: single pictures in the order of their names, the split makes the rest the loop, from a percent on", async () => {
  const page = await designPage();
  await dropPictures(page, [["b-2.png", 64], ["b-10.png", "black"], ["b-1.png", 32]]);
  assert.deepEqual(await thumbs(page).evaluateAll(b => b.map(x => x.title)), ["b-1", "b-2", "b-10"]);
  assert.equal(await page.locator("#cee-anim-loop-at option").count(), 3, "none, picture 2 and picture 3");
  await page.locator("#cee-anim-loop-at").selectOption("2");
  assert.equal(await page.locator("#cee-anim-loop-mode").isVisible(), true);
  assert.equal(await page.locator("#cee-anim-frames .cee-anim-split").count(), 1, "a divider before the loop");
  assert.equal(await page.locator("#cee-anim-frames > li.cee-anim-split + li .cee-anim-thumb").getAttribute("title"), "b-10", "the divider stands before picture 3");
  assert.deepEqual(await thumbs(page).evaluateAll(b => b.map(x => "loop" in x.dataset)), [false, false, true], "the loop pictures are marked");
  assert.equal(await page.locator("#cee-anim-loop-percent").isVisible(), false, "no percent while the loop plays on a stall");
  await page.locator("#cee-anim-loop-from-percent").check();
  assert.equal(await page.locator("#cee-anim-loop-percent").isVisible(), true);
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
  assert.equal(await page.locator("#cee-design-panel-anim").isVisible(), true, "the tab is remembered");
  await page.locator("#cee-anim-work:not([hidden])").waitFor();
  assert.equal(await thumbs(page).count(), 3, "the kept animation comes back after a reload");
  assert.equal(await page.locator("#cee-anim-loop-at").inputValue(), "2");
  assert.equal(await page.locator("#cee-anim-loop-percent").inputValue(), "80");
  assert.equal(await page.locator("#cee-anim-dirty").isVisible(), false, "what comes back is what is saved");
  await page.locator("#cee-anim-loop-at").selectOption("");
  assert.equal(await page.locator("#cee-anim-loop-mode").isHidden(), true);
  assert.equal(await page.locator("#cee-anim-frames .cee-anim-split").count(), 0);
  assert.deepEqual(page.errors, []);
});

test("Design: an animation over 16 KB is refused inline with its most expensive pictures, thinning brings it under", async () => {
  const page = await designPage();
  // every picture the inverse of the one before: about 1 KB each
  const list = Array.from({ length: 24 }, (_, i) => [`f-${String(i).padStart(2, "0")}.png`, i % 2 ? "black" : "white"]);
  await dropPictures(page, list);
  assert.match(await page.locator("#cee-anim-size-text").textContent(), /^2\d,\d von 16 KB$/);
  assert.equal(await page.locator("#cee-anim-use").isDisabled(), true, "too big is not taken");
  const why = await page.locator("#cee-anim-too-big").textContent();
  assert.match(why, /zu groß/);
  assert.match(why, /f-\d\d \(1,0 KB\)/, "names the most expensive pictures");
  assert.match(await page.locator("#cee-anim-use").getAttribute("aria-describedby"), /cee-anim-too-big/);
  assert.equal(await page.locator("#cee-anim-thin").isVisible(), true);
  await page.click("#cee-anim-thin");
  assert.equal(await thumbs(page).count(), 13, "0, 2, 4 ... 22 and the last");
  const size = await page.locator("#cee-anim-size-text").textContent();
  assert.ok(Number(size.split(" ")[0].replace(",", ".")) * 1024 <= MAX_BYTES, size);
  assert.equal(await page.locator("#cee-anim-use").isDisabled(), false);
  assert.equal(await page.locator("#cee-anim-thin").isVisible(), false);
  assert.equal(await page.locator("#cee-anim-too-big").isVisible(), false);
  await page.click("#cee-anim-use");
  assert.ok((await stored(page)).length <= MAX_BYTES);
  assert.deepEqual(page.errors, []);
});

test("Design: many pictures show 24 first, the rest on request", async () => {
  const page = await designPage();
  await dropPictures(page, Array.from({ length: 30 }, (_, i) => [`m-${String(i).padStart(2, "0")}.png`, 4 * i]));
  assert.equal(await thumbs(page).count(), 24);
  assert.match(await page.locator("#cee-anim-more").textContent(), /\(6\)/);
  await page.click("#cee-anim-more");
  assert.equal(await thumbs(page).count(), 30);
  assert.equal(await page.locator("#cee-anim-more").isVisible(), false);
  assert.deepEqual(page.errors, []);
});

test("Design: the preview plays by itself, stands still with reduced motion, and the button plays and pauses", async () => {
  const moving = await designPage({ reduce: false });
  await moving.setInputFiles("#cee-anim-file", GIF);
  await moving.locator("#cee-anim-work:not([hidden])").waitFor();
  assert.equal(await moving.getAttribute("#cee-anim-play", "aria-label"), "Anhalten", "a new animation plays");
  await moving.waitForFunction(() => document.getElementById("cee-anim-progress").value === "100", null, { timeout: 15_000 });
  await moving.waitForFunction(() => document.getElementById("cee-anim-play").getAttribute("aria-label") === "Abspielen");
  // without a loop the run ends at 100 %; playing again starts from the beginning
  await moving.click("#cee-anim-play");
  assert.equal(await moving.getAttribute("#cee-anim-play", "aria-label"), "Anhalten");
  assert.ok(Number(await moving.locator("#cee-anim-progress").inputValue()) < 50);
  await moving.click("#cee-anim-play");
  assert.equal(await moving.getAttribute("#cee-anim-play", "aria-label"), "Abspielen");
  assert.deepEqual(moving.errors, []);

  const still = await designPage();
  await still.setInputFiles("#cee-anim-file", GIF);
  await still.locator("#cee-anim-work:not([hidden])").waitFor();
  assert.equal(await still.getAttribute("#cee-anim-play", "aria-label"), "Abspielen", "reduced motion starts paused");
  assert.equal(await still.locator("#cee-anim-progress").inputValue(), "0");
  await still.click("#cee-anim-play");
  assert.equal(await still.getAttribute("#cee-anim-play", "aria-label"), "Anhalten");
  await still.waitForFunction(() => Number(document.getElementById("cee-anim-progress").value) > 0);
  await still.locator("#cee-anim-progress").fill("10");
  assert.equal(await still.getAttribute("#cee-anim-play", "aria-label"), "Abspielen", "moving the slider pauses");
  assert.deepEqual(still.errors, []);
});

test("Design: the default comes back, also after a reload; unsaved work is asked for first", async () => {
  const page = await designPage();
  assert.equal(await page.locator("#cee-anim-reset").isVisible(), false, "nothing to restore without an own animation");
  await dropPictures(page, [["a.png", 10], ["b.png", 100]]);
  await page.click("#cee-anim-use");
  assert.notEqual(await stored(page), null);
  // an unsaved change: the reset asks first, Abbrechen keeps everything
  await page.locator("#cee-anim-loop-at").selectOption("1");
  await page.click("#cee-anim-reset");
  const dialog = page.locator("dialog.ui-dialog[open]");
  await dialog.waitFor();
  await dialog.getByRole("button", { name: "Abbrechen" }).click();
  assert.notEqual(await stored(page), null);
  assert.equal(await thumbs(page).count(), 2);
  await page.click("#cee-anim-reset");
  await dialog.getByRole("button", { name: "Standard wiederherstellen" }).click();
  await page.locator("#cee-anim-work[hidden]").waitFor({ state: "attached" });
  assert.equal(await stored(page), null);
  assert.match(await page.locator("#cee-anim-state").textContent(), /Blechy/);
  assert.equal(await page.locator("#cee-anim-reset").isVisible(), false);
  await page.reload();
  await go(page, "splash");
  await page.locator("#cee-anim-state").waitFor();
  assert.match(await page.locator("#cee-anim-state").textContent(), /Blechy/);
  assert.equal(await page.locator("#cee-anim-work").isHidden(), true);
  assert.deepEqual(page.errors, []);
});

test("Design: a saved animation without changes is reset without asking", async () => {
  const page = await designPage();
  await dropPictures(page, [["a.png", 10], ["b.png", 100]]);
  await page.click("#cee-anim-use");
  await page.click("#cee-anim-reset");
  assert.equal(await stored(page), null);
  assert.equal(await page.locator("dialog.ui-dialog[open]").count(), 0);
  assert.deepEqual(page.errors, []);
});

test("Design: a file that is no picture is told, not taken", async () => {
  const page = await designPage();
  await page.setInputFiles("#cee-anim-file", h.file("broken.gif", readFileSync(GIF).subarray(0, 20)));
  await page.locator("#app-toasts .cee-toast", { hasText: "broken.gif" }).waitFor();
  assert.equal(await page.locator("#cee-anim-work").isHidden(), true);
  assert.equal(await page.locator("#cee-anim-loading").isHidden(), true, "the loading bar goes away");
  assert.deepEqual(page.errors, []);
});
