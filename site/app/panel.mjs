/**
 * The emulated device front: every control sends the panel message the
 * firmware expects (numbers in data/panel.mjs), and the LEDs show what the
 * firmware switched on. An own drawing in token colours, no logo or brand.
 */
import { el } from "./fields.mjs";
import { icon } from "./icons.mjs";
import { BUTTONS, ENCODERS, KNOBS, KNOB_OFF_ANGLE, PADS, TOUCHPAD_MAX } from "../../data/panel.mjs";
import {
  Accumulator, WheelGovernor, DETENT_DEG, DRAG_PX_PER_DETENT, DRAG_PX_FULL_RANGE, WHEEL_PX_PER_DETENT, WHEEL_PX_FULL_RANGE,
  FREE_MAX, FREE_CENTER, CLICK_MAX_MS, CLICK_MAX_PX, clamp, wheelPixels, rawOf, withCatch, angleOfValue,
} from "./dials.mjs";
import { t } from "./i18n.mjs";

const byId = list => Object.fromEntries(list.map(c => [c.id, c]));
const B = byId(BUTTONS);
const E = byId(ENCODERS);
const K = byId(KNOBS);

/** SHIFT clicked shorter than this stays down until the next click; held longer it is released on letting go. */
const LATCH_MAX_MS = 350;
const LIT = 0.1;
/** Keys under the display whose names are long for their width: one line, smaller type. */
const FIT = new Set(["gateArp", "touchScale", "masterFx", "mfxHold"]);

function set(node, attrs) {
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  return node;
}

/** Holding a control down: pointer or Enter/Space, released on every way out. */
function holdable(node, onChange) {
  let down = false;
  const go = state => {
    if (state === down) return;
    down = state;
    node.dataset.down = String(state);
    onChange(state);
  };
  node.addEventListener("pointerdown", e => {
    if (e.button !== 0) return;
    e.preventDefault();
    node.setPointerCapture?.(e.pointerId);
    node.focus();
    go(true);
  });
  for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) node.addEventListener(ev, () => go(false));
  node.addEventListener("keydown", e => {
    if ((e.key === "Enter" || e.key === " ") && !e.repeat) { e.preventDefault(); go(true); }
  });
  node.addEventListener("keyup", e => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(false); }
  });
  node.addEventListener("blur", () => go(false));
  return node;
}

/**
 * SHIFT for a mouse or a finger, which cannot hold it and turn a knob at once:
 * a short click latches it down, the next click lets go. Held longer than a
 * click it behaves like the real key.
 */
function shiftKey(node, onChange) {
  let down = false;
  let latched = false;
  let since = null;
  const show = () => {
    node.dataset.down = String(down);
    node.dataset.latched = String(latched);
    node.setAttribute("aria-pressed", String(down));
  };
  const go = state => {
    if (state === down) return;
    down = state;
    show();
    onChange(state);
  };
  let releasing = false;
  const begin = () => {
    if (since !== null) return;
    since = performance.now();
    if (latched) { latched = false; releasing = true; go(false); return; }
    go(true);
  };
  const end = () => {
    if (since === null) return;
    const held = performance.now() - since;
    since = null;
    if (releasing) { releasing = false; return; }
    if (held < LATCH_MAX_MS) { latched = true; show(); return; }
    go(false);
  };
  node.addEventListener("pointerdown", e => {
    if (e.button !== 0) return;
    e.preventDefault();
    node.setPointerCapture?.(e.pointerId);
    node.focus();
    begin();
  });
  for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) node.addEventListener(ev, () => { if (since !== null) end(); });
  node.addEventListener("keydown", e => {
    if ((e.key === "Enter" || e.key === " ") && !e.repeat) { e.preventDefault(); begin(); }
  });
  node.addEventListener("keyup", e => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); end(); }
  });
  node.addEventListener("blur", () => { if (!latched && since !== null) { since = null; go(false); } });
  node.setAttribute("aria-pressed", "false");
  return node;
}

