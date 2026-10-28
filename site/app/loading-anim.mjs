/** The loading animation on the Design page: a GIF or single pictures to a BLLA file the Patcher writes. Logic: src/loading-anim.mjs. */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { t, tNodes } from "./i18n.mjs";
import { icon } from "./icons.mjs";
import { pixelsOf, paint, switchOf } from "./splash.mjs";
import { number } from "../../src/text.mjs";
import { decodeGif } from "../../src/gif.mjs";
import { encodeAnimation, decodeAnimation, validateAnimation, thinAnimation, costPerFrame, progressIndex, loopPicture, pixelsToFrame, frameToPixels, MAX_BYTES, HEADER_BYTES, SPLASH_W, SPLASH_H } from "../../src/loading-anim.mjs";

const KEY = "cee.loading.anim";
const LOOP_MS = 96;     // the firmware's loop picture time (tools/patch/load_bar.py)
const FRAME_MS = 50;    // load_bar.FRAME_MS: at most one new picture every 50 ms
const PLAY_MS = 4000;   // one run of the preview from 0 to 100 %, longer when the pictures need more at FRAME_MS each
const PAGE = 24;        // pictures shown at once in the strip, the rest on request
const LOOP_FROM = 95;   // the loop's start percent when none is set, also for older files with 0 (loop on a stall)

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

/** A labelled block of the flow: label, content, optional help below. */
const field = (label, nodes, attrs = {}) => el("div", { className: "ui-field", ...attrs }, [label, ...nodes]);

