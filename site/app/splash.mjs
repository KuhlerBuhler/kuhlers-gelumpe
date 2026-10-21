/** The Startbild page: any picture to splash.bmp for the card (SPLASH IMPORT in the BLECH menu). Logic: src/splash-bmp.mjs. */
import { el } from "./fields.mjs";
import { toMono, grayOf, encodeBmp, SPLASH_W, SPLASH_H, SPLASH_FILE, SPLASH_FOLDER } from "../../src/splash-bmp.mjs";

const STYLE = new URL("./splash.css", import.meta.url).href;

/** The pictures that come with the app; the first is the one BLECHTRIBE brings, to get it back after SPLASH RESET. */
export const GALLERY = [
  { id: "blechtribe", title: "BLECHTRIBE", note: "Standard", src: "img/splash/blechtribe.png" },
  { id: "blech", title: "BLECH", src: "img/splash/blech.png" },
  { id: "blechy", title: "Blechy", src: "img/splash/blechy.png" },
  { id: "blechy-winkt", title: "Blechy winkt", src: "img/splash/blechy-winkt.png" },
];
const OWN = "cee.splash.own";

/** 0/1 per pixel to base64 of 1024 bytes and back: how an own picture is kept in this browser. */
export const packBits = pixels => btoa(String.fromCharCode(...Array.from({ length: pixels.length / 8 }, (_, i) => pixels.slice(i * 8, i * 8 + 8).reduce((b, p, k) => b | (p ? 0x80 >> k : 0), 0))));
export const unpackBits = text => Uint8Array.from({ length: SPLASH_W * SPLASH_H }, (_, i) => (atob(text).charCodeAt(i >> 3) >> (7 - (i & 7))) & 1);

const readOwn = () => { try { return JSON.parse(localStorage.getItem(OWN) ?? "[]"); } catch { return []; } };
const writeOwn = list => { try { localStorage.setItem(OWN, JSON.stringify(list)); return true; } catch { return false; } };

