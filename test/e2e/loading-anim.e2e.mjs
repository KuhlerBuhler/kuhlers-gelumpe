import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { setUp, go } from "./harness.mjs";
import { decodeAnimation, encodeAnimation, frameToPixels, MAX_BYTES, FRAME_BYTES } from "../../src/loading-anim.mjs";

let h;
before(async () => { h = await setUp(); });
after(async () => { await h.tearDown(); });

const GIF = new URL("../fixtures/gif/ffmpeg-moving.gif", import.meta.url).pathname;
const KEY = "cee.loading.anim";

/** The Design page on its Ladeanimation tab; `reduce` starts it with reduced motion, so the preview follows the gallery. */
async function designPage({ reduce = true } = {}) {
  const page = await h.page();
  if (reduce) await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(h.url);
  await go(page, "splash");
  await page.click("#cee-design-tab-anim");
  await page.locator("#cee-anim-slot-text:not(:empty)").waitFor();
  return page;
}

/** Pictures made in the page, one PNG per entry: "black" fills it, "white" leaves it empty, a number draws a bar that wide. */
async function dropPictures(page, list, input = "cee-anim-file") {
  await page.evaluate(async ([list, input]) => {
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
    const field = document.getElementById(input);
    field.files = dt.files;
    field.dispatchEvent(new Event("change", { bubbles: true }));
  }, [list, input]);
}

const stored = async page => {
  const text = await page.evaluate(key => localStorage.getItem(key), KEY);
  return text ? Uint8Array.from(Buffer.from(text, "base64")) : null;
};
const saved = async page => decodeAnimation(await stored(page));
const slotText = page => page.locator("#cee-anim-slot-text").textContent();
const stateText = page => page.locator("#cee-anim-state").textContent();
const canSave = async page => (await page.locator("#cee-anim-use").isVisible()) && !(await page.locator("#cee-anim-use").isDisabled());
const toSlot = async (page, s) => { await page.locator("#cee-anim-progress").fill(String(s)); };
const filled = page => page.locator("#cee-anim-slot-picture").isVisible();
const lcdShot = page => page.locator("#cee-anim-preview").evaluate(c => c.toDataURL());
const same = (a, b) => a.every((x, i) => x === b[i]);

test("Design: two tabs, Startbild and Ladeanimation; the gallery stands with 100 empty slots from the start", async () => {
  const page = await h.page();
  await page.goto(h.url);
  await go(page, "splash");
  assert.deepEqual(await page.locator("#cee-design-tabs [role=tab]").allTextContents(), ["Startbild", "Ladeanimation"]);
  assert.equal(await page.locator("#cee-design-panel-splash").isVisible(), true, "Startbild first");
  await page.click("#cee-design-tab-anim");
  assert.equal(await page.locator("#cee-design-panel-anim .ui-section-title").textContent(), "Ladeanimation");
  assert.equal(await page.locator("#cee-anim-gallery").isVisible(), true);
  assert.equal(await slotText(page), "Bild 1 von 100, 0 %. Leer, das Display bleibt hier leer.");
  assert.equal(await page.locator("#cee-anim-slot-drop").isVisible(), true, "an empty slot is a drop field with a plus");
  assert.equal(await page.locator("#cee-anim-slot-drop .lucide-plus").count(), 1);
  assert.equal(await page.locator("#cee-anim-edit").isVisible(), true, "the pen also on an empty slot");
  assert.equal(await page.locator("#cee-anim-prev").isDisabled(), true);
  assert.equal(await page.locator("#cee-anim-use").isVisible(), false, "nothing to save without pictures");
  assert.equal(await page.locator("#cee-anim-size-field").isHidden(), true);
  assert.equal(await page.locator("#cee-anim-mode-field").isHidden(), true, "no stretch or repeat without an import");
  assert.equal(await page.locator(".cee-lcd-frame #cee-anim-preview.cee-lcd").count(), 1, "the preview is drawn as the device display");
  assert.equal(await page.locator("#cee-anim .ui-pill, #cee-anim .cee-status, #cee-anim .ui-chip").count(), 0, "no pill or chip look");
  assert.deepEqual(page.errors, []);
});

