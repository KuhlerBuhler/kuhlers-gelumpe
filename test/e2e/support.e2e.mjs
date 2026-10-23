import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";
import { severeViolations } from "./support/axe.mjs";

let h;
before(async () => { h = await setUp(); });
after(async () => { await h.tearDown(); });

const PNG = [0x89, 0x50, 0x4e, 0x47];
const size = bytes => { const v = new DataView(bytes.buffer, bytes.byteOffset); return [v.getUint32(16), v.getUint32(20)]; };
const colours = (page, id) => page.evaluate(id => {
  const c = document.getElementById(id);
  const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
  return new Set(Array.from({ length: d.length / 4 }, (_, i) => `${d[i * 4]},${d[i * 4 + 1]},${d[i * 4 + 2]}`)).size;
}, id);

test("the donate button opens the Unterstützen page: PayPal, an issue, a pull request, and pictures to share", async () => {
  const page = await h.page();
  await page.goto(h.url);
  await page.click("#cee-donate");
  await page.locator("#cee-support-page").waitFor();
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Unterstützen");
  assert.deepEqual(await page.locator("#cee-support-page h2").allTextContents(), ["Spenden", "Bug gefunden oder eine Idee?", "Dein Plugin für alle?", "Erzähl's weiter"]);
  assert.equal(await page.getAttribute("#cee-support-paypal", "href"), "https://www.paypal.me/kuhlerbuhler");
  assert.equal(await page.getAttribute("#cee-support-issues", "href"), "https://github.com/KuhlerBuhler/kuhlers-gelumpe/issues/new");
  assert.equal(await page.getAttribute("#cee-support-pr", "href"), "https://github.com/KuhlerBuhler/kuhlers-gelumpe/compare/develop");
  assert.deepEqual(await severeViolations(page), [], "axe, the Unterstützen page");
  assert.deepEqual(page.errors, []);
});

test("a profile picture with a name and wallpapers for a computer and a phone, saved as PNG", async () => {
  const page = await h.page();
  await page.goto(`${h.url}#support`);
  await page.fill("#cee-support-avatar-text", "Kuhler Buhler");
  await page.waitForFunction(() => document.getElementById("cee-support-avatar-canvas").getContext("2d").getImageData(0, 0, 1, 1).data[3] === 255);
  assert.equal(await colours(page, "cee-support-avatar-canvas"), 2, "on a plain background only its colour and the pixels of the display");
  const avatar = await h.download(page, () => page.click("#cee-support-avatar-save"));
  assert.deepEqual([...avatar.slice(0, 4)], PNG);
  assert.deepEqual(size(avatar), [1024, 1024]);
  await page.check("#cee-support-avatar-bands");
  await page.check("#cee-support-avatar-stars");
  assert.ok(await colours(page, "cee-support-avatar-canvas") > 2, "the profile picture can have the dither bands and the stars too, each on its own switch");

  assert.ok(await colours(page, "cee-support-wallpaper-canvas") > 2, "the wallpaper starts on the star field of the app background");
  await page.locator("#cee-support-wallpaper-format label", { hasText: "Handy" }).click();
  await page.locator("#cee-support-wallpaper-figure label", { hasText: "Augen" }).click();
  await page.locator("#cee-support-wallpaper-place label:has(input[value=top-right])").click();
  await page.locator("#cee-support-wallpaper-size").fill("30");
  await page.locator("#cee-support-wallpaper-look label", { hasText: "Eigene" }).click();
  await page.locator("#cee-support-wallpaper-ink").fill("#00ff00");
  await page.waitForFunction(() => document.getElementById("cee-support-wallpaper-canvas").dataset.format === "phone");
  const rows = await page.evaluate(() => {
    const c = document.getElementById("cee-support-wallpaper-canvas");
    const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
    const lit = [];
    let left = c.width;
    for (let y = 0; y < c.height; y += 4) for (let x = 0; x < c.width; x += 4) { const i = (y * c.width + x) * 4; if (d[i] === 0 && d[i + 1] === 255 && d[i + 2] === 0) { lit.push(y); left = Math.min(left, x); break; } }
    return { first: lit[0], last: lit.at(-1), height: c.height, left, width: c.width };
  });
  assert.ok(rows.last < rows.height / 2, "the eyes sit in the upper half, in the colour picked");
  assert.ok(rows.left > rows.width / 2, "and on the right");
  const wallpaper = await h.download(page, () => page.click("#cee-support-wallpaper-save"));
  assert.deepEqual(size(wallpaper), [1170, 2532]);
  assert.deepEqual(page.errors, []);
});
