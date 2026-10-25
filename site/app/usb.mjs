import { el } from "./fields.mjs";
import { icon } from "./icons.mjs";

const WORDS = {
  present: ["ok", "Electribe per USB angesteckt"],
  connected: ["ok", "Electribe verbunden"],
  absent: ["off", "Keine Electribe per USB angesteckt"],
  unknown: ["off", "USB-Status unbekannt: Klick bei „Mit Electribe verbinden“ auf Erlauben, dann zeigt die App das Anstecken"],
};

/** The USB icon of the navbar: lit while an Electribe is plugged in, grey while not. Screen readers hear the change. */
export function usbIndicator(root, watch) {
  const note = el("span", { className: "ui-sr-only", role: "status" });
  const badge = el("span", { className: "cee-usb", id: "cee-usb" }, [icon("usb"), note]);
  root.append(badge);
  watch.subscribe(state => {
    const [tone, text] = WORDS[state];
    badge.dataset.tone = tone;
    badge.dataset.state = state;
    badge.title = text;
    note.textContent = text;
  });
  return badge;
}
