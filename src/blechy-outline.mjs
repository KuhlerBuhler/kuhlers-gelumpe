/**
 * A filled Blechy sprite drawn the way the loading animation draws him: the body only as its outline. Filled, a lit
 * body on the dark display reads as a white blob. Only the inside of the body goes dark: a pixel is cleared when it
 * lies inside the largest stretch of 5 x 5 lit pixels (or right beside it). Lines (legs, arms, the rings of
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
  const deep = mask.map((row, y) => row.map((_, x) => all(x, y, 2)));
  // Only the largest such stretch is his body; smaller ones (the tuft of hair, a hand) stay filled.
  const seen = deep.map(row => row.map(() => false));
  let body = [];
  deep.forEach((row, y0) => row.forEach((on, x0) => {
    if (!on || seen[y0][x0]) return;
    const area = [];
    const todo = [[x0, y0]];
    while (todo.length) {
      const [x, y] = todo.pop();
      if (!deep[y]?.[x] || seen[y][x]) continue;
      seen[y][x] = true;
      area.push([x, y]);
      todo.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
    }
    if (area.length > body.length) body = area;
  }));
  const core = mask.map(row => row.map(() => false));
  for (const [x, y] of body) core[y][x] = true;
  const nearCore = (x, y) => [-1, 0, 1].some(dy => [-1, 0, 1].some(dx => core[y + dy]?.[x + dx]));
  return mask.map((row, y) => row.map((set, x) => set && !(all(x, y, 1) && nearCore(x, y))));
}
