/**
 * Pattern-Werkzeuge: einen Part würfeln (src/dice.mjs). Kein Pattern-Editor: die Seite liest Patterns aus einer Sicherung, einer
 * Einzeldatei oder dem Pattern-Puffer des verbundenen Geräts, rechnet eine Vorschau und gibt das
 * Ergebnis weiter, als Datei, als Kopie der Sicherung mit neuen Patterns oder ans Gerät. Nichts
 * davon verändert die geladene Datei, und ans Gerät geht nur, was Linter und Türsteher durchlassen
 * und du bestätigt hast.
 */
import { el } from "./fields.mjs";
import { stateText } from "./state.mjs";
import { saveFile } from "./save-file.mjs";
import { toast } from "./toast.mjs";
import { stepEditor } from "./steps.mjs";
import { PatternFile, Pattern, parseSinglePattern, toSinglePattern, FileError, cleanName, NAME_LENGTH } from "../../src/pattern.mjs";
import { rollPart, checkRoll, SCALES, ROOTS, DEFAULTS } from "../../src/dice.mjs";
import { isFree } from "../../src/pattern-set.mjs";
import { t } from "./i18n.mjs";

const SLOTS = 250;
const MAX_DEVICE_COPIES = 8;

function field(id, label, input, help) {
  return el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: id, textContent: label }), input, help ? el("p", { className: "ui-field-help", textContent: help }) : null]);
}

function selectField(id, label, options, value, onChange) {
  const input = el("select", { className: "select", id });
  for (const [v, text] of options) input.append(el("option", { value: String(v), textContent: text }));
  input.value = String(value);
  input.addEventListener("change", () => onChange(input.value));
  return { node: field(id, label, input), input };
}

function numberField(id, label, { min, max, value, onChange, help = "" }) {
  const input = el("input", { className: "input", id, type: "number", min, max, step: 1, value: String(value) });
  input.addEventListener("input", () => onChange(input.value));
  return { node: field(id, label, input, help), input };
}

function textField(id, label, { value = "", placeholder = "", onChange, help = "" }) {
  const input = el("input", { className: "input", id, type: "text", maxLength: NAME_LENGTH, spellcheck: false, autocomplete: "off", value, placeholder });
  input.addEventListener("change", () => onChange(input.value));
  return { node: field(id, label, input, help), input };
}

function switchField(id, label, checked, onChange) {
  const input = el("input", { type: "checkbox", id, checked });
  input.setAttribute("role", "switch");
  input.addEventListener("change", () => onChange(input.checked));
  return { node: el("div", { className: "cee-field" }, [el("label", { className: "ui-switch" }, [input, el("span", { className: "ui-switch-track", ariaHidden: "true" }), label])]), input };
}

function rangeField(id, label, { min, max, value, show, onChange }) {
  const input = el("input", { type: "range", className: "ui-range", id, min, max, step: 1, value: String(value) });
  const out = el("output", { className: "ui-range-value" });
  const sync = () => { out.textContent = show(Number(input.value)); input.setAttribute("aria-valuetext", out.textContent); window.ui?.syncRange(input); };
  input.addEventListener("input", () => { sync(); onChange(Number(input.value)); });
  sync();
  return { node: el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: id }, [label, " ", out]), input]), input, sync };
}

const fileStem = name => String(name || "patterns").replace(/\.[^.]*$/, "");
const safe = name => (name.replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "") || "pattern");
const randomSeed = () => crypto.getRandomValues(new Uint32Array(1))[0];

