import { test } from "node:test";
import assert from "node:assert/strict";
import { request } from "node:http";
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