test("Design: a GIF with fewer than 100 frames is stretched over the slots by default, empty slots carry the picture before", async () => {
  const page = await designPage();
  await page.setInputFiles("#cee-anim-file", GIF);
  await page.locator("#cee-anim-slot-picture:not([hidden])").waitFor();
  assert.equal(await page.locator("#cee-anim-mode-field").isVisible(), true);
  assert.equal(await page.locator("#cee-anim-mode-stretch").isChecked(), true, "Strecken first");
  assert.match(await page.locator("#cee-anim-mode-help").textContent(), /3 Bilder laufen einmal von 0 bis 100 %/);
  assert.equal(await slotText(page), "Bild 1 von 100, 0 %. ffmpeg-moving 1");
  await toSlot(page, 1);
  assert.equal(await filled(page), false);
  assert.equal(await slotText(page), "Bild 2 von 100, 1 %. Leer, das Display zeigt hier weiter Bild 1.");
  await toSlot(page, 33);
  assert.equal(await slotText(page), "Bild 34 von 100, 33 %. ffmpeg-moving 2");
  await toSlot(page, 66);
  assert.match(await slotText(page), /ffmpeg-moving 3$/);
  assert.match(await page.locator("#cee-anim-size-text").textContent(), /^\d+,\d von 16 KB$/);
  assert.match(await stateText(page), /Änderungen noch nicht gespeichert/);
  await page.click("#cee-anim-use");
  const anim = await saved(page);
  assert.equal(anim.progress.length, 100, "one progress picture per slot");
  assert.equal(same(anim.progress[32], anim.progress[0]), true, "slots 1 to 32 keep picture 1");
  assert.equal(same(anim.progress[33], anim.progress[32]), false, "picture 2 from slot 33 on");
  assert.equal(same(anim.progress[99], anim.progress[66]), true);
  assert.match(await stateText(page), /deine Animation.*Gespeichert\./);
  assert.equal(await canSave(page), false);
  assert.deepEqual(page.errors, []);
});

test("Design: Wiederholen plays the GIF again and again, slot n takes frame n % k, the size follows", async () => {
  const page = await designPage();
  await page.setInputFiles("#cee-anim-file", GIF);
  await page.locator("#cee-anim-slot-picture:not([hidden])").waitFor();
  const stretched = await page.locator("#cee-anim-size-text").textContent();
  await page.locator("#cee-anim-mode-repeat").check({ force: true });
  await toSlot(page, 1);
  assert.equal(await filled(page), true, "no empty slot when repeating");
  assert.match(await slotText(page), /ffmpeg-moving 2$/);
  await toSlot(page, 3);
  assert.match(await slotText(page), /ffmpeg-moving 1$/, "3 % 3 = 0");
  await toSlot(page, 98);
  assert.match(await slotText(page), /ffmpeg-moving 3$/, "98 % 3 = 2");
  assert.notEqual(await page.locator("#cee-anim-size-text").textContent(), stretched, "the meter shows what the repeats cost");
  await page.click("#cee-anim-use");
  const anim = await saved(page);
  assert.equal(same(anim.progress[3], anim.progress[0]), true);
  assert.equal(same(anim.progress[1], anim.progress[0]), false);
  assert.equal(same(anim.progress[4], anim.progress[1]), true);
  await page.locator("#cee-anim-mode-stretch").check({ force: true });
  assert.match(await stateText(page), /noch nicht gespeichert/, "back to stretch is a change");
  assert.deepEqual(page.errors, []);
});

test("Design: an import over filled slots asks first; several pictures at once go in by name", async () => {
  const page = await designPage();
  await page.setInputFiles("#cee-anim-file", GIF);
  await page.locator("#cee-anim-slot-picture:not([hidden])").waitFor();
  await dropPictures(page, [["b-2.png", 64], ["b-1.png", 32]]);
  const dialog = page.locator("dialog.ui-dialog[open]");
  await dialog.waitFor();
  assert.match(await dialog.textContent(), /Galerie ersetzen\?.*3 Bilder/s);
  await dialog.getByRole("button", { name: "Abbrechen" }).click();
  assert.match(await slotText(page), /ffmpeg-moving 1$/, "Abbrechen keeps the gallery");
  await dropPictures(page, [["b-2.png", 64], ["b-1.png", 32]]);
  await dialog.getByRole("button", { name: "Ersetzen" }).click();
  await page.waitForFunction(() => document.getElementById("cee-anim-slot-text").textContent.endsWith("b-1"));
  await toSlot(page, 50);
  assert.match(await slotText(page), /b-2$/, "two pictures: slots 0 and 50");
  assert.match(await page.locator("#cee-anim-mode-help").textContent(), /2 Bilder/);
  assert.deepEqual(page.errors, []);
});