/**
 * Pointer handling shared by every dial: a drag reports vertical pixels, a
 * press that hardly moved reports a click, the wheel reports its pixels.
 */
function dialPointer(dial, { onDrag, onClick, onWheel }) {
  let last = null;
  let moved = 0;
  let at = 0;
  dial.addEventListener("pointerdown", e => {
    if (e.button !== 0) return;
    e.preventDefault();
    dial.setPointerCapture?.(e.pointerId);
    dial.focus();
    last = e.clientY;
    moved = 0;
    at = performance.now();
  });
  dial.addEventListener("pointermove", e => {
    if (last === null) return;
    const dy = last - e.clientY;
    moved += Math.abs(dy);
    last = e.clientY;
    if (dy) onDrag(dy);
  });
  const release = e => {
    if (last === null) return;
    last = null;
    if (e.type === "pointerup" && onClick && moved < CLICK_MAX_PX && performance.now() - at < CLICK_MAX_MS) onClick();
  };
  for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) dial.addEventListener(ev, release);
  dial.addEventListener("wheel", e => {
    e.preventDefault();
    onWheel(wheelPixels(e), e.timeStamp);
  }, { passive: false });
}

function labelled(dial, text) {
  return el("div", { className: "cee-e2-control" }, [el("span", { className: "cee-e2-label", textContent: text, ariaHidden: "true" }), dial]);
}

/** A small panel next to a knob to type or drag its value (0 to 127). */
function valuePopup(pre) {
  const number = el("input", { type: "number", className: "input cee-e2-pop-number", id: `${pre}-pop-number`, min: 0, max: FREE_MAX, step: 1, inputMode: "numeric" });
  const range = el("input", { type: "range", className: "ui-range", id: `${pre}-pop-range`, min: 0, max: FREE_MAX, step: 1 });
  const title = el("label", { className: "cee-e2-pop-title", htmlFor: `${pre}-pop-number` });
  const node = set(el("div", { className: "cee-e2-pop", id: `${pre}-pop`, hidden: true }, [title, number, range]), { role: "dialog" });
  let owner = null;

  const close = (refocus = false) => {
    if (!owner) return;
    const dial = owner.dial;
    owner = null;
    node.hidden = true;
    if (refocus) dial.focus();
  };
  const commit = raw => {
    if (!owner || raw === "" || !Number.isFinite(Number(raw))) return;
    const v = clamp(Math.round(Number(raw)), 0, FREE_MAX);
    number.value = String(v);
    range.value = String(v);
    window.ui?.syncRange?.(range);
    owner.set(v);
  };
  number.addEventListener("input", () => commit(number.value));
  range.addEventListener("input", () => commit(range.value));
  node.addEventListener("keydown", e => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(true); }
    if (e.key === "Enter") { e.preventDefault(); close(true); }
  });
  node.addEventListener("focusout", e => {
    if (owner && !node.contains(e.relatedTarget) && e.relatedTarget !== owner.dial) close();
  });
  document.addEventListener("pointerdown", e => {
    if (owner && !node.contains(e.target) && !owner.dial.contains(e.target)) close();
  });

  return {
    node,
    get owner() { return owner?.dial ?? null; },
    close,
    /** Opens beside `dial`, or closes when it already is open there. */
    toggle(dial, { label, value, set: setValue }) {
      if (owner?.dial === dial) { close(true); return; }
      owner = { dial, set: setValue };
      title.textContent = label;
      node.setAttribute("aria-label", t("panel.set", { label }));
      range.setAttribute("aria-label", t("panel.slider", { label }));
      number.value = String(value);
      range.value = String(value);
      node.hidden = false;
      window.ui?.syncRange?.(range);
      const body = node.parentElement.getBoundingClientRect();
      const d = dial.getBoundingClientRect();
      const w = node.offsetWidth;
      const h = node.offsetHeight;
      const gap = 8;
      const below = d.bottom - body.top + gap;
      node.style.left = `${clamp(d.left + d.width / 2 - body.left - w / 2, gap, body.width - w - gap)}px`;
      node.style.top = `${below + h > body.height ? Math.max(gap, d.top - body.top - h - gap) : below}px`;
      number.focus();
      number.select();
    },
    /** The value changed from the knob itself while the panel is open. */
    sync(dial, value) {
      if (owner?.dial !== dial) return;
      number.value = String(value);
      range.value = String(value);
      window.ui?.syncRange?.(range);
    },
  };
}

