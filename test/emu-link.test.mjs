import { test } from "node:test";
import assert from "node:assert/strict";
import { emuBase, emuHash, emuOwnPath, parseEmuLink } from "../site/app/emu-link.mjs";

const withPage = (origin, work) => {
  globalThis.location = { origin };
  try {
    return work();
  } finally {
    delete globalThis.location;
  }
};

test("the emulator is reached at its own port, or through the page's path behind a proxy", () => {
  withPage("https://blech.example", () => {
    assert.equal(emuBase({ port: 8740, token: "k" }), "http://127.0.0.1:8740");
    assert.equal(emuBase({ port: 8740, token: "k", path: "/emu-service" }), "https://blech.example/emu-service");
    assert.equal(emuBase({ port: 8740, token: "k", path: "/emu-service/" }), "https://blech.example/emu-service", "no double slash before a route");
    assert.equal(emuBase(null), "");
  });
});

test("a path that leaves the page's origin is no link: key and firmware stay here", () => {
  withPage("https://blech.example", () => {
    for (const path of ["//evil.example/x", "/\\evil.example/x", "https://evil.example/x", "evil.example/x"]) {
      assert.equal(emuOwnPath(path), null, path);
      assert.equal(parseEmuLink(`#emu=${path}:k`), null, path);
      assert.equal(emuBase({ path, token: "k" }), "", path);
    }
    assert.equal(emuOwnPath("/emu-service"), "/emu-service");
    assert.equal(emuBase({ path: "//evil.example/x", token: "k" }), "", "a server answer is checked too");
  });
});

test("a link is a port or a path on this page, nothing else", () => {
  withPage("https://blech.example", () => {
    assert.deepEqual(parseEmuLink("#emu=8740:k"), { port: 8740, token: "k" });
    assert.deepEqual(parseEmuLink("#foo&emu=/emu-service:k"), { path: "/emu-service", token: "k" });
    assert.deepEqual(parseEmuLink("#emu=/emu-service/:k"), { path: "/emu-service", token: "k" }, "a trailing slash is not a route");
    assert.equal(parseEmuLink("#emu"), null);
    assert.equal(parseEmuLink(""), null);
  });
});

test("the emulator's own window carries the path when there is one, else the port", () => {
  assert.equal(emuHash({ port: 8740, token: "k" }), "8740:k");
  assert.equal(emuHash({ port: 8740, token: "k", path: "/emu-service" }), "/emu-service:k");
});
