/**
 * The loading animation on the Design page: 100 slots, slot n for n percent, filled from a GIF, several pictures or one
 * picture per slot, edited pixel by pixel, to a BLLA file the Patcher writes. Logic: src/loading-anim.mjs.
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { t, tNodes } from "./i18n.mjs";
import { icon } from "./icons.mjs";
import { pixelsOf, paint, switchOf } from "./splash.mjs";
import { drawDisplay } from "./emulator.mjs";
import { number } from "../../src/text.mjs";
import { decodeGif } from "../../src/gif.mjs";
import {
  encodeAnimation, decodeAnimation, validateAnimation, costPerFrame, progressIndex, loopPicture, pixelsToFrame, frameToPixels,
  slotSource, slotsToAnimation, animationToSlots, SLOTS, MAX_BYTES, HEADER_BYTES, SPLASH_W, SPLASH_H,
} from "../../src/loading-anim.mjs";

const KEY = "cee.loading.anim";
const LOOP_MS = 96;     // the firmware's loop picture time (tools/patch/load_bar.py)
const FRAME_MS = 50;    // load_bar.FRAME_MS: at most one new picture every 50 ms, so one slot per 50 ms
const HOLD_MS = 2000;   // the preview stands this long at 100 % before it starts again, the loop playing
const LOOP_FROM = 95;   // the loop's start percent when it is switched on

const readStored = () => { try { return localStorage.getItem(KEY) || ""; } catch { return ""; } };
const toBase64 = bytes => btoa(String.fromCharCode(...bytes));

/** The animation kept for the Patcher, as the file the firmware reads, or null for the default. */
export function storedAnimation() {
  try {
    const text = readStored();
    if (!text) return null;
    const bytes = Uint8Array.from(atob(text), c => c.charCodeAt(0));
    return validateAnimation(bytes) ? null : bytes;
  } catch {
    return null;
  }
}

