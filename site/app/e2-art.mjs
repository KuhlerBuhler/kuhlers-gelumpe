/**
 * A small Electribe 2 drawn from above (SVG), laid out like the emulator's front (site/app/panel.mjs): the places
 * of its controls were read off that front at a width of 200. Drawn as lines, for the device cards of the patcher,
 * the Features page and the Rettung page.
 */
const NS = "http://www.w3.org/2000/svg";
const W = 200;
const H = 112;

const SCREEN = [9.5, 21, 41, 24.5];
const TOUCHPAD = [10, 72, 39, 31];
/** Knobs and encoders: centre x, centre y, radius. The power switch is the first. */
const KNOBS = [
  [13.5, 13.5, 4.3], [29.5, 13.5, 4.5], [43.5, 13.5, 4.6],
  [67, 27.5, 6], [87.5, 27.5, 5.6], [112.5, 27.5, 5.6], [138, 27.5, 5.8], [154.5, 27.5, 4.7], [170.5, 27.5, 4.7], [186.5, 27.5, 6],
  [87.5, 42, 4.7], [104.5, 42, 4.7], [121, 42, 4.7], [138, 42, 4.7], [154.5, 42, 4.7], [170.5, 42, 4.7], [186.5, 42, 4.7],
  [87.5, 54.5, 4.7], [138, 54.5, 4.7],
];
/** Buttons: x, y, width, height. Play, stop and the rest of the transport first. */
const BUTTONS = [
  [10, 50.5, 9, 9.5], [20, 50.5, 9, 9.5], [30, 50.5, 9.5, 9.5], [40.5, 50.5, 9, 9.5],
  [10, 62, 8.5, 5], [19, 62, 11, 5], [30.5, 62, 9.5, 5], [40.5, 62, 9, 5],
  // the six keys right of the display, from panel.mjs (x 380 and 432, y 263, 300 and 339): x' = 9.5 + (x - 135) * 200 / 1021
  [57.5, 38.2, 9.4, 4.7], [67.7, 38.2, 9.4, 4.7], [57.5, 45.5, 9.4, 4.7], [67.7, 45.5, 9.4, 4.7], [57.5, 53.1, 9.4, 4.9], [67.7, 53.1, 9.4, 4.9],
  [98.5, 52, 9.5, 5.5], [108.5, 52, 9.5, 5.5], [118.5, 52, 9.5, 5.5], [150, 52, 9.5, 5.5], [165.5, 52, 9.5, 5.5], [181, 52, 10, 5.5],
  ...Array.from({ length: 10 }, (_, i) => [57.5 + i * 10.1, 62, 9.5, 5]),
  ...Array.from({ length: 4 }, (_, i) => [166 + i * 6.5, 62, 5, 7.5]),
];
/** The 16 pads, two rows of eight with a wider gap after the fourth. */
const PADS = Array.from({ length: 16 }, (_, i) => [57 + (i % 8) * 16.9 + (i % 8 > 3 ? 2 : 0), i < 8 ? 71.5 : 88.5, 15, 14.5]);

const rect = ([x, y, w, h], rx, cls = "") => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}"${cls && ` class="${cls}"`}/>`;
const circle = ([cx, cy, r], cls = "") => `<circle cx="${cx}" cy="${cy}" r="${r}"${cls && ` class="${cls}"`}/>`;

function svg(cls, label, inner) {
  const node = document.createElementNS(NS, "svg");
  node.setAttribute("viewBox", `0 0 ${W} ${H}`);
  node.setAttribute("class", cls);
  node.setAttribute("role", "img");
  node.setAttribute("aria-label", label);
  node.innerHTML = inner;
  return node;
}

/** The Electribe as lines only, in the colour of the element (`currentColor`). */
export function e2Outline(label) {
  return svg("cee-e2-outline", label, `<g fill="none" stroke="currentColor" stroke-width="1.2">`
    + `<rect x="1" y="1" width="${W - 2}" height="${H - 2}" rx="4" stroke-width="2"/>`
    + rect(SCREEN, 1.5) + rect(TOUCHPAD, 2)
    + KNOBS.map(k => circle(k)).join("")
    + BUTTONS.map(b => rect(b, 1)).join("")
    + PADS.map(p => rect(p, 1.5)).join("")
    + `</g>`);
}

/** The six keys right of the display by their place in BUTTONS, in pairs as on the panel (panel.mjs). */
const KEYS = { editLeft: 8, editRight: 9, menu: 10, exit: 11, shift: 12, write: 13 };

/** Where a key of the six is drawn: x, y, width, height in the drawing. */
export const keyRect = id => BUTTONS[KEYS[id]];

/**
 * The Electribe as lines, `press` filled (the key to press) and `near` dashed (keys used on the way), for the Rettung page.
 * Each mark stays inside its own key: the gap to the next key is less than a unit, so a larger mark would cover it too.
 */
export function e2Keys(label, { press = [], near = [] } = {}) {
  const node = e2Outline(label);
  node.classList.add("cee-e2-keys");
  const mark = (cls, inset) => id => {
    const [x, y, w, h] = keyRect(id).map((v, i) => +(v + (i < 2 ? inset : -2 * inset)).toFixed(2));
    return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="1" class="${cls}" data-key="${id}"/>`;
  };
  node.insertAdjacentHTML("beforeend", near.map(mark("cee-e2-near", 0.4)).join("") + press.map(mark("cee-e2-press", 0)).join(""));
  return node;
}