/** The section of the Ladeanimation tab (splash.mjs). */
export function loadingAnimSection() {
  // { name, picture } from a file, or { name, pixels } from the kept file
  let frames = [];
  let loopAt = 0;       // index of the first loop picture in frames; 0: no loop
  let anim = null;      // the frames as the encoder takes them, built by update()
  let loopCache = new Map();
  let shownCount = PAGE;
  let pinned = null;    // a loop picture picked in the strip, shown standing
  let playing = false;
  let raf = 0;
  let playStart = 0;
  let loopSince = null;
  let drawnKey = "";
  let dirty = false;
  let tooBig = false;

  // (a) Laden
  const fileInput = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-anim-file", accept: "image/*", multiple: true });
  const files = el("span", { className: "ui-dropzone-files" });
  const drop = el("label", { className: "ui-dropzone" }, [
    fileInput,
    icon("film"),
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: t("splash.anim.drop.drag") }), t("common.pick")]),
    el("span", { className: "ui-dropzone-hint", textContent: t("splash.anim.drop.hint", { max: MAX_KB }) }),
    files,
  ]);
  const loading = el("div", { className: "ui-progress", id: "cee-anim-loading", hidden: true }, [el("span", { className: "ui-progress-bar" })]);
  loading.setAttribute("role", "progressbar");
  loading.setAttribute("aria-valuemin", "0");
  loading.setAttribute("aria-valuemax", "100");
  loading.setAttribute("aria-label", t("splash.anim.loading"));

  // (b) Ansehen
  const canvas = el("canvas", { className: "cee-splash-preview", id: "cee-anim-preview", width: SPLASH_W, height: SPLASH_H });
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", t("splash.anim.preview"));
  const play = el("button", { type: "button", className: "btn icon", id: "cee-anim-play" });
  const progress = el("input", { type: "range", className: "ui-range", id: "cee-anim-progress", min: 0, max: 100, value: 0 });
  const progressOut = el("output", { className: "ui-range-value", id: "cee-anim-progress-value", htmlFor: "cee-anim-progress", textContent: "0 %" });
  progressOut.dataset.unit = " %";
  const view = el("div", { className: "cee-anim-view" }, [
    canvas,
    el("div", { className: "cee-anim-player" }, [
      play,
      field(el("label", { className: "ui-field-label", htmlFor: "cee-anim-progress" }, [t("splash.anim.progress"), " ", progressOut]), [progress]),
    ]),
  ]);

  // (c) Bilder
  const list = el("ol", { className: "cee-anim-frames", id: "cee-anim-frames" });
  list.setAttribute("aria-label", t("splash.anim.frames"));
  const listLabel = el("span", { className: "ui-field-label" });
  const more = el("button", { type: "button", className: "btn sm", id: "cee-anim-more", hidden: true });
  const strip = field(listLabel, [list, el("div", {}, [more])]);

  // (d) Warte-Schleife
  const loopAtSelect = el("select", { className: "select cee-anim-loop-at", id: "cee-anim-loop-at" });
  loopAtSelect.setAttribute("aria-describedby", "cee-anim-loop-at-help");
  const percent = el("input", { type: "number", id: "cee-anim-loop-percent", min: 1, max: 100, value: LOOP_FROM });
  percent.addEventListener("change", () => update({ list: false }));
  const percentBox = el("div", { className: "ui-input cee-anim-percent" }, [percent, el("span", { className: "ui-input-suffix", textContent: "%" })]);
  const loopMode = field(el("label", { className: "ui-field-label", htmlFor: "cee-anim-loop-percent", textContent: t("splash.anim.loop.percent") }), [percentBox], { id: "cee-anim-loop-mode", hidden: true });
  const loopFrom = () => Math.min(100, Math.max(1, Math.round(Number(percent.value)) || LOOP_FROM));

  // (e) Umwandlung
  const threshold = el("input", { type: "range", className: "ui-range", id: "cee-anim-threshold", min: 1, max: 254, value: 128 });
  const thresholdOut = el("output", { className: "ui-range-value", htmlFor: "cee-anim-threshold", textContent: "128" });
  threshold.addEventListener("input", () => { thresholdOut.textContent = threshold.value; update(); });
  const dither = switchOf("cee-anim-dither", t("splash.dither"));
  const invert = switchOf("cee-anim-invert", t("splash.invert"));
  dither.input.addEventListener("change", () => update());
  invert.input.addEventListener("change", () => update());
  const convert = el("details", { className: "ui-details", id: "cee-anim-convert" }, [
    el("summary", { textContent: t("splash.anim.convert") }),
    el("div", { className: "ui-details-body" }, [
      field(el("label", { className: "ui-field-label", htmlFor: "cee-anim-threshold" }, tNodes("splash.threshold", { value: thresholdOut })), [threshold]),
      dither.node,
      invert.node,
    ]),
  ]);

  // (f) Speichern
  const meter = el("div", { className: "ui-meter", id: "cee-anim-size" });
  const sizeText = el("p", { className: "ui-field-help", id: "cee-anim-size-text" });
  const tooBigText = el("p", { className: "ui-field-error", id: "cee-anim-too-big", hidden: true });
  const thin = el("button", { type: "button", className: "btn sm", id: "cee-anim-thin", textContent: t("splash.anim.thin"), hidden: true });
  thin.setAttribute("aria-describedby", "cee-anim-too-big");
  const size = field(el("span", { className: "ui-field-label", textContent: t("splash.anim.size.label") }), [
    el("div", { className: "cee-anim-meter-row" }, [meter, thin]),
    sizeText,
    tooBigText,
  ]);

  const work = el("div", { className: "cee-anim-work", id: "cee-anim-work", hidden: true }, [
    view,
    strip,
    field(el("label", { className: "ui-field-label", htmlFor: "cee-anim-loop-at", textContent: t("splash.anim.loop.at") }), [
      loopAtSelect,
      el("p", { className: "ui-field-help", id: "cee-anim-loop-at-help", textContent: t("splash.anim.loop.help") }),
    ]),
    loopMode,
    convert,
    size,
  ]);

  const use = el("button", { type: "button", className: "btn cee-primary", id: "cee-anim-use", textContent: t("splash.anim.use"), hidden: true });
  const reset = el("button", { type: "button", className: "btn", id: "cee-anim-reset", textContent: t("splash.anim.reset"), hidden: true });
  // one plain line: what the Patcher takes, whether the changes are saved, and the way to the Patcher
  const stateText = el("span", { id: "cee-anim-state-text" });
  stateText.setAttribute("aria-live", "polite");
  const patcherLink = el("a", { className: "cee-text-link", id: "cee-anim-patcher-link", href: "#patcher", textContent: t("splash.anim.toPatcher") });
  const state = el("p", { className: "ui-field-help", id: "cee-anim-state" }, [stateText, " ", patcherLink]);
  const save = el("div", { className: "cee-anim-save" }, [el("div", { className: "cee-anim-actions" }, [use, reset]), state]);

  /** The pixels of a frame with the page's conversion, the same as the start image's. */
  const options = () => ({ threshold: Number(threshold.value), dither: dither.input.checked, invert: invert.input.checked });
  const key = () => `${threshold.value}|${dither.input.checked}|${invert.input.checked}`;
  const pixelsOfFrame = f => f.pixels ?? (f.cache ??= new Map()).get(key()) ?? f.cache.set(key(), pixelsOf(f.picture, options())).get(key());
  const cut = () => loopAt || frames.length;

  function build() {
    const toFrame = f => pixelsToFrame(pixelsOfFrame(f));
    anim = { progress: frames.slice(0, cut()).map(toFrame), loop: frames.slice(cut()).map(toFrame), loopFrom: 0 };
    anim.loopFrom = anim.loop.length ? loopFrom() : 0;
    loopCache = new Map();
    drawnKey = "";
  }

  /** The slider's fill and value after a value set by code, which fires no input event. */
  const sync = () => (window.ui?.syncRange ? window.ui.syncRange(progress) : (progressOut.textContent = `${progress.value}${progressOut.dataset.unit}`));
  const shownIndex = pct => progressIndex(anim.progress.length, pct >= 100 ? 1000 : pct * 10);
  const playMs = () => Math.max(PLAY_MS, anim.progress.length * FRAME_MS);

  /** Draws what the device shows at the slider's percent: the progress picture, and the loop over it when it plays. */
  function draw(now = performance.now()) {
    if (!anim) return;
    const pct = Number(progress.value);
    const i = shownIndex(pct);
    const loops = anim.loop.length > 0;
    const byPercent = loops && anim.loopFrom > 0 && pct >= anim.loopFrom;
    const active = playing && byPercent;
    if (!active) loopSince = null; else loopSince ??= now;
    let j = pinned;
    if (j === null && active) j = Math.floor((now - loopSince) / LOOP_MS) % anim.loop.length;
    else if (j === null && byPercent) j = 0;
    const drawn = `${i}|${j}`;
    if (drawn !== drawnKey) {
      drawnKey = drawn;
      let pixels;
      if (j === null) pixels = frameToPixels(anim.progress[i]);
      else {
        if (!loopCache.has(drawn)) loopCache.set(drawn, frameToPixels(loopPicture(anim.progress[i], anim.progress[progressIndex(anim.progress.length, 10 * anim.loopFrom)], anim.loop[j])));
        pixels = loopCache.get(drawn);
      }
      paint(canvas, pixels);
      const current = String(j === null ? i : cut() + j);
      for (const b of list.querySelectorAll(".cee-anim-thumb")) {
        if (b.dataset.index === current) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current");
      }
    }
  }

  function tick(now) {
    raf = 0;
    if (!playing) return;
    if (!canvas.isConnected || !(canvas.checkVisibility?.() ?? true)) { pause(); return; }
    const pct = Number(progress.value);
    if (pct < 100) {
      const next = Math.min(100, Math.floor((now - playStart) * 100 / playMs()));
      if (next !== pct) { progress.value = String(next); sync(); }
    } else if (!anim.loop.length) { pause(); return; }
    draw(now);
    raf = requestAnimationFrame(tick);
  }

  function showPlay() {
    play.replaceChildren(icon(playing ? "pause" : "play"));
    play.setAttribute("aria-label", t(playing ? "splash.anim.pause" : "splash.anim.play"));
  }
  function start() {
    if (!anim) return;
    const now = performance.now();
    if (Number(progress.value) >= 100) { progress.value = "0"; sync(); }
    playing = true;
    pinned = null;
    playStart = now - Number(progress.value) * playMs() / 100;
    showPlay();
    raf ||= requestAnimationFrame(tick);
  }
  function pause() {
    playing = false;
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    showPlay();
    draw();
  }
  play.addEventListener("click", () => (playing ? pause() : start()));
  progress.addEventListener("input", () => { pinned = null; pause(); });

  /** Jumps to picture k of the strip: a progress picture by its percent, a loop picture standing over the current one. */
  function jump(k) {
    if (k < cut()) {
      pinned = null;
      const n = anim.progress.length;
      progress.value = String(n > 1 ? Math.ceil(k * 100 / (n - 1)) : 0);
      sync();
    } else pinned = k - cut();
    pause();
  }

  // The strip draws a picture once it scrolls into view, as the gallery does.
  const observer = typeof IntersectionObserver === "function" ? new IntersectionObserver(entries => {
    for (const e of entries) if (e.isIntersecting) { observer.unobserve(e.target); e.target.draw(); }
  }, { rootMargin: "200px" }) : null;

  function drawList() {
    observer?.disconnect();
    const items = [];
    frames.slice(0, shownCount).forEach((f, k) => {
      if (loopAt && k === loopAt) {
        const split = el("li", { className: "cee-anim-split" }, [el("span", { className: "muted", textContent: t("splash.anim.loop.tag") })]);
        split.firstChild.dataset.tone = "info";
        split.setAttribute("aria-hidden", "true");
        items.push(split);
      }
      const thumb = el("canvas", { className: "cee-splash-thumb", width: SPLASH_W, height: SPLASH_H });
      thumb.setAttribute("aria-hidden", "true");
      thumb.draw = () => paint(thumb, pixelsOfFrame(f));
      const loop = loopAt > 0 && k >= loopAt;
      const button = el("button", { type: "button", className: "cee-anim-thumb", title: f.name }, [thumb, el("span", { textContent: String(k + 1) })]);
      button.dataset.index = String(k);
      if (loop) button.dataset.loop = "";
      button.setAttribute("aria-label", t(loop ? "splash.anim.thumb.loop" : "splash.anim.thumb", { n: k + 1, name: f.name }));
      button.addEventListener("click", () => jump(k));
      items.push(el("li", {}, [button]));
      if (observer) observer.observe(thumb); else thumb.draw();
    });
    list.replaceChildren(...items);
    listLabel.textContent = t("splash.anim.frames.count", { n: frames.length });
    const rest = frames.length - shownCount;
    more.hidden = rest <= 0;
    more.textContent = t("splash.anim.more", { n: Math.max(0, rest) });
    drawnKey = "";
  }
  more.addEventListener("click", () => { shownCount += PAGE; drawList(); draw(); });

  function fillLoopAt() {
    loopAtSelect.replaceChildren(
      el("option", { value: "", textContent: t("splash.anim.loop.none") }),
      ...frames.slice(1).map((_, k) => el("option", { value: String(k + 1), textContent: t("splash.anim.frame", { n: k + 2 }) })),
    );
    loopAtSelect.value = loopAt ? String(loopAt) : "";
  }
  loopAtSelect.addEventListener("change", () => { loopAt = Number(loopAtSelect.value) || 0; pinned = null; update({ options: false }); });

  /** Size, buttons, strip and preview after any change; `list: false` when the pictures and the split stay as they are. */
  function update({ list: redraw = true, options: refill = true } = {}) {
    work.hidden = !frames.length;
    if (!frames.length) {
      anim = null;
      dirty = false;
      tooBig = false;
      pause();
      showSave();
      return;
    }
    if (loopAt >= frames.length) loopAt = 0;
    build();
    loopMode.hidden = !anim.loop.length;
    if (redraw) {
      if (refill) fillLoopAt();
      drawList();
    }
    const costs = costPerFrame(anim);
    const bytes = HEADER_BYTES + costs.reduce((s, c) => s + c.bytes, 0);
    tooBig = bytes > MAX_BYTES;
    sizeText.textContent = t("splash.anim.size", { size: kb(bytes), max: MAX_KB });
    window.ui?.setMeter?.(meter, Math.min(100, bytes * 100 / MAX_BYTES), { label: t("splash.anim.size.label"), valueText: sizeText.textContent, tone: tooBig ? "error" : undefined, warnAt: 90 });
    use.setAttribute("aria-describedby", tooBig ? "cee-anim-too-big cee-anim-state" : "cee-anim-state");
    thin.hidden = !tooBig || anim.progress.length < 3;
    tooBigText.hidden = !tooBig;
    if (tooBig) {
      const named = c => frames[c.kind === "progress" ? c.index : cut() + c.index].name;
      const worst = costs.slice(1).sort((a, b) => b.bytes - a.bytes).slice(0, 3).map(c => t("splash.anim.cost", { name: named(c), size: kb(c.bytes) }));
      tooBigText.textContent = t("splash.anim.tooBig", { size: kb(bytes), max: MAX_KB, frames: worst.join(", ") }) + (thin.hidden ? "" : ` ${t("splash.anim.thin.help")}`);
    }
    dirty = tooBig || toBase64(encodeAnimation(anim).bytes) !== readStored();
    showSave();
    draw();
  }

  function showSave() {
    const kept = storedAnimation();
    const inPatcher = kept ? t("splash.anim.state.own", { size: kb(kept.length) }) : t("splash.anim.state.default");
    stateText.textContent = frames.length ? `${inPatcher} ${t(dirty ? "splash.anim.unsaved" : "splash.anim.saved")}` : inPatcher;
    reset.hidden = !kept;
    use.hidden = !frames.length;
    // saving is only offered for something new that fits
    use.disabled = tooBig || !dirty;
  }

  thin.addEventListener("click", () => {
    const progressFrames = frames.slice(0, cut());
    const loopFrames = frames.slice(cut());
    const kept = thinAnimation({ progress: progressFrames, loop: loopFrames }).progress;
    frames = [...kept, ...loopFrames];
    loopAt = loopFrames.length ? kept.length : 0;
    pinned = null;
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
    frames = [];
    loopAt = 0;
    files.textContent = "";
    update();
    toast(t("splash.anim.resetDone"), "ok");
  });

  fileInput.addEventListener("change", async () => {
    const picked = [...(fileInput.files ?? [])].sort(byName);
    fileInput.value = "";
    if (!picked.length) return;
    const next = [];
    loading.hidden = false;
    window.ui?.setProgress?.(loading, 0, t("splash.anim.loading"));
    try {
      for (const [k, file] of picked.entries()) {
        try {
          const bytes = new Uint8Array(await file.arrayBuffer());
          if (String.fromCharCode(...bytes.subarray(0, 3)) === "GIF") {
            const pictures = gifPictures(bytes);
            pictures.forEach((picture, i) => next.push({ name: pictures.length > 1 ? `${baseName(file.name)} ${i + 1}` : baseName(file.name), picture }));
          } else {
            next.push({ name: baseName(file.name), picture: await loadImage(file) });
          }
        } catch {
          toast(t("splash.notImage", { name: file.name }), "error");
          return;
        }
        window.ui?.setProgress?.(loading, (k + 1) * 100 / picked.length, t("splash.anim.loading"));
        await later();
      }
    } finally {
      loading.hidden = true;
    }
    if (!next.length) { toast(t("splash.notImage", { name: picked[0].name }), "error"); return; }
    frames = next;
    loopAt = 0;
    pinned = null;
    shownCount = PAGE;
    files.textContent = picked.length > 3 ? t("splash.anim.files", { n: picked.length, first: picked[0].name, last: picked.at(-1).name }) : picked.map(f => f.name).join(", ");
    progress.value = "0";
    sync();
    pause();
    update();
    if (!reducedMotion()) start();
    work.scrollIntoView?.({ block: "nearest" });
  });

  // the kept animation comes back as it is in the file: its pictures, the split and the loop start
  const kept = storedAnimation();
  if (kept) {
    const stored = decodeAnimation(kept);
    frames = [...stored.progress, ...stored.loop].map((f, i) => ({ name: t("splash.anim.frame", { n: i + 1 }), pixels: frameToPixels(f) }));
    loopAt = stored.loop.length ? stored.progress.length : 0;
    // an older file has 0 there, the loop on a stall: the field shows the default, saved again it is a percent
    if (stored.loopFrom) percent.value = String(stored.loopFrom);
  }
  showPlay();
  showSave();
  // the page builds the section before it is in the document: the first drawing waits for the colours of the display
  queueMicrotask(() => { update(); sync(); });

  return el("section", { className: "ui-section cee-anim", id: "cee-anim" }, [
    el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", id: "cee-anim-title", textContent: t("splash.anim.title") })]),
    el("p", { className: "cee-splash-lead", textContent: t("splash.anim.lead") }),
    drop,
    loading,
    work,
    save,
  ]);
}
