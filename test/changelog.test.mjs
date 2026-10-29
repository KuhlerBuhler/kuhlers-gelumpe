import { test } from "node:test";
import assert from "node:assert/strict";
import { systemOf, downloads } from "../site/app/changelog.mjs";

const files = ["GELUMPE_1.3.0_aarch64.dmg", "GELUMPE_1.3.0_x64.dmg", "GELUMPE_1.3.0_x64-setup.exe", "gelumpe_1.3.0_amd64.AppImage", "gelumpe_1.3.0_amd64.deb", "BLECH.patch", "BLECH-for-0a1b2c3d.bsdiff"]
  .map(name => ({ name, browser_download_url: `https://example.invalid/${name}` }));

test("the system comes from the browser's platform; a phone is none of the three", () => {
  assert.equal(systemOf({ platform: "MacIntel" }), "mac");
  assert.equal(systemOf({ userAgentData: { platform: "Windows" } }), "windows");
  assert.equal(systemOf({ platform: "Linux x86_64" }), "linux");
  assert.equal(systemOf({ platform: "Linux armv8l", userAgent: "Linux; Android 14" }), null);
});

test("a release offers the app for this system and the patch, nothing else; a Mac gets both of its apps", () => {
  assert.deepEqual(downloads(files, "mac").map(d => d.label), ["App für Mac mit Apple-Chip", "App für Intel-Mac", "Patch herunterladen"]);
  assert.equal(downloads(files, "mac")[1].href, "https://example.invalid/GELUMPE_1.3.0_x64.dmg");
  assert.deepEqual(downloads(files.filter(f => !f.name.endsWith("_x64.dmg")), "mac").map(d => d.label), ["App für Mac mit Apple-Chip", "Patch herunterladen"], "a release without the Intel file still offers the other");
  assert.equal(downloads(files, "windows")[0].href, "https://example.invalid/GELUMPE_1.3.0_x64-setup.exe");
  assert.equal(downloads(files, "linux")[0].href, "https://example.invalid/gelumpe_1.3.0_amd64.AppImage");
  assert.deepEqual(downloads(files, null).map(d => d.label), ["Patch herunterladen"], "no app to guess on an unknown system");
  assert.deepEqual(downloads([], "mac"), []);
});

test("the carried notes fill in the versions GitHub no longer has, newest first; GitHub's own release wins", async () => {
  const { entries } = await import("../site/app/changelog.mjs");
  const carried = [{ version: "1.3.6", de: "a", en: "b" }, { version: "1.3.5", de: "c", en: "d" }, { version: "1.3.10", de: "e", en: null }];
  const list = entries([{ tag_name: "v1.3.6", body: "x" }], carried);
  assert.deepEqual(list.map(e => [e.version, e.r ? "github" : "carried"]), [["1.3.10", "carried"], ["v1.3.6", "github"], ["1.3.5", "carried"]]);
  assert.deepEqual(entries([], carried).map(e => e.version), ["1.3.10", "1.3.6", "1.3.5"]);
});

test("data/release-notes.mjs is built from release-notes/ (node tools/release-notes.mjs build)", async () => {
  const { readFileSync } = await import("node:fs");
  const { notesModule, NOTES_MODULE } = await import("../tools/release-notes.mjs");
  assert.equal(readFileSync(NOTES_MODULE, "utf8"), notesModule(), "run: node tools/release-notes.mjs build");
});

test("the app keeps what was new and what was fixed, not the downloads, install hints or donation link", async () => {
  const { appNotes } = await import("../tools/release-lib.mjs");
  const md = "BLECH 1.3.4.\n\n**Herunterladen**\n- [App](https://example.invalid/x.dmg)\n\nAuf dem Mac einmal xattr.\n\n**Neu**\n- eins\n\n**Behoben**\n- zwei\n\n**Ohne App patchen**\n- BLECH.patch\n\nSpenden: https://example.invalid";
  assert.equal(appNotes(md), "BLECH 1.3.4.\n\n**Neu**\n- eins\n\n**Behoben**\n- zwei");
});

test("the app keeps the developer sections too", async () => {
  const { appNotes } = await import("../tools/release-lib.mjs");
  const md = "BLECH 1.3.7.\n\n**Neu**\n- eins\n\n**Neu für Entwickler**\n- zwei\n\n**Fixed for developers**\n- drei";
  assert.equal(appNotes(md), md);
});
