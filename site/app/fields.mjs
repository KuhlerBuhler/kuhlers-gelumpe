/**
 * One control per map field, chosen from the field's converter and type.
 *
 * The control never shows bytes. It reads the raw value through the field,
 * shows it in plain words, and on input hands a raw value back to `onChange`.
 * A value the device holds outside the editable range is shown as it is and
 * only replaced when someone moves the control.
 */
import { converter } from "../../src/map/convert.mjs";
import { typeOf, describe } from "../../src/map/index.mjs";
import { t } from "./i18n.mjs";

let seq = 0;
const uid = prefix => `${prefix}-${++seq}`;

const el = (tag, props = {}, children = []) => {
  const node = Object.assign(document.createElement(tag), props);
  for (const c of [].concat(children)) if (c != null) node.append(c);
  return node;
};

const label = f => f.label.de;

/** Which control fits a field. */
export function controlKind(f) {
  const type = typeOf(f);
  if (type.kind === "text") return "text";
  if (!f.convert) return "none";
  if (f.convert === "onOff") return "switch";
  const c = converter(f.convert);
  if (c.choices && f.convert !== "modSpeed") return c.choices.length <= 5 ? "segmented" : "select";
  return "range";
}

/**
 * @param {object} f map field
 * @param {() => number|string} read current raw value
 * @param {(raw: number|string) => void} onChange
 * @returns {{ node: HTMLElement, refresh: () => void }}
 */
export function control(f, read, onChange, { compact = false } = {}) {
  const kind = controlKind(f);
  const id = uid("cee-f");
  const help = f.note ? el("p", { className: "ui-field-help", id: `${id}-help`, textContent: f.note }) : null;

  if (kind === "text") {
    const input = el("input", { className: "input", id, type: "text", maxLength: typeOf(f).width, spellcheck: false, autocomplete: "off" });
    input.addEventListener("change", () => {
      try {
        onChange(input.value);
        window.ui?.setFieldError(input, null);
      } catch (e) {
        window.ui?.setFieldError(input, e.message);
      }
    });
    const refresh = () => { input.value = read(); };
    refresh();
    return { node: el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: id, textContent: label(f) }), input, help]), refresh };
  }

  if (kind === "switch") {
    const input = el("input", { type: "checkbox", id });
    input.setAttribute("role", "switch");
    const wrap = el("label", { className: "ui-switch" }, [input, el("span", { className: "ui-switch-track", ariaHidden: "true" }), label(f)]);
    input.addEventListener("change", () => onChange(input.checked ? 1 : 0));
    const refresh = () => {
      const raw = read();
      input.checked = raw === 1;
      input.indeterminate = raw !== 0 && raw !== 1;
    };
    refresh();
    return { node: el("div", { className: "cee-field" }, [wrap, help]), refresh };
  }

  if (kind === "segmented" || kind === "select") {
    const c = converter(f.convert);
    const options = c.choices.filter(o => !f.range || (o.raw >= f.range[0] && o.raw <= f.range[1]));
    if (kind === "segmented") {
      const group = el("div", { className: "ui-segmented", role: "radiogroup" });
      group.setAttribute("role", "radiogroup");
      group.setAttribute("aria-label", label(f));
      const name = uid("cee-seg");
      const inputs = options.map(o => {
        const input = el("input", { type: "radio", name, value: String(o.raw) });
        input.addEventListener("change", () => input.checked && onChange(o.raw));
        group.append(el("label", { className: "ui-segmented-option" }, [input, el("span", { textContent: o.label })]));
        return input;
      });
      const unknown = el("p", { className: "ui-field-help", hidden: true });
      const refresh = () => {
        const raw = read();
        let hit = false;
        for (const input of inputs) { input.checked = Number(input.value) === raw; hit ||= input.checked; }
        unknown.hidden = hit;
        unknown.textContent = hit ? "" : t("fields.deviceValue", { value: c.format(raw) });
      };
      refresh();
      return { node: el("div", { className: "ui-field" }, [el("span", { className: "ui-field-label", textContent: label(f) }), group, unknown, help]), refresh };
    }
    const select = el("select", { className: "select", id });
    for (const o of options) select.append(el("option", { value: String(o.raw), textContent: o.label }));
    const extra = el("option", { disabled: true, hidden: true });
    select.append(extra);
    select.addEventListener("change", () => onChange(Number(select.value)));
    const refresh = () => {
      const raw = read();
      const known = options.some(o => o.raw === raw);
      extra.hidden = known;
      extra.value = String(raw);
      extra.textContent = c.format(raw);
      select.value = String(raw);
    };
    refresh();
    return { node: el("div", { className: "ui-field" }, [el("label", { className: "ui-field-label", htmlFor: id, textContent: label(f) }), select, help]), refresh };
  }

  if (kind === "range") {
    const [min, max] = f.range || converter(f.convert).domain;
    const input = el("input", { type: "range", className: "ui-range", id, min, max, step: 1 });
    const out = el("output", { className: "ui-range-value" });
    const outside = el("span", { className: "cee-outside", hidden: true, textContent: t("fields.outside") });
    input.addEventListener("input", () => {
      onChange(Number(input.value));
      show(Number(input.value));
    });
    const show = raw => {
      const d = describe(f, raw);
      const text = d ? d.text : String(raw);
      out.textContent = text;
      input.setAttribute("aria-valuetext", text);
    };
    const refresh = () => {
      const raw = read();
      const inRange = raw >= min && raw <= max;
      input.value = String(inRange ? raw : Math.max(min, Math.min(max, raw)));
      outside.hidden = inRange;
      window.ui?.syncRange(input);
      show(raw);
    };
    refresh();
    const head = el("label", { className: "ui-field-label", htmlFor: id }, [label(f), " ", out, outside]);
    return { node: el("div", { className: compact ? "ui-field cee-compact" : "ui-field" }, [head, input, help]), refresh };
  }

  const span = el("span", { className: "muted" });
  const refresh = () => { span.textContent = String(read()); };
  refresh();
  return { node: el("div", { className: "ui-field" }, [el("span", { className: "ui-field-label", textContent: label(f) }), span]), refresh };
}

export { el };
