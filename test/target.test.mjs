import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, readdirSync, existsSync, writeFileSync, rmSync } from "node:fs";
import { mkdir, readdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chooseTarget, sendPlugin, targetLabel, PLUGIN_FOLDER } from "../site/app/target.mjs";
import { ARCHIVE } from "../data/script/contract.mjs";

const bytes = Uint8Array.of(0x42, 0x4c, 0x45, 0x43);

function app(answers) {
  const asked = [];
  const invoke = async (command, args) => {
    asked.push([command, args]);
    const a = answers[command];
    return typeof a === "function" ? a(args) : a;
  };
  return { asked, __TAURI__: { core: { invoke } } };
}

/** A real folder on disk behind the browser's directory handle API, as far as handleCard uses it. */
function dirHandle(path) {
  return {
    kind: "directory",
    name: path.split("/").at(-1),
    async *entries() {
      for (const e of await readdir(path, { withFileTypes: true })) yield [e.name, e.isDirectory() ? dirHandle(join(path, e.name)) : { kind: "file", name: e.name }];
    },
    async getDirectoryHandle(name, { create = false } = {}) {
      if (create) await mkdir(join(path, name), { recursive: true });
      return dirHandle(join(path, name));
    },
    async getFileHandle(name) {
      const file = join(path, name);
      return { kind: "file", name, createWritable: async () => { const parts = []; return { write: async b => parts.push(Buffer.from(b)), close: async () => writeFile(file, Buffer.concat(parts)) }; } };
    },
  };
}

const card = () => mkdtempSync(join(tmpdir(), "gelumpe-target-"));

test("the plugin folder on a card is the one the device reads", () => {
  assert.equal(`KORG/blechtribe/${PLUGIN_FOLDER}`, ARCHIVE.folder);
});

test("target: a connected device wins, the app is not asked for a card", async () => {
  const session = { device: { model: 0x24 } };
  const scope = app({ blech_cards: [{ root: "/Volumes/E2", volume: "E2" }] });
  assert.deepEqual(await chooseTarget({ session, scope }), { kind: "device", session });
  assert.deepEqual(scope.asked, []);
});

test("target in the app: one card found is the target, none or several say why", async () => {
  const one = await chooseTarget({ scope: app({ blech_cards: [{ root: "/Volumes/E2", volume: "E2" }] }) });
  assert.equal(one.kind, "card");
  assert.equal(one.card.name, "E2");
  assert.deepEqual(await chooseTarget({ scope: app({ blech_cards: [] }) }), { kind: "none", why: "target.none" });
  assert.deepEqual(await chooseTarget({ scope: app({ blech_cards: [{ root: "/a", volume: "A" }, { root: "/b", volume: "B" }] }) }),
    { kind: "none", why: "target.several", cards: ["A", "B"] });
  const android = { ...app({ blech_cards: [{ root: "/x", volume: "X" }] }), __GELUMPE_MOBILE: { platform: "android" } };
  assert.deepEqual(await chooseTarget({ scope: android }), { kind: "none", why: "target.none" });
  assert.deepEqual(android.asked, [], "the Android app has no card paths");
});

test("target in a browser without a folder dialog: nothing, and it says where it works", async () => {
  assert.deepEqual(await chooseTarget({ scope: {} }), { kind: "none", why: "target.noCardHere" });
});

test("a plugin onto the card the app found: the app gets the card, the folder and the file name", async () => {
  const scope = app({ blech_cards: [{ root: "/Volumes/E2", volume: "E2" }], blech_card_write: "/Volumes/E2/KORG/blechtribe/Plugin/Echo-1.blech" });
  const target = await chooseTarget({ scope });
  assert.equal(await sendPlugin(target, "Echo 1", bytes), "Echo-1");
  assert.deepEqual(scope.asked.at(-1), ["blech_card_write", { root: "/Volumes/E2", folder: "Plugin", name: "Echo-1.blech", bytes: [...bytes] }]);
});

test("a plugin onto the device goes over USB as before", async () => {
  const written = [];
  const session = {
    device: { model: 0x24 },
    exclusive: fn => fn(),
    sender: {
      blech: { maxBlock: 256 },
      blechInfo: async () => ({ flags: 0xffffffff, maxBlock: 256 }),
      pluginWrite: async (b, name) => written.push([name, b]),
    },
  };
  assert.equal(await sendPlugin({ kind: "device", session }, "Echo", bytes), "Echo");
  assert.deepEqual(written, [["Echo", bytes]]);
});

test("a plugin onto a card picked in the browser lands in KORG/blechtribe/Plugin, the folders made on the way", async t => {
  const root = card();
  t.after(() => rmSync(root, { recursive: true, force: true }));
  mkdirSync(join(root, "KORG", "hacktribe"), { recursive: true });
  const target = await chooseTarget({ scope: { showDirectoryPicker: async () => dirHandle(root) } });
  assert.equal(target.kind, "card");
  assert.equal(await sendPlugin(target, "Echo", bytes), "Echo");
  assert.deepEqual([...readFileSync(join(root, "KORG", "blechtribe", "Plugin", "Echo.blech"))], [...bytes]);
});

test("a picked card keeps its own letters for KORG and the plugin folder, and a plugin of the same name is replaced", async t => {
  const root = card();
  t.after(() => rmSync(root, { recursive: true, force: true }));
  mkdirSync(join(root, "korg", "BLECHTRIBE", "plugin"), { recursive: true });
  writeFileSync(join(root, "korg", "BLECHTRIBE", "plugin", "Echo.blech"), "old");
  const target = await chooseTarget({ scope: { showDirectoryPicker: async () => dirHandle(root) } });
  await sendPlugin(target, "Echo", bytes);
  assert.deepEqual([...readFileSync(join(root, "korg", "BLECHTRIBE", "plugin", "Echo.blech"))], [...bytes]);
  assert.deepEqual(readdirSync(root), ["korg"], "no second KORG folder");
  assert.deepEqual(readdirSync(join(root, "korg", "BLECHTRIBE")), ["plugin"], "no second plugin folder");
});

test("a picked folder without KORG is not the card, a closed dialog is no error", async t => {
  const root = card();
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const none = await chooseTarget({ scope: { showDirectoryPicker: async () => dirHandle(root) } });
  assert.deepEqual(none, { kind: "none", why: "target.notCard", name: root.split("/").at(-1) });
  assert.equal(existsSync(join(root, "KORG")), false, "nothing written");
  const abort = Object.assign(new Error("closed"), { name: "AbortError" });
  assert.deepEqual(await chooseTarget({ scope: { showDirectoryPicker: async () => { throw abort; } } }), { kind: "cancelled" });
  const refused = Object.assign(new Error("no click"), { name: "SecurityError" });
  assert.deepEqual(await chooseTarget({ scope: { showDirectoryPicker: async () => { throw refused; } } }), { kind: "none", why: "target.none" });
});

test("the send button says Aufs Gerät with a device, Auf die Karte without; the Android app has no card", () => {
  assert.equal(targetLabel({ device: { model: 0x24 } }, {}), "plugins.toDevice");
  assert.equal(targetLabel(null, {}), "plugins.toCard");
  assert.equal(targetLabel(null, { __GELUMPE_MOBILE: { platform: "android" } }), "plugins.toDevice");
});
