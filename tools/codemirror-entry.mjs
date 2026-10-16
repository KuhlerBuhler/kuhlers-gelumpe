/**
 * The one entry the CodeMirror bundle is built from (tools/build-codemirror.mjs): only what
 * site/app/script-editor.mjs imports, so the rest of CodeMirror stays out of site/vendor/codemirror.mjs.
 * Adding an export here means rebuilding the bundle, and test/vendor.test.mjs fails until that is done.
 */
export { EditorState, StateField, StateEffect, Compartment, Prec } from "@codemirror/state";
export { EditorView, GutterMarker, gutter, keymap, highlightActiveLine, highlightSpecialChars, hoverTooltip, showTooltip } from "@codemirror/view";
export { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
export { StreamLanguage, bracketMatching, indentOnInput, syntaxHighlighting } from "@codemirror/language";
export { classHighlighter } from "@lezer/highlight";
export { autocompletion, snippet, startCompletion, acceptCompletion } from "@codemirror/autocomplete";
export { setDiagnostics } from "@codemirror/lint";
