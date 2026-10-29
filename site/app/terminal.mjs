/**
 * Terminal page: JavaScript with the KORG library (src/korg.mjs) in scope.
 * Arrow up and down walk the history.
 *
 * With the emulator connected a script runs there. With the real Electribe
 * connected it runs in the emulator first, shows what that did step by step,
 * and only a script that passed can be sent on: the device gets the recorded
 * messages and nothing else (src/terminal.mjs, src/rehearsal.mjs). There is
 * no way here to skip the rehearsal.
 */
import { el } from "./fields.mjs";
import { HELP } from "../../src/korg.mjs";
import { NOTE_LIMIT } from "../../src/terminal.mjs";
import { describeUnits } from "../../src/rehearsal.mjs";
import { completionsAt } from "../../src/script/editor-model.mjs";
import { toast } from "./toast.mjs";
import { t } from "./i18n.mjs";

function show(value) {
  if (value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value?.summary === "function") return value.summary();
  if (value instanceof Uint8Array) return `Uint8Array(${value.length}) ${Array.from(value.slice(0, 32), b => b.toString(16).padStart(2, "0")).join(" ")}${value.length > 32 ? " …" : ""}`;
  if (Array.isArray(value) && value.every(v => typeof v === "string")) return value.join("\n");
  try { return JSON.stringify(value, (k, v) => (typeof v === "bigint" ? String(v) : v), 2); } catch { return String(value); }
}

const pill = (tone, word) => {
  const p = el("span", { className: "cee-status", textContent: word });
  p.dataset.tone = tone;
  return p;
};

/** The names the library KORG has, taken from its help lines, and run(). */
const LIBRARY = [...new Set([...HELP.join("\n").matchAll(/^(KORG\.[\w.]+)/gm)].map(m => m[1])), "run"];

/** What Tab can complete at the caret: { from, names } or null. The names of korg.* come from the plugin editor, those of KORG.* from the help. */
export function completionsFor(text, pos) {
  const token = /[A-Za-z_][\w.]*$/.exec(text.slice(0, pos))?.[0];
  if (!token) return null;
  if (/^KORG/.test(token) || (token.length >= 2 && "run".startsWith(token))) {
    const names = LIBRARY.filter(n => n.startsWith(token) && n !== token);
    return names.length ? { from: pos - token.length, names } : null;
  }
  const found = completionsAt(text, pos);
  if (!found) return null;
  const prefix = text.slice(found.from, pos);
  const names = found.options.map(o => o.label).filter(l => l.toLowerCase().startsWith(prefix.toLowerCase()) && l !== prefix);
  return names.length ? { from: found.from, names } : null;
}

const commonPrefix = list => list.reduce((a, b) => { let i = 0; while (i < a.length && a[i] === b[i]) i++; return a.slice(0, i); });

const deviceNote = () => t("console.deviceNote");

