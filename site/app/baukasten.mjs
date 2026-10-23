/**
 * The Baukasten: effects and modulation types built from blocks, without knowing the firmware. Four sub-pages: the
 * catalog, the editor, the user's own ones, and the export that puts them on places of the Electribe in the
 * collection e2sFx.all for the card (src/fx-collection.mjs). Single ones go out as .e2fx v2 files (src/fx-v2.mjs).
 * Needs no firmware until the export.
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { saveFile } from "./save-file.mjs";
import { icon } from "./icons.mjs";
import { knob } from "./fx-knob.mjs";
import { clamp } from "./dials.mjs";
import { parseUnits } from "../../src/units.mjs";
import { fxText, readFx, fxFileName, fxToRecord } from "../../src/fx-v2.mjs";
import { buildCollection, parseCollection, collectionEntry, COLLECTION_FILE, COLLECTION_FOLDER, MOD_COUNT } from "../../src/fx-collection.mjs";
import { buildOf } from "../../src/firmware.mjs";
import { FX_CATALOG, MOD_CATALOG } from "../../data/fx/catalog.mjs";
import { GROUPS, unitLabel, paramLabel } from "../../data/fx/labels.mjs";
import { GROUPS as PARAM_GROUPS, labelFor } from "../../data/map/fx-labels.mjs";
import FINDINGS from "../../data/findings.mjs";
import { BLOCKS, field } from "../../src/map/index.mjs";
import { REC } from "../../src/layout.mjs";

const OWN = "cee.baukasten";
const SLOTS = "cee.baukasten.slots";
const STAGES = { mfx: ["mfx"], ifx: ["ifx1", "ifx2"] };
const SOURCES = [[1, "LFO"], [0, "Hüllkurve"], [2, "Aus"]];
const TARGETS = [[3, "Filter"], [1, "Tonhöhe"], [2, "Oszillator"], [8, "Lautstärke"], [9, "Panorama"], [10, "Insert-Effekt"], [0, "Kein Ziel"]];
const CURVES = [[6, "Sinus", "M2 12c3-8 7-8 10 0s7 8 10 0"], [2, "Dreieck", "M2 18 7 6l5 12 5-12 5 12"], [1, "Rechteck", "M2 18V6h5v12h5V6h5v12h5"],
  [0, "Sägezahn", "M2 6l10 12V6l10 12"], [3, "Sample and Hold", "M2 14h4V8h4v8h4v-6h4v4h4"], [4, "Zufall", "M2 12l3-5 3 9 3-7 3 6 3-8 3 5"]];
const NS = "http://www.w3.org/2000/svg";

const readOwn = () => { try { return JSON.parse(localStorage.getItem(OWN) ?? "[]"); } catch { return []; } };
const writeOwn = list => { try { localStorage.setItem(OWN, JSON.stringify(list)); return true; } catch { return false; } };

function wave(path) {
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "cee-icon cee-bk-wave");
  svg.setAttribute("aria-hidden", "true");
  const p = document.createElementNS(NS, "path");
  p.setAttribute("d", path);
  svg.append(p);
  return svg;
}

/** A row of buttons that belong together, one pressed; `pick(value)` runs on a choice. */
function choices(id, label, options, pick) {
  const group = el("div", { className: "cee-bk-choices", id, role: "radiogroup" });
  group.setAttribute("aria-label", label);
  const buttons = options.map(([value, text, extra]) => {
    const b = el("button", { type: "button", className: "btn cee-bk-choice", role: "radio" }, [extra ?? null, el("span", { textContent: text })]);
    b.dataset.value = String(value);
    b.addEventListener("click", () => pick(value));
    return b;
  });
  group.append(...buttons);
  return { node: group, set(value) { for (const b of buttons) b.setAttribute("aria-checked", String(b.dataset.value === String(value))); } };
}

/** The name of an effect or modulation, edited in place: a pencil before it, the field as wide as the longest name. */
function nameField(input) {
  input.style.setProperty("--cee-name-length", input.maxLength);
  return el("label", { className: "cee-bk-name-field" }, [icon("pencil"), input]);
}

/** The values a parameter takes on the device (data/map/fx-params.mjs); 0 to 127 where the map does not know. */
function rangeOf(kind, unit, name) {
  try {
    return field(`fx.${kind}.0x${unit.toString(16).padStart(2, "0")}.${name}`).range ?? [0, 127];
  } catch {
    return [0, 127];
  }
}

/** What a building block does behind another one in an insert effect, as measured (data/findings.mjs). */
const STAGE2 = new Map(FINDINGS.filter(f => f.kind === "stage2").map(f => [f.unit, f]));
const SOLO = new Map(FINDINGS.filter(f => f.kind === "stage1NeedsSolo").map(f => [f.unit, f]));
const STAGE2_WORD = { fatal: "Stürzt an zweiter Stelle ab", silent: "Bleibt an zweiter Stelle stumm" };
const MAP_META = BLOCKS.get("fxRecord").meta;

const PARAM_ORDER = ["mix", "filter", "delay", "mod", "dyn", "room", "tone", "eq", "other"];
const KIND_WORD = { mfx: "Master-Effekt", ifx: "Insert-Effekt", mod: "Modulation" };
const SLOT_COUNT_FX = 100;
const PAGES = [["catalog", "Katalog", "grid"], ["editor", "Editor", "sliders"], ["mine", "Meine Effekte", "folder"], ["export", "Export", "download"]];

/** The word on a card under the title: the group of the first block, or what a modulation moves first. */
function tagOf(preset) {
  if (preset.kind === "mod") {
    const slot = preset.slots.find(s => s.source !== 2 && s.target !== 0);
    return slot ? TARGETS.find(([v]) => v === slot.target)?.[1] ?? "Bewegung" : "Bewegung";
  }
  const s = preset.stages.find(x => x.unit);
  return s ? unitLabel(s.stage === "mfx" ? "mfx" : "ifx", s.unit, s.unitName)[1] : "";
}

/** Which slot holds which own effect in the export, per kind: {ifx: {"42": id}, mfx: {...}, mod: {...}}. */
const readSlots = () => { try { return { ifx: {}, mfx: {}, mod: {}, ...JSON.parse(localStorage.getItem(SLOTS) ?? "{}") }; } catch { return { ifx: {}, mfx: {}, mod: {} }; } };
const writeSlots = slots => { try { localStorage.setItem(SLOTS, JSON.stringify(slots)); return true; } catch { return false; } };
const newId = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

/** The own list as {id, kind, text}; an entry from before the sub-pages carried its slot, which moves to the export. */
function ownList() {
  const list = readOwn();
  if (!list.some(o => !o.id)) return list;
  const slots = readSlots();
  for (const o of list) {
    if (o.id) continue;
    o.id = newId();
    if (o.slot) slots[o.kind][o.slot] = o.id;
    delete o.slot;
  }
  writeOwn(list);
  writeSlots(slots);
  return list;
}

/**
 * @param {HTMLElement} root
 * @param {{emulator?: object, presets?: object, sub?: object, trail?: (parts: string[]) => void, navbar?: (nodes: Node[]) => void}} [options]
 *   presets: the panel of the Presets page (fx.mjs), which knows the slots and writes a record live
 */
