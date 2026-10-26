import { render, text } from "./text.mjs";

/**
 * A linter finding or gate reason whose message is a text (src/text.mjs): `text` keeps key and values for the page,
 * `message` renders it in the current language, so the CLI, the tests and a spread copy read the same string as before.
 */
export function finding(fields, key, vars) {
  const out = { ...fields, text: text(key, vars) };
  Object.defineProperty(out, "message", { get() { return render(this.text); }, enumerable: true, configurable: true });
  return out;
}
