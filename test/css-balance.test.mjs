import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";

// A lost closing brace makes the browser drop every rule after it without a word; merges did that once.
test("every own stylesheet closes each block it opens", () => {
  const files = ["site/app.css", ...readdirSync("site/app").filter(f => f.endsWith(".css")).map(f => `site/app/${f}`)];
  for (const file of files) {
    const css = readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
    let depth = 0;
    for (const ch of css) {
      if (ch === "{") depth++;
      if (ch === "}") depth--;
      assert.ok(depth >= 0, `${file}: a closing brace without an opening one`);
    }
    assert.equal(depth, 0, `${file}: ${depth} block(s) left open`);
  }
});
