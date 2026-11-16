import { test } from "node:test";
import assert from "node:assert/strict";
import { saveWay, saveAs, findCards, saveToCard, sameCards } from "../site/app/save-target.mjs";

const bytes = Uint8Array.of(1, 2, 3);

function app(answers) {
  const asked = [];
  return { asked, __TAURI__: { core: { invoke: async (command, args) => { asked.push([command, args]); return answers[command]; } } } };
}

function picker({ abort = false, refuse = false } = {}) {
  const written = [];
  return {
    written,
    async showSaveFilePicker(options) {
      written.push(["options", options]);
      if (abort) throw Object.assign(new Error("cancelled"), { name: "AbortError" });
      if (refuse) throw Object.assign(new Error("not here"), { name: "SecurityError" });
      return { createWritable: async () => ({ write: async b => written.push(["write", b]), close: async () => written.push(["close"]) }) };
    },
  };
}

test("save way: the app first, then the browser's save dialog, else the download", () => {
  assert.equal(saveWay(app({})), "app");
  assert.equal(saveWay({ ...picker(), ...app({}) }), "app", "the app's webview may have the picker too, the app wins");
  assert.equal(saveWay(picker()), "picker");
  assert.equal(saveWay({}), "download");
  assert.equal(saveWay({ __TAURI__: {} }), "download", "no invoke, no app");
});

test("save in the app: the dialog of the app writes and names the full path, a cancel saves nothing", async () => {
  const scope = app({ save_pick: "/Users/me/Desktop/SYSTEM.VSB" });
  const download = () => assert.fail("no download in the app");
  assert.deepEqual(await saveAs(bytes, "SYSTEM.VSB", { scope, download }), { saved: true, way: "app", where: "/Users/me/Desktop/SYSTEM.VSB" });
  assert.deepEqual(scope.asked, [["save_pick", { name: "SYSTEM.VSB", bytes: [1, 2, 3] }]]);
  assert.deepEqual(await saveAs(bytes, "SYSTEM.VSB", { scope: app({ save_pick: null }), download }), { saved: false, way: "app", where: null });
});

test("save in the browser: the save dialog with the name, a cancel saves nothing, a refused dialog downloads", async () => {
  const scope = picker();
  const download = () => assert.fail("no download when the dialog works");
  assert.deepEqual(await saveAs(bytes, "SYSTEM.VSB", { scope, download }), { saved: true, way: "picker", where: null });
  assert.deepEqual(scope.written, [["options", { suggestedName: "SYSTEM.VSB" }], ["write", bytes], ["close"]]);
  assert.deepEqual(await saveAs(bytes, "SYSTEM.VSB", { scope: picker({ abort: true }), download }), { saved: false, way: "picker", where: null });
  const got = [];
  assert.deepEqual(await saveAs(bytes, "SYSTEM.VSB", { scope: picker({ refuse: true }), download: (b, n) => got.push([b, n]) }), { saved: true, way: "download", where: null });
  assert.deepEqual(got, [[bytes, "SYSTEM.VSB"]]);
});

test("save without a dialog: the download as before", async () => {
  const got = [];
  assert.deepEqual(await saveAs(bytes, "SYSTEM.VSB", { scope: {}, download: (b, n) => got.push([b, n]) }), { saved: true, way: "download", where: null });
  assert.deepEqual(got, [[bytes, "SYSTEM.VSB"]]);
});

test("cards: only the app looks, and a save names the card and the goal's folder", async () => {
  assert.deepEqual(await findCards("KORG/blechtribe/System/", {}), [], "the browser finds no card");
  const card = { root: "/Volumes/E2", volume: "E2", path: "/Volumes/E2/KORG/blechtribe/System/SYSTEM.VSB", systemExists: true, vsbExists: false };
  const scope = app({ save_cards: [card], save_card: card.path });
  assert.deepEqual(await findCards("KORG/blechtribe/System/", scope), [card]);
  assert.equal(await saveToCard(card, "KORG/blechtribe/System/", bytes, scope), card.path);
  assert.deepEqual(scope.asked, [
    ["save_cards", { target: "KORG/blechtribe/System/" }],
    ["save_card", { root: "/Volumes/E2", target: "KORG/blechtribe/System/", bytes: [1, 2, 3] }],
  ]);
  assert.equal(sameCards([card], [{ ...card }]), true);
  assert.equal(sameCards([card], [{ ...card, vsbExists: true }]), false, "a file put there later counts as a change");
  assert.equal(sameCards([], [card]), false);
});

test("the Android app saves through its own dialog and finds no cards", async () => {
  const android = { ...app({ save_cards: [{ root: "/x" }] }), __GELUMPE_MOBILE: { platform: "android" } };
  assert.equal(saveWay(android), "download");
  assert.deepEqual(await findCards("KORG/blechtribe/System/", android), []);
  const got = [];
  const out = await saveAs(bytes, "SYSTEM.VSB", { scope: android, download: (b, n) => got.push(n) });
  assert.deepEqual(got, ["SYSTEM.VSB"]);
  assert.equal(out.way, "download");
  assert.deepEqual(android.asked, []);
});
