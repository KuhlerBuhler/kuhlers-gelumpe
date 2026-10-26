/**
 * The effects panel: load your firmware file, pick a preset, change its
 * parameters and control map, see what the gatekeeper says, send it live
 * into RAM and take it back.
 *
 * The file is never written; edits live on a copy of the preset. Writing a
 * firmware file comes in phase 4a.
 */
import { el, control } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { saveFile } from "./save-file.mjs";
import { field, fieldsOf, readRaw, writeRaw, typeOf, BLOCKS } from "../../src/map/index.mjs";
import { VsbImage } from "../../src/image.mjs";
import { FxRecord } from "../../src/record.mjs";
import { identify } from "../../src/firmware.mjs";
import { buildProfile, STOCK_SLOTS } from "../../src/profile.mjs";
import { lintCheck } from "../../src/gate.mjs";
import { parseUnits, setUnits, unitFor, hex } from "../../src/units.mjs";
import { tableEntry } from "../../src/map/address.mjs";
import { addPreset, locatePresets, pointersMatch, presetRoom, recordOf, RECORD } from "../../src/presets.mjs";
import { exportPresets } from "../../src/export.mjs";
import { presetFile, presetFileName, readPresetFile, PRESET_EXT } from "../../src/preset-file.mjs";
import { checkName, checkDetail } from "../../src/patcher.mjs";
import { GROUPS, labelFor } from "../../data/map/fx-labels.mjs";
import { suggestionsFor, applySuggestion } from "../../src/suggestions.mjs";
import { t } from "./i18n.mjs";

const SEVERITY = {
  fatal: ["error", "samples.severity.fatal"], silent: ["error", "levels.muted"], error: ["error", "common.error"],
  warn: ["warn", "device.log.warn"], note: ["neutral", "mod.hint"],
};
const META = BLOCKS.get("fxRecord").meta;
const STAGE_INDEX = { ifx1: 0, ifx2: 1, mfx: 2 };

const pill = (tone, word) => {
  const p = el("span", { className: "cee-status", textContent: word });
  p.dataset.tone = tone;
  return p;
};

/** Byte ranges of the record nobody understands, for the expert report. */
const UNKNOWN = fieldsOf("fxRecord").filter(f => f.source === "unknown");
function unknownChanges(before, after) {
  const out = [];
  for (const f of UNKNOWN) {
    for (const [a, b] of spans(f)) for (let i = a; i < b; i++) if (before[i] !== after[i]) out.push({ field: f.id, offset: i });
  }
  return out;
}
const spans = f => (f.repeat ? Array.from({ length: f.repeat[0].count }, (_, i) => {
  const at = f.where.offset + i * f.repeat[0].stride;
  return [at, at + typeOf(f).width];
}) : [[f.where.offset, f.where.offset + typeOf(f).width]]);

/**
 * @param {object} opts
 * @param {string} [opts.prefix] id prefix, so a second panel can sit on the same page
 * @param {boolean} [opts.embedded] no file picker; the firmware comes through loadBytes()
 * @param {(sent: {kind: string, slot: number}) => void} [opts.onSent] after a send that was read back intact
 * @param {() => object} [opts.onlyPort] the only port this panel may send to and hand its firmware to
 * @param {() => Promise<object | null>} [opts.live] the session to read presets from and send to when no device area session is attached: the running emulator's
 * @param {string} [opts.idle] what to say while no firmware is loaded in an embedded panel
 * @param {() => object | null} [opts.emulator] the emulator panel, whose `check` tests a firmware copy before it is offered
 * @param {Node} [opts.pickerExtra] shown after the preset choice, such as the switch that follows the device
 */
