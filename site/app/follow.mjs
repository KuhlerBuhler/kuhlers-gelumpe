/**
 * Follows the device: reads which screen it shows, keeps that as the
 * display's text for screen readers, and with the switch on the Presets
 * page opens the effect the device shows (plan 3.4).
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { BUTTONS } from "../../data/panel.mjs";
import { t } from "./i18n.mjs";

const POLL_MS = 1000;
const KEY = "cee.fx.follow";
const button = id => BUTTONS.find(b => b.id === id).index;

export function describeScreen(c) {
  const parts = [c.name?.de ?? t("follow.screen", { mode: c.mode })];
  if (c.pageName) parts.push(c.pageName);
  if (c.overlay) parts.push(t("follow.window", { name: c.overlay.name?.de ?? c.overlay.kind }));
  parts.push(t("follow.part", { part: c.part + 1 }));
  return parts.join(" · ");
}

/** `emulator` and `fx` return their panels once they exist; the text goes into the emulator's `where`. */
export function followDevice({ device, emulator: emu, probe, fx, storage = null }) {
  let saved = false;
  try { saved = storage?.getItem(KEY) === "1"; } catch { /* blocked storage: the switch starts off */ }
  const toggle = el("input", { type: "checkbox", id: "cee-fx-follow", checked: saved });
  const node = el("label", { className: "ui-switch cee-fx-follow" }, [toggle, el("span", { className: "ui-switch-track", ariaHidden: "true" }), t("follow.toggle")]);
  let shown = null;
  let last = null;
  let current = null;

  toggle.addEventListener("change", () => {
    shown = null;
    try { storage?.setItem(KEY, toggle.checked ? "1" : "0"); } catch { /* kept for this visit only */ }
    if (toggle.checked) tick();
  });

  /** Where the screen is read from: the attached real device, else the running emulator; null when neither runs. */
  async function source(emulator) {
    const s = device.session;
    if (s && !s.port.emulator) return s;
    return emulator.port.running ? probe().catch(() => null) : null;
  }

  async function tick() {
    const emulator = emu();
    if (!emulator) return;
    const put = text => { if (emulator.where.textContent !== text) emulator.where.textContent = text; };
    // Reading the screen from RAM is a Hacktribe command; Korg's own firmware does not answer it (src/firmware.mjs).
    const lack = !(device.session && !device.session.port.emulator) ? emulator.lack("sysex") : null;
    if (lack) { current = null; put(""); return; }
    const s = await source(emulator);
    current = s;
    if (!s) { put(t("follow.off")); return; }
    if (s.busy || s.reserved || document.hidden) return;
    let c;
    try {
      c = await s.screen();
    } catch {
      return;
    }
    last = c;
    put(describeScreen(c));
    const panel = fx();
    if (!toggle.checked || !c.fx || !panel) return;
    if (shown?.kind === c.fx.kind && shown?.slot === c.fx.slot) return;
    // An edit not sent yet stays open; the next screen change tries again.
    if (panel.dirty) return;
    if (panel.open(c.fx.kind, c.fx.slot)) shown = c.fx;
  }

  /**
   * The firmware draws a menu page when it opens, not when RAM changes
   * (measure:2026-10-09/menuezustand). EXIT and MENU reopen the same page
   * without touching the pattern. Only ever on the emulator.
   */
  async function redraw(sent) {
    const emulator = emu();
    if (!current?.port.emulator || last?.fx?.kind !== sent.kind || last.fx.slot !== sent.slot || last.overlay) return;
    await emulator.button(button("exit"));
    await emulator.button(button("menu"));
    toast(t("follow.redrawn"), "info");
  }

  setInterval(tick, POLL_MS);
  return { node, tick, redraw };
}
