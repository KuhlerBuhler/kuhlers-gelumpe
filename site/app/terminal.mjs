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

const TARGETS = {
  none: ["neutral", "nicht verbunden", "Mit dem Emulator oder der Electribe verbinden."],
  emulator: ["ok", "Emulator", "Befehle gehen an den Emulator, durch denselben Türsteher wie im Editor."],
  device: ["warn", "Gerät über Emulator", "Jedes Skript läuft erst im Emulator. Nur ein bestandenes kann ans Gerät, und dann genau die Nachrichten der Probe. Eine Änderung am Text verwirft die Probe."],
};

/** `run("name")` starts a saved script; a line that begins with `korg.` is script language and runs in the run area, not as JavaScript with KORG. */
function scriptInput(code) {
  const call = /^\s*run\(\s*(["'`])([^"'`]+)\1\s*\)\s*;?\s*$/.exec(code);
  if (call) return { run: call[2] };
  if (/^\s*korg\./.test(code)) return { snippet: code };
  return null;
}

/** `lack()` gives the reason when the firmware in the emulator cannot take commands (Hacktribe's SysEx), else null. */
export function terminalPanel(root, { terminal, device, scripts = null, lack = () => null }) {
  const log = el("div", { className: "cee-term-log", id: "cee-term-log", role: "log", "aria-live": "polite" });
  const input = el("textarea", { className: "cee-term-input", id: "cee-term-input", rows: 1, spellcheck: false, autocomplete: "off" });
  input.setAttribute("aria-label", "Befehl");
  const run = el("button", { type: "button", className: "btn sm primary", id: "cee-term-run", textContent: "Ausführen" });
  const send = el("button", { type: "button", className: "btn sm", id: "cee-term-send", textContent: "An das Gerät senden", disabled: true, hidden: true });
  const connect = el("button", { type: "button", className: "btn sm", id: "cee-term-connect", textContent: "Mit Emulator verbinden" });
  const target = el("p", { className: "cee-term-target", id: "cee-term-target", role: "status" });
  const limit = el("p", { className: "muted", id: "cee-term-limit", hidden: true, textContent: NOTE_LIMIT });
  const rehearsal = el("div", { className: "cee-term-rehearsal", id: "cee-term-rehearsal", "aria-live": "polite", hidden: true });
  const sendNote = el("p", { className: "muted", id: "cee-term-send-note", "aria-live": "polite" });
  const history = [];
  let back = 0;
  let current = null;
  let invalidated = false;

  const line = (kind, text) => {
    log.append(el("pre", { className: `cee-term-line cee-term-${kind}`, textContent: text }));
    log.scrollTop = log.scrollHeight;
  };
  line("out", "Tippe help für die Befehlsliste.");

  function update() {
    const mode = terminal.mode;
    const [tone, word, text] = TARGETS[mode];
    const missing = mode === "none" ? null : lack();
    target.replaceChildren(el("span", {}, ["Ziel: "]), pill(missing ? "error" : tone, missing ? "nimmt keine Befehle an" : word), el("span", { textContent: missing ? "" : ` ${text}` }));
    run.textContent = mode === "device" ? "Im Emulator proben" : "Ausführen";
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
      ? [pill("ok", "Gesendet"), ` Ans Gerät gegangen: ${record.units.length} ${record.units.length === 1 ? "Einheit" : "Einheiten"}, die Nachrichten dieser Probe.`]
      : record.ok
      ? [pill("ok", "Probe bestanden"), ` ${record.units.length} ${record.units.length === 1 ? "Einheit" : "Einheiten"}, ${frames} Nachrichten, die Firmware im Emulator läuft und antwortet weiter. Am Gerät ist noch nichts passiert.`]
      : [pill("error", "Probe nicht bestanden"), ` ${record.reason} Ans Gerät geht nichts.`];
    rehearsal.replaceChildren(...[
      el("p", { className: "cee-term-rehearsal-head" }, head),
      record.ok && !record.sendable ? el("p", { className: "muted", textContent: record.whyNot }) : null,
      ...units.map(u => el("details", { className: "ui-details" }, [
        el("summary", {}, [pill(u.ok ? "ok" : "error", u.ok ? "ok" : "Fehler"), ` ${u.title}: ${u.note}`]),
        el("ol", { className: "cee-term-steps" }, u.steps.map(s => el("li", { textContent: s.text, className: s.failed ? "cee-term-failed" : "" }))),
      ])),
      el("p", { className: "cee-term-stale muted", hidden: true, textContent: "Der Text ist geändert, die Probe gilt nicht mehr. Neu im Emulator proben." }),
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
    if (code === "help") { input.value = ""; line("out", HELP.join("\n")); return; }
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
      if (mode === "none") throw new Error("Erst im Bereich Gerät verbinden: mit dem Emulator, oder mit der Electribe, dann geht alles erst durch den Emulator.");
      const missing = lack();
      if (missing) throw new Error("Die Firmware im Emulator nimmt keine Befehle an.");
      if (mode === "emulator") {
        input.value = "";
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
        onStep: ({ unit, step, of, units }) => { sendNote.textContent = `Am Gerät: Einheit ${unit + 1} von ${units}, Nachricht ${step} von ${of}.`; },
      });
      if (res.ok) {
        const text = `Ans Gerät gesendet: ${res.done.length} ${res.done.length === 1 ? "Einheit" : "Einheiten"}, genau die Nachrichten der Probe, jede Bestätigung wie dort.`;
        line("out", text);
        toast(text, "ok");
        sendNote.textContent = "";
        device.log?.(`Terminal: ${text}`, "ok");
        showRehearsal(record, true);
      } else if (res.refused) {
        line("error", `Nicht gesendet. Ist die Electribe noch verbunden? (${res.error.message})`);
        toast(`Nicht gesendet. Ist die Electribe noch verbunden? (${res.error.message})`, "error");
      } else {
        const text = `Am Gerät gestoppt bei Einheit ${res.unit + 1}, Nachricht ${res.step}: ${res.error.message} Danach ging nichts mehr raus.`;
        line("error", text);
        toast(text, "error");
        sendNote.textContent = "";
        device.log?.(`Terminal: ${text}`, "error");
        if (device.session?.blocked) { line("error", "Am Gerät ist etwas angekommen. Entscheide im Bereich Gerät, ob die Sicherung zurückgespielt wird."); device.showDecision?.(); }
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
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); execute(); return; }
    if ((e.key === "ArrowUp" || e.key === "ArrowDown") && !input.value.includes("\n")) {
      const next = Math.max(0, Math.min(history.length, back + (e.key === "ArrowUp" ? 1 : -1)));
      if (next === back) return;
      e.preventDefault();
      back = next;
      input.value = back ? history[history.length - back] : "";
      updateSend();
    }
  });
  input.addEventListener("input", updateSend);
  run.addEventListener("click", execute);
  send.addEventListener("click", sendToDevice);
  connect.addEventListener("click", () => device.connectEmulator());

  root.replaceChildren(
    el("div", { className: "cee-term-head" }, [target, connect]),
    limit,
    log,
    el("div", { className: "cee-term-prompt" }, [input, run, send]),
    sendNote,
    rehearsal,
  );
  update();
  return { update, execute: code => { input.value = code; return execute(); } };
}
