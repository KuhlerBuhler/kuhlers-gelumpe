/** The Startbild page: any picture to splash.bmp for the card (SPLASH IMPORT in the BLECH menu). Logic: src/splash-bmp.mjs. */
import { el } from "./fields.mjs";
import { saveFile } from "./save-file.mjs";
import { toastFor } from "./toast.mjs";
import { toMono, grayOf, encodeBmp, SPLASH_W, SPLASH_H, SPLASH_FILE, SPLASH_FOLDER } from "../../src/splash-bmp.mjs";
import { t, tNodes } from "./i18n.mjs";
import { loadingAnimSection } from "./loading-anim.mjs";
import { pictureFileSection } from "./picture-file.mjs";
import { icon } from "./icons.mjs";
import { dropzoneClear } from "./dropzone-clear.mjs";
import { creatorLine, creatorName } from "./creator.mjs";
/** An error of this page opens Blechy at its topic (data/rescue.mjs). */
const toast = toastFor("h:splash");

const STYLE = new URL("./splash.css", import.meta.url).href;

const KUHLER = "Kuhler Buhler";
/** The pictures that come with the app; the first is the one BLECHTRIBE brings, to get it back after SPLASH RESET.
 * The ones after "bars" come from the #splash-screens channel on Discord, with their creator's name there. */
export const GALLERY = [
  { id: "blechtribe", title: "BLECHTRIBE", note: "splash.gallery.default", creator: KUHLER, src: "img/splash/blechtribe.png" },
  { id: "blech", title: "BLECH", creator: KUHLER, src: "img/splash/blech.png" },
  { id: "blechy", title: "Blechy", creator: KUHLER, src: "img/splash/blechy.png" },
  { id: "blechy-winkt", get title() { return t("splash.gallery.wave"); }, creator: KUHLER, src: "img/splash/blechy-winkt.png" },
  { id: "kuhler", title: "KUHLER", creator: KUHLER, src: "img/splash/kuhler.png" },
  { id: "pads", get title() { return t("splash.gallery.pads"); }, creator: KUHLER, src: "img/splash/pads.png" },
  { id: "wave", get title() { return t("splash.gallery.waveform"); }, creator: KUHLER, src: "img/splash/wave.png" },
  { id: "bars", get title() { return t("splash.gallery.bars"); }, creator: KUHLER, src: "img/splash/bars.png" },
  { id: "psytrance", title: "Psytrance", creator: "Crank", src: "img/splash/psytrance.png" },
  { id: "psychosis", title: "Psychosis", creator: "Crank", src: "img/splash/psychosis.png" },
  { id: "watch-dogs", title: "Watch Dogs", creator: "Crank", src: "img/splash/watch-dogs.png" },
  { id: "muss-blechen", title: "MUSS BLECHEN", creator: "Acey", src: "img/splash/muss-blechen.png" },
  { id: "hardtekk", title: "HARDTEKK", creator: "Acey", src: "img/splash/hardtekk.png" },
  { id: "old-electribe", title: "ELECTRIBE", creator: "luzis", src: "img/splash/old-electribe.png" },
  { id: "emx-esx-blechtribe", title: "blechtribe EMX/ESX", creator: "Josie", src: "img/splash/emx-esx-blechtribe.png" },
  { id: "rules-for-terror", title: "Rules for Terror", creator: "VenganceTerror", src: "img/splash/rules-for-terror.png" },
];
const OWN = "cee.splash.own";

/** 0/1 per pixel to base64 of 1024 bytes and back: how an own picture is kept in this browser. */
export const packBits = pixels => btoa(String.fromCharCode(...Array.from({ length: pixels.length / 8 }, (_, i) => pixels.slice(i * 8, i * 8 + 8).reduce((b, p, k) => b | (p ? 0x80 >> k : 0), 0))));
export const unpackBits = text => Uint8Array.from({ length: SPLASH_W * SPLASH_H }, (_, i) => (atob(text).charCodeAt(i >> 3) >> (7 - (i & 7))) & 1);

const readOwn = () => { try { return JSON.parse(localStorage.getItem(OWN) ?? "[]"); } catch { return []; } };
const writeOwn = list => { try { localStorage.setItem(OWN, JSON.stringify(list)); return true; } catch { return false; } };

function saveBmp(pixels, name = SPLASH_FILE) {
  saveFile(encodeBmp(pixels), name, { type: "image/bmp" });
}

