// BLECH theme icons: same sizes as the firmware's images, same 1-bit way ("#" is dark). The numbers
// are the firmware's image numbers (docs/messungen/2026-10-14-display-schriften.md). Corners are cut,
// the way sheet metal is stamped; the tags are plates with their lettering punched out.

// Battery with the three middle rows of its inside given (the bars), and the SD card.
const battery = inside => [
  ".#######..",
  "#.......#.",
  `#${inside}##`,
  `#${inside}##`,
  `#${inside}##`,
  "#.......#.",
  ".#######..",
  "..........",
];

// Lettering punched into the plates: 5 rows high, as narrow as the letters can be drawn.
const LETTERS = {
  C: ["##", "#.", "#.", "#.", "##"],
  D: ["##.", "#.#", "#.#", "#.#", "##."],
  E: ["##", "#.", "##", "#.", "##"],
  G: [".##", "#..", "#.#", "#.#", ".##"],
  I: ["#", "#", "#", "#", "#"],
  L: ["#.", "#.", "#.", "#.", "##"],
  M: ["#.#", "###", "#.#", "#.#", "#.#"],
  O: ["###", "#.#", "#.#", "#.#", "###"],
  P: ["##.", "#.#", "##.", "#..", "#.."],
  R: ["##.", "#.#", "##.", "#.#", "#.#"],
  S: ["##", "#.", "##", ".#", "##"],
  T: ["###", ".#.", ".#.", ".#.", ".#."],
  ".": [".", ".", ".", ".", "#"],
};

/** A plate of `width` columns and 7 rows with its corners cut and `text` punched out, centred. */
function plate(width, text) {
  const glyphs = [...text].map(ch => LETTERS[ch]);
  const used = glyphs.reduce((n, g) => n + g[0].length, 0) + glyphs.length - 1;
  const inner = width - 2;
  if (used > inner) throw new Error(`plate "${text}" needs ${used} columns, has ${inner}`);
  const left = 1 + ((inner - used) >> 1);
  const rows = Array.from({ length: 7 }, (_, y) => {
    const row = Array(width).fill("#");
    if (y === 0 || y === 6) { row[0] = "."; row[width - 1] = "."; }
    return row;
  });
  let x = left;
  for (const g of glyphs) {
    g.forEach((line, y) => [...line].forEach((c, dx) => { if (c === "#") rows[y + 1][x + dx] = "."; }));
    x += g[0].length + 1;
  }
  return [...rows.map(r => r.join("")), ".".repeat(width)];
}

export default {
  1: [
    ".#######..",
    "#...#...#.",
    "#..##...##",
    "#.####..##",
    "#...##..##",
    "#..##...#.",
    ".#######..",
    "..........",
  ],
  2: battery(".#.#.#."),
  3: battery(".#.#..."),
  4: battery(".#....."),
  5: [
    ".########..",
    "#........#.",
    "#........##",
    "#........##",
    "#........#.",
    "#........#.",
    ".########..",
    "...........",
  ],
  6: [".#####", "######", "#....#", "#....#", "#....#", "#....#", "######", "......"],
  7: [
    "...........",
    ".....#.....",
    "....###....",
    "...#####...",
    "..#######..",
    ".#########.",
    "....###....",
    "....###....",
    "....###....",
    "....###....",
    "....###....",
    "...........",
    "...........",
    "...........",
    "...........",
    "...........",
  ],
  8: [
    "...........",
    ".#######...",
    ".#.....##..",
    ".#.....#.#.",
    ".#.....####",
    ".#.........",
    ".#.#####.#.",
    ".#.......#.",
    ".#.#####.#.",
    ".#.......#.",
    ".#########.",
    "...........",
    "...........",
    "...........",
    "...........",
    "...........",
  ],
  9: [
    "...........",
    ".####......",
    ".#...####..",
    ".#.......#.",
    ".#.......#.",
    ".#.......#.",
    ".#.......#.",
    ".#.......#.",
    ".#########.",
    "...........",
    "...........",
    "...........",
    "...........",
    "...........",
    "...........",
    "...........",
  ],
  10: ["#...", "##..", "###.", "####", "###.", "##..", "#...", "...."],
  11: plate(14, "EDIT"),
  12: plate(13, "CLIP"),
  14: plate(5, "L"),
  15: plate(22, "M.REC"),
  16: plate(15, "ORIG"),
  17: plate(8, "ST"),
  18: plate(15, "SLICE"),
};
