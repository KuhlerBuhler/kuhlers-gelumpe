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
  idle: ["Ruhig", "img/blechy/idle.png"],
  happy: ["Froh", "img/blechy/happy.png"],
  wave: ["Winkt", "img/blechy/wave.png"],
  angry: ["Sauer", "img/blechy/angry.png"],
  sad: ["Traurig", "img/blechy/sad.png"],
  tube: ["Röhrchen", "img/blechy/tube.png"],
  loaded: ["Geladen", "img/blechy/loaded.png"],
  eyes: ["Augen", EYES],
  blechtribe: ["BLECHTRIBE", "img/splash/blechtribe.png"],
  blech: ["BLECH", "img/splash/blech.png"],
  none: ["Nichts", []],
};

const BACKS = [["stars", "Sterne"], ["flat", "Fläche"]];
const PLACES = [["top", "Oben"], ["middle", "Mitte"], ["bottom", "Unten"]];
const FORMATS = { avatar: ["Profilbild", 1024, 1024], desktop: ["Rechner", 2560, 1440], phone: ["Handy", 1170, 2532] };
const TEXT_MAX = 24;
const NAME_MAX = 14;

/** A 1-bit picture as rows of booleans, cut to the pixels that are set. The more common colour is the background: the art is drawn both ways round, some with a frame. */
async function maskOf(src) {
  const picture = new Image();
  picture.src = src;
  await picture.decode();
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

const masks = {};
const figureMask = async id => (masks[id] ??= typeof FIGURES[id][1] === "string" ? await maskOf(FIGURES[id][1]) : FIGURES[id][1]);

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
 * at three depths. Same rules and strengths as site/design/bg.js, so the picture looks like the app behind it.
 */
function starField(ctx, w, h, ink) {
  const cell = Math.max(4, Math.round(Math.min(w, h) / 160));
  const cols = Math.ceil(w / cell);
  const rows = Math.ceil(h / cell);
  const width = Math.min(44, Math.max(14, Math.round(cols * 0.09)));
  ctx.fillStyle = ink;
  ctx.globalAlpha = 0.14;
  for (let j = 0; j < rows; j += 2) for (let i = 0; i < cols; i += 2) {
    const edge = Math.min(i, cols - 1 - i);
    const density = edge >= width ? 0 : (1 - edge / width) ** 1.4 * 0.9;
    if (density > BAYER[((j >> 1) & 3) * 4 + ((i >> 1) & 3)]) ctx.fillRect(i * cell, j * cell, cell, cell);
  }
  const rand = rng(23);
  for (let n = Math.min(240, Math.floor((cols * rows) / 650)); n > 0; n--) {
    const z = rand();
    const layer = z < 0.45 ? 0 : z < 0.85 ? 1 : 2;
    const x = Math.floor(rand() * cols);
    const y = Math.floor(rand() * rows);
    const plus = layer === 2 && rand() < 0.12;
    const star = (dx, dy, dim) => { ctx.globalAlpha = dim ? 0.28 : 0.55; ctx.fillRect((x + dx) * cell, (y + dy) * cell, cell, cell); };
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
 * One picture: the background, then the figure and the text below it as one block, its height at the chosen place.
 * `size` is how much of the room the figure may take; whole pixels only, so a smaller size may jump a step.
 */
function draw(canvas, state, figure) {
  const [, w, h] = FORMATS[state.format];
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  const { bg, ink } = colours(state);
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);
  if (state.back === "stars") starField(ctx, w, h, ink);
  ctx.fillStyle = ink;
  const label = state.text.trim() ? textMask(state.text.trim()) : null;
  const room = state.format === "phone" ? [0.85, 0.4] : state.format === "desktop" ? [0.8, 0.6] : [0.7, label ? 0.58 : 0.7];
  const scale = figure.length ? Math.max(1, Math.floor(fit(figure, w * room[0], h * room[1]) * state.size / 100)) : 0;
  const textScale = label ? Math.max(1, Math.min(fit(label, w * 0.8, h * 0.09), scale || Infinity)) : 0;
  const gap = label && scale ? Math.round(Math.min(w, h) * 0.05) : 0;
  const block = figure.length * scale + gap + (label ? label.length * textScale : 0);
  const centre = { top: 0.27, middle: 0.5, bottom: 0.73 }[state.place] * h;
  const top = Math.round(Math.min(Math.max(centre - block / 2, 0), h - block));
  if (scale) plot(ctx, figure, Math.round((w - figure[0].length * scale) / 2), top, scale);
  if (label) plot(ctx, label, Math.round((w - label[0].length * textScale) / 2), top + figure.length * scale + gap, textScale);
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
  const text = el("input", { className: "input", id: `${id}-text`, type: "text", maxLength: textMax, spellcheck: false, autocomplete: "off", placeholder });
  text.addEventListener("input", () => { state.text = text.value; render(); });
  const colour = (key, label) => {
    const input = el("input", { type: "color", className: "cee-support-colour", id: `${id}-${key}`, value: state[key] });
    input.addEventListener("input", () => { state[key] = input.value; render(); });
    return el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: input.id, textContent: label }), input]);
  };
  const own = el("div", { className: "cee-support-own", id: `${id}-own`, hidden: state.look !== "own" }, [colour("bg", "Hintergrund"), colour("ink", "Pixel")]);
  const size = el("input", { type: "range", className: "ui-range", id: `${id}-size`, min: 20, max: 100, step: 5, value: state.size });
  const sizeOut = el("output", { className: "ui-range-value", htmlFor: size.id, textContent: `${state.size} %` });
  size.addEventListener("input", () => { state.size = Number(size.value); sizeOut.textContent = `${size.value} %`; render(); });
  const save = el("button", { type: "button", className: "btn cee-primary", id: `${id}-save`, textContent: saveText });
  save.addEventListener("click", () => download(canvas, `${name(state)}.png`));
  const set = key => value => { state[key] = value; render(); };
  root.replaceChildren(
    el("h3", { textContent: title }),
    el("div", { className: "cee-support-maker" }, [
      canvas,
      el("div", { className: "cee-support-controls" }, [
        formats.length > 1 ? choices(`${id}-format`, "Für", formats.map(f => [f, FORMATS[f][0]]), state.format, set("format")) : null,
        choices(`${id}-figure`, "Bild", figures.map(f => [f, FIGURES[f][0]]), state.figure, set("figure")),
        el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: text.id, textContent: `${textLabel} (bis ${textMax} Zeichen)` }), text]),
        el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: size.id }, ["Größe ", sizeOut]), size]),
        choices(`${id}-place`, "Platz", PLACES, state.place, set("place")),
        choices(`${id}-back`, "Hintergrund", BACKS, state.back, set("back")),
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
    id: "cee-support-avatar", title: "Profilbild", formats: ["avatar"], figures: blechys,
    state: { format: "avatar", figure: "wave", text: "", size: 100, place: "middle", back: "flat", look: "red", bg: "#cc0000", ink: "#0a0a0b" },
    textLabel: "Dein Name", textMax: NAME_MAX, placeholder: "zum Beispiel dein Künstlername", saveText: "Profilbild speichern",
    name: s => `Blechy${s.text.trim() ? `-${fileName(s.text)}` : ""}`,
  });
  maker(wallpaper, {
    id: "cee-support-wallpaper", title: "Hintergrund", formats: ["desktop", "phone"], figures: ["blechtribe", "blech", ...blechys, "none"],
    state: { format: "desktop", figure: "blechtribe", text: "", size: 100, place: "middle", back: "stars", look: "black", bg: "#0a0a0b", ink: "#fafafa" },
    textLabel: "Text darunter", textMax: TEXT_MAX, placeholder: "zum Beispiel MEINE ELECTRIBE ROCKT", saveText: "Hintergrund speichern",
    name: s => `${fileName(FIGURES[s.figure][0]) || "BLECHTRIBE"}-${FORMATS[s.format][0]}`,
  });
}
