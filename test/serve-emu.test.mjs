import { test } from "node:test";
import assert from "node:assert/strict";
import { createServer, get as httpGet, request } from "node:http";
import { startServer } from "../tools/serve.mjs";

const get = (port, host) => new Promise((ok, fail) => {
  const req = request({ host: "127.0.0.1", port, path: "/emu.json", headers: { host } }, res => {
    let body = "";
    res.on("data", c => { body += c; });
    res.on("end", () => ok({ status: res.statusCode, body }));
  });
  req.on("error", fail);
  req.end();
});

const send = (port, method, path, body, headers = {}) => new Promise((ok, fail) => {
  const req = request({ host: "127.0.0.1", port, path, method, headers }, res => {
    let text = "";
    res.setEncoding("utf8");
    res.on("data", c => { text += c; });
    res.on("end", () => ok({ status: res.statusCode, headers: res.headers, body: text }));
  });
  req.on("error", fail);
  req.end(body);
});

/** The first chunk of a streaming answer, before the answer ends; the stream is closed right after it. */
const firstChunk = (port, path, headers = {}) => new Promise((ok, fail) => {
  const req = httpGet({ host: "127.0.0.1", port, path, headers }, res => {
    res.setEncoding("utf8");
    res.once("data", chunk => {
      const seen = { status: res.statusCode, headers: res.headers, chunk };
      req.destroy();                        // the service streams until someone stops it
      ok(seen);
    });
  });
  req.on("error", error => { if (error.code !== "ECONNRESET") fail(error); });
});

test("the local page server tells only its own page where the emulator listens", async () => {
  const port = 19900 + Math.floor(Math.random() * 90);
  const server = await startServer(port, { emu: { port: 8740, token: "k" } });
  try {
    const own = await get(port, `127.0.0.1:${port}`);
    assert.equal(own.status, 200);
    assert.deepEqual(JSON.parse(own.body), { port: 8740, token: "k" });
    const rebound = await get(port, "attacker.example");
    assert.equal(rebound.status, 403, "a rebound host name gets nothing");
    assert.equal(rebound.body, "{}");
  } finally {
    server.close();
  }
});

test("without an emulator /emu.json says so instead of failing", async () => {
  const port = 19990 + Math.floor(Math.random() * 9);
  const server = await startServer(port);
  try {
    const r = await get(port, `127.0.0.1:${port}`);
    assert.equal(r.status, 200);
    assert.equal(r.body, "null");
  } finally {
    server.close();
  }
});

test("behind a reverse proxy the link names the page's own path, and only the proxied name gets it", async () => {
  const port = 19950 + Math.floor(Math.random() * 40);
  const server = await startServer(port, { emu: { port: 8740, token: "k" }, publicOrigin: "https://blech.example" });
  try {
    const publicHost = await get(port, "blech.example");
    assert.equal(publicHost.status, 200);
    assert.deepEqual(JSON.parse(publicHost.body), { port: 8740, token: "k", path: "/emu-service" });
    const local = await get(port, `127.0.0.1:${port}`);
    assert.deepEqual(JSON.parse(local.body), { port: 8740, token: "k", path: "/emu-service" }, "the path works on loopback too");
    const rebound = await get(port, "attacker.example");
    assert.equal(rebound.status, 403, "a name the proxy does not serve gets nothing");
    const otherPort = await get(port, "blech.example:1234");
    assert.equal(otherPort.status, 200, "the proxy may listen on another port than the public default");
  } finally {
    server.close();
  }
});

