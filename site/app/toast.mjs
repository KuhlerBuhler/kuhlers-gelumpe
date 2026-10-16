/**
 * The one toast of the app: a small bubble bottom right. Success and info go away by themselves, an error stays until
 * it is closed. Success and info are announced politely, errors at once (two live regions in one popover layer).
 * Only a state that stays true belongs inline; anything that reports an action belongs here.
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
  try { layer.showPopover(); } catch { /* no popover support: the fixed box of the design still shows it */ }
}

/**
 * @param {string} message
 * @param {"ok"|"info"|"error"} [kind]
 * @returns {() => void} closes the toast
 */
export function toast(message, kind = "info") {
  if (!message) return () => {};
  mount();
  const host = kind === "error" ? assertive : polite;
  const close = el("button", { type: "button", className: "btn icon cee-toast-close", title: "Schließen" }, [icon("x")]);
  close.setAttribute("aria-label", "Schließen");
  const node = el("div", { className: `app-toast cee-toast${kind === "ok" ? " ok" : kind === "error" ? " err" : ""}` }, [el("span", { className: "cee-toast-text", textContent: message }), close]);
  node.dataset.kind = kind;
  let timer = null;
  const remove = () => {
    clearTimeout(timer);
    node.classList.remove("visible");
    setTimeout(() => node.remove(), 250);
  };
  close.addEventListener("click", remove);
  host.append(node);
  const open = [...polite.children];
  for (const old of open.slice(0, Math.max(0, open.length - MAX))) old.remove();
  requestAnimationFrame(() => node.classList.add("visible"));
  if (kind !== "error") {
    const arm = () => { timer = setTimeout(remove, AUTO_MS); };
    arm();
    node.addEventListener("mouseenter", () => clearTimeout(timer));
    node.addEventListener("mouseleave", arm);
    node.addEventListener("focusin", () => clearTimeout(timer));
    node.addEventListener("focusout", arm);
  }
  return remove;
}

// The design system rejects files through this name (ui.rejectFile).
if (typeof window !== "undefined") window.showToast = (message, tone) => toast(message, tone === "err" ? "error" : tone === "ok" ? "ok" : "info");
