/**
 * Where a file for the Electribe goes: the connected device over USB, or its SD card put straight into the computer.
 * The device wins; without one the desktop app looks for a mounted card with a KORG folder (src-tauri/src/blech_card.rs)
 * and writes below KORG/blechtribe/ only. A browser sees no card, so there only the device is a target.
 */
import { storePlugin, pluginFileName } from "../../src/usb-update.mjs";
import { ARCHIVE } from "../../data/script/contract.mjs";

/** The folder below KORG/blechtribe/ the plugin files lie in. */
export const PLUGIN_FOLDER = ARCHIVE.folder.split("/").at(-1);

/** The mounted cards with a KORG folder, as `{ root, volume }`; none outside the desktop app (the Android app sees no card paths). */
export async function findCards(scope = globalThis) {
  const invoke = scope.__TAURI__?.core?.invoke;
  if (!invoke || scope.__GELUMPE_MOBILE) return [];
  return invoke("blech_cards");
}

/**
 * The text key for the button that sends a file, or null when there is no target and only Herunterladen stays:
 * "Aufs Gerät" with a device connected, "Auf die Karte" with a card in the computer (`cards` from findCards).
 */
export function targetLabel(session, cards = []) {
  if (session) return "plugins.toDevice";
  return cards.length ? "plugins.toCard" : null;
}

/** A card the app found mounted: it names the card, the app checks folder and name and writes. */
function appCard(invoke, found) {
  return {
    name: found.volume,
    write: (folder, file, bytes) => invoke("blech_card_write", { root: found.root, folder, name: file, bytes: Array.from(bytes) }),
  };
}

/**
 * Where a file goes now, as `{ kind }`: "device" with the session, "card" with the card, or "none" with the text key
 * that says why (no card, or several).
 */
export async function chooseTarget({ session = null, scope = globalThis } = {}) {
  if (session) return { kind: "device", session };
  const cards = await findCards(scope);
  if (cards.length === 1) return { kind: "card", card: appCard(scope.__TAURI__.core.invoke, cards[0]) };
  if (!cards.length) return { kind: "none", why: "target.none" };
  return { kind: "none", why: "target.several", cards: cards.map(c => c.volume) };
}

/** A packed .blech onto `target` (one chooseTarget gave): the name it has there, as MANAGE PLUGINS lists it. */
export async function sendPlugin(target, id, bytes) {
  if (target.kind === "device") return storePlugin(target.session, id, bytes);
  const name = pluginFileName(id);
  await target.card.write(PLUGIN_FOLDER, `${name}.blech`, bytes);
  return name;
}
