/** The Startbild page: any picture to splash.bmp for the card (SPLASH IMPORT in the BLECH menu). Logic: src/splash-bmp.mjs. */
import { el } from "./fields.mjs";
import { toMono, grayOf, encodeBmp, SPLASH_W, SPLASH_H, SPLASH_FILE, SPLASH_FOLDER } from "../../src/splash-bmp.mjs";

const STYLE = new URL("./splash.css", import.meta.url).href;

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

  const download = el("button", { type: "button", className: "btn btn-primary", id: "cee-splash-download", textContent: `${SPLASH_FILE} herunterladen`, disabled: true });
  download.addEventListener("click", () => {
    if (!pixels) return;
    const url = URL.createObjectURL(new Blob([encodeBmp(pixels)], { type: "image/bmp" }));
    const a = el("a", { href: url, download: SPLASH_FILE });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  root.replaceChildren(el("div", { className: "cee-splash" }, [
    el("h1", { className: "cee-splash-title ui-sr-only", textContent: "Startbildschirm" }),
    el("p", { className: "cee-splash-lead", textContent: "Macht aus einem Bild das Startbild für die Electribe: 128 mal 64 Pixel, schwarz und weiß. Schwarz leuchtet am Gerät dunkel." }),
    drop,
    el("div", { className: "cee-splash-work", hidden: true, id: "cee-splash-work" }, [
      canvas,
      el("div", { className: "cee-splash-controls" }, [
        el("div", { className: "ui-field" }, [el("span", { className: "ui-field-label", textContent: "Ausschnitt" }), fit]),
        el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: "cee-splash-threshold" }, ["Schwelle ", thresholdOut]), threshold]),
        dither.node,
        invert.node,
        download,
      ]),
    ]),
    el("ol", { className: "cee-splash-steps", id: "cee-splash-steps" }, [
      el("li", {}, ["Lege ", el("code", { textContent: SPLASH_FILE }), " auf der Karte nach ", el("code", { textContent: SPLASH_FOLDER }), "."]),
      el("li", { textContent: "Am Gerät im Menü BLECH: CUSTOMIZATION, SPLASH IMPORT, ENTER." }),
      el("li", { textContent: "Ab dem nächsten Start ist es zu sehen. Ändern lässt es sich unter SPLASH DRAW." }),
    ]),
  ]));

  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      picture = img;
      files.textContent = file.name;
      document.getElementById("cee-splash-work").hidden = false;
      download.disabled = false;
      render();
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
    const work = document.createElement("canvas");
    work.width = SPLASH_W;
    work.height = SPLASH_H;
    const g = work.getContext("2d");
    g.fillStyle = "#fff";
    g.fillRect(0, 0, SPLASH_W, SPLASH_H);
    const cover = fits.find(f => f.input.checked)?.input.value === "cover";
    const scale = (cover ? Math.max : Math.min)(SPLASH_W / picture.width, SPLASH_H / picture.height);
    const w = picture.width * scale;
    const h = picture.height * scale;
    g.drawImage(picture, (SPLASH_W - w) / 2, (SPLASH_H - h) / 2, w, h);
    pixels = toMono(grayOf(g.getImageData(0, 0, SPLASH_W, SPLASH_H).data), {
      threshold: Number(threshold.value), dither: dither.input.checked, invert: invert.input.checked,
    });
    const style = getComputedStyle(canvas);
    const ink = style.getPropertyValue("--cee-splash-ink").trim() || "black";
    const paper = style.getPropertyValue("--cee-splash-paper").trim() || "white";
    const c = canvas.getContext("2d");
    c.fillStyle = paper;
    c.fillRect(0, 0, SPLASH_W, SPLASH_H);
    c.fillStyle = ink;
    for (let i = 0; i < pixels.length; i++) {
      if (pixels[i]) c.fillRect(i % SPLASH_W, Math.floor(i / SPLASH_W), 1, 1);
    }
  }
}
