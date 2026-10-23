/**
 * The Unterstützen page: donate, report a bug, bring a plugin into the catalog, and pictures to show BLECHTRIBE
 * around. The pictures are drawn here from the 1-bit art of the display (site/img), each pixel a square, so a profile
 * picture with a name and wallpapers for a computer or a phone come out sharp at any size. Nothing leaves the browser.
 */
import { el } from "./fields.mjs";
import { saveFile } from "./save-file.mjs";
import { FONT, FONT_FIRST, FONT_LAST, GLYPH_WIDTH, GLYPH_HEIGHT, ADVANCE } from "../../data/script/font.mjs";

/** Background and pixel colour of each look, as tokens: the red sampler, the blue synth, black, and the display. */
const LOOKS = [
  ["red", "Rot", "--color-card-suit-red", "--color-bg-page"],
  ["blue", "Blau", "--color-chart-blue", "--color-bg-page"],
  ["black", "Schwarz", "--color-bg-page", "--color-surface-card-face"],
  ["display", "Display", "--color-surface-card-face", "--color-bg-page"],
  ["own", "Eigene"],
];

// Blechy's eyes as the page background draws them (site/design/bg.js), with the pupils looking straight ahead.
const EYES = [
  "............####.....",
  "...###.........###...",
  ".##...##.....##...##.",
  ".#.....#.....#.....#.",
  "#..###..#...#..###..#",
  "#..###..#...#..###..#",
  "#..###..#...#..###..#",
  ".#.....#.....#.....#.",
  ".##...##.....##...##.",
  "...###.........###...",
  ".#.....#.....#.....#.",
  "..#...#.......#...#..",
  ".#.###.#.....#.###.#.",
].map(row => [...row].map(c => c === "#"));

/** What can stand in the picture: a file of site/img, or a mask drawn here. */
const FIGURES = {
  idle: ["Ruhig", "img/blechy/idle.png", "stroke"],
  happy: ["Froh", "img/blechy/happy.png", "stroke"],
  wave: ["Winkt", "img/blechy/wave.png", "stroke"],
  angry: ["Sauer", "img/blechy/angry.png", "stroke"],
  sad: ["Traurig", "img/blechy/sad.png", "stroke"],
  tube: ["Röhrchen", "img/blechy/tube.png"],
  loaded: ["Geladen", "img/blechy/loaded.png"],
  eyes: ["Augen", EYES],
  blechtribe: ["BLECHTRIBE", "img/splash/blechtribe.png"],
  blech: ["BLECH", "img/splash/blech.png"],
  none: ["Nichts", []],
};

const PLACES = [
  ["top-left", "Oben links"], ["top", "Oben"], ["top-right", "Oben rechts"],
  ["left", "Links"], ["middle", "Mitte"], ["right", "Rechts"],
  ["bottom-left", "Unten links"], ["bottom", "Unten"], ["bottom-right", "Unten rechts"],
];
const FORMATS = { avatar: ["Profilbild", 1024, 1024], desktop: ["Rechner", 2560, 1440], phone: ["Handy", 1170, 2532] };
const TEXT_MAX = 120;
const NAME_MAX = 40;

/** A 1-bit picture as rows of booleans, cut to the pixels that are set. The more common colour is the background: the art is drawn both ways round, some with a frame. */
async function maskOf(src) {
  // onload, not decode(): decode() was seen to stay pending for a picture that had loaded long ago.
  const picture = await new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = src;
  });
  const { width: w, height: h } = picture;
  const work = el("canvas", { width: w, height: h });
  const ctx = work.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(picture, 0, 0);
  const d = ctx.getImageData(0, 0, w, h).data;
  let light = 0;
  for (let i = 0; i < d.length; i += 4) if (d[i] > 127) light++;
  const back = light * 2 > w * h;
  const on = (x, y) => (d[(y * w + x) * 4] > 127) !== back;
  let [x0, y0, x1, y1] = [w, h, -1, -1];
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (on(x, y)) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  return Array.from({ length: y1 - y0 + 1 }, (_, y) => Array.from({ length: x1 - x0 + 1 }, (_, x) => on(x0 + x, y0 + y)));
}

