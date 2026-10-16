import { test } from "node:test";
import assert from "node:assert/strict";
import { scriptStream } from "../src/script/highlight.mjs";
import { PRESETS } from "../data/script/presets.mjs";
import { TEMPLATES, templateSource } from "../data/script/templates.mjs";

/** Just enough of CodeMirror's StringStream for the tokenizer. */
class Stream {
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

/** Tokens of a source as [text, type] pairs, whitespace left out, and the state after the last line. */
function tokens(source) {
  const state = scriptStream.startState();
  const out = [];
  for (const line of source.split("\n")) {
    const stream = new Stream(line);
    while (stream.pos < line.length) {
      stream.start = stream.pos;
      const type = scriptStream.token(stream, state);
      assert.ok(stream.pos > stream.start, `the tokenizer advances on "${line}" at ${stream.start}`);
      if (type !== null) out.push([line.slice(stream.start, stream.pos), type]);
    }
  }
  return { out, state };
}
const types = source => Object.fromEntries(tokens(source).out.map(([text, type]) => [text, type]));

test("keywords, strings, numbers, comments and the words of the language get their own types", () => {
  const t = types(`const FIRST = 0x1F + 12; // five
if (true && x != null) return "a\\"b";`);
  assert.equal(t.const, "keyword");
  assert.equal(t.FIRST, "variableName.definition");
  assert.equal(t["0x1F"], "number");
  assert.equal(t["12"], "number");
  assert.equal(t["// five"], "comment");
  assert.equal(t.if, "keyword");
  assert.equal(t.true, "bool");
  assert.equal(t.null, "null");
  assert.equal(t.x, "variableName");
  assert.equal(t['"a\\"b"'], "string");
  assert.equal(t["!="], "operator");
});

test("korg is a namespace, what follows it a property, and a key or LED name an atom", () => {
  const t = tokens(`korg.display.text("a", 0, 0); if (key == korg.key.TAP) korg.led(korg.led.PAD_1_RED, 255);`).out;
  const of = text => t.filter(([x]) => x === text).map(([, type]) => type);
  assert.deepEqual(of("korg"), ["namespace", "namespace", "namespace", "namespace"]);
  assert.deepEqual(of("display"), ["propertyName"]);
  assert.deepEqual(of("TAP"), ["atom"]);
  assert.deepEqual(of("PAD_1_RED"), ["atom"]);
  assert.deepEqual(of("led"), ["propertyName", "propertyName"]);
  assert.deepEqual(of("key"), ["variableName", "propertyName"], "key on its own is an ordinary word");
});

test("function names are definitions and a block comment runs over lines", () => {
  const { out, state } = tokens("function show() {\n  /* one\n  two */ korg.display.clear();\n}\n");
  assert.deepEqual(out.find(([x]) => x === "show"), ["show", "variableName.definition"]);
  assert.deepEqual(out.filter(([, type]) => type === "comment").map(([x]) => x), ["/* one", "  two */"]);
  assert.equal(state.block, false);
  assert.equal(state.depth, 0);
});

test("indentation follows the open brackets, and a closing bracket takes one level back", () => {
  const state = scriptStream.startState();
  for (const line of ["korg.onEvent(\"frame\", () => {", "  if (x) {"]) {
    const stream = new Stream(line);
    while (stream.pos < line.length) { stream.start = stream.pos; scriptStream.token(stream, state); }
  }
  assert.equal(state.depth, 3, "the call's parenthesis stays open with the two braces");
  const context = { unit: 2 };
  assert.equal(scriptStream.indent(state, "  korg.led(1, 2);", context), 6);
  assert.equal(scriptStream.indent(state, "}", context), 4);
});

test("the tokenizer reads every example plugin and template without stalling", () => {
  for (const p of PRESETS) assert.ok(tokens(p.source).out.length > 20, p.id);
  for (const t of TEMPLATES) assert.ok(tokens(templateSource(t.id, "x")).out.length > 20, t.id);
  const bad = tokens(`let s = "never closed\nlet t = 'x' + "y;\n/* open`);
  assert.ok(bad.out.length > 5);
  assert.equal(bad.state.block, true);
});
