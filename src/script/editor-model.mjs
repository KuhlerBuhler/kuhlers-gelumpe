/**
 * What the plugin editor knows about the script language, as plain functions of the source text and
 * a caret position: completions, the parameter hint of a call, the hover text and the range of a
 * compile error. It reads the contract and the descriptions and never touches a DOM or the editor
 * library, so it runs in Node and the tests drive it directly. site/app/script-editor.mjs wires it to CodeMirror.
 * Its words are texts of the table (src/text.mjs), read through getters, so they follow the language the page shows now.
 */
import { API, API_BY_NAME, EVENTS, EVENT_BY_NAME, SCRIPT_APPS, LIMITS } from "../../data/script/contract.mjs";
import { API_DOCS, ON_EVENT_DOC, EVENT_DOCS, GROUP_DOCS, NAME_FAMILY_DOCS } from "../../data/script/describe.mjs";
import { KEY_NAMES, LED_NAMES } from "../../data/script/names.mjs";
import { PROPERTIES, KNOB_NAMES } from "../../data/script/properties.mjs";
import { OBJECTS, OBJECT_BY_PATH, objectChildren, isObjectBranch } from "../../data/script/objects.mjs";
import { hintAt } from "./names.mjs";
import { text as msg, render } from "../text.mjs";

const say = (key, vars) => render(msg(key, vars));

const INT_MIN = -2147483648;
const INT_MAX = 2147483647;
const ALL_EVENTS = EVENTS.map(e => e.name);
const FAMILIES = { key: KEY_NAMES, led: LED_NAMES };
const FAMILY_TITLE = { key: "Taste", led: "LED" };
const IDENT = "[A-Za-z_$][\\w$]*";
const PATH_END = new RegExp(`${IDENT}(?:\\.[\\w$]*)*$`);
const PATH = new RegExp(`${IDENT}(?:\\.${IDENT})*`, "g");

/** How an argument reads in a hint: its range, or what kind of value it is. */
export function rangeText(arg) {
  if (arg.kind === "str") return say("script.editor.range.text", { max: LIMITS.stringLength });
  if (arg.kind === "arr") return say("script.editor.range.array");
  if (arg.min === INT_MIN && arg.max === INT_MAX) return say("script.editor.range.int");
  return say("script.editor.range.span", { min: arg.min, max: arg.max });
}