/**
 * A filled sprite drawn the way the display draws Blechy in the loading animation: the body only as its outline, the
 * face light and what is drawn on it dark. Filled, a light body on a dark ground reads as a white blob.
 */
function stroked(mask) {
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

const masks = {};
const figureMask = async id => {
  const [, source, style] = FIGURES[id];
  if (!masks[id]) {
    const mask = typeof source === "string" ? await maskOf(source) : source;
    masks[id] = style === "stroke" ? stroked(mask) : mask;
  }
  return masks[id];
};

/** A line of text in the 5 x 7 font of the display, as a mask like maskOf. */
function textMask(text) {
  const chars = [...text].map(c => c.charCodeAt(0)).map(c => (c >= FONT_FIRST && c <= FONT_LAST ? c : 0x3f));
  const width = Math.max(chars.length * ADVANCE - 1, 0);
  return Array.from({ length: GLYPH_HEIGHT }, (_, y) => Array.from({ length: width }, (_, x) => {
    const col = x % ADVANCE;
    return col < GLYPH_WIDTH && Boolean((FONT[chars[Math.floor(x / ADVANCE)] - FONT_FIRST][col] >> y) & 1);
  }));
}

function plot(ctx, mask, left, top, scale) {
  mask.forEach((row, y) => row.forEach((set, x) => { if (set) ctx.fillRect(left + x * scale, top + y * scale, scale, scale); }));
}

/** The largest whole pixel size at which `mask` fits into `w` x `h`. */
const fit = (mask, w, h) => (mask.length ? Math.max(1, Math.floor(Math.min(w / mask[0].length, h / mask.length))) : 0);

function rng(seed) {
  let s = seed >>> 0;
  return () => (s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296;
}

const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map(v => (v + 0.5) / 16);

/**
 * The page background, standing still: a grid of cells, dither bands thickening towards both side edges and stars
 * at three depths, each of the two on its own. The rules of site/design/bg.js, but coarser and stronger: behind a
 * page they only hint, on a picture of its own they have to show.
 */
function starField(ctx, w, h, ink, { bands, stars }) {
  const cell = Math.max(4, Math.round(Math.min(w, h) / 96));
  const cols = Math.ceil(w / cell);
  const rows = Math.ceil(h / cell);
  const width = Math.min(44, Math.max(14, Math.round(cols * 0.09)));
  ctx.fillStyle = ink;
  ctx.globalAlpha = 0.4;
  if (bands) for (let j = 0; j < rows; j += 2) for (let i = 0; i < cols; i += 2) {
    const edge = Math.min(i, cols - 1 - i);
    const density = edge >= width ? 0 : (1 - edge / width) ** 1.4 * 0.9;
    if (density > BAYER[((j >> 1) & 3) * 4 + ((i >> 1) & 3)]) ctx.fillRect(i * cell, j * cell, cell, cell);
  }
  const rand = rng(23);
  if (stars) for (let n = Math.min(240, Math.floor((cols * rows) / 250)); n > 0; n--) {
    const z = rand();
    const layer = z < 0.45 ? 0 : z < 0.85 ? 1 : 2;
    const x = Math.floor(rand() * cols);
    const y = Math.floor(rand() * rows);
    const plus = layer === 2 && rand() < 0.12;
    const star = (dx, dy, dim) => { ctx.globalAlpha = dim ? 0.6 : 1; ctx.fillRect((x + dx) * cell, (y + dy) * cell, cell, cell); };
    star(0, 0, layer === 0);
    if (layer === 2) star(1, 0, false);
    if (plus) { star(0, -1, false); star(1, 1, false); star(0, 2, true); star(-1, 0, true); star(2, 0, true); }
  }
  ctx.globalAlpha = 1;
}

/** The colours of a choice: the tokens of a look, or the two the person picked. */
function colours(state) {
  if (state.look === "own") return { bg: state.bg, ink: state.ink };
  const [, , bg, ink] = LOOKS.find(l => l[0] === state.look);
  const style = getComputedStyle(document.documentElement);
  return { bg: style.getPropertyValue(bg).trim(), ink: style.getPropertyValue(ink).trim() };
}

/**
 * One picture: the background, then the figure and the lines of text below it as one block at the chosen place,
 * a margin away from the edges. Figure and text each have their own size, a share of the most that fits; whole
 * pixels only, so a smaller size may jump a step.
 */
function draw(canvas, state, figure) {
  const [, w, h] = FORMATS[state.format];
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  const { bg, ink } = colours(state);
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);
  if (state.bands || state.stars) starField(ctx, w, h, ink, state);
  ctx.fillStyle = ink;
  const lines = state.text.split("\n").map(line => line.trim()).filter(Boolean).map(textMask);
  const widest = lines.reduce((a, b) => (b[0].length > a[0].length ? b : a), lines[0] ?? []);
  const room = state.format === "phone" ? [0.85, 0.45] : state.format === "desktop" ? [0.8, 0.65] : [0.75, 0.75];
  const scale = figure.length ? Math.max(1, Math.floor(fit(figure, w * room[0], h * room[1]) * state.size / 100)) : 0;
  const textScale = lines.length ? Math.max(1, Math.floor(fit(widest, w * 0.9, h * 0.12) * state.textSize / 100)) : 0;
  const lineGap = textScale * 3;
  const gap = lines.length && scale ? Math.round(Math.min(w, h) * 0.04) : 0;
  const items = [...(scale ? [[figure, scale, 0]] : []), ...lines.map((line, i) => [line, textScale, i ? lineGap : gap])];
  const blockW = Math.max(0, ...items.map(([mask, s]) => mask[0].length * s));
  const blockH = items.reduce((sum, [mask, s, before]) => sum + before + mask.length * s, 0);
  const margin = Math.round(Math.min(w, h) * 0.06);
  const [v, side] = state.place.includes("-") ? state.place.split("-") : ["top", "bottom"].includes(state.place) ? [state.place, "centre"] : state.place === "middle" ? ["middle", "centre"] : ["middle", state.place];
  const left = Math.max(0, side === "left" ? margin : side === "right" ? w - margin - blockW : Math.round((w - blockW) / 2));
  let y = Math.max(0, v === "top" ? margin : v === "bottom" ? h - margin - blockH : Math.round((h - blockH) / 2));
  for (const [mask, s, before] of items) {
    y += before;
    const width = mask[0].length * s;
    plot(ctx, mask, side === "left" ? left : side === "right" ? left + blockW - width : left + Math.round((blockW - width) / 2), y, s);
    y += mask.length * s;
  }
}

/** A row of choices as a segmented control; `onPick` gets the value. */
function choices(id, label, items, value, onPick) {
  const group = el("div", { className: "ui-segmented", id }, items.map(([v, text]) => {
    const input = el("input", { type: "radio", name: id, value: v, checked: v === value });
    input.addEventListener("change", () => onPick(v));
    return el("label", { className: "ui-segmented-option" }, [input, el("span", { textContent: text })]);
  }));
  group.setAttribute("role", "radiogroup");
  group.setAttribute("aria-label", label);
  return el("div", { className: "ui-field" }, [el("span", { className: "ui-field-label", textContent: label }), group]);
}

function download(canvas, name) {
  canvas.toBlob(async blob => saveFile(new Uint8Array(await blob.arrayBuffer()), name, { type: "image/png" }), "image/png");
}

const fileName = text => text.trim().replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "");

