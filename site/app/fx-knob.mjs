/**
 * A knob for the Baukasten, drawn like one on a plugin: drag it up or down, turn the wheel, or type the value in the
 * box under it. A range input sits hidden behind it for the keyboard and screen readers, so the value lives in one
 * place. A ring around it can show the stretch a control (Steuerung) moves the parameter through.
 */
import { el } from "./fields.mjs";
import { clamp, wheelPixels, DRAG_PX_FULL_RANGE, WHEEL_PX_FULL_RANGE, SWEEP_DEG } from "./dials.mjs";
import { t } from "./i18n.mjs";

const NS = "http://www.w3.org/2000/svg";
const C = 24;
const R_TRACK = 17;
const R_SPAN = 22;

/** A point on the circle, the angle in degrees with 0 pointing up. */
const at = (r, deg) => {
  const a = (deg - 90) * Math.PI / 180;
  return `${(C + r * Math.cos(a)).toFixed(2)} ${(C + r * Math.sin(a)).toFixed(2)}`;
};
const arc = (r, from, to) => {
  if (to - from < 0.5) return "";
  return `M${at(r, from)}A${r} ${r} 0 ${to - from > 180 ? 1 : 0} 1 ${at(r, to)}`;
};
const path = cls => { const p = document.createElementNS(NS, "path"); p.setAttribute("class", cls); return p; };

/** A Korg name may break after each underscore, not in the middle of a word. */
const breakable = text => text.split("_").flatMap((part, n) => (n ? [el("wbr"), `_${part}`] : [part]));

/**
 * @param {string} id the id of the hidden range input; the number box is `${id}-value`
 * @param {(v: number) => void} change runs on every new value
 */
export function knob(id, label, hint, min, max, value, change, { readOnly = false } = {}) {
  const input = el("input", { type: "range", className: "cee-knob-input", id, min, max, value, disabled: readOnly });
  const box = el("input", { type: "number", className: "input cee-bk-number", id: `${id}-value`, min, max, value, readOnly });
  box.setAttribute("aria-label", t("knob.value", { label }));

  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 48 48");
  svg.setAttribute("aria-hidden", "true");
  const span = path("cee-knob-span");
  const track = path("cee-knob-track");
  const fill = path("cee-knob-fill");
  const mark = path("cee-knob-mark");
  track.setAttribute("d", arc(R_TRACK, -SWEEP_DEG / 2, SWEEP_DEG / 2));
  svg.append(span, track, fill, mark);
  const dial = el("div", { className: `cee-knob-dial${readOnly ? " cee-knob-fixed" : ""}` }, [svg, input]);

  const angle = v => ((v - min) / (max - min || 1) - 0.5) * SWEEP_DEG;
  // A parameter that runs through zero (a modulation's strength) fills from the middle.
  const zero = min < 0 && max > 0 ? angle(0) : -SWEEP_DEG / 2;
  let shown = Number(value);
  let preview = null;
  const draw = () => {
    const v = preview ?? shown;
    const a = angle(v);
    fill.setAttribute("d", arc(R_TRACK, Math.min(zero, a), Math.max(zero, a)));
    mark.setAttribute("d", `M${at(6, a)}L${at(R_TRACK - 3, a)}`);
    dial.classList.toggle("cee-knob-moving", preview !== null);
    box.value = String(v);
  };
  const land = v => {
    const next = clamp(Math.round(v), min, max);
    if (next === shown) return;
    shown = next;
    input.value = String(next);
    box.value = String(next);
    draw();
    change(next);
  };

  input.addEventListener("input", () => land(Number(input.value)));
  input.addEventListener("change", () => land(Number(input.value)));
  box.addEventListener("input", () => { const v = Number(box.value); if (box.value !== "" && Number.isFinite(v)) land(v); });
  box.addEventListener("change", () => { box.value = String(shown); });

  if (!readOnly) {
    // Up is more, like every knob on the device; the whole travel takes as many pixels as the emulator's knobs.
    let last = null;
    let position = shown;
    dial.addEventListener("pointerdown", e => {
      if (e.button !== 0) return;
      e.preventDefault();
      try { dial.setPointerCapture(e.pointerId); } catch {}
      input.focus();
      last = e.clientY;
      position = shown;
    });
    dial.addEventListener("pointermove", e => {
      if (last === null) return;
      position = clamp(position + (last - e.clientY) * (max - min) / DRAG_PX_FULL_RANGE, min, max);
      last = e.clientY;
      land(position);
    });
    for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) dial.addEventListener(ev, () => { last = null; });
    dial.addEventListener("wheel", e => {
      e.preventDefault();
      const step = -clamp(wheelPixels(e), -200, 200) * (max - min) / WHEEL_PX_FULL_RANGE;
      land(shown + (Math.abs(step) < 1 ? Math.sign(step) : step));
    }, { passive: false });
  }
  draw();

  return {
    node: el("div", { className: "ui-field cee-knob" }, [
      el("label", { className: "ui-field-label", htmlFor: id }, [label, hint ? el("span", { className: "cee-bk-param-id" }, breakable(`(${hint})`)) : null]),
      dial,
      box,
    ]),
    /** The stretch a control moves this parameter through, or null for none. */
    span(low, high) {
      if (low === null) { span.setAttribute("d", ""); dial.classList.remove("cee-knob-mapped"); return; }
      const [a, b] = [angle(clamp(Math.min(low, high), min, max)), angle(clamp(Math.max(low, high), min, max))];
      span.setAttribute("d", arc(R_SPAN, a, Math.max(b, a + 2)));
      dial.classList.add("cee-knob-mapped");
    },
    /** Shows a value for a moment without keeping it (the preview of the controls); null shows the kept one again. */
    show(v) { preview = v === null ? null : clamp(Math.round(v), min, max); draw(); },
    get value() { return shown; },
  };
}