const list = (items, last = say("script.editor.and")) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} ${last} ${items.at(-1)}`);
const sameSet = (a, b) => a.length === b.length && a.every(n => b.includes(n));

/** The calls that take a function as their last argument (korg.after, korg.every, korg.afterSteps). */
const TIMER_CALLS = new Set(["korg.after", "korg.every", "korg.afterSteps"]);

/** How an argument of an API entry reads in a hint: a timer's callback and number say what they are, not their numbers. */
function argRange(entry, arg) {
  if (TIMER_CALLS.has(entry.name) && arg.name === "callback") return say("script.editor.callback");
  if (entry.name === "korg.cancel") return say("script.editor.timerNumber");
  return rangeText(arg);
}

/** Where an API entry may be called, from the events its contract entry lists. */
export function allowedIn(entry) {
  if (sameSet(entry.events, ALL_EVENTS)) return say("script.editor.allowed.everywhere");
  if (sameSet(entry.events, ALL_EVENTS.filter(n => n !== "start" && n !== "save"))) return say("script.editor.allowed.events");
  if (sameSet(entry.events, ALL_EVENTS.filter(n => n !== "save"))) return say("script.editor.allowed.notSave");
  return say("script.editor.allowed.only", { list: list(entry.events.map(n => (n === "start" ? say("script.editor.allowed.body") : say("script.editor.allowed.event", { event: n })))) });
}

/** The facts the editor shows about an API entry. */
function apiInfo(entry) {
  const params = entry.args.map(a => ({ name: a.name, get range() { return argRange(entry, a); } }));
  return {
    name: entry.name,
    signature: `${entry.name}(${params.map(p => p.name).join(", ")})`,
    text: API_DOCS[entry.name],
    params,
    get returns() { return entry.returns === "int" ? say("script.editor.returns.int") : null; },
    get allowed() { return allowedIn(entry); },
  };
}

const ON_EVENT_INFO = Object.freeze({
  name: ON_EVENT_DOC.name,
  signature: ON_EVENT_DOC.signature,
  text: ON_EVENT_DOC.text,
  params: Object.freeze([{ name: "ereignis", get range() { return say("script.editor.onEvent.event"); } }, { name: "handler", get range() { return say("script.editor.onEvent.handler"); } }]),
  returns: null,
  get allowed() { return say("script.editor.onEvent.allowed"); },
});

function eventInfo(event) {
  const doc = EVENT_DOCS[event.name];
  return {
    name: event.name,
    signature: `(${event.args.join(", ")})`,
    text: doc.text,
    params: event.args.map(a => ({ name: a, range: doc.args[a] })),
    returns: null,
    allowed: null,
  };
}

/** `korg.parts[i].step` as a plugin writes it, and the name the editor finds it by: `korg.parts`. */
const shown = prop => prop.path.replace("[]", "[i]");
const owner = prop => prop.path.split("[]")[0];

/** The facts the editor shows about a property: what it is, and where it may be read and set. */
function propertyInfo(prop) {
  const read = prop.read && API_BY_NAME.get(prop.read[0]);
  const write = prop.write && API_BY_NAME.get(prop.write[0]);
  const where = () => [read && say("script.editor.read", { where: allowedIn(read) }), write && say("script.editor.write", { where: allowedIn(write) })].filter(Boolean).join("; ");
  return { name: shown(prop), signature: shown(prop), text: prop.text, params: [], get returns() { return read ? say("script.editor.returns.int") : null; }, get allowed() { return where(); } };
}

/** The properties of one object, korg.parts: every field in one text. */
function objectInfo(name) {
  const props = PROPERTIES.filter(p => owner(p) === name);
  if (!props.length) return null;
  if (props.length === 1) return propertyInfo(props[0]);
  return { name, signature: `${name}[i]`, text: props.map(p => `${shown(p)}: ${render(p.text)}`).join(" "), params: [], returns: null, allowed: null };
}

/** What a leaf of the object tree is: its range, whether it is read or set and where, and the API version it came with. */
function leafInfo(leaf) {
  if (leaf.action) {
    const set = API_BY_NAME.get("korg.set");
    return { name: leaf.path, signature: `${leaf.path}()`, text: leaf.text, params: [], returns: null,
      get allowed() { return [say("script.editor.action"), allowedIn(set), say("script.editor.since", { since: leaf.since })].join("; "); } };
  }
  const read = API_BY_NAME.get("korg.get");
  const write = API_BY_NAME.get("korg.set");
  return {
    name: leaf.path, signature: leaf.path, text: leaf.text, params: [],
    get returns() { return say("script.editor.returns.int"); },
    get allowed() {
      return [say("script.editor.range.span", { min: leaf.min, max: leaf.max }), say("script.editor.read", { where: allowedIn(read) }),
        leaf.write ? say("script.editor.write", { where: allowedIn(write) }) : say("script.editor.readOnly"), say("script.editor.since", { since: leaf.since })].join("; ");
    },
  };
}

/** The names that follow a branch of the object tree: its children, and the API calls under the same name (korg.menu.add). */
function branchNames(path) {
  const depth = path.split(".").length;
  const calls = API.filter(a => a.name.startsWith(`${path}.`) && a.name.split(".").length === depth + 1).map(a => a.name.split(".").at(-1));
  return [...objectChildren(path), ...calls.filter(c => !objectChildren(path).includes(c))];
}

function branchInfo(path) {
  return { name: path, signature: `${path}.`, get text() { return say("script.editor.branch.text", { list: list(branchNames(path)) }); }, params: [], returns: null, allowed: null };
}

/** A path of the object tree: a leaf, or a branch that has leaves below it. */
const treeInfo = path => (OBJECT_BY_PATH.has(path) ? leafInfo(OBJECT_BY_PATH.get(path)) : isObjectBranch(path) ? branchInfo(path) : null);

/** An API entry by its name; `korg.tempo` without a bracket behind it is the property. */
const infoFor = (name, called = true) => (name === ON_EVENT_DOC.name ? ON_EVENT_INFO
  : treeInfo(name) ? treeInfo(name)
  : called && API_BY_NAME.has(name) ? apiInfo(API_BY_NAME.get(name))
    : objectInfo(name) ?? (API_BY_NAME.has(name) ? apiInfo(API_BY_NAME.get(name)) : null));

/**
 * Walk the source up to `pos` and say where the caret is: in code, in a string or in a comment, and
 * which calls and brackets are open around it. A call frame knows its callee, how many commas it has
 * seen at its own level and the first argument if that was a string.
 */
function scan(text, pos) {
  const stack = [];
  let mode = "code";
  let from = 0;
  for (let i = 0; i < pos; i++) {
    const c = text[i];
    if (mode === "line") { if (c === "\n") mode = "code"; continue; }
    if (mode === "block") { if (c === "*" && text[i + 1] === "/") { mode = "code"; i++; } continue; }
    if (mode === "string") {
      if (c === "\\") { i++; continue; }
      if (c === text[from] || c === "\n") {
        mode = "code";
        const top = stack.at(-1);
        if (top && top.commas === 0 && top.first === undefined && c !== "\n") top.first = text.slice(from + 1, i);
      }
      continue;
    }
    if (c === "/" && text[i + 1] === "/") { mode = "line"; i++; continue; }
    if (c === "/" && text[i + 1] === "*") { mode = "block"; i++; continue; }
    if (c === '"' || c === "'" || c === "`") { mode = "string"; from = i; continue; }
    if (c === "(") {
      const callee = PATH_END.exec(text.slice(Math.max(0, i - 80), i).trimEnd())?.[0] ?? null;
      stack.push({ callee: callee && !/^(?:if|while|for|function|return)$/.test(callee) ? callee : null, kind: "(", open: i, commas: 0 });
    } else if (c === "[" || c === "{") stack.push({ callee: null, kind: c, open: i, commas: 0 });
    else if (c === ")" || c === "]" || c === "}") stack.pop();
    else if (c === "," && stack.length) stack.at(-1).commas += 1;
  }
  return { mode: mode === "line" || mode === "block" ? "comment" : mode, stringStart: from, stack };
}

