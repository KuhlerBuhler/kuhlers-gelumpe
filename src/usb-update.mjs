/**
 * The firmware update over USB (tools/patch/blech_sysex.py, FILE READ and FILE BEGIN): the editor reads the update file from
 * the card of the connected Electribe, the patcher puts BLECH on it, and the result goes back as KORG/<folder>/System/SYSTEM.VSB.
 * The flash is written by Korg's own update afterwards, started on the device; nothing here writes the flash.
 *
 * A patched file cannot be patched again, so the unpatched one is kept beside it as ORIGINAL.BIN the first time; every later
 * update starts from that.
 */
import { BLECH } from "./protocol.mjs";

/** Why the connected device cannot do it, in the page's words; null when it can. */
export function unsupported(info) {
  if (!info) return "Das Gerät antwortet nicht auf BLECHs Befehle (kein BLECH drauf, oder EXIT beim Einschalten gehalten).";
  if (!(info.flags & BLECH.FLAG_FILE)) return "Das BLECH auf dem Gerät kann die Update-Datei noch nicht über USB lesen. Einmal mit der Karte aktualisieren, danach geht es über USB.";
  return null;
}

/** The device's BLECH INFO for its own model byte, and the block size set on the sender. */
async function prepare(session) {
  const model = session.device?.model;
  if (model == null) throw new Error("Erst auf der Seite Gerät verbinden.");
  const info = await session.sender.blechInfo(model);
  const why = unsupported(info);
  if (why) throw new Error(why);
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
    if (!size) throw new Error("Auf der Karte liegt im Ordner System keine SYSTEM.VSB. Leg deine Firmware-Datei dort einmal hin.");
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
