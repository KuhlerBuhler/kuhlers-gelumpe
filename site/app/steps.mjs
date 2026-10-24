/**
 * The step raster: one part, sixteen steps at a time, as on the device.
 *
 * An ARIA grid with a roving tab stop: one cell is in the tab order, arrow
 * keys move it, Space or a click switches the step, the focused step's
 * details sit below. Only the cell that changed is redrawn.
 */
import { el, control } from "./fields.mjs";
import { field } from "../../src/map/index.mjs";
import { noteLabel } from "../../src/map/convert.mjs";

const PAGE = 16;
/** The note a factory step carries when nobody chose one: 61, C4. */
const DEFAULT_NOTE_RAW = 61;

export function stepEditor(doc) {
  let part = 0;
  let page = 0;
  let focus = 0;
  const root = el("div", { className: "cee-steps-wrap" });

  const pages = el("div", { className: "ui-segmented" });
  pages.setAttribute("role", "radiogroup");
  pages.setAttribute("aria-label", "Steps");
  const pageInputs = [0, 1, 2, 3].map(p => {
    const input = el("input", { type: "radio", name: "cee-step-page", value: String(p), checked: p === 0 });
    input.addEventListener("change", () => { if (input.checked) { page = p; focus = 0; draw(); } });
    pages.append(el("label", { className: "ui-segmented-option" }, [input, el("span", { textContent: `${p * PAGE + 1} bis ${p * PAGE + PAGE}` })]));
    return input;
  });

  const grid = el("div", { className: "cee-steps" });
  grid.setAttribute("role", "grid");
  const row = el("div", { className: "cee-steps-row" });
  row.setAttribute("role", "row");
  grid.append(row);
  const cells = Array.from({ length: PAGE }, (_, i) => {
    const cell = el("div");
    cell.setAttribute("role", "gridcell");
    const button = el("button", { type: "button", className: "cee-step", tabIndex: i === 0 ? 0 : -1 });
    button.dataset.index = String(i);
    cell.append(button);
    row.append(cell);
    return button;
  });
  const detail = el("div", { className: "cee-step-detail" });
  const warning = el("p", { className: "cee-hint", hidden: true });

  const stepIndex = i => page * PAGE + i;
  const ix = i => [part, stepIndex(i)];

  function drawCell(i) {
    const b = cells[i];
    const on = doc.get("step.on", ix(i)) === 1;
    const trigger = doc.get("step.trigger", ix(i)) === 1;
    const note = doc.get("step.note", [...ix(i), 0]);
    b.setAttribute("aria-pressed", String(on));
    b.dataset.trigger = String(trigger);
    const n = stepIndex(i) + 1;
    const noteText = on && note ? noteLabel(note - 1) : "";
    // The name starts with what the step shows (number and note), the rest only for screen readers (WCAG 2.5.3).
    b.replaceChildren(el("span", { className: "cee-step-num", textContent: String(n) }), " ", el("span", { className: "cee-step-note", textContent: noteText }),
      el("span", { className: "ui-sr-only", textContent: `, Step ${n}, ${on ? "an" : "aus"}${on && !trigger ? ", ohne Trigger" : ""}` }));
    b.removeAttribute("aria-label");
  }

  function drawDetail() {
    const s = stepIndex(focus);
    const fields = ["step.trigger", "step.gate", "step.velocity"].map(id => control(field(id), () => doc.get(id, [part, s]), raw => { doc.set(id, [part, s], raw); drawCell(focus); drawWarning(); }));
    const notes = [0, 1, 2, 3].map(k => control({ ...field("step.note"), label: { de: `Note ${k + 1}`, en: `Note ${k + 1}` } },
      () => doc.get("step.note", [part, s, k]), raw => { doc.set("step.note", [part, s, k], raw); drawCell(focus); }, { compact: true }));
    detail.replaceChildren(el("h3", { textContent: `Step ${s + 1}` }), el("div", { className: "cee-grid" }, [...fields, ...notes].map(c => c.node)));
    drawWarning();
  }

  function drawWarning() {
    const s = stepIndex(focus);
    const on = doc.get("step.on", [part, s]) === 1;
    const trigger = doc.get("step.trigger", [part, s]) === 1;
    warning.hidden = !(on && !trigger);
    warning.textContent = warning.hidden ? "" : "Warnung: Step ist an, aber ohne Trigger. So klingt er nicht.";
  }

  function draw() {
    grid.setAttribute("aria-label", `Steps von Part ${part + 1}, ${page * PAGE + 1} bis ${page * PAGE + PAGE}`);
    cells.forEach((b, i) => { b.tabIndex = i === focus ? 0 : -1; drawCell(i); });
    drawDetail();
  }

  function toggle(i) {
    const on = doc.get("step.on", ix(i)) === 1;
    doc.group(() => {
      if (on) { doc.set("step.on", ix(i), 0); return; }
      doc.set("step.on", ix(i), 1);
      // A step sounds only with both on and trigger set.
      if (doc.get("step.trigger", ix(i)) !== 1) doc.set("step.trigger", ix(i), 1);
      if (doc.get("step.note", [...ix(i), 0]) === 0) doc.set("step.note", [...ix(i), 0], DEFAULT_NOTE_RAW);
    });
    drawCell(i);
    if (i === focus) drawDetail();
  }

  function moveFocus(i, { take = true } = {}) {
    focus = Math.max(0, Math.min(PAGE - 1, i));
    cells.forEach((b, k) => { b.tabIndex = k === focus ? 0 : -1; });
    if (take) cells[focus].focus();
    drawDetail();
  }

  row.addEventListener("click", e => {
    const b = e.target.closest(".cee-step");
    if (!b) return;
    const i = Number(b.dataset.index);
    if (i !== focus) moveFocus(i, { take: false });
    toggle(i);
  });
  row.addEventListener("keydown", e => {
    const keys = { ArrowRight: focus + 1, ArrowLeft: focus - 1, Home: 0, End: PAGE - 1 };
    if (e.key in keys) { e.preventDefault(); moveFocus(keys[e.key]); }
  });

  root.append(pages, grid, warning, detail);
  return {
    node: root,
    show(p) { part = p; draw(); },
    refresh: draw,
    get part() { return part; },
    pageInputs,
  };
}
