import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { startServer, resolvePath } from "../tools/serve.mjs";

// Port 0: the system picks a free one, so two test runs on the same machine (two worktrees, two agents) do not collide on a fixed port.
let server, port;
before(async () => { server = await startServer(0); port = server.address().port; });
after(() => server.close());

const get = path => fetch(`http://127.0.0.1:${port}${path}`);

test("the page and everything it loads are served", async () => {
  const html = await (await get("/")).text();
  assert.match(html, /<title>Kuhler's GELUMPE<\/title>/);
  const refs = [...html.matchAll(/(?:href|src)="([^"]+)"/g)].map(m => m[1]).filter(r => !r.startsWith("data:") && !/^https?:/.test(r));
  assert.ok(refs.length >= 5);
  for (const ref of refs) {
    assert.doesNotMatch(ref, /^\//, `${ref} is absolute and breaks below a sub path`);
    assert.equal((await get("/" + ref)).status, 200, ref);
  }
});

test("the fonts the stylesheet names are served", async () => {
  const css = await (await get("/design/root.min.css")).text();
  const fonts = [...css.matchAll(/url\("?(fonts\/[^")?]+)/g)].map(m => m[1]);
  assert.ok(fonts.length >= 3);
  for (const font of fonts) {
    const res = await get("/design/" + font);
    assert.equal(res.status, 200, font);
    assert.equal(res.headers.get("content-type"), "font/woff2");
  }
});

test("the BLECH set and every patch it lists are served, as the Patcher page loads them", async () => {
  const { loadBlechSet, BLECH_SET_URL } = await import("../src/patcher.mjs");
  const set = await loadBlechSet(async url => {
    const res = await get(`/${url}`);
    assert.equal(res.status, 200, url);
    return res.json();
  });
  assert.equal(BLECH_SET_URL, "data/patches/blech.json");
  assert.ok(set.items.length >= 5);
  for (const p of set.items) assert.ok(p.id && p.label, p.url);
});

const ROOT = new URL("../", import.meta.url).pathname;
const walk = dir => readdirSync(dir).flatMap(n => {
  const p = join(dir, n);
  return statSync(p).isDirectory() ? walk(p) : [p];
});

test("nothing the page can load imports a node module", () => {
  for (const dir of ["src", "data", "site/app"]) {
    for (const file of walk(join(ROOT, dir)).filter(f => f.endsWith(".mjs"))) {
      if (file.endsWith("src/node.mjs")) continue;
      assert.doesNotMatch(readFileSync(file, "utf8"), /from\s+["']node:/, `${file} imports a node module`);
    }
  }
});

// Follow every static import from the entry point through the server, the
// way the browser would, so a module that only exists locally shows up.
test("every module the page imports is served", async () => {
  const seen = new Set();
  const queue = ["/app/main.mjs", "/src/index.mjs"];
  while (queue.length) {
    const path = queue.shift();
    if (seen.has(path)) continue;
    seen.add(path);
    const res = await get(path);
    assert.equal(res.status, 200, path);
    const code = await res.text();
    for (const m of code.matchAll(/(?:import|export)\s[^"']*?from\s+["'](\.{1,2}\/[^"']+)["']/g)) {
      queue.push(new URL(m[1], `http://x${path}`).pathname);
    }
  }
  assert.ok(seen.size > 10);
});

test("the server does not leave its directories", () => {
  assert.equal(resolvePath("/../package.json"), null);
  assert.equal(resolvePath("/src/../../package.json"), null);
});

test("a malformed path gets a 400, and the server keeps running", async () => {
  assert.equal((await get("/%E0%A4%A")).status, 400);
  assert.equal((await get("/")).status, 200);
});

test("the editor draws no status pills: status is plain text in the status colour (cee-status), nowhere the ui-pill box", () => {
  const files = [join("site", "index.html"), join("site", "app.css"), ...readdirSync("site/app").map(f => join("site/app", f))];
  for (const file of files) assert.doesNotMatch(readFileSync(file, "utf8"), /ui-pill/, `${file} uses ui-pill`);
  const css = readFileSync("site/app.css", "utf8");
  const rule = /\.cee-status \{([^}]*)\}/.exec(css)[1];
  assert.doesNotMatch(rule, /border|background|padding/, "no box around a status");
  for (const tone of ["ok", "warn", "error", "info"]) assert.match(css, new RegExp(`\\.cee-status\\[data-tone="${tone}"\\][^{]*\\{ color: var\\(--color-status-${tone}-text\\)`));
});
