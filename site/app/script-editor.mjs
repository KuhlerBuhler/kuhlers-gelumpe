/**
 * The code editor of the plugins page: CodeMirror 6 (the vendored bundle, nothing from the network)
 * wired to what the page knows about the script language. The completions, the parameter hint of a call,
 * the hover text and the error ranges come from src/script/editor-model.mjs, the highlighting from
 * src/script/highlight.mjs; this file only turns them into editor extensions.
 */
import {
  EditorState, StateField, StateEffect, Compartment, Prec,
  EditorView, GutterMarker, gutter, keymap, highlightSpecialChars, hoverTooltip, showTooltip,
  defaultKeymap, history, historyKeymap,
  StreamLanguage, bracketMatching, indentOnInput, syntaxHighlighting, classHighlighter,
  autocompletion, snippet, startCompletion, acceptCompletion,
  setDiagnostics,
} from "../vendor/codemirror.mjs";
import { completionsAt, callAt, hoverAt, errorRange } from "../../src/script/editor-model.mjs";
import { scriptStream } from "../../src/script/highlight.mjs";

const node = (tag, className, text) => {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (text !== undefined) n.textContent = text;
  return n;
};

/** The tooltip body for an info object of the editor model: signature, sentence, parameters, where it is allowed. */
function infoDom(info, active = -2) {
  const dom = node("div", "cee-script-tip");
  const sig = node("code", "cee-script-tip-sig");
  const open = info.signature.indexOf("(");
  if (info.params.length && open > 0 && info.signature.endsWith(")")) {
    sig.append(info.signature.slice(0, open + 1));
    info.params.forEach((p, i) => {
      if (i) sig.append(", ");
      const word = node("span", i === active ? "cee-script-tip-active" : "", p.name);
      sig.append(word);
    });
    sig.append(")");
  } else sig.textContent = info.signature;
  dom.append(sig);
  if (active === -1) dom.append(node("p", "cee-script-tip-note", "Mehr Argumente, als der Aufruf nimmt."));
  if (active >= 0) dom.append(node("p", "cee-script-tip-note", `${info.params[active].name}: ${info.params[active].range}`));
  if (active === -2) {
    dom.append(node("p", "cee-script-tip-text", info.text));
    if (info.params.length) {
      const list = node("ul", "cee-script-tip-params");
      for (const p of info.params) list.append(node("li", "", `${p.name}: ${p.range}`));
      dom.append(list);
    }
    const facts = [info.returns ? `Gibt ${info.returns} zurück.` : null, info.allowed ? `Erlaubt: ${info.allowed}.` : null].filter(Boolean);
    if (facts.length) dom.append(node("p", "cee-script-tip-note", facts.join(" ")));
  }
  return dom;
}

class LineNumber extends GutterMarker {
  constructor(n, state) { super(); this.n = n; this.state = state; }
  eq(other) { return other.n === this.n && other.state === this.state; }
  toDOM() {
    const span = node("span", "cee-script-line", String(this.n));
    if (this.state) span.dataset.state = this.state;
    return span;
  }
}

const setMarks = StateEffect.define();
const noMarks = { covered: new Set(), missing: new Set(), error: null };
const marksField = StateField.define({
  create: () => noMarks,
  update(value, tr) {
    for (const e of tr.effects) if (e.is(setMarks)) return e.value;
    return value;
  },
});

const lineGutter = gutter({
  class: "cee-script-gutter",
  lineMarker(view, line) {
    const n = view.state.doc.lineAt(line.from).number;
    const marks = view.state.field(marksField);
    return new LineNumber(n, marks.error === n ? "error" : marks.missing.has(n) ? "missing" : marks.covered.has(n) ? "covered" : "");
  },
  lineMarkerChange: update => update.transactions.some(tr => tr.effects.some(e => e.is(setMarks))),
  initialSpacer: view => new LineNumber("8".repeat(Math.max(2, String(view.state.doc.lines).length)), ""),
  updateSpacer: (spacer, update) => (String(update.state.doc.lines).length > spacer.n.length ? new LineNumber("8".repeat(String(update.state.doc.lines).length), "") : spacer),
});

const focusEffect = StateEffect.define();
const hintTooltip = state => {
  const sel = state.selection.main;
  if (state.readOnly) return null;
  const found = callAt(state.doc.toString(), sel.head);
  return found ? { pos: sel.head, above: true, strictSide: true, create: () => ({ dom: infoDom(found.info, found.index) }) } : null;
};
const hintField = StateField.define({
  create: () => ({ focused: false, tip: null }),
  update(value, tr) {
    let focused = value.focused;
    for (const e of tr.effects) if (e.is(focusEffect)) focused = e.value;
    if (!tr.docChanged && !tr.selection && focused === value.focused) return value;
    return { focused, tip: focused ? hintTooltip(tr.state) : null };
  },
  provide: field => showTooltip.from(field, value => value.tip),
});

