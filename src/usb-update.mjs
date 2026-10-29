/**
 * The firmware update over USB (tools/patch/blech_sysex.py, FILE READ and FILE BEGIN): the editor reads the update file from
 * the card of the connected Electribe, the patcher puts BLECH on it, and the result goes back as KORG/<folder>/System/SYSTEM.VSB.
 * The flash is written by Korg's own update afterwards, started on the device; nothing here writes the flash.
 *
 * A patched file cannot be patched again, so the unpatched one is kept beside it as ORIGINAL.BIN the first time; every later
 * update starts from that. Without one, the patcher page rebuilds it from Korg's file (restoreOriginal in src/patcher.mjs).
 */
import { BLECH } from "./protocol.mjs";
import { text, TextError } from "./text.mjs";

/** Why the connected device cannot do it, as a text (src/text.mjs); null when it can. */
export function unsupported(info) {
  if (!info) return text("usbupdate.noBlech");
  if (!(info.flags & BLECH.FLAG_FILE)) return text("usbupdate.tooOld");
  return null;
}

/** The device's BLECH INFO for its own model byte, and the block size set on the sender. */
export async function prepare(session) {
  const model = session.device?.model;
  if (model == null) throw new TextError("usbupdate.notConnected");
  const info = await session.sender.blechInfo(model);
  const why = unsupported(info);
  if (why) throw new TextError(why.key);
  if (!session.sender.blech) session.sender.blech = { maxBlock: info.maxBlock };
  return model;
}

/**
 * The file the update starts from: ORIGINAL.BIN when the card has one, else SYSTEM.VSB.
 * @returns {Promise<{bytes: Uint8Array, fromOriginal: boolean}>}
 */
export function fetchUpdateFile(session, onProgress) {
  return session.exclusive(async () => {
    const model = await prepare(session);
    const kept = await session.sender.fileSize(model, true);
    if (kept) return { bytes: await session.sender.fileRead(kept, model, onProgress, true), fromOriginal: true };
    const size = await session.sender.fileSize(model);
    if (!size) throw new TextError("usbupdate.noVsb");
    return { bytes: await session.sender.fileRead(size, model, onProgress), fromOriginal: false };
  });
}

/** The patched file as SYSTEM.VSB; with `original` (the first time) the unpatched one goes beside it as ORIGINAL.BIN first. */
export function storeUpdateFile(session, patched, original, onProgress) {
  return session.exclusive(async () => {
    const model = await prepare(session);
    const total = patched.length + (original?.length ?? 0);
    if (original) await session.sender.fileWrite(original, model, done => onProgress?.(done, total), true);
    const base = original?.length ?? 0;
    await session.sender.fileWrite(patched, model, done => onProgress?.(base + done, total));
  });
}

/** The name a plugin file gets on the card: its own id when that is a valid name, else the id with every other character as "-", cut to 16. */
export function pluginFileName(id) {
  const name = String(id ?? "").replace(/[^A-Za-z0-9_-]/g, "-").slice(0, BLECH.NAME_MAX);
  return name || "plugin";
}

/** A .blech onto the card of the connected device, as KORG/blechtribe/Plugin/<name>.blech; MANAGE PLUGINS in the BLECH menu lists it. */
export function storePlugin(session, id, bytes, onProgress) {
  return session.exclusive(async () => {
    const model = await prepare(session);
    const info = await session.sender.blechInfo(model);
    if (!(info.flags & BLECH.FLAG_PLUGIN)) throw new TextError("usbupdate.pluginsTooOld");
    const name = pluginFileName(id);
    try {
      await session.sender.pluginWrite(bytes, name, model, onProgress);
    } catch (e) {
      // the firmware does not make the folder itself (docs/plugins.md); a card error at the first block is most likely that
      if (e.status === BLECH.STATUS.FILE) throw new TextError("usbupdate.noPluginFolder");
      throw e;
    }
    return name;
  });
}
