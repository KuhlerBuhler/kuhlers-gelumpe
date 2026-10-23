/**
 * A filled Blechy sprite drawn the way the loading animation draws him: the body only as its outline. Filled, a lit
 * body on the dark display reads as a white blob. A lit pixel with lit pixels all round goes dark, so every filled
 * area keeps only its edge. Lines (legs, arms, the rings of the eyes) and small spots (pupils, feet) stay exactly
 * as drawn, and so does the face. `mask` is rows of booleans
 * (true = lit), the result has the same size. The page's pictures and his frames on the device
 * (tools/blechy-build.mjs) both go through here.
 */
/** A filled stretch whose inside has fewer pixels than this is a spot (a pupil) and stays filled. */
const SPOT = 4;

export function outlined(mask) {
  const lit = (x, y) => mask[y]?.[x] ?? false;
  const filled = (x, y) => [-1, 0, 1].every(dy => [-1, 0, 1].every(dx => lit(x + dx, y + dy)));
  // The inside of every filled stretch goes dark, the body and the tuft of hair alike; a stretch whose inside is
  // only a few pixels (a pupil) stays as it is.
  const seen = mask.map(row => row.map(() => false));
  const clear = mask.map(row => row.map(() => false));
  mask.forEach((row, y0) => row.forEach((_, x0) => {
    if (seen[y0][x0] || !filled(x0, y0)) return;
    const area = [];
    const todo = [[x0, y0]];
    while (todo.length) {
      const [x, y] = todo.pop();
      if (seen[y]?.[x] !== false || !filled(x, y)) continue;
      seen[y][x] = true;
      area.push([x, y]);
      todo.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
    }
    if (area.length >= SPOT) for (const [x, y] of area) clear[y][x] = true;
  }));
  return mask.map((row, y) => row.map((set, x) => set && !clear[y][x]));
}
