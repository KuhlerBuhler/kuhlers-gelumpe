/**
 * The app's texts by key, one table per language (site/app/i18n-<lang>.mjs). index.html keeps its German text next to
 * `data-i18n` / `data-i18n-label`, so the page reads right before the script runs; test/i18n.test.mjs keeps both equal.
 */
import de from "./i18n-de.mjs";
import { fill, isText, useTexts } from "../../src/text.mjs";
// Only German loads with the page; another language loads when it is chosen (loadLanguage), so a start reads one
// table, not eleven. The names are here so the settings can list every language without loading it.
const NAMES = { de: "Deutsch", en: "English", fr: "Français", it: "Italiano", es: "Español", nl: "Nederlands", pt: "Português", pl: "Polski", cs: "Čeština", ru: "Русский", uk: "Українська" };
const TABLES = { de };
/** The languages there are, with their own names for the settings. */
export const LANGUAGES = Object.entries(NAMES);

/** The language of the system when there is a table for it, else German: the start value until the user picks one. */
export function systemLanguage(prefs = globalThis.navigator?.languages ?? []) {
  for (const tag of prefs) {
    const id = String(tag).toLowerCase().split("-")[0];
    if (NAMES[id]) return id;
  }
  return "de";
}

let lang = "de";

/** Switches to a language whose table is loaded; any other id means German. */
export function setLanguage(id) {
  lang = TABLES[id] ? id : "de";
  if (globalThis.document) document.documentElement.lang = lang;
}

/** Loads the table of `id` (once) and switches to it; an unknown id, or a table that does not load, means German. */
export async function loadLanguage(id) {
  if (NAMES[id] && !TABLES[id]) {
    try { TABLES[id] = (await import(`./i18n-${id}.mjs`)).default; } catch { /* German stays */ }
  }
  setLanguage(id);
}

export const language = () => lang;

/** The locale numbers and dates follow: the language, German as de-DE. */
const LOCALES = { de: "de-DE" };
export const locale = () => LOCALES[lang] ?? lang;

/**
 * The text for `key`; `{name}` in it is replaced by `vars.name`. `key` may also be a text from src/ or data/
 * ({key, vars}, src/text.mjs), and so may a value.
 */
export function t(key, vars = {}) {
  if (isText(key)) return t(key.key, key.vars);
  return fill(TABLES[lang][key] ?? de[key] ?? key, vars);
}

useTexts(t, locale);

/** Like t(), but a value may be a DOM node or a list of them: the text comes back as a flat list of strings and nodes, for append(). */
export function tNodes(key, vars = {}) {
  const text = TABLES[lang][key] ?? de[key] ?? key;
  return text.split(/(\{\w+\})/).flatMap(part => {
    const name = part.match(/^\{(\w+)\}$/)?.[1];
    return name && name in vars ? vars[name] : part;
  }).filter(part => part !== "");
}

/** Puts the texts of the chosen language into every marked element below `root`. */
export function translate(root = document) {
  for (const node of root.querySelectorAll("[data-i18n]")) node.textContent = t(node.dataset.i18n);
  // Text with links or code in it: the table holds its markup. Set only on a change, so the links keep their listeners.
  for (const node of root.querySelectorAll("[data-i18n-html]")) {
    const html = t(node.dataset.i18nHtml);
    if (node.innerHTML !== html) node.innerHTML = html;
  }
  for (const node of root.querySelectorAll("[data-i18n-label]")) node.setAttribute("aria-label", t(node.dataset.i18nLabel));
}
