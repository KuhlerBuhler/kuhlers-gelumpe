import { test } from "node:test";
import assert from "node:assert/strict";
import { emuBase, emuHash } from "../site/app/emu-link.mjs";

test("the emulator is reached at its own port, or through the page's path behind a proxy", () => {
  globalThis.location = { origin: "https://blech.example" };
  try {
    assert.equal(emuBase({ port: 8740, token: "k" }), "http://127.0.0.1:8740");
    assert.equal(emuBase({ port: 8740, token: "k", path: "/emu-service" }), "https://blech.example/emu-service");
    assert.equal(emuBase({ port: 8740, token: "k", path: "/emu-service/" }), "https://blech.example/emu-service", "no double slash before a route");
    assert.equal(emuBase(null), "");
  } finally {
    delete globalThis.location;
  }
});

test("the emulator's own window carries the path when there is one, else the port", () => {
  assert.equal(emuHash({ port: 8740, token: "k" }), "8740:k");
  assert.equal(emuHash({ port: 8740, token: "k", path: "/emu-service" }), "/emu-service:k");
});
