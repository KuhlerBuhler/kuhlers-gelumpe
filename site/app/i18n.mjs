/**
 * The app's texts by key, one table per language (site/app/i18n-<lang>.mjs). index.html keeps its German text next to
 * `data-i18n` / `data-i18n-label`, so the page reads right before the script runs; test/i18n.test.mjs keeps both equal.
 */
import de from "./i18n-de.mjs";
import en from "./i18n-en.mjs";
import fr from "./i18n-fr.mjs";
import it from "./i18n-it.mjs";
import es from "./i18n-es.mjs";
import nl from "./i18n-nl.mjs";
import pt from "./i18n-pt.mjs";
import pl from "./i18n-pl.mjs";
import cs from "./i18n-cs.mjs";
import ru from "./i18n-ru.mjs";
import uk from "./i18n-uk.mjs";

const TABLES = { de, en, fr, it, es, nl, pt, pl, cs, ru, uk };
/** The languages there are, with their own names for the settings. */
export const LANGUAGES = Object.keys(TABLES).map(id => [id, TABLES[id]["language.name"]]);

/** The language of the system when there is a table for it, else German: the start value until the user picks one. */
export function systemLanguage(prefs = globalThis.navigator?.languages ?? []) {
  for (const tag of prefs) {
    const id = String(tag).toLowerCase().split("-")[0];
    if (TABLES[id]) return id;
  }
  return "de";
}

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
