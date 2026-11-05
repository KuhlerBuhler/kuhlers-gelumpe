import test from "node:test";
import assert from "node:assert/strict";
import { NAME, headOf, isVsb, skipDir, identify, problemsOf, planCard, applyPlan } from "../src/card-check.mjs";
import { VSB_SIZE, withHead } from "../src/patcher.mjs";

/** A file of the right size with "E2" and the head of one Electribe; no firmware bytes beyond that. */
function vsb(head) {
  const bytes = new Uint8Array(VSB_SIZE);
  bytes[0x10] = 0x45;
  bytes[0x11] = 0x32;
  return withHead(bytes, head === "synth" ? "blue" : "sampler");
}

const RED = { path: "KORG/electribe sampler/System/SYSTEM.VSB", heads: ["sampler"] };
const BLUE = { path: "KORG/electribe/System/SYSTEM.VSB", heads: ["synth"] };
const BLECH = { path: "KORG/blechtribe/System/SYSTEM.VSB", heads: ["sampler", "synth"] };

/** A card in memory: paths in any letters name the same file, like FAT. */
function fakeCard(files, { copies = false } = {}) {
  const map = new Map(Object.entries(files).map(([path, bytes]) => [path, { bytes, modified: 0 }]));
  const key = path => [...map.keys()].find(k => k.toLowerCase() === path.toLowerCase());
  return {
    map,
    list: async () => [...map].map(([path, f]) => ({ path, size: f.bytes.length, modified: f.modified })),
    read: async path => map.get(key(path)).bytes,
    exists: async path => key(path) !== undefined,
    async move(from, to, { replace = false } = {}) {
      const source = map.get(key(from));
      if (!source) throw new Error(from);
      if (key(to) !== undefined && !replace) throw new Error(`${to} taken`);
      if (!copies) map.delete(key(from));
      map.set(key(to) ?? to, { ...source });
      return copies ? "copied" : "moved";
    },
  };
}

async function look(card, target) {
  const files = await Promise.all((await card.list()).map(e => identify(e, card.read)));
  return planCard(files, target);
}

test("the head tells the Sampler from the blue Electribe", () => {
  assert.equal(headOf(vsb("sampler")), "sampler");
  assert.equal(headOf(vsb("synth")), "synth");
  assert.equal(headOf(new Uint8Array(VSB_SIZE)), null);
  assert.equal(headOf(new Uint8Array(4)), null);
});

test("only .VSB files count, no Mac shadows and no system folders", () => {
  assert.ok(isVsb("SYSTEM.VSB") && isVsb("system (1).vsb") && isVsb("SYSTEM.VSB.VSB"));
  assert.ok(!isVsb("._SYSTEM.VSB") && !isVsb("SYSTEM.VSB.old") && !isVsb("SYSTEM.BIN"));
  assert.ok(skipDir(".Trashes") && skipDir("System Volume Information") && !skipDir("KORG"));
});

test("problems: name, case, folder, size, unknown, the other Electribe", () => {
  const ok = { path: RED.path, size: VSB_SIZE, head: "sampler" };
  assert.deepEqual(problemsOf(ok, RED), []);
  assert.deepEqual(problemsOf({ ...ok, path: "KORG/electribe sampler/System/SYSTEM (1).VSB" }, RED), ["name"]);
  assert.deepEqual(problemsOf({ ...ok, path: "KORG/electribe sampler/System/SYSTEM.VSB.VSB" }, RED), ["name"]);
  assert.deepEqual(problemsOf({ ...ok, path: "korg/Electribe Sampler/system/System.vsb" }, RED), ["case"]);
  assert.deepEqual(problemsOf({ ...ok, path: "SYSTEM.VSB" }, RED), ["folder"]);
  assert.deepEqual(problemsOf({ ...ok, size: 12 }, RED), ["size"]);
  assert.deepEqual(problemsOf({ ...ok, head: null }, RED), ["unknown"]);
  assert.deepEqual(problemsOf({ ...ok, head: "synth" }, RED), ["other"]);
  assert.deepEqual(problemsOf({ ...ok, path: BLECH.path, head: "synth" }, BLECH), []);
});

