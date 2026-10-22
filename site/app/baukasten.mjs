/**
 * The Baukasten: effects and modulation types built from blocks, without knowing the firmware. A ready one from the
 * catalog or an empty one, a few choices, sliders, a name; out comes an .e2fx v2 file (src/fx-v2.mjs) and, with the
 * user's firmware in the emulator, the collection e2sFx.all for the card (src/fx-collection.mjs). Needs no firmware
 * until that last step.
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { parseUnits } from "../../src/units.mjs";
import { fxText, readFx, fxFileName } from "../../src/fx-v2.mjs";
import { buildCollection, collectionEntry, COLLECTION_FILE, COLLECTION_FOLDER, MOD_COUNT } from "../../src/fx-collection.mjs";
import { buildOf } from "../../src/firmware.mjs";
import { FX_CATALOG, MOD_CATALOG } from "../../data/fx/catalog.mjs";
import { GROUPS, unitLabel, paramLabel } from "../../data/fx/labels.mjs";

const OWN = "cee.baukasten";
const STAGES = { mfx: ["mfx"], ifx: ["ifx1", "ifx2"] };
const SOURCES = [[1, "LFO"], [0, "Hüllkurve"], [2, "Aus"]];
const TARGETS = [[3, "Filter"], [1, "Tonhöhe"], [2, "Oszillator"], [8, "Lautstärke"], [9, "Panorama"], [10, "Insert-Effekt"], [0, "Kein Ziel"]];
const CURVES = [[6, "Sinus", "M2 12c3-8 7-8 10 0s7 8 10 0"], [2, "Dreieck", "M2 18 7 6l5 12 5-12 5 12"], [1, "Rechteck", "M2 18V6h5v12h5V6h5v12h5"],
  [0, "Sägezahn", "M2 6l10 12V6l10 12"], [3, "Sample and Hold", "M2 14h4V8h4v8h4v-6h4v4h4"], [4, "Zufall", "M2 12l3-5 3 9 3-7 3 6 3-8 3 5"]];
const NS = "http://www.w3.org/2000/svg";

const readOwn = () => { try { return JSON.parse(localStorage.getItem(OWN) ?? "[]"); } catch { return []; } };
const writeOwn = list => { try { localStorage.setItem(OWN, JSON.stringify(list)); return true; } catch { return false; } };

function save(bytes, name, type = "application/octet-stream") {
  const url = URL.createObjectURL(new Blob([bytes], { type }));
  const a = el("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

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

/** A slider with its label and the value beside it. */
function slider(id, label, hint, min, max, value, change) {
  const input = el("input", { type: "range", className: "ui-range", id, min, max, value });
  const out = el("output", { className: "ui-range-value", htmlFor: id, textContent: String(value) });
  input.addEventListener("input", () => { out.textContent = input.value; change(Number(input.value)); });
  return el("div", { className: "ui-field cee-bk-slider" }, [
    el("label", { className: "ui-field-label", htmlFor: id }, [label, " ", out]),
    input,
    hint ? el("span", { className: "ui-field-help", textContent: hint }) : null,
  ]);
}