function saveBmp(pixels, name = SPLASH_FILE) {
  const url = URL.createObjectURL(new Blob([encodeBmp(pixels)], { type: "image/bmp" }));
  const a = el("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** A picture drawn to 128 x 64 and cut to one bit, the way the page and the device see it. */
function pixelsOf(picture, { cover = false, threshold = 128, dither = false, invert = false } = {}) {
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
function paint(canvas, pixels) {
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
  img.onerror = () => reject(new Error(`${src} ließ sich nicht laden.`));
  img.src = src;
});

function switchOf(id, text) {
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
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: "Bild hierher ziehen oder " }), "auswählen"]),
    el("span", { className: "ui-dropzone-hint", textContent: "PNG, JPG, GIF oder WebP" }),
    files,
  ]);

  const canvas = el("canvas", { className: "cee-splash-preview", id: "cee-splash-preview", width: SPLASH_W, height: SPLASH_H });
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", "Vorschau des Startbilds, 128 mal 64 Pixel");

  const fitName = "cee-splash-fit";
  const fits = [["contain", "Einpassen"], ["cover", "Füllen"]].map(([value, text], i) => {
    const input = el("input", { type: "radio", name: fitName, value, checked: i === 0 });
    input.addEventListener("change", render);
    return { input, node: el("label", { className: "ui-segmented-option" }, [input, el("span", { textContent: text })]) };
  });
  const fit = el("div", { className: "ui-segmented", id: "cee-splash-fit" }, fits.map(f => f.node));
  fit.setAttribute("role", "radiogroup");
  fit.setAttribute("aria-label", "Ausschnitt");

  const threshold = el("input", { type: "range", className: "ui-range", id: "cee-splash-threshold", min: 1, max: 254, value: 128 });
  const thresholdOut = el("output", { className: "ui-range-value", htmlFor: "cee-splash-threshold", textContent: "128" });
  threshold.addEventListener("input", render);
  const dither = switchOf("cee-splash-dither", "Rastern");
  const invert = switchOf("cee-splash-invert", "Umkehren");
  dither.input.addEventListener("change", render);
  invert.input.addEventListener("change", render);

  const download = el("button", { type: "button", className: "btn cee-primary", id: "cee-splash-download", textContent: `${SPLASH_FILE} herunterladen`, disabled: true });
  download.addEventListener("click", () => { if (pixels) saveBmp(pixels); });
  const keep = el("button", { type: "button", className: "btn", id: "cee-splash-keep", textContent: "In der Galerie speichern", disabled: true });
  let pictureName = "";
  keep.addEventListener("click", () => {
    if (!pixels) return;
    const list = readOwn();
    list.push({ id: `own-${Date.now()}`, title: pictureName || "Eigenes Bild", bits: packBits(pixels) });
    if (!writeOwn(list)) { files.textContent = "Dieser Browser lässt die Seite nichts speichern."; return; }
    drawGallery();
    document.getElementById("cee-splash-gallery").lastElementChild?.scrollIntoView?.({ block: "nearest" });
  });

  // The gallery: the pictures of the app and the own ones of this browser. A picture is drawn once it scrolls into view.
  const gallery = el("ul", { className: "cee-splash-gallery", id: "cee-splash-gallery" });
  const later = typeof IntersectionObserver === "function" ? new IntersectionObserver(entries => {
    for (const e of entries) if (e.isIntersecting) { later.unobserve(e.target); e.target.draw(); }
  }, { rootMargin: "200px" }) : null;
  function card(item, own) {
    const canvas = el("canvas", { className: "cee-splash-thumb", width: SPLASH_W, height: SPLASH_H });
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", `Startbild ${item.title}`);
    let bits = own ? unpackBits(item.bits) : null;
    const ready = async () => bits ??= pixelsOf(await loadImage(item.src));
    canvas.draw = () => ready().then(p => paint(canvas, p)).catch(() => {});
    const get = el("button", { type: "button", className: "btn sm", textContent: SPLASH_FILE });
    get.setAttribute("aria-label", `${item.title} als ${SPLASH_FILE} herunterladen`);
    get.addEventListener("click", async () => saveBmp(await ready()));
    const edit = el("button", { type: "button", className: "btn sm", textContent: "Bearbeiten" });
    edit.addEventListener("click", async () => {
      const p = await ready();
      const c = el("canvas", { width: SPLASH_W, height: SPLASH_H });
      const g = c.getContext("2d");
      const img = g.createImageData(SPLASH_W, SPLASH_H);
      p.forEach((v, i) => img.data.set(v ? [0, 0, 0, 255] : [255, 255, 255, 255], i * 4));
      g.putImageData(img, 0, 0);
      open(c, item.title);
    });
    const actions = [get, edit];
    if (own) {
      const remove = el("button", { type: "button", className: "btn sm", textContent: "Entfernen" });
      remove.addEventListener("click", () => { writeOwn(readOwn().filter(o => o.id !== item.id)); drawGallery(); });
      actions.push(remove);
    }
    const li = el("li", { className: "cee-splash-item", id: `cee-splash-item-${item.id}` }, [
      canvas,
      el("p", { className: "cee-splash-item-title" }, [el("strong", { textContent: item.title }), item.note ? el("span", { className: "muted", textContent: ` ${item.note}` }) : own ? el("span", { className: "muted", textContent: " Eigenes" }) : null]),
      el("div", { className: "actions" }, actions),
    ]);
    if (later) later.observe(canvas); else canvas.draw();
    return li;
  }
  function drawGallery() {
    gallery.replaceChildren(...GALLERY.map(item => card(item, false)), ...readOwn().map(item => card(item, true)));
  }

  root.replaceChildren(el("div", { className: "cee-splash" }, [
    el("h1", { className: "cee-splash-title ui-sr-only", textContent: "Startbildschirm" }),
    el("p", { className: "cee-splash-lead", textContent: "Macht aus einem Bild das Startbild für die Electribe: 128 mal 64 Pixel, schwarz und weiß. Schwarz leuchtet am Gerät dunkel." }),
    el("h2", { className: "cee-splash-head", textContent: "Galerie" }),
    gallery,
    el("h2", { className: "cee-splash-head", textContent: "Eigenes Bild" }),
    drop,
    el("div", { className: "cee-splash-work", hidden: true, id: "cee-splash-work" }, [
      canvas,
      el("div", { className: "cee-splash-controls" }, [
        el("div", { className: "ui-field" }, [el("span", { className: "ui-field-label", textContent: "Ausschnitt" }), fit]),
        el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: "cee-splash-threshold" }, ["Schwelle ", thresholdOut]), threshold]),
        dither.node,
        invert.node,
        el("div", { className: "actions" }, [download, keep]),
      ]),
    ]),
    el("ol", { className: "cee-splash-steps", id: "cee-splash-steps" }, [
      el("li", {}, ["Lege ", el("code", { textContent: SPLASH_FILE }), " auf der Karte nach ", el("code", { textContent: SPLASH_FOLDER }), "."]),
      el("li", { textContent: "Am Gerät im Menü BLECH: CUSTOMIZATION, SPLASH IMPORT, ENTER." }),
      el("li", { textContent: "Ab dem nächsten Start ist es zu sehen. Ändern lässt es sich unter SPLASH DRAW." }),
    ]),
  ]));

  /** Puts a picture into the editor: a dropped file or one of the gallery. */
  function open(img, name) {
    picture = img;
    pictureName = name;
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
      files.textContent = `${file.name} ist kein Bild, das der Browser lesen kann.`;
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