/** `prefix` starts the ids of the controls, so a second drawing on the page does not repeat them. */
/** The two LEDs of each pad, red 0x2c + 2n and blue 0x2d + 2n. */
const isPadLed = i => i >= 0x2c && i <= 0x4b;

export function devicePanel(send, { prefix = "cee-e2" } = {}) {
  const pre = prefix;
  let frontNode = null;
  let settled = null;
  const leds = new Map();
  // Knob markers rest at fixed positions while the device is off (KNOB_OFF_ANGLE).
  const restings = [];
  let powered = false;
  const onLed = (index, apply) => {
    if (!leds.has(index)) leds.set(index, []);
    leds.get(index).push(apply);
  };
  const popup = valuePopup(pre);

  const lightButton = (node, label) => v => {
    node.style.setProperty("--cee-e2-glow", String(v));
    node.dataset.lit = v >= 0.5 ? "on" : v > LIT ? "dim" : "off";
    node.setAttribute("aria-label", v > LIT ? t("panel.lit", { label }) : label);
  };

  // The transport keys carry the symbol printed on the device; the name is for the pointer and the screen reader.
  const SYMBOLS = { rec: ["rec", t("panel.rec")], stop: ["stop", "STOP"], play: ["play", t("panel.play")] };
  const button = c => {
    const symbol = SYMBOLS[c.id];
    const b = el("button", { type: "button", className: "cee-e2-btn", id: `${pre}-${c.id}` }, [
      symbol ? icon(symbol[0]) : el("span", { className: "cee-e2-label", textContent: c.label }),
    ]);
    const name = symbol ? symbol[1] : c.label;
    if (symbol) b.title = name;
    if (FIT.has(c.id)) b.classList.add("cee-e2-btn-fit");
    b.setAttribute("aria-label", name);
    b.dataset.index = String(c.index);
    b.dataset.lit = "off";
    if (c.id === "play") {
      // Two blue LEDs, no red: the whole key glows blue, as bright as both together.
      b.classList.add("cee-e2-btn-blue");
      const light = lightButton(b, name);
      const parts = [0, 0];
      [c.led, c.ledBlue].forEach((led, n) => onLed(led, v => { parts[n] = v; light(Math.min(1, parts[0] + parts[1])); }));
    } else if (c.ledBlue === undefined) onLed(c.led, lightButton(b, name));
    else {
      // Two LEDs in one key: blue in the upper part, red in the lower; the key itself stays dark.
      b.classList.add("cee-e2-btn-dots");
      const dot = color => {
        const d = el("span", { className: "cee-e2-led", ariaHidden: "true" });
        d.dataset.color = color;
        b.append(d);
        return d;
      };
      const blue = dot("blue");
      const red = dot("red");
      const light = lightButton(b, name);
      onLed(c.led, v => { red.style.setProperty("--cee-e2-glow", String(v)); light(Math.max(v, Number(blue.style.getPropertyValue("--cee-e2-glow")) || 0)); });
      onLed(c.ledBlue, v => { blue.style.setProperty("--cee-e2-glow", String(v)); light(Math.max(v, Number(red.style.getPropertyValue("--cee-e2-glow")) || 0)); });
    }
    if (c.id === "shift") {
      b.title = t("panel.shift");
      return shiftKey(b, down => send({ kind: "button", index: c.index, down }));
    }
    return holdable(b, down => send({ kind: "button", index: c.index, down }));
  };

  /** Endless encoder with clicks: 24 per turn, one message per click. */
  const encoder = c => {
    const dial = set(el("div", { className: "cee-e2-dial cee-e2-encoder cee-e2-endless", id: `${pre}-${c.id}`, tabIndex: 0 }, [el("span", { className: "cee-e2-mark" })]), {
      role: "spinbutton", "aria-label": c.label, "aria-valuetext": t("panel.endless"),
    });
    let turned = 0;
    const click = direction => {
      turned += direction;
      dial.style.setProperty("--cee-e2-angle", String(turned * DETENT_DEG));
      send({ kind: "encoder", index: c.index, delta: direction });
    };
    const drag = new Accumulator(DRAG_PX_PER_DETENT);
    const wheel = new WheelGovernor(WHEEL_PX_PER_DETENT);
    dialPointer(dial, {
      onDrag: dy => { const n = drag.add(dy); for (let i = 0; i < Math.abs(n); i++) click(Math.sign(n)); },
      onWheel: (px, now) => { const n = wheel.step(px, now); if (n) click(n); },
    });
    dial.addEventListener("pointerdown", () => drag.reset());
    dial.addEventListener("keydown", e => {
      const d = { ArrowUp: 1, ArrowRight: 1, ArrowDown: -1, ArrowLeft: -1 }[e.key];
      if (d) { e.preventDefault(); click(d); }
    });
    return labelled(dial, c.label);
  };

  /**
   * A control that runs from 0 to 127 without clicks. `emit(value, before)`
   * says what changed; `center` makes it catch briefly in the middle.
   */
  const freeDial = (c, { center = null, emit, popupEnabled = true }) => {
    let value = FREE_CENTER;
    let position = value;
    // The marker leaves its resting angle only once a real value exists: the user turned the knob.
    let known = false;
    const dial = set(el("div", { className: "cee-e2-dial cee-e2-free", id: `${pre}-${c.id}`, tabIndex: 0 }, [el("span", { className: "cee-e2-mark" })]), {
      role: "slider", "aria-label": c.label, "aria-valuemin": 0, "aria-valuemax": FREE_MAX,
    });
    const show = () => {
      dial.setAttribute("aria-valuenow", String(value));
      dial.style.setProperty("--cee-e2-angle", String((!powered || !known) && c.id in KNOB_OFF_ANGLE ? KNOB_OFF_ANGLE[c.id] : angleOfValue(value)));
      popup.sync(dial, value);
    };
    restings.push(show);
    const land = next => {
      known = true;
      const before = value;
      value = clamp(next, 0, FREE_MAX);
      show();
      if (value !== before) emit(value, before);
    };
    const move = units => {
      position = clamp(position + units, 0, FREE_MAX);
      land(center === null ? Math.round(position) : withCatch(position, center));
    };
    const to = v => { position = v; land(v); };
    dialPointer(dial, {
      onDrag: dy => move(dy * FREE_MAX / DRAG_PX_FULL_RANGE),
      onWheel: px => move(-clamp(px, -200, 200) * FREE_MAX / WHEEL_PX_FULL_RANGE),
      onClick: popupEnabled ? () => popup.toggle(dial, { label: c.label, value, set: to }) : null,
    });
    dial.addEventListener("pointerdown", () => { position = value; });
    dial.addEventListener("keydown", e => {
      const d = { ArrowUp: 1, ArrowRight: 1, ArrowDown: -1, ArrowLeft: -1, PageUp: 10, PageDown: -10 }[e.key];
      if (d) { e.preventDefault(); to(clamp(value + d, 0, FREE_MAX)); return; }
      if (e.key === "Home") { e.preventDefault(); to(0); }
      if (e.key === "End") { e.preventDefault(); to(FREE_MAX); }
      if (popupEnabled && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); popup.toggle(dial, { label: c.label, value, set: to }); }
    });
    show();
    return labelled(dial, c.label);
  };

  /** A potentiometer: the panel message carries the position itself. */
  const knob = (c, { center = null } = {}) => freeDial(c, {
    center,
    emit: value => send({ kind: "knob", index: c.index, value: rawOf(value) }, `knob-${c.index}`),
  });

  /** CUTOFF turns like an encoder but runs free from 0 to 127: it sends the change since the last value. */
  const cutoff = c => {
    let pending = 0;
    let timer = null;
    const flush = () => {
      while (pending) {
        const delta = clamp(pending, -16, 16);
        pending -= delta;
        send({ kind: "encoder", index: c.index, delta });
      }
    };
    // The first change goes out at once, changes within the next 30 ms travel together.
    const closeWindow = () => { timer = null; if (pending) { flush(); timer = setTimeout(closeWindow, 30); } };
    const control = freeDial(c, {
      popupEnabled: false,
      emit: (value, before) => {
        pending += value - before;
        if (timer) return;
        flush();
        timer = setTimeout(closeWindow, 30);
      },
    });
    control.querySelector(".cee-e2-dial").classList.add("cee-e2-endless");
    return control;
  };

  const padFace = [];
  const pad = p => {
    const b = el("button", { type: "button", className: "cee-e2-pad", id: `${pre}-${p.id}` }, [
      el("span", { className: "cee-e2-label", textContent: p.label, ariaHidden: "true" }),
    ]);
    const face = { node: b, red: 0, blue: 0, name: t("panel.pad", { label: p.label }) };
    padFace.push(face);
    b.dataset.index = String(p.index);
    paintPad(face);
    onLed(p.ledRed, v => { face.red = v; paintPad(face); });
    onLed(p.ledBlue, v => { face.blue = v; paintPad(face); });
    return holdable(b, down => {
      send(down ? { kind: "pad", index: p.index, down, velocity: 100 } : { kind: "pad", index: p.index, down });
      paintPad(face);
    });
  };

  /** Pressed reads red like the red LED; a blue pad that is pressed reads purple. */
  function paintPad(face) {
    const pressed = face.node.dataset.down === "true";
    const red = pressed ? 1 : face.red;
    const tone = red > LIT && face.blue > LIT ? "purple" : red > LIT ? "red" : face.blue > LIT ? "blue" : "off";
    face.node.dataset.tone = tone;
    face.node.style.setProperty("--cee-e2-glow", String(Math.max(red, face.blue)));
    face.node.style.setProperty("--cee-e2-red", String(red));
    face.node.style.setProperty("--cee-e2-blue", String(face.blue));
    const state = { off: null, red: pressed ? "panel.pad.pressed" : "panel.pad.red", blue: "panel.pad.blue", purple: pressed ? "panel.pad.pressedBlue" : "panel.pad.redBlue" }[tone];
    face.node.setAttribute("aria-label", state ? t(state, { name: face.name }) : face.name);
  }

  const touchpad = () => {
    const area = set(el("div", { className: "cee-e2-touchpad", id: `${pre}-touchpad`, tabIndex: 0 }, [el("span", { className: "cee-e2-touchpoint" })]), {
      role: "application", "aria-label": t("panel.touchpad"),
    });
    let touching = false;
    let x = TOUCHPAD_MAX / 2, y = TOUCHPAD_MAX / 2;
    const place = () => {
      area.style.setProperty("--cee-e2-x", String(x / TOUCHPAD_MAX));
      area.style.setProperty("--cee-e2-y", String(1 - y / TOUCHPAD_MAX));
    };
    const at = e => {
      const r = area.getBoundingClientRect();
      x = Math.round(Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * TOUCHPAD_MAX);
      y = Math.round(Math.max(0, Math.min(1, 1 - (e.clientY - r.top) / r.height)) * TOUCHPAD_MAX);
      place();
    };
    const start = () => { touching = true; area.dataset.down = "true"; send({ kind: "touch", x, y, down: true }); };
    const move = () => send({ kind: "touch", x, y }, "touch");
    const end = () => {
      if (!touching) return;
      touching = false;
      area.dataset.down = "false";
      send({ kind: "touch", down: false });
    };
    area.addEventListener("pointerdown", e => {
      if (e.button !== 0) return;
      e.preventDefault();
      area.setPointerCapture?.(e.pointerId);
      area.focus();
      at(e);
      start();
    });
    area.addEventListener("pointermove", e => { if (touching) { at(e); move(); } });
    for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) area.addEventListener(ev, end);
    const STEP = 32;
    area.addEventListener("keydown", e => {
      if (e.key === " " || e.key === "Enter") { e.preventDefault(); if (!e.repeat && !touching) start(); return; }
      const d = { ArrowLeft: [-STEP, 0], ArrowRight: [STEP, 0], ArrowUp: [0, STEP], ArrowDown: [0, -STEP] }[e.key];
      if (!d) return;
      e.preventDefault();
      x = Math.max(0, Math.min(TOUCHPAD_MAX, x + d[0]));
      y = Math.max(0, Math.min(TOUCHPAD_MAX, y + d[1]));
      place();
      if (touching) move();
    });
    area.addEventListener("keyup", e => { if (e.key === " " || e.key === "Enter") end(); });
    area.addEventListener("blur", end);
    place();
    return area;
  };

  // The real device has no power switch on its front, so this one sits in the drawing, left of the Volume knob.
  const power = holdable(el("button", { type: "button", className: "btn icon cee-e2-power", id: `${pre}-power`, title: t("panel.power.hint") }), down => send({ kind: "power", down }));
  power.setAttribute("aria-label", t("panel.power"));

  // Positions in a 1200 x 700 space, the layout of the device front
  // (from the prototype accepted on 2026-10-09). CSS scales the space.
  const at = (node, x, y, w, h) => {
    node.classList.add("cee-e2-at");
    node.style.cssText += `--x:${x};--y:${y};--w:${w};--h:${h}`;
    return node;
  };
  // Volume and Input Level are not wired to the firmware; they rest at 0.
  const dummy = (x, y, w, h, label, id) => at(set(el("span", { className: "cee-e2-control" }, [
    el("span", { className: "cee-e2-label", textContent: label }),
    el("span", { className: "cee-e2-dial cee-e2-fixed", style: `--cee-e2-angle:${KNOB_OFF_ANGLE[id]}` }, [el("span", { className: "cee-e2-mark" })]),
  ]), { "aria-hidden": "true" }), x, y, w, h);
  // `end`: the title ends at the frame's right edge instead of being centred, for the frame next to the case edge.
  const section = (name, x, w, end = false) => at(set(el("span", { className: "cee-e2-section" }, name ? [el("span", { className: end ? "cee-e2-section-name cee-e2-section-name-end" : "cee-e2-section-name", textContent: name })] : []), { "aria-hidden": "true" }), x, 146, w, 230);
  const PAD_SLOTS = [378, 465, 551, 637, 733, 819, 905, 992];

  return {
    build(lcd) {
      const root = set(el("div", { className: "cee-e2", id: pre, "data-power": "off" }), { role: "group", "aria-label": t("panel.device") });
      const pads = PADS.map(pad);
      pads.forEach((node, n) => at(node, PAD_SLOTS[n % 8], n < 8 ? 433 : 520, 76, 75));
      const body = el("div", { className: "cee-e2-body" }, [
        at(power, 135, 115, 44, 44),
        at(set(el("span", { className: "cee-e2-label cee-e2-power-label" }, [icon("power")]), { "aria-hidden": "true" }), 135, 101, 44, 12),
        dummy(216, 113, 46, 49, "Volume", "volume"),
        dummy(285, 113, 47, 49, "Input Level", "inputLevel"),
        at(el("div", { className: "cee-e2-screen" }, [lcd]), 135, 175, 210, 125),
        section("Sample", 488, 96), section("Filter", 586, 160), section("Modulation", 748, 90), section("", 840, 154), section("Insert Fx", 996, 88, true),
        at(encoder(E.value), 400, 177, 61, 62),
        at(encoder(E.osc), 507, 178, 57, 60),
        at(cutoff(E.cutoff), 633, 178, 58, 60),
        at(encoder(E.modType), 764, 178, 59, 60),
        at(knob(K.level), 852, 185, 48, 48),
        at(knob(K.pan, { center: FREE_CENTER }), 934, 185, 48, 48),
        at(encoder(E.ifxType), 1010, 178, 61, 60),
        at(knob(K.pitch, { center: FREE_CENTER }), 511, 257, 48, 48),
        at(knob(K.resonance), 597, 257, 48, 48),
        at(knob(K.egInt, { center: FREE_CENTER }), 681, 257, 48, 48),
        at(knob(K.modDepth), 768, 257, 48, 48),
        at(knob(K.attack), 853, 257, 48, 48),
        at(knob(K.decay), 934, 257, 48, 48),
        at(knob(K.ifxEdit), 1017, 257, 48, 48),
        at(knob(K.oscEdit), 511, 322, 48, 48),
        at(knob(K.modSpeed), 769, 322, 48, 48),
        at(button(B.editLeft), 380, 263, 48, 24), at(button(B.editRight), 432, 263, 48, 24),
        at(button(B.menu), 380, 300, 48, 24), at(button(B.exit), 432, 300, 48, 24),
        at(button(B.shift), 380, 339, 48, 25), at(button(B.write), 432, 339, 48, 25),
        at(button(B.rec), 138, 327, 47, 49), at(button(B.stop), 189, 327, 48, 49),
        at(button(B.play), 241, 327, 49, 49), at(button(B.tap), 294, 327, 46, 49),
        at(button(B.gateArp), 138, 386, 43, 25), at(button(B.touchScale), 184, 386, 56, 25),
        at(button(B.masterFx), 243, 386, 48, 25), at(button(B.mfxHold), 294, 386, 46, 25),
        at(button(B.lpf), 592, 335, 48, 27), at(button(B.hpf), 642, 335, 48, 27), at(button(B.bpf), 692, 335, 48, 27),
        at(button(B.mfxSend), 853, 335, 48, 27), at(button(B.ampEg), 934, 335, 48, 27), at(button(B.ifxOn), 1013, 335, 52, 27),
        at(button(B.partDec), 380, 385, 48, 25), at(button(B.partInc), 432, 385, 49, 25),
        at(button(B.partMute), 484, 385, 48, 25), at(button(B.partErase), 536, 385, 49, 25),
        at(button(B.trigger), 587, 385, 48, 25), at(button(B.sequencer), 638, 385, 49, 25),
        at(button(B.keyboard), 690, 385, 50, 25), at(button(B.chord), 741, 385, 48, 25),
        at(button(B.stepJump), 792, 385, 49, 25), at(button(B.patternSet), 844, 385, 49, 25),
        at(button(B.bar1), 935, 385, 26, 38), at(button(B.bar2), 969, 385, 26, 38),
        at(button(B.bar3), 1003, 385, 26, 38), at(button(B.bar4), 1036, 385, 26, 38),
        at(touchpad(), 139, 435, 200, 159),
        ...pads,
        popup.node,
      ]);
      root.append(el("div", { className: "cee-e2-viewport" }, [body]));
      frontNode = root;
      return root;
    },
    /**
     * LED brightness from the firmware, 0 to 255. Unlisted LEDs keep their state. The pad LEDs
     * (0x2c to 0x4b) are on or off on the device: any value from 1 lights fully (measured 2026-10-16,
     * docs/messungen/2026-10-16-pad-led-stufen.md), so the panel shows them the same way.
     */
    showLeds(state, replace = false) {
      if (replace) for (const applies of leds.values()) for (const apply of applies) apply(0);
      for (const [i, v] of Object.entries(state)) {
        const level = isPadLed(Number(i)) ? (v > 0 ? 1 : 0) : v / 255;
        for (const apply of leds.get(Number(i)) || []) apply(level);
      }
    },
    /** The display and the controls only mean something while the firmware runs. */
    setPower(on) {
      const root = frontNode;
      if (root) {
        root.dataset.power = on ? "on" : "off";
        root.dataset.settling = "";
        clearTimeout(settled);
        settled = setTimeout(() => delete root.dataset.settling, 400);
      }
      powered = on;
      for (const show of restings) show();
      if (!on) popup.close();
    },
  };
}