/** The rest of the line after `pos`, to tell whether a snippet may add the closing text. */
const restOfLine = (text, pos) => text.slice(pos, text.indexOf("\n", pos) < 0 ? text.length : text.indexOf("\n", pos));

const handlerParams = event => `(${event.args.join(", ")})`;

/** The text an API call goes in as: its arguments as fields, a timer's function as an arrow to write into. */
function callSnippet(entry, label = entry.name) {
  if (TIMER_CALLS.has(entry.name)) return `${label}(\${1:${entry.args[0].name}}, () => {\n  \${2}\n})`;
  return `${label}(${entry.args.map((a, i) => `\${${i + 1}:${a.name}}`).join(", ")})`;
}

function apiOption(entry) {
  const info = apiInfo(entry);
  return { label: entry.name, type: "function", detail: `(${info.params.map(p => p.name).join(", ")})`, info, snippet: callSnippet(entry) };
}

/** A leaf as the option after its branch: the last name only, with its range and whether it is set. */
function leafOption(leaf, label = leaf.path.split(".").at(-1)) {
  const info = leafInfo(leaf);
  if (leaf.action) return { label, type: "function", get detail() { return say("script.editor.action"); }, info, snippet: `${label}()` };
  return { label, type: "property", get detail() { return `${say("script.editor.range.span", { min: leaf.min, max: leaf.max })}, ${say(leaf.write ? "script.editor.readWrite" : "script.editor.readOnly")}`; }, info };
}

/** What may follow `path.`: the children of a branch of the object tree, and the API calls below the same name. */
function treeOptions(path) {
  return branchNames(path).map(name => {
    const full = `${path}.${name}`;
    if (OBJECT_BY_PATH.has(full)) return leafOption(OBJECT_BY_PATH.get(full));
    if (API_BY_NAME.has(full)) {
      const entry = API_BY_NAME.get(full);
      return { label: name, type: "function", detail: `(${entry.args.map(a => a.name).join(", ")})`, info: apiInfo(entry), snippet: callSnippet(entry, name) };
    }
    return { label: name, type: "namespace", get detail() { return say("script.editor.branch"); }, info: branchInfo(full), apply: `${name}.`, retrigger: true };
  });
}

/** The first branches of the object tree, offered after `korg.` beside the flat names: `korg.menu`, `korg.system`. */
const TREE_ROOTS = [...new Set(OBJECTS.map(o => o.path.split(".").slice(0, 2).join(".")))].map(path => ({
  label: path, type: "namespace", get detail() { return say("script.editor.branch"); }, info: branchInfo(path), apply: `${path}.`, retrigger: true,
}));

const NAMESPACE_OPTION = Object.freeze({ label: "korg.key", type: "namespace", get detail() { return say("script.editor.keys"); }, info: { name: "korg.key", signature: "korg.key.NAME", text: NAME_FAMILY_DOCS.key, params: [], returns: null, allowed: null }, apply: "korg.key.", retrigger: true });
const ON_EVENT_OPTION = Object.freeze({ label: ON_EVENT_DOC.name, type: "function", detail: "(ereignis, handler)", info: ON_EVENT_INFO, snippet: `korg.onEvent("\${1:ereignis}", (\${2}) => {\n  \${3}\n});` });

