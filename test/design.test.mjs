import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const SITE = new URL("../site/", import.meta.url).pathname;
const DESIGN = join(SITE, "design");

function walk(dir) {
  return readdirSync(dir).flatMap(n => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
}

test("font URLs are relative, so the page works below a sub path", () => {
  for (const file of walk(DESIGN).filter(n => n.endsWith(".css"))) {
    const css = readFileSync(file, "utf8");
    assert.doesNotMatch(css, /url\(["']?\//, `${relative(DESIGN, file)} still has an absolute URL`);
  }
});

test("the font licences travel with the fonts", () => {
  const fonts = walk(join(DESIGN, "fonts")).map(p => relative(DESIGN, p));
  assert.ok(fonts.some(n => n.endsWith(".woff2")));
  for (const family of ["ibmplexsans", "ibmplexmono", "sora"]) {
    assert.ok(fonts.includes(`fonts/OFL-${family}.txt`), `licence for ${family} missing`);
  }
});

// The editor never grows its own design system page, an overview of every
// component.
test("there is no design system page", () => {
  for (const file of walk(SITE)) {
    const rel = relative(SITE, file);
    assert.doesNotMatch(rel, /design-?system|styleguide|components?\.html/i, `${rel} looks like a design system page`);
    if (rel.startsWith("design/")) {
      assert.doesNotMatch(rel, /\.html?$/i, `${rel}: the design folder holds no pages`);
    }
    if (/\.(html|mjs|js)$/.test(rel) && !rel.startsWith("design/")) {
      const text = readFileSync(file, "utf8");
      assert.doesNotMatch(text, /\/designsystem|COMPONENTS\.md/, `${rel} links to a design system page`);
    }
  }
});

test("the build publishes the design's code and fonts, not its documents", async () => {
  const { execFileSync } = await import("node:child_process");
  const { existsSync } = await import("node:fs");
  const root = new URL("../", import.meta.url).pathname;
  execFileSync("node", ["tools/build-site.mjs"], { cwd: root });
  assert.ok(existsSync(join(root, "dist/design/root.min.css")));
  assert.ok(existsSync(join(root, "dist/design/fonts/OFL-sora.txt")));
  assert.equal(existsSync(join(root, "dist/design/COMPONENTS.md")), false);
  assert.equal(existsSync(join(root, "dist/design/DESIGN.md")), false);
  assert.equal(existsSync(join(root, "dist/src/node.mjs")), false);
});
