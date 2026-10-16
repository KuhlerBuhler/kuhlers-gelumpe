import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { applyPatches, PATCH_FORMAT } from "../src/patch.mjs";
import { sha256 } from "../src/firmware.mjs";
import { checkHooks, HOOK_KINDS, HOOK_POSITIONS } from "../src/hooks.mjs";
import { CHAINS, INCOMPATIBLE } from "../data/hooks.mjs";
import { makeFirmware } from "./helpers.mjs";

const read = path => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
const SPLASH = read("../data/patches/splash-editor.json");
const MFX = read("../data/patches/mfx-switch.json");
const [RUNTIME] = read("./fixtures/hooks-planned.json").patches;
const PATTERN_SWITCH = read("../data/patches/pattern-switch.json");
const FREE = 0x1a2100;

const hook = (site, chain, position = "before", swallow = false, kind = "instruction") => ({ site, kind, chain, position, swallow });
const patch = (id, ...hooks) => ({ id, hooks });

test("the built patches declare hooks that the chain table knows and that sit on bytes the patch writes", () => {
  for (const p of [SPLASH, MFX, PATTERN_SWITCH, RUNTIME]) assert.ok(checkHooks([p]).ok, `${p.id}: ${checkHooks([p]).reasons.join(" ")}`);
  for (const p of [SPLASH, MFX, PATTERN_SWITCH]) {
    assert.equal(p.version, 1, "the format stays version 1");
    assert.ok(p.hooks.length > 0);
    for (const h of p.hooks) {
      assert.ok(HOOK_KINDS.includes(h.kind) && HOOK_POSITIONS.includes(h.position) && typeof h.swallow === "boolean");
      const file = parseInt(h.site, 16) - 0xC0000000 + 0x100;
      const written = p.changes.some(c => c.bytes !== undefined && file >= c.file && file + 4 <= c.file + c.bytes.length / 2);
      assert.ok(written, `${p.id}: ${h.site} is not a word the patch writes`);
    }
  }
});

test("no site is listed twice within a chain of the table", () => {
  for (const [name, stages] of Object.entries(CHAINS)) {
    const sites = stages.flatMap(s => s.sites);
    assert.equal(new Set(sites).size, sites.length, `${name}: a site twice`);
  }
});

test("the splash editor and MFX 2 are accepted together, with no dependency, in either order", () => {
  for (const order of [[SPLASH, MFX], [MFX, SPLASH]]) {
    const res = checkHooks(order);
    assert.equal(res.ok, true, res.reasons.join(" "));
    assert.deepEqual(res.dependencies, []);
  }
});

test("input and frame runtime hooks coexist with splash and MFX while retaining the input dependency", () => {
  const core = { ...RUNTIME, hooks: RUNTIME.hooks.filter(h => ["0xC002837C", "0xC00836FC"].includes(h.site)) };
  assert.equal(core.hooks.length, 2);
  for (const order of [[SPLASH, MFX, core], [core, MFX, SPLASH]]) {
    const result = checkHooks(order);
    assert.equal(result.ok, true, result.reasons.join(" "));
    assert.equal(result.dependencies.length, 1);
    assert.match(result.dependencies[0], /mfx-switch.*script-runtime.*0xC002837C/);
  }
  for (const site of ["0xC002ADAC", "0xC0064D3C"]) {
    const overlap = { ...core, hooks: [...core.hooks, RUNTIME.hooks.find(h => h.site === site)] };
    const result = checkHooks([SPLASH, overlap]);
    assert.equal(result.ok, false);
    assert.equal(result.reasons.length, 1);
    assert.match(result.reasons[0], /splash-editor und script-runtime passen nicht zusammen/);
  }
});

test("two patches on the same site are refused, whatever the kind and position", () => {
  const res = checkHooks([patch("a", hook("0xC00700D8", "key-dispatch")), patch("b", hook("0xC00700D8", "key-dispatch", "after", false, "call"))]);
  assert.equal(res.ok, false);
  assert.equal(res.reasons.length, 1);
  assert.match(res.reasons[0], /^b: Einhängestelle 0xC00700D8 ist schon von a besetzt/);
  const once = checkHooks([patch("a", hook("0xC00700D8", "key-dispatch"), hook("0xC00700D8", "key-dispatch"))]);
  assert.match(once.reasons[0], /doppelt/);
});

test("two hooks on one stage of a chain are refused when one replaces, and fine when none does", () => {
  const sites = ["0xC006EDE4", "0xC006EE00"];
  const replace = checkHooks([patch("a", hook(sites[0], "pattern-set", "replace", true)), patch("b", hook(sites[1], "pattern-set"))]);
  assert.equal(replace.ok, false);
  assert.match(replace.reasons[0], /Kette "pattern-set" an derselben Stelle \(select\), und a ersetzt dort/);
  assert.equal(checkHooks([patch("a", hook(sites[0], "pattern-set")), patch("b", hook(sites[1], "pattern-set"))]).ok, true);
});

