import { test } from "node:test";
import assert from "node:assert/strict";
import { PART, messages, split } from "../tools/discord-release.mjs";

test("the notes are cut at line ends into parts Discord takes", () => {
  const lines = Array.from({ length: 300 }, (_, i) => `- line ${i} ${"x".repeat(20)}`);
  const parts = split(lines.join("\r\n"));
  assert.ok(parts.length > 1);
  assert.ok(parts.every(p => p.length <= PART));
  assert.equal(parts.join("\n"), lines.join("\n"));
});

test("a line longer than a part is cut where it must", () => {
  const parts = split("a".repeat(PART + 10));
  assert.deepEqual(parts.map(p => p.length), [PART, 10]);
});

test("the first message names the version and links the release, the last is the link, nobody is pinged", () => {
  const out = messages({ tag_name: "v1.3.1", html_url: "https://github.com/o/r/releases/tag/v1.3.1", body: `@everyone\n${"y\n".repeat(3000)}` });
  assert.ok(out.length > 1);
  assert.equal(out[0].embeds[0].title, "BLECHTRIBE 1.3.1 ist da");
  assert.equal(out[0].embeds[0].url, "https://github.com/o/r/releases/tag/v1.3.1");
  assert.ok(out.slice(1, -1).every(m => !m.embeds[0].title));
  assert.deepEqual(out.at(-1), { allowed_mentions: { parse: [] }, content: "https://github.com/o/r/releases/tag/v1.3.1" });
  assert.ok(out.every(m => m.allowed_mentions.parse.length === 0));
});

test("a release without notes still gets its message and the link", () => {
  assert.equal(messages({ tag_name: "v1.3.1", html_url: "u", body: "" }).length, 2);
});
