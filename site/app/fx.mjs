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

const SEVERITY = {
  fatal: ["error", "tödlich"], silent: ["error", "stumm"], error: ["error", "Fehler"],
  warn: ["warn", "Warnung"], note: ["neutral", "Hinweis"],
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
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: "SYSTEM.VSB hierher ziehen oder " }), "auswählen"]),
    el("span", { className: "ui-dropzone-hint", textContent: "Deine eigene Firmware-Datei. Sie bleibt auf deinem Rechner, der Editor schreibt nicht hinein." }),
    el("span", { className: "ui-dropzone-files" }),
  ]);
  const identity = el("p", { className: "cee-identity", id: `${prefix}-vsb-identity` });
  const picker = el("div", { className: "cee-picker", hidden: true });
  const editor = el("div", { className: "cee-fx-editor", id: `${prefix}-fx-editor` });
  const verdict = el("div", { className: "cee-verdict", id: `${prefix}-verdict`, ariaLive: "polite" });
  const job = el("div", { className: "ui-job cee-job", hidden: true, role: "status" });
  const actions = el("div", { className: "actions", hidden: true });
  const sendButton = el("button", { type: "button", className: "btn cee-primary", id: `${prefix}-send`, textContent: "Live ins RAM" });
  const undoButton = el("button", { type: "button", className: "btn", id: `${prefix}-live-undo`, textContent: "Live zurücknehmen", disabled: true });
  actions.append(sendButton, undoButton);
  const limits = el("p", { className: "muted", textContent: "Der Türsteher prüft Form, nicht Klang. Ob ein Preset gut klingt, oder auf echter Hardware überhaupt, sagt nur das Ohr." });

  // Into a copy of the firmware file: presets added as copies of existing ones, edits written in, the copy tested in the emulator.
  const room = el("p", { className: "muted cee-small", id: `${prefix}-fx-room` });
  const addButton = el("button", { type: "button", className: "btn", id: `${prefix}-add`, textContent: "Preset hinzufügen (Kopie des gewählten)" });
  const exportButton = el("button", { type: "button", className: "btn cee-primary", id: `${prefix}-export`, textContent: "Firmware-Kopie prüfen" });
  const downloadButton = el("button", { type: "button", className: "btn", id: `${prefix}-download`, textContent: "Firmware-Kopie laden", hidden: true });
  const saveButton = el("button", { type: "button", className: "btn", id: `${prefix}-preset-save`, textContent: "Preset als Datei speichern" });
  const presetInput = el("input", { type: "file", className: "cee-visually-hidden", id: `${prefix}-preset-open`, accept: PRESET_EXT });
  const loadLabel = el("label", { className: "btn", htmlFor: `${prefix}-preset-open` }, ["Preset-Datei laden"]);
  const exportNote = el("p", { className: "cee-hint", id: `${prefix}-export-note`, hidden: true, role: "status" });
  const exportChecks = el("ul", { className: "ui-list", id: `${prefix}-export-checks`, hidden: true });
  const fileGroup = el("div", { className: "cee-group", id: `${prefix}-file-group`, hidden: true }, [
    el("h3", { textContent: "In die Firmware-Datei" }),
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
      identity.replaceChildren(...(id.build === "stock" ? [] : [pill("error", "unbekannt"), ` ${id.reasons.join(" ")}`]));
      if (!embedded) window.ui?.rejectFile(fileInput, "Nicht die vermessene Firmware.");
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
    kinds.setAttribute("aria-label", "Art");
    for (const [kind, label] of [["ifx", "Insert"], ["mfx", "Master"]]) {
      const input = el("input", { type: "radio", name: `${prefix}-fx-kind`, value: kind, checked: state.kind === kind });
      input.addEventListener("change", () => { state.kind = kind; state.slot = null; renderPicker(); });
      kinds.append(el("label", { className: "ui-segmented-option" }, [input, el("span", { textContent: label })]));
    }
    const select = el("select", { className: "select", id: `${prefix}-fx-slot` });
    const list = state.image.list(state.kind);
    for (const { slot, name } of list) select.append(el("option", { value: String(slot), textContent: `${slot} ${name}` }));
    select.addEventListener("change", () => openSlot(Number(select.value)));
    picker.replaceChildren(kinds, el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: `${prefix}-fx-slot`, textContent: "Preset" }), select]), ...(pickerExtra ? [pickerExtra] : []));
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
      state.why = "Das verbundene Gerät läuft nicht auf Korgs Original mit BLECHTRIBE; Korgs Records lassen sich nur mit BLECHTRIBEs Befehlen lesen und schreiben.";
      return false;
    }
    if (state.matched?.session !== s || state.matched.bytes !== state.base) {
      state.matched = null;
      await s.idle();
      const ok = await pointersMatch(state.base, (addr, length) => s.readRamBlock(addr, length)).catch(e => (e.kind === "busy" ? null : false));
      if (ok === null) return false;
      state.matched = { session: s, bytes: state.base, ok };
    }
    if (!state.matched.ok) state.why = "Die Zeigerfelder im Gerät sind nicht die der geladenen Firmware-Datei; geschrieben wird nur, wo die Datei die Records weiß.";
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
    const mine = ++opening;
    state.slot = slot;
    let from = "Stand aus der Firmware-Datei.";
    const session = await pick();
    if (!session && state.why) from = `${state.why} Stand aus der Firmware-Datei.`;
    if (refresh && (state.dirty || session?.busy || session?.reserved)) return;
    if (session && !session.reserved && !state.added.has(`${state.kind}:${slot}`)) {
      try {
        const entry = state.stock ? { ram: recordOf(state.base, state.kind, slot).ram, size: RECORD } : tableEntry(`table.${state.kind}`, slot - 1);
        state.image.bytes.set(await whenIdle(session, () => session.readRamBlock(entry.ram, entry.size)), state.image.slotOffset(state.kind, slot));
        from = session.port.emulator ? "Gelesen aus dem laufenden Emulator." : "Gelesen aus dem Gerät, nur lesend.";
      } catch (e) {
        from = `Nicht gelesen (${e.message}); Stand aus der Firmware-Datei.`;
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
    if (!unit) return [el("p", { className: "muted", textContent: `Baustein ${hex(device)} ist unbekannt; seine Parameter kennt niemand.` })];
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
          s.setAttribute("aria-label", `${label}, Zeile ${row.index + 1}`);
          for (const o of options) s.append(el("option", { value: String(o.raw), textContent: o.label }));
          if (!options.some(o => o.raw === current)) s.append(el("option", { value: String(current), textContent: `unbekannt (${current})` }));
          s.value = String(current);
          s.addEventListener("change", () => { set(id, Number(s.value)); if (id !== "fx.map.param") draw(); });
          return s;
        };
        const chain = META.chains.find(c => c.raw === row.chain);
        const unit = chain?.stage ? unitFor(state.units, chain.stage === "mfx" ? "mfx" : "ifx", state.rec.device(chain.stage)) : null;
        const params = unit ? unit.params.map(p => ({ raw: p.index, label: labelFor(p.name).de })) : [{ raw: row.param, label: `Parameter ${row.param}` }];
        const number = (id, word) => {
          const input = el("input", { type: "number", className: "input cee-num", min: 0, max: 127, step: 1, value: String(row[id === "fx.map.low" ? "low" : "high"]) });
          input.setAttribute("aria-label", `${word}, Zeile ${row.index + 1}`);
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
        const remove = el("button", { type: "button", className: "btn sm", textContent: "Entfernen" });
        remove.setAttribute("aria-label", `Zeile ${row.index + 1} entfernen`);
        remove.addEventListener("click", () => { writeRaw(state.rec.bytes, field("fx.map.source"), ix, 0); edited(); draw(); });
        rows.append(el("div", { className: "cee-fxmap-row" }, [
          el("div", { className: "cee-sentence" }, [
            select("fx.map.source", sources.map(s => ({ raw: s.raw, label: who(s) })), row.source, "Quelle"),
            el("span", { textContent: "steuert" }),
            select("fx.map.chain", chains.map(c => ({ raw: c.raw, label: c.label })), row.chain, "Ziel"),
            ...(chain?.stage ? [el("span", { textContent: ">" }), select("fx.map.param", params, row.param, "Parameter")] : []),
            el("span", { textContent: "von" }),
            number("fx.map.low", "Von"),
            el("span", { textContent: "bis" }),
            number("fx.map.high", "Bis"),
            remove,
          ]),
          bar,
        ]));
      }
      const add = el("button", { type: "button", className: "btn sm", textContent: "Steuerung hinzufügen" });
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
        toast("Das geht hier nicht: Es ist kein Platz mehr frei, oder dieser Effekt lässt sich nicht kopieren.", "error");
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
    details.append(el("summary", { textContent: "Expertenmodus: unbekannte Bytes" }));
    const body = el("div", { className: "ui-details-body" });
    body.append(el("p", { className: "cee-hint", textContent: "Was diese Bytes bewirken, weiß niemand. Der Probelauf prüft nur, dass der Befehl ankommt. Änderungen gehen nur live ins RAM." }));
    for (const f of UNKNOWN) {
      const levels = f.repeat ? f.repeat[0].count : 1;
      for (let i = 0; i < levels; i++) {
        const [a, bEnd] = spans(f)[i];
        if (f.id.startsWith("fx.map") && state.rec.bytes[field("fx.map.source").where.offset + i * 28] === 0) continue;
        if (f.id === "fx.stage.unknown" && !state.rec.bytes[field("fx.stage.device").where.offset + i * 0x4a]) continue;
        const inputs = [];
        for (let k = a; k < bEnd; k++) {
          const input = el("input", { type: "number", className: "input cee-byte", min: 0, max: 255, value: String(state.rec.bytes[k]) });
          input.setAttribute("aria-label", `${f.label.de} ${i + 1}, Byte ${k - a + 1}`);
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
        const apply = el("button", { type: "button", className: "btn", id: `${id}-apply`, textContent: "Werte übernehmen" });
        apply.addEventListener("click", () => { applySuggestion(state.rec, s, state.units); edited(); renderEditor(); });
        const values = Object.entries(s.params).map(([name, v]) => `${labelFor(name).de} ${v}`).join(", ");
        return el("div", { className: "cee-group", id }, [
          el("h3", { textContent: `Vorschlag: ${s.label.de}` }),
          el("p", {}, [pill("warn", "am Gerät ungetestet"), ` ${s.hint}`]),
          el("p", { className: "muted cee-small", textContent: `Setzt: ${values}. Alles andere im Preset bleibt, wie es ist.` }),
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
        el("h3", { textContent: `${stage === "mfx" ? "Master" : `Stufe ${STAGE_INDEX[stage] + 1}`}: ${unit ? unit.unit : hex(state.rec.device(stage))}` }),
        ...paramSections(stage),
      ]);
    });
    const toggle = el("input", { type: "checkbox", id: `${prefix}-expert-toggle`, checked: state.expert });
    toggle.setAttribute("role", "switch");
    toggle.addEventListener("change", () => { state.expert = toggle.checked; renderEditor(); });
    editor.replaceChildren(
      el("p", { className: "muted cee-small", id: `${prefix}-fx-source`, textContent: state.from ?? "" }),
      el("div", { className: "cee-group cee-fxhead" }, [name.node, el("label", { className: "ui-switch" }, [toggle, el("span", { className: "ui-switch-track", ariaHidden: "true" }), "Experte"])]),
      ...stageBlocks,
      ...suggestionBlocks(),
      el("div", { className: "cee-group" }, [el("h3", { textContent: "Steuerung" }), mapRows()]),
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
      list.append(el("li", { className: "ui-row" }, [pill(tone, word), el("span", { className: "ui-break", textContent: ` ${f.message}` })]));
    }
    const unknown = unknownChanges(state.original.bytes, state.rec.bytes).length;
    verdict.replaceChildren(
      el("h3", { textContent: "Türsteher" }),
      findings.length ? list : el("p", {}, [pill("ok", "sauber"), " Keine Befunde."]),
      unknown ? el("p", { className: "cee-hint", textContent: `${unknown} Byte in unbekannten Feldern geändert.` }) : "",
    );
  }

  function progress(name) {
    job.hidden = false;
    const bar = el("div", { className: "ui-progress", role: "progressbar" }, [el("span", { className: "ui-progress-bar" })]);
    bar.setAttribute("aria-valuemin", "0");
    bar.setAttribute("aria-valuemax", "100");
    const state = el("span", { className: "cee-status", textContent: "Läuft" });
    state.dataset.tone = "running";
    const meta = el("span", { className: "ui-job-meta" });
    job.replaceChildren(el("div", { className: "ui-job-head" }, [el("span", { className: "ui-job-name", textContent: name }), state]), bar, meta);
    return {
      step(n, total) { window.ui?.setProgress(bar, Math.round((n / total) * 100), name); meta.textContent = `Schritt ${n} von ${total}`; },
      done(ok, text) {
        state.textContent = ok ? "Fertig" : "Fehlgeschlagen";
        state.dataset.tone = ok ? "ok" : "error";
        bar.dataset.tone = ok ? "ok" : "error";
        window.ui?.setProgress(bar, 100, name, ok ? undefined : { valueText: "Fehlgeschlagen" });
        meta.textContent = text;
      },
    };
  }

  async function send() {
    const session = await pick();
    if (!session) { verdict.prepend(el("p", { className: "cee-error", textContent: state.why ?? "Weder Emulator noch Gerät verbunden. Schalte den Emulator ein." })); return; }
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
        const text = checked.reasons.map(r => `${SEVERITY[r.severity]?.[1] ?? r.severity}: ${r.message}`).join("\n");
        const yes = await window.ui.confirm({ title: "Trotz Warnungen senden?", text, confirmLabel: "Senden", danger: false });
        if (!yes) return;
      }
      p = progress(`${state.kind === "ifx" ? "IFX" : "MFX"} ${state.slot} ins RAM`);
      // The yes covers exactly what was shown; a different verdict asks again.
      const result = await whenIdle(session, () => session.apply(edit, { confirmed: checked.token, onStep: p.step }));
      if (result.needsConfirmation) { p.done(false, "Der Befund hat sich geändert, bitte noch einmal senden."); return; }
      if (result.gate?.verdict === "blocked") { p.done(false, "Vom Türsteher gesperrt."); showBlocked(result.gate.reasons); return; }
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
      const [tone, word] = SEVERITY[r.severity] ?? ["error", "gesperrt"];
      list.append(el("li", { className: "ui-row" }, [pill(tone, word), el("span", { className: "ui-break", textContent: ` ${r.message}` })]));
    }
    verdict.replaceChildren(el("h3", { textContent: "Gesperrt" }), list);
    device.log?.(`Gesperrt: ${reasons[0]?.message ?? ""}`, "error");
  }

  function finish(result, p) {
    const target = `${state.kind === "ifx" ? "IFX" : "MFX"} ${state.slot}`;
    if (result.ok) {
      p?.done(true, "Gesendet und zurückgelesen, stimmt überein.");
      device.log?.(`${target} live geschrieben.`, "ok");
      undoButton.disabled = false;
      onSent?.({ kind: state.kind, slot: state.slot });
      return;
    }
    const text = result.error ? `${result.error.message}${result.pending?.now ? ` ${result.pending.now.text}` : ""}` : "abgebrochen";
    p?.done(false, text);
    device.log?.(`${target}: ${text}`, "error");
    if (device.session?.blocked) {
      showBlocked([{ severity: "error", code: "target-blocked", message: `${device.session.blocked} Entscheiden im Bereich Gerät.` }]);
      device.showDecision?.();
    }
  }

  async function undoLive() {
    const session = await pick();
    if (!session) return;
    const release = session.reserve();
    undoButton.disabled = true;
    const p = progress("Zurücknehmen");
    let res;
    try {
      res = await whenIdle(session, () => session.undo({ onStep: p.step }));
    } catch (e) {
      res = { ok: false, error: e };
    } finally {
      release();
    }
    p.done(res.ok, res.ok ? "Alter Stand ist wieder im RAM." : res.error.message);
    device.log?.(res.ok ? "Letzte Änderung zurückgenommen." : `Zurücknehmen fehlgeschlagen: ${res.error.message}`, res.ok ? "ok" : "error");
    undoButton.disabled = !session.history.length;
  }

  const kindWord = kind => (kind === "ifx" ? "Insert" : "Master");

  function renderRoom() {
    const info = state.image ? presetRoom(state.image.bytes, state.kind) : null;
    fileGroup.hidden = !info;
    if (!info) return;
    const more = info.patched ? "" : ` Die Firmware kennt nur ${info.capacity}; mit dem BLECHTRIBE-Patch preset-tables sind es 128.`;
    room.textContent = `${kindWord(state.kind)}: ${info.count} von ${info.capacity} Plätzen im Menü.${more}`;
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

  function addCopy() {
    commit();
    const added = addPreset(state.image.bytes, state.kind, state.slot);
    if (!added.ok) {
      window.ui?.toast?.(added.reasons.join(" "));
      exportNote.hidden = false;
      exportNote.textContent = added.reasons.join(" ");
      return;
    }
    state.image.bytes.set(added.bytes);
    state.added.add(`${state.kind}:${added.slot}`);
    state.fileDirty = true;
    state.passed = null;
    downloadButton.hidden = true;
    exportNote.hidden = false;
    exportNote.textContent = `${kindWord(state.kind)} ${added.slot} ist eine Kopie von ${state.slot}. Ändere sie hier und prüfe die Kopie der Firmware.`;
    state.dirty = false;
    state.slot = added.slot;
    renderPicker();
  }

  /** The preset in the form as a .e2fx file, to pass it on. */
  function savePreset() {
    if (!state.rec) return;
    commit();
    const rec = state.image.read(state.kind, state.slot);
    const a = el("a", { href: URL.createObjectURL(new Blob([presetFile(state.kind, rec.bytes)], { type: "application/json" })), download: presetFileName(state.kind, rec.name) });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
  }

  /** A .e2fx file as a new slot of its kind: a copy of slot 1 is made, then the file's record goes in, name and all. */
  async function loadPreset(file) {
    const got = readPresetFile(await file.text());
    exportNote.hidden = false;
    if (!got.ok) { exportNote.textContent = got.reason; return; }
    if (!state.image) { exportNote.textContent = "Erst eine Firmware laden, dann kommt das Preset hinein."; return; }
    commit();
    const added = addPreset(state.image.bytes, got.kind, 1);
    if (!added.ok) { exportNote.textContent = added.reasons.join(" "); return; }
    state.image.bytes.set(added.bytes);
    state.image.write(got.kind, added.slot, new FxRecord(got.record, got.kind));
    state.added.add(`${got.kind}:${added.slot}`);
    state.fileDirty = true;
    state.passed = null;
    downloadButton.hidden = true;
    state.kind = got.kind;
    state.slot = added.slot;
    state.dirty = false;
    exportNote.textContent = `${kindWord(got.kind)} ${added.slot}: „${got.name}“ aus der Datei. Prüf die Kopie der Firmware, dann kommt es aufs Gerät.`;
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
      if (!emu) throw new Error("Wähle im Bereich Emulator die Firmware (VSB): dort wird die Kopie geprüft, bevor du sie bekommst.");
      exportNote.textContent = "Der Emulator startet die Kopie auf allen Startwegen und prüft die Presets, das dauert ein paar Minuten.";
      const report = await emu.check(state.base, res.bytes, res.allow, res.allowCode);
      exportChecks.replaceChildren(...report.checks.map(c => el("li", { className: "ui-row" }, [
        pill(c.ok ? "ok" : "error", c.ok ? "bestanden" : "nicht bestanden"), el("strong", { textContent: ` ${checkName(c.id)}` }), el("span", { className: "ui-break muted", textContent: ` ${checkDetail(c.detail)}` }),
      ])));
      exportChecks.hidden = false;
      const good = report.checks.filter(c => c.ok).length;
      exportNote.textContent = report.ok
        ? "Geprüft, alles in Ordnung. Du kannst die Datei jetzt speichern."
        : `Die Prüfung hat ${report.checks.length - good} Fehler gefunden. Diese Änderung lässt sich so nicht speichern. Schick uns bitte einen Screenshot.`;
      if (report.ok) { state.passed = res.bytes; downloadButton.hidden = false; }
    } catch (e) {
      exportNote.textContent = e.message;
    } finally {
      renderRoom();
    }
  }

  function downloadCopy() {
    if (!state.passed) return;
    const a = el("a", { href: URL.createObjectURL(new Blob([state.passed], { type: "application/octet-stream" })), download: "SYSTEM.VSB" });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
    exportNote.textContent = "Kopiere die Datei wie im Bereich Patcher beschrieben auf die SD-Karte und starte SOFTWARE UPDATE unter DATA UTILITY.";
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
    /** Show inserts or masters; before a file is loaded, the dropzone is where to go. */
    selectKind(kind) {
      if (!state.image) return drop;
      if (state.kind !== kind) { state.kind = kind; state.slot = null; renderPicker(); }
      return picker;
    },
  };
}
