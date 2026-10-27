/**
 * Where this page reaches the emulator service. Normally the service runs on this computer at
 * http://127.0.0.1:<port>. Behind a reverse proxy the page server hands the service through its
 * own path instead (tools/serve.mjs, GELUMPE_PUBLIC_ORIGIN), so browser and service share one
 * origin: that works over HTTPS, and the visitor's 127.0.0.1 is their own machine, not the server.
 */

/** The base address of the service for a link from /emu.json or `#emu=…`. */
export function emuBase(link) {
  if (!link) return "";
  if (link.path) return new URL(link.path, location.origin).href.replace(/\/+$/, "");
  return `http://127.0.0.1:${link.port}`;
}

/** The link as `#emu=…` carries it over to the emulator's own window: its path when proxied, else its port. */
export function emuHash(link) {
  return `${link.path || link.port}:${link.token}`;
}