const kb = bytes => number(bytes / 1024, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const MAX_KB = number(MAX_BYTES / 1024);
const baseName = name => name.replace(/\.[^.]+$/, "");
const byName = (a, b) => a.name.localeCompare(b.name, undefined, { numeric: true });
const reducedMotion = () => document.documentElement.dataset.motion === "reduce" || !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const later = () => new Promise(resolve => setTimeout(resolve));

const loadImage = file => new Promise((resolve, reject) => {
  const url = URL.createObjectURL(file);
  const img = new Image();
  img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
  img.onerror = () => { URL.revokeObjectURL(url); reject(new Error(file.name)); };
  img.src = url;
});

/** Every frame of a GIF as a canvas the size of the GIF, composed as a browser shows it. */
function gifPictures(bytes) {
  const gif = decodeGif(bytes);
  return gif.frames.map(f => {
    const c = el("canvas", { width: gif.width, height: gif.height });
    c.getContext("2d").putImageData(new ImageData(f.rgba, gif.width, gif.height), 0, 0);
    return c;
  });
}

/** The pictures of a file as { name, picture }: every frame of a GIF, else the one picture. Throws on anything else. */
async function picturesOf(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (String.fromCharCode(...bytes.subarray(0, 3)) === "GIF") {
    const pictures = gifPictures(bytes);
    return pictures.map((picture, i) => ({ name: pictures.length > 1 ? `${baseName(file.name)} ${i + 1}` : baseName(file.name), picture }));
  }
  return [{ name: baseName(file.name), picture: await loadImage(file) }];
}

/** A labelled block of the flow: label, content, optional help below. */
const field = (label, nodes, attrs = {}) => el("div", { className: "ui-field", ...attrs }, [label, ...nodes]);

function segmented(name, options, label) {
  const inputs = options.map(([value], i) => el("input", { type: "radio", name, value, id: `${name}-${value}`, checked: i === 0 }));
  const node = el("div", { className: "ui-segmented", id: name }, options.map(([, text, glyph], i) => el("label", { className: "ui-segmented-option" }, [inputs[i], el("span", {}, [glyph ? icon(glyph) : null, text])])));
  node.setAttribute("role", "radiogroup");
  node.setAttribute("aria-label", label);
  return { node, inputs, value: () => inputs.find(i => i.checked)?.value };
}

const iconButton = (id, glyph, label) => {
  const b = el("button", { type: "button", className: "btn icon", id }, [icon(glyph)]);
  b.setAttribute("aria-label", label);
  return b;
};

/** The section of the Ladeanimation tab (splash.mjs). */
export function loadingAnimSection() {
  // The gallery: the imported pictures, spread over the slots by the mode, and what a slot got of its own (a picture,
  // an edit, or null for emptied). An item is { name, picture } from a file or { name, pixels } drawn or kept.
  let source = [];
  const own = new Map();
  let current = 0;
  let anim = null;
  let frames = [];          // the frame per slot, before invert, null for an empty slot; built by update()
  let dirty = false;
  let tooBig = false;

  // (a) Laden: a GIF or several pictures replace the gallery
  const fileInput = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-anim-file", accept: "image/*", multiple: true });
  const files = el("span", { className: "ui-dropzone-files" });
  const drop = el("label", { className: "ui-dropzone" }, [
    fileInput,
    icon("film"),
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: t("splash.anim.drop.drag") }), t("common.pick")]),
    el("span", { className: "ui-dropzone-hint", textContent: t("splash.anim.drop.hint") }),
    files,
  ]);
  const loading = el("div", { className: "ui-progress", id: "cee-anim-loading", hidden: true }, [el("span", { className: "ui-progress-bar" })]);
  loading.setAttribute("role", "progressbar");
  loading.setAttribute("aria-valuemin", "0");
  loading.setAttribute("aria-valuemax", "100");
  loading.setAttribute("aria-label", t("splash.anim.loading"));

  const mode = segmented("cee-anim-mode", [["stretch", t("splash.anim.mode.stretch")], ["repeat", t("splash.anim.mode.repeat")]], t("splash.anim.mode"));
  const modeHelp = el("p", { className: "ui-field-help", id: "cee-anim-mode-help" });
  mode.node.setAttribute("aria-describedby", modeHelp.id);
  const modeField = field(el("span", { className: "ui-field-label", textContent: t("splash.anim.mode") }), [mode.node, modeHelp], { id: "cee-anim-mode-field", hidden: true });
  for (const input of mode.inputs) input.addEventListener("change", () => update());

  // (b) Galerie: one slot at a time, arrows, slider and play
  const slotCanvas = el("canvas", { className: "cee-splash-preview cee-anim-slot-picture", id: "cee-anim-slot-picture", width: SPLASH_W, height: SPLASH_H });
  slotCanvas.setAttribute("role", "img");
  const slotInput = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-anim-slot-file", accept: "image/*" });
  const slotHint = el("span", { className: "ui-dropzone-hint" });
  const slotDrop = el("label", { className: "ui-dropzone cee-anim-slot-drop", id: "cee-anim-slot-drop" }, [
    slotInput,
    icon("plus"),
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: t("splash.drop.drag") }), t("common.pick")]),
    slotHint,
  ]);
  const edit = iconButton("cee-anim-edit", "pencil", "");
  const remove = iconButton("cee-anim-remove", "trash", "");
  const prev = iconButton("cee-anim-prev", "chevronLeft", t("splash.anim.prev"));
  const next = iconButton("cee-anim-next", "chevronRight", t("splash.anim.next"));
  const slotText = el("p", { className: "ui-field-help", id: "cee-anim-slot-text" });
  slotText.setAttribute("aria-live", "polite");
  const stage = el("div", { className: "cee-anim-stage" }, [
    prev,
    el("div", { className: "cee-anim-slot", id: "cee-anim-slot" }, [slotCanvas, slotDrop, el("div", { className: "cee-anim-slot-tools" }, [edit, remove])]),
    next,
  ]);
  const play = el("button", { type: "button", className: "btn icon", id: "cee-anim-play" });
  const progress = el("input", { type: "range", className: "ui-range", id: "cee-anim-progress", min: 0, max: SLOTS - 1, value: 0 });
  const progressOut = el("output", { className: "ui-range-value", id: "cee-anim-progress-value", htmlFor: "cee-anim-progress", textContent: "0 %" });
  progressOut.dataset.unit = " %";
  const gallery = el("div", { className: "cee-anim-gallery", id: "cee-anim-gallery" }, [
    stage,
    slotText,
    el("div", { className: "cee-anim-player" }, [
      play,
      field(el("label", { className: "ui-field-label", htmlFor: "cee-anim-progress" }, [t("splash.anim.progress"), " ", progressOut]), [progress]),
    ]),
  ]);
  gallery.setAttribute("role", "group");
  gallery.setAttribute("aria-label", t("splash.anim.frames"));

  // (c) Vorschau: the animation as the display shows it, always running
  const lcd = el("canvas", { className: "cee-lcd cee-catalog-thumb", id: "cee-anim-preview", width: SPLASH_W, height: SPLASH_H });
  lcd.setAttribute("role", "img");
  lcd.setAttribute("aria-label", t("splash.anim.preview"));
  const lcdAt = el("span", { className: "muted", id: "cee-anim-preview-at" });
  const invert = switchOf("cee-anim-invert", t("splash.invert"));
  invert.input.addEventListener("change", () => update());
  const preview = field(el("span", { className: "ui-field-label", textContent: t("splash.anim.preview.title") }), [
    el("div", { className: "cee-lcd-frame cee-anim-lcd" }, [lcd]),
    el("p", { className: "ui-field-help" }, [lcdAt]),
    invert.node,
  ], { id: "cee-anim-preview-field" });

  // (d) Warte-Schleife: the slots from a percent on play in a circle while the loading stands
  const loopSwitch = switchOf("cee-anim-loop", t("splash.anim.loop"));
  loopSwitch.input.addEventListener("change", () => update());
  const percent = el("input", { type: "number", id: "cee-anim-loop-percent", min: 1, max: SLOTS - 1, value: LOOP_FROM });
  percent.setAttribute("aria-describedby", "cee-anim-loop-help");
  percent.addEventListener("change", () => update());
  const percentBox = el("div", { className: "ui-input cee-anim-percent" }, [percent, el("span", { className: "ui-input-suffix", textContent: "%" })]);
  const loopMode = field(el("label", { className: "ui-field-label", htmlFor: "cee-anim-loop-percent", textContent: t("splash.anim.loop.percent") }), [percentBox], { id: "cee-anim-loop-mode", hidden: true });
  const loopFrom = () => Math.min(SLOTS - 1, Math.max(1, Math.round(Number(percent.value)) || LOOP_FROM));
  const loopCut = () => (loopSwitch.input.checked ? loopFrom() : SLOTS);
  const loop = el("div", { className: "cee-anim-loop" }, [
    loopSwitch.node,
    loopMode,
    el("p", { className: "ui-field-help", id: "cee-anim-loop-help", textContent: t("splash.anim.loop.help") }),
  ]);

  // (e) Umwandlung
  const threshold = el("input", { type: "range", className: "ui-range", id: "cee-anim-threshold", min: 1, max: 254, value: 128 });
  const thresholdOut = el("output", { className: "ui-range-value", htmlFor: "cee-anim-threshold", textContent: "128" });
  threshold.addEventListener("input", () => { thresholdOut.textContent = threshold.value; update(); });
  const dither = switchOf("cee-anim-dither", t("splash.dither"));
  dither.input.addEventListener("change", () => update());
  const convert = el("details", { className: "ui-details", id: "cee-anim-convert" }, [
    el("summary", { textContent: t("splash.anim.convert") }),
    el("div", { className: "ui-details-body" }, [
      field(el("label", { className: "ui-field-label", htmlFor: "cee-anim-threshold" }, tNodes("splash.threshold", { value: thresholdOut })), [threshold]),
      dither.node,
    ]),
  ]);

  // (f) Größe und Speichern
  const meter = el("div", { className: "ui-meter", id: "cee-anim-size" });
  const sizeText = el("p", { className: "ui-field-help", id: "cee-anim-size-text" });
  const tooBigText = el("p", { className: "ui-field-error", id: "cee-anim-too-big", hidden: true });
  const thin = el("button", { type: "button", className: "btn sm", id: "cee-anim-thin", textContent: t("splash.anim.thin"), hidden: true });
  thin.setAttribute("aria-describedby", "cee-anim-too-big");
  const size = field(el("span", { className: "ui-field-label", textContent: t("splash.anim.size.label") }), [
    el("div", { className: "cee-anim-meter-row" }, [meter, thin]),
    sizeText,
    tooBigText,
  ], { id: "cee-anim-size-field" });

  const use = el("button", { type: "button", className: "btn cee-primary", id: "cee-anim-use", textContent: t("splash.anim.use"), hidden: true });
  const reset = el("button", { type: "button", className: "btn", id: "cee-anim-reset", textContent: t("splash.anim.reset"), hidden: true });
  // one plain line: what the Patcher takes, whether the changes are saved, and the way to the Patcher
  const stateText = el("span", { id: "cee-anim-state-text" });
  stateText.setAttribute("aria-live", "polite");
  const patcherLink = el("a", { className: "cee-text-link", id: "cee-anim-patcher-link", href: "#patcher", textContent: t("splash.anim.toPatcher") });
  const state = el("p", { className: "ui-field-help", id: "cee-anim-state" }, [stateText, " ", patcherLink]);
  const save = el("div", { className: "cee-anim-save" }, [el("div", { className: "cee-anim-actions" }, [use, reset]), state]);

  // (g) Der Editor: pen and eraser on the 128 x 64 pixels of one slot
  const tool = segmented("cee-anim-tool", [["pen", t("splash.anim.tool.pen"), "pencil"], ["eraser", t("splash.anim.tool.eraser"), "eraser"]], t("splash.anim.tool"));
  const board = el("canvas", { className: "cee-splash-preview cee-anim-board", id: "cee-anim-board", width: SPLASH_W, height: SPLASH_H });
  board.setAttribute("role", "img");
  const editorTitle = el("h2", { className: "ui-dialog-title", id: "cee-anim-editor-title" });
  const editorClose = iconButton("cee-anim-editor-close", "x", t("common.close"));
  editorClose.classList.add("ui-dialog-close");
  editorClose.setAttribute("data-ui-dialog-close", "");
  const editor = el("dialog", { className: "ui-dialog ui-dialog-wide cee-anim-editor", id: "cee-anim-editor" });
  editor.setAttribute("aria-labelledby", editorTitle.id);
  editor.setAttribute("data-ui-static", "");
  editor.append(el("form", { method: "dialog", className: "ui-dialog-box" }, [
    el("header", { className: "ui-dialog-head" }, [editorTitle, editorClose]),
    el("div", { className: "ui-dialog-body" }, [
      tool.node,
      board,
      el("p", { className: "ui-field-help", textContent: t("splash.anim.editor.help") }),
    ]),
    el("footer", { className: "ui-dialog-foot" }, [
      el("button", { type: "submit", className: "btn", value: "cancel", textContent: t("common.cancel") }),
      el("button", { type: "submit", className: "btn primary", id: "cee-anim-editor-apply", value: "ok", textContent: t("splash.anim.editor.apply") }),
    ]),
  ]));

  // --- the model ---
  const key = () => `${threshold.value}|${dither.input.checked}`;
  /** The item a slot shows: its own, else the imported picture the mode gives it, else null. */
  const itemAt = s => (own.has(s) ? own.get(s) : source[slotSource(s, source.length, mode.value())] ?? null);
  /** A slot's pixels before invert: drawn, kept, or the picture with the page's conversion. */
  const basePixels = item => item.pixels ?? (item.cache ??= new Map()).get(key())
    ?? item.cache.set(key(), pixelsOf(item.picture, { threshold: Number(threshold.value), dither: dither.input.checked })).get(key());
  const shownPixels = px => (invert.input.checked ? px.map(p => p ^ 1) : px);
  const filledCount = () => Array.from({ length: SLOTS }, (_, s) => itemAt(s)).filter(Boolean).length;
  /** The last filled slot before `s`, or -1. */
  const before = s => { for (let p = s - 1; p >= 0; p--) if (itemAt(p)) return p; return -1; };

  function build() {
    const cache = new Map();
    frames = Array.from({ length: SLOTS }, (_, s) => {
      const item = itemAt(s);
      if (!item) return null;
      if (!cache.has(item)) cache.set(item, pixelsToFrame(basePixels(item)));
      return cache.get(item);
    });
    anim = slotsToAnimation(frames, { loopFrom: loopSwitch.input.checked ? loopFrom() : 0, invert: invert.input.checked });
  }

  /** The slider's fill and value after a value set by code, which fires no input event. */
  const sync = () => (window.ui?.syncRange ? window.ui.syncRange(progress) : (progressOut.textContent = `${progress.value}${progressOut.dataset.unit}`));

  function showSlot() {
    const s = current;
    const item = itemAt(s);
    slotCanvas.hidden = !item;
    slotDrop.hidden = !!item;
    remove.hidden = !item;
    const n = s + 1;
    edit.setAttribute("aria-label", t("splash.anim.edit", { n }));
    remove.setAttribute("aria-label", t("splash.anim.remove", { n }));
    slotHint.textContent = t("splash.anim.slot.hint", { n });
    prev.disabled = s === 0;
    next.disabled = s === SLOTS - 1;
    const head = t("splash.anim.slot", { n, total: SLOTS, pct: s });
    const p = before(s);
    const inLoop = s >= loopCut();
    const what = item ? item.name : inLoop ? t("splash.anim.slot.skip") : p >= 0 ? t("splash.anim.slot.carry", { n: p + 1 }) : t("splash.anim.slot.blank");
    slotText.textContent = `${head}. ${what}${inLoop ? ` ${t("splash.anim.slot.loop")}` : ""}`;
    if (item) {
      slotCanvas.setAttribute("aria-label", t("splash.anim.thumb", { n, name: item.name }));
      paint(slotCanvas, shownPixels(basePixels(item)));
    }
    if (String(progress.value) !== String(s)) { progress.value = String(s); sync(); }
    if (!previewMoving()) drawPreview(Math.min(1000, Math.ceil(s * 1000 / (SLOTS - 1))), null);
  }

  function go(s) {
    current = Math.min(SLOTS - 1, Math.max(0, s));
    showSlot();
  }
  prev.addEventListener("click", () => { pause(); go(current - 1); });
  next.addEventListener("click", () => { pause(); go(current + 1); });
  progress.addEventListener("input", () => { pause(); go(Number(progress.value)); });

  // --- gallery play: one slot per FRAME_MS, as fast as the firmware may change the picture ---
  let playing = false;
  let playTimer = 0;
  function showPlay() {
    play.replaceChildren(icon(playing ? "pause" : "play"));
    play.setAttribute("aria-label", t(playing ? "splash.anim.pause" : "splash.anim.play"));
  }
  function start() {
    if (current >= SLOTS - 1) go(0);
    playing = true;
    showPlay();
    playTimer = setInterval(() => {
      if (!gallery.isConnected || current >= SLOTS - 1) { pause(); return; }
      go(current + 1);
    }, FRAME_MS);
  }
  function pause() {
    playing = false;
    clearInterval(playTimer);
    playTimer = 0;
    showPlay();
  }
  play.addEventListener("click", () => (playing ? pause() : start()));

  // --- preview: the run from 0 to 100 % at FRAME_MS a slot, a pause at 100 % with the loop, and again ---
  const previewMoving = () => !reducedMotion();
  let raf = 0;
  let runStart = 0;
  let loopSince = null;
  let drawnKey = "";
  /** What the device shows at `permille`, with loop picture `j` over it once the loop plays. */
  function drawPreview(permille, j) {
    if (!anim) return;
    const i = progressIndex(anim.progress.length, permille);
    const looping = anim.loop.length > 0 && anim.loopFrom > 0 && permille >= 10 * anim.loopFrom;
    const k = looping ? (j ?? 0) % anim.loop.length : null;
    lcdAt.textContent = `${Math.floor(permille / 10)} %`;
    const drawn = `${i}|${k}`;
    if (drawn === drawnKey) return;
    drawnKey = drawn;
    const frame = k === null ? anim.progress[i] : loopPicture(anim.progress[i], anim.progress[progressIndex(anim.progress.length, 10 * anim.loopFrom)], anim.loop[k]);
    drawDisplay(lcd, frame);
  }
  function tick(now) {
    raf = 0;
    if (!lcd.isConnected || !(lcd.checkVisibility?.() ?? true) || !previewMoving()) return;
    const run = SLOTS * FRAME_MS;
    // a frame's time can lie just before the start taken with performance.now()
    const at = Math.max(0, now - runStart) % (run + HOLD_MS);
    const permille = at >= run ? 1000 : Math.floor(at * 1000 / run);
    const looping = anim && anim.loop.length && anim.loopFrom && permille >= 10 * anim.loopFrom;
    if (!looping) loopSince = null; else loopSince ??= now;
    drawPreview(permille, looping ? Math.floor((now - loopSince) / LOOP_MS) : null);
    raf = requestAnimationFrame(tick);
  }
  const runPreview = () => {
    if (raf || !previewMoving()) return;
    runStart = performance.now();
    raf = requestAnimationFrame(tick);
  };
  // the preview runs while it is on screen and starts again when it comes back (the tab, a scroll)
  const seen = typeof IntersectionObserver === "function" ? new IntersectionObserver(entries => {
    if (entries.some(e => e.isIntersecting)) runPreview();
  }) : null;
  seen?.observe(lcd);

  // --- the editor ---
  let pixels = null;
  let editing = 0;
  let last = null;
  function openEditor() {
    pause();
    editing = current;
    const item = itemAt(editing);
    const p = before(editing);
    const startWith = item ?? (p >= 0 ? itemAt(p) : null);
    pixels = startWith ? Uint8Array.from(shownPixels(basePixels(startWith))) : new Uint8Array(SPLASH_W * SPLASH_H).fill(invert.input.checked ? 1 : 0);
    editorTitle.textContent = t("splash.anim.edit", { n: editing + 1 });
    board.setAttribute("aria-label", t("splash.anim.editor.canvas", { n: editing + 1 }));
    tool.inputs[0].checked = true;
    if (window.ui?.openDialog) window.ui.openDialog(editor); else editor.showModal();
    paint(board, pixels);
  }
  edit.addEventListener("click", openEditor);
  const at = e => {
    const r = board.getBoundingClientRect();
    return [Math.floor((e.clientX - r.left) * SPLASH_W / r.width), Math.floor((e.clientY - r.top) * SPLASH_H / r.height)];
  };
  function dot([x, y]) {
    if (x < 0 || y < 0 || x >= SPLASH_W || y >= SPLASH_H) return;
    pixels[y * SPLASH_W + x] = tool.value() === "pen" ? 1 : 0;
  }
  /** A line from the last point, so a fast stroke leaves no gaps. */
  function stroke(to) {
    const from = last ?? to;
    const steps = Math.max(Math.abs(to[0] - from[0]), Math.abs(to[1] - from[1]), 1);
    for (let i = 0; i <= steps; i++) dot([Math.round(from[0] + (to[0] - from[0]) * i / steps), Math.round(from[1] + (to[1] - from[1]) * i / steps)]);
    last = to;
    paint(board, pixels);
  }
  board.addEventListener("pointerdown", e => {
    e.preventDefault();
    board.setPointerCapture?.(e.pointerId);
    last = null;
    stroke(at(e));
  });
  board.addEventListener("pointermove", e => { if (last && e.buttons) stroke(at(e)); });
  const lift = () => { last = null; };
  board.addEventListener("pointerup", lift);
  board.addEventListener("pointercancel", lift);
  editor.addEventListener("close", () => {
    if (editor.returnValue !== "ok" || !pixels) return;
    const name = itemAt(editing)?.name ?? t("splash.anim.frame", { n: editing + 1 });
    own.set(editing, { name, pixels: invert.input.checked ? pixels.map(p => p ^ 1) : pixels });
    pixels = null;
    update();
  });

  /** Size, buttons, slot and preview after any change. */
  function update() {
    const k = source.length;
    modeField.hidden = !(k > 1 && k < SLOTS);
    if (!modeField.hidden) modeHelp.textContent = t("splash.anim.mode.help", { k });
    loopMode.hidden = !loopSwitch.input.checked;
    build();
    drawnKey = "";
    const filled = frames.some(Boolean);
    size.hidden = !filled;
    if (!filled) {
      dirty = false;
      tooBig = false;
    } else {
      const costs = costPerFrame(anim);
      const bytes = HEADER_BYTES + costs.reduce((s, c) => s + c.bytes, 0);
      tooBig = bytes > MAX_BYTES;
      sizeText.textContent = t("splash.anim.size", { size: kb(bytes), max: MAX_KB });
      window.ui?.setMeter?.(meter, Math.min(100, bytes * 100 / MAX_BYTES), { label: t("splash.anim.size.label"), valueText: sizeText.textContent, tone: tooBig ? "error" : undefined, warnAt: 90 });
      use.setAttribute("aria-describedby", tooBig ? "cee-anim-too-big cee-anim-state" : "cee-anim-state");
      thin.hidden = !tooBig || progressSlots().length < 3;
      tooBigText.hidden = !tooBig;
      if (tooBig) {
        const loopSlots = Array.from({ length: SLOTS }, (_, s) => s).filter(s => s >= loopCut() && frames[s]);
        const slotOf = c => (c.kind === "progress" ? c.index : loopSlots[c.index]);
        const named = c => itemAt(slotOf(c))?.name ?? t("splash.anim.frame", { n: slotOf(c) + 1 });
        const worst = costs.slice(1).sort((a, b) => b.bytes - a.bytes).slice(0, 3).map(c => t("splash.anim.cost", { name: named(c), size: kb(c.bytes) }));
        tooBigText.textContent = t("splash.anim.tooBig", { size: kb(bytes), max: MAX_KB, frames: worst.join(", ") }) + (thin.hidden ? "" : ` ${t("splash.anim.thin.help")}`);
      }
      dirty = tooBig || toBase64(encodeAnimation(anim).bytes) !== readStored();
    }
    showSave();
    showSlot();
    runPreview();
  }

  /** The filled slots before the loop, the ones thinning may empty. */
  const progressSlots = () => Array.from({ length: loopCut() }, (_, s) => s).filter(s => frames[s]);

  function showSave() {
    const kept = storedAnimation();
    const inPatcher = kept ? t("splash.anim.state.own", { size: kb(kept.length) }) : t("splash.anim.state.default");
    const filled = frames.some(Boolean);
    stateText.textContent = filled ? `${inPatcher} ${t(dirty ? "splash.anim.unsaved" : "splash.anim.saved")}` : inPatcher;
    reset.hidden = !kept;
    use.hidden = !filled;
    // saving is only offered for something new that fits
    use.disabled = tooBig || !dirty;
  }

  thin.addEventListener("click", () => {
    const slots = progressSlots();
    slots.forEach((s, i) => { if (i % 2 && i !== slots.length - 1) own.set(s, null); });
    update();
  });

  use.addEventListener("click", () => {
    const { bytes } = encodeAnimation(anim);
    const bad = validateAnimation(bytes);
    if (bad) { toast(t("splash.anim.invalid", { reason: bad }), "error"); return; }
    try {
      localStorage.setItem(KEY, toBase64(bytes));
    } catch {
      toast(t("splash.noStorage"), "error");
      return;
    }
    dirty = false;
    showSave();
    toast(t("splash.anim.used"), "ok");
  });

  reset.addEventListener("click", async () => {
    const ok = dirty
      ? await (window.ui?.confirm?.({ title: t("splash.anim.reset.title"), text: t("splash.anim.reset.text"), danger: true, confirmLabel: t("splash.anim.reset"), cancelLabel: t("common.cancel") }) ?? true)
      : true;
    if (!ok) return;
    try { localStorage.removeItem(KEY); } catch { /* nothing kept */ }
    source = [];
    own.clear();
    loopSwitch.input.checked = false;
    invert.input.checked = false;
    files.textContent = "";
    pause();
    go(0);
    update();
    toast(t("splash.anim.resetDone"), "ok");
  });

  /** The pictures of the files in the order of their names, or null after telling which file failed. */
  async function readAll(picked) {
    const out = [];
    loading.hidden = false;
    window.ui?.setProgress?.(loading, 0, t("splash.anim.loading"));
    try {
      for (const [k, file] of picked.entries()) {
        try {
          out.push(...await picturesOf(file));
        } catch {
          toast(t("splash.notImage", { name: file.name }), "error");
          return null;
        }
        window.ui?.setProgress?.(loading, (k + 1) * 100 / picked.length, t("splash.anim.loading"));
        await later();
      }
    } finally {
      loading.hidden = true;
    }
    if (!out.length) { toast(t("splash.notImage", { name: picked[0].name }), "error"); return null; }
    return out;
  }

  fileInput.addEventListener("change", async () => {
    const picked = [...(fileInput.files ?? [])].sort(byName);
    fileInput.value = "";
    if (!picked.length) return;
    const n = filledCount();
    if (n && !(await (window.ui?.confirm?.({ title: t("splash.anim.replace.title"), text: t("splash.anim.replace.text", { n }), confirmLabel: t("splash.anim.replace.ok"), cancelLabel: t("common.cancel") }) ?? true))) {
      files.textContent = "";
      drop.removeAttribute("data-filled");
      return;
    }
    const next = await readAll(picked);
    if (!next) return;
    source = next;
    own.clear();
    files.textContent = picked.length > 3 ? t("splash.anim.files", { n: picked.length, first: picked[0].name, last: picked.at(-1).name }) : picked.map(f => f.name).join(", ");
    pause();
    current = 0;
    update();
  });

  slotInput.addEventListener("change", async () => {
    const file = slotInput.files?.[0];
    slotInput.value = "";
    slotDrop.removeAttribute("data-filled");
    if (!file) return;
    const s = current;
    const got = await readAll([file]);
    if (!got) return;
    own.set(s, got[0]);
    update();
  });

  remove.addEventListener("click", () => { own.set(current, null); update(); });

  // the kept animation comes back as it is in the file: its slots and the loop start
  const kept = storedAnimation();
  if (kept) {
    const back = animationToSlots(decodeAnimation(kept));
    source = back.slots.map((f, s) => (f ? { name: t("splash.anim.frame", { n: s + 1 }), pixels: frameToPixels(f) } : null));
    if (back.loopFrom) { loopSwitch.input.checked = true; percent.value = String(back.loopFrom); }
  }
  showPlay();
  // the page builds the section before it is in the document: the first drawing waits for the colours of the display
  queueMicrotask(() => { update(); sync(); });

  return el("section", { className: "ui-section cee-anim", id: "cee-anim" }, [
    el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", id: "cee-anim-title", textContent: t("splash.anim.title") })]),
    el("p", { className: "cee-splash-lead", textContent: t("splash.anim.lead") }),
    drop,
    loading,
    modeField,
    gallery,
    preview,
    loop,
    convert,
    size,
    save,
    editor,
  ]);
}
