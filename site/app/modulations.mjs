/** The Modulationen page: 72 modulation types of the loaded firmware, a firmware copy after the emulator check. Logic: src/modtable.mjs, src/export.mjs. */
import { el, control } from "./fields.mjs";
import { identify, firmwareAdvice } from "../../src/firmware.mjs";
import { field, describe } from "../../src/map/index.mjs";
import { converter } from "../../src/map/convert.mjs";
import { locateModTable, readModType, readModTypes, writeModType, MOD_FIELDS, SLOT_FIELDS, SLOT_COUNT, MOD_COUNT } from "../../src/modtable.mjs";
import { lintModType, slotActive, TARGETS_KNOWN, TARGETS_UNCLEAR } from "../../src/modtable-rules.mjs";
import { exportModTypes } from "../../src/export.mjs";
import { checkName, checkDetail } from "../../src/patcher.mjs";
import { toast } from "./toast.mjs";
import { saveFile } from "./save-file.mjs";

const TARGET = field("modType.target");

// Not the map's notes: those are for people who work on the map.
const FIELD_TEXT = {
  name: { label: "Name", note: "Bis zu 16 Zeichen, die das Display zeigen kann." },
  depth: {
    label: "Vorgabe-Tiefe (MOD. DEPTH)",
    note: "Diesen Wert setzt die Firmware auf MOD. DEPTH, wenn du die Art mit MOD. TYPE wählst. Danach kannst du daran drehen.",
  },
  speed: {
    label: "Vorgabe-Speed (MOD. SPEED)",
    note: "Diesen Wert setzt die Firmware auf MOD. SPEED, wenn du die Art mit MOD. TYPE wählst. Danach kannst du daran drehen.",
  },
  curve: {
    label: "Kurve",
    note: "Die Wellenform der LFO-Einheit. Sie wirkt nur bei Slots mit der Quelle LFO. Im Emulator gemessen, nicht gehört.",
  },
};

const SLOT_TEXT = {
  source: "Quelle",
  target: "Ziel",
  lo: { label: "Stärke von" },
  hi: { label: "Stärke bis" },
  follow: { label: "Tiefe folgt MOD. DEPTH" },
};

const pill = (tone, word) => {
  const p = el("span", { className: "cee-status", textContent: word });
  p.dataset.tone = tone;
  return p;
};

