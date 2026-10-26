/**
 * The levels of the pattern in the device's buffer side by side (play level,
 * part levels, output levels of the insert presets in use), scaled together
 * with a preview and sent over the normal pattern send path. The insert levels
 * are shown, not scaled: a preset can serve several parts and patterns, and
 * changing it is the effect editor's job.
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { Pattern } from "../../src/pattern.mjs";
import { FxRecord } from "../../src/record.mjs";
import { profileKey } from "../../src/profile.mjs";
import { readLevels, planScale, applyScale, outputLevels, judgeOutput, LEVEL_MAX } from "../../src/gain.mjs";
import { t } from "./i18n.mjs";

const pill = (tone, word) => {
  const p = el("span", { className: "cee-status", textContent: word });
  p.dataset.tone = tone;
  return p;
};

const number = n => String(Math.round(n * 100) / 100).replace(".", ",");

/**
 * @param {HTMLElement} root
 * @param {object} opts
 * @param {() => Promise<object | null>} opts.session the session to read the buffer from and send to: the attached device, else the running emulator
 * @param {() => {list: (kind: string) => {slot: number, name: string, record: object}[], units: object, profile: object | null} | null} opts.presets the presets of the loaded firmware, null before one is loaded
 * @param {(slot: number) => void} opts.openPreset show an insert preset in the effect editor
 * @param {{log?: Function, showDecision?: Function}} [opts.device]
 */
