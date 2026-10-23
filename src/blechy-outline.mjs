/**
 * A filled Blechy sprite drawn the way the loading animation draws him: the body only as its outline, the face lit
 * and what is drawn on it dark. Filled, a lit body on the dark display reads as a white blob. `mask` is rows of
 * booleans (true = lit), the result has the same size. The page's pictures and his frames on the device
 * (tools/blechy-build.mjs) both go through here.
 */
/** The fewest pixels an enclosed light area needs to count as the face. */
const FACE_MIN = 60;

export function outlined(mask) {
  const R = 2;   // gaps up to this many pixels on each side close
  const P = R + 1;   // room around the sprite, so the grown ink never closes off a piece of the outside at the edge
  const h = mask.length + 2 * P;
  const w = mask[0].length + 2 * P;
  const ink = (x, y) => mask[y - P]?.[x - P] ?? false;
  const steps = Array.from({ length: 2 * R + 1 }, (_, i) => i - R);
  const near = (x, y, test) => steps.some(dy => steps.some(dx => test(x + dx, y + dy)));
  // The face is open to the outside by a pixel or two here and there: close those gaps (ink grown by R) before
  // filling the outside, then shrink the silhouette back by R.
  const outside = Array.from({ length: h }, () => new Array(w).fill(false));
  const stack = [[0, 0]];
  while (stack.length) {
    const [x, y] = stack.pop();
    if (x < 0 || y < 0 || x >= w || y >= h || outside[y][x] || near(x, y, ink)) continue;
    outside[y][x] = true;
    stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
  }
  const out = (x, y) => x < 0 || y < 0 || x >= w || y >= h || outside[y][x];
  const inside = (x, y) => !ink(x, y) && !near(x, y, out);
  // Only a large enclosed area is the face; the small corners the closing also shuts (under an arm, between the
  // feet) stay dark.
  const face = Array.from({ length: h }, () => new Array(w).fill(false));
  const seen = Array.from({ length: h }, () => new Array(w).fill(false));
  for (let y0 = 0; y0 < h; y0++) for (let x0 = 0; x0 < w; x0++) {
    if (seen[y0][x0] || !inside(x0, y0)) continue;
    const area = [];
    const todo = [[x0, y0]];
    while (todo.length) {
      const [x, y] = todo.pop();
      if (x < 0 || y < 0 || x >= w || y >= h || seen[y][x] || !inside(x, y)) continue;
      seen[y][x] = true;
      area.push([x, y]);
      todo.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
    }
    if (area.length >= FACE_MIN) for (const [x, y] of area) face[y][x] = true;
  }
  const lit = (x, y) => face[y]?.[x] ?? false;
  const edge = (x, y) => !ink(x, y) && !lit(x, y);
  return mask.map((row, y) => row.map((set, x) => {
    const [px, py] = [x + P, y + P];
    if (!set) return lit(px, py);
    return edge(px + 1, py) || edge(px - 1, py) || edge(px, py + 1) || edge(px, py - 1);
  }));
}
