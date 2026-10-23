/**
 * Highlighting and indentation for the plugin language, as a CodeMirror stream parser: JavaScript's
 * words, strings, numbers and comments, with `korg` and the names after `korg.key.`, `korg.led.` and
 * `korg.knobs.` set apart. It needs no CodeMirror import (the editor passes it to StreamLanguage.define), so the
 * tests run it on a plain stream. Token names are the highlighting tags CodeMirror knows.
 */
const KEYWORDS = new Set([
  "async", "await", "break", "case", "catch", "class", "const", "continue", "debugger", "default", "delete", "do", "else",
  "export", "extends", "finally", "for", "function", "if", "import", "in", "instanceof", "let", "new", "of", "return",
  "switch", "this", "throw", "try", "typeof", "var", "void", "while", "with", "yield",
]);
const DEFINES = new Set(["function", "let", "const"]);
const FAMILIES = new Set(["key", "led", "knobs"]);
const OPEN = "([{";
const CLOSE = ")]}";

export const scriptStream = Object.freeze({
  name: "plugin",
  startState: () => ({ block: false, depth: 0, path: [], dot: false, define: false }),
  token(stream, state) {
    if (state.block) {
      if (stream.match(/^.*?\*\//)) state.block = false; else stream.skipToEnd();
      return "comment";
    }
    if (stream.eatSpace()) return null;
    if (stream.match("//")) { stream.skipToEnd(); return "comment"; }
    if (stream.match("/*")) {
      if (stream.match(/^.*?\*\//)) return "comment";
      state.block = true;
      stream.skipToEnd();
      return "comment";
    }
    if (stream.match(/^(?:"(?:[^"\\]|\\.)*"?|'(?:[^'\\]|\\.)*'?)/)) { state.path = []; state.dot = false; state.define = false; return "string"; }
    if (stream.match(/^(?:0[xX][0-9a-fA-F]+|\d+)/)) { state.path = []; state.dot = false; state.define = false; return "number"; }
    const word = stream.match(/^[A-Za-z_$][\w$]*/);
    if (word) {
      const name = word[0];
      if (state.dot) {
        state.dot = false;
        state.path.push(name);
        const [root, family] = state.path;
        return root === "korg" && FAMILIES.has(family) && state.path.length === 3 ? "atom" : "propertyName";
      }
      state.path = [name];
      if (KEYWORDS.has(name)) { state.define = DEFINES.has(name); return "keyword"; }
      if (name === "true" || name === "false") { state.define = false; return "bool"; }
      if (name === "null" || name === "undefined") { state.define = false; return "null"; }
      const style = state.define ? "variableName.definition" : name === "korg" ? "namespace" : "variableName";
      state.define = false;
      return style;
    }
    if (stream.match(".")) { state.dot = state.path.length > 0; return "punctuation"; }
    const ch = stream.peek();
    state.dot = false;
    state.define = false;
    if (OPEN.includes(ch)) { stream.next(); state.depth += 1; state.path = []; return "punctuation"; }
    if (CLOSE.includes(ch)) { stream.next(); state.depth = Math.max(0, state.depth - 1); state.path = []; return "punctuation"; }
    state.path = [];
    if (stream.match(/^(?:=>|[+\-*/%&|^!<>=?:~]+)/)) return "operator";
    stream.next();
    return "punctuation";
  },
  indent: (state, textAfter, context) => Math.max(0, state.depth - (/^\s*[)\]}]/.test(textAfter) ? 1 : 0)) * context.unit,
  languageData: {
    indentOnInput: /^\s*[)\]}]$/,
    commentTokens: { line: "//", block: { open: "/*", close: "*/" } },
  },
});

/** Just enough of CodeMirror's StringStream for scriptStream, to colour code outside the editor. */
class LineStream {
  constructor(line) { this.string = line; this.pos = 0; this.start = 0; }
  eatSpace() { const m = /^\s+/.exec(this.string.slice(this.pos)); if (m) this.pos += m[0].length; return !!m; }
  skipToEnd() { this.pos = this.string.length; }
  peek() { return this.string[this.pos]; }
  next() { return this.string[this.pos++]; }
  match(pattern) {
    if (typeof pattern === "string") { if (!this.string.startsWith(pattern, this.pos)) return false; this.pos += pattern.length; return true; }
    const m = pattern.exec(this.string.slice(this.pos));
    if (!m || m.index !== 0) return null;
    this.pos += m[0].length;
    return m;
  }
}

/** A source as lines of [text, type] pieces, whitespace included (type null), with the editor's token types. */
export function highlightLines(source) {
  const state = scriptStream.startState();
  return source.split("\n").map(line => {
    const stream = new LineStream(line);
    const pieces = [];
    while (stream.pos < line.length) {
      stream.start = stream.pos;
      const type = scriptStream.token(stream, state);
      if (stream.pos === stream.start) stream.pos += 1;
      pieces.push([line.slice(stream.start, stream.pos), type]);
    }
    return pieces;
  });
}
