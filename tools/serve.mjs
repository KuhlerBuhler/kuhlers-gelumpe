#!/usr/bin/env node
/**
 * A static server for working on the page locally.
 *
 *   node tools/serve.mjs [port]
 *
 * No dependencies. Serves the same layout the Pages build produces, so a
 * path that works here works there.
 */
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { extname, join, normalize, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { ROUTES } from "./site-routes.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const TYPES = {
  ".html": "text/html; charset=utf-8", ".mjs": "text/javascript", ".js": "text/javascript",
  ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml",
  ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8", ".md": "text/markdown; charset=utf-8",
};

/**
 * @param {string} urlPath
 * @param {Array<[string, string]>} [extra] routes checked first; tests use
 *   them to serve support files that never belong to the page
 */
export function resolvePath(urlPath, extra = []) {
  const clean = decodeURIComponent(urlPath.split("?")[0]);
  for (const [prefix, dir] of [...extra, ...ROUTES]) {
    if (!(clean === prefix || clean.startsWith(prefix.endsWith("/") ? prefix : `${prefix}\0`))) continue;
    if (!prefix.endsWith("/")) return dir;
    const base = dir.startsWith("/") ? dir : join(ROOT, dir);
    const file = normalize(join(base, clean.slice(prefix.length) || "index.html"));
    return file.startsWith(base) ? file : null;
  }
  return null;
}

/**
 * @param {object} [opts.emu] {port, token} of a local emulator; served as
 *   /emu.json (null without one) so the page connects by itself, only to
 *   requests for this host
 */
export function startServer(port = 8737, { extra = [], emu = null } = {}) {
  const server = createServer(async (req, res) => {
    if (req.url.split("?")[0] === "/emu.json") {
      const ok = [`127.0.0.1:${port}`, `localhost:${port}`].includes(req.headers.host);
      res.writeHead(ok ? 200 : 403, { "content-type": "application/json", "cache-control": "no-store" });
      res.end(ok ? JSON.stringify(emu) : "{}");
      return;
    }
    let file;
    try {
      file = resolvePath(req.url, extra);
    } catch {
      res.writeHead(400, { "content-type": "text/plain" });
      res.end("bad request");
      return;
    }
    try {
      if (file && (await stat(file)).isDirectory()) file = join(file, "index.html");
      const body = await readFile(file);
      res.writeHead(200, { "content-type": TYPES[extname(file)] || "application/octet-stream" });
      res.end(body);
    } catch {
      res.writeHead(404, { "content-type": "text/plain" });
      res.end("not found");
    }
  });
  return new Promise((ok, fail) => {
    server.once("error", fail);
    server.listen(port, "127.0.0.1", () => { server.off("error", fail); ok(server); });
  });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const port = Number(process.argv[2] || process.env.PORT || 8737);
  startServer(port).then(() => console.log(`http://127.0.0.1:${port}/`));
}
