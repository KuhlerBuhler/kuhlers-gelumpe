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
];

const POSES = [["idle", "Ruhig"], ["happy", "Froh"], ["wave", "Winkt"], ["angry", "Sauer"], ["sad", "Traurig"]];
const MOTIFS = [["blechtribe", "BLECHTRIBE", "img/splash/blechtribe.png"], ["blech", "BLECH", "img/splash/blech.png"], ["blechy", "Blechy", "img/blechy/wave.png"]];
const FORMATS = [["desktop", "Rechner", 2560, 1440], ["phone", "Handy", 1170, 2532]];
const AVATAR = 1024;
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

function colours(look) {
  const [, , bg, ink] = LOOKS.find(l => l[0] === look);
  const style = getComputedStyle(document.documentElement);
  return { bg: style.getPropertyValue(bg).trim(), ink: style.getPropertyValue(ink).trim() };
}

/** The largest whole pixel size at which `mask` fits into `w` x `h`. */
const fit = (mask, w, h) => Math.max(1, Math.floor(Math.min(w / mask[0].length, h / mask.length)));

/** Blechy in a pose, the name below him, on a square. */
function drawAvatar(canvas, { figure, name, look }) {
  const ctx = canvas.getContext("2d");
  const { bg, ink } = colours(look);
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, AVATAR, AVATAR);
  ctx.fillStyle = ink;
  const label = name.trim() ? textMask(name.trim()) : null;
  const scale = fit(figure, AVATAR * 0.62, AVATAR * (label ? 0.58 : 0.7));
  const textScale = label ? fit(label, AVATAR * 0.8, AVATAR * 0.09) : 0;
  const gap = label ? Math.round(AVATAR * 0.06) : 0;
  const total = figure.length * scale + gap + (label ? label.length * textScale : 0);
  const top = Math.round((AVATAR - total) / 2);
  plot(ctx, figure, Math.round((AVATAR - figure[0].length * scale) / 2), top, scale);
  if (label) plot(ctx, label, Math.round((AVATAR - label[0].length * textScale) / 2), top + figure.length * scale + gap, textScale);
}

/** A motif in the middle of a wallpaper: wide on a computer, narrower and a bit higher on a phone. */
function drawWallpaper(canvas, { motif, look, format }) {
  const [, , w, h] = FORMATS.find(f => f[0] === format);
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  const { bg, ink } = colours(look);
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = ink;
  const scale = fit(motif, w * (format === "phone" ? 0.8 : 0.5), h * 0.4);
  plot(ctx, motif, Math.round((w - motif[0].length * scale) / 2), Math.round((h * (format === "phone" ? 0.45 : 0.5)) - (motif.length * scale) / 2), scale);
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

const fileName = text => text.trim().replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "") || "Blechy";

function avatarMaker(root) {
  const state = { pose: "wave", look: "red", name: "" };
  const masks = {};
  const canvas = el("canvas", { className: "cee-support-preview", id: "cee-support-avatar-canvas", width: AVATAR, height: AVATAR });
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", "Vorschau des Profilbilds");
  const name = el("input", { className: "input", id: "cee-support-name", type: "text", maxLength: NAME_MAX, spellcheck: false, autocomplete: "off", placeholder: "zum Beispiel dein Künstlername" });
  const render = async () => {
    masks[state.pose] ??= await maskOf(`img/blechy/${state.pose}.png`);
    drawAvatar(canvas, { figure: masks[state.pose], name: state.name, look: state.look });
  };
  name.addEventListener("input", () => { state.name = name.value; render(); });
  const save = el("button", { type: "button", className: "btn cee-primary", id: "cee-support-avatar-save", textContent: "Profilbild speichern" });
  save.addEventListener("click", () => download(canvas, `Blechy-${fileName(state.name)}.png`));
  root.replaceChildren(
    el("h3", { textContent: "Profilbild" }),
    el("div", { className: "cee-support-maker" }, [
      canvas,
      el("div", { className: "cee-support-controls" }, [
        el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: "cee-support-name", textContent: `Dein Name (bis ${NAME_MAX} Zeichen)` }), name]),
        choices("cee-support-pose", "Blechy", POSES, state.pose, v => { state.pose = v; render(); }),
        choices("cee-support-avatar-look", "Farbe", LOOKS, state.look, v => { state.look = v; render(); }),
        el("div", { className: "actions" }, [save]),
      ]),
    ]),
  );
  render();
}

function wallpaperMaker(root) {
  const state = { motif: "blechtribe", look: "black", format: "desktop" };
  const masks = {};
  const canvas = el("canvas", { className: "cee-support-preview", id: "cee-support-wallpaper-canvas" });
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", "Vorschau des Hintergrunds");
  const render = async () => {
    masks[state.motif] ??= await maskOf(MOTIFS.find(m => m[0] === state.motif)[2]);
    drawWallpaper(canvas, { motif: masks[state.motif], look: state.look, format: state.format });
    canvas.dataset.format = state.format;
  };
  const save = el("button", { type: "button", className: "btn cee-primary", id: "cee-support-wallpaper-save", textContent: "Hintergrund speichern" });
  save.addEventListener("click", () => {
    const [, motifName] = MOTIFS.find(m => m[0] === state.motif);
    download(canvas, `${fileName(motifName)}-${state.format === "phone" ? "Handy" : "Rechner"}.png`);
  });
  root.replaceChildren(
    el("h3", { textContent: "Hintergrund" }),
    el("div", { className: "cee-support-maker" }, [
      canvas,
      el("div", { className: "cee-support-controls" }, [
        choices("cee-support-motif", "Motiv", MOTIFS, state.motif, v => { state.motif = v; render(); }),
        choices("cee-support-format", "Für", FORMATS, state.format, v => { state.format = v; render(); }),
        choices("cee-support-wallpaper-look", "Farbe", LOOKS, state.look, v => { state.look = v; render(); }),
        el("div", { className: "actions" }, [save]),
      ]),
    ]),
  );
  render();
}

export function supportPage({ avatar, wallpaper }) {
  avatarMaker(avatar);
  wallpaperMaker(wallpaper);
}
