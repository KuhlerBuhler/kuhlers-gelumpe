import { test } from "node:test";
import assert from "node:assert/strict";
import { systemOf, downloads } from "../site/app/changelog.mjs";

const files = ["GELUMPE_1.3.0_aarch64.dmg", "GELUMPE_1.3.0_x64-setup.exe", "gelumpe_1.3.0_amd64.AppImage", "gelumpe_1.3.0_amd64.deb", "BLECH.patch", "BLECH-for-0a1b2c3d.bsdiff"]
  .map(name => ({ name, browser_download_url: `https://example.invalid/${name}` }));

test("the system comes from the browser's platform; a phone is none of the three", () => {
  assert.equal(systemOf({ platform: "MacIntel" }), "mac");
  assert.equal(systemOf({ userAgentData: { platform: "Windows" } }), "windows");
  assert.equal(systemOf({ platform: "Linux x86_64" }), "linux");
  assert.equal(systemOf({ platform: "Linux armv8l", userAgent: "Linux; Android 14" }), null);
});

test("a release offers the app for this system and the patch, nothing else", () => {
  assert.deepEqual(downloads(files, "mac").map(d => d.label), ["App für macOS", "Patch herunterladen"]);
  assert.equal(downloads(files, "windows")[0].href, "https://example.invalid/GELUMPE_1.3.0_x64-setup.exe");
  assert.equal(downloads(files, "linux")[0].href, "https://example.invalid/gelumpe_1.3.0_amd64.AppImage");
  assert.deepEqual(downloads(files, null).map(d => d.label), ["Patch herunterladen"], "no app to guess on an unknown system");
  assert.deepEqual(downloads([], "mac"), []);
});
