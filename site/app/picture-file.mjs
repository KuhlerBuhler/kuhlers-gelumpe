/**
 * The Bilder tab of the Design page: several pictures (BMP, PNG, JPG, what the browser reads) into one GIFnn.E2G for the
 * plugins Image Viewer and GIF Player, one frame per picture in name order. Logic: src/script/gif.mjs.
 */
import { el } from "./fields.mjs";
import { saveFile } from "./save-file.mjs";
import { toastFor } from "./toast.mjs";
import { t, tNodes } from "./i18n.mjs";
import { icon } from "./icons.mjs";
import { SPLASH_W, SPLASH_H } from "../../src/splash-bmp.mjs";
import { packGif, frameOfPixels } from "../../src/script/gif.mjs";
import { SCRIPT_GIF } from "../../data/script/contract.mjs";
import { pixelsOf, paint, switchOf } from "./splash.mjs";

const toast = toastFor("h:splash");
/** How long the GIF Player shows each picture of such a file; the Image Viewer pages by hand. */
const DELAY_MS = 1000;
const fileName = n => `GIF${String(n).padStart(2, "0")}.E2G`;

const readPicture = file => new Promise(resolve => {
  const url = URL.createObjectURL(file);
  const img = new Image();
  img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
  img.onerror = () => { URL.revokeObjectURL(url); resolve(null); };
  img.src = url;
});

export function pictureFileSection() {
  let pictures = [];   // { name, picture }

  const fileInput = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-pics-file", accept: "image/*,.bmp", multiple: true });
  const files = el("span", { className: "ui-dropzone-files" });
  const drop = el("label", { className: "ui-dropzone" }, [
    fileInput,
    icon("image"),
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: t("pics.drop.drag") }), t("common.pick")]),
    el("span", { className: "ui-dropzone-hint", textContent: t("pics.drop.hint") }),
    files,
  ]);

  const list = el("ol", { className: "cee-splash-gallery", id: "cee-pics-list" });
  const dither = switchOf("cee-pics-dither", t("splash.dither"));
  const invert = switchOf("cee-pics-invert", t("splash.invert"));
  const number = el("input", { type: "number", id: "cee-pics-number", min: 0, max: SCRIPT_GIF.maxFile, value: 0 });
  number.setAttribute("aria-describedby", "cee-pics-number-help");
  const download = el("button", { type: "button", className: "btn cee-primary", id: "cee-pics-download", disabled: true });
  const work = el("div", { className: "cee-splash-controls", id: "cee-pics-work", hidden: true }, [
    dither.node,
    invert.node,
    el("div", { className: "ui-field" }, [
      el("label", { className: "ui-field-label", htmlFor: "cee-pics-number", textContent: t("pics.number") }),
      el("div", { className: "ui-input" }, [number]),
      el("p", { className: "ui-field-help", id: "cee-pics-number-help", textContent: t("pics.number.help") }),
    ]),
    el("div", { className: "actions" }, [download]),
  ]);

  const nr = () => Math.min(SCRIPT_GIF.maxFile, Math.max(0, Math.round(Number(number.value)) || 0));
  const options = () => ({ dither: dither.input.checked, invert: invert.input.checked });

  function render() {
    download.textContent = t("common.download", { file: fileName(nr()) });
    download.disabled = !pictures.length;
    work.hidden = !pictures.length;
    list.replaceChildren(...pictures.map((p, i) => {
      const canvas = el("canvas", { className: "cee-splash-thumb", width: SPLASH_W, height: SPLASH_H });
      canvas.setAttribute("role", "img");
      canvas.setAttribute("aria-label", t("splash.thumb", { title: p.name }));
      const remove = el("button", { type: "button", className: "btn sm", textContent: t("common.remove") });
      remove.setAttribute("aria-label", `${t("common.remove")}: ${p.name}`);
      remove.addEventListener("click", () => { pictures.splice(i, 1); render(); });
      const li = el("li", { className: "cee-splash-item" }, [
        canvas,
        el("p", { className: "cee-splash-item-title" }, [el("strong", { textContent: `${i + 1}. ${p.name}` })]),
        el("div", { className: "actions" }, [remove]),
      ]);
      paint(canvas, pixelsOf(p.picture, options()));
      return li;
    }));
  }

  fileInput.addEventListener("change", async () => {
    const chosen = [...(fileInput.files ?? [])].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
    fileInput.value = "";
    for (const file of chosen) {
      const picture = await readPicture(file);
      if (picture) pictures.push({ name: file.name.replace(/\.[^.]+$/, ""), picture });
      else toast(t("splash.notImage", { name: file.name }), "error");
    }
    files.textContent = pictures.map(p => p.name).join(", ");
    render();
  });
  for (const input of [dither.input, invert.input]) input.addEventListener("change", render);
  number.addEventListener("input", render);
  download.addEventListener("click", () => {
    if (!pictures.length) return;
    const file = packGif(pictures.map(p => ({ delay: DELAY_MS, bytes: frameOfPixels(pixelsOf(p.picture, options())) })));
    saveFile(file, fileName(nr()), { type: "application/octet-stream" });
  });
  render();

  return el("section", { className: "ui-section", id: "cee-pics-section" }, [
    el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: t("pics.title") })]),
    el("p", { className: "cee-splash-lead", textContent: t("pics.lead") }),
    drop,
    list,
    work,
    el("ol", { className: "cee-splash-steps", id: "cee-pics-steps" }, [
      el("li", {}, tNodes("pics.step.copy", { folder: el("code", { textContent: SCRIPT_GIF.folder }) })),
      el("li", { textContent: t("pics.step.open") }),
    ]),
  ]);
}