function propertyOption(prop) {
  const snippet = prop.path.replace("[]", "[${1:i}]");
  return { label: shown(prop), type: "property", get detail() { return say(prop.write ? "script.editor.readWrite" : prop.read ? "script.editor.readOnly" : "script.editor.writeOnly"); }, info: propertyInfo(prop), snippet };
}

/** The options for every name a plugin may write after `korg.`, with `korg` itself for the first letters. */
const KORG_OPTIONS = Object.freeze([...PROPERTIES.map(propertyOption), ...API.map(apiOption), ...OBJECTS.filter(o => o.action).map(o => leafOption(o, o.path)),
  ON_EVENT_OPTION, NAMESPACE_OPTION, ...TREE_ROOTS]);

const KNOB_OPTIONS = Object.freeze(KNOB_NAMES.map(k => ({
  label: k.name, type: "constant", detail: String(k.value),
  info: { name: `korg.knobs.${k.name}`, signature: `korg.knobs.${k.name}`, get text() { return say("script.editor.knob", { label: k.label }); }, params: [], get returns() { return say("script.editor.returns.int"); }, get allowed() { return allowedIn(API_BY_NAME.get("korg.read.knob")); } },
})));

function nameOptions(family) {
  return FAMILIES[family].map(n => ({
    label: n.name,
    type: "constant",
    detail: String(n.value),
    info: { name: `korg.${family}.${n.name}`, signature: `korg.${family}.${n.name}`, get text() { return say(family === "key" ? "script.editor.key" : "script.editor.led", { label: n.label, value: n.value }); }, params: [], returns: null, allowed: null },
  }));
}

/**
 * The completions at `pos`, or null when there is nothing to offer: { from, options }. An option has a
 * label, a type (function, constant, enum, namespace, keyword), a detail, an info object and
 * either a `snippet` (with ${n:name} fields), an `apply` text or nothing (the label goes in). `retrigger`
 * asks the editor to complete again after the text went in.
 */
export function completionsAt(text, pos) {
  const here = scan(text, pos);
  if (here.mode === "comment") return null;
  const call = here.stack.at(-1);
  if (here.mode === "string") {
    const from = here.stringStart + 1;
    if (!/^[A-Za-z]*$/.test(text.slice(from, pos)) || !call) return null;
    const blank = /^\s*$/.test(restOfLine(text, pos));
    if (call.callee === ON_EVENT_DOC.name && call.commas === 0) {
      return {
        from,
        options: EVENTS.filter(e => e.name !== "start").map(e => ({
          label: e.name, type: "enum", detail: handlerParams(e), info: eventInfo(e),
          ...(blank ? { snippet: `${e.name}", ${handlerParams(e)} => {\n  \${}\n});` } : {}),
        })),
      };
    }
    if (call.callee === "korg.app" && call.commas === 1) {
      return { from, options: SCRIPT_APPS.groups.map(g => ({ label: g, type: "enum", get detail() { return say("script.editor.group"); }, info: { name: g, signature: `"${g}"`, text: GROUP_DOCS[g], params: [], returns: null, allowed: null }, ...(blank ? { apply: `${g}");` } : {}) })) };
    }
    return null;
  }
  const token = PATH_END.exec(text.slice(Math.max(0, pos - 80), pos))?.[0];
  if (!token) return null;
  const parts = token.split(".");
  if (parts[0] === "korg" && parts.length === 3 && (parts[1] === "key" || parts[1] === "led")) {
    return { from: pos - parts[2].length, options: nameOptions(parts[1]) };
  }
  if (parts[0] === "korg" && parts.length === 3 && parts[1] === "knobs") return { from: pos - parts[2].length, options: KNOB_OPTIONS };
  if (parts[0] === "korg" && parts.length > 2 && isObjectBranch(parts.slice(0, -1).join("."))) return { from: pos - parts.at(-1).length, options: treeOptions(parts.slice(0, -1).join(".")) };
  if (parts[0] === "korg" && parts.length > 1) return { from: pos - token.length, options: KORG_OPTIONS };
  if (parts.length === 1 && token.length >= 2 && "korg".startsWith(token)) {
    return { from: pos - token.length, options: [{ label: "korg", type: "keyword", detail: say("script.editor.korg"), info: { name: "korg", signature: "korg", text: say("script.editor.korg.text"), params: [], returns: null, allowed: null }, apply: "korg.", retrigger: true }] };
  }
  return null;
}

