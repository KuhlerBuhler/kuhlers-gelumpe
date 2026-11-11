import { test } from "node:test";
import assert from "node:assert/strict";
import { systemOf, downloads } from "../site/app/changelog.mjs";
import { releaseBody } from "../site/app/changelog.mjs";
import { loadLanguage, setLanguage } from "../site/app/i18n.mjs";
import { RELEASE_NOTES } from "../data/release-notes.mjs";

test("French release notes replace GitHub's foreign-language body where a French text exists", async () => {
  try {
    await loadLanguage("fr");
    assert.ok(RELEASE_NOTES.some(n => n.fr));
    for (const n of RELEASE_NOTES) {
      // A new release may ship before its French text; GitHub's body stays until then.
      if (!n.fr) { assert.equal(releaseBody({ tag_name: `v${n.version}`, body: "original" }), "original"); continue; }
      assert.ok(n.fr?.startsWith(`BLECH ${n.version} et l’application`), n.version);
      assert.match(n.fr, /\*\*(Corrections|Nouveautés)\*\*/);
      assert.equal(releaseBody({ tag_name: `v${n.version}`, body: "original" }), n.fr);
    }
    assert.equal(releaseBody({ tag_name: "v99.0.0", body: "new release" }), "new release");
    setLanguage("de");
    assert.equal(releaseBody({ tag_name: "v1.4.2", body: "original" }), "original");
  } finally { setLanguage("de"); }
});

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

test("the release the person has shows its notes without the download blocks, in both languages", async () => {
  const { withoutDownloads } = await import("../site/app/changelog.mjs");
  const { releaseBody: published } = await import("../tools/release-lib.mjs");
  const names = files.map(f => f.name.replace("GELUMPE_1.3.0", "Kuhlers GELUMPE_1.4.5").replace("gelumpe_1.3.0", "kuhlers-gelumpe_1.4.5"));
  const body = published("BLECHTRIBE 1.4.5 und die App 1.4.5.\n\n**Neu**\n- eins\n\n## English\n\nBLECHTRIBE 1.4.5 and the app 1.4.5.\n\n**New**\n- one\n", "1.4.5", names);
  assert.match(body, /Herunterladen/);
  const bare = withoutDownloads(body);
  assert.doesNotMatch(bare, /Herunterladen|Download|xattr|Assets|BLECH\.patch|Ohne App|without the app/);
  assert.match(bare, /BLECHTRIBE 1\.4\.5 und die App 1\.4\.5\.\n\n\*\*Neu\*\*\n- eins/);
  assert.match(bare, /## English\n+BLECHTRIBE 1\.4\.5 and the app 1\.4\.5\.\n\n\*\*New\*\*\n- one/);
  assert.equal(withoutDownloads("BLECH 1.4.1.\n\n**Behoben**\n- zwei"), "BLECH 1.4.1.\n\n**Behoben**\n- zwei", "notes without a download block stay as they are");
});

test("downloads go away for the installed release and for a newer one the update button brings, never in a browser", async () => {
  const { hasIt } = await import("../site/app/changelog.mjs");
  assert.equal(hasIt("v1.4.5", "v1.4.5", "1.4.5"), true, "the installed version");
  assert.equal(hasIt("v1.4.6", "v1.4.6", "1.4.5"), true, "the newest release, which the update button installs");
  assert.equal(hasIt("v1.4.2", "v1.4.6", "1.4.5"), false, "an older release keeps its downloads");
  assert.equal(hasIt("v1.4.7-beta", "v1.4.6", "1.4.5"), false, "a prerelease the update button does not offer");
  assert.equal(hasIt("v1.4.5", "v1.4.5", undefined), false, "a browser has no installed version");
});