export function levelsPanel(root, { session, presets, openPreset, device = {} }) {
  const state = { block: null, name: "", mode: "factor", value: "1", master: false, sendable: false };

  const fetchButton = el("button", { type: "button", className: "btn", id: "cee-lv-fetch", textContent: t("levels.fetch") });
  const sendButton = el("button", { type: "button", className: "btn cee-primary", id: "cee-lv-send", textContent: t("levels.send"), disabled: true });
  const undoButton = el("button", { type: "button", className: "btn", id: "cee-lv-undo", textContent: t("backup.sendUndo"), disabled: true });
  const body = el("div", { className: "cee-levels", id: "cee-lv-body", hidden: true });
  // `kind` where the caller knows it; a message from elsewhere is judged by its words.
  const say = (text, kind) => {
    toast(text, kind ?? (/nicht geklappt|nicht holen|nicht sichern|Gesperrt|Abgebrochen|Nichts verbunden|inzwischen etwas geändert|Entscheide/.test(text) ? "error" : /^(Geholt|Gesendet|Der vorherige)/.test(text) ? "ok" : "info"));
  };
  const attached = async () => {
    try {
      const s = await session();
      if (!s) say(t("levels.nothing"), "error");
      return s;
    } catch (e) { say(e.message); return null; }
  };

  const modes = el("div", { className: "ui-segmented" });
  modes.setAttribute("role", "radiogroup");
  modes.setAttribute("aria-label", t("levels.scale"));
  const modeInputs = [["factor", t("levels.mode.factor")], ["target", t("levels.mode.target")]].map(([value, text]) => {
    const input = el("input", { type: "radio", name: "cee-lv-mode", value, checked: value === state.mode });
    input.addEventListener("change", () => {
      if (!input.checked) return;
      state.mode = value;
      state.value = value === "factor" ? "1" : String(readLevels(pattern()).parts.reduce((m, p) => Math.max(m, p.value), 0));
      valueInput.value = state.value;
      draw();
    });
    modes.append(el("label", { className: "ui-segmented-option" }, [input, el("span", { textContent: text })]));
    return input;
  });
  const valueInput = el("input", { type: "number", className: "input", id: "cee-lv-value", min: "0", step: "0.05", value: state.value });
  const valueLabel = el("label", { className: "ui-field-label", htmlFor: "cee-lv-value", textContent: t("levels.mode.factor") });
  valueInput.addEventListener("input", () => { state.value = valueInput.value; draw(); });
  const masterToggle = el("input", { type: "checkbox", id: "cee-lv-master" });
  masterToggle.setAttribute("role", "switch");
  masterToggle.addEventListener("change", () => { state.master = masterToggle.checked; draw(); });

  const summary = el("p", { id: "cee-lv-summary", ariaLive: "polite" });
  const rows = el("div", { className: "cee-level-rows", id: "cee-lv-rows" });
  const fxRows = el("div", { className: "cee-group", id: "cee-lv-fx" });
  const controls = el("div", { className: "cee-levels-controls" }, [
    el("div", { className: "ui-field" }, [el("span", { className: "ui-field-label", textContent: t("levels.kind") }), modes]),
    el("div", { className: "ui-field" }, [valueLabel, valueInput]),
    el("label", { className: "ui-switch" }, [masterToggle, el("span", { className: "ui-switch-track", ariaHidden: "true" }), t("levels.master")]),
  ]);
  body.append(controls, summary, rows, fxRows, el("div", { className: "actions" }, [sendButton, undoButton]));

  const pattern = () => new Pattern(state.block);
  const plan = () => planScale(readLevels(pattern()), { mode: state.mode, value: Number(String(state.value).replace(",", ".")), master: state.master });

  function meter(node, value, label) {
    node.className = "ui-meter";
    node.dataset.size = "sm";
    window.ui?.setMeter?.(node, (value / LEVEL_MAX) * 100, { label, valueText: String(value) });
  }

  function draw() {
    valueLabel.textContent = state.mode === "factor" ? t("levels.mode.factor") : t("levels.target");
    valueInput.step = state.mode === "factor" ? "0.05" : "1";
    const p = plan();
    rows.replaceChildren();
    const levels = readLevels(pattern());
    const shown = p.error ? [levels.master, ...levels.parts].map(l => ({ ...l, before: l.value, after: l.value, delta: 0 })) : p.rows;
    const all = new Map(shown.map(r => [r.id + r.indices, r]));
    for (const l of [levels.master, ...levels.parts]) {
      const r = all.get(l.id + l.indices) ?? { before: l.value, after: l.value, delta: 0 };
      const bar = el("span", { className: "cee-level-bar" });
      meter(bar, r.after, l.label);
      const text = r.delta === 0 ? String(r.before) : t("levels.change", { before: r.before, after: r.after });
      const row = el("div", { className: "cee-level-row", id: `cee-lv-row-${l.part ?? "pattern"}` }, [
        el("span", { className: "cee-level-name", textContent: l.id === "pattern.playLevel" ? t("levels.playLevel") : l.label }),
        bar,
        el("span", { className: "cee-level-value", textContent: text }),
        l.muted ? pill("neutral", t("levels.muted")) : null,
      ]);
      row.dataset.changed = String(r.delta !== 0);
      rows.append(row);
    }
    if (p.error) {
      summary.textContent = p.error;
      summary.className = "cee-hint";
    } else {
      summary.className = "";
      const changed = p.rows.filter(r => r.delta !== 0).length;
      summary.textContent = p.changed
        ? `${t(changed === 1 ? "levels.summary.one" : "levels.summary.many", { factor: number(p.factor), before: p.peakBefore, after: p.peakAfter, count: changed })}${p.limited ? ` ${t("levels.summary.limited", { requested: number(p.requested), max: LEVEL_MAX, factor: number(p.factor) })}` : ""}`
        : t("levels.unchanged");
    }
    sendButton.disabled = !!p.error || !p.changed || !state.sendable;
  }

  function drawFx(found) {
    fxRows.replaceChildren(el("h3", { textContent: t("levels.fx.title") }));
    if (!found) {
      fxRows.append(el("p", { className: "muted", textContent: t("levels.fx.noFirmware") }));
      return;
    }
    if (!found.length) {
      fxRows.append(el("p", { className: "muted", textContent: t("levels.fx.none") }));
      return;
    }
    const list = el("ul", { className: "ui-list" });
    for (const f of found) {
      const text = f.levels.length
        ? f.levels.map(l => `${l.param} ${l.value}`).join(", ")
        : f.missing ? t("levels.fx.missing") : t("levels.fx.noOutput");
      const verdicts = f.levels.map(l => judgeOutput(l.device, l.param, l.value, f.profile?.params[profileKey("ifx", l.device, l.param)])).filter(Boolean);
      const open = el("button", { type: "button", className: "btn sm", textContent: t("levels.fx.open") });
      open.setAttribute("aria-label", t("levels.fx.openLabel", { slot: f.slot }));
      open.addEventListener("click", () => openPreset(f.slot));
      const item = el("li", { className: "ui-row" }, [
        el("span", { className: "ui-break", textContent: t("levels.fx.row", { parts: f.parts.join(", "), slot: f.slot, name: f.name, text }) }),
        verdicts.length ? pill("warn", verdicts.some(v => v.measured) ? t("levels.fx.heard") : verdicts.some(v => v.code === "output-too-loud") ? t("levels.fx.loud") : t("levels.fx.untested")) : null,
        open,
      ]);
      item.dataset.fxSlot = String(f.slot);
      list.append(item);
    }
    fxRows.append(list, el("p", { className: "muted cee-small", textContent: t("levels.fx.source", { source: found.source }) }));
  }

  /** The output levels of the insert presets the parts use, from the device's RAM where it can be read, else from the firmware file. */
  async function readFx(s) {
    const known = presets();
    if (!known) return null;
    const { units, profile } = known;
    const byPart = new Map();
    for (const part of readLevels(pattern()).parts) {
      if (part.ifx === null) continue;
      byPart.set(part.ifx, [...(byPart.get(part.ifx) ?? []), part.part + 1]);
    }
    const list = known.list("ifx");
    let fromRam = 0;
    const found = [];
    for (const [slot, parts] of [...byPart].sort((a, b) => a[0] - b[0])) {
      let record = list.find(x => x.slot === slot)?.record ?? null;
      const name = list.find(x => x.slot === slot)?.name ?? "";
      if (s && !s.busy && !s.reserved) {
        try {
          const entry = known.address("ifx", slot);
          record = new FxRecord(await s.readRamBlock(entry.ram, entry.size), "ifx");
          fromRam++;
        } catch { /* the firmware file's copy stands in */ }
      }
      found.push({ slot, parts, name: record?.name || name, levels: record ? outputLevels(record, units) : [], missing: !record, profile });
    }
    const source = fromRam === found.length && found.length ? t("levels.fx.ram")
      : fromRam ? t("levels.fx.partRam") : t("levels.fx.file");
    found.source = source;
    return found;
  }

  function resetControls() {
    state.mode = "factor";
    state.value = "1";
    state.master = false;
    modeInputs[0].checked = true;
    valueInput.value = "1";
    masterToggle.checked = false;
  }

  async function load() {
    const s = await attached();
    if (!s) return;
    fetchButton.disabled = true;
    try {
      await s.idle();
      const block = await s.fetchPattern();
      state.block = Uint8Array.from(block);
      state.sendable = true;
      const p = new Pattern(block);
      state.name = p.name || t("backup.noName");
      resetControls();
      body.hidden = false;
      say(t("levels.fetched", { name: state.name }), "ok");
      draw();
      drawFx(await readFx(s));
      undoButton.disabled = !s.history.some(h => h.pattern);
    } catch (e) {
      say(t("backup.fetchFailed", { error: e.message }), "error");
    } finally {
      fetchButton.disabled = false;
    }
  }

  async function send() {
    const s = await attached();
    if (!s || !state.block) return;
    const p = plan();
    if (p.error || !p.changed) return;
    const edited = pattern();
    applyScale(edited, p);
    const edit = { kind: "patternSend", block: Uint8Array.from(edited.bytes) };
    const buttons = [sendButton, undoButton, fetchButton];
    buttons.forEach(b => { b.disabled = true; });
    const release = s.reserve();
    try {
      await s.idle();
      let active;
      try { active = new Pattern(await s.fetchPattern()).name || t("backup.noName"); } catch (e) {
        say(t("backup.noBackup", { error: e.message }), "error");
        return;
      }
      const checked = await s.check(edit);
      if (checked.verdict === "blocked") { say(t("backup.blocked", { reasons: checked.reasons.map(r => r.message).join(" ") }), "error"); return; }
      const warnings = checked.reasons.map(r => t("backup.warning", { message: r.message })).join("\n");
      const changes = p.rows.filter(r => r.delta !== 0).map(r => t("levels.changeOf", { label: r.label, before: r.before, after: r.after })).join(", ");
      const yes = await window.ui.confirm({
        title: t("levels.send.title"),
        text: `${changes}.\n\n${t("backup.send.text", { name: active })}${warnings ? `\n\n${warnings}` : ""}`,
        confirmLabel: t("backup.send.confirm"),
      });
      if (!yes) return;
      say(t("backup.sending"), "info");
      const res = await s.apply(edit, { confirmed: checked.token });
      if (res.ok) {
        state.block = edit.block;
        resetControls();
        say(t("backup.sent", { name: active }), "ok");
        device.log?.(t("levels.sentLog"), "ok");
      } else if (res.needsConfirmation) say(t("backup.changed"), "error");
      else if (res.gate?.verdict === "blocked") say(t("backup.blocked", { reasons: res.gate.reasons.map(r => r.message).join(" ") }), "error");
      else say(`${res.error?.message ?? t("common.aborted")}${res.pending?.now ? ` ${res.pending.now.text}` : ""}${s.blocked ? ` ${t("backup.decide")}` : ""}`, s.blocked || !res.error?.message ? "error" : undefined);
      if (s.blocked) device.showDecision?.();
    } catch (e) {
      say(t("backup.aborted", { error: e.message }), "error");
    } finally {
      release();
      fetchButton.disabled = false;
      undoButton.disabled = !s.history.some(h => h.pattern);
      draw();
    }
  }

  async function undo() {
    const s = await attached();
    if (!s) return;
    const release = s.reserve();
    try {
      await s.idle();
      const res = await s.undo();
      say(res.ok ? t("levels.undone") : t("backup.undoFailed", { error: res.error.message }), res.ok ? "ok" : "error");
    } catch (e) {
      say(t("backup.undoFailed", { error: e.message }), "error");
    } finally {
      release();
      undoButton.disabled = !s.history.some(h => h.pattern);
    }
  }

  fetchButton.addEventListener("click", load);
  sendButton.addEventListener("click", send);
  undoButton.addEventListener("click", undo);
  root.replaceChildren(
    el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: t("levels.title") })]),
    el("p", { className: "muted", textContent: t("levels.lead") }),
    el("div", { className: "actions" }, [fetchButton]),
    body,
  );

  return { load, draw: () => { if (state.block) draw(); } };
}
