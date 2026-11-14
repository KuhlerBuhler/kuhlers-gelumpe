import { test } from "node:test";
import assert from "node:assert/strict";
import { DONE_KEY, VERSION_AT, compareVersions, deviceFacts, deviceReads, parseBlechVersion, seenBefore, startView, updateState } from "../site/app/start.mjs";
import { VERSION_AT as PATCH_AT } from "../tools/patch/blech_version.mjs";

const store = (init = {}) => {
  const m = new Map(Object.entries(init));
  return { getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, String(v)), map: m };
};
const text = s => { const b = new Uint8Array(16); b.set(new TextEncoder().encode(s)); return b; };

test("the start view: the hub once BLECHTRIBE is on the Electribe, in the emulator or was here before, else the welcome", () => {
  assert.equal(startView({}).view, "welcome");
  assert.deepEqual(startView({ device: { blech: null } }), { view: "welcome", found: true, blech: false }, "an Electribe without BLECHTRIBE keeps the welcome and is named");
  assert.deepEqual(startView({ device: { blech: { version: 1 } } }), { view: "hub", found: false, blech: true });
  assert.equal(startView({ emulator: true }).view, "hub");
  assert.equal(startView({ seen: true }).view, "hub");
  assert.equal(startView({ seen: true, device: { blech: null } }).found, true);
});

test("the version on the device: BLECH x.y.z from the patch's 16 bytes, null for anything else", () => {
  assert.equal(VERSION_AT, PATCH_AT, "the address the patch writes");
  assert.equal(parseBlechVersion(text("BLECH 1.5.0")), "1.5.0");
  assert.equal(parseBlechVersion(text("BLECH 1.4.12")), "1.4.12");
  assert.equal(parseBlechVersion(new Uint8Array(16).fill(0xff)), null, "a set without the patch");
  assert.equal(parseBlechVersion(new Uint8Array(16)), null);
  assert.equal(parseBlechVersion(text("HACK 1.0.0")), null);
  assert.equal(parseBlechVersion(null), null);
});

test("device against app: update when older, current, newer than this app, unknown without a version", () => {
  assert.equal(compareVersions("1.4.6", "1.5.0"), -1);
  assert.equal(compareVersions("1.10.0", "1.9.9"), 1);
  assert.equal(compareVersions("1.5", "1.5.0"), 0);
  assert.equal(updateState("1.4.6", "1.5.0"), "update");
  assert.equal(updateState("1.5.0", "1.5.0"), "current");
  assert.equal(updateState("1.6.0", "1.5.0"), "newer");
  assert.equal(updateState(null, "1.5.0"), "unknown");
});

test("the merker: kept answers stand; without one, earlier use counts once and is stored", () => {
  assert.equal(seenBefore(store({ [DONE_KEY]: "1" })), true);
  assert.equal(seenBefore(store({ [DONE_KEY]: "0", "cee.area": "patcher" })), false, "a stored no is not asked again");
  const fresh = store();
  assert.equal(seenBefore(fresh), false);
  assert.equal(fresh.map.get(DONE_KEY), "0");
  for (const init of [{ "cee.area": "patcher" }, { "cee.changelog.seen": "1.4.6" }, { "cee.scripts.v1": "[]" }]) {
    const s = store(init);
    assert.equal(seenBefore(s), true, JSON.stringify(init));
    assert.equal(s.map.get(DONE_KEY), "1");
  }
  assert.equal(seenBefore(store({ "cee.area": "start" })), false, "the start page alone is no sign");
  assert.equal(seenBefore({ getItem() { throw new Error("blocked"); } }), false, "blocked storage is a first visit");
});

test("device facts: one read each per session, the version only with BLECH's RAM read, failures give null", async () => {
  const reads = [];
  const session = {
    device: { ram: "blech", blech: {} },
    hardware: async () => { reads.push("hw"); return "red"; },
    readRamBlock: async (addr, n) => { reads.push([addr, n]); return text("BLECH 1.4.6"); },
  };
  assert.deepEqual(await deviceFacts(session), { hardware: "red", version: "1.4.6" });
  assert.deepEqual(await deviceFacts(session), { hardware: "red", version: "1.4.6" });
  assert.deepEqual(reads, [[VERSION_AT, 16], "hw"], "the version first, cached per session");
  const hacktribe = { device: { ram: "hacktribe", blech: null }, hardware: async () => "blue", readRamBlock: async () => { throw new Error("not asked"); } };
  assert.deepEqual(await deviceFacts(hacktribe), { hardware: "blue", version: null });
  const failing = { device: { ram: "blech", blech: {} }, hardware: async () => { throw new Error("timeout"); }, readRamBlock: async () => { throw new Error("timeout"); } };
  assert.deepEqual(await deviceFacts(failing), { hardware: null, version: null });
  assert.deepEqual(await deviceFacts(null), { hardware: null, version: null });
  const stuck = { device: { ram: "blech", blech: {} }, hardware: () => new Promise(() => {}), readRamBlock: async () => text("BLECH 1.4.6") };
  assert.deepEqual(await deviceFacts(stuck, 20), { hardware: null, version: "1.4.6" }, "a read that does not come back is unknown after the wait");
  const slow = { device: { ram: "blech", blech: {} }, hardware: async () => "red", readRamBlock: () => new Promise(done => setTimeout(done, 60, text("BLECH 1.4.6"))) };
  const late = deviceReads(slow, 20);
  assert.equal(await late.version, null, "unknown after the wait");
  assert.equal(await late.late.version, "1.4.6", "the read goes on and its answer can still be drawn");
});

test("device facts: a session busy with another read (the sidebar's LEDs, or the version) is waited for, not taken as unknown", async () => {
  // One operation at a time, as Session.exclusive: a second one while one runs is refused with kind "busy".
  const busySession = () => ({
    device: { ram: "blech", blech: {} },
    running: null,
    get busy() { return !!this.running; },
    async idle() { while (this.running) await this.running.catch(() => {}); },
    async exclusive(fn) {
      if (this.running) throw Object.assign(new Error("busy"), { kind: "busy" });
      this.running = fn();
      try { return await this.running; } finally { this.running = null; }
    },
    hardware() { return this.exclusive(async () => "red"); },
    readRamBlock() { return this.exclusive(async () => text("BLECH 1.0.0")); },
  });
  assert.deepEqual(await deviceFacts(busySession(), 1000), { hardware: "red", version: "1.0.0" }, "the flash read waits for the RAM read");
  const session = busySession();
  const leds = session.exclusive(() => new Promise(done => setTimeout(done, 30)));
  assert.deepEqual(await deviceFacts(session, 1000), { hardware: "red", version: "1.0.0" }, "both wait for the LED read");
  await leds;
});
