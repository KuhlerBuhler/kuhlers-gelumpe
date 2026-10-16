import { test } from "node:test";
import assert from "node:assert/strict";
import { isNewer, newerRelease } from "../site/app/update.mjs";

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