export function baukastenPage(root, { emulator = null } = {}) {
  let raw = null;            // data/units.json as it is, for the defaults of a block
  let units = null;
  let fx = null;             // the effect being built, .e2fx v2 values
  let mod = null;            // the modulation being built
  let slotFx = 100;
  let slotMod = 72;

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

  // ---- effects --------------------------------------------------------------------
  const fxCatalog = el("ul", { className: "cee-bk-catalog", id: "cee-bk-fx-catalog" }, FX_CATALOG.map(item => el("li", { className: "cee-bk-card" }, [
    el("h3", { textContent: item.name }),
    el("p", { className: "cee-bk-kind", textContent: item.kind === "mfx" ? "Master-Effekt, wirkt auf alles" : "Insert-Effekt, wirkt auf eine Spur" }),
    el("p", { textContent: item.description }),
    el("button", { type: "button", className: "btn cee-primary", textContent: "Öffnen und anpassen", onclick: () => { openFx(structuredClone(item)); builderFx.scrollIntoView?.({ block: "start" }); } }),
  ])));

  const where = choices("cee-bk-where", "Wo soll der Effekt wirken?", [["mfx", "Auf alles (Master-Effekt)"], ["ifx", "Auf eine Spur (Insert-Effekt)"]], kind => {
    if (fx?.kind === kind) return;
    openFx({ kind, name: fx?.name ?? "", stages: STAGES[kind].map(stage => ({ stage, unit: 0, unitName: "nofx_thru", params: {} })), map: [] });
  });
  const blocks = el("div", { className: "cee-bk-blocks", id: "cee-bk-blocks" });
  const fxName = el("input", { className: "input", id: "cee-bk-fx-name", type: "text", maxLength: 15, spellcheck: false, autocomplete: "off", placeholder: "zum Beispiel Mein Echo" });
  fxName.addEventListener("input", () => { if (fx) fx.name = fxName.value; });
  const fxSlot = el("input", { className: "input", id: "cee-bk-fx-slot", type: "number", min: 1, max: 100, value: slotFx });
  fxSlot.addEventListener("input", () => { slotFx = Number(fxSlot.value); });
  const fxSave = el("button", { type: "button", className: "btn cee-primary", id: "cee-bk-fx-save", textContent: "Speichern" });
  const fxDownload = el("button", { type: "button", className: "btn", id: "cee-bk-fx-download", textContent: "Als Datei herunterladen" });
  const fxSteps = el("div", { className: "cee-bk-steps", id: "cee-bk-fx-steps", hidden: true }, [
    el("h3", { textContent: "2. Bausteine" }),
    el("p", { className: "muted", textContent: "Ein Baustein ist ein Effekt wie Hall, Echo oder Filter. Wähl einen aus und stell ihn mit den Reglern ein." }),
    blocks,
    el("h3", { textContent: "3. Name und Speichern" }),
    el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: "cee-bk-fx-name", textContent: "Name (bis 15 Zeichen, so zeigt ihn das Display)" }), fxName]),
    el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: "cee-bk-fx-slot", textContent: "Platz auf deiner Electribe (1 bis 100)" }), fxSlot,
      el("span", { className: "ui-field-help", textContent: "Auf der Karte ersetzt der Effekt das Preset auf diesem Platz. Die Firmware selbst bleibt, wie sie ist." })]),
    el("div", { className: "actions" }, [fxSave, fxDownload]),
  ]);
  const builderFx = el("div", { className: "cee-bk-builder", id: "cee-bk-fx-builder" }, [
    el("h3", { textContent: "1. Wo soll der Effekt wirken?" }),
    where.node,
    fxSteps,
  ]);

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
    where.set(fx?.kind);
    fxSteps.hidden = !fx;
    if (!fx) return;
    fxName.value = fx.name;
    blocks.replaceChildren(...fx.stages.map((s, i) => {
      const kind = unitKind(s.stage);
      const [label, group] = s.unit ? unitLabel(kind, s.unit, s.unitName) : ["Noch leer", ""];
      const params = s.unit ? (units[kind].get(s.unit)?.params ?? []) : [];
      return el("div", { className: "cee-bk-block", id: `cee-bk-block-${i + 1}` }, [
        el("div", { className: "cee-bk-block-head" }, [
          el("h4", { textContent: fx.stages.length > 1 ? `Baustein ${i + 1}: ${label}` : label }),
          group ? el("span", { className: "cee-bk-group-name", textContent: group }) : null,
          el("div", { className: "actions" }, [
            el("button", { type: "button", className: `btn sm${s.unit ? "" : " cee-primary"}`, textContent: s.unit ? "Anderen Baustein wählen" : "Baustein wählen", onclick: () => choose(s.stage) }),
            s.unit && fx.stages.length > 1 ? el("button", { type: "button", className: "btn sm", textContent: "Entfernen", onclick: () => { Object.assign(s, { unit: 0, unitName: "nofx_thru", params: {} }); renderFx(); } }) : null,
          ]),
        ]),
        params.length ? el("div", { className: "cee-bk-params" }, params.map(p => {
          const value = s.params[p.name] ?? 0;
          return slider(`cee-bk-p-${i}-${p.name}`, paramLabel(p.name), p.name, 0, value > 127 ? 255 : 127, value, v => { s.params[p.name] = v; });
        })) : null,
      ]);
    }));
  }

  function openFx(preset) {
    fx = { kind: preset.kind, name: preset.name, stages: preset.stages.map(s => ({ ...s, params: { ...s.params } })), map: preset.map ?? [] };
    loadUnits().then(renderFx);
  }

  /** The effect as it stands, or why it is not ready. */
  function readyFx() {
    if (!fx) return { ok: false, reason: "Wähl zuerst, wo der Effekt wirken soll." };
    if (!fx.stages.some(s => s.unit)) return { ok: false, reason: "Wähl mindestens einen Baustein." };
    if (!fx.name.trim()) return { ok: false, reason: "Gib dem Effekt einen Namen." };
    if (!/^[\x20-\x7e]+$/.test(fx.name)) return { ok: false, reason: "Der Name darf nur Buchstaben ohne Umlaute, Ziffern und einfache Zeichen haben, das Display kennt keine anderen." };
    if (!(slotFx >= 1 && slotFx <= 100)) return { ok: false, reason: "Der Platz muss zwischen 1 und 100 liegen." };
    return { ok: true, preset: { ...fx, name: fx.name.trim() } };
  }
  fxSave.addEventListener("click", () => keep(readyFx(), slotFx));
  fxDownload.addEventListener("click", () => {
    const r = readyFx();
    if (!r.ok) { toast(r.reason, "error"); return; }
    save(fxText(r.preset), fxFileName(r.preset), "application/json");
  });

  // ---- modulations --------------------------------------------------------------------
  const modCatalog = el("ul", { className: "cee-bk-catalog", id: "cee-bk-mod-catalog" }, MOD_CATALOG.map(item => el("li", { className: "cee-bk-card" }, [
    el("h3", { textContent: item.name }),
    el("p", { textContent: item.description }),
    el("button", { type: "button", className: "btn cee-primary", textContent: "Öffnen und anpassen", onclick: () => { openMod(structuredClone(item)); builderMod.scrollIntoView?.({ block: "start" }); } }),
  ])));
  const modName = el("input", { className: "input", id: "cee-bk-mod-name", type: "text", maxLength: 16, spellcheck: false, autocomplete: "off" });
  modName.addEventListener("input", () => { if (mod) mod.name = modName.value; });
  const modSlot = el("input", { className: "input", id: "cee-bk-mod-slot", type: "number", min: 1, max: MOD_COUNT, value: slotMod });
  modSlot.addEventListener("input", () => { slotMod = Number(modSlot.value); });
  const curve = choices("cee-bk-curve", "Welle", CURVES.map(([v, label, path]) => [v, label, wave(path)]), v => { mod.curve = v; curve.set(v); });
  const modBody = el("div", { className: "cee-bk-mod-body", id: "cee-bk-mod-body" });
  const modSave = el("button", { type: "button", className: "btn cee-primary", id: "cee-bk-mod-save", textContent: "Speichern" });
  const modDownload = el("button", { type: "button", className: "btn", id: "cee-bk-mod-download", textContent: "Als Datei herunterladen" });
  const builderMod = el("div", { className: "cee-bk-builder", id: "cee-bk-mod-builder" }, [
    el("div", { className: "actions" }, [el("button", { type: "button", className: "btn", id: "cee-bk-mod-new", textContent: "Leere Modulation", onclick: () => openMod({ name: "", depth: 64, speed: 64, curve: 6, slots: Array.from({ length: 5 }, () => ({ source: 2, target: 0, lo: 0, hi: 0, follow: 0 })) }) })]),
    modBody,
  ]);

  function renderMod() {
    if (!mod) { modBody.replaceChildren(); return; }
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
        el("h4", { textContent: `Slot ${k + 1}` }),
        el("p", { className: "ui-field-label", textContent: "Was bewegt?" }), source.node,
        el("p", { className: "ui-field-label", textContent: "Was wird bewegt?" }), target.node,
        el("div", { className: "cee-bk-params" }, [
          slider(`cee-bk-lo-${k}`, "Stärke am Anfang", null, -128, 127, s.lo, v => { s.lo = v; }),
          slider(`cee-bk-hi-${k}`, "Stärke am Ende", null, -128, 127, s.hi, v => { s.hi = v; }),
        ]),
        el("label", { className: "cee-bk-check" }, [follow, " Stärke folgt dem Regler MOD. DEPTH"]),
      ]);
    });
    modBody.replaceChildren(
      el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: "cee-bk-mod-name", textContent: "Name (bis 16 Zeichen)" }), modName]),
      el("p", { className: "ui-field-label", textContent: "Welle des LFO" }), curve.node,
      el("div", { className: "cee-bk-params" }, [
        slider("cee-bk-depth", "Tiefe", "So weit dreht die Firmware MOD. DEPTH, wenn du diese Modulation wählst.", 0, 127, mod.depth, v => { mod.depth = v; }),
        slider("cee-bk-speed", "Tempo", "So weit dreht die Firmware MOD. SPEED, wenn du diese Modulation wählst.", 0, 127, mod.speed, v => { mod.speed = v; }),
      ]),
      el("p", { className: "muted", textContent: "Eine Modulation hat fünf Slots. Jeder nimmt eine Quelle (LFO oder Hüllkurve) und bewegt damit ein Ziel. Ein Slot mit der Quelle Aus tut nichts." }),
      ...slots,
      el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: "cee-bk-mod-slot", textContent: `Platz auf deiner Electribe (1 bis ${MOD_COUNT})` }), modSlot]),
      el("div", { className: "actions" }, [modSave, modDownload]),
    );
  }
  function openMod(preset) {
    mod = { kind: "mod", name: preset.name, depth: preset.depth, speed: preset.speed, curve: preset.curve, slots: preset.slots.map(s => ({ ...s })) };
    renderMod();
  }
  function readyMod() {
    if (!mod) return { ok: false, reason: "Öffne eine Modulation aus der Liste oder fang leer an." };
    if (!mod.name.trim() || !/^[\x20-\x7e]+$/.test(mod.name)) return { ok: false, reason: "Gib der Modulation einen Namen, ohne Umlaute." };
    if (!(slotMod >= 1 && slotMod <= MOD_COUNT)) return { ok: false, reason: `Der Platz muss zwischen 1 und ${MOD_COUNT} liegen.` };
    return { ok: true, preset: { ...mod, name: mod.name.trim() } };
  }
  modSave.addEventListener("click", () => keep(readyMod(), slotMod));
  modDownload.addEventListener("click", () => {
    const r = readyMod();
    if (!r.ok) { toast(r.reason, "error"); return; }
    save(fxText(r.preset), fxFileName(r.preset), "application/json");
  });

  // ---- what the user keeps --------------------------------------------------------------
  const mine = el("ul", { className: "cee-bk-catalog", id: "cee-bk-mine" });
  const mineEmpty = el("p", { className: "muted", id: "cee-bk-mine-empty", textContent: "Noch nichts gespeichert. Öffne oben einen fertigen Effekt oder bau einen neuen." });
  function keep(ready, slot) {
    if (!ready.ok) { toast(ready.reason, "error"); return; }
    const list = readOwn().filter(o => !(o.kind === ready.preset.kind && o.slot === slot));
    list.push({ kind: ready.preset.kind, slot, text: fxText(ready.preset) });
    if (!writeOwn(list)) { toast("Dieser Browser lässt die Seite nichts speichern. Lad den Effekt als Datei herunter.", "error"); return; }
    renderMine();
    toast(`„${ready.preset.name}“ gespeichert, Platz ${slot}.`, "ok");
  }
  function renderMine() {
    const list = readOwn();
    mineEmpty.hidden = list.length > 0;
    mine.replaceChildren(...list.map((o, i) => {
      const read = units ? readFx(o.text, units) : null;
      const p = read?.ok ? read.preset : JSON.parse(o.text);
      return el("li", { className: "cee-bk-card" }, [
        el("h3", { textContent: p.name }),
        el("p", { className: "cee-bk-kind", textContent: `${o.kind === "mod" ? "Modulation" : o.kind === "mfx" ? "Master-Effekt" : "Insert-Effekt"}, Platz ${o.slot}` }),
        el("div", { className: "actions" }, [
          el("button", { type: "button", className: "btn sm", textContent: "Bearbeiten", onclick: () => { if (o.kind === "mod") { slotMod = o.slot; modSlot.value = o.slot; shelf("mod"); openMod(p); } else { slotFx = o.slot; fxSlot.value = o.slot; shelf("fx"); openFx(p); } } }),
          el("button", { type: "button", className: "btn sm", textContent: "Herunterladen", onclick: () => save(o.text, fxFileName(p), "application/json") }),
          el("button", { type: "button", className: "btn sm", textContent: "Löschen", onclick: () => { writeOwn(readOwn().filter((_, k) => k !== i)); renderMine(); } }),
        ]),
      ]);
    }));
  }
  const importInput = el("input", { type: "file", className: "cee-visually-hidden", id: "cee-bk-open", accept: ".e2fx,application/json" });
  importInput.addEventListener("change", async () => {
    const file = importInput.files?.[0];
    importInput.value = "";
    if (!file) return;
    const read = readFx(await file.text(), await loadUnits());
    if (!read.ok) { toast(`${file.name}: ${read.reason}`, "error"); return; }
    if (read.preset.kind === "mod") { shelf("mod"); openMod(read.preset); } else { shelf("fx"); openFx(read.preset); }
    toast(`${file.name} geöffnet. Speichern legt ihn unter Meine Sachen ab.`, "ok");
  });

  // The collection for the card needs the firmware it is for: the records are made from that firmware's own.
  const cardNote = el("p", { className: "muted", id: "cee-bk-card-note" });
  const cardButton = el("button", { type: "button", className: "btn cee-primary", id: "cee-bk-collection", textContent: `${COLLECTION_FILE} für die Karte bauen` });
  cardButton.addEventListener("click", async () => {
    const vsb = emulator?.firmware;
    const list = readOwn();
    if (!list.length) { toast("Speichere zuerst mindestens einen Effekt oder eine Modulation.", "error"); return; }
    if (!vsb) { toast("Dafür braucht die Seite deine Firmware: im Bereich Emulator die SYSTEM.VSB aufs Display ziehen. Sie bleibt auf deinem Rechner.", "error"); return; }
    const build = buildOf(vsb);
    if (build === "synth") { toast("Die Sammeldatei gibt es bisher nur für den roten Sampler.", "error"); return; }
    await loadUnits();
    const entries = [];
    for (const o of list) {
      const read = readFx(o.text, units);
      const made = read.ok ? collectionEntry(read.preset, vsb, o.slot - 1, units) : read;
      if (!made.ok) { toast(`${read.preset?.name ?? "Ein Eintrag"}: ${made.reason}`, "error"); return; }
      entries.push(made.entry);
    }
    save(buildCollection({ build, entries }), COLLECTION_FILE);
    toast(`${COLLECTION_FILE} gespeichert. Leg die Datei auf der Karte nach ${COLLECTION_FOLDER}/, beim nächsten Einschalten lädt BLECHTRIBE sie.`, "ok");
  });

  // ---- page --------------------------------------------------------------------------
  const fxShelf = el("div", { className: "cee-bk-shelf", id: "cee-bk-fx" }, [
    el("h2", { className: "cee-bk-title", textContent: "Fertige Effekte" }), fxCatalog,
    el("h2", { className: "cee-bk-title", textContent: "Effekt bauen" }), builderFx,
  ]);
  const modShelf = el("div", { className: "cee-bk-shelf", id: "cee-bk-mod", hidden: true }, [
    el("h2", { className: "cee-bk-title", textContent: "Fertige Modulationen" }), modCatalog,
    el("h2", { className: "cee-bk-title", textContent: "Modulation bauen" }), builderMod,
  ]);
  const tabs = [["fx", "Effekte"], ["mod", "Modulationen"]].map(([id, text]) => {
    const b = el("button", { type: "button", className: "ui-segmented-option cee-shelf-tab", id: `cee-bk-tab-${id}`, textContent: text, onclick: () => shelf(id) });
    b.dataset.shelf = id;
    return b;
  });
  const tabRow = el("div", { className: "ui-segmented cee-shelf-tabs", role: "group" }, tabs);
  tabRow.setAttribute("aria-label", "Effekte oder Modulationen");
  function shelf(id) {
    for (const b of tabs) b.setAttribute("aria-pressed", String(b.dataset.shelf === id));
    fxShelf.hidden = id !== "fx";
    modShelf.hidden = id !== "mod";
  }
  root.replaceChildren(el("div", { className: "cee-bk" }, [
    el("h1", { className: "ui-sr-only", textContent: "Baukasten" }),
    el("p", { className: "cee-bk-lead", textContent: "Bau dir eigene Effekte und Modulationen aus Bausteinen. Nimm einen fertigen und dreh an den Reglern, oder fang leer an. Am Ende bekommst du eine Datei, die du teilen oder auf die Karte deiner Electribe legen kannst." }),
    tabRow, fxShelf, modShelf,
    el("h2", { className: "cee-bk-title", textContent: "Meine Sachen" }),
    mineEmpty, mine,
    el("div", { className: "actions" }, [el("label", { className: "btn", htmlFor: "cee-bk-open", textContent: ".e2fx-Datei öffnen" }), importInput]),
    el("h2", { className: "cee-bk-title", textContent: "Auf die Electribe" }),
    el("p", { textContent: `Alles unter Meine Sachen kommt in eine Datei, ${COLLECTION_FILE}. Auf der Karte unter ${COLLECTION_FOLDER}/ lädt BLECHTRIBE sie bei jedem Einschalten. Sie ändert nichts an der Firmware: nimmst du die Datei weg oder hältst EXIT beim Einschalten, sind die alten Presets wieder da.` }),
    cardNote,
    el("div", { className: "actions" }, [cardButton]),
  ]));
  shelf("fx");
  loadUnits().then(renderMine).catch(() => renderMine());
  return {
    /** The note under the card button follows the firmware in the emulator. */
    update() { cardNote.textContent = emulator?.firmware ? "Deine Firmware ist im Emulator geladen, die Datei kann gebaut werden." : "Für diese Datei braucht die Seite deine Firmware: im Bereich Emulator die SYSTEM.VSB aufs Display ziehen."; },
  };
}
