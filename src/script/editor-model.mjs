/**
 * What the plugin editor knows about the script language, as plain functions of the source text and
 * a caret position: completions, the parameter hint of a call, the hover text and the range of a
 * compile error. It reads the contract and the descriptions and never touches a DOM or the editor
 * library, so it runs in Node and the tests drive it directly. site/app/script-editor.mjs wires it to CodeMirror.
 */
import { API, API_BY_NAME, EVENTS, EVENT_BY_NAME, SCRIPT_APPS, LIMITS } from "../../data/script/contract.mjs";
import { API_DOCS, ON_EVENT_DOC, EVENT_DOCS, GROUP_DOCS, NAME_FAMILY_DOCS } from "../../data/script/describe.mjs";
import { KEY_NAMES, LED_NAMES } from "../../data/script/names.mjs";
import { hintAt } from "./names.mjs";

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
  if (arg.kind === "str") return `Text, höchstens ${LIMITS.stringLength} Zeichen`;
  if (arg.kind === "arr") return "ein Feld aus Zahlen von 0 bis 255";
  if (arg.min === INT_MIN && arg.max === INT_MAX) return "ganze Zahl";
  return `${arg.min} bis ${arg.max}`;
}

const list = (items, last = "und") => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} ${last} ${items.at(-1)}`);
const sameSet = (a, b) => a.length === b.length && a.every(n => b.includes(n));

/** Where an API entry may be called, from the events its contract entry lists. */
export function allowedIn(entry) {
  if (sameSet(entry.events, ALL_EVENTS)) return "überall";
  if (sameSet(entry.events, ALL_EVENTS.filter(n => n !== "start" && n !== "save"))) return "in allen Ereignissen außer dem Rumpf und save";
  return `nur ${list(entry.events.map(n => (n === "start" ? "im Rumpf" : `in ${n}`)))}`;
}

/** The facts the editor shows about an API entry. */
function apiInfo(entry) {
  const params = entry.args.map(a => ({ name: a.name, range: rangeText(a) }));
  return {
    name: entry.name,
    signature: `${entry.name}(${params.map(p => p.name).join(", ")})`,
    text: API_DOCS[entry.name],
    params,
    returns: entry.returns === "int" ? "eine ganze Zahl" : null,
    allowed: allowedIn(entry),
  };
}

const ON_EVENT_INFO = Object.freeze({
  name: ON_EVENT_DOC.name,
  signature: ON_EVENT_DOC.signature,
  text: ON_EVENT_DOC.text,
  params: Object.freeze([{ name: "ereignis", range: `der Name eines Ereignisses, zum Beispiel "frame"` }, { name: "handler", range: "eine Pfeilfunktion oder der Name einer Funktion" }]),
  returns: null,
  allowed: "nur ganz oben im Code",
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

const infoFor = name => (name === ON_EVENT_DOC.name ? ON_EVENT_INFO : API_BY_NAME.has(name) ? apiInfo(API_BY_NAME.get(name)) : null);

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

function apiOption(entry) {
  const info = apiInfo(entry);
  const fields = entry.args.map((a, i) => `\${${i + 1}:${a.name}}`).join(", ");
  return { label: entry.name, type: "function", detail: `(${info.params.map(p => p.name).join(", ")})`, info, snippet: `${entry.name}(${fields})` };
}

const NAMESPACE_OPTION = Object.freeze({ label: "korg.key", type: "namespace", detail: "Namen der Tasten", info: { name: "korg.key", signature: "korg.key.NAME", text: NAME_FAMILY_DOCS.key, params: [], returns: null, allowed: null }, apply: "korg.key.", retrigger: true });
const ON_EVENT_OPTION = Object.freeze({ label: ON_EVENT_DOC.name, type: "function", detail: "(ereignis, handler)", info: ON_EVENT_INFO, snippet: `korg.onEvent("\${1:ereignis}", (\${2}) => {\n  \${3}\n});` });

/** The options for every name a plugin may write after `korg.`, with `korg` itself for the first letters. */
const KORG_OPTIONS = Object.freeze([...API.map(apiOption), ON_EVENT_OPTION, NAMESPACE_OPTION]);

function nameOptions(family) {
  return FAMILIES[family].map(n => ({
    label: n.name,
    type: "constant",
    detail: String(n.value),
    info: { name: `korg.${family}.${n.name}`, signature: `korg.${family}.${n.name}`, text: family === "key" ? `Die Taste ${n.label}, Code ${n.value}.` : `Die LED ${n.label}, Nummer ${n.value}.`, params: [], returns: null, allowed: null },
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
      return { from, options: SCRIPT_APPS.groups.map(g => ({ label: g, type: "enum", detail: "Gruppe", info: { name: g, signature: `"${g}"`, text: GROUP_DOCS[g], params: [], returns: null, allowed: null }, ...(blank ? { apply: `${g}");` } : {}) })) };
    }
    return null;
  }
  const token = PATH_END.exec(text.slice(Math.max(0, pos - 80), pos))?.[0];
  if (!token) return null;
  const parts = token.split(".");
  if (parts[0] === "korg" && parts.length === 3 && (parts[1] === "key" || parts[1] === "led")) {
    return { from: pos - parts[2].length, options: nameOptions(parts[1]) };
  }
  if (parts[0] === "korg" && parts.length > 1) return { from: pos - token.length, options: KORG_OPTIONS };
  if (parts.length === 1 && token.length >= 2 && "korg".startsWith(token)) {
    return { from: pos - token.length, options: [{ label: "korg", type: "keyword", detail: "die Funktionen der Electribe", info: { name: "korg", signature: "korg", text: "Alle Funktionen der Electribe beginnen mit korg., zum Beispiel korg.display.text oder korg.led.", params: [], returns: null, allowed: null }, apply: "korg.", retrigger: true }] };
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
      const upTo = Math.max(1, segments.findIndex((_, i) => from + segments.slice(0, i + 1).join(".").length >= pos) + 1);
      const path = segments.slice(0, upTo).join(".");
      const whole = infoFor(word);
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