/**
 * A picture maker: the preview, then its choices. `formats` are the sizes it offers, `figures` what can stand in it;
 * the profile picture has a name under Blechy, the wallpapers a free line of text.
 */
function maker(root, { id, title, formats, figures, state, textLabel, textMax, placeholder, saveText, name }) {
  const canvas = el("canvas", { className: "cee-support-preview", id: `${id}-canvas` });
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", `Vorschau: ${title}`);
  const render = async () => {
    const figure = await figureMask(state.figure);
    draw(canvas, state, figure);
    canvas.dataset.format = state.format;
  };
  const text = el("textarea", { className: "input", id: `${id}-text`, rows: 2, maxLength: textMax, spellcheck: false, autocomplete: "off", placeholder });
  text.addEventListener("input", () => { state.text = text.value; render(); });
  const colour = (key, label) => {
    const input = el("input", { type: "color", className: "cee-support-colour", id: `${id}-${key}`, value: state[key] });
    input.addEventListener("input", () => { state[key] = input.value; render(); });
    return el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: input.id, textContent: label }), input]);
  };
  const own = el("div", { className: "cee-support-own", id: `${id}-own`, hidden: state.look !== "own" }, [colour("bg", "Hintergrund"), colour("ink", "Pixel")]);
  const slider = (key, label) => {
    const input = el("input", { type: "range", className: "ui-range", id: `${id}-${key}`, min: 10, max: 100, step: 5, value: state[key] });
    const out = el("output", { className: "ui-range-value", htmlFor: input.id, textContent: `${state[key]} %` });
    out.dataset.unit = " %";
    input.addEventListener("input", () => { state[key] = Number(input.value); out.textContent = `${input.value} %`; render(); });
    window.ui?.syncRange(input); // ui.js only fills sliders present at load and on input; this one starts off at its value
    return el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: input.id }, [`${label} `, out]), input]);
  };
  const save = el("button", { type: "button", className: "btn cee-primary", id: `${id}-save`, textContent: saveText });
  save.addEventListener("click", () => download(canvas, `${name(state)}.png`));
  const set = key => value => { state[key] = value; render(); };
  const toggle = (key, label) => {
    const input = el("input", { type: "checkbox", role: "switch", id: `${id}-${key}`, checked: state[key] });
    input.addEventListener("change", () => set(key)(input.checked));
    return el("label", { className: "ui-switch" }, [input, el("span", { className: "ui-switch-track", ariaHidden: "true" }), label]);
  };
  root.replaceChildren(
    el("h3", { textContent: title }),
    el("div", { className: "cee-support-maker" }, [
      canvas,
      el("div", { className: "cee-support-controls" }, [
        formats.length > 1 ? choices(`${id}-format`, "Für", formats.map(f => [f, FORMATS[f][0]]), state.format, set("format")) : null,
        choices(`${id}-figure`, "Bild", figures.map(f => [f, FIGURES[f][0]]), state.figure, set("figure")),
        el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: text.id, textContent: `${textLabel} (bis ${textMax} Zeichen, Enter für eine neue Zeile)` }), text]),
        slider("size", "Bildgröße"),
        slider("textSize", "Textgröße"),
        choices(`${id}-place`, "Platz", PLACES, state.place, set("place")),
        el("div", { className: "ui-field" }, [el("span", { className: "ui-field-label", textContent: "Hintergrund" }), toggle("bands", "Punktmuster an den Rändern"), toggle("stars", "Sterne")]),
        choices(`${id}-look`, "Farbe", LOOKS, state.look, value => { own.hidden = value !== "own"; set("look")(value); }),
        own,
        el("div", { className: "actions" }, [save]),
      ]),
    ]),
  );
  render();
}

