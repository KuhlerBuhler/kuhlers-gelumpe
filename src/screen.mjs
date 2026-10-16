/**
 * What the device shows right now, read from its RAM through the screen
 * manager (data/map/screen.mjs, measure:2026-10-09/menuezustand).
 */
import { BLOCKS, field, readRaw, offsetOf } from "./map/index.mjs";
import { pointerBlock, RAM_BASE, CURRENT_PATTERN } from "./map/address.mjs";
import { readU32le } from "./bytes.mjs";

const MANAGER = BLOCKS.get("screenManager");
const SCREEN = BLOCKS.get("screen");
const EDIT = BLOCKS.get("editState");

/**
 * @param {(addr: number, length: number) => Promise<Uint8Array>} readRam
 * @returns {Promise<{mode: number, name: object|null, page: number|null, pageName: string|null, overlay: object|null}>}
 */
export async function readScreen(readRam) {
  const at = await pointerBlock("screenManager", async a => readU32le(await readRam(a, 4)));
  const manager = await readRam(at, MANAGER.size);
  const mode = readRaw(manager, field("screen.mode"));
  const current = readRaw(manager, field("screen.current"));
  const known = MANAGER.meta.modes[mode] ?? null;
  let page = null;
  if (known?.pages && current >= RAM_BASE) {
    const screen = await readRam(current, SCREEN.size);
    const p = readRaw(screen, field("screen.page"));
    if (p < known.pages.length) page = p;
  }
  const kind = readRaw(manager, field("screen.overlayKind"));
  const overlay = readRaw(manager, field("screen.overlay")) ? { kind, name: MANAGER.meta.overlays[kind] ?? null } : null;
  return {
    mode,
    name: known ? { de: known.de, en: known.en } : null,
    page,
    pageName: page === null ? null : known.pages[page],
    overlay,
  };
}

/**
 * The screen plus the selected part and, where the screen shows an effect,
 * its slot as the display numbers it (menu place + 1).
 */
export async function readContext(readRam) {
  const screen = await readScreen(readRam);
  const u32 = async a => readU32le(await readRam(a, 4));
  const part = readRaw(await readRam(await pointerBlock("editState", u32), EDIT.size), field("edit.part"));
  const shown = MANAGER.meta.effects.find(e => e.overlay !== undefined ? screen.overlay?.kind === e.overlay : screen.mode === e.mode && screen.page === e.page);
  let fx = null;
  if (shown && part < 16) {
    const f = field(shown.field);
    const at = (await u32(CURRENT_PATTERN.at)) + CURRENT_PATTERN.header + offsetOf(f, f.repeat ? [part] : []);
    fx = { kind: shown.kind, slot: (await readRam(at, 1))[0] + 1 };
  }
  return { ...screen, part, fx };
}
