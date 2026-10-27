/**
 * Text that src/ and data/ hand to the page: a key of the table in site/app/i18n-de.mjs and the values for its `{name}`
 * placeholders, never the finished German. A value may itself be such a text. The page renders it with t() in the
 * chosen language: site/app/i18n.mjs registers itself here (useTexts). In Node (the CLI, tools, tests) nobody has to:
 * the German table is read directly, so their output stays German. src/ never imports site/app/i18n.mjs itself, the
 * page serves src/ and site/ from different roots.
 */

/** A text: `key` in the table, `vars` the values for its placeholders. */
export const text = (key, vars) => (vars ? { key, vars } : { key });

export const isText = value => value !== null && typeof value === "object" && typeof value.key === "string" && !Array.isArray(value);

let lookup = key => key;
let localeOf = () => "de-DE";

/** The page's t() and the locale of its language; replaces the German default of Node. */
export function useTexts(t, locale) {
  lookup = t;
  localeOf = locale;
}

/** `{name}` in `template` replaced by `vars.name`; a value that is a text is rendered first. */
export function fill(template, vars = {}) {
  return template.replace(/\{(\w+)\}/g, (all, name) => (name in vars ? String(render(vars[name])) : all));
}

/** A text in the current language; a string or number comes back as it is. */
export function render(value) {
  return isText(value) ? lookup(value.key, value.vars ?? {}) : value;
}

/** A number written the way the current language writes it (German: 1.234,5). */
export const number = (n, options) => n.toLocaleString(localeOf(), options);

/** An error whose message is a text: `message` renders it in the current language, `text` keeps key and values. */
export class TextError extends Error {
  constructor(key, vars, options) {
    const own = text(key, vars);
    super(render(own), options);
    this.text = own;
    Object.defineProperty(this, "message", { get: () => render(this.text), configurable: true });
  }
}

if (globalThis.process?.versions?.node) {
  const de = (await import("../site/app/i18n-de.mjs")).default;
  lookup = (key, vars) => fill(de[key] ?? key, vars);
}
