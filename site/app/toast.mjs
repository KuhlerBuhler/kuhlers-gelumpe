/**
 * The one toast of the app: a small bubble bottom right. Success and info go away by themselves, an error stays until
 * it is closed. Success and info are announced politely, errors at once (two live regions in one popover layer).
 * Infos, warnings and errors never stand in the page itself, they all come here; a screen-reader line may keep them too.
 */
import { el } from "./fields.mjs";
import { icon } from "./icons.mjs";

const AUTO_MS = 5000;
const MAX = 4;
let polite = null;
let assertive = null;

function mount() {
  if (polite) return;
  const layer = el("div", { id: "app-toasts" });
  layer.setAttribute("popover", "manual");
  polite = el("div", { className: "cee-toast-live", id: "cee-toasts-polite" });
  polite.setAttribute("aria-live", "polite");
  assertive = el("div", { className: "cee-toast-live", id: "cee-toasts-assertive", role: "alert" });
  assertive.setAttribute("aria-live", "assertive");
  layer.append(polite, assertive);
  document.body.append(layer);
  raise();
  // A dialog opened later lies above the layer and its backdrop blurs the toasts: put the layer back on top.
  new MutationObserver(changes => { if (changes.some(c => c.target.localName === "dialog")) raise(); }).observe(document.body, { subtree: true, attributeFilter: ["open"] });
}

/** Shows the layer last in the top layer, above an open dialog. */
function raise() {
  const layer = document.getElementById("app-toasts");
  try {
    if (layer.matches(":popover-open")) layer.hidePopover();
    layer.showPopover();
  } catch { /* no popover support: the fixed box of the design still shows it */ }
}

/**
 * @param {string} message
 * @param {"ok"|"info"|"error"} [kind]
 * @param {{stay?: boolean}} [options] stay: an info or ok toast that waits to be closed, like an error
 * @returns {() => void} closes the toast
 */
export function toast(message, kind = "info", { stay = false } = {}) {
  if (!message) return () => {};
  mount();
  // The same words again (a background check that fails every few seconds): the open toast stays, its time starts anew.
  const same = [...polite.children, ...assertive.children].find(n => n.dataset.kind === kind && n.textContent === message && !n.dataset.closing);
  if (same) { same.restart?.(); return same.close; }
  const host = kind === "error" ? assertive : polite;
  const close = el("button", { type: "button", className: "btn icon cee-toast-close", title: "Schließen" }, [icon("x")]);
  close.setAttribute("aria-label", "Schließen");
  const node = el("div", { className: `app-toast cee-toast${kind === "ok" ? " ok" : kind === "error" ? " err" : ""}` }, [el("span", { className: "cee-toast-text", textContent: message }), close]);
  node.dataset.kind = kind;
  let timer = null;
  const remove = () => {
    clearTimeout(timer);
    node.dataset.closing = "1";
    node.classList.remove("visible");
    setTimeout(() => node.remove(), 250);
  };
  close.addEventListener("click", remove);
  host.append(node);
  raise();
  const open = [...polite.children];
  for (const old of open.slice(0, Math.max(0, open.length - MAX))) old.remove();
  requestAnimationFrame(() => node.classList.add("visible"));
  if (kind !== "error" && !stay) {
    const arm = () => { clearTimeout(timer); timer = setTimeout(remove, AUTO_MS); };
    arm();
    node.restart = arm;
    node.addEventListener("mouseenter", () => clearTimeout(timer));
    node.addEventListener("mouseleave", arm);
    node.addEventListener("focusin", () => clearTimeout(timer));
    node.addEventListener("focusout", arm);
  }
  node.close = remove;
  return remove;
}

// The design system rejects files through this name (ui.rejectFile).
if (typeof window !== "undefined") window.showToast = (message, tone) => toast(message, tone === "err" ? "error" : tone === "ok" ? "ok" : "info");