test("Design: a single picture into one slot by its plus, and emptied again", async () => {
  const page = await designPage();
  await page.click("#cee-anim-next");
  await page.click("#cee-anim-next");
  assert.match(await slotText(page), /^Bild 3 von 100/);
  await dropPictures(page, [["only.png", 50]], "cee-anim-slot-file");
  await page.locator("#cee-anim-slot-picture:not([hidden])").waitFor();
  assert.equal(await slotText(page), "Bild 3 von 100, 2 %. only");
  assert.equal(await page.locator("dialog.ui-dialog[open]").count(), 0, "one slot does not ask");
  assert.equal(await page.locator("#cee-anim-mode-field").isHidden(), true);
  await page.click("#cee-anim-use");
  const anim = await saved(page);
  assert.equal(anim.progress[1].every(b => b === 0xff), true, "slots 0 and 1 blank");
  assert.equal(anim.progress[2].every(b => b === 0xff), false);
  await page.click("#cee-anim-remove");
  assert.equal(await page.locator("#cee-anim-slot-drop").isVisible(), true);
  assert.match(await slotText(page), /Leer, das Display bleibt hier leer\./);
  assert.deepEqual(page.errors, []);
});

test("Design: arrows, slider and play move through the slots; the preview runs by itself", async () => {
  const page = await designPage({ reduce: false });
  await page.setInputFiles("#cee-anim-file", GIF);
  await page.locator("#cee-anim-slot-picture:not([hidden])").waitFor();
  await page.click("#cee-anim-next");
  assert.equal(await page.locator("#cee-anim-progress").inputValue(), "1");
  await page.click("#cee-anim-prev");
  assert.equal(await page.locator("#cee-anim-progress").inputValue(), "0");
  await toSlot(page, 99);
  assert.equal(await page.locator("#cee-anim-next").isDisabled(), true);
  assert.equal(await page.locator("#cee-anim-progress-value").textContent(), "99 %");
  await toSlot(page, 0);
  assert.equal(await page.getAttribute("#cee-anim-play", "aria-label"), "Abspielen");
  await page.click("#cee-anim-play");
  assert.equal(await page.getAttribute("#cee-anim-play", "aria-label"), "Anhalten");
  await page.waitForFunction(() => Number(document.getElementById("cee-anim-progress").value) > 10);
  await page.click("#cee-anim-play");
  const stopped = await page.locator("#cee-anim-progress").inputValue();
  await page.waitForTimeout(200);
  assert.equal(await page.locator("#cee-anim-progress").inputValue(), stopped, "paused");
  // the preview runs on its own: its percent moves while the gallery stands
  const a = await page.locator("#cee-anim-preview-at").textContent();
  await page.waitForFunction(was => document.getElementById("cee-anim-preview-at").textContent !== was, a);
  assert.deepEqual(page.errors, []);
});

test("Design: with reduced motion the preview shows the slot of the gallery", async () => {
  const page = await designPage();
  await page.setInputFiles("#cee-anim-file", GIF);
  await page.locator("#cee-anim-slot-picture:not([hidden])").waitFor();
  const first = await lcdShot(page);
  await toSlot(page, 66);
  assert.equal(await page.locator("#cee-anim-preview-at").textContent(), "66 %");
  assert.notEqual(await lcdShot(page), first);
  await toSlot(page, 0);
  assert.equal(await lcdShot(page), first);
  assert.equal(await page.locator("#cee-anim-preview-toggle").isHidden(), true, "nothing runs, nothing to stop");
  assert.deepEqual(page.errors, []);
});

test("Design: the running preview can be stopped, then it shows the slot of the gallery", async () => {
  const page = await designPage({ reduce: false });
  await page.setInputFiles("#cee-anim-file", GIF);
  await page.locator("#cee-anim-slot-picture:not([hidden])").waitFor();
  assert.equal(await page.getAttribute("#cee-anim-preview-toggle", "aria-label"), "Vorschau anhalten");
  await page.click("#cee-anim-preview-toggle");
  assert.equal(await page.getAttribute("#cee-anim-preview-toggle", "aria-label"), "Vorschau abspielen");
  await toSlot(page, 66);
  assert.equal(await page.locator("#cee-anim-preview-at").textContent(), "66 %");
  await page.waitForTimeout(300);
  assert.equal(await page.locator("#cee-anim-preview-at").textContent(), "66 %", "stands");
  await page.click("#cee-anim-preview-toggle");
  await page.waitForFunction(() => document.getElementById("cee-anim-preview-at").textContent !== "66 %");
  assert.deepEqual(page.errors, []);
});

/** Draws a stroke on the editor's board from pixel (x0, y) to (x1, y). */
async function stroke(page, x0, x1, y) {
  const box = await page.locator("#cee-anim-board").boundingBox();
  const px = (x, yy) => [box.x + (x + 0.5) * box.width / 128, box.y + (yy + 0.5) * box.height / 64];
  await page.mouse.move(...px(x0, y));
  await page.mouse.down();
  await page.mouse.move(...px(x1, y), { steps: 4 });
  await page.mouse.up();
}