const toCompletion = option => ({
  label: option.label,
  type: option.type,
  detail: option.detail,
  info: () => infoDom(option.info),
  apply: option.snippet
    ? (view, completion, from, to) => snippet(option.snippet)(view, completion, from, to)
    : option.apply !== undefined
      ? (view, completion, from, to) => {
        view.dispatch({ changes: { from, to, insert: option.apply }, selection: { anchor: from + option.apply.length }, userEvent: "input.complete" });
        if (option.retrigger) startCompletion(view);
      }
      : undefined,
});

function completionSource(context) {
  if (context.state.readOnly) return null;
  const found = completionsAt(context.state.doc.toString(), context.pos);
  return found ? { from: found.from, options: found.options.map(toCompletion), validFor: /^[\w.$]*$/ } : null;
}

const hoverSource = hoverTooltip((view, pos, side) => {
  const found = hoverAt(view.state.doc.toString(), pos);
  if (!found || (found.from === pos && side < 0) || (found.to === pos && side > 0)) return null;
  return { pos: found.from, end: found.to, above: true, create: () => ({ dom: infoDom(found.info) }) };
}, { hideOnChange: true });

/**
 * @param {HTMLElement} parent where the editor goes
 * @param {{ label: string, onInput: () => void, onCaret: () => void }} options `onInput` runs after every edit, `onCaret` when the caret moved
 */
export function createScriptEditor(parent, { label, onInput = () => {}, onCaret = () => {} }) {
  const language = StreamLanguage.define(scriptStream);
  const readOnly = new Compartment();
  const extensions = [
    marksField,
    lineGutter,
    highlightSpecialChars(),
    history(),
    indentOnInput(),
    bracketMatching(),
    language.extension,
    syntaxHighlighting(classHighlighter),
    autocompletion({ override: [completionSource], icons: true, maxRenderedOptions: 80 }),
    hoverSource,
    hintField,
    EditorView.focusChangeEffect.of((state, focusing) => focusEffect.of(focusing)),
    // Tab takes the selected suggestion while the list is open, like Enter. Without a list it does nothing here,
    // so Tab still leaves the editor for the next control (keyboard access) or moves between snippet fields.
    Prec.highest(keymap.of([{ key: "Tab", run: acceptCompletion }])),
    keymap.of([...defaultKeymap, ...historyKeymap]),
    EditorState.tabSize.of(2),
    EditorView.contentAttributes.of({ id: "cee-script-text", tabindex: "0", "aria-label": label, spellcheck: "false", autocapitalize: "off", autocorrect: "off" }),
    EditorView.updateListener.of(update => {
      if (update.docChanged) onInput();
      else if (update.selectionSet) onCaret();
    }),
    readOnly.of([]),
  ];
  const makeState = doc => EditorState.create({ doc, extensions });
  const view = new EditorView({ state: makeState(""), parent });
  parent.view = view;
  const lock = on => view.dispatch({ effects: readOnly.reconfigure(on ? [EditorState.readOnly.of(true), EditorView.contentAttributes.of({ "aria-readonly": "true" })] : []) });

  return {
    view,
    get value() { return view.state.doc.toString(); },
    /** Replace the text for another plugin: the undo history starts anew and the caret goes to the top. */
    load(text) { view.setState(makeState(text)); },
    get caret() { return view.state.selection.main.head; },
    get readOnly() { return view.state.readOnly; },
    setReadOnly(on) { if (on !== view.state.readOnly) lock(on); },
    focus() { view.focus(); },
    setMarks(marks) { view.dispatch({ effects: setMarks.of(marks) }); },
    /** Underline the compile errors in the text: [{ line, column, message }]. */
    setErrors(errors) {
      const text = view.state.doc.toString();
      view.dispatch(setDiagnostics(view.state, errors.map(e => ({ ...errorRange(text, e), severity: "error", message: e.message }))));
    },
    /** Put the caret on a compile error: its word is selected, the editor scrolls there and takes the focus. */
    jump(error) {
      const range = errorRange(view.state.doc.toString(), error);
      view.dispatch({ selection: { anchor: range.from, head: range.to }, scrollIntoView: true });
      view.focus();
    },
    /** Put `text` at the caret; `back` characters before it are replaced (what was typed of a name). */
    insert(text, back = 0) {
      if (view.state.readOnly) return;
      const { from, to } = view.state.selection.main;
      view.dispatch({ changes: { from: from - back, to, insert: text }, selection: { anchor: from - back + text.length }, userEvent: "input" });
      view.focus();
    },
  };
}
