import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { setUp } from "./harness.mjs";
import { severeViolations } from "./support/axe.mjs";

let h;
before(async () => { h = await setUp(); });
after(async () => { await h.tearDown(); });

test("the Doom page hands out both files for the card and says where they go and how to start", async () => {
  const page = await h.page();
  await page.goto(h.url);
  await page.click("#cee-tab-doom");
  await page.locator("#cee-doom-page").waitFor();
  assert.equal(await page.locator("#cee-nav-title").textContent(), "Doom");
  assert.match(await page.locator("#cee-doom-files").textContent(), /KORG\/blechtribe\/Doom\//);
  assert.match(await page.locator("#cee-doom-start").textContent(), /SHIFT und TAP/);
  for (const name of ["bin", "wad"]) {
    const file = await h.download(page, () => page.click(`#cee-doom-${name}`));
    assert.equal(file.length, readFileSync(new URL(`../../third_party/doom/doom.${name}`, import.meta.url)).length, `doom.${name} comes whole`);
    // through saveFile like every download, so the app window saves it too and the page says so
    await page.locator("#app-toasts .cee-toast", { hasText: `„doom.${name}“ gespeichert` }).waitFor();
  }
  assert.deepEqual(await severeViolations(page), [], "axe, the Doom page");
  assert.deepEqual(page.errors, []);
});
