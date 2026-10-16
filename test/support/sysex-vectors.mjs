import PROTECTED from "../../data/protected.mjs";
import { allowedRegions } from "../../src/plan.mjs";
import { refusal, RAM_WINDOW } from "../../src/protect.mjs";
import { BLECH } from "../../src/protocol.mjs";

/**
 * Ranges to ask a device about, and what the rule of src/protect.mjs says about each: the edges of every protected RAM region,
 * the declared windows the editor writes, and some places at random. `status` is BLECH's: 0 ok, 2 refused, 3 out of range.
 */
export function sysexVectors(build = "hacktribe") {
  const declared = allowedRegions({ build });
  let seed = 20261015;
  const next = n => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed % n; };
  const spots = [];
  for (const r of PROTECTED.regions.filter(x => x.space === "ram")) {
    for (const at of [r.start - 1, r.start, r.start + 3, r.end - 4, r.end - 1, r.end]) if (at >= 0xc0000000) spots.push(at);
  }
  for (const d of declared.filter((_, i) => i % 97 === 0)) spots.push(d.start, d.start - 1, d.end - 1);
  for (let i = 0; i < 40; i++) spots.push(0xc0000000 + next(0x8000000));
  const out = [];
  for (const addr of spots) {
    for (const length of [1, 4, 16, 2000]) {
      for (const op of ["read", "write"]) {
        const refused = refusal({ space: "ram", op, addr, length }, { declared });
        const outside = addr < RAM_WINDOW.start || addr + length > RAM_WINDOW.end;
        out.push({ op, addr, length, status: outside ? BLECH.STATUS.RANGE : refused ? BLECH.STATUS.REFUSED : BLECH.STATUS.OK });
      }
    }
  }
  return out;
}
