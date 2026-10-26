/**
 * The app's texts by key, one table per language (site/app/i18n-<lang>.mjs). index.html keeps its German text next to
 * `data-i18n` / `data-i18n-label`, so the page reads right before the script runs; test/i18n.test.mjs keeps both equal.
 */
import de from "./i18n-de.mjs";

const TABLES = { de };
/** The languages there are, with their own names for the settings. */
export const LANGUAGES = Object.keys(TABLES).map(id => [id, TABLES[id]["language.name"]]);

let lang = "de";

export function setLanguage(id) {
  lang = TABLES[id] ? id : "de";
  if (globalThis.document) document.documentElement.lang = lang;
}

export const language = () => lang;

/** The text for `key`; `{name}` in it is replaced by `vars.name`. */
export function t(key, vars = {}) {
  const text = TABLES[lang][key] ?? de[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (all, name) => (name in vars ? String(vars[name]) : all));
}

/** Puts the texts of the chosen language into every marked element below `root`. */
export function translate(root = document) {
  for (const node of root.querySelectorAll("[data-i18n]")) node.textContent = t(node.dataset.i18n);
  for (const node of root.querySelectorAll("[data-i18n-label]")) node.setAttribute("aria-label", t(node.dataset.i18nLabel));
}
