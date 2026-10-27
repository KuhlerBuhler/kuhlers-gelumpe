import { test } from "node:test";
import assert from "node:assert/strict";
import { PART, messages, split, splitBody } from "../tools/discord-release.mjs";

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

test("the first message names the version and links the release, the last is the link, only the first pings @everyone", () => {
  const out = messages({ tag_name: "v1.3.1", html_url: "https://github.com/o/r/releases/tag/v1.3.1", body: `@everyone\n${"y\n".repeat(3000)}` });
  assert.ok(out.length > 1);
  assert.equal(out[0].embeds[0].title, "BLECHTRIBE 1.3.1 ist da");
  assert.equal(out[0].embeds[0].url, "https://github.com/o/r/releases/tag/v1.3.1");
  assert.ok(out.slice(1, -1).every(m => !m.embeds[0].title));
  assert.deepEqual(out.at(-1), { allowed_mentions: { parse: [] }, content: "https://github.com/o/r/releases/tag/v1.3.1" });
  assert.equal(out[0].content, "@everyone");
  assert.deepEqual(out[0].allowed_mentions, { parse: ["everyone"] });
  assert.ok(out.slice(1).every(m => m.allowed_mentions.parse.length === 0 && !m.content?.includes("@")));
});

test("a release without notes still gets its message and the link", () => {
  assert.equal(messages({ tag_name: "v1.3.1", html_url: "u", body: "" }).length, 2);
});

test("both languages: German first, English in a part of its own, every part within the limit", () => {
  const de = Array.from({ length: 200 }, (_, i) => `- Zeile ${i} ${"x".repeat(30)}`).join("\n");
  const en = Array.from({ length: 200 }, (_, i) => `- line ${i} ${"y".repeat(30)}`).join("\n");
  const parts = splitBody(`${de}\n\n## English\n\n${en}`);
  assert.ok(parts.every(p => p.length <= PART));
  const first = parts.findIndex(p => p.startsWith("## English"));
  assert.ok(first > 0);
  assert.ok(parts.slice(0, first).every(p => !p.includes("line ")) && parts.slice(0, first).join("\n").includes("Zeile 199"));
  assert.ok(parts.slice(first).every(p => !p.includes("Zeile ")) && parts.slice(first).join("\n").includes("line 199"));
  assert.deepEqual(splitBody("Kurz\n\n## English\n\nShort"), ["Kurz", "## English\n\nShort"]);
  assert.deepEqual(splitBody("Nur deutsch"), ["Nur deutsch"], "an older release without English");
});

test("with both languages only the first message pings and the last is still the link", () => {
  const body = `${"a\n".repeat(2500)}\n## English\n\n${"b\n".repeat(2500)}`;
  const out = messages({ tag_name: "v1.3.5", html_url: "https://example.invalid/r", body });
  assert.ok(out.length >= 4);
  assert.equal(out[0].content, "@everyone");
  assert.ok(out.slice(1).every(m => !m.content?.includes("@everyone") && m.allowed_mentions.parse.length === 0));
  assert.ok(out.slice(0, -1).every(m => m.embeds[0].description.length <= PART));
  assert.ok(out.some(m => m.embeds?.[0].description.startsWith("## English")));
  assert.equal(out.at(-1).content, "https://example.invalid/r");
});
