import { icon } from "./icons.mjs";
import { t } from "./i18n.mjs";

const bound = new WeakMap();

/**
 * Round X on the top right corner of an upload field that holds a file: the label gets a positioned wrapper and the
 * button sits beside it (a button in a label is invalid HTML). A click empties the input and the shown name, then calls
 * `onClear` for what the file left pending. Owns data-filled and data-selected of the field. A field with no parent yet
 * comes back wrapped: insert `node` instead of the label.
 */
export function dropzoneClear(input, onClear = () => {}) {
  const zone = input.closest(".ui-dropzone");
  bound.get(input)?.abort();
  const own = new AbortController();
  bound.set(input, own);
  const node = document.createElement("div");
  node.className = "cee-dropzone-wrap";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "cee-dropzone-clear";
  button.setAttribute("aria-label", t("common.removeFile"));
  button.title = t("common.removeFile");
  button.append(icon("x"));
  zone.before(node);
  node.append(zone, button);
  zone.setAttribute("data-selected", "");
  const names = () => zone.querySelector(".ui-dropzone-files");
  // capture: the page's own change handler may empty the input before ui.js looks
  input.addEventListener("change", () => {
    const files = [...(input.files ?? [])].map(f => f.name);
    zone.toggleAttribute("data-filled", files.length > 0);
    if (!files.length) return;
    zone.removeAttribute("data-invalid");
    if (names()) names().textContent = files.join(", ");
  }, { capture: true, signal: own.signal });
  button.addEventListener("click", event => {
    event.preventDefault();
    event.stopPropagation();
    input.value = "";
    zone.removeAttribute("data-filled");
    zone.removeAttribute("data-invalid");
    if (names()) names().textContent = "";
    onClear();
    input.focus({ preventScroll: true });
  });
  return { node, button };
}
