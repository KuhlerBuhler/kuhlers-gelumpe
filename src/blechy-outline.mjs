/**
 * A filled Blechy sprite drawn the way the loading animation draws him: the body only as its outline. Filled, a lit
 * body on the dark display reads as a white blob. Only the inside of large filled areas goes dark: a pixel is cleared
 * when it lies inside a stretch of at least 5 x 5 lit pixels (or right beside one). Lines (legs, arms, the rings of
 * the eyes) and small spots (pupils, feet) stay exactly as drawn, and so does the face. `mask` is rows of booleans
 * (true = lit), the result has the same size. The page's pictures and his frames on the device
 * (tools/blechy-build.mjs) both go through here.
 */
export function outlined(mask) {
  const lit = (x, y) => mask[y]?.[x] ?? false;
  const all = (x, y, r) => {
    for (let dy = -r; dy <= r; dy++) for (let dx = -r; dx <= r; dx++) if (!lit(x + dx, y + dy)) return false;
    return true;
  };
  const core = mask.map((row, y) => row.map((_, x) => all(x, y, 2)));
  const nearCore = (x, y) => [-1, 0, 1].some(dy => [-1, 0, 1].some(dx => core[y + dy]?.[x + dx]));
  return mask.map((row, y) => row.map((set, x) => set && !(all(x, y, 1) && nearCore(x, y))));
}
