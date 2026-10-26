import { el } from "./fields.mjs";
import { icon } from "./icons.mjs";
import { t } from "./i18n.mjs";

const WORDS = {
  present: ["ok", "usb.present"],
  connected: ["ok", "usb.connected"],
  absent: ["off", "usb.absent"],
  unknown: ["off", "usb.unknown"],
};

/** The USB icon of the navbar: lit while an Electribe is plugged in, grey while not. Screen readers hear the change. */
export function usbIndicator(root, watch) {
  const note = el("span", { className: "ui-sr-only", role: "status" });
  const badge = el("span", { className: "cee-usb", id: "cee-usb" }, [icon("usb"), note]);
  root.append(badge);
  watch.subscribe(state => {
    const [tone, key] = WORDS[state];
    const text = t(key);
    badge.dataset.tone = tone;
    badge.dataset.state = state;
    badge.title = text;
    note.textContent = text;
  });
  return badge;
}
