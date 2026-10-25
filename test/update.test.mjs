import { test } from "node:test";
import assert from "node:assert/strict";
import { isNewer, newerRelease, unseenNews, showNews, installRelease } from "../site/app/update.mjs";

test("version comparison is numeric, not textual", () => {
  assert.equal(isNewer("v0.10.0", "0.9.9"), true);
  assert.equal(isNewer("v1.0.0", "1.0.0"), false);
  assert.equal(isNewer("0.1.0", "v0.1.1"), false);
  assert.equal(isNewer("1.0", "1.0.1"), false);
});

const answer = (ok, body) => async () => ({ ok, json: async () => body });

test("a newer release is returned, an older or equal one is not", async () => {
  const release = { tag_name: "v0.2.0", html_url: "https://github.com/x/y/releases/tag/v0.2.0" };
  assert.deepEqual(await newerRelease("0.1.0", answer(true, release)), release);
  assert.equal(await newerRelease("0.2.0", answer(true, release)), null);
});

test("404 of a private repository, a network error or odd JSON mean no news", async () => {
  assert.equal(await newerRelease("0.1.0", answer(false, {})), null);
  assert.equal(await newerRelease("0.1.0", async () => { throw new Error("offline"); }), null);
  assert.equal(await newerRelease("0.1.0", answer(true, { tag_name: 5 })), null);
});

const NEWS = [{ version: "1.3.0", items: ["a"] }, { version: "1.4.0", items: ["b", "c"] }];

test("the news since the version last seen, or only this version's after the first start", () => {
  assert.deepEqual(unseenNews("1.4.0", "1.2.0", NEWS).map(n => n.version), ["1.3.0", "1.4.0"]);
  assert.deepEqual(unseenNews("1.4.0", "1.3.0", NEWS).map(n => n.version), ["1.4.0"]);
  assert.deepEqual(unseenNews("1.4.0", "1.4.0", NEWS), []);
  assert.deepEqual(unseenNews("1.3.0", null, NEWS).map(n => n.version), ["1.3.0"]);
  assert.deepEqual(unseenNews("1.3.1", null, NEWS), [], "a patch release without news says nothing");
});

test("the news shows once, as a toast that stays, and never in a browser", () => {
  const store = new Map();
  const storage = { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) };
  const shown = [];
  const toast = (...args) => shown.push(args);
  showNews(toast, { version: "1.3.0" }, storage);
  showNews(toast, { version: "1.3.0" }, storage);
  showNews(toast, undefined, storage);
  assert.equal(shown.length, 1);
  assert.equal(shown[0][0], "BLECHTRIBE 1.3 ist da. Was neu ist, steht unter Changelogs.");
  assert.deepEqual(shown[0].slice(1), ["info", { stay: true }]);
});

const RELEASE = { tag_name: "v1.3.2", html_url: "https://github.com/x/y/releases/tag/v1.3.2" };

function fakeCore(run) {
  class Channel {}
  return { Channel, invoke: async (command, args) => run(command, args) };
}

test("the install shows the progress, then says what happens next", async () => {
  const labels = [], toasts = [], pages = [];
  const core = fakeCore((command, args) => {
    assert.equal(command, "update_install");
    assert.equal(args.tag, "v1.3.2");
    args.events.onmessage({ stage: "download", received: 50, total: 200 });
    args.events.onmessage({ stage: "install" });
    return { file: "/Users/x/Downloads/a.dmg", quits: false };
  });
  const ok = await installRelease(RELEASE, { core, toast: (...a) => toasts.push(a), label: t => labels.push(t), openPage: u => pages.push(u) });
  assert.equal(ok, true);
  assert.deepEqual(labels, ["Lade …", "Lade … 25 %", "Installation startet …", "Installation geöffnet"]);
  assert.equal(toasts.length, 1);
  assert.equal(toasts[0][1], "ok");
  assert.deepEqual(pages, []);
});

test("a failure shows the error and falls back to the release page", async () => {
  const labels = [], toasts = [], pages = [];
  const core = fakeCore(() => { throw "Das Release hat keine Datei für dieses System."; });
  const ok = await installRelease(RELEASE, { core, toast: (...a) => toasts.push(a), label: t => labels.push(t), openPage: u => pages.push(u) });
  assert.equal(ok, false);
  assert.equal(labels.at(-1), "Neue Version verfügbar");
  assert.equal(toasts[0][1], "error");
  assert.match(toasts[0][0], /Das Release hat keine Datei/);
  assert.deepEqual(pages, [RELEASE.html_url]);
});

test("without the desktop bridge the release page opens", async () => {
  const pages = [];
  assert.equal(await installRelease(RELEASE, { core: undefined, toast() {}, openPage: u => pages.push(u) }), false);
  assert.deepEqual(pages, [RELEASE.html_url]);
});
