/**
 * Where a file for the Electribe goes: the connected device over USB, or its SD card put straight into the computer.
 * The device wins; without one the app looks for a mounted card with a KORG folder (src-tauri/src/blech_card.rs), Chrome
 * and Edge ask for the card's top folder (showDirectoryPicker). A card target writes below KORG/blechtribe/ only.
 */
import { handleCard } from "./card-access.mjs";
import { storePlugin, pluginFileName } from "../../src/usb-update.mjs";
import { ARCHIVE } from "../../data/script/contract.mjs";

/** The folder below KORG/blechtribe/ the plugin files lie in. */
export const PLUGIN_FOLDER = ARCHIVE.folder.split("/").at(-1);

/** A card the app found mounted: it names the card, the app checks folder and name and writes. */
function appCard(invoke, found) {
  return {
    name: found.volume,
    write: (folder, file, bytes) => invoke("blech_card_write", { root: found.root, folder, name: file, bytes: Array.from(bytes) }),
  };
}

async function hasKorg(dir) {
  for await (const [key, handle] of dir.entries()) {
    if (handle.kind === "directory" && key.toLowerCase() === "korg") return true;
  }
  return false;
}

/** A card the person picked in the browser; the files go below KORG/blechtribe/ of that folder. */
function pickedCard(root) {
  const card = handleCard(root);
  return {
    name: root.name,
    async write(folder, file, bytes) {
      const path = `KORG/blechtribe/${folder}/${file}`;
      await card.write(path, bytes);
      return `${root.name}/${path}`;
    },
  };
}

/**
 * Where a file goes now, as `{ kind }`: "device" with the session, "card" with the card, "cancelled" when the person
 * closed the browser's folder dialog, or "none" with the text key that says why. Call it from the click: the browser
 * opens its folder dialog only in answer to one.
 */
export async function chooseTarget({ session = null, scope = globalThis } = {}) {
  if (session) return { kind: "device", session };
  // the Android app sees no card paths
  if (scope.__GELUMPE_MOBILE) return { kind: "none", why: "target.none" };
  const invoke = scope.__TAURI__?.core?.invoke;
  if (invoke) {
    const cards = await invoke("blech_cards");
    if (cards.length === 1) return { kind: "card", card: appCard(invoke, cards[0]) };
    if (!cards.length) return { kind: "none", why: "target.none" };
    return { kind: "none", why: "target.several", cards: cards.map(c => c.volume) };
  }
  if (typeof scope.showDirectoryPicker !== "function") return { kind: "none", why: "target.noCardHere" };
  let root;
  try {
    root = await scope.showDirectoryPicker({ id: "gelumpe-card", mode: "readwrite" });
  } catch (e) {
    if (e?.name === "AbortError") return { kind: "cancelled" };
    return { kind: "none", why: "target.none" };
  }
  if (!await hasKorg(root)) return { kind: "none", why: "target.notCard", name: root.name };
  return { kind: "card", card: pickedCard(root) };
}

/** A packed .blech onto `target` (one chooseTarget gave): the name it has there, as MANAGE PLUGINS lists it. */
export async function sendPlugin(target, id, bytes) {
  if (target.kind === "device") return storePlugin(target.session, id, bytes);
  const name = pluginFileName(id);
  await target.card.write(PLUGIN_FOLDER, `${name}.blech`, bytes);
  return name;
}