test("an upstream hook that can swallow is a dependency for the hooks behind it, not a refusal", () => {
  const res = checkHooks([MFX, RUNTIME]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  const key = res.dependencies.filter(d => d.includes("0xC00700D8"));
  assert.equal(key.length, 1);
  assert.match(key[0], /^mfx-switch: Der Haken an 0xC00700D8 \(Kette "key-dispatch"\) liegt hinter dem Haken von script-runtime an 0xC002837C, der Ereignisse verschlucken kann/);
  assert.match(key[0], /Was script-runtime verschluckt, erreicht mfx-switch nicht/);
  assert.deepEqual(checkHooks([RUNTIME, MFX]).dependencies, res.dependencies, "the order of the list does not matter");
  const reverse = checkHooks([patch("late", hook("0xC002837C", "key-dispatch")), patch("early", hook("0xC00700D8", "key-dispatch", "before", true))]);
  assert.deepEqual(reverse.dependencies, [], "a swallowing hook downstream of a plain one is no dependency");
  const plain = checkHooks([patch("up", hook("0xC002837C", "key-dispatch")), patch("down", hook("0xC00700D8", "key-dispatch"))]);
  assert.deepEqual(plain.dependencies, [], "an upstream hook that cannot swallow is no dependency");
});

test("the pattern switch and patternChange at 0xC0081F50 are accepted: the wheel hook still calls set_number", () => {
  const res = checkHooks([PATTERN_SWITCH, RUNTIME]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.deepEqual(checkHooks([RUNTIME, PATTERN_SWITCH]).dependencies, res.dependencies, "the order of the list does not matter");
  assert.ok(res.dependencies.length > 0 && res.dependencies.every(d => d.startsWith("pattern-switch:") && d.includes("script-runtime") && d.includes("0xC002837C")), res.dependencies.join("\n"));
  const wheel = hook("0xC006513C", "pattern-set", "replace");
  const clash = checkHooks([patch("a", wheel), patch("b", hook("0xC006EE00", "pattern-set"))]);
  assert.equal(clash.ok, false, "two hooks on the entries of the selection, one replacing, are still refused");
});

test("the old splash editor and the runtime are refused as a pair, once", () => {
  for (const order of [[SPLASH, RUNTIME], [RUNTIME, SPLASH]]) {
    const res = checkHooks(order);
    assert.equal(res.ok, false);
    assert.equal(res.reasons.length, 1, res.reasons.join(" "));
    assert.match(res.reasons[0], /^splash-editor und script-runtime passen nicht zusammen: .*0xC002ADAC.*0xC0064D3C/);
  }
  assert.deepEqual(INCOMPATIBLE.map(p => p.patches), [["splash-editor", "script-runtime"]]);
  const sites = SPLASH.hooks.map(h => h.site);
  for (const site of ["0xC002ADAC", "0xC0064D3C"]) {
    assert.ok(sites.includes(site) && RUNTIME.hooks.some(h => h.site === site), `${site} is owned by both`);
  }
});

test("the splash editor, MFX 2 and the pattern switch go together, and what it costs is reported", () => {
  const res = checkHooks([SPLASH, MFX, PATTERN_SWITCH]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.equal(res.dependencies.length, 2, res.dependencies.join("\n"));
  assert.ok(res.dependencies.every(d => d.startsWith("pattern-switch:") && d.includes("von mfx-switch an 0xC00700D8")));
});

test("a hook the table does not know, or a malformed one, is refused with the reason", () => {
  const bad = (h, text) => assert.match(checkHooks([patch("x", h)]).reasons[0], text);
  bad(hook("0xC00700D8", "no-such-chain"), /Kette "no-such-chain" ist nicht bekannt/);
  bad(hook("0xC00700DC", "key-dispatch"), /gehört nicht zur Kette "key-dispatch"/);
  bad(hook("00700D8", "key-dispatch"), /Adresse im Abbild/);
  bad(hook("0x00700D8F", "key-dispatch"), /Adresse im Abbild/);
  bad({ ...hook("0xC00700D8", "key-dispatch"), kind: "jump" }, /kind ist einer von/);
  bad({ ...hook("0xC00700D8", "key-dispatch"), position: "middle" }, /position ist einer von/);
  bad({ ...hook("0xC00700D8", "key-dispatch"), swallow: "yes" }, /swallow ist true oder false/);
  bad({ ...hook("0xC00700D8", "key-dispatch"), chain: [] }, /chain nennt eine Kette/);
  bad(null, /keine Beschreibung/);
  assert.match(checkHooks([{ id: "x", hooks: {} }]).reasons[0], /hooks ist eine Liste/);
  assert.deepEqual(checkHooks([{ id: "data" }, null]).reasons, [], "a patch without hooks is not registered");
});

test("applyPatches refuses colliding hooks before it touches the image, and passes dependencies on", async () => {
  const vsb = await makeFirmware();
  const change = async (id, hooks) => ({
    format: PATCH_FORMAT, version: 1, id, hooks,
    changes: [{ file: FREE + (id === "a" ? 0 : 16), bytes: "e12fff1e", expect: await sha256(vsb.subarray(FREE, FREE + 4)) }],
  });
  const a = await change("a", [hook("0xC00700D8", "key-dispatch", "before", true)]);
  const clash = await applyPatches(vsb, [a, await change("b", [hook("0xC00700D8", "key-dispatch")])]);
  assert.equal(clash.ok, false);
  assert.match(clash.reasons[0], /schon von a besetzt/);
  const behind = await applyPatches(vsb, [await change("a", [hook("0xC002837C", "key-dispatch", "before", true)]), await change("b", [hook("0xC00700D8", "key-dispatch")])]);
  assert.equal(behind.ok, true, behind.reasons.join(" "));
  assert.equal(behind.dependencies.length, 1);
  const alone = await applyPatches(vsb, [a]);
  assert.deepEqual(alone.dependencies, []);
});

const vsbPath = process.env.E2_VSB;
test("the built splash editor and MFX 2 patch the own firmware together", { skip: vsbPath ? false : "E2_VSB not set" }, async () => {
  const vsb = new Uint8Array(readFileSync(vsbPath));
  const res = await applyPatches(vsb, [SPLASH, MFX]);
  assert.equal(res.ok, true, res.reasons.join(" "));
  assert.deepEqual(res.dependencies, []);
});