export function baukastenPage(root, { emulator = null, presets = null, sub = null, trail = () => {}, navbar = () => {} } = {}) {
  let raw = null;            // data/units.json as it is, for the defaults of a block
  let units = null;
  let shelfKind = "fx";      // Effekte or Modulationen, for every sub-page
  let shown = null;
  let fx = null;             // the effect in the editor, .e2fx v2 values
  let fxId = null;           // the own entry it came from, null for a new one or a copy of the catalog
  let mod = null;
  let modId = null;
  let fxTarget = null;       // the slot this effect was loaded to on the device; the next load goes there without asking
  const snap = { fx: null, mod: null }; // the open piece as last opened or saved, so Abbrechen knows whether it loses anything

  async function loadUnits() {
    if (units) return units;
    const res = await fetch(new URL("../../data/units.json", import.meta.url));
    raw = await res.json();
    units = parseUnits(raw);
    return units;
  }
  const defaultsOf = (kind, id) => Object.fromEntries((raw[kind === "mfx" ? "mfx_device" : "ifx_device"][`0x${id.toString(16).padStart(2, "0")}`]?.params ?? [])
    .map(p => [p.name, parseInt(p.default, 16)]));
  const unitKind = stage => (stage === "mfx" ? "mfx" : "ifx");
  const parse = o => { const read = units ? readFx(o.text, units) : null; return read?.ok ? read.preset : JSON.parse(o.text); };

  /** The plugin catalog's card (scripts.mjs catalogCard): the whole card opens it; `extra` sits on top of the card (the trash can). */
  function card(preset, { creator, onOpen, extra = null, id = null }) {
    return el("li", { className: "cee-catalog-card cee-bk-card", id }, [
      el("h3", {}, el("button", { type: "button", className: "cee-catalog-open", textContent: preset.name, onclick: onOpen })),
      el("p", { className: "cee-catalog-category", textContent: tagOf(preset) }),
      el("p", { className: "muted", textContent: preset.description ? `${KIND_WORD[preset.kind]}. ${preset.description}` : KIND_WORD[preset.kind] }),
      creator ? el("p", { className: "cee-catalog-creator muted", textContent: `von ${creator}` }) : null,
      extra,
    ]);
  }

  // ---- Katalog ----------------------------------------------------------------------
  const fxCatalog = el("ul", { className: "cee-catalog cee-bk-catalog", id: "cee-bk-fx-catalog" }, FX_CATALOG.map(item => card(item, { creator: item.creator, onOpen: () => openDetail(item) })));
  const modCatalog = el("ul", { className: "cee-catalog cee-bk-catalog", id: "cee-bk-mod-catalog", hidden: true }, MOD_CATALOG.map(item => card(item, { creator: item.creator, onOpen: () => { openMod(structuredClone(item), null); page("editor"); } })));
  const catalogTitle = el("h2", { className: "cee-bk-title", textContent: "Effekte" });
  const catalogPage = el("div", { className: "cee-bk-page", id: "cee-bk-page-catalog" }, [
    el("p", { className: "cee-bk-lead", textContent: "Bau dir eigene Effekte und Modulationen aus Bausteinen. Nimm einen fertigen und dreh an den Reglern, oder fang im Editor leer an. Unter Export kommt alles in eine Datei für die Karte deiner Electribe." }),
    catalogTitle, fxCatalog, modCatalog,
  ]);

  // ---- Editor: effect ---------------------------------------------------------------
  const blocks = el("div", { className: "cee-bk-blocks", id: "cee-bk-blocks" });
  const fxName = el("input", { className: "cee-bk-name", id: "cee-bk-fx-name", type: "text", maxLength: 15, spellcheck: false, autocomplete: "off", placeholder: "Name des Effekts" });
  fxName.setAttribute("aria-label", "Name des Effekts, bis 15 Zeichen");
  fxName.addEventListener("input", () => { if (fx) fx.name = fxName.value; });
  const fxKind = el("p", { className: "cee-bk-kind muted", id: "cee-bk-fx-kind" });
  const fxSave = el("button", { type: "button", className: "btn cee-primary", id: "cee-bk-fx-save", textContent: "Speichern" });
  const fxDownload = el("button", { type: "button", className: "btn", id: "cee-bk-fx-download", textContent: "Als Datei herunterladen" });
  const fxSaved = el("p", { className: "cee-bk-saved", id: "cee-bk-fx-saved", role: "status" });
  const fxLoad = el("button", { type: "button", className: "btn", id: "cee-bk-fx-load", textContent: "Auf dem Gerät laden" });
  const fxRetarget = el("button", { type: "button", className: "btn", id: "cee-bk-fx-retarget", textContent: "Anderer Platz", hidden: true });
  let fxHelp = null;
  const fxEditor = el("div", { className: "cee-bk-builder", id: "cee-bk-fx-builder", hidden: true }, [
    el("div", { className: "cee-bk-head" }, [nameField(fxName), fxKind]),
    fxHelp = el("p", { className: "muted", id: "cee-bk-fx-help", textContent: "Ein Baustein ist ein einzelner Effekt wie Hall, Echo oder Filter. Ein Insert-Effekt kann zwei hintereinander haben, der zweite darf leer bleiben. Anhören kannst du ihn erst an der Electribe." }),
    blocks,
    el("div", { className: "actions" }, [fxSave, fxDownload, fxLoad, fxRetarget, el("button", { type: "button", className: "btn", id: "cee-bk-fx-cancel", textContent: "Abbrechen", onclick: () => leave("fx") })]),
    fxSaved,
  ]);
  const fxStart = el("div", { className: "cee-bk-builder", id: "cee-bk-fx-start" }, [
    el("h2", { className: "cee-bk-title", textContent: "Neuer Effekt" }),
    el("ul", { className: "cee-bk-explain" }, [
      el("li", {}, [el("strong", { textContent: "Master-Effekt: " }), "das ganze Pattern klingt durch den Effekt, zum Beispiel ein Hall über alles."]),
      el("li", {}, [el("strong", { textContent: "Insert-Effekt: " }), "nur der Part, dem du den Effekt gibst, zum Beispiel ein Echo nur auf der Snare."]),
    ]),
    el("div", { className: "actions", id: "cee-bk-where" }, [
      el("button", { type: "button", className: "btn cee-primary", id: "cee-bk-new-mfx", textContent: "Neuer Master-Effekt", onclick: () => newFx("mfx") }),
      el("button", { type: "button", className: "btn cee-primary", id: "cee-bk-new-ifx", textContent: "Neuer Insert-Effekt", onclick: () => newFx("ifx") }),
      el("button", { type: "button", className: "btn", textContent: "Aus dem Katalog nehmen", onclick: () => page("catalog") }),
    ]),
  ]);
  const newFx = kind => openFx({ kind, name: "", stages: STAGES[kind].map(stage => ({ stage, unit: 0, unitName: "nofx_thru", params: {} })), map: [] }, null);

  // The building blocks to choose from, by group; a dialog over the page.
  const palette = el("dialog", { className: "ui-dialog cee-bk-palette", id: "cee-bk-palette" });
  palette.setAttribute("aria-labelledby", "cee-bk-palette-title");
  const paletteBody = el("div", { className: "ui-dialog-body" });
  palette.append(el("form", { method: "dialog", className: "ui-dialog-box" }, [
    el("header", { className: "ui-dialog-head" }, el("h2", { className: "ui-dialog-title", id: "cee-bk-palette-title", textContent: "Baustein wählen" })),
    paletteBody,
    el("footer", { className: "ui-dialog-foot" }, el("button", { type: "submit", className: "btn", value: "cancel", textContent: "Abbrechen" })),
  ]));
  document.body.append(palette);
  function choose(stage) {
    const kind = unitKind(stage);
    const all = [...units[kind].values()].filter(u => u.id !== 0 && u.unit !== "nofx_mute" && u.params.length);
    const other = fx.stages.find(x => x.stage === (stage === "ifx1" ? "ifx2" : "ifx1"));
    /** Why this block cannot go here, or null. */
    const barred = u => {
      if (stage === "ifx2" && STAGE2_WORD[STAGE2.get(u.id)?.verdict]) return STAGE2_WORD[STAGE2.get(u.id).verdict];
      if (stage === "ifx2" && SOLO.has(other?.unit)) return "Baustein 1 läuft nur allein";
      if (stage === "ifx1" && other?.unit && SOLO.has(u.id)) return "Läuft nur allein, ohne Baustein 2";
      return null;
    };
    paletteBody.replaceChildren(...GROUPS.map(group => {
      const here = all.filter(u => unitLabel(kind, u.id, u.unit)[1] === group);
      if (!here.length) return null;
      return el("section", { className: "cee-bk-group" }, [
        el("h3", { textContent: group }),
        el("div", { className: "cee-bk-units" }, here.map(u => el("button", { type: "button", className: "btn cee-bk-unit", disabled: !!barred(u), title: barred(u) ?? "", onclick: () => {
          const s = fx.stages.find(x => x.stage === stage);
          Object.assign(s, { unit: u.id, unitName: u.unit, params: defaultsOf(kind, u.id) });
          palette.close();
          renderFx();
        } }, [el("strong", { textContent: unitLabel(kind, u.id, u.unit)[0] }), el("span", { className: "muted", textContent: barred(u) ?? (stage === "ifx2" && STAGE2.get(u.id)?.verdict !== "ok" ? `${u.unit}, an zweiter Stelle nicht getestet` : u.unit) })]))),
      ]);
    }).filter(Boolean));
    if (window.ui?.openDialog) window.ui.openDialog(palette); else palette.showModal?.();
  }

  function renderFx() {
    fxEditor.hidden = !fx;
    fxStart.hidden = !!fx;
    if (shown) switchRow();
    if (!fx) return;
    fxName.value = fx.name;
    fxKind.textContent = KIND_WORD[fx.kind];
    const knobs = new Map();
    blocks.replaceChildren(...blockCards(fx, { knobs }), mapSection(fx, { knobs }));
    // The explanation is for an effect built from scratch; one that already has its blocks needs none.
    fxHelp.hidden = fx.stages.some(s => s.unit);
  }

  /**
   * Steuerung: which control moves which parameter between two values, as on the device's own presets. A new row
   * copies a used one when the record is written (src/fx-v2.mjs), so it never comes from zeros. The knob a row moves
   * shows the stretch as a ring.
   */
  function mapSection(piece, { readOnly = false, pre = "cee-bk", knobs = new Map() } = {}) {
    const kind = piece.kind === "mfx" ? "mfx" : "ifx";
    const sources = MAP_META.sources.filter(x => x[kind]);
    const chains = MAP_META.chains.filter(c => !c.stage || (kind === "mfx" ? c.stage === "mfx" : c.stage !== "mfx"));
    const rows = el("div", { className: "cee-fxmap", id: `${pre}-map` });
    const rings = () => {
      for (const k of knobs.values()) k.span(null);
      for (const row of piece.map) knobs.get(targetOf(row))?.span(row.low, row.high);
    };
    const draw = () => {
      rows.replaceChildren(...piece.map.map((row, n) => {
        const select = (key, options, word) => {
          const box = el("select", { className: "select", disabled: readOnly });
          box.setAttribute("aria-label", `${word}, Zeile ${n + 1}`);
          for (const o of options) box.append(el("option", { value: String(o.raw), textContent: o.label }));
          if (!options.some(o => o.raw === row[key])) box.append(el("option", { value: String(row[key]), textContent: `unbekannt (${row[key]})` }));
          box.value = String(row[key]);
          box.addEventListener("change", () => { row[key] = Number(box.value); if (key === "chain") row.param = 0; if (key === "chain" || key === "source") draw(); else rings(); });
          return box;
        };
        const chain = chains.find(c => c.raw === row.chain);
        const stage = chain?.stage ? piece.stages.find(x => x.stage === chain.stage) : null;
        const params = stage?.unit ? (units[unitKind(stage.stage)].get(stage.unit)?.params ?? []).map(x => ({ raw: x.index, label: paramLabel(x.name) })) : [];
        const number = (key, word) => {
          const box = el("input", { type: "number", className: "input cee-num", min: 0, max: 127, step: 1, value: String(row[key]), readOnly });
          box.setAttribute("aria-label", `${word}, Zeile ${n + 1}`);
          box.addEventListener("change", () => { row[key] = Math.max(0, Math.min(127, Math.round(Number(box.value) || 0))); box.value = String(row[key]); rings(); });
          return box;
        };
        // A control with two states (the touchpad held or not, the FX switch, play) sets one value per state.
        const [off, on] = sources.find(x => x.raw === row.source)?.states?.[kind] ?? ["von", "bis"];
        return el("div", { className: "cee-fxmap-row" }, [
          el("div", { className: "cee-sentence" }, [
            select("source", sources.map(x => ({ raw: x.raw, label: x.who?.[kind] ?? x.label })), "Quelle"),
            el("span", { textContent: "steuert" }),
            select("chain", chains.map(c => ({ raw: c.raw, label: chainLabel(piece, c) })), "Ziel"),
            ...(params.length ? [el("span", { textContent: ">" }), select("param", params, "Parameter")] : []),
            el("span", { textContent: off }), number("low", off === "von" ? "Von" : `Wert ${off}`),
            el("span", { textContent: on }), number("high", on === "bis" ? "Bis" : `Wert ${on}`),
            readOnly ? null : el("button", { type: "button", className: "btn sm", textContent: "Entfernen", onclick: () => { piece.map.splice(n, 1); draw(); } }),
          ]),
        ]);
      }));
      if (!piece.map.length) rows.append(el("p", { className: "muted", textContent: "Keine Steuerung: der Effekt klingt immer gleich." }));
      if (!readOnly && piece.map.length < REC.mapEntries) {
        rows.append(el("div", { className: "actions" }, el("button", { type: "button", className: "btn sm", id: `${pre}-map-add`, textContent: "Steuerung hinzufügen", onclick: () => {
          piece.map.push({ source: sources[0].raw, chain: chains[0].raw, param: 0, low: 0, high: 127 });
          draw();
        } })));
      }
      rings();
    };
    draw();
    const look = el("button", { type: "button", className: "btn sm", id: `${pre}-map-preview`, onclick: () => previewMap(piece, knobs) }, [icon("eye"), "Vorschau"]);
    return el("section", { className: "cee-bk-map" }, [
      el("div", { className: "cee-bk-map-head" }, [el("h3", { className: "cee-bk-stage-title", textContent: "Steuerung" }), look]),
      rows,
    ]);
  }

  /** What a row drives in the words of the editor: the block as its card names it, or the level around the effect. */
  function chainLabel(piece, chain) {
    if (!chain?.stage) return chain?.label ?? "?";
    const stage = piece.stages.find(x => x.stage === chain.stage);
    const name = stage?.unit ? unitLabel(unitKind(stage.stage), stage.unit, stage.unitName)[0] : "leer";
    return piece.stages.length > 1 ? `Baustein ${piece.stages.indexOf(stage) + 1} (${name})` : `Baustein (${name})`;
  }

  /** The key of the knob a map row moves: its stage and parameter, or the level it drives. */
  function targetOf(row) {
    const chain = MAP_META.chains.find(c => c.raw === row.chain);
    return chain?.stage ? `${chain.stage}:${row.param}` : `level:${row.chain}`;
  }

  // The preview of the controls: the device's controls on the right, the knobs they move on the left. Nothing is
  // heard, it only shows what moves where.
  const previewDialog = el("dialog", { className: "ui-dialog ui-dialog-wide cee-bk-preview", id: "cee-bk-preview" });
  previewDialog.setAttribute("aria-labelledby", "cee-bk-preview-title");
  const previewBody = el("div", { className: "ui-dialog-body" });
  previewDialog.append(el("form", { method: "dialog", className: "ui-dialog-box" }, [
    el("header", { className: "ui-dialog-head" }, el("h2", { className: "ui-dialog-title", id: "cee-bk-preview-title", textContent: "Vorschau der Steuerung" })),
    previewBody,
    el("footer", { className: "ui-dialog-foot" }, el("button", { type: "submit", className: "btn", value: "cancel", textContent: "Schließen" })),
  ]));
  document.body.append(previewDialog);

  /**
   * How far a source is turned, 0 to 127, from the state of the controls. The halves are a reading of Korg's names
   * (data/map/fx.mjs), not measured: the upper half moves only above the middle, the lower only below it.
   */
  function sourceValue(raw, c) {
    const upper = v => clamp((v - 64) * 127 / 63, 0, 127);
    const lower = v => clamp(v * 127 / 63, 0, 127);
    switch (raw) {
      case 0x41: return c.on ? 127 : 0;
      case 0x42: return c.x;
      case 0x43: return c.y;
      case 0x44: return upper(c.x);
      case 0x45: return lower(c.x);
      case 0x46: return upper(c.y);
      case 0x47: return lower(c.y);
      case 0x4a: return c.play ? 127 : 0;
      default: return null;
    }
  }

  function previewMap(piece, knobs) {
    const kind = piece.kind === "mfx" ? "mfx" : "ifx";
    // The touchpad only moves anything while it is touched; the insert effect's knob always sits somewhere.
    // On a master effect the switch is the touch itself, so it starts released.
    const c = { x: kind === "ifx" ? 0 : null, y: null, on: kind === "ifx", play: false };
    const shown = new Map();
    for (const row of piece.map) {
      const key = targetOf(row);
      if (shown.has(key)) continue;
      const mirror = knobs.get(key);
      const chain = MAP_META.chains.find(x => x.raw === row.chain);
      const stage = chain?.stage ? piece.stages.find(x => x.stage === chain.stage) : null;
      const p = stage?.unit ? units[unitKind(stage.stage)].get(stage.unit)?.params.find(x => x.index === row.param) : null;
      const [min, max] = p ? rangeOf(unitKind(stage.stage), stage.unit, p.name) : [0, 127];
      const start = p ? (stage.params[p.name] ?? 0) : 127;
      const k = knob(`cee-bk-preview-${key.replace(":", "-")}`, p ? paramLabel(p.name) : chainLabel(piece, chain), p ? chainLabel(piece, chain) : null, min, max, start, () => {}, { readOnly: true });
      k.span(row.low, row.high);
      shown.set(key, { k, mirror, start });
    }
    const apply = () => {
      const moved = new Map();
      for (const row of piece.map) {
        const s = sourceValue(row.source, c);
        if (s === null || !shown.has(targetOf(row))) continue;
        moved.set(targetOf(row), row.low + (row.high - row.low) * s / 127);
      }
      for (const [key, { k, mirror }] of shown) {
        const v = moved.has(key) ? moved.get(key) : null;
        k.show(v);
        mirror?.show(v);
      }
    };

    const controls = [];
    if (kind === "mfx") {
      const dot = el("span", { className: "cee-bk-pad-dot", hidden: true });
      const pad = el("div", { className: "cee-bk-pad", id: "cee-bk-preview-pad", tabIndex: 0, role: "application" }, [dot]);
      pad.setAttribute("aria-label", "Touchpad: drücken und ziehen");
      const touch = e => {
        const r = pad.getBoundingClientRect();
        c.x = Math.round(clamp((e.clientX - r.left) / r.width, 0, 1) * 127);
        c.y = Math.round(clamp(1 - (e.clientY - r.top) / r.height, 0, 1) * 127);
        c.on = true;
        dot.hidden = false;
        dot.style.left = `${(c.x / 127) * 100}%`;
        dot.style.top = `${(1 - c.y / 127) * 100}%`;
        apply();
      };
      const release = () => { c.x = null; c.y = null; c.on = false; dot.hidden = true; apply(); };
      pad.addEventListener("pointerdown", e => { e.preventDefault(); try { pad.setPointerCapture(e.pointerId); } catch {} touch(e); });
      pad.addEventListener("pointermove", e => { if (c.x !== null) touch(e); });
      for (const ev of ["pointerup", "pointercancel"]) pad.addEventListener(ev, release);
      controls.push(el("div", { className: "ui-field" }, [el("span", { className: "ui-field-label", textContent: "Touchpad" }), pad]));
    } else {
      controls.push(knob("cee-bk-preview-knob", "IFX-Regler", null, 0, 127, 0, v => { c.x = v; apply(); }).node);
    }
    const toggle = (id, label, key) => {
      const box = el("input", { type: "checkbox", id, role: "switch", checked: c[key] });
      box.addEventListener("change", () => { c[key] = box.checked; apply(); });
      return el("label", { className: "ui-switch" }, [box, el("span", { className: "ui-switch-track", ariaHidden: "true" }), label]);
    };
    if (kind === "ifx") controls.push(toggle("cee-bk-preview-on", "IFX ON", "on"));
    controls.push(toggle("cee-bk-preview-play", "Pattern läuft", "play"));

    previewBody.replaceChildren(
      el("p", { className: "muted", textContent: "Dreh am IFX-Regler oder drück aufs Touchpad: links siehst du, wie sich die Parameter bewegen. Zu hören ist dabei nichts. So liest die Seite die Steuerung, nachgemessen am Gerät ist das nicht." }),
      shown.size ? el("div", { className: "cee-bk-preview-grid" }, [
        el("div", { className: "cee-bk-params cee-bk-preview-knobs" }, [...shown.values()].map(x => x.k.node)),
        el("div", { className: "cee-bk-preview-controls" }, controls),
      ]) : el("p", { textContent: "Keine Steuerung angelegt: es bewegt sich nichts." }),
    );
    const close = () => { for (const { mirror } of shown.values()) mirror?.show(null); previewDialog.removeEventListener("close", close); };
    previewDialog.addEventListener("close", close);
    if (window.ui?.openDialog) window.ui.openDialog(previewDialog); else previewDialog.showModal?.();
    apply();
  }

  /** The cards of a piece's blocks; read only on a catalog effect's page, where the empty block is left out. */
  function blockCards(piece, { readOnly = false, pre = "cee-bk", knobs = null } = {}) {
    const stages = readOnly ? piece.stages.filter(s => s.unit) : piece.stages;
    return stages.map((s, i) => {
      const kind = unitKind(s.stage);
      const [label, group] = s.unit ? unitLabel(kind, s.unit, s.unitName) : ["Noch leer", ""];
      const params = s.unit ? (units[kind].get(s.unit)?.params ?? []) : [];
      const one = p => {
        const value = s.params[p.name] ?? 0;
        const [min, max] = rangeOf(kind, s.unit, p.name);
        const k = knob(`${pre}-p-${i}-${p.name}`, paramLabel(p.name), p.name, min, max, value, v => { s.params[p.name] = v; }, { readOnly });
        knobs?.set(`${s.stage}:${p.index}`, k);
        return k.node;
      };
      // Knobs that belong together stand together, like the sections of a plugin: the group comes from the name
      // (data/map/fx-labels.mjs), the order puts what shapes the sound before EQ and the rest.
      const sections = PARAM_ORDER.map(id => [id, params.filter(p => labelFor(p.name).group === id)]).filter(([, list]) => list.length);
      const pick = el("button", { type: "button", className: `btn sm${s.unit ? "" : " cee-primary"}`, onclick: () => choose(s.stage) }, s.unit ? [icon("swap"), "Anderen Baustein wählen"] : ["Baustein wählen"]);
      const card = el("div", { className: `cee-bk-block${s.unit ? "" : " cee-bk-block-empty"}`, id: `${pre}-block-${i + 1}` }, s.unit ? [
        el("div", { className: "cee-bk-block-head" }, [
          el("h4", { textContent: label }),
          group ? el("span", { className: "cee-bk-group-name", textContent: group }) : null,
          readOnly ? null : el("div", { className: "actions" }, [
            pick,
            fx.stages.length > 1 ? el("button", { type: "button", className: "btn sm", textContent: "Entfernen", onclick: () => { Object.assign(s, { unit: 0, unitName: "nofx_thru", params: {} }); renderFx(); } }) : null,
          ]),
        ]),
        el("div", { className: "cee-bk-knob-groups" }, sections.map(([id, list]) => el("section", { className: "cee-bk-knob-group" }, [
          el("h5", { className: "cee-bk-more", textContent: PARAM_GROUPS.find(g => g.id === id).label }),
          el("div", { className: "cee-bk-knob-row" }, list.map(one)),
        ]))),
      ] : [el("p", { className: "muted", textContent: "Noch leer" }), pick]);
      return stages.length > 1 ? el("section", { className: "cee-bk-stage" }, [el("h3", { className: "cee-bk-stage-title", textContent: `Baustein ${i + 1}` }), card]) : card;
    });
  }

  function openFx(preset, id) {
    fx = { kind: preset.kind, name: preset.name, stages: preset.stages.map(s => ({ ...s, params: { ...s.params } })), map: (preset.map ?? []).map(m => ({ ...m })) };
    fxId = id;
    snap.fx = JSON.stringify(fx);
    fxTarget = null;
    showTarget();
    fxSaved.textContent = "";
    shelf("fx");
    loadUnits().then(() => { renderFx(); updateTrail(); });
  }

  /** The effect as it stands, or why it is not ready. */
  function readyFx(piece = fx) {
    const fx = piece;
    if (!fx) return { ok: false, reason: "Leg zuerst einen Effekt an." };
    if (!fx.stages.some(s => s.unit)) return { ok: false, reason: "Wähl mindestens einen Baustein." };
    if (!fx.name.trim()) return { ok: false, reason: "Gib dem Effekt oben einen Namen." };
    if (!/^[\x20-\x7e]+$/.test(fx.name)) return { ok: false, reason: "Der Name darf nur Buchstaben ohne Umlaute, Ziffern und einfache Zeichen haben, das Display kennt keine anderen." };
    return { ok: true, preset: { ...fx, name: fx.name.trim() } };
  }
  fxSave.addEventListener("click", () => { const id = keep(readyFx(), fxId, fxSaved); if (id) { fxId = id; snap.fx = JSON.stringify(fx); } });
  fxDownload.addEventListener("click", () => {
    const r = readyFx();
    if (!r.ok) { toast(r.reason, "error"); return; }
    saveFile(fxText(r.preset), fxFileName(r.preset), { type: "application/json" });
  });

  // To try it on the device: the first load asks for a slot of the menu and overwrites that preset live in the RAM,
  // every later load of the same effect goes to the same slot at once. Switching it off brings the preset back.
  const slotDialog = el("dialog", { className: "ui-dialog cee-bk-palette", id: "cee-bk-slots-dialog" });
  slotDialog.setAttribute("aria-labelledby", "cee-bk-slots-title");
  const slotTitle = el("h2", { className: "ui-dialog-title", id: "cee-bk-slots-title" });
  const slotBody = el("div", { className: "ui-dialog-body" });
  slotDialog.append(el("form", { method: "dialog", className: "ui-dialog-box" }, [
    el("header", { className: "ui-dialog-head" }, slotTitle),
    slotBody,
    el("footer", { className: "ui-dialog-foot" }, el("button", { type: "submit", className: "btn", value: "cancel", textContent: "Abbrechen" })),
  ]));
  document.body.append(slotDialog);
  function showTarget() {
    fxLoad.textContent = fxTarget ? `Auf dem Gerät laden (${KIND_WORD[fxTarget.kind]} ${fxTarget.slot})` : "Auf dem Gerät laden";
    fxRetarget.hidden = !fxTarget;
  }
  function pickSlot(piece = fx) {
    const list = presets?.presets()?.list(piece.kind);
    if (!list?.length) { toast("Dafür braucht die Seite deine Firmware und den laufenden Emulator oder die verbundene Electribe: im Bereich Emulator die SYSTEM.VSB aufs Display ziehen.", "error"); return; }
    slotTitle.textContent = `Welchen ${KIND_WORD[piece.kind]} überschreiben?`;
    slotBody.replaceChildren(
      el("p", { className: "muted", textContent: "Der gewählte Platz bekommt deinen Effekt, live im Arbeitsspeicher. Nach dem Ausschalten ist das alte Preset wieder da." }),
      el("div", { className: "cee-bk-units" }, list.map(({ slot, name }) => el("button", { type: "button", className: "btn cee-bk-unit", onclick: () => { slotDialog.close(); loadTo({ kind: piece.kind, slot }, piece); } }, [
        el("strong", { textContent: `${slot}` }), el("span", { className: "muted", textContent: name }),
      ]))),
    );
    if (window.ui?.openDialog) window.ui.openDialog(slotDialog); else slotDialog.showModal?.();
  }
  async function loadTo(target, piece = fx) {
    const r = readyFx(piece);
    if (!r.ok) { toast(r.reason, "error"); return; }
    await loadUnits();
    fxLoad.disabled = true;
    try {
      const res = await presets.writeRecord(target.kind, target.slot, (before, records) => fxToRecord(r.preset, before, records, units));
      if (!res.ok) { if (res.reason) toast(res.reason, "error"); return; }
      if (piece !== fx) { toast(`„${r.preset.name}“ liegt jetzt auf ${KIND_WORD[target.kind]} ${target.slot}. Am Gerät auswählen und anhören.`, "ok"); return; }
      fxTarget = target;
      showTarget();
      toast(`„${r.preset.name}“ liegt jetzt auf ${KIND_WORD[target.kind]} ${target.slot}. Am Gerät auswählen und anhören.`, "ok");
    } finally {
      fxLoad.disabled = false;
    }
  }
  fxLoad.addEventListener("click", () => {
    if (!presets) return;
    if (fxTarget?.kind === fx?.kind) loadTo(fxTarget); else pickSlot();
  });
  fxRetarget.addEventListener("click", () => { if (presets) pickSlot(); });

  // ---- A catalog effect: its own page, like a plugin's ---------------------------------
  // Its values are read only; to change them it becomes an own effect, which then may take its place.
  let view = null;
  const detailHead = el("div", { className: "cee-detail-text", id: "cee-bk-detail-head" });
  const detailBlocks = el("div", { className: "cee-bk-blocks", id: "cee-bk-detail-blocks" });
  const detailPage = el("div", { className: "cee-bk-page cee-detail", id: "cee-bk-page-detail" }, [
    el("button", { type: "button", className: "cee-text-link cee-detail-back", id: "cee-bk-detail-back", textContent: "← Zurück zum Katalog", onclick: () => page("catalog") }),
    detailHead,
    detailBlocks,
  ]);
  function openDetail(item) {
    view = structuredClone(item);
    const download = el("button", { type: "button", className: "btn", id: "cee-bk-detail-download", onclick: () => saveFile(fxText(view), fxFileName(view), { type: "application/json" }) }, [icon("download"), "Herunterladen"]);
    const usb = el("button", { type: "button", className: "btn", id: "cee-bk-detail-load", onclick: () => { if (presets) pickSlot(view); } }, [icon("usb"), "Aufs Gerät"]);
    const own = el("button", { type: "button", className: "btn", id: "cee-bk-detail-own", textContent: "Als eigenen Effekt bearbeiten", onclick: () => {
      const id = keep({ ok: true, preset: structuredClone(view) }, null, fxSaved);
      if (!id) return;
      openFx(view, id);
      page("editor");
    } });
    detailHead.replaceChildren(
      el("h2", { className: "cee-detail-title", id: "cee-bk-detail-title", textContent: view.name }),
      view.description ? el("p", { textContent: view.description }) : null,
      el("dl", { className: "cee-detail-facts" }, [
        el("dt", { textContent: "Art" }), el("dd", { textContent: KIND_WORD[view.kind] }),
        el("dt", { textContent: "Kategorie" }), el("dd", { textContent: tagOf(view) }),
        el("dt", { textContent: "Von" }), el("dd", { textContent: view.creator }),
      ]),
      el("div", { className: "actions" }, [download, usb, own]),
    );
    detailBlocks.replaceChildren();
    page("detail");
    loadUnits().then(() => {
      if (view?.name !== item.name) return;
      const knobs = new Map();
      detailBlocks.replaceChildren(...blockCards(view, { readOnly: true, pre: "cee-bk-detail", knobs }), mapSection(view, { readOnly: true, pre: "cee-bk-detail", knobs }));
    });
  }

  // ---- Editor: modulation -----------------------------------------------------------
  const modName = el("input", { className: "cee-bk-name", id: "cee-bk-mod-name", type: "text", maxLength: 16, spellcheck: false, autocomplete: "off", placeholder: "Name der Modulation" });
  modName.setAttribute("aria-label", "Name der Modulation, bis 16 Zeichen");
  modName.addEventListener("input", () => { if (mod) mod.name = modName.value; });
  const curve = choices("cee-bk-curve", "Welle", CURVES.map(([v, label, path]) => [v, label, wave(path)]), v => { mod.curve = v; curve.set(v); });
  const modBody = el("div", { className: "cee-bk-mod-body", id: "cee-bk-mod-body" });
  const modSave = el("button", { type: "button", className: "btn cee-primary", id: "cee-bk-mod-save", textContent: "Speichern" });
  const modDownload = el("button", { type: "button", className: "btn", id: "cee-bk-mod-download", textContent: "Als Datei herunterladen" });
  const modSaved = el("p", { className: "cee-bk-saved", id: "cee-bk-mod-saved", role: "status" });
  const modEditor = el("div", { className: "cee-bk-builder", id: "cee-bk-mod-builder", hidden: true }, [
    el("div", { className: "cee-bk-head" }, [nameField(modName), el("p", { className: "cee-bk-kind muted", textContent: KIND_WORD.mod })]),
    modBody,
    el("div", { className: "actions" }, [modSave, modDownload, el("button", { type: "button", className: "btn", id: "cee-bk-mod-cancel", textContent: "Abbrechen", onclick: () => leave("mod") })]),
    modSaved,
  ]);
  const modStart = el("div", { className: "cee-bk-builder", id: "cee-bk-mod-start" }, [
    el("h2", { className: "cee-bk-title", textContent: "Neue Modulation" }),
    el("p", { className: "muted", textContent: "Eine Modulation hat fünf Slots. Jeder nimmt eine Quelle (LFO oder Hüllkurve) und bewegt damit ein Ziel." }),
    el("div", { className: "actions" }, [
      el("button", { type: "button", className: "btn cee-primary", id: "cee-bk-mod-new", textContent: "Neue Modulation", onclick: () => openMod({ name: "", depth: 64, speed: 64, curve: 6, slots: Array.from({ length: 5 }, () => ({ source: 2, target: 0, lo: 0, hi: 0, follow: 0 })) }, null) }),
      el("button", { type: "button", className: "btn", textContent: "Aus dem Katalog nehmen", onclick: () => page("catalog") }),
    ]),
  ]);

  function renderMod() {
    if (shown) switchRow();
    modEditor.hidden = !mod;
    modStart.hidden = !!mod;
    if (!mod) return;
    modName.value = mod.name;
    curve.set(mod.curve);
    const slots = mod.slots.map((s, k) => {
      const source = choices(`cee-bk-source-${k}`, `Quelle von Slot ${k + 1}`, SOURCES, v => { s.source = v; source.set(v); });
      const target = choices(`cee-bk-target-${k}`, `Ziel von Slot ${k + 1}`, TARGETS, v => { s.target = v; target.set(v); });
      source.set(s.source);
      target.set(s.target);
      const follow = el("input", { type: "checkbox", id: `cee-bk-follow-${k}`, checked: !!s.follow });
      follow.addEventListener("change", () => { s.follow = follow.checked ? 1 : 0; });
      return el("div", { className: "cee-bk-block", id: `cee-bk-slot-${k + 1}` }, [
        el("h3", { textContent: `Slot ${k + 1}` }),
        el("p", { className: "ui-field-label", textContent: "Was bewegt?" }), source.node,
        el("p", { className: "ui-field-label", textContent: "Was wird bewegt?" }), target.node,
        el("div", { className: "cee-bk-params" }, [
          knob(`cee-bk-lo-${k}`, "Stärke am Anfang", null, -128, 127, s.lo, v => { s.lo = v; }).node,
          knob(`cee-bk-hi-${k}`, "Stärke am Ende", null, -128, 127, s.hi, v => { s.hi = v; }).node,
        ]),
        el("label", { className: "cee-bk-check" }, [follow, " Stärke folgt dem Regler MOD. DEPTH"]),
        el("p", { className: "ui-field-help", textContent: "Ein: mit dem Regler MOD. DEPTH am Gerät machst du diesen Slot stärker oder schwächer. Aus: er wirkt immer gleich stark." }),
      ]);
    });
    modBody.replaceChildren(
      el("p", { className: "ui-field-label", textContent: "Welle des LFO" }), curve.node,
      el("div", { className: "cee-bk-params" }, [
        knob("cee-bk-depth", "Tiefe", "So weit dreht die Firmware MOD. DEPTH, wenn du diese Modulation wählst.", 0, 127, mod.depth, v => { mod.depth = v; }).node,
        knob("cee-bk-speed", "Tempo", "So weit dreht die Firmware MOD. SPEED, wenn du diese Modulation wählst.", 0, 127, mod.speed, v => { mod.speed = v; }).node,
      ]),
      el("p", { className: "muted", textContent: "Eine Modulation hat fünf Slots. Jeder nimmt eine Quelle (LFO oder Hüllkurve) und bewegt damit ein Ziel. Ein Slot mit der Quelle Aus tut nichts." }),
      ...slots,
    );
  }
  function openMod(preset, id) {
    mod = { kind: "mod", name: preset.name, depth: preset.depth, speed: preset.speed, curve: preset.curve, slots: preset.slots.map(s => ({ ...s })) };
    modId = id;
    snap.mod = JSON.stringify(mod);
    modSaved.textContent = "";
    shelf("mod");
    renderMod();
    updateTrail();
  }
  function readyMod() {
    if (!mod) return { ok: false, reason: "Leg zuerst eine Modulation an." };
    if (!mod.name.trim() || !/^[\x20-\x7e]+$/.test(mod.name)) return { ok: false, reason: "Gib der Modulation oben einen Namen, ohne Umlaute." };
    return { ok: true, preset: { ...mod, name: mod.name.trim() } };
  }
  modSave.addEventListener("click", () => { const id = keep(readyMod(), modId, modSaved); if (id) { modId = id; snap.mod = JSON.stringify(mod); } });

  /** Abbrechen: closes the open effect or modulation and goes back to the start of the editor; unsaved changes ask first. */
  async function leave(kind) {
    const open = kind === "fx" ? fx : mod;
    if (open && JSON.stringify(open) !== snap[kind]) {
      const yes = window.ui?.confirm ? await window.ui.confirm({ title: "Änderungen verwerfen?", text: "Was du seit dem letzten Speichern geändert hast, geht verloren.", confirmLabel: "Verwerfen", danger: true }) : true;
      if (!yes) return;
    }
    if (kind === "fx") { fx = null; fxId = null; fxTarget = null; fxSaved.textContent = ""; renderFx(); } else { mod = null; modId = null; modSaved.textContent = ""; renderMod(); }
    renderEditor();
    updateTrail();
  }
  modDownload.addEventListener("click", () => {
    const r = readyMod();
    if (!r.ok) { toast(r.reason, "error"); return; }
    saveFile(fxText(r.preset), fxFileName(r.preset), { type: "application/json" });
  });
  const editorPage = el("div", { className: "cee-bk-page", id: "cee-bk-page-editor" }, [fxStart, fxEditor, modStart, modEditor]);

  /** Saves into this browser: over the own entry it came from, or as a new one. Returns its id. */
  function keep(ready, id, status) {
    if (!ready.ok) { toast(ready.reason, "error"); return null; }
    const list = ownList();
    const at = list.findIndex(o => o.id === id);
    const entry = { id: at >= 0 ? id : newId(), kind: ready.preset.kind, text: fxText(ready.preset) };
    if (at >= 0) list[at] = entry; else list.push(entry);
    if (!writeOwn(list)) { toast("Dieser Browser lässt die Seite nichts speichern. Lad den Effekt als Datei herunter.", "error"); return null; }
    renderMine();
    renderExport();
    const where = ready.preset.kind === "mod" ? "Meine Modulationen" : "Meine Effekte";
    status.textContent = `Gespeichert: „${ready.preset.name}“ steht unter ${where}. Unter Export legst du fest, auf welchen Platz er kommt.`;
    toast(`„${ready.preset.name}“ gespeichert, steht unter ${where}.`, "ok");
    return entry.id;
  }

  // ---- Meine Effekte / Modulationen ---------------------------------------------------
  const mine = el("ul", { className: "cee-catalog cee-bk-catalog", id: "cee-bk-mine" });
  const mineTitle = el("h2", { className: "cee-bk-title", textContent: "Meine Effekte" });
  const mineEmpty = el("p", { className: "muted", id: "cee-bk-mine-empty" });
  function renderMine() {
    const list = ownList().filter(o => (shelfKind === "mod") === (o.kind === "mod"));
    mineEmpty.hidden = list.length > 0;
    mineEmpty.textContent = shelfKind === "mod" ? "Noch keine Modulation gespeichert. Nimm eine aus dem Katalog oder bau eine im Editor." : "Noch kein Effekt gespeichert. Nimm einen aus dem Katalog oder bau einen im Editor.";
    mine.replaceChildren(...list.map(o => {
      const p = parse(o);
      const trash = el("button", { type: "button", className: "btn icon sm cee-bk-trash", title: `${p.name} löschen`, onclick: () => remove(o.id, p.name) }, [icon("trash")]);
      trash.setAttribute("aria-label", `${p.name} löschen`);
      return card(p, { onOpen: () => { if (o.kind === "mod") openMod(p, o.id); else openFx(p, o.id); page("editor"); }, extra: trash, id: `cee-bk-own-${o.id}` });
    }));
  }
  async function remove(id, name) {
    const yes = window.ui?.confirm ? await window.ui.confirm({ title: `„${name}“ löschen?`, text: "Er verschwindet aus diesem Browser und aus dem Export. Eine heruntergeladene Datei bleibt.", confirmLabel: "Löschen", danger: true }) : true;
    if (!yes) return;
    writeOwn(ownList().filter(o => o.id !== id));
    const slots = readSlots();
    for (const kind of Object.keys(slots)) for (const [slot, own] of Object.entries(slots[kind])) if (own === id) delete slots[kind][slot];
    writeSlots(slots);
    if (fxId === id) fxId = null;
    if (modId === id) modId = null;
    renderMine();
    renderExport();
    toast(`„${name}“ gelöscht.`, "ok");
  }
  const importInput = el("input", { type: "file", className: "cee-visually-hidden", id: "cee-bk-open", accept: ".e2fx,application/json" });
  importInput.addEventListener("change", async () => {
    const file = importInput.files?.[0];
    importInput.value = "";
    if (!file) return;
    const read = readFx(await file.text(), await loadUnits());
    if (!read.ok) { toast(`${file.name}: ${read.reason}`, "error"); return; }
    if (read.preset.kind === "mod") openMod(read.preset, null); else openFx(read.preset, null);
    page("editor");
    toast(`${file.name} geöffnet. Speichern legt ihn unter Meine Sachen ab.`, "ok");
  });
  const minePage = el("div", { className: "cee-bk-page", id: "cee-bk-page-mine" }, [
    mineTitle, mineEmpty, mine,
    el("div", { className: "actions" }, [el("label", { className: "btn", htmlFor: "cee-bk-open", textContent: ".e2fx-Datei öffnen" }), importInput]),
  ]);

  // ---- Export ------------------------------------------------------------------------
  // The collection for the card needs the firmware it is for: the records are made from that firmware's own.
  const cardNote = el("p", { className: "muted", id: "cee-bk-card-note" });
  const allInput = el("input", { type: "file", className: "ui-dropzone-input", id: "cee-bk-all", accept: ".all" });
  const allFiles = el("span", { className: "ui-dropzone-files" });
  const allDrop = el("label", { className: "ui-dropzone" }, [
    allInput,
    el("span", { className: "ui-dropzone-title" }, [el("span", { className: "ui-dropzone-drag", textContent: `${COLLECTION_FILE} hierher ziehen oder ` }), "auswählen"]),
    el("span", { className: "ui-dropzone-hint", textContent: `Die Datei von deiner Karte (${COLLECTION_FOLDER}/), um sie weiter zu bearbeiten. Ohne fängst du leer an.` }),
    allFiles,
  ]);
  allInput.addEventListener("change", async () => {
    const file = allInput.files?.[0];
    allInput.value = "";
    if (!file) return;
    const read = parseCollection(new Uint8Array(await file.arrayBuffer()));
    if (!read.ok) { toast(`${file.name}: ${read.reason}`, "error"); return; }
    await loadUnits();
    const list = ownList();
    const slots = readSlots();
    let added = 0;
    for (const entry of read.entries) {
      const fxRead = readFx(entry.text, units);
      if (!fxRead.ok) continue;
      const text = fxText(fxRead.preset);
      // A piece of the catalog stays the catalog's, it does not turn into an own one.
      const item = catalogOf(entry.kind).find(x => readFx(fxText(x), units).ok && fxText(readFx(fxText(x), units).preset) === text);
      if (item) { slots[entry.kind][entry.index + 1] = catalogId(item); continue; }
      let own = list.find(o => o.text === text);
      if (!own) { own = { id: newId(), kind: entry.kind, text }; list.push(own); added++; }
      slots[entry.kind][entry.index + 1] = own.id;
    }
    writeOwn(list);
    writeSlots(slots);
    allFiles.textContent = `${file.name}: ${read.entries.length} Einträge`;
    renderMine();
    renderExport();
    toast(`${file.name} geladen: ${read.entries.length} Einträge, ${added} neu unter Meine Sachen.`, "ok");
  });
  const exportLists = el("div", { className: "cee-bk-export", id: "cee-bk-export" });
  /** The catalog's pieces go on a place like own ones; the slot keeps "catalog:<name>" instead of an own id. */
  const catalogId = item => `catalog:${item.name}`;
  const catalogOf = kind => (kind === "mod" ? MOD_CATALOG : FX_CATALOG.filter(item => item.kind === kind));
  /** The .e2fx text of what a place holds, an own piece or one from the catalog; null when it is gone. */
  function textOf(id) {
    const item = [...FX_CATALOG, ...MOD_CATALOG].find(x => catalogId(x) === id);
    if (item) return fxText(item);
    return ownList().find(x => x.id === id)?.text ?? null;
  }

  /** The names of the firmware's own presets by slot, so a place is not overwritten by mistake; empty without a firmware. */
  let factoryShown = false;
  function factoryNames(kind) {
    try {
      return new Map((presets?.presets()?.list(kind) ?? []).map(x => [x.slot, x.name]));
    } catch {
      return new Map();
    }
  }
  function slotRow(kind, slot, own, slots, factory) {
    const assigned = slots[kind][slot] ?? "";
    const stock = factory.get(slot);
    const select = el("select", { className: "select", id: `cee-bk-slot-${kind}-${slot}` }, [
      el("option", { value: "", textContent: stock ? `Werks-Preset: ${stock}` : "Werks-Preset" }),
      own.length ? el("optgroup", { label: kind === "mod" ? "Meine Modulationen" : "Meine Effekte" }, own.map(o => el("option", { value: o.id, textContent: parse(o).name, selected: o.id === assigned }))) : null,
      el("optgroup", { label: "Katalog" }, catalogOf(kind).map(item => el("option", { value: catalogId(item), textContent: item.name, selected: catalogId(item) === assigned }))),
    ]);
    select.setAttribute("aria-label", `${KIND_WORD[kind]} Platz ${slot}`);
    select.addEventListener("change", () => {
      const next = readSlots();
      if (select.value) next[kind][slot] = select.value; else delete next[kind][slot];
      writeSlots(next);
      renderExport();
    });
    const clear = el("button", { type: "button", className: "btn icon sm", title: `Platz ${slot} leeren`, disabled: !assigned, onclick: () => {
      const next = readSlots();
      delete next[kind][slot];
      writeSlots(next);
      renderExport();
    } }, [icon("trash")]);
    clear.setAttribute("aria-label", `${KIND_WORD[kind]} Platz ${slot} leeren`);
    const grip = el("span", { className: "cee-bk-grip", title: "Ziehen, um mit einem anderen Platz zu tauschen" }, [icon("grip")]);
    const name = el("span", { className: "cee-bk-slot-factory", textContent: stock ?? "" });
    if (stock && assigned) name.title = `Ersetzt das Werks-Preset ${stock}`;
    const row = el("li", { className: `cee-bk-slot${assigned ? " cee-bk-slot-set" : ""}` }, [
      grip, el("span", { className: "cee-bk-slot-number", textContent: String(slot) }), name, select, clear,
    ]);
    row.dataset.kind = kind;
    row.dataset.slot = String(slot);
    // Dragged by the grip with pointer events (mouse, pen and touch alike); a drop swaps two places: A takes the
    // place of B and B the place of A.
    grip.addEventListener("pointerdown", e => {
      e.preventDefault();
      grip.setPointerCapture?.(e.pointerId);
      row.classList.add("cee-bk-dragging");
      let over = null;
      const under = ev => document.elementFromPoint(ev.clientX, ev.clientY)?.closest(`.cee-bk-slot[data-kind="${kind}"]`);
      const move = ev => {
        const next = under(ev);
        if (next === over) return;
        over?.classList.remove("cee-bk-drop");
        over = next && next !== row ? next : null;
        over?.classList.add("cee-bk-drop");
      };
      const up = ev => {
        grip.removeEventListener("pointermove", move);
        grip.removeEventListener("pointerup", up);
        grip.removeEventListener("pointercancel", up);
        row.classList.remove("cee-bk-dragging");
        over?.classList.remove("cee-bk-drop");
        const target = ev.type === "pointerup" ? under(ev) : null;
        if (target && target !== row) swap(kind, slot, Number(target.dataset.slot));
      };
      grip.addEventListener("pointermove", move);
      grip.addEventListener("pointerup", up);
      grip.addEventListener("pointercancel", up);
    });
    return row;
  }
  function swap(kind, a, b) {
    const slots = readSlots();
    const [x, y] = [slots[kind][a], slots[kind][b]];
    if (y) slots[kind][a] = y; else delete slots[kind][a];
    if (x) slots[kind][b] = x; else delete slots[kind][b];
    writeSlots(slots);
    renderExport();
  }
  function renderExport() {
    const list = ownList();
    const slots = readSlots();
    const kinds = shelfKind === "mod" ? [["mod", MOD_COUNT]] : [["ifx", SLOT_COUNT_FX], ["mfx", SLOT_COUNT_FX]];
    exportLists.replaceChildren(...kinds.map(([kind, count]) => {
      const own = list.filter(o => o.kind === kind);
      const factory = factoryNames(kind);
      return el("section", { className: "cee-bk-export-kind" }, [
        el("h3", { textContent: kind === "mod" ? "Modulationen" : `${KIND_WORD[kind]}e` }),
        el("ol", { className: "cee-bk-slots", id: `cee-bk-slots-${kind}` }, Array.from({ length: count }, (_, i) => slotRow(kind, i + 1, own, slots, factory))),
      ]);
    }));
  }
  async function exportAll() {
    const vsb = emulator?.firmware;
    const slots = readSlots();
    const wanted = Object.entries(slots).flatMap(([kind, map]) => Object.entries(map).map(([slot, id]) => ({ kind, slot: Number(slot), id })));
    if (!wanted.length) { toast("Leg zuerst unten mindestens einen Platz fest.", "error"); return; }
    if (!vsb) { toast("Dafür braucht die Seite deine Firmware: im Bereich Emulator die SYSTEM.VSB aufs Display ziehen. Sie bleibt auf deinem Rechner.", "error"); return; }
    const build = buildOf(vsb);
    if (build === "synth") { toast("Die Sammeldatei gibt es bisher nur für den roten Sampler.", "error"); return; }
    await loadUnits();
    const entries = [];
    for (const w of wanted) {
      const text = textOf(w.id);
      if (!text) continue;
      const read = readFx(text, units);
      const made = read.ok ? collectionEntry(read.preset, vsb, w.slot - 1, units) : read;
      if (!made.ok) { toast(`${read.preset?.name ?? "Ein Eintrag"}: ${made.reason}`, "error"); return; }
      entries.push(made.entry);
    }
    saveFile(buildCollection({ build, entries }), COLLECTION_FILE, { note: `Leg die Datei auf der Karte nach ${COLLECTION_FOLDER}/, beim nächsten Einschalten lädt BLECHTRIBE sie.` });
  }
  const exportButton = el("button", { type: "button", className: "btn cee-primary", id: "cee-bk-collection" }, [icon("download"), "Exportieren"]);
  exportButton.addEventListener("click", exportAll);
  const exportPage = el("div", { className: "cee-bk-page", id: "cee-bk-page-export" }, [
    el("h2", { className: "cee-bk-title", textContent: `${COLLECTION_FILE} für die Karte` }),
    el("p", { className: "muted", textContent: `Leg fest, welcher deiner Effekte auf welchem Platz der Electribe liegt. Ein Platz mit Werks-Preset bleibt, wie er ist. Zieh eine Zeile auf eine andere, um die beiden zu tauschen. Exportieren oben rechts speichert die Datei, sie gehört auf die Karte nach ${COLLECTION_FOLDER}/. Nimmst du sie weg oder hältst EXIT beim Einschalten, sind die alten Presets wieder da.` }),
    cardNote,
    allDrop,
    exportLists,
  ]);

  // ---- pages ------------------------------------------------------------------------
  const tabs = [["fx", "Effekte"], ["mod", "Modulationen"]].map(([id, text]) => {
    const input = el("input", { type: "radio", name: "cee-bk-shelf", value: id, onchange: () => shelf(id) });
    return el("label", { className: "ui-segmented-option", id: `cee-bk-tab-${id}` }, [input, el("span", { textContent: text })]);
  });
  const tabRow = el("div", { className: "ui-segmented cee-shelf-tabs", role: "radiogroup" }, tabs);
  tabRow.setAttribute("aria-label", "Effekte oder Modulationen");
  function shelf(id) {
    shelfKind = id;
    for (const t of tabs) { const input = t.querySelector("input"); input.checked = input.value === id; }
    fxCatalog.hidden = id !== "fx";
    modCatalog.hidden = id !== "mod";
    catalogTitle.textContent = id === "mod" ? "Modulationen" : "Effekte";
    mineTitle.textContent = id === "mod" ? "Meine Modulationen" : "Meine Effekte";
    const mineNav = document.querySelector("#cee-baukasten-page-mine span");
    if (mineNav) mineNav.textContent = mineTitle.textContent;
    renderEditor();
    renderMine();
    renderExport();
    updateTrail();
  }
  function renderEditor() {
    const isFx = shelfKind === "fx";
    fxStart.hidden = !isFx || !!fx;
    fxEditor.hidden = !isFx || !fx;
    modStart.hidden = isFx || !!mod;
    modEditor.hidden = isFx || !mod;
    switchRow();
  }
  /** Effekte or Modulationen is a choice for the catalog and a new piece; with one open it stays as it is. */
  function switchRow() {
    tabRow.hidden = shown === "detail" || (shown === "editor" && !!(shelfKind === "fx" ? fx : mod));
  }

  const PAGE_NODES = { catalog: catalogPage, editor: editorPage, mine: minePage, export: exportPage, detail: detailPage };
  const subPages = sub?.pages("baukasten", { id: "cee-baukasten-pages", label: "Bereiche des Baukastens", items: PAGES.map(([id, title, ic]) => ({ id, title, icon: ic })), pick: id => page(id) });
  function updateTrail() {
    if (!shown) return;
    const name = shelfKind === "mod" ? mod?.name : fx?.name;
    if (shown === "detail") { trail([{ text: "Katalog", go: () => page("catalog") }, view.name]); return; }
    trail(shown === "editor" ? ["Editor", ...(name ? [name] : [])] : [shown === "mine" ? mineTitle.textContent : PAGES.find(p => p[0] === shown)[1]]);
  }
  function page(id) {
    if (!PAGE_NODES[id]) id = "catalog";
    shown = id;
    for (const [key, node] of Object.entries(PAGE_NODES)) node.hidden = key !== id;
    subPages?.select(id === "detail" ? "catalog" : id);
    switchRow();
    navbar(id === "export" ? [exportButton] : []);
    updateTrail();
    root.closest(".cee-main")?.scrollTo?.({ top: 0 });
  }

  root.replaceChildren(el("div", { className: "cee-bk" }, [
    el("h1", { className: "ui-sr-only", textContent: "Baukasten" }),
    tabRow, catalogPage, detailPage, editorPage, minePage, exportPage,
  ]));
  shelf("fx");
  page("catalog");
  loadUnits().then(() => { renderMine(); renderExport(); }).catch(() => renderMine());
  return {
    /** The note on the export page follows the firmware in the emulator. */
    update() {
      cardNote.textContent = emulator?.firmware ? "Deine Firmware ist im Emulator geladen, die Datei kann gebaut werden. Neben jedem Platz steht das Werks-Preset, das dort liegt." : "Für diese Datei braucht die Seite deine Firmware: im Bereich Emulator die SYSTEM.VSB aufs Display ziehen. Sie bleibt auf deinem Rechner. Dann siehst du auch, welches Werks-Preset auf welchem Platz liegt.";
      // Runs every second (main.mjs): the slots are drawn again only when the firmware's presets come or go.
      const loaded = !!presets?.presets();
      if (units && loaded !== factoryShown) { factoryShown = loaded; renderExport(); }
    },
    page,
  };
}