test("the verdict: empty, ok, wrong, fix", async () => {
  assert.equal((await look(fakeCard({}), RED)).verdict, "empty");
  assert.equal((await look(fakeCard({ [RED.path]: vsb("sampler") }), RED)).verdict, "ok");
  const other = await look(fakeCard({ [RED.path]: vsb("synth"), "SYSTEM.VSB": new Uint8Array(10) }), RED);
  assert.equal(other.verdict, "wrong");
  assert.deepEqual(other.files.map(f => f.problems), [["other"], ["size", "folder"]]);
  const blue = await look(fakeCard({ "KORG/electribe/System/SYSTEM (1).VSB": vsb("synth") }), BLUE);
  assert.equal(blue.verdict, "fix");
  assert.deepEqual(blue.steps, [{ op: "move", from: "KORG/electribe/System/SYSTEM (1).VSB", to: BLUE.path }]);
});

test("a wrong name in the right folder is moved to SYSTEM.VSB", async () => {
  const card = fakeCard({ "KORG/electribe sampler/System/SYSTEM (1).VSB": vsb("sampler") });
  const plan = await look(card, RED);
  const done = await applyPlan(card, plan.steps);
  assert.deepEqual(done.map(s => [s.op, s.how]), [["move", "moved"]]);
  assert.deepEqual([...card.map.keys()], [RED.path]);
});

test("the right file in the wrong folder goes over, the file in the way goes aside", async () => {
  const card = fakeCard({ "SYSTEM.VSB": vsb("sampler"), [RED.path]: vsb("synth"), [`${RED.path}.old`]: vsb("synth") });
  const plan = await look(card, RED);
  assert.deepEqual(plan.steps.map(s => s.op), ["aside", "move"]);
  const done = await applyPlan(card, plan.steps);
  assert.equal(done[0].to, `${RED.path}.old2`);
  assert.equal(headOf(card.map.get(RED.path).bytes), "sampler");
  assert.equal(headOf(card.map.get(`${RED.path}.old2`).bytes), "synth");
  assert.equal(card.map.size, 3, "nothing is deleted");
});

test("the file in the right folder wins over others, then the newest", async () => {
  const card = fakeCard({ "a/SYSTEM.VSB": vsb("sampler"), "KORG/electribe sampler/System/SYSTEM.VSB.VSB": vsb("sampler") });
  assert.equal((await look(card, RED)).file.path, "KORG/electribe sampler/System/SYSTEM.VSB.VSB");
  const loose = fakeCard({ "a/SYSTEM.VSB": vsb("sampler"), "b/SYSTEM.VSB": vsb("sampler") });
  loose.map.get("b/SYSTEM.VSB").modified = 5;
  assert.equal((await look(loose, RED)).file.path, "b/SYSTEM.VSB");
});

test("a name in other letters is renamed through a free name", async () => {
  const card = fakeCard({ "KORG/electribe sampler/System/system.vsb": vsb("sampler") });
  const plan = await look(card, RED);
  assert.deepEqual(plan.steps, [{ op: "rename", from: "KORG/electribe sampler/System/system.vsb", to: RED.path }]);
  await applyPlan(card, plan.steps);
  assert.deepEqual([...card.map.keys()], [RED.path]);
  assert.ok(RED.path.endsWith(NAME));
});

test("where the card can only copy, the original stays and the aside is kept", async () => {
  const card = fakeCard({ "SYSTEM.VSB": vsb("sampler"), [RED.path]: vsb("synth") }, { copies: true });
  const done = await applyPlan(card, (await look(card, RED)).steps);
  assert.deepEqual(done.map(s => s.how), ["copied", "copied"]);
  assert.equal(headOf(card.map.get(RED.path).bytes), "sampler");
  assert.equal(headOf(card.map.get(`${RED.path}.old`).bytes), "synth");
  assert.ok(card.map.has("SYSTEM.VSB"));
});
