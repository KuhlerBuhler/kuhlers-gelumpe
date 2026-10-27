/**
 * Where this page reaches the emulator service. Normally the service runs on this computer at
 * http://127.0.0.1:<port>. Behind a reverse proxy the page server hands the service through its
 * own path instead (tools/serve.mjs, GELUMPE_PUBLIC_ORIGIN), so browser and service share one
 * origin: that works over HTTPS, and the visitor's 127.0.0.1 is their own machine, not the server.
 */

/**
 * The path of the service below this page's own origin, or null for one that points elsewhere.
 * A link is a stranger's text, so `//evil.example/x` and `/\evil.example/x` must not become
 * another host: that would send the key and the firmware there.
 */
export function emuOwnPath(path, origin = location.origin) {
  if (typeof path !== "string" || !path.startsWith("/")) return null;
  let url;
  try {
    url = new URL(path, origin);
  } catch {
    return null;
  }
  if (url.origin !== origin) return null;
  return url.pathname.replace(/\/+$/, "") || "/";
}

/** A link from `#emu=port:key`, or `#emu=/path:key` behind a reverse proxy; null for one that leads elsewhere. */
export function parseEmuLink(hash, origin = location.origin) {
  const m = String(hash).match(/(?:^#|&)emu=([\w./-]+):([\w-]+)/);
  if (!m) return null;
  if (/^\d+$/.test(m[1])) return { port: Number(m[1]), token: m[2] };
  const path = emuOwnPath(m[1], origin);
  return path ? { path, token: m[2] } : null;
}

/** The base address of the service for a link from /emu.json or `#emu=…`; empty when it leads elsewhere. */
export function emuBase(link) {
  if (!link) return "";
  if (link.path) {
    const path = emuOwnPath(link.path);
    return path ? new URL(path, location.origin).href : "";
  }
  return `http://127.0.0.1:${link.port}`;
}

/** The link as `#emu=…` carries it over to the emulator's own window: its path when proxied, else its port. */
export function emuHash(link) {
  return `${link.path || link.port}:${link.token}`;
}
