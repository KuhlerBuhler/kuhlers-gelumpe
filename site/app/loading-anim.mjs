/** The loading animation on the Design page: a GIF or single pictures to a BLLA file the Patcher writes. Logic: src/loading-anim.mjs. */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { t, tNodes } from "./i18n.mjs";
import { pixelsOf, paint, switchOf } from "./splash.mjs";
import { number } from "../../src/text.mjs";
import { decodeGif } from "../../src/gif.mjs";
import { encodeAnimation, decodeAnimation, validateAnimation, thinAnimation, costPerFrame, progressIndex, loopPicture, pixelsToFrame, frameToPixels, MAX_BYTES, HEADER_BYTES, SPLASH_W, SPLASH_H } from "../../src/loading-anim.mjs";

const KEY = "cee.loading.anim";
const LOOP_MS = 96;     // the firmware's loop picture time (tools/patch/load_bar.py)
const STALL_MS = 500;   // load_bar.STALL_MS: the loop of a stalled progress starts after this

/** The animation kept for the Patcher, as the file the firmware reads, or null for the default. */
export function storedAnimation() {
  try {
    const text = localStorage.getItem(KEY);
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

/** The section's nodes, for the Design page (splash.mjs). */
export function loadingAnimSection() {
  // { name, picture } from a file, or { name, pixels } from the kept file; role "progress" or "loop"
  let frames = [];
  let toldTooBig = "";
  let playing = null;
  let stallTimer = null;

  const fileInput = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-anim-file", accept: "image/*", multiple: true });
  const files = el("span", { className: "ui-dropzone-files" });
  const drop = el("label", { className: "ui-dropzone" }, [
    fileInput,
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: t("splash.anim.drop.drag") }), t("common.pick")]),
    el("span", { className: "ui-dropzone-hint", textContent: t("splash.anim.drop.hint") }),
    files,
  ]);

  const canvas = el("canvas", { className: "cee-splash-preview", id: "cee-anim-preview", width: SPLASH_W, height: SPLASH_H });
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", t("splash.anim.preview"));

  const progress = el("input", { type: "range", className: "ui-range", id: "cee-anim-progress", min: 0, max: 100, value: 0 });
  const progressOut = el("output", { className: "ui-range-value", id: "cee-anim-progress-value", htmlFor: "cee-anim-progress", textContent: "0" });
  progress.addEventListener("input", () => { stall(); preview(); });

  const threshold = el("input", { type: "range", className: "ui-range", id: "cee-anim-threshold", min: 1, max: 254, value: 128 });
  const thresholdOut = el("output", { className: "ui-range-value", htmlFor: "cee-anim-threshold", textContent: "128" });
  threshold.addEventListener("input", () => { thresholdOut.textContent = threshold.value; update(); });
  const dither = switchOf("cee-anim-dither", t("splash.dither"));
  const invert = switchOf("cee-anim-invert", t("splash.invert"));
  dither.input.addEventListener("change", update);
  invert.input.addEventListener("change", update);

  const modes = [["stall", t("splash.anim.loop.stall")], ["percent", t("splash.anim.loop.from")]].map(([value, text], i) => {
    const input = el("input", { type: "radio", name: "cee-anim-loop-from", id: `cee-anim-loop-from-${value}`, value, checked: i === 0 });
    input.addEventListener("change", update);
    return { input, node: el("label", { className: "ui-segmented-option" }, [input, el("span", { textContent: text })]) };
  });
  const mode = el("div", { className: "ui-segmented", id: "cee-anim-loop-from" }, modes.map(m => m.node));
  mode.setAttribute("role", "radiogroup");
  mode.setAttribute("aria-label", t("splash.anim.loop"));
  const percent = el("input", { type: "number", className: "input", id: "cee-anim-loop-percent", min: 1, max: 100, value: 95 });
  percent.addEventListener("change", update);
  const fromPercent = () => modes[1].input.checked;
  const loopFrom = () => (fromPercent() ? Math.min(100, Math.max(1, Math.round(Number(percent.value)) || 95)) : 0);

  const meter = el("div", { className: "ui-meter", id: "cee-anim-size" });
  const sizeText = el("span", { className: "muted", id: "cee-anim-size-text" });
  const thin = el("button", { type: "button", className: "btn", id: "cee-anim-thin", textContent: t("splash.anim.thin"), hidden: true });
  const use = el("button", { type: "button", className: "btn cee-primary", id: "cee-anim-use", textContent: t("splash.anim.use"), disabled: true });
  const list = el("ol", { className: "cee-anim-frames", id: "cee-anim-frames", hidden: true });
  list.setAttribute("aria-label", t("splash.anim.frames"));

  const state = el("p", { className: "cee-splash-lead", id: "cee-anim-state" });
  const reset = el("button", { type: "button", className: "btn", id: "cee-anim-reset", textContent: t("splash.anim.reset") });
  const work = el("div", { className: "cee-splash-work", id: "cee-anim-work", hidden: true }, [
    canvas,
    el("div", { className: "cee-splash-controls" }, [
      el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: "cee-anim-progress" }, tNodes("splash.anim.progress", { value: progressOut })), progress]),
      el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: "cee-anim-threshold" }, tNodes("splash.threshold", { value: thresholdOut })), threshold]),
      dither.node,
      invert.node,
      el("div", { className: "ui-field" }, [el("span", { className: "ui-field-label", textContent: t("splash.anim.loop") }), mode]),
      el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: "cee-anim-loop-percent", textContent: t("splash.anim.loop.percent") }), percent]),
      el("div", { className: "ui-field" }, [el("span", { className: "ui-field-label", textContent: t("splash.anim.size.label") }), meter, sizeText]),
      el("div", { className: "actions" }, [use, thin]),
    ]),
  ]);

  /** The pixels of a frame with the page's conversion, the same as the start image's. */
  const pixelsOfFrame = f => f.pixels ?? (f.cache ??= new Map()).get(key()) ?? f.cache.set(key(), pixelsOf(f.picture, options())).get(key());
  const options = () => ({ threshold: Number(threshold.value), dither: dither.input.checked, invert: invert.input.checked });
  const key = () => `${threshold.value}|${dither.input.checked}|${invert.input.checked}`;

  /** The frames as the encoder takes them, plus what each of the page's frames is in it. */
  function model() {
    const progressFrames = frames.filter(f => f.role === "progress");
    const loopFrames = frames.filter(f => f.role === "loop");
    return {
      progressFrames, loopFrames,
      anim: { progress: progressFrames.map(f => pixelsToFrame(pixelsOfFrame(f))), loop: loopFrames.map(f => pixelsToFrame(pixelsOfFrame(f))), loopFrom: loopFrom() },
    };
  }

  function drawList() {
    list.replaceChildren(...frames.map((f, i) => {
      const thumb = el("canvas", { className: "cee-splash-thumb", width: SPLASH_W, height: SPLASH_H });
      thumb.setAttribute("aria-hidden", "true");
      paint(thumb, pixelsOfFrame(f));
      const role = el("select", { className: "select", id: `cee-anim-role-${i}` }, [
        el("option", { value: "progress", textContent: t("splash.anim.role.progress"), selected: f.role === "progress" }),
        el("option", { value: "loop", textContent: t("splash.anim.role.loop"), selected: f.role === "loop" }),
      ]);
      role.setAttribute("aria-label", t("splash.anim.role", { name: f.name }));
      role.addEventListener("change", () => { f.role = role.value; update({ list: false }); });
      return el("li", { className: "cee-anim-frame" }, [thumb, el("span", { className: "cee-anim-frame-name", textContent: f.name }), role]);
    }));
  }

  /** Size, buttons and preview after any change; `list: false` when the thumbnails stay as they are. */
  function update({ list: redraw = true } = {}) {
    work.hidden = !frames.length;
    list.hidden = !frames.length;
    if (!frames.length) { stopLoop(); return; }
    if (redraw) drawList();
    percent.disabled = !fromPercent();
    const { progressFrames, loopFrames, anim } = model();
    if (!progressFrames.length) {
      sizeText.textContent = t("splash.anim.noProgress");
      window.ui?.setMeter?.(meter, 0, { label: t("splash.anim.size.label"), valueText: sizeText.textContent });
      use.disabled = true;
      thin.hidden = true;
      preview();
      return;
    }
    const costs = costPerFrame(anim);
    const size = HEADER_BYTES + costs.reduce((s, c) => s + c.bytes, 0);
    const tooBig = size > MAX_BYTES;
    sizeText.textContent = t("splash.anim.size", { size: kb(size), max: MAX_KB });
    window.ui?.setMeter?.(meter, Math.min(100, size * 100 / MAX_BYTES), { label: t("splash.anim.size.label"), valueText: sizeText.textContent, tone: tooBig ? "error" : undefined, warnAt: 90 });
    use.disabled = tooBig;
    thin.hidden = !tooBig || progressFrames.length < 3;
    const told = tooBig ? `${size}|${frames.length}` : "";
    if (told && told !== toldTooBig) {
      const named = c => (c.kind === "progress" ? progressFrames : loopFrames)[c.index].name;
      const worst = costs.slice(1).sort((a, b) => b.bytes - a.bytes).slice(0, 3).map(c => t("splash.anim.cost", { name: named(c), size: kb(c.bytes) }));
      toast(t("splash.anim.tooBig", { size: kb(size), max: MAX_KB, frames: worst.join(", ") }), "error");
    }
    toldTooBig = told;
    preview();
  }

  /** What the device shows at the slider's percent: the progress picture, and the loop over it when it plays. */
  function preview() {
    progressOut.textContent = progress.value;
    const { anim } = model();
    if (!anim.progress.length) { stopLoop(); paint(canvas, new Uint8Array(SPLASH_W * SPLASH_H)); return; }
    const pct = Number(progress.value);
    const shown = anim.progress[progressIndex(anim.progress.length, pct >= 100 ? 1000 : pct * 10)];
    const loops = anim.loop.length && anim.loopFrom > 0 && pct >= anim.loopFrom;
    if (loops) startLoop(shown, anim); else { if (!stallTimer) stopLoop(); paint(canvas, frameToPixels(shown)); }
  }

  function startLoop(shown, anim) {
    stopLoop();
    const base = anim.progress[progressIndex(anim.progress.length, 10 * anim.loopFrom)];
    const pictures = anim.loop.map(loop => frameToPixels(loopPicture(shown, base, loop)));
    let j = 0;
    const step = () => paint(canvas, pictures[j++ % pictures.length]);
    step();
    playing = setInterval(step, LOOP_MS);
  }
  function stopLoop() { if (playing) { clearInterval(playing); playing = null; } }

  /** With the loop on a stall: the slider stands still for STALL_MS, then the loop plays, as on the device. */
  function stall() {
    clearTimeout(stallTimer);
    stallTimer = null;
    stopLoop();
    const { anim } = model();
    if (!anim.loop.length || anim.loopFrom > 0 || !anim.progress.length) return;
    stallTimer = setTimeout(() => {
      if (!canvas.isConnected) return;
      const now = model().anim;
      if (!now.loop.length || now.loopFrom > 0) return;
      const pct = Number(progress.value);
      startLoop(now.progress[progressIndex(now.progress.length, pct >= 100 ? 1000 : pct * 10)], now);
    }, STALL_MS);
  }

  function showState() {
    const kept = storedAnimation();
    state.textContent = kept ? t("splash.anim.state.own", { size: kb(kept.length) }) : t("splash.anim.state.default");
    reset.disabled = !kept;
  }

  thin.addEventListener("click", () => {
    const { progressFrames, loopFrames } = model();
    const kept = new Set(thinAnimation({ progress: progressFrames, loop: loopFrames }).progress);
    frames = frames.filter(f => f.role === "loop" || kept.has(f));
    update();
  });

  use.addEventListener("click", () => {
    const { bytes } = encodeAnimation(model().anim);
    const bad = validateAnimation(bytes);
    if (bad) { toast(t("splash.anim.invalid", { reason: bad }), "error"); return; }
    try {
      localStorage.setItem(KEY, btoa(String.fromCharCode(...bytes)));
    } catch {
      toast(t("splash.noStorage"), "error");
      return;
    }
    showState();
    toast(t("splash.anim.used"), "ok");
  });

  reset.addEventListener("click", () => {
    try { localStorage.removeItem(KEY); } catch { /* nothing kept */ }
    frames = [];
    files.textContent = "";
    clearTimeout(stallTimer);
    stallTimer = null;
    update();
    showState();
    toast(t("splash.anim.resetDone"), "ok");
  });

  fileInput.addEventListener("change", async () => {
    const picked = [...(fileInput.files ?? [])].sort(byName);
    fileInput.value = "";
    if (!picked.length) return;
    const next = [];
    for (const file of picked) {
      try {
        const bytes = new Uint8Array(await file.arrayBuffer());
        if (String.fromCharCode(...bytes.subarray(0, 3)) === "GIF") {
          const pictures = gifPictures(bytes);
          pictures.forEach((picture, i) => next.push({ name: pictures.length > 1 ? `${baseName(file.name)} ${i + 1}` : baseName(file.name), picture, role: "progress" }));
        } else {
          next.push({ name: baseName(file.name), picture: await loadImage(file), role: "progress" });
        }
      } catch {
        toast(t("splash.notImage", { name: file.name }), "error");
        return;
      }
    }
    if (!next.length) { toast(t("splash.notImage", { name: picked[0].name }), "error"); return; }
    frames = next;
    files.textContent = picked.map(f => f.name).join(", ");
    progress.value = "0";
    update();
    work.scrollIntoView?.({ block: "nearest" });
  });

  // the kept animation comes back as it is in the file: its pictures, roles and loop start
  const kept = storedAnimation();
  if (kept) {
    const anim = decodeAnimation(kept);
    frames = [
      ...anim.progress.map((f, i) => ({ name: t("splash.anim.frame", { n: i + 1 }), pixels: frameToPixels(f), role: "progress" })),
      ...anim.loop.map((f, i) => ({ name: t("splash.anim.frame", { n: anim.progress.length + i + 1 }), pixels: frameToPixels(f), role: "loop" })),
    ];
    modes[anim.loopFrom ? 1 : 0].input.checked = true;
    if (anim.loopFrom) percent.value = String(anim.loopFrom);
  }
  showState();
  // the page builds the section before it is in the document: the first drawing waits for the colours of the display
  queueMicrotask(() => update());

  return [
    el("h2", { className: "cee-splash-head", id: "cee-anim-title", textContent: t("splash.anim.title") }),
    el("p", { className: "cee-splash-lead", textContent: t("splash.anim.lead") }),
    el("div", { className: "cee-anim-state" }, [state, reset]),
    drop,
    work,
    list,
  ];
}