export function fxPanel(root, { device, prefix = "cee", embedded = false, onSent = null, onlyPort = null, live = null, idle = "", emulator = null, pickerExtra = null }) {
  const state = { units: null, image: null, bytes: null, identity: null, profile: null, kind: "ifx", slot: null, rec: null, original: null, expert: false, dirty: false, base: null, passed: null, stock: false, added: new Set(), fileDirty: false };

  const fileInput = el("input", { type: "file", className: "ui-dropzone-input", id: `${prefix}-vsb`, accept: ".VSB,.vsb" });
  const drop = el("label", { className: "ui-dropzone" }, [
    fileInput,
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: t("presets.drop") }), t("common.pick")]),
    el("span", { className: "ui-dropzone-hint", textContent: t("presets.drop.hint") }),
    el("span", { className: "ui-dropzone-files" }),
  ]);
  const identity = el("p", { className: "cee-identity", id: `${prefix}-vsb-identity` });
  const picker = el("div", { className: "cee-picker", hidden: true });
  const editor = el("div", { className: "cee-fx-editor", id: `${prefix}-fx-editor` });
  const verdict = el("div", { className: "cee-verdict", id: `${prefix}-verdict`, ariaLive: "polite" });
  const job = el("div", { className: "ui-job cee-job", hidden: true, role: "status" });
  const actions = el("div", { className: "actions", hidden: true });
  const sendButton = el("button", { type: "button", className: "btn cee-primary", id: `${prefix}-send`, textContent: t("samples.send") });
  const undoButton = el("button", { type: "button", className: "btn", id: `${prefix}-live-undo`, textContent: t("presets.liveUndo"), disabled: true });
  actions.append(sendButton, undoButton);
  const limits = el("p", { className: "muted", textContent: t("presets.limits") });

  // Into a copy of the firmware file: presets added as copies of existing ones, edits written in, the copy tested in the emulator.
  const room = el("p", { className: "muted cee-small", id: `${prefix}-fx-room` });
  const addButton = el("button", { type: "button", className: "btn", id: `${prefix}-add`, textContent: t("presets.add") });
  const exportButton = el("button", { type: "button", className: "btn cee-primary", id: `${prefix}-export`, textContent: t("presets.export") });
  const downloadButton = el("button", { type: "button", className: "btn", id: `${prefix}-download`, textContent: t("presets.download"), hidden: true });
  const saveButton = el("button", { type: "button", className: "btn", id: `${prefix}-preset-save`, textContent: t("presets.save") });
  const presetInput = el("input", { type: "file", className: "cee-visually-hidden", id: `${prefix}-preset-open`, accept: PRESET_EXT });
  const loadLabel = el("label", { className: "btn", htmlFor: `${prefix}-preset-open` }, [t("presets.load")]);
  const exportNote = el("p", { className: "cee-hint", id: `${prefix}-export-note`, hidden: true, role: "status" });
  const exportChecks = el("ul", { className: "ui-list", id: `${prefix}-export-checks`, hidden: true });
  const fileGroup = el("div", { className: "cee-group", id: `${prefix}-file-group`, hidden: true }, [
    el("h3", { textContent: t("presets.file") }),
    room,
    el("div", { className: "actions" }, [addButton, saveButton, loadLabel, presetInput, exportButton, downloadButton]),
    exportNote, exportChecks,
  ]);

  async function units() {
    if (state.units) return state.units;
    const res = await fetch(new URL("../../data/units.json", import.meta.url));
    state.units = setUnits(parseUnits(await res.json()));
    return state.units;
  }

  async function loadBytes(bytes) {
    await units();
    const id = await identify(bytes);
    state.identity = id;
    // Korg's own build is not "known" (its presets are not Hacktribe's), but its presets are read through the pointer arrays all the same
    const stock = id.build === "stock" && !!locatePresets(bytes);
    if (!id.known && !stock) {
      identity.replaceChildren(...(id.build === "stock" ? [] : [pill("error", t("presets.unknown")), ` ${id.reasons.join(" ")}`]));
      if (!embedded) window.ui?.rejectFile(fileInput, t("presets.notMeasured"));
      picker.hidden = true;
      return false;
    }
    state.bytes = bytes;
    state.base = Uint8Array.from(bytes);
    state.stock = stock;
    state.passed = null;
    state.added = new Set();
    state.fileDirty = false;
    state.kind = "ifx";
    state.slot = null;
    state.image = new VsbImage(bytes);
    state.profile = buildProfile(state.image, state.units, stock ? STOCK_SLOTS : undefined);
    identity.replaceChildren();
    hookSession();
    renderPicker();
    return true;
  }

  /** The session this panel works on: none when it is tied to a port and the device area is on another. */
  const target = () => {
    const s = device.session;
    return s && (!onlyPort || s.port === onlyPort()) ? s : null;
  };

  function hookSession() {
    const s = target();
    if (s && state.bytes) s.useFirmware(state.bytes, state.identity, { units: state.units, profile: state.profile });
  }

  function renderPicker() {
    const kinds = el("div", { className: "ui-segmented" });
    kinds.setAttribute("role", "radiogroup");
    kinds.setAttribute("aria-label", t("levels.kind"));
    for (const [kind, label] of [["ifx", t("presets.kind.ifx")], ["mfx", t("presets.kind.mfx")]]) {
      const input = el("input", { type: "radio", name: `${prefix}-fx-kind`, value: kind, checked: state.kind === kind });
      input.addEventListener("change", () => { state.kind = kind; state.slot = null; renderPicker(); });
      kinds.append(el("label", { className: "ui-segmented-option" }, [input, el("span", { textContent: label })]));
    }
    const select = el("select", { className: "select", id: `${prefix}-fx-slot` });
    const list = state.image.list(state.kind);
    for (const { slot, name } of list) select.append(el("option", { value: String(slot), textContent: `${slot} ${name}` }));
    select.addEventListener("change", () => openSlot(Number(select.value)));
    picker.replaceChildren(kinds, el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: `${prefix}-fx-slot`, textContent: t("presets.preset") }), select]), ...(pickerExtra ? [pickerExtra] : []));
    picker.hidden = false;
    if (list.length) openSlot(state.slot ?? list[0].slot);
    if (state.slot) select.value = String(state.slot);
    renderRoom();
  }

  /** The session the presets are read from: the attached device, else the running emulator; null when neither. */
  const pick = async () => {
    const s = target() ?? (live ? await live().catch(() => null) : null);
    state.why = null;
    if (s && state.stock && !(await stockReady(s))) return null;
    if (s && state.bytes) s.useFirmware(state.bytes, state.identity, { units: state.units, profile: state.profile });
    return s;
  };

  /** Korg's records are found through the pointer arrays, so live access needs BLECH on Korg's build, running the file's arrays. */
  async function stockReady(s) {
    if (s.device?.build !== "stock" || s.device.ram !== "blech") {
      state.why = t("presets.why.stock");
      return false;
    }
    if (state.matched?.session !== s || state.matched.bytes !== state.base) {
      state.matched = null;
      await s.idle();
      const ok = await pointersMatch(state.base, (addr, length) => s.readRamBlock(addr, length)).catch(e => (e.kind === "busy" ? null : false));
      if (ok === null) return false;
      state.matched = { session: s, bytes: state.base, ok };
    }
    if (!state.matched.ok) state.why = t("presets.why.pointers");
    return state.matched.ok;
  }

  /** A background read (the screen poll of the sidebar) may hold the session just then; a person's action waits for it and tries again, nothing has gone out yet. */
  async function whenIdle(session, run) {
    for (let attempt = 0; ; attempt++) {
      if (session.busy) await session.idle();
      try { return await run(); } catch (e) { if (e.kind !== "busy" || attempt >= 8) throw e; }
    }
  }

  let opening = 0;
  async function openSlot(slot, { refresh = false } = {}) {
    // A refresh gives way to an open that is under way; counting it would drop that open while the refresh itself gives up on the busy session.
    const mine = refresh ? opening : ++opening;
    state.slot = slot;
    let from = t("presets.from.file");
    const session = await pick();
    if (!session && state.why) from = t("presets.from.fileWhy", { why: state.why });
    if (refresh && (state.dirty || session?.busy || session?.reserved)) return;
    if (session && !session.reserved && !state.added.has(`${state.kind}:${slot}`)) {
      try {
        const entry = state.stock ? { ram: recordOf(state.base, state.kind, slot).ram, size: RECORD } : tableEntry(`table.${state.kind}`, slot - 1);
        state.image.bytes.set(await whenIdle(session, () => session.readRamBlock(entry.ram, entry.size)), state.image.slotOffset(state.kind, slot));
        from = session.port.emulator ? t("presets.from.emu") : t("presets.from.device");
      } catch (e) {
        from = t("presets.from.failed", { error: e.message });
      }
    }
    if (mine !== opening || (refresh && (state.dirty || session?.reserved))) return;
    state.original = state.image.read(state.kind, slot);
    state.rec = state.original.clone();
    state.dirty = false;
    state.from = from;
    renderEditor();
  }

  const edited = () => { state.dirty = true; refreshVerdict(); renderRoom(); };

  /** A parameter whose values Korg names but we do not know: a plain number, not a slider over 128 steps. */
  function choiceField(f, read, write) {
    const id = `${prefix}-ch-${f.id.replace(/\W/g, "-")}`;
    const top = f.range?.[1] ?? 127;
    const input = el("input", { type: "number", className: "input", id, min: 0, max: top, step: 1, value: String(read()) });
    input.addEventListener("change", () => {
      const v = Math.max(0, Math.min(top, Math.round(Number(input.value) || 0)));
      input.value = String(v);
      write(v);
    });
    return el("div", { className: "ui-field cee-compact" }, [el("label", { className: "ui-field-label", htmlFor: id, textContent: f.label.de }), input]);
  }

  /** The parameters of one stage, in sections; fields nobody understands wait behind the expert toggle. */
  function paramSections(stage) {
    const device = state.rec.device(stage);
    const kind = stage === "mfx" ? "mfx" : "ifx";
    const unit = unitFor(state.units, kind, device);
    if (!unit) return [el("p", { className: "muted", textContent: t("presets.unknownUnit", { unit: hex(device) }) })];
    const ix = stage === "mfx" ? [] : [STAGE_INDEX[stage]];
    const byGroup = new Map(GROUPS.map(g => [g.id, []]));
    for (const p of unit.params) {
      const f = field(`fx.${kind}.${hex(device)}.${p.name}`);
      if (f.edit === "expert" && !state.expert) continue;
      const read = () => readRaw(state.rec.bytes, f, ix);
      const write = raw => { writeRaw(state.rec.bytes, f, ix, raw); edited(); };
      byGroup.get(f.group ?? "other").push(f.fxChoice ? choiceField(f, read, write) : control(f, read, write, { compact: true }).node);
    }
    return GROUPS.filter(g => byGroup.get(g.id).length).map(g =>
      el("section", { className: "cee-fxsec" }, [el("h4", { textContent: g.label }), el("div", { className: "cee-grid" }, byGroup.get(g.id))]));
  }

  function mapRows() {
    const rows = el("div", { className: "cee-fxmap" });
    const sources = META.sources.filter(s => state.kind === "mfx" || s.ifx);
    const who = s => s.who?.[state.kind === "mfx" ? "mfx" : "ifx"] ?? s.label;
    const chains = META.chains.filter(c => !c.stage || (state.kind === "mfx" ? c.stage === "mfx" : c.stage !== "mfx"));
    const draw = () => {
      rows.replaceChildren();
      for (const row of state.rec.map) {
        const ix = [row.index];
        const set = (id, v) => { writeRaw(state.rec.bytes, field(id), ix, v); edited(); };
        const select = (id, options, current, label) => {
          const s = el("select", { className: "select" });
          s.setAttribute("aria-label", t("presets.map.row", { label, row: row.index + 1 }));
          for (const o of options) s.append(el("option", { value: String(o.raw), textContent: o.label }));
          if (!options.some(o => o.raw === current)) s.append(el("option", { value: String(current), textContent: t("presets.map.unknownValue", { value: current }) }));
          s.value = String(current);
          s.addEventListener("change", () => { set(id, Number(s.value)); if (id !== "fx.map.param") draw(); });
          return s;
        };
        const chain = META.chains.find(c => c.raw === row.chain);
        const unit = chain?.stage ? unitFor(state.units, chain.stage === "mfx" ? "mfx" : "ifx", state.rec.device(chain.stage)) : null;
        const params = unit ? unit.params.map(p => ({ raw: p.index, label: labelFor(p.name).de })) : [{ raw: row.param, label: t("presets.map.param", { n: row.param }) }];
        const number = (id, word) => {
          const input = el("input", { type: "number", className: "input cee-num", min: 0, max: 127, step: 1, value: String(row[id === "fx.map.low" ? "low" : "high"]) });
          input.setAttribute("aria-label", t("presets.map.row", { label: word, row: row.index + 1 }));
          input.addEventListener("change", () => {
            const v = Math.max(0, Math.min(127, Math.round(Number(input.value) || 0)));
            input.value = String(v);
            set(id, v);
            span();
          });
          return input;
        };
        const bar = el("span", { className: "cee-range", ariaHidden: "true" }, [el("span", { className: "cee-range-fill" })]);
        const span = () => {
          const lo = readRaw(state.rec.bytes, field("fx.map.low"), ix);
          const hi = readRaw(state.rec.bytes, field("fx.map.high"), ix);
          bar.firstChild.style.left = `${(Math.min(lo, hi) / 127) * 100}%`;
          bar.firstChild.style.width = `${(Math.abs(hi - lo) / 127) * 100}%`;
        };
        span();
        const remove = el("button", { type: "button", className: "btn sm", textContent: t("common.remove") });
        remove.setAttribute("aria-label", t("presets.map.remove", { row: row.index + 1 }));
        remove.addEventListener("click", () => { writeRaw(state.rec.bytes, field("fx.map.source"), ix, 0); edited(); draw(); });
        rows.append(el("div", { className: "cee-fxmap-row" }, [
          el("div", { className: "cee-sentence" }, [
            select("fx.map.source", sources.map(s => ({ raw: s.raw, label: who(s) })), row.source, t("mod.slot.source")),
            el("span", { textContent: t("presets.map.steers") }),
            select("fx.map.chain", chains.map(c => ({ raw: c.raw, label: c.label })), row.chain, t("mod.slot.target")),
            ...(chain?.stage ? [el("span", { textContent: ">" }), select("fx.map.param", params, row.param, t("presets.map.parameter"))] : []),
            el("span", { textContent: t("presets.map.from") }),
            number("fx.map.low", t("presets.map.low")),
            el("span", { textContent: t("presets.map.to") }),
            number("fx.map.high", t("presets.map.high")),
            remove,
          ]),
          bar,
        ]));
      }
      const add = el("button", { type: "button", className: "btn sm", textContent: t("presets.map.add") });
      add.addEventListener("click", addRow);
      rows.append(el("div", { className: "actions" }, [add]));
    };
    function addRow() {
      const b = state.rec.bytes;
      const size = field("fx.map.source").repeat[0].stride;
      const base = field("fx.map.source").where.offset;
      const used = state.rec.map;
      const free = Array.from({ length: field("fx.map.source").repeat[0].count }, (_, i) => i).find(i => b[base + i * size] === 0);
      if (free === undefined || !used.length) {
        toast(t("presets.map.full"), "error");
        return;
      }
      const donor = used[used.length - 1].index;
      b.copyWithin(base + free * size, base + donor * size, base + (donor + 1) * size);
      edited();
      draw();
    }
    draw();
    return rows;
  }

  function expertSection() {
    const details = el("details", { className: "ui-details", id: `${prefix}-expert` });
    details.append(el("summary", { textContent: t("presets.expert") }));
    const body = el("div", { className: "ui-details-body" });
    body.append(el("p", { className: "cee-hint", textContent: t("presets.expert.hint") }));
    for (const f of UNKNOWN) {
      const levels = f.repeat ? f.repeat[0].count : 1;
      for (let i = 0; i < levels; i++) {
        const [a, bEnd] = spans(f)[i];
        if (f.id.startsWith("fx.map") && state.rec.bytes[field("fx.map.source").where.offset + i * 28] === 0) continue;
        if (f.id === "fx.stage.unknown" && !state.rec.bytes[field("fx.stage.device").where.offset + i * 0x4a]) continue;
        const inputs = [];
        for (let k = a; k < bEnd; k++) {
          const input = el("input", { type: "number", className: "input cee-byte", min: 0, max: 255, value: String(state.rec.bytes[k]) });
          input.setAttribute("aria-label", t("presets.expert.byte", { label: f.label.de, n: i + 1, byte: k - a + 1 }));
          input.addEventListener("change", () => {
            const v = Math.max(0, Math.min(255, Math.round(Number(input.value) || 0)));
            state.rec.bytes[k] = v;
            input.value = String(v);
            edited();
          });
          inputs.push(input);
        }
        body.append(el("div", { className: "ui-field" }, [el("span", { className: "ui-field-label", textContent: `${f.label.de} ${levels > 1 ? i + 1 : ""}` }), el("div", { className: "cee-bytes" }, inputs)]));
      }
    }
    details.append(body);
    return details;
  }

  /** Suggestions for the open preset, shown only where its unit is the one they were made for. */
  function suggestionBlocks() {
    if (state.kind !== "ifx") return [];
    return suggestionsFor(state.rec)
      .filter(({ suggestion: s }) => state.rec.device("ifx1") === s.unit || state.rec.device("ifx2") === s.unit)
      .map(({ suggestion: s, refusal }) => {
        const id = `${prefix}-suggest-${s.id}`;
        const apply = el("button", { type: "button", className: "btn", id: `${id}-apply`, textContent: t("presets.suggest.apply") });
        apply.addEventListener("click", () => { applySuggestion(state.rec, s, state.units); edited(); renderEditor(); });
        const values = Object.entries(s.params).map(([name, v]) => `${labelFor(name).de} ${v}`).join(", ");
        return el("div", { className: "cee-group", id }, [
          el("h3", { textContent: t("presets.suggest.title", { label: s.label.de }) }),
          el("p", {}, [pill("warn", t("presets.suggest.untested")), ` ${s.hint}`]),
          el("p", { className: "muted cee-small", textContent: t("presets.suggest.sets", { values }) }),
          refusal ? el("p", { className: "cee-hint", id: `${id}-refusal`, textContent: refusal }) : apply,
        ]);
      });
  }

  function renderEditor() {
    const name = control(field("fx.name"), () => state.rec.name, v => { writeRaw(state.rec.bytes, field("fx.name"), [], v); edited(); });
    const stages = state.rec.stageNames.filter(s => state.rec.device(s));
    const stageBlocks = stages.map(stage => {
      const unit = unitFor(state.units, stage === "mfx" ? "mfx" : "ifx", state.rec.device(stage));
      return el("div", { className: "cee-group" }, [
        el("h3", { textContent: t(stage === "mfx" ? "presets.stage.master" : "presets.stage", { n: STAGE_INDEX[stage] + 1, unit: unit ? unit.unit : hex(state.rec.device(stage)) }) }),
        ...paramSections(stage),
      ]);
    });
    const toggle = el("input", { type: "checkbox", id: `${prefix}-expert-toggle`, checked: state.expert });
    toggle.setAttribute("role", "switch");
    toggle.addEventListener("change", () => { state.expert = toggle.checked; renderEditor(); });
    editor.replaceChildren(
      el("p", { className: "muted cee-small", id: `${prefix}-fx-source`, textContent: state.from ?? "" }),
      el("div", { className: "cee-group cee-fxhead" }, [name.node, el("label", { className: "ui-switch" }, [toggle, el("span", { className: "ui-switch-track", ariaHidden: "true" }), t("presets.expertToggle")])]),
      ...stageBlocks,
      ...suggestionBlocks(),
      el("div", { className: "cee-group" }, [el("h3", { textContent: t("presets.map") }), mapRows()]),
      ...(state.expert ? [expertSection()] : []),
    );
    actions.hidden = false;
    refreshVerdict();
    renderRoom();
  }

  async function refreshVerdict() {
    const findings = await lintCheck({ kind: "fxRecord", table: state.kind, slot: state.slot, bytes: state.rec.bytes, before: state.original.bytes }, { units: state.units, profile: state.profile });
    const list = el("ul", { className: "ui-list" });
    for (const f of findings) {
      const [tone, word] = SEVERITY[f.severity];
      list.append(el("li", { className: "ui-row" }, [pill(tone, t(word)), el("span", { className: "ui-break", textContent: ` ${f.message}` })]));
    }
    const unknown = unknownChanges(state.original.bytes, state.rec.bytes).length;
    verdict.replaceChildren(
      el("h3", { textContent: t("samples.gate") }),
      findings.length ? list : el("p", {}, [pill("ok", t("samples.clean")), ` ${t("samples.noFindings")}`]),
      unknown ? el("p", { className: "cee-hint", textContent: t("presets.unknownBytes", { count: unknown }) }) : "",
    );
  }

  function progress(name) {
    job.hidden = false;
    const bar = el("div", { className: "ui-progress", role: "progressbar" }, [el("span", { className: "ui-progress-bar" })]);
    bar.setAttribute("aria-valuemin", "0");
    bar.setAttribute("aria-valuemax", "100");
    const state = el("span", { className: "cee-status", textContent: t("samples.job.running") });
    state.dataset.tone = "running";
    const meta = el("span", { className: "ui-job-meta" });
    job.replaceChildren(el("div", { className: "ui-job-head" }, [el("span", { className: "ui-job-name", textContent: name }), state]), bar, meta);
    return {
      step(n, total) { window.ui?.setProgress(bar, Math.round((n / total) * 100), name); meta.textContent = t("samples.job.step", { n, total }); },
      done(ok, text) {
        state.textContent = ok ? t("samples.job.done") : t("samples.job.failed");
        state.dataset.tone = ok ? "ok" : "error";
        bar.dataset.tone = ok ? "ok" : "error";
        window.ui?.setProgress(bar, 100, name, ok ? undefined : { valueText: t("samples.job.failed") });
        meta.textContent = text;
      },
    };
  }

  async function send() {
    const session = await pick();
    if (!session) { verdict.prepend(el("p", { className: "cee-error", textContent: state.why ?? t("presets.noSession") })); return; }
    const edit = { kind: "fxRecord", table: state.kind, slot: state.slot, bytes: Uint8Array.from(state.rec.bytes), before: state.original.bytes, unknownChanges: unknownChanges(state.original.bytes, state.rec.bytes) };
    if (state.stock) edit.ram = recordOf(state.base, state.kind, state.slot)?.ram;
    sendButton.disabled = undoButton.disabled = true;
    const release = session.reserve();
    let p = null;
    try {
      await session.idle();
      const checked = await session.check(edit);
      if (checked.verdict === "blocked") { showBlocked(checked.reasons); return; }
      if (checked.verdict === "confirm") {
        const text = checked.reasons.map(r => `${SEVERITY[r.severity] ? t(SEVERITY[r.severity][1]) : r.severity}: ${r.message}`).join("\n");
        const yes = await window.ui.confirm({ title: t("samples.confirm.title"), text, confirmLabel: t("backup.send.confirm"), danger: false });
        if (!yes) return;
      }
      p = progress(t("presets.job", { target: `${state.kind === "ifx" ? "IFX" : "MFX"} ${state.slot}` }));
      // The yes covers exactly what was shown; a different verdict asks again.
      const result = await whenIdle(session, () => session.apply(edit, { confirmed: checked.token, onStep: p.step }));
      if (result.needsConfirmation) { p.done(false, t("backup.changed")); return; }
      if (result.gate?.verdict === "blocked") { p.done(false, t("samples.blockedByGate")); showBlocked(result.gate.reasons); return; }
      finish(result, p);
    } catch (e) {
      if (p) p.done(false, e.message);
      else verdict.prepend(el("p", { className: "cee-error", textContent: e.message }));
    } finally {
      release();
      sendButton.disabled = false;
      undoButton.disabled = !session.history.length;
    }
  }

  function showBlocked(reasons) {
    const list = el("ul", { className: "ui-list", id: `${prefix}-blocked` });
    for (const r of reasons) {
      const [tone, word] = SEVERITY[r.severity] ?? ["error", "backup.locked"];
      list.append(el("li", { className: "ui-row" }, [pill(tone, t(word)), el("span", { className: "ui-break", textContent: ` ${r.message}` })]));
    }
    verdict.replaceChildren(el("h3", { textContent: t("samples.blocked") }), list);
    device.log?.(t("backup.blocked", { reasons: reasons[0]?.message ?? "" }), "error");
  }

  function finish(result, p) {
    const target = `${state.kind === "ifx" ? "IFX" : "MFX"} ${state.slot}`;
    if (result.ok) {
      p?.done(true, t("presets.sent"));
      device.log?.(t("presets.sentLog", { target }), "ok");
      undoButton.disabled = false;
      onSent?.({ kind: state.kind, slot: state.slot });
      return;
    }
    const text = result.error ? `${result.error.message}${result.pending?.now ? ` ${result.pending.now.text}` : ""}` : t("samples.aborted");
    p?.done(false, text);
    device.log?.(t("presets.failedLog", { target, error: text }), "error");
    if (device.session?.blocked) {
      showBlocked([{ severity: "error", code: "target-blocked", message: t("samples.decide", { reason: device.session.blocked }) }]);
      device.showDecision?.();
    }
  }

  async function undoLive() {
    const session = await pick();
    if (!session) return;
    const release = session.reserve();
    undoButton.disabled = true;
    const p = progress(t("samples.undo"));
    let res;
    try {
      res = await whenIdle(session, () => session.undo({ onStep: p.step }));
    } catch (e) {
      res = { ok: false, error: e };
    } finally {
      release();
    }
    p.done(res.ok, res.ok ? t("samples.undone") : res.error.message);
    device.log?.(res.ok ? t("samples.undoneLog") : t("backup.undoFailed", { error: res.error.message }), res.ok ? "ok" : "error");
    undoButton.disabled = !session.history.length;
  }

  const kindWord = kind => t(kind === "ifx" ? "presets.kind.ifx" : "presets.kind.mfx");

  function renderRoom() {
    const info = state.image ? presetRoom(state.image.bytes, state.kind) : null;
    fileGroup.hidden = !info;
    if (!info) return;
    const more = info.patched ? "" : ` ${t("presets.room.more", { capacity: info.capacity })}`;
    room.textContent = t("presets.room", { kind: kindWord(state.kind), count: info.count, capacity: info.capacity, more });
    addButton.disabled = info.count >= info.capacity || !state.rec;
    saveButton.disabled = !state.rec;
    exportButton.disabled = !state.fileDirty && !state.dirty;
  }

  /** What is open in the form goes into the image first, so a copy is a copy of what is shown. */
  function commit() {
    if (!state.rec || !state.dirty) return;
    state.image.write(state.kind, state.slot, state.rec);
    state.fileDirty = true;
    state.passed = null;
    downloadButton.hidden = true;
  }

  /** A message of the file group goes to the toast; only the running check stands in the note. */
  function note(text, kind = "info") {
    exportNote.hidden = true;
    toast(text, kind);
  }

  function addCopy() {
    commit();
    const added = addPreset(state.image.bytes, state.kind, state.slot);
    if (!added.ok) {
      note(added.reasons.join(" "), "error");
      return;
    }
    state.image.bytes.set(added.bytes);
    state.added.add(`${state.kind}:${added.slot}`);
    state.fileDirty = true;
    state.passed = null;
    downloadButton.hidden = true;
    note(t("presets.copied", { kind: kindWord(state.kind), slot: added.slot, from: state.slot }), "ok");
    state.dirty = false;
    state.slot = added.slot;
    renderPicker();
  }

  /** The preset in the form as a .e2fx file, to pass it on. */
  function savePreset() {
    if (!state.rec) return;
    commit();
    const rec = state.image.read(state.kind, state.slot);
    saveFile(presetFile(state.kind, rec.bytes), presetFileName(state.kind, rec.name), { type: "application/json" });
  }

  /** A .e2fx file as a new slot of its kind: a copy of slot 1 is made, then the file's record goes in, name and all. */
  async function loadPreset(file) {
    const got = readPresetFile(await file.text());
    if (!got.ok) { note(got.reason, "error"); return; }
    if (!state.image) { note(t("presets.loadFirst"), "error"); return; }
    commit();
    const added = addPreset(state.image.bytes, got.kind, 1);
    if (!added.ok) { note(added.reasons.join(" "), "error"); return; }
    state.image.bytes.set(added.bytes);
    state.image.write(got.kind, added.slot, new FxRecord(got.record, got.kind));
    state.added.add(`${got.kind}:${added.slot}`);
    state.fileDirty = true;
    state.passed = null;
    downloadButton.hidden = true;
    state.kind = got.kind;
    state.slot = added.slot;
    state.dirty = false;
    note(t("presets.loaded", { kind: kindWord(got.kind), slot: added.slot, name: got.name }), "ok");
    renderPicker();
  }

  async function runExport() {
    commit();
    exportButton.disabled = addButton.disabled = true;
    downloadButton.hidden = true;
    exportChecks.hidden = true;
    state.passed = null;
    exportNote.hidden = false;
    try {
      const res = await exportPresets(state.base, state.image.bytes);
      if (!res.ok) throw new Error(res.reasons.join(" "));
      const emu = emulator?.();
      if (!emu) throw new Error(t("presets.noEmu"));
      exportNote.textContent = t("presets.checking");
      const report = await emu.check(state.base, res.bytes, res.allow, res.allowCode);
      exportChecks.replaceChildren(...report.checks.map(c => el("li", { className: "ui-row" }, [
        pill(c.ok ? "ok" : "error", c.ok ? t("check.passed") : t("check.failed")), el("strong", { textContent: ` ${checkName(c.id)}` }), el("span", { className: "ui-break muted", textContent: ` ${checkDetail(c.detail)}` }),
      ])));
      exportChecks.hidden = false;
      const good = report.checks.filter(c => c.ok).length;
      if (report.ok) note(t("mod.checked.ok"), "ok");
      else note(t("mod.checked.failed", { count: report.checks.length - good }), "error");
      if (report.ok) { state.passed = res.bytes; downloadButton.hidden = false; }
    } catch (e) {
      note(e.message, "error");
    } finally {
      renderRoom();
    }
  }

  function downloadCopy() {
    if (!state.passed) return;
    saveFile(state.passed, "SYSTEM.VSB");
    note(t("presets.copyNote"), "ok");
  }

  addButton.addEventListener("click", addCopy);
  saveButton.addEventListener("click", savePreset);
  presetInput.addEventListener("change", () => { const f = presetInput.files?.[0]; presetInput.value = ""; if (f) loadPreset(f); });
  exportButton.addEventListener("click", runExport);
  downloadButton.addEventListener("click", downloadCopy);
  fileInput.addEventListener("change", async () => { const f = fileInput.files?.[0]; if (f) loadBytes(new Uint8Array(await f.arrayBuffer())); });
  sendButton.addEventListener("click", send);
  undoButton.addEventListener("click", undoLive);
  if (embedded && idle) identity.textContent = idle;
  root.replaceChildren(...(embedded ? [] : [drop]), identity, picker, editor, verdict, actions, job, fileGroup, ...(embedded ? [] : [limits]));

  return {
    sessionChanged: hookSession,
    loadBytes,
    /** Refresh an untouched preset from the running session. */
    refresh() { if (state.image && state.slot && !state.dirty) return openSlot(state.slot, { refresh: true }); },
    get loaded() { return !!state.image; },
    /** An edit of the open preset that was not sent or written yet. */
    get dirty() { return state.dirty; },
    /** The presets of the loaded firmware and what their parameters are called, for the level overview; null before a firmware is loaded. */
    presets() {
      return state.image ? {
        list: kind => state.image.list(kind), units: state.units, profile: state.profile,
        /** Where a record is in the RAM of a running device: Hacktribe's table, or Korg's record found through the pointer arrays. */
        address: (kind, slot) => (state.stock ? { ram: recordOf(state.base, kind, slot).ram, size: RECORD } : tableEntry(`table.${kind}`, slot - 1)),
      } : null;
    },
    /** Open a preset by the number the device shows; false when the loaded file has no such slot. */
    open(kind, slot) {
      if (!state.image || !state.image.list(kind).some(x => x.slot === slot)) return false;
      state.kind = kind;
      state.slot = slot;
      renderPicker();
      return true;
    },
    /**
     * Writes a record built elsewhere (the Baukasten) live into `slot`, through the same gate as Live ins RAM.
     * `make(before, records)` builds it from what the slot holds now and the other records of its kind.
     * @returns {Promise<{ok: true} | {ok: false, reason: string}>}
     */
    async writeRecord(kind, slot, make) {
      if (!state.image) return { ok: false, reason: t("presets.needsFirmware") };
      const session = await pick();
      if (!session) {
        const off = emulator?.()?.firmware && !emulator().port?.running;
        return { ok: false, reason: state.why ?? (off ? t("presets.emuOff") : t("presets.noSessionDevice")) };
      }
      const before = Uint8Array.from(state.image.read(kind, slot).bytes);
      const made = make(before, state.image.list(kind).map(x => Uint8Array.from(x.record.bytes)));
      if (!made.ok) return made;
      const edit = { kind: "fxRecord", table: kind, slot, bytes: made.record, before, unknownChanges: unknownChanges(before, made.record) };
      if (state.stock) edit.ram = recordOf(state.base, kind, slot)?.ram;
      const release = session.reserve();
      try {
        await session.idle();
        const checked = await session.check(edit);
        if (checked.verdict === "blocked") return { ok: false, reason: t("backup.blocked", { reasons: checked.reasons[0]?.message ?? "" }) };
        if (checked.verdict === "confirm") {
          const text = checked.reasons.map(r => `${SEVERITY[r.severity] ? t(SEVERITY[r.severity][1]) : r.severity}: ${r.message}`).join("\n");
          if (!(await window.ui.confirm({ title: t("samples.confirm.title"), text, confirmLabel: t("backup.send.confirm"), danger: false }))) return { ok: false, reason: "" };
        }
        const result = await whenIdle(session, () => session.apply(edit, { confirmed: checked.token }));
        if (result.needsConfirmation) return { ok: false, reason: t("backup.changed") };
        if (result.gate?.verdict === "blocked") return { ok: false, reason: t("backup.blocked", { reasons: result.gate.reasons[0]?.message ?? "" }) };
        if (!result.ok) return { ok: false, reason: result.error?.message ?? t("samples.aborted") };
        state.image.write(kind, slot, new FxRecord(made.record, kind));
        device.log?.(t("presets.sentLogBaukasten", { target: `${kind === "ifx" ? "IFX" : "MFX"} ${slot}` }), "ok");
        onSent?.({ kind, slot });
        renderPicker();
        if (state.kind === kind && state.slot === slot && !state.dirty) openSlot(slot, { refresh: true });
        return { ok: true };
      } catch (e) {
        return { ok: false, reason: e.message };
      } finally {
        release();
      }
    },
    /** Show inserts or masters; before a file is loaded, the dropzone is where to go. */
    selectKind(kind) {
      if (!state.image) return drop;
      if (state.kind !== kind) { state.kind = kind; state.slot = null; renderPicker(); }
      return picker;
    },
  };
}
