import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { setUp } from "./harness.mjs";
import { tempDir } from "../support/lifetime.mjs";
import { fakeService, TOKEN } from "./support/fake-emu.mjs";

// Behind a reverse proxy the page and the emulator share one origin: the page's own path carries the
// service, so the browser never needs port 8740. The service here is a stand-in.
const SD_DIR = tempDir("cee-e2e-sd-");
let h;
let fake;

before(async () => {
  fake = await fakeService("http://127.0.0.1", { sdDir: SD_DIR });
  h = await setUp(() => [], { emu: { port: fake.port, token: TOKEN }, publicOrigin: true });
});
after(async () => {
  fake.server.closeAllConnections?.();
  fake.server.close();
  await h.tearDown();
});

test("behind a reverse proxy the page loads its emulator from its own origin", async () => {
  const page = await h.page();
  // On this machine the service's own port would be reachable; a visitor's 127.0.0.1 is not the
  // server. Cutting it leaves only the proxied path.
  await page.route(`http://127.0.0.1:${fake.port}/**`, route => route.abort());
  await page.goto(h.url);
  await page.waitForFunction(() => sessionStorage.getItem("cee.emu") !== null);
  const link = JSON.parse(await page.evaluate(() => sessionStorage.getItem("cee.emu")));
  assert.equal(link.path, "/emu-service", "the page is told the path");
  assert.equal(link.port, fake.port, "the port stays in the link for texts that name it");
  await page.locator("#cee-emu-status", { hasText: "bereit" }).waitFor();
  // The card in the navbar talks to the same link.
  await page.locator("#cee-sd-status").waitFor();
  assert.ok(fake.seen.sd > 0, "the card state arrived through the proxy");
  assert.deepEqual(page.errors, []);
  await page.close();
});

test("a link that points at another host is dropped: the key stays on this page", async () => {
  const page = await h.page();
  const foreign = [];
  await page.route("https://evil.example/**", route => { foreign.push(route.request().url()); route.abort(); });
  await page.goto(`${h.url}#emu=//evil.example/x:${TOKEN}`);
  await page.waitForFunction(() => sessionStorage.getItem("cee.emu") !== null);
  const link = JSON.parse(await page.evaluate(() => sessionStorage.getItem("cee.emu")));
  assert.equal(link.path, "/emu-service", "the hostile link was not taken, the page's own link was");
  assert.deepEqual(foreign, [], "token and firmware never go to the other host");
  await page.locator("#cee-emu-status", { hasText: "bereit" }).waitFor();
  assert.doesNotMatch(page.url(), /evil\.example/, "nothing of the bad link stays in the address bar");
  await page.close();
});
