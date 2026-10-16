/**
 * The settings of this browser: a small list of fields, each saved by itself in localStorage (per viewer, never sent anywhere).
 * A new setting is one entry in FIELDS: its default, a label, and what it does when it applies.
 */
import { el } from "./fields.mjs";
import { icon } from "./icons.mjs";

const KEY = "cee.settings";

const FIELDS = [
  {
    id: "particles", type: "switch", default: true,
    label: "Hintergrund mit Partikeln", hint: "Das 1-Bit-Muster hinter der Seite.",
  },
  {
    id: "motion", type: "choice", default: "system",
    label: "Bewegung", options: [["system", "Wie das System"], ["reduce", "Reduziert"], ["full", "Normal"]],
  },
];

let values = {};
try { values = JSON.parse(localStorage.getItem(KEY) ?? "{}") ?? {}; } catch { values = {}; }

export const get = id => values[id] ?? FIELDS.find(f => f.id === id).default;

function save() {
  try { localStorage.setItem(KEY, JSON.stringify(values)); } catch { /* blocked: the choice holds until the page closes */ }
}

/** Whether motion is reduced now: the choice, or the system setting while the choice is the system one. */
export function reducedMotion() {
  const choice = get("motion");
  return choice === "reduce" || (choice === "system" && matchMedia("(prefers-reduced-motion: reduce)").matches);
}

/** Puts every setting to work on the page. */
export function apply() {
  document.documentElement.dataset.motion = reducedMotion() ? "reduce" : "full";
  // The background script reads the system setting itself and cannot be told otherwise, so an own "reduced" hides it.
  const bg = document.getElementById("bg-canvas");
  const off = new URLSearchParams(location.search).get("bg") === "off" || bg?.dataset.variant === "off";
  if (bg && !off) bg.hidden = !get("particles") || get("motion") === "reduce";
}

export function set(id, value) {
  values = { ...values, [id]: value };
  save();
  apply();
}

/** The gear in the sidebar footer and the dialog it opens. */
export function settingsButton(button) {
  button.prepend(icon("settings"));
  let dialog = null;
  const build = () => {
    const rows = FIELDS.map(field => {
      if (field.type === "switch") {
        const input = el("input", { type: "checkbox", id: `cee-set-${field.id}`, checked: !!get(field.id) });
        input.setAttribute("role", "switch");
        input.addEventListener("change", () => set(field.id, input.checked));
        const track = el("span", { className: "ui-switch-track" });
        track.setAttribute("aria-hidden", "true");
        const label = el("label", { className: "ui-switch" }, [input, track, el("span", { className: "ui-switch-text" }, [field.label, field.hint ? el("span", { className: "ui-switch-hint", textContent: field.hint }) : null])]);
        label.setAttribute("data-end", "");
        return label;
      }
      const select = el("select", { className: "select", id: `cee-set-${field.id}` }, field.options.map(([value, label]) => el("option", { value, textContent: label, selected: get(field.id) === value })));
      select.addEventListener("change", () => set(field.id, select.value));
      return el("div", { className: "cee-settings-row" }, [el("label", { htmlFor: select.id, textContent: field.label }), select]);
    });
    dialog = el("dialog", { className: "ui-dialog ui-dialog-narrow", id: "cee-settings" });
    dialog.setAttribute("aria-labelledby", "cee-settings-title");
    dialog.append(el("form", { method: "dialog", className: "ui-dialog-box" }, [
      el("header", { className: "ui-dialog-head" }, el("h2", { className: "ui-dialog-title", id: "cee-settings-title", textContent: "Einstellungen" })),
      el("div", { className: "ui-dialog-body cee-settings" }, rows),
      el("footer", { className: "ui-dialog-foot" }, [el("button", { type: "submit", className: "btn primary", textContent: "Fertig" })]),
    ]));
    document.body.append(dialog);
  };
  button.addEventListener("click", () => {
    if (!dialog) build();
    if (window.ui?.openDialog) window.ui.openDialog(dialog);
    else dialog.showModal();
  });
}
