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
import { parseUnits } from "../../src/units.mjs";
import { fxText, readFx, fxFileName, fxToRecord } from "../../src/fx-v2.mjs";
import { buildCollection, parseCollection, collectionEntry, COLLECTION_FILE, COLLECTION_FOLDER, MOD_COUNT } from "../../src/fx-collection.mjs";
import { buildOf } from "../../src/firmware.mjs";
import { FX_CATALOG, MOD_CATALOG } from "../../data/fx/catalog.mjs";
import { GROUPS, MAIN, unitLabel, paramLabel } from "../../data/fx/labels.mjs";

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

/** A slider with its label and a number box beside it: drag it or type the value. */
function slider(id, label, hint, min, max, value, change) {
  const input = el("input", { type: "range", className: "ui-range", id, min, max, value });
  const box = el("input", { type: "number", className: "input cee-bk-number", id: `${id}-value`, min, max, value });
  box.setAttribute("aria-label", `${label}, Wert`);
  const fromRange = () => { box.value = input.value; change(Number(input.value)); };
  const fromBox = () => {
    const v = Math.max(min, Math.min(max, Math.round(Number(box.value))));
    if (!Number.isFinite(v)) return;
    input.value = String(v);
    window.ui?.syncRange(input);
    change(v);
  };
  input.addEventListener("input", fromRange);
  input.addEventListener("change", fromRange);
  box.addEventListener("input", fromBox);
  box.addEventListener("change", () => { fromBox(); box.value = input.value; });
  window.ui?.syncRange(input);
  return el("div", { className: "ui-field cee-bk-slider" }, [
    el("label", { className: "ui-field-label", htmlFor: id, textContent: label }),
    el("div", { className: "cee-bk-slider-row" }, [input, box]),
    hint ? el("span", { className: "ui-field-help", textContent: hint }) : null,
  ]);
}

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

  /** A card like the plugin catalog's: the whole card opens it; `extra` sits on top of the card (the trash can). */
  function card(preset, { creator, onOpen, extra = null, id = null }) {
    return el("li", { className: "cee-catalog-card cee-bk-card", id }, [
      el("h3", {}, el("button", { type: "button", className: "cee-catalog-open", textContent: preset.name, onclick: onOpen })),
      el("p", { className: "cee-bk-meta" }, [el("span", { className: "cee-catalog-category", textContent: tagOf(preset) }), creator ? el("span", { className: "muted", textContent: `von ${creator}` }) : null]),
      el("p", { className: "cee-bk-kind muted", textContent: KIND_WORD[preset.kind] }),
      preset.description ? el("p", { textContent: preset.description }) : null,
      extra,
    ]);
  }

  // ---- Katalog ----------------------------------------------------------------------
  const fxCatalog = el("ul", { className: "cee-catalog cee-bk-catalog", id: "cee-bk-fx-catalog" }, FX_CATALOG.map(item => card(item, { creator: item.creator, onOpen: () => { openFx(structuredClone(item), null); page("editor"); } })));
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
  const fxEditor = el("div", { className: "cee-bk-builder", id: "cee-bk-fx-builder", hidden: true }, [
    el("div", { className: "cee-bk-head" }, [fxName, fxKind]),
    el("p", { className: "muted", textContent: "Ein Baustein ist ein einzelner Effekt wie Hall, Echo oder Filter. Ein Insert-Effekt kann zwei hintereinander haben, der zweite darf leer bleiben. Anhören kannst du ihn erst an der Electribe." }),
    blocks,
    el("div", { className: "actions" }, [fxSave, fxDownload, fxLoad, fxRetarget]),
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
    paletteBody.replaceChildren(...GROUPS.map(group => {
      const here = all.filter(u => unitLabel(kind, u.id, u.unit)[1] === group);
      if (!here.length) return null;
      return el("section", { className: "cee-bk-group" }, [
        el("h3", { textContent: group }),
        el("div", { className: "cee-bk-units" }, here.map(u => el("button", { type: "button", className: "btn cee-bk-unit", onclick: () => {
          const s = fx.stages.find(x => x.stage === stage);
          Object.assign(s, { unit: u.id, unitName: u.unit, params: defaultsOf(kind, u.id) });
          palette.close();
          renderFx();
        } }, [el("strong", { textContent: unitLabel(kind, u.id, u.unit)[0] }), el("span", { className: "muted", textContent: u.unit })]))),
      ]);
    }).filter(Boolean));
    if (window.ui?.openDialog) window.ui.openDialog(palette); else palette.showModal?.();
  }

  function renderFx() {
    fxEditor.hidden = !fx;
    fxStart.hidden = !!fx;
    if (!fx) return;
    fxName.value = fx.name;
    fxKind.textContent = KIND_WORD[fx.kind];
    blocks.replaceChildren(...fx.stages.map((s, i) => {
      const kind = unitKind(s.stage);
      const [label, group] = s.unit ? unitLabel(kind, s.unit, s.unitName) : ["Noch leer", ""];
      const params = s.unit ? (units[kind].get(s.unit)?.params ?? []) : [];
      const one = p => {
        const value = s.params[p.name] ?? 0;
        return slider(`cee-bk-p-${i}-${p.name}`, paramLabel(p.name), p.name, 0, value > 127 ? 255 : 127, value, v => { s.params[p.name] = v; });
      };
      // The parameters that shape the sound most come first, the rest under their own heading.
      const shownFirst = params.some(p => MAIN.has(p.name)) ? p => MAIN.has(p.name) : () => true;
      const main = params.filter(shownFirst);
      const more = params.filter(p => !shownFirst(p));
      return el("div", { className: "cee-bk-block", id: `cee-bk-block-${i + 1}` }, [
        el("div", { className: "cee-bk-block-head" }, [
          el("h3", { textContent: fx.stages.length > 1 ? `Baustein ${i + 1}: ${label}` : label }),
          group ? el("span", { className: "cee-bk-group-name", textContent: group }) : null,
          el("div", { className: "actions" }, [
            el("button", { type: "button", className: `btn sm${s.unit ? "" : " cee-primary"}`, textContent: s.unit ? "Anderen Baustein wählen" : "Baustein wählen", onclick: () => choose(s.stage) }),
            s.unit && fx.stages.length > 1 ? el("button", { type: "button", className: "btn sm", textContent: "Entfernen", onclick: () => { Object.assign(s, { unit: 0, unitName: "nofx_thru", params: {} }); renderFx(); } }) : null,
          ]),
        ]),
        main.length ? el("div", { className: "cee-bk-params" }, main.map(one)) : null,
        more.length ? el("h4", { className: "cee-bk-more", textContent: "Erweiterte Einstellungen" }) : null,
        more.length ? el("div", { className: "cee-bk-params" }, more.map(one)) : null,
      ]);
    }));
  }

  function openFx(preset, id) {
    fx = { kind: preset.kind, name: preset.name, stages: preset.stages.map(s => ({ ...s, params: { ...s.params } })), map: preset.map ?? [] };
    fxId = id;
    fxTarget = null;
    showTarget();
    fxSaved.textContent = "";
    shelf("fx");
    loadUnits().then(() => { renderFx(); updateTrail(); });
  }

  /** The effect as it stands, or why it is not ready. */
  function readyFx() {
    if (!fx) return { ok: false, reason: "Leg zuerst einen Effekt an." };
    if (!fx.stages.some(s => s.unit)) return { ok: false, reason: "Wähl mindestens einen Baustein." };
    if (!fx.name.trim()) return { ok: false, reason: "Gib dem Effekt oben einen Namen." };
    if (!/^[\x20-\x7e]+$/.test(fx.name)) return { ok: false, reason: "Der Name darf nur Buchstaben ohne Umlaute, Ziffern und einfache Zeichen haben, das Display kennt keine anderen." };
    return { ok: true, preset: { ...fx, name: fx.name.trim() } };
  }
  fxSave.addEventListener("click", () => { const id = keep(readyFx(), fxId, fxSaved); if (id) fxId = id; });
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
  function pickSlot() {
    const list = presets?.presets()?.list(fx.kind);
    if (!list?.length) { toast("Dafür braucht die Seite deine Firmware und den laufenden Emulator oder die verbundene Electribe: im Bereich Emulator die SYSTEM.VSB aufs Display ziehen.", "error"); return; }
    slotTitle.textContent = `Welchen ${KIND_WORD[fx.kind]} überschreiben?`;
    slotBody.replaceChildren(
      el("p", { className: "muted", textContent: "Der gewählte Platz bekommt deinen Effekt, live im Arbeitsspeicher. Nach dem Ausschalten ist das alte Preset wieder da." }),
      el("div", { className: "cee-bk-units" }, list.map(({ slot, name }) => el("button", { type: "button", className: "btn cee-bk-unit", onclick: () => { slotDialog.close(); loadTo({ kind: fx.kind, slot }); } }, [
        el("strong", { textContent: `${slot}` }), el("span", { className: "muted", textContent: name }),
      ]))),
    );
    if (window.ui?.openDialog) window.ui.openDialog(slotDialog); else slotDialog.showModal?.();
  }
  async function loadTo(target) {
    const r = readyFx();
    if (!r.ok) { toast(r.reason, "error"); return; }
    await loadUnits();
    fxLoad.disabled = true;
    try {
      const res = await presets.writeRecord(target.kind, target.slot, (before, records) => fxToRecord(r.preset, before, records, units));
      if (!res.ok) { if (res.reason) toast(res.reason, "error"); return; }
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
    el("div", { className: "cee-bk-head" }, [modName, el("p", { className: "cee-bk-kind muted", textContent: KIND_WORD.mod })]),
    modBody,
    el("div", { className: "actions" }, [modSave, modDownload]),
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
          slider(`cee-bk-lo-${k}`, "Stärke am Anfang", null, -128, 127, s.lo, v => { s.lo = v; }),
          slider(`cee-bk-hi-${k}`, "Stärke am Ende", null, -128, 127, s.hi, v => { s.hi = v; }),
        ]),
        el("label", { className: "cee-bk-check" }, [follow, " Stärke folgt dem Regler MOD. DEPTH"]),
        el("p", { className: "ui-field-help", textContent: "Ein: mit dem Regler MOD. DEPTH am Gerät machst du diesen Slot stärker oder schwächer. Aus: er wirkt immer gleich stark." }),
      ]);
    });
    modBody.replaceChildren(
      el("p", { className: "ui-field-label", textContent: "Welle des LFO" }), curve.node,
      el("div", { className: "cee-bk-params" }, [
        slider("cee-bk-depth", "Tiefe", "So weit dreht die Firmware MOD. DEPTH, wenn du diese Modulation wählst.", 0, 127, mod.depth, v => { mod.depth = v; }),
        slider("cee-bk-speed", "Tempo", "So weit dreht die Firmware MOD. SPEED, wenn du diese Modulation wählst.", 0, 127, mod.speed, v => { mod.speed = v; }),
      ]),
      el("p", { className: "muted", textContent: "Eine Modulation hat fünf Slots. Jeder nimmt eine Quelle (LFO oder Hüllkurve) und bewegt damit ein Ziel. Ein Slot mit der Quelle Aus tut nichts." }),
      ...slots,
    );
  }
  function openMod(preset, id) {
    mod = { kind: "mod", name: preset.name, depth: preset.depth, speed: preset.speed, curve: preset.curve, slots: preset.slots.map(s => ({ ...s })) };
    modId = id;
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
  modSave.addEventListener("click", () => { const id = keep(readyMod(), modId, modSaved); if (id) modId = id; });
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
  function slotRow(kind, slot, own, slots) {
    const assigned = slots[kind][slot] ?? "";
    const select = el("select", { className: "select", id: `cee-bk-slot-${kind}-${slot}` }, [
      el("option", { value: "", textContent: "Werks-Preset" }),
      ...own.map(o => el("option", { value: o.id, textContent: parse(o).name, selected: o.id === assigned })),
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
    const row = el("li", { className: `cee-bk-slot${assigned ? " cee-bk-slot-set" : ""}` }, [
      grip, el("span", { className: "cee-bk-slot-number", textContent: String(slot) }), select, clear,
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
      return el("section", { className: "cee-bk-export-kind" }, [
        el("h3", { textContent: kind === "mod" ? "Modulationen" : `${KIND_WORD[kind]}e` }),
        el("ol", { className: "cee-bk-slots", id: `cee-bk-slots-${kind}` }, Array.from({ length: count }, (_, i) => slotRow(kind, i + 1, own, slots))),
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
    const list = ownList();
    const entries = [];
    for (const w of wanted) {
      const o = list.find(x => x.id === w.id);
      if (!o) continue;
      const read = readFx(o.text, units);
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
  }

  const PAGE_NODES = { catalog: catalogPage, editor: editorPage, mine: minePage, export: exportPage };
  const subPages = sub?.pages("baukasten", { id: "cee-baukasten-pages", label: "Bereiche des Baukastens", items: PAGES.map(([id, title, ic]) => ({ id, title, icon: ic })), pick: id => page(id) });
  function updateTrail() {
    if (!shown) return;
    const name = shelfKind === "mod" ? mod?.name : fx?.name;
    trail(shown === "editor" ? ["Editor", ...(name ? [name] : [])] : [shown === "mine" ? mineTitle.textContent : PAGES.find(p => p[0] === shown)[1]]);
  }
  function page(id) {
    if (!PAGE_NODES[id]) id = "catalog";
    shown = id;
    for (const [key, node] of Object.entries(PAGE_NODES)) node.hidden = key !== id;
    subPages?.select(id);
    navbar(id === "export" ? [exportButton] : []);
    updateTrail();
    root.closest(".cee-main")?.scrollTo?.({ top: 0 });
  }

  root.replaceChildren(el("div", { className: "cee-bk" }, [
    el("h1", { className: "ui-sr-only", textContent: "Baukasten" }),
    tabRow, catalogPage, editorPage, minePage, exportPage,
  ]));
  shelf("fx");
  page("catalog");
  loadUnits().then(() => { renderMine(); renderExport(); }).catch(() => renderMine());
  return {
    /** The note on the export page follows the firmware in the emulator. */
    update() { cardNote.textContent = emulator?.firmware ? "Deine Firmware ist im Emulator geladen, die Datei kann gebaut werden." : "Für diese Datei braucht die Seite deine Firmware: im Bereich Emulator die SYSTEM.VSB aufs Display ziehen. Sie bleibt auf deinem Rechner."; },
    page,
  };
}