export function supportPage({ avatar, wallpaper }) {
  const blechys = ["wave", "idle", "happy", "angry", "sad", "tube", "loaded", "eyes"];
  maker(avatar, {
    // The tube scene is wide and flat, a square leaves it a strip in the middle: only for the wallpapers.
    id: "cee-support-avatar", title: "Profilbild", formats: ["avatar"], figures: blechys.filter(f => f !== "tube"),
    state: { format: "avatar", figure: "wave", text: "", size: 100, textSize: 60, place: "middle", bands: false, stars: false, look: "red", bg: "#cc0000", ink: "#0a0a0b" },
    textLabel: "Dein Name", textMax: NAME_MAX, placeholder: "zum Beispiel dein Künstlername", saveText: "Profilbild speichern",
    name: s => `Blechy${s.text.trim() ? `-${fileName(s.text)}` : ""}`,
  });
  maker(wallpaper, {
    id: "cee-support-wallpaper", title: "Hintergrund", formats: ["desktop", "phone"], figures: ["blechtribe", "blech", ...blechys, "none"],
    state: { format: "desktop", figure: "blechtribe", text: "", size: 100, textSize: 40, place: "middle", bands: true, stars: true, look: "black", bg: "#0a0a0b", ink: "#fafafa" },
    textLabel: "Text", textMax: TEXT_MAX, placeholder: "zum Beispiel MEINE ELECTRIBE ROCKT", saveText: "Hintergrund speichern",
    name: s => `${fileName(FIGURES[s.figure][0]) || "BLECHTRIBE"}-${FORMATS[s.format][0]}`,
  });
}
