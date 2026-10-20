import { test } from "node:test";
import assert from "node:assert/strict";
import { isNewer, newerRelease, unseenNews, showNews } from "../site/app/update.mjs";

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
  assert.match(shown[0][0], /^Neu in 1\.3:\n• /);
  assert.deepEqual(shown[0].slice(1), ["info", { stay: true }]);
});
