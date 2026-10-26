/**
 * Finds text that looks like hard-coded German UI text, for test/i18n.test.mjs. Kept small on purpose: a tokenizer that
 * knows strings, template literals, comments and regex literals, and one heuristic for "this is a sentence or a label".
 */

/** Every string and template literal in `src`, with its line; a template's `${...}` parts read as `{}`. */
export function literals(src) {
  const out = [];
  let i = 0;
  let line = 1;
  let prev = ""; // the last significant character outside literals, to tell a regex from a division
  let word = ""; // the last identifier, for `return /re/` and the like

  const step = () => { if (src[i] === "\n") line++; i++; };
  const readString = quote => {
    const start = line;
    let value = "";
    step();
    while (i < src.length && src[i] !== quote) {
      if (src[i] === "\\") { value += src[i + 1] ?? ""; step(); step(); continue; }
      value += src[i];
      step();
    }
    step();
    out.push({ value, line: start });
  };
  const readTemplate = () => {
    const start = line;
    let value = "";
    step();
    while (i < src.length && src[i] !== "`") {
      if (src[i] === "\\") { value += src[i + 1] ?? ""; step(); step(); continue; }
      if (src[i] === "$" && src[i + 1] === "{") {
        step(); step();
        value += "{}";
        code("}");
        step();
        continue;
      }
      value += src[i];
      step();
    }
    step();
    out.push({ value, line: start });
  };
  const readRegex = () => {
    let inClass = false;
    step();
    while (i < src.length && src[i] !== "\n") {
      const c = src[i];
      if (c === "\\") { step(); step(); continue; }
      if (c === "[") inClass = true;
      else if (c === "]") inClass = false;
      else if (c === "/" && !inClass) break;
      step();
    }
    step();
    while (/[a-z]/i.test(src[i] ?? "")) step();
  };
  // Reads code until the `end` character at depth zero (used for `${...}`), or to the end of the source.
  function code(end) {
    let depth = 0;
    while (i < src.length) {
      const c = src[i];
      if (c === end && depth === 0) return;
      if (c === "/" && src[i + 1] === "/") { while (i < src.length && src[i] !== "\n") step(); continue; }
      if (c === "/" && src[i + 1] === "*") { const close = src.indexOf("*/", i + 2); const stop = close < 0 ? src.length : close + 2; while (i < stop) step(); continue; }
      if (c === "\"" || c === "'") { readString(c); prev = "a"; word = ""; continue; }
      if (c === "`") { readTemplate(); prev = "a"; word = ""; continue; }
      if (c === "/" && (prev === "" || "(,=:[!&|?{};+-*%<>~^".includes(prev) || /^(return|typeof|case|in|of|void|delete|throw)$/.test(word))) {
        readRegex(); prev = "a"; word = ""; continue;
      }
      if (c === "{") depth++;
      if (c === "}") depth--;
      if (/[\w$]/.test(c)) word = /[\w$]/.test(prev) ? word + c : c;
      if (!/\s/.test(c)) prev = c;
      step();
    }
  }
  code(null);
  return out;
}

/**
 * Whether a literal looks like German UI text: it has an umlaut or ß; or it has two or more words, one of them a
 * capitalised word, and none a class name (`cee-a`) or selector/markup character; or it is one capitalised word of
 * four letters or more, like a button label. Lowercase single words ("an", "neu") slip through: keep them in t() anyway.
 */
export function looksLikeUiText(value) {
  const text = value.replace(/\{\}/g, " ").trim();
  if (!/[A-Za-zÄÖÜäöüß]/.test(text)) return false;
  if (/[äöüÄÖÜß]/.test(text)) return true;
  const words = text.split(/\s+/);
  const prose = /^[A-ZÄÖÜ][a-zäöüß]+(-[A-Za-zÄÖÜäöüß]+)*[.,:;!?]?$/;
  if (words.length >= 2 && words.some(w => prose.test(w)) && words.every(w => !/^[a-z]+-[a-z-]+$/.test(w) && !/[#=<>{}]/.test(w))) return true;
  return words.length === 1 && prose.test(text) && text.length > 3;
}

const VOID = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"]);

/**
 * The text nodes of the page's body and its aria-label, title, placeholder and alt values, with their line. Skipped: the
 * content of elements marked data-i18n or data-i18n-html, an aria-label next to data-i18n-label, and the elements whose id
 * is in `excluded`.
 */
export function htmlText(html, excluded = []) {
  const body = html.indexOf("<body");
  const out = [];
  const stack = [];
  let skip = Infinity; // the stack depth below which everything is skipped
  const lineAt = index => html.slice(0, index).split("\n").length;
  for (const m of html.slice(body < 0 ? 0 : body).matchAll(/<!--[\s\S]*?-->|<(\/?)([a-zA-Z][\w-]*)([^>]*)>|[^<]+/g)) {
    const index = m.index + Math.max(body, 0);
    if (m[0].startsWith("<!--")) continue;
    if (m[2]) {
      const [, close, tag, attrs] = m;
      if (close) {
        while (stack.length && stack.pop() !== tag.toLowerCase());
        if (stack.length < skip) skip = Infinity;
        continue;
      }
      const attr = name => attrs.match(new RegExp(`\\s${name}="([^"]*)"`))?.[1];
      const hidden = stack.length >= skip || excluded.includes(attr("id"));
      if (!hidden) {
        for (const name of ["aria-label", "title", "placeholder", "alt"]) {
          const value = attr(name);
          if (value && !(name === "aria-label" && attr("data-i18n-label"))) out.push({ value, line: lineAt(index) });
        }
      }
      if (VOID.has(tag.toLowerCase()) || attrs.endsWith("/")) continue;
      stack.push(tag.toLowerCase());
      if (skip === Infinity && (excluded.includes(attr("id")) || attr("data-i18n") !== undefined || attr("data-i18n-html") !== undefined)) skip = stack.length;
      continue;
    }
    const value = m[0].trim();
    if (value && stack.length < skip && !stack.some(tag => tag === "script" || tag === "style")) out.push({ value, line: lineAt(index) });
  }
  return out;
}