export function modulationsPage(root, { emulator }) {
  const state = { original: null, bytes: null, file: 0, place: null, index: 0 };
  let passed = null;

  const idle = el("p", { className: "muted", id: "cee-mod-idle", textContent: "Wähle im Bereich Emulator die Firmware (VSB). Die Modulationsarten liest dieser Bereich aus der geladenen Datei." });
  const intro = el("div", { className: "cee-mod-intro", id: "cee-mod-intro", hidden: true }, [
    el("p", { id: "cee-mod-measured", textContent: "Im Emulator gemessen, nicht gehört. Wirkt erst mit der neuen Firmware." }),
  ]);
  const list = el("ul", { className: "ui-list cee-pattern-list", id: "cee-mod-list" });
  const side = el("aside", { className: "ui-split-side", id: "cee-mod-side" }, [el("h2", { className: "ui-section-title", textContent: "Modulationsarten" }), list]);
  const form = el("div", { className: "cee-mod-form", id: "cee-mod-form" });
  const toggle = el("button", { type: "button", className: "btn ui-split-toggle", textContent: "Arten" });
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-controls", "cee-mod-side");
  const split = el("div", { className: "ui-split", id: "cee-mod-split", hidden: true }, [toggle, side, el("div", { className: "ui-split-main" }, [form])]);

  const count = el("span", { className: "muted", id: "cee-mod-count", role: "status" });
  const warnings = el("span", { className: "muted", id: "cee-mod-warnings" });
  const run = el("button", { type: "button", className: "btn cee-primary", id: "cee-mod-run", textContent: "Im Emulator prüfen", disabled: true });
  const reset = el("button", { type: "button", className: "btn", id: "cee-mod-reset-all", textContent: "Alles zurücksetzen", disabled: true });
  const download = el("button", { type: "button", className: "btn cee-primary", id: "cee-mod-download", textContent: "SYSTEM.VSB herunterladen", hidden: true });
  const bar = el("div", { className: "ui-progress", id: "cee-mod-bar", hidden: true });
  const note = el("p", { className: "muted", id: "cee-mod-note", role: "status", hidden: true });
  const checkList = el("ul", { className: "ui-list", id: "cee-mod-checks" });
  const checks = el("details", { className: "ui-details", id: "cee-mod-details", hidden: true }, [el("summary", { id: "cee-mod-details-title" }), el("div", { className: "ui-details-body" }, [checkList])]);
  const actions = el("section", { className: "cee-mod-actions", id: "cee-mod-actions", hidden: true }, [
    el("div", { className: "actions" }, [count, warnings, reset, run, download]), bar, note, checks,
  ]);

  root.replaceChildren(idle, intro, split, actions);

  const value = (bytes, i) => readModType(bytes, state.file, i);
  const flat = t => [t.name, t.depth, t.speed, t.curve, ...t.slots.flatMap(sl => Object.keys(SLOT_FIELDS).map(k => sl[k]))];
  const isChanged = i => {
    const now = flat(value(state.bytes, i));
    const was = flat(value(state.original, i));
    return now.some((v, k) => v !== was[k]);
  };
  const changedTypes = () => Array.from({ length: MOD_COUNT }, (_, i) => i).filter(isChanged);
  const hintsOf = i => lintModType(value(state.bytes, i), value(state.original, i));
  let redraw = () => {};

  function drawItem(i) {
    const item = list.children[i].firstChild;
    item.querySelector(".ui-truncate").textContent = value(state.bytes, i).name;
    item.querySelector(".cee-mod-changed").hidden = !isChanged(i);
  }

  function status() {
    const n = changedTypes().length;
    count.textContent = n ? `${n} ${n === 1 ? "Art" : "Arten"} geändert` : "Nichts geändert";
    const hints = changedTypes().reduce((sum, i) => sum + hintsOf(i).length, 0);
    warnings.textContent = hints ? `${hints} ${hints === 1 ? "Hinweis" : "Hinweise"} zu den Änderungen` : "";
    reset.disabled = !n;
    run.disabled = !n;
  }

  function edited(i) {
    passed = null;
    download.hidden = true;
    checks.hidden = true;
    note.hidden = true;
    drawItem(i);
    status();
    redraw();
  }

  let sel = 0;
  /** A choice as a select; `groups` are [label or null, options] so that values with an open meaning sit apart. */
  function pick(label, groups, read, write) {
    const id = `cee-mod-pick-${++sel}`;
    const select = el("select", { className: "select", id });
    for (const [group, options] of groups) {
      const parent = group ? el("optgroup", { label: group }) : select;
      for (const o of options) parent.append(el("option", { value: String(o.raw), textContent: o.label }));
      if (group) select.append(parent);
    }
    const extra = el("option", { disabled: true, hidden: true });
    select.append(extra);
    select.addEventListener("change", () => write(Number(select.value)));
    const refresh = () => {
      const raw = read();
      const known = groups.some(([, options]) => options.some(o => o.raw === raw));
      extra.hidden = known;
      extra.value = String(raw);
      extra.textContent = `Wert ${raw}, nicht gemessen`;
      select.value = String(raw);
    };
    refresh();
    return el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: id, textContent: label }), select]);
  }

  const sourceChoices = converter("modSlotSource").choices;
  const targetChoices = converter("modSlotTarget").choices;
  const targetGroups = [
    [null, [0, ...TARGETS_KNOWN].map(raw => targetChoices[raw])],
    ["Expertenwerte, Wirkung am Klang unklar", TARGETS_UNCLEAR.map(raw => ({ raw, label: `Code ${raw}, Wirkung unklar` }))],
  ];

  function slotState(slot) {
    if (slotActive(slot)) return "";
    if (slot.source > 1) return "Ohne Wirkung: die Quelle ist aus.";
    if (slot.target === 0) return "Ohne Wirkung: kein Ziel.";
    return "Ohne Wirkung: die Stärke ist 0.";
  }

  function slotGroup(i, k) {
    const slot = () => value(state.bytes, i).slots[k];
    const set = key => raw => { writeModType(state.bytes, state.file, i, { slots: Object.assign([], { [k]: { [key]: raw } }) }); edited(i); };
    const stateLine = el("p", { className: "ui-field-help cee-mod-slot-state", id: `cee-mod-slot-${k}-state` });
    const refreshState = () => { stateLine.textContent = slotState(slot()); };
    refreshState();
    const named = key => ({ ...SLOT_FIELDS[key], label: { de: SLOT_TEXT[key].label, en: SLOT_TEXT[key].label }, note: null });
    const numeric = key => control(named(key), () => slot()[key], set(key)).node;
    const title = el("h5", { id: `cee-mod-slot-${k}-title`, textContent: `Slot ${k + 1}` });
    const group = el("div", { className: "cee-group cee-mod-slot", id: `cee-mod-slot-${k}` }, [
      title, stateLine,
      el("div", { className: "cee-grid" }, [
        pick(SLOT_TEXT.source, [[null, sourceChoices]], () => slot().source, set("source")),
        pick(SLOT_TEXT.target, targetGroups, () => slot().target, set("target")),
        numeric("lo"), numeric("hi"), numeric("follow"),
      ]),
    ]);
    group.setAttribute("role", "group");
    group.setAttribute("aria-labelledby", title.id);
    return { node: group, refreshState };
  }

  function openType(i) {
    state.index = i;
    for (const b of list.querySelectorAll("button")) b.setAttribute("aria-current", String(Number(b.dataset.n) === i));
    const set = key => raw => { writeModType(state.bytes, state.file, i, { [key]: raw }); edited(i); };
    const fields = Object.keys(MOD_FIELDS).map(key => {
      const f = { ...MOD_FIELDS[key], label: { de: FIELD_TEXT[key].label, en: FIELD_TEXT[key].label }, note: FIELD_TEXT[key].note };
      return control(f, () => value(state.bytes, i)[key], set(key)).node;
    });
    const target = value(state.bytes, i).target;
    const label = el("div", { className: "ui-field", id: "cee-mod-target" }, [
      el("span", { className: "ui-field-label", textContent: "Ziel (nur Etikett)" }),
      el("span", { className: "muted", id: "cee-mod-target-value", textContent: describe(TARGET, target)?.text ?? String(target) }),
      el("p", { className: "ui-field-help", textContent: "Die Firmware liest dieses Byte nie, es ist nur ein Etikett. Was eine Art moduliert, steht in den Slots unten." }),
    ]);
    fields.splice(1, 0, label);
    const slots = Array.from({ length: SLOT_COUNT }, (_, k) => slotGroup(i, k));
    const hints = el("ul", { className: "ui-list", id: "cee-mod-hints" });
    const hintBox = el("div", { className: "cee-group", id: "cee-mod-hint-box", hidden: true }, [el("h4", { textContent: "Hinweise zu dieser Art" }), hints]);
    redraw = () => {
      slots.forEach(sl => sl.refreshState());
      const found = hintsOf(i);
      hints.replaceChildren(...found.map(h => el("li", { className: "ui-row" }, [pill("warn", "Hinweis"), el("span", { className: "ui-break", textContent: ` ${h.message}` })])));
      hintBox.hidden = !found.length;
    };
    const back = el("button", { type: "button", className: "btn sm", id: "cee-mod-reset", textContent: "Diese Art zurücksetzen" });
    back.addEventListener("click", () => {
      const { target: _label,...was } = value(state.original, i);
      writeModType(state.bytes, state.file, i, was);
      edited(i);
      openType(i);
    });
    form.replaceChildren(
      el("h3", { textContent: `Art ${i + 1}` }),
      el("div", { className: "cee-grid" }, fields),
      el("div", { className: "cee-group" }, [
        el("h4", { textContent: "Was die Art moduliert" }),
        el("p", { className: "ui-field-help", textContent: "Jeder Slot ist eine Modulation: eine Quelle, ein Ziel und eine Stärke. Mehrere Slots mit demselben Ziel addieren sich. Die Stärke läuft von -63 bis 63: \"von\" gilt bei MOD. DEPTH 0, \"bis\" bei 127, mit \"bis\" auf 0 oder darunter kehrt sich die Wirkung um. Ist \"Tiefe folgt MOD. DEPTH\" aus, bleibt die Stärke bei der Vorgabe-Tiefe der Art und MOD. DEPTH ändert sie nicht." }),
      ]),
      ...slots.map(sl => sl.node),
      hintBox,
      el("div", { className: "actions" }, [back]),
    );
    redraw();
  }

  function build() {
    list.replaceChildren(...Array.from({ length: MOD_COUNT }, (_, i) => {
      const changed = pill("info", "geändert");
      changed.classList.add("cee-mod-changed");
      changed.hidden = true;
      const b = el("button", { type: "button", className: "cee-pattern-item" }, [
        el("span", { className: "cee-pattern-num", textContent: String(i + 1) }),
        el("span", { className: "ui-truncate" }),
        changed,
      ]);
      b.dataset.n = String(i);
      return el("li", {}, b);
    }));
    for (let i = 0; i < MOD_COUNT; i++) drawItem(i);
  }

  list.addEventListener("click", e => {
    const b = e.target.closest("button[data-n]");
    if (b) openType(Number(b.dataset.n));
  });

  reset.addEventListener("click", () => {
    state.bytes = Uint8Array.from(state.original);
    passed = null;
    build();
    openType(state.index);
    edited(state.index);
  });

  function progress(text) {
    bar.hidden = false;
    window.ui?.setProgress(bar, null, text);
    note.hidden = false;
    note.dataset.tone = "";
    note.textContent = text;
  }

  run.addEventListener("click", async () => {
    run.disabled = reset.disabled = true;
    passed = null;
    download.hidden = true;
    checks.hidden = true;
    try {
      const res = await exportModTypes(state.original, readModTypes(state.bytes, state.file));
      if (!res.ok) throw new Error(res.reasons.join(" "));
      progress("Der Emulator startet die Kopie auf allen Startwegen, das dauert ein paar Minuten.");
      const report = await emulator.check(state.original, res.bytes, res.allow, []);
      checkList.replaceChildren(...report.checks.map(c => el("li", { className: "ui-row" }, [
        pill(c.ok ? "ok" : "error", c.ok ? "bestanden" : "nicht bestanden"), el("strong", { textContent: ` ${checkName(c.id)}` }), el("span", { className: "ui-break muted", textContent: ` ${checkDetail(c.detail)}` }),
      ])));
      document.getElementById("cee-mod-details-title").textContent = `Alle Prüfungen des Emulators (${report.checks.length})`;
      checks.hidden = false;
      const good = report.checks.filter(c => c.ok).length;
      note.hidden = true;
      toast(report.ok ? `Geprüft, alles in Ordnung. Du kannst die Datei jetzt speichern.` : `Die Prüfung hat ${report.checks.length - good} Fehler gefunden. Diese Änderung lässt sich so nicht speichern. Schick uns bitte einen Screenshot.`, report.ok ? "ok" : "error");
      if (report.ok) { passed = res.bytes; download.hidden = false; }
    } catch (e) {
      note.hidden = true;
      toast(e.message, "error");
    } finally {
      bar.hidden = true;
      status();
    }
  });

  download.addEventListener("click", () => {
    if (!passed) return;
    saveFile(passed, "SYSTEM.VSB", { note: "Kopier die Datei auf die SD-Karte nach KORG › dein Ordner › System und starte am Gerät das Update: Menü -> DATA UTILITY -> SOFTWARE UPDATE." });
  });

  /** False when the firmware is not one this editor knows. */
  async function loadBytes(bytes) {
    const id = await identify(bytes);
    const found = id.known ? locateModTable(bytes) : null;
    idle.hidden = false;
    intro.hidden = split.hidden = actions.hidden = true;
    if (!found?.ok) {
      idle.textContent = firmwareAdvice(id, found?.reasons ?? id.reasons);
      return false;
    }
    Object.assign(state, { original: bytes, bytes: Uint8Array.from(bytes), file: found.file, place: found.place, index: 0 });
    passed = null;
    idle.hidden = true;
    intro.hidden = split.hidden = actions.hidden = false;
    build();
    openType(0);
    download.hidden = true;
    checks.hidden = true;
    note.hidden = true;
    status();
    return true;
  }

  return { loadBytes, get loaded() { return !!state.original; } };
}