export function patternToolsPage(root, { device }) {
  /** What the pickers offer: the loaded backup or single file, and copies of the device's buffer. */
  const pool = { file: null, fileName: "", single: null, free: new Set(), copies: [], copyCount: 0 };
  const pickers = [];
  // Messages go to the toast; only a running step ("Sende …") stands in the line.
  const say = (text, tone = "info") => {
    line.textContent = tone === "progress" ? text : "";
    if (tone !== "progress") toast(text, tone);
  };
  const line = el("p", { className: "muted ui-break", id: "cee-pt-line", role: "status" });

  // ---- Quelle ----
  const input = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-pt-file", accept: ".e2sallpat,.e2spat" });
  const loaded = el("p", { className: "muted", id: "cee-pt-loaded", textContent: t("ptools.noFile") });
  input.addEventListener("change", () => { const f = input.files?.[0]; if (f) load(f); });
  const undoSend = el("button", { type: "button", className: "btn", id: "cee-pt-undo", textContent: t("backup.sendUndo"), disabled: true });
  const connectEmu = el("button", { type: "button", className: "btn", id: "cee-pt-connect-emu", textContent: t("device.connectEmu") });
  connectEmu.addEventListener("click", () => device.connectEmulator());
  const source = el("section", { className: "ui-section" }, [
    el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: t("ptools.source") })]),
    el("p", { className: "muted", textContent: t("ptools.source.lead") }),
    el("label", { className: "ui-dropzone" }, [
      input,
      el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: t("backup.drop.drag") }), t("common.pick")]),
      el("span", { className: "ui-dropzone-hint", textContent: t("backup.drop.hint") }),
      el("span", { className: "ui-dropzone-files" }),
    ]),
    loaded,
    el("div", { className: "actions cee-pt-device-row" }, [connectEmu, undoSend]),
    line,
  ]);

  async function load(file) {
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const single = bytes.length === 0x100 + 0x4000;
      const parsed = single ? parseSinglePattern(bytes) : PatternFile.parse(bytes);
      pool.fileName = file.name;
      pool.file = single ? null : parsed;
      pool.single = single ? parsed : null;
      pool.free = new Set();
      if (pool.file) for (let n = 1; n <= pool.file.count; n++) if (isFree(pool.file.pattern(n))) pool.free.add(n);
      loaded.textContent = (single ? t("backup.loaded.one", { file: file.name }) : t("ptools.loaded", { file: file.name, count: pool.file.count, free: pool.free.size }));
      for (const p of pickers) p.fill({ reset: true });
      dice.roll();
    } catch (e) {
      const message = e instanceof FileError ? e.message : t("sampleset.unreadable", { error: e.message });
      if (window.ui?.rejectFile) window.ui.rejectFile(input, message); else toast(message, "error");
    }
  }

  /** A pattern chosen in a picker: its bytes as a Pattern, where it sits in the backup (or null), and a label. */
  function resolve(value) {
    if (value === "single" && pool.single) return { pattern: new Pattern(pool.single.bytes), number: null, label: pool.fileName };
    if (value.startsWith("copy:")) {
      const copy = pool.copies.find(c => c.id === value);
      return copy ? { pattern: new Pattern(copy.bytes), number: null, label: copy.label } : null;
    }
    const n = Number(value);
    return pool.file && n >= 1 && n <= pool.file.count ? { pattern: pool.file.pattern(n), number: n, label: `${n} ${pool.file.name(n) || t("backup.noName")}` } : null;
  }

  function picker(id, label, which, onPick) {
    const select = el("select", { className: "select", id });
    const fetch = el("button", { type: "button", className: "btn", id: `${id}-fetch`, textContent: t("backup.fetch"), disabled: true });
    function fill({ reset = false } = {}) {
      const keep = reset ? null : select.value;
      select.replaceChildren();
      if (pool.single) select.append(el("option", { value: "single", textContent: t("ptools.file", { name: pool.single.name || t("backup.noName") }) }));
      if (pool.file) for (let n = 1; n <= pool.file.count; n++) select.append(el("option", { value: String(n), textContent: `${n}  ${pool.file.name(n) || t("backup.noName")}${pool.free.has(n) ? ` ${t("ptools.free")}` : ""}` }));
      for (const c of pool.copies) select.append(el("option", { value: c.id, textContent: c.label }));
      select.disabled = !select.options.length;
      if (select.disabled) select.append(el("option", { value: "", textContent: t("ptools.empty") }));
      if (keep && [...select.options].some(o => o.value === keep)) select.value = keep;
      else if (pool.file) select.value = String(firstWithContent(which));
    }
    fetch.addEventListener("click", async () => {
      const copy = await fetchFromDevice();
      if (!copy) return;
      fill({});
      select.value = copy.id;
      for (const p of pickers) if (p.select !== select) p.fill({});
      onPick();
    });
    select.addEventListener("change", onPick);
    const node = field(id, label, select);
    node.append(fetch);
    const p = { select, fill, fetch, node };
    pickers.push(p);
    return p;
  }

  /** The first and second pattern with content: where the pickers start on a backup. */
  function firstWithContent(which) {
    const used = [...Array(pool.file.count)].map((_, i) => i + 1).filter(n => !pool.free.has(n));
    return used[which] ?? used[0] ?? Math.min(which + 1, pool.file.count);
  }

  async function fetchFromDevice() {
    const s = device.session;
    if (!s) { say(t("levels.nothing"), "error"); return null; }
    const release = s.reserve();
    try {
      await s.idle();
      const bytes = Uint8Array.from(await s.fetchPattern());
      const name = new Pattern(bytes).name || t("backup.noName");
      pool.copyCount++;
      const copy = { id: `copy:${pool.copyCount}`, bytes, label: t("ptools.copy", { n: pool.copyCount, name }) };
      pool.copies.push(copy);
      if (pool.copies.length > MAX_DEVICE_COPIES) pool.copies.shift();
      say(t("ptools.fetched", { name }), "ok");
      return copy;
    } catch (e) {
      say(t("backup.fetchFailed", { error: e.message }), "error");
      return null;
    } finally {
      release();
    }
  }

  /** Fetching and sending use the device's own gate and confirmation; the same flow as the other pattern transport. */
  async function sendToDevice(pattern, label) {
    const s = device.session;
    if (!s) return;
    const release = s.reserve();
    try {
      await s.idle();
      let active = t("backup.unknown");
      try { active = new Pattern(await s.fetchPattern()).name || t("backup.noName"); } catch (e) {
        say(t("backup.noBackup", { error: e.message }), "error");
        return;
      }
      const edit = { kind: "patternSend", block: Uint8Array.from(pattern.bytes) };
      const checked = await s.check(edit);
      if (checked.verdict === "blocked") { say(t("backup.blocked", { reasons: checked.reasons.map(r => r.message).join(" ") }), "error"); return; }
      const warnings = checked.reasons.map(r => t("backup.warning", { message: r.message })).join("\n");
      const yes = await window.ui.confirm({
        title: t("ptools.send.title", { name: label }),
        text: `${t("ptools.send.text", { name: active })}${warnings ? `\n\n${warnings}` : ""}`,
        confirmLabel: t("backup.send.confirm"),
      });
      if (!yes) return;
      say(t("backup.sending"), "progress");
      const res = await s.apply(edit, { confirmed: checked.token });
      if (res.ok) say(t("ptools.sent", { name: label, before: active }), "ok");
      else if (res.needsConfirmation) say(t("backup.changed"), "error");
      else if (res.gate?.verdict === "blocked") say(t("backup.blocked", { reasons: res.gate.reasons.map(r => r.message).join(" ") }), "error");
      else say(`${res.error?.message ?? t("common.aborted")}${res.pending?.now ? ` ${res.pending.now.text}` : ""}${s.blocked ? ` ${t("backup.decide")}` : ""}`, "error");
      device.log?.(res.ok ? t("backup.sentLog") : t("backup.failedLog", { error: res.error?.message ?? t("backup.locked") }), res.ok ? "ok" : "error");
      if (s.blocked) device.showDecision?.();
    } catch (e) {
      say(t("backup.aborted", { error: e.message }), "error");
    } finally {
      release();
      sessionChanged();
    }
  }

  undoSend.addEventListener("click", async () => {
    const s = device.session;
    if (!s) return;
    const release = s.reserve();
    try {
      await s.idle();
      const res = await s.undo();
      say(res.ok ? t("backup.undone") : t("backup.undoFailed", { error: res.error.message }), res.ok ? "ok" : "error");
    } catch (e) {
      say(t("backup.undoFailed", { error: e.message }), "error");
    } finally {
      release();
      sessionChanged();
    }
  });

  /** Put patterns into a copy of the loaded backup and offer it as a download; occupied slots ask first. */
  async function intoBackup(items) {
    if (!pool.file) return;
    const taken = items.filter(it => !pool.free.has(it.slot));
    if (taken.length) {
      const list = taken.map(it => `${it.slot} ${pool.file.name(it.slot) || t("backup.noName")}`).join(", ");
      const yes = await window.ui.confirm({
        title: t("ptools.overwrite.title"),
        text: t("ptools.overwrite.text", { list }),
        confirmLabel: t("ptools.overwrite.confirm"), danger: true,
      });
      if (!yes) return;
    }
    const all = new PatternFile(pool.file.header.slice(), pool.file.blocks.map(b => b.slice()));
    for (const it of items) all.replace(it.slot, it.pattern);
    const name = `${fileStem(pool.fileName)}-neu.e2sallpat`;
    saveFile(all.toBytes(), name);
    say(t("ptools.saved.backup", { name, slots: items.map(i => i.slot).join(", ") }), "ok");
  }

  const saveSingle = (pattern, name) => { saveFile(toSinglePattern(pattern), name); say(t("ptools.saved", { name }), "ok"); };

  /** Findings as a list; true when one of them stops the output. */
  function findingsList(findings) {
    const list = el("ul", { className: "ui-list cee-pt-findings" });
    for (const f of findings) list.append(el("li", { className: "ui-row" }, [stateText(f.severity === "error" ? "error" : "warn", f.severity === "error" ? t("common.error") : t("device.log.warn")), el("span", { textContent: ` ${t(f.text ?? f.message)}` })]));
    return list;
  }

  // ---- Würfeln ----
  const dice = (() => {
    const D = { ...DEFAULTS, seed: randomSeed(), name: "", swingOn: false, swingValue: 0 };
    let rolled = null;
    const doc = {
      get: (id, ix = []) => rolled.pattern.raw(id, ix),
      set: (id, ix, raw) => { rolled.pattern.setRaw(id, ix, raw); showFindings(); },
      group: fn => fn(),
    };
    const steps = stepEditor(doc);
    const base = picker("cee-pt-dice-base", t("ptools.d.base"), 0, () => roll());
    const status = el("p", { id: "cee-pt-d-text", role: "status" });
    const warn = el("ul", { className: "cee-pt-notes", id: "cee-pt-d-warnings" });
    const findings = el("div", { id: "cee-pt-d-findings" });
    const slot = numberField("cee-pt-d-slot", t("ptools.d.slot"), { min: 1, max: SLOTS, value: "", onChange: () => syncButtons() });
    const save = el("button", { type: "button", className: "btn", id: "cee-pt-d-save", textContent: t("ptools.saveSingle") });
    const send = el("button", { type: "button", className: "btn", id: "cee-pt-d-send", textContent: t("backup.send"), disabled: true });
    const intoFile = el("button", { type: "button", className: "btn cee-primary", id: "cee-pt-d-backup", textContent: t("ptools.intoBackup") });
    const hint = el("span", { className: "muted", id: "cee-pt-d-hint" });

    const seed = numberField("cee-pt-seed", t("ptools.d.seed"), { min: 0, max: 4294967295, value: D.seed, onChange: v => { D.seed = Number(v); roll(); } });
    const again = el("button", { type: "button", className: "btn", id: "cee-pt-reroll", textContent: t("ptools.d.again") });
    again.addEventListener("click", () => { D.seed = randomSeed(); seed.input.value = String(D.seed); roll(); });
    const nameField = textField("cee-pt-d-name", t("ptools.d.name"), { placeholder: t("ptools.d.name.auto"), help: t("ptools.d.name.help"), onChange: v => { D.name = v; roll(); } });
    const kind = selectField("cee-pt-kind", t("levels.kind"), [["drums", t("ptools.d.kind.drums")], ["melody", t("ptools.d.kind.melody")]], D.kind, v => { D.kind = v; syncKind(); roll(); });
    const part = selectField("cee-pt-part", t("ptools.d.part"), Array.from({ length: 16 }, (_, i) => [i, t("backup.part", { part: i + 1 })]), D.part, v => { D.part = Number(v); roll(); });
    const density = rangeField("cee-pt-density", t("ptools.d.density"), { min: 0, max: 100, value: D.density * 100, show: v => `${v} %`, onChange: v => { D.density = v / 100; roll(); } });
    const scale = selectField("cee-pt-scale", t("ptools.d.scale"), SCALES.map(s => [s.name, s.name]), D.scale, v => { D.scale = v; roll(); });
    const rootF = selectField("cee-pt-root", t("ptools.d.root"), ROOTS.map((r, i) => [i, r]), D.root, v => { D.root = Number(v); roll(); });
    const octave = selectField("cee-pt-octave", t("ptools.d.octave"), [1, 2, 3, 4, 5, 6].map(o => [o, `C${o}`]), D.octave, v => { D.octave = Number(v); roll(); });
    const span = selectField("cee-pt-span", t("ptools.d.span"), [[1, t("ptools.d.span1")], [2, t("ptools.d.span2")], [3, t("ptools.d.span3")]], D.span, v => { D.span = Number(v); roll(); });
    const gate = rangeField("cee-pt-gate", t("ptools.d.gate"), { min: 0, max: 100, value: D.gate * 100, show: v => `${v} %`, onChange: v => { D.gate = v / 100; roll(); } });
    const accent = rangeField("cee-pt-accent", t("ptools.d.accent"), { min: 0, max: 100, value: D.accent * 100, show: v => `${v} %`, onChange: v => { D.accent = v / 100; roll(); } });
    const bars = selectField("cee-pt-bars", t("samples.fact.length"), [["", t("ptools.d.bars.pattern")], [1, t("ptools.d.bars1")], [2, t("ptools.d.bars2")], [3, t("ptools.d.bars3")], [4, t("ptools.d.bars4")]], "", v => { D.bars = v === "" ? null : Number(v); roll(); });
    const swingOn = switchField("cee-pt-swing-on", t("ptools.d.swingOn"), D.swingOn, v => { D.swingOn = v; swing.input.disabled = !v; roll(); });
    const swing = numberField("cee-pt-swing", t("ptools.d.swing"), { min: -48, max: 48, value: 0, onChange: v => { D.swingValue = Number(v); roll(); } });
    swing.input.disabled = true;
    const unmute = switchField("cee-pt-unmute", t("ptools.d.unmute"), D.unmute, v => { D.unmute = v; roll(); });
    const writeScale = switchField("cee-pt-write-scale", t("ptools.d.writeScale"), D.writeScale, v => { D.writeScale = v; roll(); });
    const melodyOnly = [scale, rootF, octave, span, writeScale];
    function syncKind() { for (const f of melodyOnly) { f.node.hidden = D.kind !== "melody"; } }
    syncKind();

    const node = el("section", { className: "ui-section" }, [
      el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: t("ptools.d.title") })]),
      el("p", { className: "muted", textContent: t("ptools.d.lead") }),
      el("div", { className: "cee-grid" }, [base.node, part.node, kind.node, density.node, seed.node, el("div", { className: "ui-field" }, [again])]),
      el("div", { className: "cee-grid" }, [scale.node, rootF.node, octave.node, span.node, gate.node, accent.node, bars.node, swing.node]),
      el("div", { className: "cee-grid" }, [swingOn.node, unmute.node, writeScale.node]),
      status, warn,
      steps.node,
      el("p", { className: "muted", textContent: t("ptools.d.stepsHint") }),
      findings,
      el("div", { className: "cee-grid" }, [nameField.node, slot.node]),
      el("div", { className: "actions" }, [intoFile, save, send, hint]),
    ]);

    function options() {
      return { part: D.part, kind: D.kind, density: D.density, seed: D.seed, root: D.root, scale: D.scale, octave: D.octave, span: D.span, gate: D.gate, accent: D.accent, swing: D.swingOn ? D.swingValue : null, bars: D.bars, unmute: D.unmute, writeScale: D.writeScale, name: D.name.trim() ? D.name : `DICE ${D.seed}` };
    }

    function roll() {
      const from = resolve(base.select.value);
      rolled = null;
      warn.replaceChildren();
      findings.replaceChildren();
      if (!from) { status.textContent = t("ptools.d.pickBase"); steps.node.hidden = true; syncButtons(); return; }
      try {
        const r = rollPart(from.pattern, options());
        rolled = { ...r, from };
      } catch (e) {
        status.textContent = e.message;
        steps.node.hidden = true;
        syncButtons();
        return;
      }
      status.textContent = t("ptools.d.status", { text: rolled.text, name: rolled.pattern.name });
      warn.replaceChildren(...rolled.warnings.map(w => el("li", { textContent: w })));
      steps.node.hidden = false;
      steps.show(D.part);
      if (pool.file && !slot.input.dataset.touched) {
        const free = [...pool.free];
        const near = from.number ?? 0;
        slot.input.value = String(free.find(s => s > near) ?? free[0] ?? from.number ?? 1);
      }
      showFindings();
    }

    function showFindings() {
      if (!rolled) return;
      findings.replaceChildren(...(checkRoll(rolled.pattern).length ? [findingsList(checkRoll(rolled.pattern))] : []));
      syncButtons();
    }

    function syncButtons() {
      const stop = !rolled || checkRoll(rolled.pattern).some(f => f.severity === "error");
      save.disabled = stop;
      send.disabled = stop || !device.session;
      const n = Number(slot.input.value);
      const limit = pool.file?.count ?? 0;
      const okSlot = Number.isInteger(n) && n >= 1 && n <= limit;
      intoFile.disabled = stop || !pool.file || !okSlot;
      hint.textContent = !pool.file ? t("ptools.d.needFile") : !okSlot ? t("ptools.d.slotRange", { limit }) : pool.free.has(n) ? t("ptools.d.slotFree") : t("ptools.d.slotTaken");
    }

    slot.input.addEventListener("input", () => { slot.input.dataset.touched = "1"; });
    save.addEventListener("click", () => saveSingle(rolled.pattern, `${safe(rolled.pattern.name)}.e2spat`));
    send.addEventListener("click", () => sendToDevice(rolled.pattern, rolled.pattern.name));
    intoFile.addEventListener("click", () => intoBackup([{ slot: Number(slot.input.value), pattern: rolled.pattern }]));
    return { node, roll, syncButtons };
  })();

  // ---- Zusammenbau ----
  const intro = el("p", { className: "cee-pt-intro", textContent: t("ptools.intro") });
  root.replaceChildren(intro, source, dice.node);
  for (const p of pickers) p.fill({ reset: true });
  dice.roll();

  function sessionChanged() {
    const s = device.session;
    for (const p of pickers) p.fetch.disabled = !s;
    undoSend.disabled = !s || !s.history.some(h => h.pattern);
    dice.syncButtons();
  }

  return { sessionChanged };
}
