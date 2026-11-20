/**
 * Checks for the language files of the firmware menus (data/lang/, docs/firmware-sprache.md).
 * Browser-safe: no file access, the caller passes the parsed JSON.
 */

export const LANG_FORMATS = { blech: "gelumpe-lang-blech", korg: "gelumpe-lang-korg" };
export const LANG_FONTS = [0, 1, 3];
const CHARSET = /^[\x20-\x7EÄÖÜäöüß]*$/;
const PLACEHOLDER = /%[-+ #0]*\d*(?:\.\d+)?[hlL]?[diouxXcsfeEgG%]/g;
const DOTTED = /[A-Za-zÄÖÜäöüß]+\./g;
const FORBIDDEN_KEYS = new Set(["en", "english"]);
const KORG_KEY = /^0x[0-9a-f]{8}$/;
const SHA = /^[0-9a-f]{64}$/;

/** The printf placeholders of a text, in order. */
export const placeholders = text => text.match(PLACEHOLDER) ?? [];

/** Whether two texts have the same placeholders in the same order. */
export const samePlaceholders = (a, b) => placeholders(a).join("\u0000") === placeholders(b).join("\u0000");

/** Characters the fonts cannot draw: anything but printable ASCII and ÄÖÜäöüß. */
export const badCharacters = text => [...new Set([...text].filter(c => !CHARSET.test(c)))];

/**
 * Words with a dot that are not in the abbreviation list. A dot at the very end of the text ends a sentence, and
 * a dot that starts "..." is an ellipsis; both are not abbreviations, nor is a dot with a letter or digit right after it (a file name such as e2sFx.all).
 * Case does not count: titles are in capitals.
 */
export function unknownAbbreviations(text, abbreviations) {
  const known = new Set(abbreviations.map(a => a.short.toLowerCase()));
  const out = [];
  for (const m of text.matchAll(DOTTED)) {
    const after = m.index + m[0].length;
    if (after === text.length || /[.A-Za-z0-9]/.test(text[after])) continue;
    if (!known.has(m[0].toLowerCase())) out.push(m[0]);
  }
  return out;
}

/** The forms a glossary term may take in a text: its German form and the listed abbreviations of that form. */
export function termForms(term, glossary, abbreviations) {
  const form = glossary.terms[term];
  if (form === undefined) return [];
  return [form, ...abbreviations.filter(a => a.long.split(", ").includes(form)).map(a => a.short)];
}

/** Object keys that would carry English text into data/lang/, anywhere in the value. */
export function englishKeys(value, path = "") {
  if (Array.isArray(value)) return value.flatMap((v, i) => englishKeys(v, `${path}[${i}]`));
  if (value === null || typeof value !== "object") return [];
  return Object.entries(value).flatMap(([k, v]) => [
    ...(FORBIDDEN_KEYS.has(k.toLowerCase()) ? [`${path}.${k}`] : []),
    ...englishKeys(v, `${path}.${k}`),
  ]);
}

/** Problems of one entry: either `text` or `keep` (the reason it stays English), the character set, abbreviations, glossary. */
export function entryProblems(where, entry, { glossary, abbreviations }) {
  const problems = [];
  const hasText = typeof entry?.text === "string";
  const hasKeep = typeof entry?.keep === "string" && entry.keep.trim() !== "";
  if (hasText === hasKeep) return [`${where}: needs either text or keep with a reason`];
  if (!hasText) return problems;
  const bad = badCharacters(entry.text);
  if (bad.length) problems.push(`${where}: characters the fonts cannot draw: ${bad.join(" ")}`);
  for (const word of unknownAbbreviations(entry.text, abbreviations)) problems.push(`${where}: "${word}" is not in data/lang/de-abk.json`);
  for (const term of entry.glossar ?? []) {
    const forms = termForms(term, glossary, abbreviations);
    if (!forms.length) problems.push(`${where}: glossary term "${term}" does not exist`);
    else if (!forms.some(f => entry.text.includes(f))) problems.push(`${where}: glossary term "${term}" must read "${forms.join('" or "')}"`);
  }
  return problems;
}

/** Problems of a language file (blech.json or korg-<build>.json). */
export function langFileProblems(name, data, context) {
  const problems = englishKeys(data, name).map(p => `${p}: no English text in data/lang/`);
  const kind = Object.keys(LANG_FORMATS).find(k => LANG_FORMATS[k] === data?.format);
  if (!kind) return [...problems, `${name}: format is not one of ${Object.values(LANG_FORMATS).join(", ")}`];
  if (data.version !== 1) problems.push(`${name}: version 1 expected`);
  if (data.texts === null || typeof data.texts !== "object" || Array.isArray(data.texts)) return [...problems, `${name}: texts is an object`];
  for (const [key, entry] of Object.entries(data.texts)) {
    const where = `${name} ${key}`;
    problems.push(...entryProblems(where, entry, context));
    if (kind === "blech" && !/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) problems.push(`${where}: a BLECH key is the label of the text`);
    if (kind !== "korg") continue;
    if (!KORG_KEY.test(key)) problems.push(`${where}: a Korg key is the template address, 0x and 8 lower-case hex digits`);
    if (!SHA.test(entry.expect ?? "")) problems.push(`${where}: expect is the SHA-256 of the old text with its NUL`);
    if (!LANG_FONTS.includes(entry.font)) problems.push(`${where}: font is one of ${LANG_FONTS.join(", ")}`);
    for (const p of entry.pointers ?? []) {
      if (!KORG_KEY.test(p.at ?? "") || !SHA.test(p.expect ?? "")) problems.push(`${where}: a pointer has at (address) and expect (SHA-256 of the old word)`);
    }
    for (const k of ["space", "buffer"]) {
      if (entry[k] !== undefined && entry[k] !== null && !(Number.isInteger(entry[k]) && entry[k] > 0)) problems.push(`${where}: ${k} is a positive whole number`);
    }
  }
  return problems;
}
