/**
 * The plugins page (code name: scripts): templates and own plugins, the editor with its compile
 * result, and the run area. A plugin leaves as a file only after a probe of
 * exactly this text (src/script/gate.mjs).
 */
import { el } from "./fields.mjs";
import { icon } from "./icons.mjs";
import { simPanel } from "./sim-panel.mjs";
import { drawDisplay } from "./emulator.mjs";
import { PADS } from "../../data/panel.mjs";
import { parseMarkdown } from "./markdown.mjs";
import { toast } from "./toast.mjs";
import { createScriptEditor } from "./script-editor.mjs";
import { compile, formatError } from "../../src/script/compiler.mjs";
import { decodeBlob, markProbed } from "../../src/script/blob.mjs";
import { LIMITS, BUDGET, ARCHIVE, SCRIPT_APPS } from "../../data/script/contract.mjs";
import { PRESETS } from "../../data/script/presets.mjs";
import { TEMPLATES, templateSource } from "../../data/script/templates.mjs";
import { KEY_NAMES, LED_NAMES } from "../../data/script/names.mjs";
import { hintAt } from "../../src/script/names.mjs";
import { Workspace, sourceKey, validName } from "../../src/script/workspace.mjs";
import { SimDevice, probe as runProbe, FRAME_MS } from "../../src/script/sim.mjs";
import { exportGate } from "../../src/script/gate.mjs";
import { packAll, packBlech, parseBlech } from "../../src/script/archive.mjs";
import { storePlugin } from "../../src/usb-update.mjs";

const EXIT_KEY = KEY_NAMES.find(n => n.name === "EXIT").value;

const pill = (tone, word) => {
  const p = el("span", { className: "cee-status", textContent: word });
  p.dataset.tone = tone;
  return p;
};

function download(bytes, name) {
  const blob = new Blob([bytes], { type: "application/octet-stream" });
  const a = el("a", { href: URL.createObjectURL(blob), download: name });
  document.body.append(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
}

const ask = async (options, fallback) => (window.ui?.prompt ? window.ui.prompt(options) : fallback);

/** The second step of "Neues Plugin": which kind to start from. Resolves to a template id, or null when the user cancels. */
function askKind() {
  if (!window.ui?.openDialog) return Promise.resolve(TEMPLATES[0].id);
  return new Promise(resolve => {
    const hint = el("p", { className: "muted", id: "cee-script-kind-hint", textContent: TEMPLATES[0].description });
    hint.setAttribute("aria-live", "polite");
    const radios = TEMPLATES.map((t, i) => el("input", { type: "radio", name: "cee-script-kind", value: t.id, checked: i === 0, autofocus: i === 0 }));
    const group = el("div", { className: "ui-segmented", id: "cee-script-kind-options", role: "radiogroup" }, TEMPLATES.map((t, i) => el("label", { className: "ui-segmented-option" }, [radios[i], el("span", { textContent: t.label })])));
    group.setAttribute("aria-label", "Art des Plugins");
    const chosen = () => radios.find(r => r.checked)?.value ?? TEMPLATES[0].id;
    const dialog = el("dialog", { className: "ui-dialog ui-dialog-narrow", id: "cee-script-kind" });
    dialog.setAttribute("aria-labelledby", "cee-script-kind-title");
    dialog.append(el("form", { method: "dialog", className: "ui-dialog-box" }, [
      el("header", { className: "ui-dialog-head" }, el("h2", { className: "ui-dialog-title", id: "cee-script-kind-title", textContent: "Welche Art von Plugin?" })),
      el("div", { className: "ui-dialog-body" }, [group, hint]),
      el("footer", { className: "ui-dialog-foot" }, [
        el("button", { type: "submit", className: "btn", value: "cancel", textContent: "Abbrechen", formNoValidate: true }),
        el("button", { type: "submit", className: "btn primary", value: "ok", textContent: "Anlegen" }),
      ]),
    ]));
    for (const r of radios) {
      r.addEventListener("change", () => { hint.textContent = TEMPLATES.find(t => t.id === chosen())?.description ?? ""; });
      // Enter in a radio would press the first submit button, which is Cancel.
      r.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); dialog.close("ok"); } });
    }
    dialog.addEventListener("close", () => {
      resolve(dialog.returnValue === "ok" ? chosen() : null);
      setTimeout(() => dialog.remove(), 0);
    }, { once: true });
    document.body.append(dialog);
    window.ui.openDialog(dialog);
  });
}
const confirmed = async options => (window.ui?.confirm ? window.ui.confirm(options) : false);