test("the page passes the emulator through its own path, with the service's host name and the stream", async () => {
  const seen = [];
  const sockets = new Set();
  const upstream = createServer((req, res) => {
    seen.push({ url: req.url, host: req.headers.host, origin: req.headers.origin, method: req.method, token: req.headers["x-emu-token"] });
    if (req.url.startsWith("/events")) {
      res.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-store" });
      res.write("event: status\ndata: {\"state\":\"empty\"}\n\n");
      return;                                   // stays open, as the service does
    }
    let body = "";
    req.setEncoding("utf8");
    req.on("data", c => { body += c; });
    req.on("end", () => {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ body, token: req.headers["x-emu-token"] ?? null }));
    });
  });
  upstream.on("connection", s => { sockets.add(s); s.on("close", () => sockets.delete(s)); });
  await new Promise(ok => upstream.listen(0, "127.0.0.1", ok));
  const upstreamPort = upstream.address().port;

  const port = 19910 + Math.floor(Math.random() * 40);
  const server = await startServer(port, {
    emu: { port: upstreamPort, token: "k" },
    publicOrigin: "https://blech.example",
  });
  try {
    const posted = await send(port, "POST", "/emu-service/boot?token=k", "firmware", {
      host: "blech.example", origin: "https://blech.example", "x-emu-token": "k", "content-type": "application/octet-stream",
    });
    assert.equal(posted.status, 200);
    assert.equal(seen.at(-1).url, "/boot?token=k", "the path below the page is cut off");
    assert.equal(seen.at(-1).host, `127.0.0.1:${upstreamPort}`, "the service hears its own host name");
    assert.equal(seen.at(-1).origin, undefined, "the page's public origin is not passed on");
    assert.equal(seen.at(-1).token, "k", "the key goes through");
    assert.deepEqual(JSON.parse(posted.body), { body: "firmware", token: "k" });

    // A same-origin GET and the display stream carry no Origin at all; they are the page's own.
    const events = await firstChunk(port, "/emu-service/events?token=k", { host: "blech.example" });
    assert.equal(events.status, 200);
    assert.match(events.headers["content-type"], /text\/event-stream/);
    assert.match(events.chunk, /event: status/, "the display stream comes through before the answer ends");
  } finally {
    for (const s of sockets) s.destroy();
    server.closeAllConnections?.();
    server.close();
    upstream.closeAllConnections?.();
    upstream.close();
  }
});

/** The page server and a stand-in emulator that counts what reaches it. */
async function withUpstream(options) {
  const seen = [];
  const upstream = createServer((req, res) => {
    seen.push(req.url);
    res.writeHead(200, { "content-type": "application/json" });
    res.end("{}");
  });
  await new Promise(ok => upstream.listen(0, "127.0.0.1", ok));
  const port = 19900 + Math.floor(Math.random() * 90);
  const server = await startServer(port, { emu: { port: upstream.address().port, token: "k" }, ...options });
  return {
    seen, port,
    async close() {
      server.closeAllConnections?.();
      server.close();
      upstream.closeAllConnections?.();
      upstream.close();
    },
  };
}

test("without a public origin the proxied path does not exist, even with an emulator", async () => {
  const { seen, port, close } = await withUpstream({});
  try {
    const r = await send(port, "GET", `/emu-service/status?token=k`);
    assert.equal(r.status, 404, "the local page server keeps the emulator's own port");
    assert.deepEqual(seen, [], "nothing reached the emulator");
  } finally {
    await close();
  }
});

test("the proxied path takes requests from the page's own origin only", async () => {
  const { seen, port, close } = await withUpstream({ publicOrigin: "https://blech.example" });
  try {
    const own = await send(port, "POST", "/emu-service/step?token=k", "x", { host: "blech.example", origin: "https://blech.example" });
    assert.equal(own.status, 200, "the page itself gets through");

    const foreign = await send(port, "POST", "/emu-service/step?token=k", "x", { host: "blech.example", origin: "https://evil.example" });
    assert.equal(foreign.status, 403, "another site's page does not drive the emulator");
    assert.match(foreign.body, /nicht steuern/);

    const crossSite = await send(port, "GET", "/emu-service/status?token=k", null, { host: "blech.example", "sec-fetch-site": "cross-site" });
    assert.equal(crossSite.status, 403, "a browser without Origin still names its site");

    const rebound = await send(port, "GET", "/emu-service/status?token=k", null, { host: "attacker.example" });
    assert.equal(rebound.status, 404, "a name the proxy does not serve is not the proxied path");

    assert.deepEqual(seen, ["/step?token=k"], "only the page's own request reached the emulator");
  } finally {
    await close();
  }
});

test("without an emulator the proxied path is not there", async () => {
  const port = 19980 + Math.floor(Math.random() * 9);
  const server = await startServer(port, { publicOrigin: "https://blech.example" });
  try {
    const r = await send(port, "GET", "/emu-service/status", null, { host: "blech.example" });
    assert.equal(r.status, 404);
  } finally {
    server.close();
  }
});
