/**
 * The plugins page (code name: scripts): the catalog with a page per plugin, the own plugins, the editor over the
 * whole page and the preview, the simulated device over the page. A plugin leaves as a file only after a probe of
 * exactly this text (src/script/gate.mjs).
 */
import { el } from "./fields.mjs";
import { icon } from "./icons.mjs";
import { simPanel } from "./sim-panel.mjs";
import { drawDisplay } from "./emulator.mjs";
import { PADS } from "../../data/panel.mjs";
import { parseMarkdown } from "./markdown.mjs";
import { toast } from "./toast.mjs";
import { saveFile } from "./save-file.mjs";
import { createScriptEditor } from "./script-editor.mjs";
import { highlightLines } from "../../src/script/highlight.mjs";
import { compile, formatError } from "../../src/script/compiler.mjs";
import { decodeBlob, markProbed } from "../../src/script/blob.mjs";
import { LIMITS, BUDGET, ARCHIVE, SCRIPT_APPS } from "../../data/script/contract.mjs";
import { PRESETS } from "../../data/script/presets.mjs";
import { TEMPLATES, templateSource } from "../../data/script/templates.mjs";
import { KEY_NAMES, LED_NAMES } from "../../data/script/names.mjs";
import { KNOB_NAMES } from "../../data/script/properties.mjs";
import { hintAt } from "../../src/script/names.mjs";
import { Workspace, sourceKey, validName } from "../../src/script/workspace.mjs";
import { SimDevice, probe as runProbe, FRAME_MS } from "../../src/script/sim.mjs";
import { exportGate } from "../../src/script/gate.mjs";
import { packAll, packBlech, parseBlech } from "../../src/script/archive.mjs";
import { storePlugin } from "../../src/usb-update.mjs";
import { creatorLine, creatorName, metaFields, metaProblem } from "./creator.mjs";
import { pixelsOf } from "./splash.mjs";
import { t, locale } from "./i18n.mjs";

/** 0/1 pixels row by row (splash.mjs) to the display's 1024 bytes: eight rows per byte, bit 0 on top. */
function displayBytes(pixels) {
  const out = new Uint8Array(1024);
  for (let i = 0; i < pixels.length; i++) if (pixels[i]) { const x = i % 128, y = Math.floor(i / 128); out[(y >> 3) * 128 + x] |= 1 << (y & 7); }
  return out;
}
const toBase64 = bytes => btoa(String.fromCharCode(...bytes));
const fromBase64 = text => { try { const b = Uint8Array.from(atob(text), c => c.charCodeAt(0)); return b.length === 1024 ? b : null; } catch { return null; } };

const EXIT_KEY = KEY_NAMES.find(n => n.name === "EXIT").value;

const pill = (tone, word) => {
  const p = el("span", { className: "cee-status", textContent: word });
  p.dataset.tone = tone;
  return p;
};

const ask = async (options, fallback) => (window.ui?.prompt ? window.ui.prompt(options) : fallback);

