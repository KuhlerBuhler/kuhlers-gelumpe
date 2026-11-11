import { icon } from "./icons.mjs";
import { t } from "./i18n.mjs";

/** Round X on the corner of an upload field carrying data-filled; a click empties the input and calls `onClear`. Sits in the label so a click never opens the picker. */
export function dropzoneClear(input, onClear) {
  const zone = input.closest(".ui-dropzone");
  const button = document.createElement("button");
  button.type = "button";
  button.className = "cee-dropzone-clear";
  button.setAttribute("aria-label", t("common.removeFile"));
  button.title = t("common.removeFile");
  button.append(icon("x"));
  button.addEventListener("click", event => {
    event.preventDefault();
    event.stopPropagation();
    input.value = "";
    zone.removeAttribute("data-filled");
    onClear();
    input.focus({ preventScroll: true });
  });
  zone.append(button);
  return button;
}