export function scriptsPanel(root, { storage = null, sub = null, session = () => null } = {}) {
  /** A packed .blech onto the connected device's card; IMPORT PLUGIN in the BLECH menu then lists it. */
  async function toDevice(bytes, id, button) {
    const s = session();
    if (!s) { toast("Erst auf der Seite Gerät die Electribe verbinden.", "error"); return; }
    button.disabled = true;
    try {
      const name = await storePlugin(s, id, bytes);
      toast(`${name}.blech liegt auf der Karte. Am Gerät BLECH, IMPORT PLUGIN, ENTER, dann einschalten.`, "ok");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      button.disabled = false;
    }
  }

  const workspace = new Workspace(storage);
  const saved = new Map();
  const values = { load: name => saved.get(name) ?? null, save: records => records.forEach(r => saved.set(r.name, r)) };
  let current = null;
  let built = null;
  let marks = { covered: new Set(), missing: new Set(), error: null };
  let live = null;
  let recording = false;
  let saveTimer = null;

  const name = el("input", { className: "input", id: "cee-script-name", type: "text", maxLength: LIMITS.nameLength, spellcheck: false, autocomplete: "off" });
  const editorHost = el("div", { className: "cee-script-editor", id: "cee-script-editor" });
  const editor = createScriptEditor(editorHost, { label: "Plugin-Code", onInput: () => queueMicrotask(onInput), onCaret: () => caretHelp() });
  const status = el("p", { className: "muted cee-script-status", id: "cee-script-status", role: "status" });
  const hint = el("p", { className: "muted cee-script-hint", id: "cee-script-hint", role: "status" });
  const namesFilter = el("input", { className: "input", id: "cee-names-filter", type: "search", placeholder: "Filter, zum Beispiel TAP oder Pad 3", spellcheck: false, autocomplete: "off" });
  namesFilter.setAttribute("aria-label", "Namen filtern");
  const namesBody = el("div", { className: "cee-names-body", id: "cee-names-body" });
  const problems = el("ul", { className: "cee-script-problems", id: "cee-script-problems" });
  const log = el("ul", { className: "cee-script-log", id: "cee-script-log", "aria-live": "polite" });
  const presetList = el("ul", { className: "ui-list cee-pattern-list", id: "cee-script-presets" });
  const ownList = el("ul", { className: "ui-list cee-pattern-list", id: "cee-script-own" });
  const ownEmpty = el("p", { className: "muted cee-ws-empty", textContent: "Noch keine eigenen." });
  const note = el("span", { className: "cee-status", id: "cee-script-readonly", hidden: true, textContent: "Schreibgeschützt" });
  note.dataset.tone = "neutral";

  const button = (id, label, onclick, extra = "") => el("button", { type: "button", className: `btn ${extra}`.trim(), id, textContent: label, onclick });
  const copy = button("cee-script-copy", "Als eigenes Plugin öffnen", () => copyPreset(), "sm primary");
  const newButton = button("cee-script-new", "Neues Plugin", () => newScript(), "sm");
  const duplicate = button("cee-script-duplicate", "Duplizieren", () => duplicateScript(), "sm");
  const remove = button("cee-script-remove", "Löschen", () => removeScript(), "sm");
  const runButton = button("cee-script-run", "Lauf starten", () => start(), "sm");
  const stopButton = button("cee-script-stop", "Lauf beenden", () => stop(), "sm");
  const probeButton = button("cee-script-probe", "Proben", () => probeScript(), "sm");
  const recordButton = button("cee-script-record", "Eingaben aufnehmen", () => toggleRecording(), "sm");
  const clearInputs = button("cee-script-clear-inputs", "Aufnahme löschen", () => dropInputs(), "sm");
  const exportButton = button("cee-script-export", "Als .blech speichern", () => exportOne(), "sm");
  const usbButton = button("cee-script-usb", "Per USB aufs Gerät", () => exportOne(usbButton), "sm");
  const exportAll = button("cee-script-export-all", "Alle speichern", () => exportCollection(), "sm");
  exportAll.title = `Alle Plugins als ${ARCHIVE.file} speichern`;
  const open = el("input", { type: "file", className: "cee-visually-hidden", id: "cee-script-open", accept: ".blech" });
  const openLabel = el("label", { className: "btn sm", htmlFor: "cee-script-open" }, ["Datei öffnen"]);
  const inputsInfo = el("p", { className: "muted", id: "cee-script-inputs" });
  const probeInfo = el("p", { id: "cee-script-probe-info", role: "status" });

  const simRoot = el("div", { className: "cee-sim", id: "cee-sim" });
  // The drawing is built when the run page is first needed: its controls repeat the ids of the emulator page.
  let panelBuilt = null;
  const panel = () => {
    if (!panelBuilt) {
      panelBuilt = simPanel(simRoot, { post: (event, ...args) => { try { live?.device.post(event, ...args); } catch { /* an event the ring does not take */ } } });
      panelBuilt.show(new Uint8Array(1024), []);
    }
    return panelBuilt;
  };

  const say = (words, tone) => {
    if (words) toast(words, tone === "error" ? "error" : tone === "ok" ? "ok" : "info");
  };

  const own = () => (current?.kind === "own" ? workspace.get(current.id) : null);
  const sourceNow = () => editor.value;

  const drawGutter = () => editor.setMarks(marks);

  function clearMarks() {
    marks = { covered: new Set(), missing: new Set(), error: marks.error };
  }

  function recompile() {
    const source = sourceNow();
    const label = current?.id ?? "plugin";
    const result = compile(source, { name: validName(label) ? label : "plugin" });
    built = result;
    marks.error = null;
    problems.replaceChildren();
    editor.setErrors(result.ok ? [] : result.errors);
    if (!result.ok) {
      marks.error = result.errors[0]?.line ?? null;
      status.textContent = "Übersetzen fehlgeschlagen.";
      status.title = "";
      for (const e of result.errors) {
        const item = el("li", {}, el("button", { type: "button", className: "cee-script-problem", textContent: formatError(e), onclick: () => editor.jump(e) }));
        problems.append(item);
      }
    } else {
      const h = decodeBlob(result.blob).header;
      const size = result.blob.length;
      status.textContent = `Block ${size} Byte, Variablen ${h.varCount} von ${BUDGET.variableSlots}, Code ${h.codeSize} von ${LIMITS.code} Byte, Texte ${h.stringCount} von ${LIMITS.strings}, Zahlen ${h.constCount} von ${LIMITS.consts}.`;
      status.title = `${status.textContent} Die Karte nimmt Blöcke bis ${ARCHIVE.maxBlock} Byte.`;
      if (size > ARCHIVE.maxBlock) problems.append(el("li", { className: "cee-script-problem-text", textContent: `Der Block hat ${size} Byte, auf der Karte sind höchstens ${ARCHIVE.maxBlock} möglich.` }));
    }
    drawGutter();
    updateActions();
  }

  function renderLists() {
    const item = (kind, id, title, detail) => {
      const b = el("button", { type: "button", className: "cee-pattern-item cee-plugin-item", title: detail ? `${title}: ${detail}` : title }, [
        el("span", { className: "cee-plugin-title ui-truncate", textContent: title }),
        detail ? el("span", { className: "cee-plugin-detail muted ui-truncate", textContent: detail }) : null,
      ]);
      b.dataset.kind = kind;
      b.dataset.id = id;
      b.setAttribute("aria-current", String(current?.kind === kind && current.id === id));
      b.addEventListener("click", () => select(kind, id));
      return el("li", {}, b);
    };
    presetList.replaceChildren(...PRESETS.map(p => item("preset", p.id, p.title, p.description)));
    const mine = workspace.list();
    ownList.hidden = !mine.length;
    ownEmpty.hidden = mine.length > 0;
    ownList.replaceChildren(...mine.map(s => item("own", s.name, s.name, s.probe?.key === sourceKey(s.source) && s.probe.ok ? "geprobt" : "")));
  }

  function updateActions() {
    const mine = own();
    const isOwn = !!mine;
    const isPreset = current?.kind === "preset";
    note.hidden = !isPreset;
    copy.hidden = !isPreset;
    duplicate.hidden = !isOwn;
    remove.hidden = !isOwn;
    name.disabled = !isOwn;
    editor.setReadOnly(!isOwn);
    const ok = !!built?.ok && built.blob.length <= ARCHIVE.maxBlock;
    runButton.disabled = !ok;
    stopButton.disabled = !live;
    probeButton.disabled = !ok;
    recordButton.hidden = !isOwn;
    recordButton.disabled = !ok;
    recordButton.textContent = recording ? "Aufnahme beenden" : "Eingaben aufnehmen";
    clearInputs.hidden = !isOwn || !mine?.inputs?.length;
    exportButton.hidden = !isOwn;
    usbButton.hidden = !isOwn;
    exportAll.disabled = workspace.list().length === 0;
    const n = mine?.inputs?.length ?? 0;
    inputsInfo.textContent = isOwn ? (n ? `Eingabefolge: ${n} Eingaben, bis Rahmen ${mine.inputs.at(-1).frame}.` : "Keine Eingabefolge. Die Probe läuft ohne Eingaben, nur ready und frame.") : "";
    const gate = isOwn ? exportGate({ source: mine.source, probe: mine.probe }) : null;
    probeInfo.replaceChildren(...(gate ? [gate.ok ? pill(gate.confirm ? "warn" : "ok", gate.confirm ? "Zeilen offen" : "Probe bestanden") : pill("neutral", "nicht geprobt"), ` ${gate.reason ?? "Alle Zeilen mit Code sind gelaufen."}`] : []));
    exportButton.disabled = !ok || !gate?.ok;
    usbButton.disabled = exportButton.disabled;
  }

  function select(kind, id) {
    stop();
    flush();
    const preset = kind === "preset" ? PRESETS.find(p => p.id === id) : null;
    const mine = kind === "own" ? workspace.get(id) : null;
    if (!preset && !mine) return;
    current = { kind, id };
    editor.load(preset ? preset.source : mine.source);
    name.value = preset ? preset.id : mine.name;
    runTarget.textContent = `Plugin: ${preset ? preset.title : mine.name}`;
    marks = { covered: new Set(), missing: new Set(), error: null };
    if (mine?.probe && mine.probe.key === sourceKey(mine.source)) marks = { covered: new Set(), missing: new Set(mine.probe.missing), error: null };
    log.replaceChildren();
    say("");
    renderLists();
    recompile();
    caretHelp();
    try { storage?.setItem("cee.scripts.last", `${kind}:${id}`); } catch { /* optional */ }
  }

  function flush() {
    if (saveTimer) { clearTimeout(saveTimer); saveTimer = null; }
    const mine = own();
    if (mine && mine.source !== sourceNow()) workspace.save({ name: mine.name, source: sourceNow() });
  }

  /** The name of a number under the caret. The names after `korg.key.` and `korg.led.` come from the editor's completion. */
  function caretHelp() {
    hint.textContent = hintAt(sourceNow(), editor.caret);
  }

  const copyName = async name => {
    try { await navigator.clipboard.writeText(name); toast(`${name} kopiert`, "ok"); } catch { toast("Kopieren ist hier nicht erlaubt.", "error"); }
  };

  function renderNames() {
    const q = namesFilter.value.trim().toLowerCase().replace(/[\s_]+/g, " ");
    const group = (kind, title, list) => {
      const rows = list.filter(n => !q || `${n.name} ${n.label} ${n.value}`.toLowerCase().replace(/_/g, " ").includes(q));
      if (!rows.length) return null;
      const body = el("tbody", {}, rows.map(n => el("tr", {}, [
        el("td", {}, el("button", { type: "button", className: "cee-names-name", textContent: `korg.${kind}.${n.name}`, title: "Kopieren", onclick: () => copyName(`korg.${kind}.${n.name}`) })),
        el("td", { textContent: String(n.value) }),
        el("td", { textContent: n.label }),
      ])));
      return el("table", { className: "cee-names" }, [el("caption", { textContent: title }), el("thead", {}, el("tr", {}, ["Name", "Nummer", "Gerät"].map(h => el("th", { scope: "col", textContent: h })))), body]);
    };
    namesBody.replaceChildren(...[
      group("key", "Tasten (korg.key, der Wert von buttonPress und buttonRelease)", KEY_NAMES),
      group("led", "LEDs (korg.led, das erste Argument von korg.led(...))", LED_NAMES),
    ].filter(Boolean));
    if (!namesBody.children.length) namesBody.textContent = "Kein Name passt zum Filter.";
  }

  function onInput() {
    caretHelp();
    clearMarks();
    recompile();
    if (!own()) return;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => { flush(); renderLists(); updateActions(); }, 300);
  }

  async function newScript() {
    const suggestion = workspace.freeName("plugin");
    const chosen = await ask({ title: "Neues Plugin", label: "Name", value: suggestion }, suggestion);
    if (chosen === null || chosen === undefined) return;
    if (!validName(chosen)) { say(`„${chosen}“ ist kein Name: ASCII, Buchstabe am Anfang, höchstens ${LIMITS.nameLength} Zeichen.`, "error"); return; }
    if (workspace.get(chosen)) { say(`„${chosen}“ gibt es schon.`, "error"); return; }
    const kind = await askKind();
    if (kind === null) return;
    workspace.save({ name: chosen, source: templateSource(kind, chosen) });
    select("own", chosen);
    editor.focus();
  }

  function copyPreset() {
    const preset = PRESETS.find(p => p.id === current?.id);
    if (!preset) return;
    const chosen = workspace.freeName(preset.id);
    workspace.save({ name: chosen, source: preset.source });
    select("own", chosen);
    say(`Als „${chosen}“ unter Meine Plugins angelegt.`, "ok");
  }

  function duplicateScript() {
    const mine = own();
    if (!mine) return;
    flush();
    const chosen = workspace.freeName(mine.name);
    workspace.save({ name: chosen, source: sourceNow(), inputs: mine.inputs });
    select("own", chosen);
  }

  async function removeScript() {
    const mine = own();
    if (!mine) return;
    if (!(await confirmed({ title: `„${mine.name}“ löschen?`, text: "Das Plugin liegt nur hier auf diesem Rechner und lässt sich danach nicht zurückholen.", confirmLabel: "Löschen", danger: true }))) return;
    stop();
    workspace.remove(mine.name);
    select("preset", PRESETS[0].id);
  }

  name.addEventListener("change", () => {
    const mine = own();
    if (!mine) return;
    try {
      flush();
      workspace.rename(mine.name, name.value.trim());
      current = { kind: "own", id: name.value.trim() };
      renderLists();
      recompile();
      say("Umbenannt.", "ok");
    } catch (e) {
      name.value = mine.name;
      say(e.message, "error");
    }
  });
  namesFilter.addEventListener("input", renderNames);

  function showFaults(faults) {
    for (const f of faults) {
      log.append(el("li", { className: "cee-script-fault", textContent: `${f.script ?? "Plugin"}: ${f.message}${f.line ? `, Zeile ${f.line}` : ""}${f.event ? ` (${f.event})` : ""}` }));
      if (f.line) marks.error = f.line;
    }
    if (faults.length) drawGutter();
  }

  function start(blob = built?.ok ? built.blob : null, label = current?.id ?? "plugin") {
    if (!blob) return false;
    stop();
    const device = new SimDevice({ storage: values });
    const loaded = device.load(blob);
    log.replaceChildren();
    live = { device, label, timer: null };
    page("run");
    if (loaded.error) showFaults([{ script: label, ...loaded.error }]);
    const appActions = { open: id => device.openApp(id), exit: () => device.post("buttonPress", EXIT_KEY) };
    if (device.apps.length && !loaded.error) device.openApp(device.apps[0].id);
    live.timer = setInterval(() => {
      showFaults(device.run(1));
      panel().show(device.shown, device.leds);
      panel().menus(device.menus, (id, value) => device.menuSet(id, value));
      panel().apps(device.apps, appActions);
    }, FRAME_MS);
    panel().show(device.shown, device.leds);
    panel().menus([], () => null);
    panel().apps(device.apps, appActions);
    panel().say(`Lauf: ${label}, ${Math.round(1000 / FRAME_MS)} Hz, Referenz-VM im Editor.${device.apps.length ? " App offen." : ""}`);
    updateActions();
    return true;
  }

  function stop() {
    if (!live) return;
    clearInterval(live.timer);
    if (recording) finishRecording();
    const lines = live.device.lines(0);
    marks = { covered: new Set(lines.covered), missing: new Set(lines.missing), error: marks.error };
    live = null;
    panel().release();
    panel().apps([], { open: () => {}, exit: () => {} });
    panel().say("Kein Lauf.");
    drawGutter();
    updateActions();
  }

  function toggleRecording() {
    if (recording) { finishRecording(); return; }
    if (!live && !start()) return;
    live.device.startRecording();
    recording = true;
    updateActions();
    say("Aufnahme läuft: bediene die Tasten und Pads, dann „Aufnahme beenden“.", "warn");
  }

  function finishRecording() {
    const inputs = live?.device.stopRecording() ?? [];
    recording = false;
    const mine = own();
    if (mine) {
      flush();
      workspace.save({ name: mine.name, source: sourceNow(), inputs });
      say(`${inputs.length} Eingaben gespeichert.`, "ok");
    }
    updateActions();
  }

  function dropInputs() {
    const mine = own();
    if (!mine) return;
    workspace.save({ name: mine.name, source: sourceNow(), inputs: [] });
    updateActions();
    say("Eingabefolge gelöscht.", "ok");
  }

  function probeScript() {
    if (!built?.ok) return;
    stop();
    const mine = own();
    const result = runProbe(built.blob, mine?.inputs ?? []);
    marks = { covered: new Set(result.lines.covered), missing: new Set(result.lines.missing), error: result.faults[0]?.line ?? null };
    log.replaceChildren();
    showFaults(result.loadError ? [{ script: current?.id, ...result.loadError }] : result.faults);
    if (mine) {
      flush();
      workspace.save({ name: mine.name, source: sourceNow(), probe: { key: sourceKey(sourceNow()), ok: result.ok, missing: result.lines.missing } });
    }
    const covered = result.lines.covered.length;
    const all = result.lines.all.length;
    say(result.ok
      ? `Probe über ${result.frames} Rahmen: ${covered} von ${all} Zeilen mit Code sind gelaufen${result.lines.missing.length ? `, nicht gelaufen: ${result.lines.missing.join(", ")}` : ""}.`
      : "Die Probe ist mit einem Fehler zu Ende gegangen.", result.ok ? (result.lines.missing.length ? "warn" : "ok") : "error");
    renderLists();
    drawGutter();
    updateActions();
  }

  async function allowExport(subject, gates) {
    const refused = gates.filter(g => !g.gate.ok);
    if (refused.length) {
      say(`${refused.map(g => `„${g.name}“: ${g.gate.reason}`).join(" ")} Zuerst proben.`, "error");
      return false;
    }
    const open = gates.filter(g => g.gate.confirm);
    if (!open.length) return true;
    const list = open.map(g => `„${g.name}“: Zeilen ${g.gate.missing.join(", ")}`).join("\n");
    return confirmed({ title: "Zeilen ohne Lauf exportieren?", text: `Die Probe hat diese Zeilen nie ausgeführt:\n${list}\n\nSie laufen am Gerät zum ersten Mal.`, confirmLabel: `${subject} trotzdem speichern` });
  }

  async function exportOne(toUsb = null) {
    const mine = own();
    if (!mine) return;
    flush();
    const fresh = workspace.get(mine.name);
    const result = compile(fresh.source, { name: fresh.name });
    if (!result.ok) { say("Das Plugin lässt sich nicht übersetzen.", "error"); return; }
    if (!(await allowExport("Plugin", [{ name: fresh.name, gate: exportGate(fresh) }]))) return;
    const packed = packBlech(markProbed(result.blob), fresh.source);
    if (!packed.ok) { say(packed.error.message, "error"); return; }
    if (toUsb) { await toDevice(packed.bytes, fresh.name, toUsb); return; }
    download(packed.bytes, `${fresh.name}.blech`);
    say(`${fresh.name}.blech gespeichert. Auf die Karte nach ${ARCHIVE.folder}/ kopieren.`, "ok");
  }

  async function exportCollection() {
    flush();
    const items = workspace.list();
    const blocks = [];
    const gates = [];
    let apps = 0;
    for (const s of items) {
      const result = compile(s.source, { name: s.name });
      if (!result.ok) { say(`„${s.name}“ lässt sich nicht übersetzen.`, "error"); return; }
      if (result.info.app) apps += 1;
      blocks.push(markProbed(result.blob));
      gates.push({ name: s.name, gate: exportGate(s) });
    }
    if (apps > SCRIPT_APPS.max) { say(`Das sind ${apps} Apps. Die Electribe zeigt höchstens ${SCRIPT_APPS.max}. Lösch ein paar Apps aus der Liste und speichere nochmal.`, "error"); return; }
    if (!(await allowExport("Alle", gates))) return;
    const packed = packAll(blocks);
    if (!packed.ok) { say(packed.error.message, "error"); return; }
    download(packed.bytes, ARCHIVE.file);
    say(`${ARCHIVE.file} mit ${blocks.length} Plugins gespeichert. Auf die Karte nach ${ARCHIVE.folder}/ kopieren.`, "ok");
  }

  open.addEventListener("change", async () => {
    const file = open.files?.[0];
    open.value = "";
    if (!file) return;
    const parsed = parseBlech(new Uint8Array(await file.arrayBuffer()));
    if (!parsed.ok) { say(`${file.name}: ${parsed.error.message}`, "error"); return; }
    if (parsed.source === null) { say(`${file.name} enthält keinen Quelltext, nur den Block. Zum Bearbeiten fehlt der Text.`, "error"); return; }
    const chosen = workspace.freeName(parsed.parts.header.name);
    workspace.save({ name: chosen, source: parsed.source });
    select("own", chosen);
    say(`„${chosen}“ aus ${file.name} geöffnet.`, "ok");
  });

  const sideActions = el("div", { className: "cee-ws-side-actions" }, [newButton, openLabel, open, exportAll]);
  const side = el("aside", { className: "ui-split-side cee-ws-side", id: "cee-scripts-side" }, [
    sideActions,
    el("h2", { className: "cee-list-title", textContent: "Beispiele" }),
    presetList,
    el("h2", { className: "cee-list-title", textContent: "Meine Plugins" }),
    ownList,
    ownEmpty,
    el("p", { className: "muted cee-ws-side-note", textContent: "Eigene Plugins bleiben auf diesem Rechner." }),
  ]);

  const nameField = el("div", { className: "cee-ws-name" }, [el("label", { className: "muted", htmlFor: "cee-script-name", textContent: "Name" }), name]);
  const toolbar = el("div", { className: "cee-ws-toolbar" }, [nameField, note, el("div", { className: "cee-ws-toolbar-actions" }, [copy, duplicate, remove, exportButton, usbButton])]);
  const strip = el("div", { className: "cee-ws-strip" }, [status, probeInfo, hint]);

  const consoleHost = el("div", { className: "cee-ws-console", id: "cee-terminal" });
  const runTarget = el("p", { className: "muted", id: "cee-run-target" });

  const main = el("div", { className: "ui-split-main cee-ws-main" }, [toolbar, editorHost, problems, strip]);

  const split = el("div", { className: "ui-split cee-workspace", id: "cee-scripts-split" }, [
    el("button", { type: "button", className: "btn ui-split-toggle", textContent: "Plugins", "aria-expanded": "false", "aria-controls": "cee-scripts-side" }),
    side,
    main,
  ]);

  const thumbs = new Map();
  let thumbsDone = false;

  // The documentation: docs/plugins.md read as a page, with the live table of names as one of its sections.
  const docsSearch = el("input", { className: "input", id: "cee-docs-search", type: "search", placeholder: "Dokumentation durchsuchen", spellcheck: false, autocomplete: "off" });
  docsSearch.setAttribute("aria-label", "Dokumentation durchsuchen");
  const docsToc = el("details", { className: "ui-details", id: "cee-docs-toc" }, [el("summary", { textContent: "Inhalt" }), el("div", { className: "ui-details-body" })]);
  const docsArticle = el("article", { className: "cee-docs-article", id: "cee-docs-article" }, [el("p", { className: "muted", textContent: "Wird geladen …" })]);
  const docsEmpty = el("p", { className: "muted", id: "cee-docs-empty", hidden: true, textContent: "Nichts gefunden." });
  const docsPage = el("div", { className: "cee-plug-page cee-docs" }, [el("div", { className: "cee-docs-head" }, [docsSearch]), docsToc, docsArticle, docsEmpty]);
  let docSections = [];
  let docsLoaded = false;
  const jumpTo = id => {
    docsSearch.value = "";
    filterDocs();
    document.getElementById(id)?.scrollIntoView({ block: "start" });
  };
  function filterDocs() {
    const q = docsSearch.value.trim().toLowerCase();
    let any = false;
    for (const s of docSections) {
      const hit = !q || s.node.textContent.toLowerCase().includes(q);
      s.node.hidden = !hit;
      any ||= hit;
    }
    docsEmpty.hidden = any;
  }
  docsSearch.addEventListener("input", filterDocs);
  const NAMES_TITLE = "Namen für Tasten und LEDs";
  async function loadDocs() {
    if (docsLoaded) return;
    docsLoaded = true;
    let text;
    try {
      const res = await fetch(new URL("../../docs/plugins.md", import.meta.url));
      if (!res.ok) throw new Error(String(res.status));
      text = await res.text();
    } catch {
      docsArticle.replaceChildren(el("p", { className: "cee-error", textContent: "Die Dokumentation ließ sich nicht laden." }));
      docsLoaded = false;
      return;
    }
    const { blocks } = parseMarkdown(text, { onJump: id => jumpTo(`doc-${id}`) });
    docSections = [];
    let section = null;
    const links = [];
    for (const { node, heading } of blocks) {
      if (heading && heading.level <= 3 || !section) {
        section = { title: heading?.text ?? "", node: el("section", { className: "cee-doc-section" }) };
        docSections.push(section);
      }
      if (heading && heading.level >= 2) links.push(heading);
      // The tables of the names are the live ones below; the static copies in the doc stay out of the page.
      if (section.title === NAMES_TITLE && (node.classList.contains("cee-doc-table") || /^(Tasten|LEDs) \(/.test(node.textContent))) continue;
      if (/^Deutsche Version/.test(node.textContent)) continue;
      section.node.append(node);
    }
    const names = docSections.find(s => s.title === NAMES_TITLE);
    if (names) names.node.append(el("div", { className: "cee-names-head" }, [namesFilter, el("p", { className: "muted", textContent: "Klick kopiert den Namen. Beim Übersetzen wird er zur Nummer." })]), namesBody);
    docsArticle.replaceChildren(...docSections.map(s => s.node));
    docsToc.querySelector(".ui-details-body").replaceChildren(el("ul", { className: "cee-doc-toc" }, links.map(h => el("li", { className: `cee-doc-toc-${h.level}` }, el("button", { type: "button", className: "cee-text-link", textContent: h.text, onclick: () => jumpTo(h.id) })))));
  }

  // The catalog: the bundled examples as cards, each with a picture of its display after a few frames of the browser VM.
  const catalog = el("ul", { className: "cee-catalog", id: "cee-catalog" }, PRESETS.map(catalogCard));

  const PAGES = [
    { id: "catalog", title: "Katalog", node: el("div", { className: "cee-plug-page" }, [catalog]) },
    { id: "editor", title: "Editor", node: split },
    { id: "run", title: "Lauf", node: el("div", { className: "cee-plug-page cee-run" }, [
      runTarget,
      el("div", { className: "cee-run-bar" }, [runButton, stopButton, probeButton, recordButton, clearInputs, inputsInfo]),
      simRoot,
      log,
    ]) },
    { id: "console", title: "Konsole", node: el("div", { className: "cee-plug-page" }, [consoleHost]) },
    { id: "docs", title: "Dokumentation", node: docsPage },
  ];
  for (const p of PAGES) { p.node.id ||= `cee-plugin-${p.id}`; p.node.hidden = true; p.node.dataset.page = p.id; }
  root.replaceChildren(...PAGES.map(p => p.node));

  let shown = null;
  const PAGE_ICONS = { catalog: "grid", editor: "code", run: "play", console: "terminal", docs: "book" };
  const subPages = sub?.pages("scripts", { id: "cee-scripts-pages", label: "Bereiche der Plugins", items: PAGES.map(({ id, title }) => ({ id, title, icon: PAGE_ICONS[id] })), pick: id => page(id) });
  /** Opens one of the pages of Plugins: the editor, the run area, the console, the names, the catalog. */
  function page(id) {
    if (!PAGES.some(p => p.id === id)) id = "editor";
    if (id === shown) return;
    shown = id;
    for (const p of PAGES) p.node.hidden = p.id !== id;
    subPages?.select(id);
    if (id === "catalog") drawThumbs();
    if (id === "docs") loadDocs();
    if (id === "run") panel();
  }

  const THUMB_FRAMES = 40;
  const noStore = { load: () => null, save: () => {} };

  /** The display of a plugin after a few frames, drawn with the LCD drawing of the emulator page; a plugin that only lights LEDs shows its pads. */
  function renderThumb(canvas, preset) {
    const result = compile(preset.source, { name: validName(preset.id) ? preset.id : "plugin" });
    drawDisplay(canvas, new Uint8Array(1024));
    if (!result.ok) return;
    const device = new SimDevice({ storage: noStore });
    const loaded = device.load(result.blob);
    if (loaded.ok && device.apps.length) device.openApp(device.apps[0].id);
    device.run(THUMB_FRAMES);
    const bytes = device.shown;
    if (bytes.some(b => b)) { drawDisplay(canvas, bytes); return; }
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = getComputedStyle(canvas).getPropertyValue("--cee-lcd-on");
    for (const pad of PADS) {
      const level = Math.max(device.leds[pad.ledRed] ?? 0, device.leds[pad.ledBlue] ?? 0) / 255;
      ctx.globalAlpha = 0.12 + 0.88 * level;
      ctx.fillRect(8 + (pad.index % 8) * 14, 18 + Math.floor(pad.index / 8) * 16, 11, 11);
    }
    ctx.globalAlpha = 1;
  }

  function drawThumbs() {
    if (thumbsDone) return;
    thumbsDone = true;
    for (const [canvas, preset] of thumbs) renderThumb(canvas, preset);
  }

  function catalogCard(preset) {
    const canvas = el("canvas", { className: "cee-lcd cee-catalog-thumb", width: 128, height: 64 });
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", `Display von ${preset.title}`);
    thumbs.set(canvas, preset);
    const note = el("p", { className: "cee-error", hidden: true });
    // Icon buttons: the label says only what the button does, for the screen reader and as the tooltip.
    const iconButton = (name, label, onclick, primary = false) => {
      const b = el("button", { type: "button", className: `btn icon${primary ? " primary" : ""}`, title: label, onclick }, [icon(name)]);
      b.setAttribute("aria-label", label);
      return b;
    };
    const view = iconButton("eye", "Code ansehen", () => { select("preset", preset.id); page("editor"); });
    const pack = () => {
      const result = compile(preset.source, { name: validName(preset.id) ? preset.id : "plugin" });
      const probed = result.ok ? runProbe(result.blob) : null;
      const packed = probed?.ok ? packBlech(markProbed(result.blob), preset.source) : null;
      note.hidden = !!packed?.ok;
      if (!packed?.ok) { note.textContent = packed?.error?.message ?? "Dieses Beispiel lässt sich nicht speichern."; return null; }
      return packed.bytes;
    };
    const get = iconButton("download", "Herunterladen", () => {
      const bytes = pack();
      if (bytes) download(bytes, `${preset.id}.blech`);
    });
    const usb = iconButton("usb", "Per USB auf die Electribe schicken", () => {
      const bytes = pack();
      if (bytes) toDevice(bytes, preset.id, usb);
    }, true);
    return el("li", { className: "cee-catalog-card", id: `cee-catalog-${preset.id}` }, [
      canvas,
      el("h3", { textContent: preset.title }),
      el("p", { className: "muted", textContent: preset.description }),
      el("div", { className: "cee-catalog-actions" }, [view, get, usb]),
      note,
    ]);
  }

  renderNames();
  let last = null;
  try { last = storage?.getItem("cee.scripts.last"); } catch { /* optional */ }
  const [kind, id] = (last ?? "").split(/:(.*)/s);
  if (kind === "own" && workspace.get(id)) select("own", id);
  else select("preset", PRESETS.some(p => p.id === id) ? id : PRESETS[0].id);
  page("catalog");

  return {
    /** The names the terminal's run() accepts. */
    names: () => [...PRESETS.map(p => p.id), ...workspace.list().map(s => s.name)],
    /** Start a saved script or a template in the run area. Returns what happened in words. */
    runNamed(wanted) {
      const key = String(wanted).replace(/^.*[\\/]/, "").replace(/\.(blech|js)$/i, "");
      const mine = workspace.get(key);
      const preset = PRESETS.find(p => p.id === key || p.title === key);
      const source = mine?.source ?? preset?.source;
      if (source === undefined) throw new Error(`Kein Plugin „${wanted}“. Es gibt: ${[...PRESETS.map(p => p.id), ...workspace.list().map(s => s.name)].join(", ")}.`);
      const label = mine?.name ?? preset.id;
      const result = compile(source, { name: validName(label) ? label : "plugin" });
      if (!result.ok) throw new Error(result.errors.map(formatError).join("\n"));
      start(result.blob, label);
      return `„${label}“ läuft im Bereich Lauf, Display und LEDs stehen dort.`;
    },
    /** Run lines of script language once, at the first frame, in the run area. */
    runSnippet(code) {
      const result = compile(`korg.app("einzeiler", "TOOLS");\nkorg.onEvent("ready", () => {\n${code.trim().replace(/;?$/, ";")}\n});`, { name: "einzeiler" });
      if (!result.ok) throw new Error(result.errors.map(e => `${formatError({ ...e, line: Math.max(1, e.line - 2) })}`).join("\n"));
      start(result.blob, "einzeiler");
      return "Läuft im Bereich Lauf, als App geöffnet.";
    },
    stop,
    page,
    get running() { return !!live; },
  };
}
