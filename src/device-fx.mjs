/**
 * The presets and modulation types the connected red Electribe has right now, read from its RAM over BLECH's READ: the
 * firmware's own, what e2sFx.all put over them at power-on, the menus as long as the card loader grew them
 * (tools/patch/fx_card.s). Only reads go out. The result is an image of the firmware file in which only those bytes are
 * filled in, so the export of e2sFx.all (src/fx-collection.mjs collectionFor) builds on it as on the user's SYSTEM.VSB,
 * without the emulator and without a firmware file (docs/messungen/2026-11-14-effekte-vom-geraet.md).
 *
 * With BLECH's FILE READ of e2sFx.all (bits 30 and 29) the file on the card comes along, so the export starts from it.
 */
import { BLECH } from "./protocol.mjs";
import { TABLES } from "./map/index.mjs";
import { fileToRam } from "./map/address.mjs";
import { HACKTRIBE_CODE, buildOf } from "./firmware.mjs";
import { readPresetsLive, recordOf, menuLength, nameAt } from "./presets.mjs";
import { modTableAt, readModType, MOD_COUNT } from "./modtable.mjs";
import { parseCollection, COLLECTION_MAGIC, HEADER_SIZE } from "./fx-collection.mjs";

const IMAGE = 0x200100;
const MOD_RECORD = TABLES.get("table.modType").stride;
/** The copy of the modulation types each build reads, the one the card loader writes to (tools/patch/script_hooks.py FX_MODS). */
const MOD_TABLE = { hacktribe: "table.modType", stock: "table.modTypeStock" };
/** What the card loader did at the last start: status and entries loaded (tools/patch/script_hooks.py CARD + fx_card.s FX_STATE_AT). */
export const FX_STATE = 0xc01f7fe0;
const STATUS = { 2: "ok", 4: "skipped", 5: "none", 7: "build" };
/** A collection is at most this large: 255 + 255 + 72 entries with text (fx_card.s); a larger file is not one. */
const FILE_MAX = 0x500000;

/**
 * @param {(addr: number, length: number) => Promise<Uint8Array>} read reads RAM
 * @param {{build?: string | null}} [opts] the build the session found by its signatures; the image must agree
 * @returns {Promise<{ok: true, build: string, image: Uint8Array, modTable: object, counts: {ifx: number, mfx: number},
 *   card: null | {status: string, loaded: number}} | {ok: false, reason: "build" | "presets" | "modTable"}>}
 */
export async function readDeviceFx(read, { build: known = null } = {}) {
  const image = new Uint8Array(IMAGE);
  // The run Hacktribe adds and Korg's build leaves erased is in RAM as in the file, so buildOf tells the build here too.
  image.set(await read(fileToRam(HACKTRIBE_CODE.file), HACKTRIBE_CODE.length), HACKTRIBE_CODE.file);
  const build = buildOf(image);
  if (!MOD_TABLE[build] || (known && known !== build)) return { ok: false, reason: "build" };
  if (!(await readPresetsLive(image, read))) return { ok: false, reason: "presets" };
  const file = TABLES.get(MOD_TABLE[build]).file;
  image.set(await read(fileToRam(file), MOD_COUNT * MOD_RECORD), file);
  const modTable = modTableAt(image, file);
  if (!modTable.ok) return { ok: false, reason: "modTable" };
  const state = new DataView((await read(FX_STATE, 8)).buffer);
  const status = STATUS[state.getUint32(0, true)] ?? (state.getUint32(0, true) >= 6 && state.getUint32(0, true) <= 10 ? "bad" : null);
  const card = status ? { status, loaded: status === "ok" ? state.getUint32(4, true) : 0 } : null;
  const counts = { ifx: menuLength(image, "ifx").value, mfx: menuLength(image, "mfx").value };
  return { ok: true, build, image, modTable, counts, card };
}

/** The names the menu shows, place (1-based) to name; empty places are left out. */
export function deviceFxNames(fx, kind) {
  const out = new Map();
  if (kind === "mod") {
    for (let i = 0; i < MOD_COUNT; i++) {
      const name = readModType(fx.image, fx.modTable.file, i).name.trim();
      if (name) out.set(i + 1, name);
    }
    return out;
  }
  for (let slot = 1; slot <= fx.counts[kind]; slot++) {
    const at = recordOf(fx.image, kind, slot);
    const name = at ? nameAt(fx.image, at.file).trim() : "";
    if (name) out.set(slot, name);
  }
  return out;
}

/**
 * e2sFx.all from the card over FILE READ with bits 30 and 29 (read only). Null when the firmware cannot: it has no Doom
 * flag (bit 29 would be taken as the sample file), answers out of range (from before the read), or the bytes are no
 * collection. `{bytes: null}` when the card has none.
 * @param {object} sender src/sender.mjs, inside the session's `exclusive`
 * @returns {Promise<null | {bytes: Uint8Array | null}>}
 */
export async function readCollectionFile(sender, model, info) {
  if (!(info.flags & BLECH.FLAG_FILE) || !(info.flags & BLECH.FLAG_DOOM)) return null;
  const size = await sender.fxFileSize(model);
  if (size === null) return null;
  if (size === 0) return { bytes: null };
  if (size < HEADER_SIZE || size > FILE_MAX) return null;
  const head = await sender.fxFileRead(0, HEADER_SIZE, model);
  if (new DataView(head.buffer, head.byteOffset).getUint32(0, true) !== COLLECTION_MAGIC) return null;
  return { bytes: await sender.fxFileRead(0, size, model) };
}

/**
 * Everything at once for the page, over the session: the RAM, and the file where the firmware can read it.
 * `file` is parseCollection's result, null when it could not be read.
 */
export async function readDeviceEffects(session) {
  const device = session.device;
  if (!device || device.ram !== "blech") return { ok: false, reason: "noBlech" };
  for (let attempt = 0; ; attempt++) {
    await session.idle();
    try {
      return await session.exclusive(async () => {
        const raw = session.ramReader();
        const max = Math.min(session.sender.blech?.maxBlock ?? 0x1000, 0x1000);
        const read = async (addr, length) => {
          const out = new Uint8Array(length);
          for (let at = 0; at < length; at += max) out.set(await raw(addr + at, Math.min(max, length - at)), at);
          return out;
        };
        const fx = await readDeviceFx(read, { build: device.build });
        if (!fx.ok) return fx;
        const got = device.blech ? await readCollectionFile(session.sender, device.model, device.blech) : null;
        // the loader takes a place up to 100 past the menu and grows it (fx_card.s FX_SLOTS)
        const file = got?.bytes ? parseCollection(got.bytes, { counts: { ifx: Math.max(fx.counts.ifx, 100), mfx: Math.max(fx.counts.mfx, 100) } }) : null;
        return { ...fx, file: got ? { present: !!got.bytes, read: file } : null };
      });
    } catch (e) {
      if (e.kind !== "busy" || attempt >= 8) throw e;
    }
  }
}