/** A picture drawn to 128 x 64 and cut to one bit, the way the page and the device see it. */
export function pixelsOf(picture, { cover = false, threshold = 128, dither = false, invert = false } = {}) {
  const work = document.createElement("canvas");
  work.width = SPLASH_W;
  work.height = SPLASH_H;
  const g = work.getContext("2d");
  g.fillStyle = "#fff"; // raw-ok: the paper behind the picture before it is cut to one bit
  g.fillRect(0, 0, SPLASH_W, SPLASH_H);
  const scale = (cover ? Math.max : Math.min)(SPLASH_W / picture.width, SPLASH_H / picture.height);
  const w = picture.width * scale;
  const h = picture.height * scale;
  g.drawImage(picture, (SPLASH_W - w) / 2, (SPLASH_H - h) / 2, w, h);
  return toMono(grayOf(g.getImageData(0, 0, SPLASH_W, SPLASH_H).data), { threshold, dither, invert });
}

/** Draws 0/1 pixels in the colours of the emulator's display. */
export function paint(canvas, pixels) {
  const style = getComputedStyle(canvas);
  const c = canvas.getContext("2d");
  c.fillStyle = style.getPropertyValue("--cee-splash-paper").trim() || "white";
  c.fillRect(0, 0, SPLASH_W, SPLASH_H);
  c.fillStyle = style.getPropertyValue("--cee-splash-ink").trim() || "black";
  for (let i = 0; i < pixels.length; i++) if (pixels[i]) c.fillRect(i % SPLASH_W, Math.floor(i / SPLASH_W), 1, 1);
}

const loadImage = src => new Promise((resolve, reject) => {
  const img = new Image();
  img.onload = () => resolve(img);
  img.onerror = () => reject(new Error(t("splash.loadFailed", { src })));
  img.src = src;
});

export function switchOf(id, text) {
  const input = el("input", { type: "checkbox", role: "switch", id });
  return { input, node: el("label", { className: "ui-switch" }, [input, el("span", { className: "ui-switch-track", ariaHidden: "true" }), text]) };
}