/**
 * The call the caret is inside: { info, index } with the API entry's facts and the number of the
 * argument being written, or null. `index` is -1 when more arguments stand there than the call takes.
 */
export function callAt(text, pos) {
  const here = scan(text, pos);
  const top = here.stack.at(-1);
  if (here.mode === "comment" || !top || top.kind !== "(" || !top.callee) return null;
  const info = infoFor(top.callee);
  if (!info) return null;
  return { info, index: top.commas < info.params.length ? top.commas : -1 };
}

const TOKENS = new RegExp(`"(?:[^"\\\\\\n]|\\\\.)*"|'(?:[^'\\\\\\n]|\\\\.)*'|0[xX][0-9a-fA-F]+|\\d+|${IDENT}(?:\\.${IDENT})*`, "g");

/**
 * What to say about the token at `pos`: { from, to, info } or null. Names of the API, `korg.key.TAP`
 * and `korg.led.TAP`, an event name in korg.onEvent("..."), a group in korg.app, a handler's parameter
 * and a number that is a key code or an LED number.
 */
export function hoverAt(text, pos) {
  const lineStart = text.lastIndexOf("\n", pos - 1) + 1;
  const end = text.indexOf("\n", pos);
  const line = text.slice(lineStart, end < 0 ? text.length : end);
  for (const m of line.matchAll(TOKENS)) {
    const from = lineStart + m.index;
    const to = from + m[0].length;
    if (pos < from || pos > to) continue;
    const here = scan(text, from);
    if (here.mode !== "code") return null;
    const call = here.stack.at(-1);
    const word = m[0];
    if (/^["']/.test(word)) {
      if (!call) return null;
      const value = word.slice(1, -1);
      if (call.callee === ON_EVENT_DOC.name && call.commas === 0 && EVENT_BY_NAME.has(value)) return { from, to, info: eventInfo(EVENT_BY_NAME.get(value)) };
      if (call.callee === "korg.app" && call.commas === 1 && GROUP_DOCS[value]) return { from, to, info: { name: value, signature: word, text: GROUP_DOCS[value], params: [], returns: null, allowed: null } };
      return null;
    }
    if (/^\d|^0[xX]/.test(word)) {
      const hint = hintAt(text, pos);
      return hint ? { from, to, info: { name: word, signature: word, text: hint, params: [], returns: null, allowed: null } } : null;
    }
    const segments = word.split(".");
    if (segments[0] === "korg") {
      const family = segments[1];
      if (FAMILIES[family] && segments.length === 3) {
        const found = nameOptions(family).find(o => o.label === segments[2]);
        return found ? { from, to, info: found.info } : null;
      }
      if (family === "knobs" && segments.length === 3) {
        const found = KNOB_OPTIONS.find(o => o.label === segments[2]);
        return found ? { from, to, info: found.info } : null;
      }
      const upTo = Math.max(1, segments.findIndex((_, i) => from + segments.slice(0, i + 1).join(".").length >= pos) + 1);
      const path = segments.slice(0, upTo).join(".");
      const whole = infoFor(word, line[to - lineStart] === "(");
      if (whole) return { from, to, info: whole };
      if (infoFor(path)) return { from, to: from + path.length, info: infoFor(path) };
      return family === "key" && segments.length === 2 ? { from, to, info: NAMESPACE_OPTION.info } : null;
    }
    if (segments.length === 1 && call && call.kind === "(" && !call.callee) {
      const owner = here.stack.at(-2);
      const event = owner?.callee === ON_EVENT_DOC.name && owner.commas === 1 ? EVENT_BY_NAME.get(owner.first) : null;
      const index = event?.args.indexOf(word) ?? -1;
      if (index >= 0) return { from, to, info: { name: word, signature: `${word} (${event.name})`, text: EVENT_DOCS[event.name].args[word], params: [], returns: null, allowed: null } };
    }
    return null;
  }
  return null;
}

/** The range a compile error covers: from its column to the end of the word there, or one character. */
export function errorRange(text, error) {
  let start = 0;
  for (let i = 1; i < error.line; i++) {
    const next = text.indexOf("\n", start);
    if (next < 0) break;
    start = next + 1;
  }
  const next = text.indexOf("\n", start);
  const lineEnd = next < 0 ? text.length : next;
  const from = Math.min(start + Math.max(0, error.column - 1), lineEnd);
  const word = /^[\w$.]+/.exec(text.slice(from, lineEnd))?.[0].length ?? 1;
  const to = Math.min(from + word, lineEnd);
  return from === to && from > start ? { from: from - 1, to } : { from, to };
}
