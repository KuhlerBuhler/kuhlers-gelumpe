/**
 * The run area of the plugins page: the same device drawing as the emulator page (panel.mjs), driven by the
 * simulated plugin run in the browser, and below it the apps and menu pages the plugins declared.
 * Display, LEDs, keys, pads, knobs and the touchpad all go to the browser VM.
 */
import { el } from "./fields.mjs";
import { TOUCH_BUTTON } from "../../data/panel.mjs";
import { drawDisplay } from "./emulator.mjs";
import { devicePanel } from "./panel.mjs";
import { t } from "./i18n.mjs";

/**
 * @param {HTMLElement} root
 * @param {{ post: (event: string, ...args: number[]) => void }} input where the controls send their events
 */
export function simPanel(root, { post }) {
  const canvas = el("canvas", { className: "cee-lcd cee-sim-lcd", id: "cee-sim-lcd", width: 128, height: 64 });
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-label", t("sim.display"));
  const state = el("p", { className: "muted cee-sim-state", id: "cee-sim-state", role: "status", textContent: t("sim.idle") });
  const screenNote = el("p", { className: "muted cee-sim-screen", id: "cee-sim-screen", role: "status" });

  // What the drawing sends is what the emulator would get; the VM takes the same events by their script names.
  const send = e => {
    switch (e.kind) {
      case "button": post(e.down ? "buttonPress" : "buttonRelease", e.index); break;
      case "encoder": post("encoder", e.index, e.delta); break;
      case "knob": post("knob", e.index, e.value); break;
      case "pad": post("pad", e.index, e.down ? 1 : 0, e.down ? (e.velocity ?? 100) : 0); break;
      case "touch":
        if (e.down === true) post("buttonPress", TOUCH_BUTTON);
        if (e.down === false) post("buttonRelease", TOUCH_BUTTON);
        else post("touch", e.x, e.y);
        break;
      default: break;
    }
  };
  const front = devicePanel(send, { prefix: "cee-sim" });
  const drawing = front.build(el("div", { className: "cee-lcd-frame" }, [canvas]));
  front.setPower(true);

  const menuBody = el("div", { className: "ui-details-body cee-sim-menu", id: "cee-sim-menu-pages" });
  const menuBox = el("details", { className: "ui-details", id: "cee-sim-menu-box", hidden: true }, [el("summary", { textContent: t("sim.menuPages") }), menuBody]);
  let menuKey = "";
  let menuInputs = [];
  const appBody = el("div", { className: "cee-sim-apps", id: "cee-sim-apps" });
  const appBox = el("div", { className: "cee-sim-appbox", id: "cee-sim-apps-box", hidden: true }, [el("p", { className: "muted", textContent: t("sim.apps") }), appBody]);
  let appKey = null;
  let appButtons = [];

  root.replaceChildren(drawing, state, screenNote, appBox, menuBox);

  return {
    /** Draw the display bytes and the LED levels (0 to 255 each). */
    show(displayBytes, leds) {
      drawDisplay(canvas, displayBytes);
      front.showLeds(leds, true);
    },
    say(text) { state.textContent = text; },
    /**
     * The apps the plugins declared, as the GAMES and TOOLS pages of the BLECH menu on the device: one button each opens it,
     * EXIT leaves the open one. `open(id)` and `exit()` are the user's actions, `shown` the name of the open app or null.
     */
    apps(items, { open, exit }) {
      appBox.hidden = items.length === 0;
      const open_ = items.find(a => a.open) ?? null;
      screenNote.textContent = items.length === 0
        ? t("sim.screen.own")
        : open_ ? t("sim.screen.app", { name: open_.name }) : t("sim.screen.home");
      const key = items.map(a => `${a.id}:${a.group}:${a.name}`).join("|");
      if (key !== appKey) {
        appKey = key;
        appBody.replaceChildren();
        appButtons = items.map(a => {
          const b = el("button", { type: "button", className: "btn sm cee-sim-app", textContent: t("sim.openApp", { group: a.group, name: a.name }), onclick: () => open(a.id) });
          b.dataset.app = String(a.id);
          return b;
        });
        const leave = el("button", { type: "button", className: "btn sm", id: "cee-sim-app-exit", textContent: t("sim.exitApp"), onclick: () => exit() });
        appButtons.push(leave);
        appBody.append(...appButtons);
      }
      items.forEach((a, i) => { appButtons[i].disabled = !!open_; appButtons[i].setAttribute("aria-pressed", String(a.open)); });
      appButtons.at(-1).disabled = !open_;
    },
    /** The pages the script added to the device menu, as a slider each; `set(id, value)` is the user turning one. */
    menus(items, set) {
      menuBox.hidden = items.length === 0;
      const key = items.map(m => `${m.id}:${m.script}:${m.label}:${m.min}:${m.max}`).join("|");
      if (key !== menuKey) {
        menuKey = key;
        menuBody.replaceChildren();
        menuInputs = items.map(m => {
          const id = `cee-sim-menu-${m.id}`;
          const out = el("output", { htmlFor: id, textContent: String(m.value) });
          const input = el("input", { type: "range", min: m.min, max: m.max, value: m.value, id, className: "cee-sim-knob" });
          input.addEventListener("input", () => { const v = set(m.id, Number(input.value)); out.textContent = String(v ?? input.value); });
          menuBody.append(el("label", { className: "cee-sim-control", htmlFor: id }, [el("span", { textContent: `${m.label} (${m.script})` }), input, out]));
          return { input, out };
        });
      }
      items.forEach((m, i) => {
        if (document.activeElement !== menuInputs[i].input) { menuInputs[i].input.value = String(m.value); menuInputs[i].out.textContent = String(m.value); }
      });
    },
    /** Let go of everything, so a stopped run leaves no key held. */
    release() { front.showLeds({}, true); },
  };
}