/** `run("name")` starts a saved script; a line that begins with `korg.` is script language and runs in the run area, not as JavaScript with KORG. */
function scriptInput(code) {
  const call = /^\s*run\(\s*(["'`])([^"'`]+)\1\s*\)\s*;?\s*$/.exec(code);
  if (call) return { run: call[2] };
  if (/^\s*korg\./.test(code)) return { snippet: code };
  return null;
}

/**
 * `lack()` gives the reason when the firmware in the emulator cannot take commands (Hacktribe's SysEx), else null.
 * `power()` switches the emulator on (the command start), `forward` is the switch in the navbar that lets scripts
 * go on to a connected Electribe.
 */
export function terminalPanel(root, { terminal, device, scripts = null, lack = () => null, power = async () => {}, forward = null }) {
  // A terminal: the output scrolls and the line you type stands at its end, not in a bar below.
  const lines = el("div", { className: "cee-term-lines", role: "log", "aria-live": "polite" });
  const input = el("textarea", { className: "cee-term-input", id: "cee-term-input", rows: 1, spellcheck: false, autocomplete: "off" });
  input.setAttribute("aria-label", t("console.command"));
  const log = el("div", { className: "cee-term-log", id: "cee-term-log" }, [lines, el("div", { className: "cee-term-entry" }, [el("span", { className: "cee-term-caret", ariaHidden: "true", textContent: ">" }), input])]);
  log.addEventListener("click", e => { if (!e.target.closest("a, button, textarea") && !getSelection()?.toString()) input.focus(); });
  const run = { disabled: false };            // a script is running; Enter waits for it
  const send = el("button", { type: "button", className: "btn sm cee-primary", id: "cee-term-send", textContent: t("console.send"), disabled: true, hidden: true });
  // Where the commands go, for screen readers; on the page the toast says it once when it changes; not when the firmware
  // takes no commands, that came at every start of Korg's firmware and only confused (a typed command says it).
  const target = el("p", { className: "cee-term-target ui-sr-only", id: "cee-term-target", role: "status", hidden: true });
  let toldTarget = "";
  const limit = el("p", { className: "muted", id: "cee-term-limit", hidden: true, textContent: NOTE_LIMIT });
  const rehearsal = el("div", { className: "cee-term-rehearsal", id: "cee-term-rehearsal", "aria-live": "polite", hidden: true });
  const sendNote = el("p", { className: "muted", id: "cee-term-send-note", "aria-live": "polite" });
  const history = [];
  let back = 0;
  let current = null;
  let invalidated = false;

  const line = (kind, text) => {
    lines.append(el("pre", { className: `cee-term-line cee-term-${kind}`, textContent: text }));
    log.scrollTop = log.scrollHeight;
  };
  line("out", t("console.welcome"));
  const grow = () => { input.rows = Math.min(12, input.value.split("\n").length); };

  function update() {
    const mode = terminal.mode;
    const missing = lack();
    target.hidden = mode !== "device" && !missing;
    target.replaceChildren(...(missing ? [pill("error", t("console.noCommands.tag")), ` ${t("console.noCommands")}`] : [pill("warn", t("console.viaEmu")), ` ${deviceNote()}`]));
    const told = target.hidden ? "" : missing ? t("console.noCommands") : deviceNote();
    if (told && told !== toldTarget && !missing) toast(told, "info");
    toldTarget = told;
    input.placeholder = mode === "device" ? t("console.placeholder") : "";
    send.hidden = mode !== "device";
    limit.hidden = mode !== "device";
    if (mode !== "device") { current = null; rehearsal.hidden = true; }
    updateSend();
  }

  /**
   * The send button works only for the rehearsal of exactly the text that
   * stands in the box. Any change throws the rehearsal away for good, even if
   * the text is put back: a rehearsal belongs to the run that was seen.
   */
  function updateSend() {
    if (current && input.value !== current.code) invalidated = true;
    const can = current && !invalidated ? terminal.canSend(current, input.value) : { ok: false };
    send.disabled = !can.ok || run.disabled;
    const note = rehearsal.querySelector(".cee-term-stale");
    if (note) note.hidden = !invalidated;
  }

  function showRehearsal(record, sent = false) {
    const units = describeUnits(record);
    const frames = record.units.reduce((n, u) => n + u.steps.length + (u.cleanup?.steps.length ?? 0), 0);
    const head = sent
      ? [pill("ok", t("console.sent")), ` ${t(record.units.length === 1 ? "console.sent.one" : "console.sent.many", { count: record.units.length })}`]
      : record.ok
      ? [pill("ok", t("console.passed")), ` ${t(record.units.length === 1 ? "console.passed.one" : "console.passed.many", { count: record.units.length, frames })}`]
      : [pill("error", t("console.failed")), ` ${t("console.failed.text", { reason: record.reason })}`];
    rehearsal.replaceChildren(...[
      el("p", { className: "cee-term-rehearsal-head" }, head),
      record.ok && !record.sendable ? el("p", { className: "muted", textContent: record.whyNot }) : null,
      ...units.map(u => el("details", { className: "ui-details" }, [
        el("summary", {}, [pill(u.ok ? "ok" : "error", u.ok ? "ok" : t("common.error")), ` ${u.title}: ${u.note}`]),
        el("ol", { className: "cee-term-steps" }, u.steps.map(s => el("li", { textContent: s.text, className: s.failed ? "cee-term-failed" : "" }))),
      ])),
      el("p", { className: "cee-term-stale muted", hidden: true, textContent: t("console.stale") }),
    ].filter(Boolean));
    rehearsal.hidden = false;
  }

  async function execute() {
    const code = input.value.trim();
    if (!code) return;
    history.push(code);
    back = 0;
    const mode = terminal.mode;
    line("in", `> ${code}`);
    input.value = "";
    grow();
    if (code === "help") { line("out", [t("console.help.start"), ...HELP].join("\n")); return; }
    if (code === "start") {
      try { line("out", await power()); } catch (e) { line("error", e.message); }
      return;
    }
    if (mode === "device") input.value = code;      // the rehearsal belongs to the text that stays in the box
    run.disabled = true;
    send.disabled = true;
    sendNote.textContent = "";
    try {
      const script = scripts ? scriptInput(code) : null;
      if (script) {
        input.value = "";
        line("out", script.run !== undefined ? scripts.runNamed(script.run) : scripts.runSnippet(script.snippet));
        return;
      }
      const missing = lack();
      if (missing) throw new Error(t("console.noCommands"));
      if (mode === "emulator") {
        const out = show(await terminal.runDirect(code, { print: text => line("out", text) }));
        if (out) line("out", out);
      } else {
        current = null;
        rehearsal.hidden = true;
        const record = await terminal.rehearse(input.value, { print: text => line("out", text) });
        const out = show(record.value);
        if (out) line("out", out);
        if (!record.ok) line("error", record.reason);
        else if (!record.sendable) line("out", record.whyNot);
        current = record;
        invalidated = false;
        showRehearsal(record);
      }
    } catch (e) {
      line("error", e.message);
    } finally {
      run.disabled = false;
      updateSend();
      input.focus();
    }
  }

  async function sendToDevice() {
    const record = current;
    run.disabled = true;
    send.disabled = true;
    try {
      const res = await terminal.send(record, input.value, {
        onStep: ({ unit, step, of, units }) => { sendNote.textContent = t("console.progress", { unit: unit + 1, units, step, of }); },
      });
      if (res.ok) {
        const text = t(res.done.length === 1 ? "console.done.one" : "console.done.many", { count: res.done.length });
        line("out", text);
        toast(text, "ok");
        sendNote.textContent = "";
        device.log?.(t("console.logLine", { text }), "ok");
        showRehearsal(record, true);
      } else if (res.refused) {
        line("error", t("console.refused", { error: res.error.message }));
        toast(t("console.refused", { error: res.error.message }), "error");
      } else {
        const text = t("console.stopped", { unit: res.unit + 1, step: res.step, error: res.error.message });
        line("error", text);
        toast(text, "error");
        sendNote.textContent = "";
        device.log?.(t("console.logLine", { text }), "error");
        if (device.session?.blocked) { line("error", t("console.arrived")); device.showDecision?.(); }
      }
    } catch (e) {
      line("error", e.message);
    } finally {
      run.disabled = false;
      updateSend();
    }
  }

  // Tab completes korg.* and KORG.* at the caret; with several choices it completes the common start and lists them.
  function complete() {
    const at = input.selectionStart;
    const found = completionsFor(input.value, at);
    if (!found) return false;
    input.setRangeText(commonPrefix(found.names), found.from, at, "end");
    if (found.names.length > 1) line("out", found.names.join("   "));
    updateSend();
    return true;
  }

  input.addEventListener("keydown", e => {
    if (e.key === "Tab" && !e.shiftKey && !e.ctrlKey && !e.altKey && !e.metaKey && input.selectionStart === input.selectionEnd && complete()) { e.preventDefault(); return; }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!run.disabled) execute(); return; }
    if ((e.key === "ArrowUp" || e.key === "ArrowDown") && !input.value.includes("\n")) {
      const next = Math.max(0, Math.min(history.length, back + (e.key === "ArrowUp" ? 1 : -1)));
      if (next === back) return;
      e.preventDefault();
      back = next;
      input.value = back ? history[history.length - back] : "";
      updateSend();
    }
  });
  input.addEventListener("input", () => { grow(); updateSend(); });
  send.addEventListener("click", sendToDevice);
  forward?.addEventListener("change", () => {
    if (forward.checked && !device.session) {
      forward.checked = false;
      toast(t("console.forwardFirst"), "error");
    }
    update();
  });

  root.replaceChildren(
    target,
    limit,
    log,
    el("div", { className: "actions cee-term-send", hidden: false }, [send]),
    sendNote,
    rehearsal,
  );
  update();
  return { update, execute: code => { input.value = code; return execute(); } };
}
