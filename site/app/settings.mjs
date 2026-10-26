/**
 * The settings of this browser: a small list of fields, each saved by itself in localStorage (per viewer, never sent anywhere).
 * A new setting is one entry in FIELDS: its default, a label, and what it does when it applies. Labels are i18n keys.
 */
import { el } from "./fields.mjs";
import { icon } from "./icons.mjs";
import { LANGUAGES, language, loadLanguage, setLanguage, systemLanguage, t, translate } from "./i18n.mjs";

const KEY = "cee.settings";

const FIELDS = [
  // Starts with the system's language when there is a table for it, German otherwise.
  {
    id: "language", type: "choice", default: systemLanguage(),
    label: "settings.language", options: LANGUAGES, raw: true,
  },
  {
    id: "particles", type: "switch", default: true,
    label: "settings.particles", hint: "settings.particles.hint",
  },
  {
    id: "motion", type: "choice", default: "system",
    label: "settings.motion", options: [["system", "settings.motion.system"], ["reduce", "settings.motion.reduce"], ["full", "settings.motion.full"]],
  },
];

let values = {};
try { values = JSON.parse(localStorage.getItem(KEY) ?? "{}") ?? {}; } catch { values = {}; }

export const get = id => values[id] ?? FIELDS.find(f => f.id === id).default;

await loadLanguage(get("language"));
let shown = null;

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
  setLanguage(get("language"));
  // Only on a change: the update entry writes its progress into its own text.
  if (shown !== language()) { translate(); shown = language(); }
  document.documentElement.dataset.motion = reducedMotion() ? "reduce" : "full";
  // The background script reads the system setting itself and cannot be told otherwise, so an own "reduced" hides it.
  const bg = document.getElementById("bg-canvas");
  const off = new URLSearchParams(location.search).get("bg") === "off" || bg?.dataset.variant === "off";
  if (bg && !off) bg.hidden = !get("particles") || get("motion") === "reduce";
}

export function set(id, value) {
  values = { ...values, [id]: value };
  save();
  // Most pages build their texts once, so a new language takes a fresh start of the page.
  if (id === "language" && value !== language()) { location.reload(); return; }
  apply();
}

/** The settings button in the sidebar footer: it opens the settings page like any other area. */
export function settingsButton(button, open) {
  button.prepend(icon("slidersHorizontal"));
  button.addEventListener("click", open);
}

/** The settings page in the main content. */
/** The installed app's version, from the desktop app (src-tauri); a browser has none, and the line stays away. */
export function settingsPage(root, app = window.__GELUMPE_APP) {
  const rows = FIELDS.filter(field => field.options?.length !== 1).map(field => {
    if (field.type === "switch") {
      const input = el("input", { type: "checkbox", id: `cee-set-${field.id}`, checked: !!get(field.id) });
      input.setAttribute("role", "switch");
      input.addEventListener("change", () => set(field.id, input.checked));
      const track = el("span", { className: "ui-switch-track" });
      track.setAttribute("aria-hidden", "true");
      const label = el("label", { className: "ui-switch" }, [input, track, el("span", { className: "ui-switch-text" }, [t(field.label), field.hint ? el("span", { className: "ui-switch-hint", textContent: t(field.hint) }) : null])]);
      label.setAttribute("data-end", "");
      return label;
    }
    const select = el("select", { className: "select", id: `cee-set-${field.id}` }, field.options.map(([value, label]) => el("option", { value, textContent: field.raw ? label : t(label), selected: get(field.id) === value })));
    select.addEventListener("change", () => set(field.id, select.value));
    return el("div", { className: "cee-settings-row" }, [el("label", { htmlFor: select.id, textContent: t(field.label) }), select]);
  });
  root.replaceChildren(
    el("h1", { className: "ui-sr-only", id: "cee-settings-title", textContent: t("settings.title") }),
    el("div", { className: "cee-settings" }, rows),
    ...(app?.version ? [el("p", { className: "muted cee-version", id: "cee-version", textContent: t("settings.version", { version: app.version }) })] : []),
  );
}