export function splashPage(root) {
  if (!document.querySelector("link[data-cee-splash]")) {
    const css = el("link", { rel: "stylesheet", href: STYLE });
    css.setAttribute("data-cee-splash", "");
    document.head.append(css);
  }
  let picture = null;
  let pixels = null;

  const fileInput = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-splash-file", accept: "image/*" });
  const files = el("span", { className: "ui-dropzone-files" });
  const drop = el("label", { className: "ui-dropzone" }, [
    fileInput,
    icon("image"),
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: t("splash.drop.drag") }), t("common.pick")]),
    el("span", { className: "ui-dropzone-hint", textContent: t("splash.drop.hint") }),
    files,
  ]);

  const canvas = el("canvas", { className: "cee-splash-preview", id: "cee-splash-preview", width: SPLASH_W, height: SPLASH_H });
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", t("splash.preview"));

  const fitName = "cee-splash-fit";
  const fits = [["contain", t("splash.fit.contain")], ["cover", t("splash.fit.cover")]].map(([value, text], i) => {
    const input = el("input", { type: "radio", name: fitName, value, checked: i === 0 });
    input.addEventListener("change", render);
    return { input, node: el("label", { className: "ui-segmented-option" }, [input, el("span", { textContent: text })]) };
  });
  const fit = el("div", { className: "ui-segmented", id: "cee-splash-fit" }, fits.map(f => f.node));
  fit.setAttribute("role", "radiogroup");
  fit.setAttribute("aria-label", t("splash.fit"));

  const threshold = el("input", { type: "range", className: "ui-range", id: "cee-splash-threshold", min: 1, max: 254, value: 128 });
  const thresholdOut = el("output", { className: "ui-range-value", htmlFor: "cee-splash-threshold", textContent: "128" });
  threshold.addEventListener("input", render);
  const dither = switchOf("cee-splash-dither", t("splash.dither"));
  const invert = switchOf("cee-splash-invert", t("splash.invert"));
  dither.input.addEventListener("change", render);
  invert.input.addEventListener("change", render);

  const download = el("button", { type: "button", className: "btn cee-primary", id: "cee-splash-download", textContent: t("common.download", { file: SPLASH_FILE }), disabled: true });
  download.addEventListener("click", () => { if (pixels) saveBmp(pixels); });
  const keep = el("button", { type: "button", className: "btn", id: "cee-splash-keep", textContent: t("splash.keep"), disabled: true });
  let pictureName = "";
  keep.addEventListener("click", () => {
    if (!pixels) return;
    const list = readOwn();
    list.push({ id: `own-${Date.now()}`, title: pictureName || t("splash.ownPicture"), bits: packBits(pixels) });
    if (!writeOwn(list)) { toast(t("splash.noStorage"), "error"); return; }
    drawGallery();
    show("gallery");
    document.getElementById("cee-splash-gallery").lastElementChild?.scrollIntoView?.({ block: "nearest" });
  });

  // The gallery: the pictures of the app and the own ones of this browser. A picture is drawn once it scrolls into view.
  const gallery = el("ul", { className: "cee-catalog cee-splash-gallery", id: "cee-splash-gallery" });
  const later = typeof IntersectionObserver === "function" ? new IntersectionObserver(entries => {
    for (const e of entries) if (e.isIntersecting) { later.unobserve(e.target); e.target.draw(); }
  }, { rootMargin: "200px" }) : null;
  /** Pixels of a picture and a canvas that draws them: the gallery card and the picture's own page share it. */
  const bitsOf = new Map();
  const ready = async item => { if (!bitsOf.has(item.id)) bitsOf.set(item.id, item.bits ? unpackBits(item.bits) : pixelsOf(await loadImage(item.src))); return bitsOf.get(item.id); };
  function thumb(item) {
    const c = el("canvas", { className: "cee-splash-thumb", width: SPLASH_W, height: SPLASH_H });
    c.setAttribute("role", "img");
    c.setAttribute("aria-label", t("splash.thumb", { title: item.title }));
    c.draw = () => ready(item).then(p => paint(c, p)).catch(() => {});
    return c;
  }
  const tagOf = (item, own) => (item.note ? t(item.note) : own ? t("splash.ownTag") : null);
  /** A card like the plugin catalog's (scripts.mjs catalogCard): the whole card opens the picture's page. */
  function card(item, own) {
    const canvas = thumb(item);
    const tag = tagOf(item, own);
    const li = el("li", { className: "cee-catalog-card cee-splash-item", id: `cee-splash-item-${item.id}` }, [
      canvas,
      el("h3", {}, el("button", { type: "button", className: "cee-catalog-open", textContent: item.title, onclick: () => openDetail(item, own) })),
      tag ? el("p", { className: "cee-catalog-category", textContent: tag }) : null,
      creatorLine(item.creator),
    ]);
    if (later) later.observe(canvas); else canvas.draw();
    return li;
  }
  function drawGallery() {
    gallery.replaceChildren(...GALLERY.map(item => card(item, false)), ...readOwn().map(item => card(item, true)));
  }

  // Three tabs, each its own section: the start image for the card, the loading animation for the Patcher, and pictures for the Image Viewer.
  const tabs = el("div", { className: "ui-tabs", id: "cee-design-tabs" });
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", t("nav.splash"));
  const panels = [["splash", t("splash.title")], ["anim", t("splash.anim.title")], ["pics", t("pics.title")]].map(([id, text], i) => {
    const tab = el("button", { type: "button", className: "ui-tab", id: `cee-design-tab-${id}`, textContent: text });
    tab.setAttribute("role", "tab");
    tab.dataset.tab = id;
    tab.setAttribute("aria-controls", `cee-design-panel-${id}`);
    tab.setAttribute("aria-selected", String(i === 0));
    if (i) tab.tabIndex = -1;
    tabs.append(tab);
    const panel = el("div", { className: "ui-tabpanel", id: `cee-design-panel-${id}`, tabIndex: 0, hidden: i > 0 });
    panel.setAttribute("role", "tabpanel");
    panel.setAttribute("aria-labelledby", tab.id);
    return panel;
  });

  const dropZone = dropzoneClear(fileInput, () => {
    picture = null;
    pictureName = "";
    document.getElementById("cee-splash-work").hidden = true;
    download.disabled = true;
    keep.disabled = true;
    render();
  }).node;
  // The Startbild tab has three pages: the gallery, one picture's page, and the editor that turns any picture into one.
  const back = id => el("button", { type: "button", className: "cee-text-link cee-detail-back", id, textContent: t("splash.back"), onclick: () => show("gallery") });
  const makeOwn = el("button", { type: "button", className: "btn", id: "cee-splash-make", textContent: t("splash.make"), onclick: () => show("editor") });
  const steps = () => el("ol", { className: "cee-splash-steps" }, [
    el("li", {}, tNodes("splash.step.copy", { file: el("code", { textContent: SPLASH_FILE }), folder: el("code", { textContent: SPLASH_FOLDER }) })),
    el("li", { textContent: t("splash.step.import") }),
    el("li", { textContent: t("splash.step.see") }),
  ]);
  const galleryPage = el("div", { className: "cee-splash-page", id: "cee-splash-page-gallery" }, [
    el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: t("splash.title") }), makeOwn]),
    el("p", { className: "cee-splash-lead", textContent: t("splash.lead") }),
    gallery,
    el("h3", { className: "cee-splash-head", textContent: t("splash.howto") }),
    Object.assign(steps(), { id: "cee-splash-steps" }),
  ]);
  const detailHead = el("div", { className: "cee-detail-head", id: "cee-splash-detail-head" });
  const detailPage = el("div", { className: "cee-splash-page cee-detail", id: "cee-splash-page-detail", hidden: true }, [back("cee-splash-detail-back"), detailHead]);
  const editorTitle = el("h2", { className: "ui-section-title", id: "cee-splash-editor-title", textContent: t("splash.ownPicture") });
  const editorPage = el("div", { className: "cee-splash-page", id: "cee-splash-page-editor", hidden: true }, [
    back("cee-splash-editor-back"),
    el("div", { className: "ui-section-head" }, [editorTitle]),
    dropZone,
    el("div", { className: "cee-splash-work", hidden: true, id: "cee-splash-work" }, [
      canvas,
      el("div", { className: "cee-splash-controls" }, [
        el("div", { className: "ui-field" }, [el("span", { className: "ui-field-label", textContent: t("splash.fit") }), fit]),
        el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: "cee-splash-threshold" }, tNodes("splash.threshold", { value: thresholdOut })), threshold]),
        dither.node,
        invert.node,
        el("div", { className: "actions" }, [download, keep]),
      ]),
    ]),
    steps(),
  ]);
  const PAGES = { gallery: galleryPage, detail: detailPage, editor: editorPage };
  function show(id) {
    for (const [k, node] of Object.entries(PAGES)) node.hidden = k !== id;
    PAGES[id].scrollIntoView?.({ block: "nearest" });
  }
  /** One picture's page: big, with its creator, download and Bearbeiten, and Entfernen for an own one. */
  function openDetail(item, own) {
    const big = thumb(item);
    big.classList.add("cee-splash-big");
    const get = el("button", { type: "button", className: "btn cee-primary", id: "cee-splash-detail-download", textContent: t("common.download", { file: SPLASH_FILE }) });
    get.addEventListener("click", async () => saveBmp(await ready(item)));
    const edit = el("button", { type: "button", className: "btn", id: "cee-splash-detail-edit", textContent: t("common.edit") });
    edit.addEventListener("click", async () => {
      const p = await ready(item);
      const c = el("canvas", { width: SPLASH_W, height: SPLASH_H });
      const g = c.getContext("2d");
      const img = g.createImageData(SPLASH_W, SPLASH_H);
      p.forEach((v, i) => img.data.set(v ? [0, 0, 0, 255] : [255, 255, 255, 255], i * 4));
      g.putImageData(img, 0, 0);
      open(c, item.title);
    });
    const actions = [get, edit];
    if (own) {
      const remove = el("button", { type: "button", className: "btn", id: "cee-splash-detail-remove", textContent: t("common.remove") });
      remove.addEventListener("click", () => { writeOwn(readOwn().filter(o => o.id !== item.id)); bitsOf.delete(item.id); drawGallery(); show("gallery"); });
      actions.push(remove);
    }
    const tag = tagOf(item, own);
    detailHead.replaceChildren(big, el("div", { className: "cee-detail-text" }, [
      el("h2", { className: "cee-detail-title", id: "cee-splash-detail-title", textContent: item.title }),
      el("dl", { className: "cee-detail-facts" }, [
        el("dt", { textContent: t("plugins.by") }), el("dd", {}, creatorName(item.creator) ?? (own ? t("splash.ownTag") : "?")),
        ...(tag && !own ? [el("dt", { textContent: t("splash.fact.kind") }), el("dd", { textContent: tag })] : []),
        el("dt", { textContent: t("splash.fact.size") }), el("dd", { textContent: t("splash.fact.sizeValue", { file: SPLASH_FILE }) }),
      ]),
      el("div", { className: "actions" }, actions),
    ]));
    big.draw();
    show("detail");
  }
  panels[0].append(el("section", { className: "ui-section", id: "cee-splash-section" }, [galleryPage, detailPage, editorPage]));
  panels[1].append(loadingAnimSection());
  panels[2].append(pictureFileSection());
  root.replaceChildren(el("h1", { className: "ui-sr-only", textContent: t("nav.splash") }), tabs, ...panels);
  window.ui?.tabs?.(tabs, { persist: "cee.design.tab", hash: false });

  /** Puts a picture into the editor: a dropped file or one of the gallery. */
  function open(img, name) {
    picture = img;
    pictureName = name;
    editorTitle.textContent = name;
    show("editor");
    files.textContent = name;
    document.getElementById("cee-splash-work").hidden = false;
    download.disabled = false;
    keep.disabled = false;
    render();
    document.getElementById("cee-splash-work").scrollIntoView?.({ block: "nearest" });
  }
  drawGallery();

  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      open(img, file.name.replace(/\.[^.]+$/, ""));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      toast(t("splash.notImage", { name: file.name }), "error");
    };
    img.src = url;
  });

  function render() {
    thresholdOut.textContent = threshold.value;
    if (!picture) return;
    pixels = pixelsOf(picture, {
      cover: fits.find(f => f.input.checked)?.input.value === "cover",
      threshold: Number(threshold.value), dither: dither.input.checked, invert: invert.input.checked,
    });
    paint(canvas, pixels);
  }
}
