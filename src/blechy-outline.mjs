/**
 * A filled Blechy sprite drawn the way the loading animation draws him: the body only as its outline, the face lit
 * and what is drawn on it dark. Filled, a lit body on the dark display reads as a white blob. `mask` is rows of
 * booleans (true = lit), the result has the same size.
 */
export function outlined(mask) {
  const P = 2;   // room around the sprite, so the grown ink never closes off a piece of the outside at the edge
  const h = mask.length + 2 * P;
  const w = mask[0].length + 2 * P;
  const ink = (x, y) => mask[y - P]?.[x - P] ?? false;
  const near = (x, y, test) => [-1, 0, 1].some(dy => [-1, 0, 1].some(dx => test(x + dx, y + dy)));
  // The face is open to the outside by a pixel here and there: close those gaps (ink grown by one) before filling
  // the outside, then shrink the silhouette back by one.
  const outside = Array.from({ length: h }, () => new Array(w).fill(false));
  const stack = [[0, 0]];
  while (stack.length) {
    const [x, y] = stack.pop();
    if (x < 0 || y < 0 || x >= w || y >= h || outside[y][x] || near(x, y, ink)) continue;
    outside[y][x] = true;
    stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
  }
  const out = (x, y) => x < 0 || y < 0 || x >= w || y >= h || outside[y][x];
  const inside = (x, y) => !near(x, y, out);
  const edge = (x, y) => !inside(x, y) && !ink(x, y);
  return mask.map((row, y) => row.map((set, x) => {
    const [px, py] = [x + P, y + P];
    if (!set) return inside(px, py);
    return edge(px + 1, py) || edge(px - 1, py) || edge(px, py + 1) || edge(px, py - 1);
  }));
}