test("Design: the editor draws with the pen and takes away with the eraser, an empty slot gets its own picture", async () => {
  const page = await designPage();
  await page.click("#cee-anim-edit");
  const dialog = page.locator("#cee-anim-editor[open]");
  await dialog.waitFor();
  assert.equal(await page.locator("#cee-anim-editor-title").textContent(), "Bild 1 bearbeiten");
  assert.equal(await page.locator("#cee-anim-tool-pen").isChecked(), true);
  await stroke(page, 10, 60, 20);
  await page.click("#cee-anim-editor-apply");
  await page.locator("#cee-anim-slot-picture:not([hidden])").waitFor();
  assert.equal(await slotText(page), "Bild 1 von 100, 0 %. Bild 1");
  await page.click("#cee-anim-use");
  let px = frameToPixels((await saved(page)).progress[0]);
  assert.equal(px[20 * 128 + 10], 1, "drawn");
  assert.equal(px[20 * 128 + 60], 1, "the whole stroke");
  assert.equal(px[20 * 128 + 35], 1);
  assert.equal(px[40 * 128 + 35], 0, "nothing else");

  await page.click("#cee-anim-edit");
  await dialog.waitFor();
  await page.locator("#cee-anim-tool-eraser").check({ force: true });
  await stroke(page, 30, 40, 20);
  await page.click("#cee-anim-editor-apply");
  await page.click("#cee-anim-use");
  px = frameToPixels((await saved(page)).progress[0]);
  assert.equal(px[20 * 128 + 35], 0, "erased");
  assert.equal(px[20 * 128 + 10], 1, "the rest stays");

  // Abbrechen leaves the slot as it is
  await page.click("#cee-anim-edit");
  await dialog.waitFor();
  await stroke(page, 0, 127, 50);
  await dialog.getByRole("button", { name: "Abbrechen" }).click();
  assert.equal(await canSave(page), false, "nothing changed");
  assert.deepEqual(page.errors, []);
});

test("Design: invert turns the whole animation and the preview", async () => {
  const page = await designPage();
  await dropPictures(page, [["a.png", 10], ["b.png", 100]]);
  await page.locator("#cee-anim-slot-picture:not([hidden])").waitFor();
  await page.click("#cee-anim-use");
  const plain = await saved(page);
  const before = await lcdShot(page);
  await page.locator("#cee-anim-invert").setChecked(true, { force: true });
  assert.notEqual(await lcdShot(page), before, "the preview follows");
  assert.match(await stateText(page), /noch nicht gespeichert/);
  await page.click("#cee-anim-use");
  const turned = await saved(page);
  assert.equal(turned.progress[0].every((b, i) => b === (plain.progress[0][i] ^ 0xff)), true);
  assert.equal(turned.progress[99].every((b, i) => b === (plain.progress[99][i] ^ 0xff)), true);
  assert.deepEqual(page.errors, []);
});

test("Design: the waiting loop takes the slots from its percent on and comes back after a reload", async () => {
  const page = await designPage();
  await dropPictures(page, [["p.png", 20]], "cee-anim-slot-file");
  await page.locator("#cee-anim-slot-picture:not([hidden])").waitFor();
  for (const [s, w] of [[95, 60], [97, 90]]) {
    await toSlot(page, s);
    await dropPictures(page, [[`l-${s}.png`, w]], "cee-anim-slot-file");
    await page.locator("#cee-anim-slot-picture:not([hidden])").waitFor();
  }
  assert.equal(await page.locator("#cee-anim-loop-mode").isHidden(), true);
  await page.locator("#cee-anim-loop").setChecked(true, { force: true });
  assert.equal(await page.locator("#cee-anim-loop-percent").inputValue(), "95");
  assert.match(await slotText(page), /Teil der Warte-Schleife\.$/);
  await page.click("#cee-anim-use");
  const anim = await saved(page);
  assert.equal(anim.loop.length, 2);
  assert.equal(anim.loopFrom, 95);
  await page.reload();
  await go(page, "splash");
  await page.locator("#cee-anim-slot-picture:not([hidden])").waitFor();
  assert.equal(await page.locator("#cee-anim-loop").isChecked(), true);
  assert.equal(await page.locator("#cee-anim-loop-percent").inputValue(), "95");
  assert.equal(await canSave(page), false, "what comes back is what is saved");
  // the file keeps the loop pictures, not the gaps between them: they come back in a row from the loop's percent
  await toSlot(page, 96);
  assert.equal(await filled(page), true);
  await toSlot(page, 97);
  assert.equal(await filled(page), false);
  assert.match(await slotText(page), /Leer, die Warte-Schleife lässt es aus\. Teil der Warte-Schleife\.$/);
  assert.deepEqual(page.errors, []);
});