/** The second step of "Neues Plugin": which kind to start from. Resolves to a template id, or null when the user cancels. */
function askKind() {
  if (!window.ui?.openDialog) return Promise.resolve(TEMPLATES[0].id);
  return new Promise(resolve => {
    const hint = el("p", { className: "muted", id: "cee-script-kind-hint", textContent: TEMPLATES[0].description });
    hint.setAttribute("aria-live", "polite");
    const radios = TEMPLATES.map((t, i) => el("input", { type: "radio", name: "cee-script-kind", value: t.id, checked: i === 0, autofocus: i === 0 }));
    const group = el("div", { className: "ui-segmented", id: "cee-script-kind-options", role: "radiogroup" }, TEMPLATES.map((t, i) => el("label", { className: "ui-segmented-option" }, [radios[i], el("span", { textContent: t.label })])));
    group.setAttribute("aria-label", t("plugins.kind.label"));
    const chosen = () => radios.find(r => r.checked)?.value ?? TEMPLATES[0].id;
    const dialog = el("dialog", { className: "ui-dialog ui-dialog-narrow", id: "cee-script-kind" });
    dialog.setAttribute("aria-labelledby", "cee-script-kind-title");
    dialog.append(el("form", { method: "dialog", className: "ui-dialog-box" }, [
      el("header", { className: "ui-dialog-head" }, el("h2", { className: "ui-dialog-title", id: "cee-script-kind-title", textContent: t("plugins.kind.title") })),
      el("div", { className: "ui-dialog-body" }, [group, hint]),
      el("footer", { className: "ui-dialog-foot" }, [
        el("button", { type: "submit", className: "btn", value: "cancel", textContent: t("common.cancel"), formNoValidate: true }),
        el("button", { type: "submit", className: "btn cee-primary", value: "ok", textContent: t("plugins.kind.create") }),
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

export function scriptsPanel(root, { storage = null, sub = null, session = () => null, onRun = () => {}, trail: setTrail = () => {}, navbar = () => {} } = {}) {
  // The title in the breadcrumb leads to the catalog, the start of the page.
  const trail = parts => setTrail(parts, () => page("catalog"));
  /** A packed .blech onto the connected device's card; PLUGIN EDIT in the BLECH menu then lists it. */
  async function toDevice(bytes, id, button) {
    const s = session();
    if (!s) { toast(t("console.forwardFirst"), "error"); return; }
    button.disabled = true;
    try {
      const name = await storePlugin(s, id, bytes);
      toast(t("plugins.onCard", { name }), "ok");
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
  const editor = createScriptEditor(editorHost, { label: t("plugins.code"), onInput: () => queueMicrotask(onInput), onCaret: () => caretHelp() });
  const status = el("p", { className: "muted cee-script-status", id: "cee-script-status", role: "status" });
  const hint = el("p", { className: "muted cee-script-hint", id: "cee-script-hint", role: "status" });
  const namesFilter = el("input", { className: "input", id: "cee-names-filter", type: "search", placeholder: t("plugins.names.filter"), spellcheck: false, autocomplete: "off" });
  namesFilter.setAttribute("aria-label", t("plugins.names.filterLabel"));
  const namesBody = el("div", { className: "cee-names-body", id: "cee-names-body" });
  const problems = el("ul", { className: "cee-script-problems", id: "cee-script-problems" });
  const log = el("ul", { className: "cee-script-log", id: "cee-script-log", "aria-live": "polite" });
  const ownList = el("ul", { className: "cee-catalog cee-own", id: "cee-script-own" });
  const ownEmpty = el("p", { className: "muted cee-ws-empty", id: "cee-script-own-empty", textContent: t("plugins.own.empty") });
  const note = el("span", { className: "cee-status", id: "cee-script-readonly", hidden: true, textContent: t("plugins.readOnly") });
  note.dataset.tone = "neutral";

  const button = (id, label, onclick, extra = "") => el("button", { type: "button", className: `btn ${extra}`.trim(), id, textContent: label, onclick });
  const copy = button("cee-script-copy", t("plugins.copy"), () => copyPreset(), "sm cee-primary");
  const newButton = button("cee-script-new", t("plugins.new"), () => newScript(), "sm");
  const duplicate = button("cee-script-duplicate", t("plugins.duplicate"), () => duplicateScript(), "sm");
  const remove = button("cee-script-remove", t("plugins.remove"), () => removeScript(), "sm");
  const runButton = button("cee-script-run", t("plugins.restart"), () => (shown === "detail" ? detailView("preview") : start()), "sm");
  const stopButton = button("cee-script-stop", t("plugins.stop"), () => stop(), "sm");
  const previewButton = button("cee-script-preview", t("plugins.preview"), () => preview(), "cee-primary");
  const probeButton = button("cee-script-probe", t("plugins.probe"), () => probeScript(), "sm");
  const recordButton = button("cee-script-record", t("plugins.record"), () => toggleRecording(), "sm");
  const clearInputs = button("cee-script-clear-inputs", t("plugins.clearInputs"), () => dropInputs(), "sm");
  const exportButton = button("cee-script-export", t("plugins.download"), () => exportOne(), "");
  const usbButton = button("cee-script-usb", t("plugins.toDevice"), () => exportOne(usbButton), "");
  const exportAll = button("cee-script-export-all", t("plugins.saveAll"), () => exportCollection(), "sm");
  exportAll.title = t("plugins.saveAll.title", { file: ARCHIVE.file });
  const open = el("input", { type: "file", className: "cee-visually-hidden", id: "cee-script-open", accept: ".blech" });
  const openLabel = el("label", { className: "btn sm", htmlFor: "cee-script-open" }, [t("common.open")]);
  // The editor's file actions sit in the navbar: Öffnen a .blech from this computer, Speichern the one in the editor.
  const openNav = button("cee-script-open-nav", t("common.open"), () => open.click(), "sm");
  const saveNav = button("cee-script-save", t("common.save"), () => exportOne(), "sm cee-primary");
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
      status.textContent = t("plugins.compileFailed");
      status.title = "";
      for (const e of result.errors) {
        const item = el("li", {}, el("button", { type: "button", className: "cee-script-problem", textContent: formatError(e), onclick: () => editor.jump(e) }));
        problems.append(item);
      }
    } else {
      const h = decodeBlob(result.blob).header;
      const size = result.blob.length;
      status.textContent = t("plugins.size", { size, vars: h.varCount, varMax: BUDGET.variableSlots, code: h.codeSize, codeMax: LIMITS.code, strings: h.stringCount, stringMax: LIMITS.strings, consts: h.constCount, constMax: LIMITS.consts });
      status.title = t("plugins.size.title", { size: status.textContent, max: ARCHIVE.maxBlock });
      if (size > ARCHIVE.maxBlock) problems.append(el("li", { className: "cee-script-problem-text", textContent: t("plugins.tooBig", { size, max: ARCHIVE.maxBlock }) }));
    }
    drawGutter();
    updateActions();
  }

  /** The own plugins of this browser as cards like the catalog's: the whole card opens the plugin in the editor, where
   * Herunterladen, Aufs Gerät and Löschen are. */
  function renderLists() {
    const mine = workspace.list();
    ownEmpty.hidden = mine.length > 0;
    // Drawn once the cards are in the page: the display's colours come from the stylesheet.
    const draws = [];
    ownList.replaceChildren(...mine.map(s => {
      const probed = s.probe?.key === sourceKey(s.source) && s.probe.ok;
      const canvas = el("canvas", { className: "cee-lcd cee-catalog-thumb", width: 128, height: 64 });
      canvas.setAttribute("role", "img");
      canvas.setAttribute("aria-label", t("plugins.display", { name: s.name }));
      const picture = s.meta?.image ? fromBase64(s.meta.image) : null;
      draws.push(() => { if (picture) drawDisplay(canvas, picture); else renderThumb(canvas, { id: s.name, source: s.source }); });
      const open = el("button", { type: "button", className: "cee-catalog-open cee-own-name", textContent: s.name, onclick: () => { select("own", s.name); page("editor"); } });
      return el("li", { className: "cee-catalog-card cee-own-card", id: `cee-own-${s.name}` }, [
        canvas,
        el("h3", {}, open),
        el("p", { className: "cee-catalog-category", textContent: t("plugins.own") }),
        s.meta?.description ? el("p", { className: "muted", textContent: s.meta.description }) : null,
        el("p", { className: "muted", textContent: probed ? t("plugins.probed") : t("plugins.notProbed") }),
        creatorLine(s.meta?.creator, s.meta?.creatorUrl),
      ]);
    }));
    for (const draw of draws) draw();
  }

  function updateActions() {
    emptyEditor.hidden = !!current;
    main.hidden = !current;
    const mine = own();
    const isOwn = !!mine;
    wordsButton.hidden = !isOwn;
    // The words are filled in only when another plugin opens, so typing is never overwritten.
    if (isOwn && wordsFor !== mine.name) { wordsFor = mine.name; words = { ...mine.meta }; ownMeta.set(words); showPicture(); }
    if (!isOwn) { wordsFor = null; words = null; }
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
    recordButton.textContent = recording ? t("plugins.recordStop") : t("plugins.record");
    clearInputs.hidden = !isOwn || !mine?.inputs?.length;
    exportButton.hidden = !isOwn;
    usbButton.hidden = !isOwn;
    exportAll.disabled = workspace.list().length === 0;
    const n = mine?.inputs?.length ?? 0;
    inputsInfo.textContent = isOwn ? (n ? t("plugins.inputs", { count: n, frame: mine.inputs.at(-1).frame }) : t("plugins.noInputs")) : "";
    const gate = isOwn ? exportGate({ source: mine.source, probe: mine.probe }) : null;
    probeInfo.replaceChildren(...(gate ? [gate.ok ? pill(gate.confirm ? "warn" : "ok", gate.confirm ? t("plugins.linesOpen") : t("console.passed")) : pill("neutral", t("plugins.notProbedTag")), ` ${gate.reason ?? t("plugins.allRan")}`] : []));
    exportButton.disabled = !ok || !gate?.ok;
    usbButton.disabled = exportButton.disabled;
    // Speichern in the navbar is the same export: a plugin of the catalog is read only, an own one needs its probe first
    saveNav.disabled = !isOwn || exportButton.disabled;
    saveNav.title = !isOwn ? t("plugins.readOnlyHint") : exportButton.disabled ? t("plugins.probeFirst") : "";
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
    runTarget.textContent = t("plugins.target", { name: preset ? preset.title : mine.name });
    marks = { covered: new Set(), missing: new Set(), error: null };
    if (mine?.probe && mine.probe.key === sourceKey(mine.source)) marks = { covered: new Set(), missing: new Set(mine.probe.missing), error: null };
    log.replaceChildren();
    say("");
    renderLists();
    recompile();
    caretHelp();
    if (shown === "editor") trail([t("plugins.page.editor"), id]);
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
    try { await navigator.clipboard.writeText(name); toast(t("plugins.copied", { name }), "ok"); } catch { toast(t("plugins.noClipboard"), "error"); }
  };

  function renderNames() {
    const q = namesFilter.value.trim().toLowerCase().replace(/[\s_]+/g, " ");
    const group = (kind, title, list) => {
      const rows = list.filter(n => !q || `${n.name} ${n.label} ${n.value}`.toLowerCase().replace(/_/g, " ").includes(q));
      if (!rows.length) return null;
      const body = el("tbody", {}, rows.map(n => el("tr", {}, [
        el("td", {}, el("button", { type: "button", className: "cee-names-name", textContent: `korg.${kind}.${n.name}`, title: t("plugins.names.copy"), onclick: () => copyName(`korg.${kind}.${n.name}`) })),
        el("td", { textContent: String(n.value) }),
        el("td", { textContent: n.label }),
      ])));
      return el("table", { className: "cee-names" }, [el("caption", { textContent: title }), el("thead", {}, el("tr", {}, [t("mod.field.name"), t("plugins.names.number"), t("plugins.names.device")].map(h => el("th", { scope: "col", textContent: h })))), body]);
    };
    namesBody.replaceChildren(...[
      group("key", t("plugins.names.keys"), KEY_NAMES),
      group("led", t("plugins.names.leds"), LED_NAMES),
      group("knobs", t("plugins.names.knobs"), KNOB_NAMES),
    ].filter(Boolean));
    if (!namesBody.children.length) namesBody.textContent = t("plugins.names.none");
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
    const chosen = await ask({ title: t("plugins.new"), label: t("mod.field.name"), value: suggestion }, suggestion);
    if (chosen === null || chosen === undefined) return;
    if (!validName(chosen)) { say(t("plugins.badName", { name: chosen, max: LIMITS.nameLength }), "error"); return; }
    if (workspace.get(chosen)) { say(t("plugins.exists", { name: chosen }), "error"); return; }
    const kind = await askKind();
    if (kind === null) return;
    workspace.save({ name: chosen, source: templateSource(kind, chosen) });
    select("own", chosen);
    page("editor");
    editor.focus();
  }

  function copyPreset() {
    const preset = PRESETS.find(p => p.id === current?.id);
    if (!preset) return;
    const chosen = workspace.freeName(preset.id);
    workspace.save({ name: chosen, source: preset.source, meta: { description: preset.description } });
    select("own", chosen);
    say(t("plugins.copiedPreset", { name: chosen }), "ok");
  }

  function duplicateScript() {
    const mine = own();
    if (!mine) return;
    flush();
    const chosen = workspace.freeName(mine.name);
    workspace.save({ name: chosen, source: sourceNow(), inputs: mine.inputs, meta: mine.meta });
    select("own", chosen);
  }

  async function removeScript() {
    const mine = own();
    if (!mine) return;
    if (!(await confirmed({ title: t("plugins.remove.title", { name: mine.name }), text: t("plugins.remove.text"), confirmLabel: t("plugins.remove"), danger: true }))) return;
    stop();
    workspace.remove(mine.name);
    select("preset", PRESETS[0].id);
    page("catalog");
    shelf("own");
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
      say(t("plugins.renamed"), "ok");
    } catch (e) {
      name.value = mine.name;
      say(e.message, "error");
    }
  });
  namesFilter.addEventListener("input", renderNames);

  function showFaults(faults) {
    for (const f of faults) {
      log.append(el("li", { className: "cee-script-fault", textContent: t("plugins.fault", { script: f.script ?? t("plugins.fault.plugin"), message: f.message, line: f.line ? t("plugins.fault.line", { line: f.line }) : "", event: f.event ? ` (${f.event})` : "" }) }));
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
    showRun();
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
    panel().say(t("plugins.run", { label, hz: Math.round(1000 / FRAME_MS), app: device.apps.length ? ` ${t("plugins.run.app")}` : "" }));
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
    panel().say(t("sim.idle"));
    drawGutter();
    updateActions();
  }

  function toggleRecording() {
    if (recording) { finishRecording(); return; }
    if (!live && !start()) return;
    live.device.startRecording();
    recording = true;
    updateActions();
    say(t("plugins.recording"), "warn");
  }

  function finishRecording() {
    const inputs = live?.device.stopRecording() ?? [];
    recording = false;
    const mine = own();
    if (mine) {
      flush();
      workspace.save({ name: mine.name, source: sourceNow(), inputs });
      say(t("plugins.inputsSaved", { count: inputs.length }), "ok");
    }
    updateActions();
  }

  function dropInputs() {
    const mine = own();
    if (!mine) return;
    workspace.save({ name: mine.name, source: sourceNow(), inputs: [] });
    updateActions();
    say(t("plugins.inputsCleared"), "ok");
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
      ? t("plugins.probe.ok", { frames: result.frames, covered, all, missing: result.lines.missing.length ? t("plugins.probe.missing", { lines: result.lines.missing.join(", ") }) : "" })
      : t("plugins.probe.failed"), result.ok ? (result.lines.missing.length ? "warn" : "ok") : "error");
    renderLists();
    drawGutter();
    updateActions();
  }

  async function allowExport(subject, gates) {
    const refused = gates.filter(g => !g.gate.ok);
    if (refused.length) {
      say(t("plugins.refused", { list: refused.map(g => `„${g.name}“: ${g.gate.reason}`).join(" ") }), "error");
      return false;
    }
    const open = gates.filter(g => g.gate.confirm);
    if (!open.length) return true;
    const list = open.map(g => t("plugins.openLines", { name: g.name, lines: g.gate.missing.join(", ") })).join("\n");
    return confirmed({ title: t("plugins.openLines.title"), text: t("plugins.openLines.text", { list }), confirmLabel: t("plugins.openLines.confirm", { subject }) });
  }

  async function exportOne(toUsb = null) {
    const mine = own();
    if (!mine) return;
    flush();
    const fresh = workspace.get(mine.name);
    const result = compile(fresh.source, { name: fresh.name });
    if (!result.ok) { say(t("plugins.noCompile"), "error"); return; }
    if (!(await allowExport(t("plugins.subject.one"), [{ name: fresh.name, gate: exportGate(fresh) }]))) return;
    const packed = packBlech(markProbed(result.blob), fresh.source);
    if (!packed.ok) { say(packed.error.message, "error"); return; }
    if (toUsb) { await toDevice(packed.bytes, fresh.name, toUsb); return; }
    saveFile(packed.bytes, `${fresh.name}.blech`, { note: t("plugins.copyTo", { folder: ARCHIVE.folder }) });
  }

  async function exportCollection() {
    flush();
    const items = workspace.list();
    const blocks = [];
    const gates = [];
    let apps = 0;
    for (const s of items) {
      const result = compile(s.source, { name: s.name });
      if (!result.ok) { say(t("plugins.noCompileName", { name: s.name }), "error"); return; }
      if (result.info.app) apps += 1;
      blocks.push(markProbed(result.blob));
      gates.push({ name: s.name, gate: exportGate(s) });
    }
    if (apps > SCRIPT_APPS.max) { say(t("plugins.tooManyApps", { count: apps, max: SCRIPT_APPS.max }), "error"); return; }
    if (!(await allowExport(t("plugins.subject.all"), gates))) return;
    const packed = packAll(blocks);
    if (!packed.ok) { say(packed.error.message, "error"); return; }
    saveFile(packed.bytes, ARCHIVE.file, { note: t("plugins.copyAll", { count: blocks.length, folder: ARCHIVE.folder }) });
  }

  open.addEventListener("change", async () => {
    const file = open.files?.[0];
    open.value = "";
    if (!file) return;
    const parsed = parseBlech(new Uint8Array(await file.arrayBuffer()));
    if (!parsed.ok) { say(`${file.name}: ${parsed.error.message}`, "error"); return; }
    if (parsed.source === null) { say(t("plugins.noSource", { file: file.name }), "error"); return; }
    const chosen = workspace.freeName(parsed.parts.header.name);
    workspace.save({ name: chosen, source: parsed.source });
    select("own", chosen);
    page("editor");
    say(t("plugins.opened", { name: chosen, file: file.name }), "ok");
  });

  const nameField = el("div", { className: "cee-ws-name" }, [el("label", { className: "muted", htmlFor: "cee-script-name", textContent: t("mod.field.name") }), name]);
  // Angaben: what an own plugin shows on its card. Kept in this browser with the plugin, not in the file for the device.
  let words = null;                         // the meta of the open own plugin, written back on every edit
  let wordsFor = null;
  const keepWords = () => {
    const mine = own();
    if (!mine || !words || metaProblem(words)) return;
    workspace.save({ name: mine.name, source: mine.source, meta: words });
    renderLists();
  };
  const ownMeta = metaFields("cee-script", () => words, keepWords);
  const pictureCanvas = el("canvas", { className: "cee-lcd cee-catalog-thumb cee-own-picture", id: "cee-script-picture", width: 128, height: 64 });
  pictureCanvas.setAttribute("role", "img");
  pictureCanvas.setAttribute("aria-label", t("plugins.picture"));
  const pictureInput = el("input", { type: "file", className: "cee-visually-hidden", id: "cee-script-picture-file", accept: "image/*" });
  const pictureInvert = el("input", { type: "checkbox", role: "switch", id: "cee-script-picture-invert" });
  const pictureClear = button("cee-script-picture-clear", t("plugins.picture.clear"), () => { if (words) { delete words.image; keepWords(); showPicture(); } }, "sm");
  let pictureSource = null;
  const takePicture = async () => {
    if (!pictureSource || !words) return;
    words.image = toBase64(displayBytes(pixelsOf(pictureSource, { dither: true, invert: !pictureInvert.checked })));
    keepWords();
    showPicture();
  };
  pictureInput.addEventListener("change", async () => {
    const file = pictureInput.files?.[0];
    pictureInput.value = "";
    if (!file) return;
    try {
      pictureSource = await createImageBitmap(file);
      await takePicture();
    } catch {
      toast(t("plugins.picture.bad", { file: file.name }), "error");
    }
  });
  pictureInvert.addEventListener("change", takePicture);
  function showPicture() {
    const mine = own();
    const bytes = words?.image ? fromBase64(words.image) : null;
    if (bytes) drawDisplay(pictureCanvas, bytes); else if (mine) renderThumb(pictureCanvas, { id: mine.name, source: mine.source });
    pictureClear.disabled = !bytes;
  }
  // In a dialog, so the editor keeps the whole height of the page.
  const wordsSection = el("dialog", { className: "ui-dialog cee-own-words-dialog", id: "cee-script-words" });
  wordsSection.setAttribute("aria-labelledby", "cee-script-words-title");
  const wordsBody = el("div", { className: "ui-dialog-body cee-own-words" }, [
    el("div", { className: "cee-own-picture-row" }, [
      pictureCanvas,
      el("div", { className: "cee-meta-fields" }, [
        el("p", { className: "ui-field-help", textContent: t("plugins.picture.help") }),
        el("div", { className: "actions" }, [el("label", { className: "btn sm", htmlFor: "cee-script-picture-file", textContent: t("plugins.picture.pick") }), pictureInput, pictureClear]),
        el("label", { className: "ui-switch" }, [pictureInvert, el("span", { className: "ui-switch-track", ariaHidden: "true" }), t("plugins.picture.invert")]),
      ]),
    ]),
    ownMeta.node,
  ]);
  wordsSection.append(el("form", { method: "dialog", className: "ui-dialog-box" }, [
    el("header", { className: "ui-dialog-head" }, el("h2", { className: "ui-dialog-title", id: "cee-script-words-title", textContent: t("plugins.words.title") })),
    wordsBody,
    el("footer", { className: "ui-dialog-foot" }, el("button", { type: "submit", className: "btn", value: "close", textContent: t("samples.job.done") })),
  ]));
  document.body.append(wordsSection);
  const wordsButton = button("cee-script-words-open", t("plugins.words"), () => { if (window.ui?.openDialog) window.ui.openDialog(wordsSection); else wordsSection.showModal?.(); }, "sm");
  const toolbar = el("div", { className: "cee-ws-toolbar" }, [nameField, note, el("div", { className: "cee-ws-toolbar-actions" }, [copy, wordsButton, duplicate, remove])]);
  const strip = el("div", { className: "cee-ws-strip" }, [status, probeInfo, hint]);

  const runTarget = el("p", { className: "muted", id: "cee-run-target" });

  // The editor is the whole page: no list beside it. Vorschau, Herunterladen and Aufs Gerät stand under it.
  const main = el("div", { className: "cee-ws-main" }, [toolbar, editorHost, problems, strip, el("div", { className: "actions cee-ws-actions" }, [previewButton, exportButton, usbButton])]);
  // Nothing is open until a plugin is chosen: the editor says so and offers the ways to one.
  const emptyEditor = el("div", { className: "cee-ws-empty", id: "cee-editor-empty" }, [
    el("p", { className: "muted", textContent: t("plugins.noneOpen") }),
    el("div", { className: "actions" }, [
      button("cee-editor-empty-new", t("plugins.new"), () => newScript(), "cee-primary"),
      button("cee-editor-empty-open", t("common.open"), () => open.click(), ""),
      button("cee-editor-empty-catalog", t("plugins.toCatalog"), () => { page("catalog"); shelf("catalog"); }, ""),
    ]),
  ]);
  const split = el("div", { className: "cee-workspace", id: "cee-scripts-split" }, [emptyEditor, main]);

  // The preview: the simulated Electribe over the darkened editor; a click beside it or the X closes it.
  const runBox = el("div", { className: "cee-run", id: "cee-run" }, [
    runTarget,
    el("div", { className: "cee-run-bar" }, [runButton, stopButton, probeButton, recordButton, clearInputs, inputsInfo]),
    simRoot,
    log,
  ]);
  const previewClose = el("button", { type: "button", className: "btn icon", id: "cee-plugin-run-close", title: t("plugins.preview.close") }, [icon("x")]);
  previewClose.setAttribute("aria-label", t("plugins.preview.close"));
  const previewDialog = el("dialog", { className: "ui-dialog cee-preview", id: "cee-plugin-run" });
  previewDialog.setAttribute("aria-labelledby", "cee-plugin-run-title");
  const previewBody = el("div", { className: "ui-dialog-body" });
  previewDialog.append(el("div", { className: "ui-dialog-box" }, [
    el("header", { className: "ui-dialog-head" }, [el("h2", { className: "ui-dialog-title", id: "cee-plugin-run-title", textContent: t("plugins.preview") }), previewClose]),
    previewBody,
  ]));
  previewClose.addEventListener("click", () => previewDialog.close());
  previewDialog.addEventListener("click", e => { if (e.target === previewDialog) previewDialog.close(); });
  previewDialog.addEventListener("close", () => { if (runBox.parentNode === previewBody) stop(); });
  document.body.append(previewDialog);
  /** Where a run shows: in the preview of a plugin's page while that is open, else in the preview over the editor. */
  function showRun() {
    panel();
    if (shown === "detail" && detailRun.contains(runBox)) return;
    if (runBox.parentNode !== previewBody) previewBody.append(runBox);
    if (!previewDialog.open) (window.ui?.openDialog ? window.ui.openDialog(previewDialog) : previewDialog.showModal?.());
  }
  function preview() {
    if (start()) return;
    say(t("plugins.preview.noCompile"), "error");
  }

  const thumbs = new Map();
  let thumbsDone = false;

  // The documentation: docs/plugins.md read as a page, with the live table of names as one of its sections.
  const docsSearch = el("input", { className: "input", id: "cee-docs-search", type: "search", placeholder: t("plugins.docs.search"), spellcheck: false, autocomplete: "off" });
  docsSearch.setAttribute("aria-label", t("plugins.docs.search"));
  // The contents stand beside the text and scroll along; on a narrow window they fold above it.
  const docsToc = el("details", { className: "ui-details cee-docs-toc", id: "cee-docs-toc" }, [el("summary", { textContent: t("plugins.docs.toc") }), el("div", { className: "ui-details-body" })]);
  const wide = window.matchMedia?.("(min-width: 60rem)");
  const unfold = () => { docsToc.open = !!wide?.matches; };
  wide?.addEventListener?.("change", unfold);
  unfold();
  const docsArticle = el("article", { className: "cee-docs-article", id: "cee-docs-article" }, [el("p", { className: "muted", textContent: t("plugins.docs.loading") })]);
  const docsEmpty = el("p", { className: "muted", id: "cee-docs-empty", hidden: true, textContent: t("plugins.docs.none") });
  const docsPage = el("div", { className: "cee-plug-page cee-docs" }, [
    el("div", { className: "cee-docs-head" }, [docsSearch]),
    el("div", { className: "cee-docs-body" }, [docsToc, el("div", { className: "cee-docs-text" }, [docsArticle, docsEmpty])]),
  ]);
  /** The heading the reader is at: the last one above the top of the page, for the breadcrumb. */
  let reading = null;
  docsPage.addEventListener("scroll", () => {
    const top = docsPage.getBoundingClientRect().top + 8;
    let at = null;
    for (const h of docsArticle.querySelectorAll(".cee-doc-heading")) {
      if (h.closest("[hidden]")) continue;
      if (h.getBoundingClientRect().top <= top) at = h; else break;
    }
    const text = at?.textContent ?? null;
    // The section you read stands out in the table of contents.
    for (const b of docsToc.querySelectorAll("button[data-target]")) b.toggleAttribute("aria-current", !!at && b.dataset.target === at.id);
    if (text !== reading) { reading = text; trail([{ text: t("plugins.page.docs"), go: () => { docsPage.scrollTo({ top: 0 }); } }, ...(text ? [text] : [])]); }
  }, { passive: true });
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
      docsArticle.replaceChildren(el("p", { className: "cee-error", textContent: t("plugins.docs.failed") }));
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
    if (names) names.node.append(el("div", { className: "cee-names-head" }, [namesFilter, el("p", { className: "muted", textContent: t("plugins.names.hint") })]), namesBody);
    docsArticle.replaceChildren(...docSections.map(s => s.node));
    const tocLink = h => {
      const b = el("button", { type: "button", className: "cee-text-link", textContent: h.text, onclick: () => jumpTo(h.id) });
      b.dataset.target = h.id;
      return b;
    };
    docsToc.querySelector(".ui-details-body").replaceChildren(el("ul", { className: "cee-doc-toc" }, links.map(h => el("li", { className: `cee-doc-toc-${h.level}` }, tocLink(h)))));
  }

  // The catalog: the plugins of the app as cards, each with a picture of its display after a few frames of the browser VM.
  // Beside it, under its own button, the plugins of this browser.
  const catalog = el("ul", { className: "cee-catalog", id: "cee-catalog" }, PRESETS.map(catalogCard));
  const exportAllOwn = exportAll;
  const ownShelf = el("div", { className: "cee-plug-page cee-own-shelf", id: "cee-own-shelf" }, [
    el("div", { className: "actions" }, [newButton, openLabel, open, exportAllOwn]),
    ownEmpty,
    ownList,
    el("p", { className: "muted", textContent: t("plugins.own.local") }),
  ]);
  /** The catalog or Meine Plugins, each its own sub-page. */
  const shelf = id => page(id === "own" ? "mine" : "catalog");

  // A plugin's own page: picture, title, description and details on top; Vorschau and Code below, switched by a segmented control.
  const detailRun = el("div", { className: "cee-detail-run", id: "cee-detail-run" });
  const detailCode = el("pre", { className: "cee-doc-code cee-detail-code", id: "cee-detail-code", tabIndex: 0, hidden: true });
  const detailHead = el("div", { className: "cee-detail-head", id: "cee-detail-head" });
  const views = [["preview", t("plugins.preview")], ["code", t("plugins.view.code")]].map(([id, text]) => {
    const input = el("input", { type: "radio", name: "cee-detail-view", value: id, onchange: () => detailView(id) });
    return el("label", { className: "ui-segmented-option", id: `cee-detail-view-${id}` }, [input, el("span", { textContent: text })]);
  });
  const viewTabs = el("div", { className: "ui-segmented cee-detail-views", role: "radiogroup" }, views);
  viewTabs.setAttribute("aria-label", t("plugins.view.label"));
  const detailPage = el("div", { className: "cee-plug-page cee-detail" }, [
    el("button", { type: "button", className: "cee-text-link cee-detail-back", id: "cee-detail-back", textContent: t("plugins.back"), onclick: () => page("catalog") }),
    detailHead,
    viewTabs,
    detailRun,
    detailCode,
  ]);
  let detailOf = null;
  function detailView(id) {
    for (const v of views) { const input = v.querySelector("input"); input.checked = input.value === id; }
    detailRun.hidden = id !== "preview";
    detailCode.hidden = id !== "code";
    if (id === "preview") {
      detailRun.append(runBox);
      const result = compile(detailOf.source, { name: validName(detailOf.id) ? detailOf.id : "plugin" });
      if (result.ok) start(result.blob, detailOf.id);
      runTarget.textContent = t("plugins.target", { name: detailOf.title });
      probeButton.hidden = true;
    } else stop();
  }
  /** Opens the page of one plugin of the catalog. */
  function openDetail(preset) {
    detailOf = preset;
    const canvas = el("canvas", { className: "cee-lcd cee-catalog-thumb", width: 128, height: 64 });
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", t("plugins.display", { name: preset.title }));
    const { get, usb } = packButtons(preset, true);
    const copyOwn = el("button", { type: "button", className: "btn", id: "cee-detail-copy", textContent: t("plugins.copy"), onclick: () => { select("preset", preset.id); copyPreset(); page("editor"); } });
    const added = new Date(`${preset.added}T12:00:00`).toLocaleDateString(locale(), { day: "numeric", month: "long", year: "numeric" });
    detailHead.replaceChildren(
      canvas,
      el("div", { className: "cee-detail-text" }, [
        el("h2", { className: "cee-detail-title", id: "cee-detail-title", textContent: preset.title }),
        el("p", { textContent: preset.description }),
        el("dl", { className: "cee-detail-facts" }, [
          el("dt", { textContent: t("samples.fact.category") }), el("dd", { textContent: preset.category }),
          el("dt", { textContent: t("plugins.by") }), el("dd", {}, creatorName(preset.creator) ?? "?"),
          el("dt", { textContent: t("plugins.added") }), el("dd", {}, el("time", { dateTime: preset.added, textContent: added })),
          el("dt", { textContent: t("presets.map") }), el("dd", {}, preset.controls.length ? el("ul", { className: "cee-detail-controls" }, preset.controls.map(c => el("li", { textContent: c }))) : t("plugins.noControls")),
        ]),
        el("div", { className: "actions" }, [get, usb, copyOwn]),
      ]),
    );
    renderThumb(canvas, preset);
    // Coloured like the editor: the same tokenizer, the same token classes.
    detailCode.replaceChildren(...highlightLines(preset.source).flatMap((pieces, i) => [
      ...(i ? ["\n"] : []),
      ...pieces.map(([text, type]) => type ? el("span", { className: type.split(".").map(t => `tok-${t}`).join(" "), textContent: text }) : text),
    ]));
    page("detail");
    trail([{ text: t("plugins.page.catalog"), go: () => { page("catalog"); shelf("catalog"); } }, preset.title]);
    detailView("preview");
  }

  const PAGES = [
    { id: "catalog", title: t("plugins.page.catalog"), node: el("div", { className: "cee-plug-page" }, [catalog]) },
    { id: "mine", title: t("plugins.page.mine"), node: ownShelf },
    { id: "editor", title: t("plugins.page.editor"), node: split },
    { id: "docs", title: t("plugins.page.docs"), node: docsPage },
    { id: "detail", title: t("plugins.fault.plugin"), node: detailPage, hidden: true },
  ];
  for (const p of PAGES) { p.node.id ||= `cee-plugin-${p.id}`; p.node.hidden = true; p.node.dataset.page = p.id; }
  root.replaceChildren(...PAGES.map(p => p.node));

  let shown = null;
  const PAGE_ICONS = { catalog: "grid", mine: "folder", editor: "code", docs: "book" };
  const subPages = sub?.pages("scripts", { id: "cee-scripts-pages", label: t("plugins.pages"), items: PAGES.filter(p => !p.hidden).map(({ id, title }) => ({ id, title, icon: PAGE_ICONS[id] })), pick: id => page(id) });
  /** Opens one of the pages of Plugins: the catalog, a plugin's page, the editor, the documentation. */
  function page(id) {
    if (!PAGES.some(p => p.id === id)) id = "editor";
    if (id === shown) return;
    if (shown === "detail") { stop(); probeButton.hidden = false; runTarget.textContent = current ? t("plugins.target", { name: current.id }) : ""; }
    shown = id;
    for (const p of PAGES) p.node.hidden = p.id !== id;
    subPages?.select(id === "detail" ? "catalog" : id);
    reading = null;
    trail(id === "editor" ? [t("plugins.page.editor"), ...(current ? [current.id] : [])] : [PAGES.find(p => p.id === id).title]);
    navbar(id === "editor" ? [openNav, saveNav] : []);
    if (id === "catalog") drawThumbs();
    if (id === "docs") loadDocs();
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

  /** Herunterladen and Aufs Gerät for a plugin of the catalog; `text` gives them words besides the icon. */
  function packButtons(preset, text = false) {
    const make = (name, label, onclick, primary = false) => {
      const b = el("button", { type: "button", className: `btn${text ? "" : " icon"}${primary ? " cee-primary" : ""}`, title: label, onclick }, [icon(name), text ? label : null]);
      if (!text) b.setAttribute("aria-label", label);
      return b;
    };
    const pack = () => {
      const result = compile(preset.source, { name: validName(preset.id) ? preset.id : "plugin" });
      const probed = result.ok ? runProbe(result.blob) : null;
      const packed = probed?.ok ? packBlech(markProbed(result.blob), preset.source) : null;
      if (!packed?.ok) { say(packed?.error?.message ?? t("plugins.cannotSave"), "error"); return null; }
      return packed.bytes;
    };
    const get = make("download", t("plugins.download"), () => {
      const bytes = pack();
      if (bytes) saveFile(bytes, `${preset.id}.blech`, { note: t("plugins.copyTo", { folder: ARCHIVE.folder }) });
    });
    const usb = make("usb", t("plugins.toDevice"), () => {
      const bytes = pack();
      if (bytes) toDevice(bytes, preset.id, usb);
    }, true);
    return { get, usb };
  }

  function catalogCard(preset) {
    const canvas = el("canvas", { className: "cee-lcd cee-catalog-thumb", width: 128, height: 64 });
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", t("plugins.display", { name: preset.title }));
    thumbs.set(canvas, preset);
    // The whole card leads to the plugin's page (the title's button covers it); download and device are there.
    const title = el("button", { type: "button", className: "cee-catalog-open", textContent: preset.title, onclick: () => openDetail(preset) });
    return el("li", { className: "cee-catalog-card", id: `cee-catalog-${preset.id}` }, [
      canvas,
      el("h3", {}, title),
      el("p", { className: "cee-catalog-category", textContent: preset.category }),
      el("p", { className: "muted", textContent: preset.description }),
      creatorLine(preset.creator),
    ]);
  }

  renderNames();
  page("catalog");
  updateActions();
  renderLists();

  return {
    /** The names the terminal's run() accepts. */
    names: () => [...PRESETS.map(p => p.id), ...workspace.list().map(s => s.name)],
    /** Start a saved script or a template in the run area. Returns what happened in words. */
    runNamed(wanted) {
      const key = String(wanted).replace(/^.*[\\/]/, "").replace(/\.(blech|js)$/i, "");
      const mine = workspace.get(key);
      const preset = PRESETS.find(p => p.id === key || p.title === key);
      const source = mine?.source ?? preset?.source;
      if (source === undefined) throw new Error(t("plugins.unknown", { name: wanted, list: [...PRESETS.map(p => p.id), ...workspace.list().map(s => s.name)].join(", ") }));
      const label = mine?.name ?? preset.id;
      const result = compile(source, { name: validName(label) ? label : "plugin" });
      if (!result.ok) throw new Error(result.errors.map(formatError).join("\n"));
      start(result.blob, label);
      onRun();
      return t("plugins.running", { name: label });
    },
    /** Run lines of script language once, at the first frame, in the run area. */
    runSnippet(code) {
      const result = compile(`korg.app("einzeiler", "TOOLS");\nkorg.onEvent("ready", () => {\n${code.trim().replace(/;?$/, ";")}\n});`, { name: "einzeiler" });
      if (!result.ok) throw new Error(result.errors.map(e => `${formatError({ ...e, line: Math.max(1, e.line - 2) })}`).join("\n"));
      start(result.blob, "einzeiler");
      onRun();
      return t("plugins.snippetRunning");
    },
    stop,
    page,
    get running() { return !!live; },
  };
}
