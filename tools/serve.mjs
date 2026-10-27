#!/usr/bin/env node
/**
 * A static server for working on the page locally.
 *
 *   node tools/serve.mjs [port]
 *
 * No dependencies. Serves the same layout the Pages build produces, so a
 * path that works here works there.
 *
 * With GELUMPE_PUBLIC_ORIGIN (the address a reverse proxy serves the page at,
 * e.g. https://blech.example) the emulator is proxied below EMU_PATH on this
 * same origin. Then the browser talks to one host and one port only, which is
 * what HTTPS in front of the container needs: the page cannot reach
 * http://127.0.0.1:8740 on the server from the visitor's browser.
 */
import { createServer, request } from "node:http";
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
/** Where the emulator sits below the page when a reverse proxy serves it. */
export const EMU_PATH = "/emu-service";
// From one connection to the next: the emulator streams the display as server-sent events.
const HOP = ["connection", "keep-alive", "transfer-encoding", "upgrade", "te", "trailer",
  "proxy-authenticate", "proxy-authorization"];

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

/** The origin a reverse proxy serves the page at, or null when there is none. */
function parseOrigin(value) {
  try {
    return value ? new URL(value) : null;
  } catch {
    return null;
  }
}

/**
 * Whether a request's Host may see the emulator link: the page's own loopback, or the host the
 * reverse proxy puts in front. A rebound name is what this keeps away from the token.
 */
function knownHost(header, origin) {
  const host = String(header || "");
  const name = host.replace(/:\d+$/, "");
  if (["127.0.0.1", "localhost"].includes(name)) return true;
  return !!origin && (host === origin.host || name === origin.hostname);
}

/** Hands one request to the emulator service and streams its answer back as it comes. */
function proxyEmulator(req, res, emu) {
  const rest = req.url.slice(EMU_PATH.length) || "/";
  // The service only answers its own host name. No Origin either: the browser's origin is the
  // public one, which the service is not told about and must not need.
  const headers = { ...req.headers, host: `127.0.0.1:${emu.port}` };
  delete headers.origin;
  delete headers.referer;
  const upstream = request({
    host: "127.0.0.1",
    port: emu.port,
    method: req.method,
    path: rest.startsWith("/") ? rest : `/${rest}`,
    headers,
  }, up => {
    const headers = { ...up.headers };
    for (const name of HOP) delete headers[name];
    res.writeHead(up.statusCode, headers);
    res.flushHeaders();
    up.pipe(res);
  });
  upstream.setTimeout(0);                       // a full check runs for a long time before it answers
  upstream.on("error", error => {
    if (res.headersSent) { res.end(); return; }
    res.writeHead(502, { "content-type": "application/json", "cache-control": "no-store" });
    res.end(JSON.stringify({ error: `Der Emulator antwortet nicht: ${error.code || error.message}` }));
  });
  req.pipe(upstream);
}

/**
 * @param {object} [opts.emu] {port, token} of a local emulator; served as
 *   /emu.json (null without one) so the page connects by itself, only to
 *   requests for this host
 * @param {string} [opts.host] address to listen on; default GELUMPE_HOST, else
 *   127.0.0.1. A container needs 0.0.0.0, because a published port reaches the
 *   container's own address and never its loopback
 * @param {string} [opts.publicOrigin] the address a reverse proxy serves the
 *   page at; default GELUMPE_PUBLIC_ORIGIN. Set, the emulator is proxied below
 *   EMU_PATH and /emu.json names that path too. Unset, the page talks to the
 *   emulator's own port on 127.0.0.1 as before
 */
export function startServer(port = 8737, {
  extra = [], emu = null,
  host = process.env.GELUMPE_HOST || "127.0.0.1",
  publicOrigin = process.env.GELUMPE_PUBLIC_ORIGIN || "",
} = {}) {
  const origin = parseOrigin(publicOrigin);
  const server = createServer(async (req, res) => {
    const pathname = req.url.split("?")[0];
    if (pathname === "/emu.json") {
      const ok = knownHost(req.headers.host, origin);
      res.writeHead(ok ? 200 : 403, { "content-type": "application/json", "cache-control": "no-store" });
      res.end(!ok ? "{}" : JSON.stringify(emu && origin ? { ...emu, path: EMU_PATH } : emu));
      return;
    }
    if (pathname === EMU_PATH || pathname.startsWith(`${EMU_PATH}/`)) {
      if (!emu) {
        res.writeHead(404, { "content-type": "text/plain" });
        res.end("not found");
        return;
      }
      proxyEmulator(req, res, emu);
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
    server.listen(port, host, () => { server.off("error", fail); ok(server); });
  });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const port = Number(process.argv[2] || process.env.PORT || 8737);
  const host = process.env.GELUMPE_HOST || "127.0.0.1";
  startServer(port, { host }).then(() => console.log(`http://${host === "0.0.0.0" ? "127.0.0.1" : host}:${port}/`));
}