test("Design: an older file with the loop on a stall (byte 5 = 0) shows 95 % and is saved with it", async () => {
  const page = await designPage();
  const frame = fill => new Uint8Array(FRAME_BYTES).fill(fill);
  const old = encodeAnimation({ progress: [frame(0), frame(0x0f)], loop: [frame(0xff)], loopFrom: 0 }).bytes;
  await page.evaluate(([key, text]) => localStorage.setItem(key, text), [KEY, Buffer.from(old).toString("base64")]);
  await page.reload();
  await go(page, "splash");
  await page.locator("#cee-anim-slot-picture:not([hidden])").waitFor();
  assert.equal(await page.locator("#cee-anim-loop").isChecked(), true);
  assert.equal(await page.locator("#cee-anim-loop-percent").inputValue(), "95");
  await page.click("#cee-anim-use");
  assert.equal((await saved(page)).loopFrom, 95);
  assert.deepEqual(page.errors, []);
});

test("Design: an animation over 16 KB is refused inline with its most expensive pictures, thinning brings it under", async () => {
  const page = await designPage();
  // every picture the inverse of the one before: about 1 KB each
  await dropPictures(page, Array.from({ length: 24 }, (_, i) => [`f-${String(i).padStart(2, "0")}.png`, i % 2 ? "black" : "white"]));
  await page.locator("#cee-anim-slot-picture:not([hidden])").waitFor();
  assert.match(await page.locator("#cee-anim-size-text").textContent(), /^2\d,\d von 16 KB$/);
  assert.equal(await page.locator("#cee-anim-use").isDisabled(), true, "too big is not taken");
  const why = await page.locator("#cee-anim-too-big").textContent();
  assert.match(why, /zu groß/);
  assert.match(why, /f-\d\d \(1,0 KB\)/, "names the most expensive pictures");
  await page.click("#cee-anim-thin");
  const size = await page.locator("#cee-anim-size-text").textContent();
  assert.ok(Number(size.split(" ")[0].replace(",", ".")) * 1024 <= MAX_BYTES, size);
  assert.equal(await page.locator("#cee-anim-use").isDisabled(), false);
  assert.equal(await page.locator("#cee-anim-too-big").isVisible(), false);
  await page.click("#cee-anim-use");
  assert.ok((await stored(page)).length <= MAX_BYTES);
  assert.deepEqual(page.errors, []);
});

test("Design: the default comes back, also after a reload; unsaved work is asked for first", async () => {
  const page = await designPage();
  assert.equal(await page.locator("#cee-anim-reset").isVisible(), false, "nothing to restore without an own animation");
  await dropPictures(page, [["a.png", 10], ["b.png", 100]]);
  await page.locator("#cee-anim-slot-picture:not([hidden])").waitFor();
  await page.click("#cee-anim-use");
  assert.notEqual(await stored(page), null);
  await page.locator("#cee-anim-invert").setChecked(true, { force: true });
  await page.click("#cee-anim-reset");
  const dialog = page.locator("dialog.ui-dialog[open]");
  await dialog.waitFor();
  await dialog.getByRole("button", { name: "Abbrechen" }).click();
  assert.notEqual(await stored(page), null);
  await page.click("#cee-anim-reset");
  await dialog.getByRole("button", { name: "Standard wiederherstellen" }).click();
  await page.locator("#cee-anim-slot-drop:not([hidden])").waitFor();
  assert.equal(await stored(page), null);
  assert.match(await stateText(page), /Blechy/);
  assert.equal(await page.locator("#cee-anim-reset").isVisible(), false);
  assert.equal(await page.locator("#cee-anim-use").isVisible(), false);
  await page.reload();
  await go(page, "splash");
  await page.locator("#cee-anim-state").waitFor();
  assert.match(await stateText(page), /Blechy/);
  assert.equal(await page.locator("#cee-anim-slot-drop").isVisible(), true);
  assert.deepEqual(page.errors, []);
});

test("Design: a saved animation without changes is reset without asking", async () => {
  const page = await designPage();
  await dropPictures(page, [["a.png", 10], ["b.png", 100]]);
  await page.locator("#cee-anim-slot-picture:not([hidden])").waitFor();
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
  assert.equal(await page.locator("#cee-anim-slot-drop").isVisible(), true);
  assert.equal(await page.locator("#cee-anim-loading").isHidden(), true, "the loading bar goes away");
  assert.deepEqual(page.errors, []);
});
