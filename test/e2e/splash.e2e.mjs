import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp, go } from "./harness.mjs";

let h;
before(async () => { h = await setUp(); });
after(async () => { await h.tearDown(); });

// A picture made in the page itself: left half black, right half white.
async function dropPicture(page) {
  await page.evaluate(async () => {
    const c = document.createElement("canvas");
    c.width = 256;
    c.height = 128;
    const g = c.getContext("2d");
    g.fillStyle = "#fff";
    g.fillRect(0, 0, 256, 128);
    g.fillStyle = "#000";
    g.fillRect(0, 0, 128, 128);
    const blob = await new Promise(r => c.toBlob(r, "image/png"));
    const dt = new DataTransfer();
    dt.items.add(new File([blob], "half.png", { type: "image/png" }));
    const input = document.getElementById("cee-splash-file");
    input.files = dt.files;
    input.dispatchEvent(new Event("change"));
  });
  await page.locator("#cee-splash-work:not([hidden])").waitFor();
}

test("Startbild: a picture becomes splash.bmp, black is drawn, the guide names the menu", async () => {
  const page = await h.page();
  await page.goto(h.url);
  await go(page, "splash");
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Startbild");
  assert.equal(await page.locator("#cee-splash-download").isDisabled(), true, "nothing to download before a picture");
  await dropPicture(page);
  const download = page.waitForEvent("download");
  await page.locator("#cee-splash-download").click();
  const file = await download;
  assert.equal(file.suggestedFilename(), "splash.bmp");
  const bytes = await (await file.createReadStream()).toArray().then(parts => Buffer.concat(parts));
  assert.equal(bytes.length, 1086);
  assert.equal(bytes.subarray(0, 2).toString(), "BM");
  // top row, bottom-up file: the last row of pixel data; left 64 pixels drawn (bit 1), right 64 empty
  const top = bytes.subarray(62 + 63 * 16, 62 + 64 * 16);
  assert.deepEqual([...top], [...Array(8).fill(0xff), ...Array(8).fill(0)]);
  assert.match(await page.locator("#cee-splash-steps").textContent(), /SPLASH IMPORT/);
  assert.deepEqual(page.errors, []);
});
