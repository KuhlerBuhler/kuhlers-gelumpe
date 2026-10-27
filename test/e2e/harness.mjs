/**
 * Shared set-up for the browser tests: the static server, a browser, and a
 * scratch directory for generated files. Uses the installed Chrome unless
 * E2E_CHANNEL says otherwise, so no browser download is needed.
 */
import { afterEach } from "node:test";
import { writeFileSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "playwright";
import { startServer } from "../../tools/serve.mjs";
import { tempDir } from "../support/lifetime.mjs";

const SUPPORT = new URL("./support/", import.meta.url).pathname;

// A page left open keeps its timers running (the device page reads the LEDs four times a second), so the pages of
// earlier tests slow the later ones down. No test hands a page on to the next one.
const open = new Set();
afterEach(async () => {
  const contexts = [...open];
  open.clear();
  await Promise.all(contexts.map(c => c.close().catch(() => {})));
});

/**
 * @param {(dir: string) => Array<[string, string]>} [routes] more served paths, built from the scratch directory
 * @param {{realDevices?: boolean, emu?: {port: number, token: string}, publicOrigin?: string | true}} [options]
 *   `realDevices`: the page knows the measured builds by their signatures, for a test against the emulator running the user's own firmware.
 *   `emu` and `publicOrigin` put the page behind a reverse proxy: `true` for the origin the page is then served at
 */
export async function setUp(routes = () => [], { realDevices = false, emu = null, publicOrigin = "" } = {}) {
  const dir = tempDir("cee-e2e-");
  const extra = [
    ["/test-support/files/", `${dir}/`],
    ["/test-support/", SUPPORT],
    ...(realDevices ? [] : [["/data/devices.mjs", join(SUPPORT, "devices.mjs")]]),
    ...routes(dir),
  ];
  // The test files run side by side, so a port picked at random can already be taken.
  let port;
  let server;
  for (let attempt = 0; !server; attempt++) {
    port = 19000 + Math.floor(Math.random() * 20000);
    const origin = publicOrigin === true ? `http://127.0.0.1:${port}` : publicOrigin;
    try { server = await startServer(port, { extra, emu, publicOrigin: origin }); } catch (error) { if (attempt >= 20 || error.code !== "EADDRINUSE") throw error; }
  }
  const browser = await chromium.launch({ channel: process.env.E2E_CHANNEL || "chrome" });
  return {
    url: `http://127.0.0.1:${port}/`,
    browser,
    dir,
    file(name, bytes) {
      const path = join(dir, name);
      writeFileSync(path, bytes);
      return path;
    },
    /** `autoConnect`: the page connects to a plugged-in Electribe by itself; off here, the tests click connect. */
    async page({ device = false, autoConnect = false } = {}) {
      const context = await browser.newContext({ acceptDownloads: true, locale: "de-DE" });
      open.add(context);
      if (!autoConnect) await context.addInitScript(() => {
        try {
          const saved = JSON.parse(localStorage.getItem("cee.settings") ?? "{}") ?? {};
          if (!("autoConnect" in saved)) localStorage.setItem("cee.settings", JSON.stringify({ ...saved, autoConnect: false }));
        } catch { /* blocked storage: the default holds */ }
      });
      context.setDefaultTimeout(20_000);
      // The changelog page asks GitHub for the releases; tests never reach the network and see none.
      await context.route("https://api.github.com/**", route => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
      const page = await context.newPage();
      if (device) await page.addInitScript(() => { window.__ceeStubReady = import("/test-support/install.mjs"); });
      const errors = [];
      page.on("pageerror", e => errors.push(e.message));
      page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
      page.errors = errors;
      return page;
    },
    async download(page, click) {
      const [download] = await Promise.all([page.waitForEvent("download"), click()]);
      return new Uint8Array(readFileSync(await download.path()));
    },
    async tearDown() {
      await browser.close();
      server.close();
    },
  };
}

/** Select a preset after its record has arrived from the connected session. */
export async function pickPreset(page, slot, prefix = "cee") {
  const id = `${prefix}-fx-slot`;
  const name = (await page.locator(`#${id} option[value='${slot}']`).textContent()).replace(/^\d+\s+/, "");
  if (await page.locator(`#${id}`).inputValue() !== String(slot)) await page.selectOption(`#${id}`, String(slot));
  await page.waitForFunction(({ prefix, name }) =>
    document.querySelector(`#${prefix}-fx-editor input[type=text]`)?.value === name,
  { prefix, name });
}

/** Open a page the way a person does: the sidebar entry, or for the real device the menu in the navbar. */
export async function go(page, id) {
  if (id !== "device") {
    if (id === "emu" && await page.locator("#cee-mode").isVisible()) {
      await page.click("#cee-mode-button");
      await page.click("#cee-mode-menu [data-value=emu]");
      return;
    }
    // Presets and Modulationen have no sidebar entry any more, only their address
    if (["fx", "mod"].includes(id)) await page.evaluate(tab => { location.hash = tab; }, id);
    else await page.click(`#cee-tab-${id}`);
    return;
  }
  if (!(await page.locator("#cee-mode").isVisible())) await page.click("#cee-tab-emu");
  await page.click("#cee-mode-button");
  await page.click("#cee-mode-menu [data-value=device]");
}
