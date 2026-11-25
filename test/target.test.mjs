import { test } from "node:test";
import assert from "node:assert/strict";
import { chooseTarget, sendPlugin, targetLabel, findCards, PLUGIN_FOLDER } from "../site/app/target.mjs";
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
});

test("a browser and the Android app see no card", async () => {
  assert.deepEqual(await findCards({}), []);
  const android = { ...app({ blech_cards: [{ root: "/x", volume: "X" }] }), __GELUMPE_MOBILE: { platform: "android" } };
  assert.deepEqual(await findCards(android), []);
  assert.deepEqual(await chooseTarget({ scope: android }), { kind: "none", why: "target.none" });
  assert.deepEqual(android.asked, []);
  assert.deepEqual(await chooseTarget({ scope: {} }), { kind: "none", why: "target.none" });
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

test("the send button: Aufs Gerät with a device, Auf die Karte with a card, gone with neither", () => {
  const card = [{ root: "/Volumes/E2", volume: "E2" }];
  assert.equal(targetLabel({ device: { model: 0x24 } }, card), "plugins.toDevice");
  assert.equal(targetLabel(null, card), "plugins.toCard");
  assert.equal(targetLabel(null, []), null);
});

test("a card the app cannot write to gives an Error with the app's words", async () => {
  const scope = app({ blech_cards: [{ root: "/Volumes/E2", volume: "E2" }], blech_card_write: () => Promise.reject("Diese Karte ist nicht mehr da.") });
  const target = await chooseTarget({ scope });
  await assert.rejects(sendPlugin(target, "Echo", bytes), { message: "Diese Karte ist nicht mehr da." });
  const gone = app({ blech_cards: () => Promise.reject("kein Zugriff") });
  await assert.rejects(chooseTarget({ scope: gone }), { message: "kein Zugriff" });
});
