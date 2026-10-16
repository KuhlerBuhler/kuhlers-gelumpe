/**
 * Which parameters each DSP unit has, and in which order.
 *
 * The order is what matters: a control map does not name a parameter, it
 * stores its position in this list. Get the list wrong and the map points at
 * a neighbouring parameter, or past the end of the list entirely.
 *
 * This module stays free of file access so the same code runs in a browser.
 * Node callers go through src/node.mjs, which reads data/units.json for them.
 */

let cache = null;

/** Turn the raw table into the shape the rest of the code expects. */
export function parseUnits(raw) {
  const table = { ifx: new Map(), mfx: new Map() };
  for (const [key, kind] of [["ifx_device", "ifx"], ["mfx_device", "mfx"]]) {
    for (const [id, entry] of Object.entries(raw[key] || {})) {
      table[kind].set(Number(id), {
        id: Number(id),
        unit: entry.unit,
        params: entry.params.map((p, index) => ({ index, name: p.name })),
      });
    }
  }
  return table;
}

/** Hand in the table once; everything else picks it up from here. */
export function setUnits(table) { cache = table; return cache; }

export function loadUnits() {
  if (!cache) throw new Error("no unit table loaded; call setUnits() or use src/node.mjs");
  return cache;
}

/** The unit behind a device byte, or null when nothing is known about it. */
export function unitFor(units, kind, device) {
  return units[kind].get(device) || null;
}

export const hex = n => "0x" + n.toString(16).padStart(2, "0");
