import { el } from "./fields.mjs";
import { icon } from "./icons.mjs";

/** The icon of each tone: the icon and the word say the state, not a colour. */
const ICONS = { ok: "check", error: "x", warn: "alert", info: "info", running: "clock", neutral: "info" };

/**
 * A state as plain text: a small icon and the word in the text colour. No chip, no dot, no status colour.
 * `props` go onto the span (id, hidden); `setStateText` changes it later, as a job that ends.
 */
export function stateText(tone, word, props = {}) {
  const s = el("span", { className: "cee-state", ...props });
  setStateText(s, tone, word);
  return s;
}

/** Gives a state from `stateText()` another tone and word. */
export function setStateText(node, tone, word) {
  node.dataset.tone = tone;
  node.replaceChildren(icon(ICONS[tone] ?? "info"), el("span", { textContent: word }));
}
