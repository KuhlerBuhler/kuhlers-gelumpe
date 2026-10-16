/**
 * The emulator sidebar: what the emulated device shows right now, and the
 * effect it shows, opened in the effects editor (plan 3.4).
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { fxPanel } from "./fx.mjs";
import { BUTTONS } from "../../data/panel.mjs";

const POLL_MS = 1000;
const button = id => BUTTONS.find(b => b.id === id).index;

export function describeScreen(c) {
  const parts = [c.name?.de ?? `Bildschirm ${c.mode}`];
  if (c.pageName) parts.push(c.pageName);
  if (c.overlay) parts.push(`Fenster ${c.overlay.name?.de ?? c.overlay.kind}`);
  parts.push(`Part ${c.part + 1}`);
  return parts.join(" · ");
}

export function contextSidebar(root, { device, emulator, probe }) {
  const where = el("p", { className: "cee-side-where", id: "cee-side-where", role: "status" });
  const hint = el("p", { className: "muted", id: "cee-side-hint" });
  const note = el("p", { className: "muted", id: "cee-side-note", "aria-live": "polite" });
  const body = el("div", { id: "cee-side-fx", hidden: true });
  const fx = fxPanel(body, { device, prefix: "cee-side", embedded: true, onSent: redraw, live: async () => (emulator.port.running ? probe() : null) });
  let shown = null;
  let last = null;
  let firmware = null;
  let current = null;

  /** Where the screen is read from: the attached real device, else the running emulator; null when neither runs. */
  async function source() {
    const s = device.session;
    if (s && !s.port.emulator) return s;
    return emulator.port.running ? probe().catch(() => null) : null;
  }

  root.replaceChildren(el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: "Was das Gerät gerade zeigt" })]), where, hint, note, body);

  const put = (node, text) => { if (node.textContent !== text) node.textContent = text; };

  async function tick() {
    // Reading the screen from RAM is a Hacktribe command; Korg's own firmware does not answer it (src/firmware.mjs).
    const lack = !(device.session && !device.session.port.emulator) ? emulator.lack("sysex") : null;
    // Korgs own build has nothing to show here: the whole section stays away, no word about it.
    root.hidden = !!lack;
    if (lack) {
      current = null;
      body.hidden = true;
      shown = null;
      return;
    }
    const s = await source();
    current = s;
    if (!s) {
      put(where, "");
      put(hint, "Die Electribe ist aus.");
      body.hidden = true;
      shown = null;
      return;
    }
    if (s.busy || s.reserved || document.hidden) return;
    let c;
    try {
      c = await s.screen();
    } catch (e) {
      if (e.kind !== "busy") put(note, `Bildschirm nicht gelesen: ${e.message}`);
      return;
    }
    last = c;
    put(where, describeScreen(c));
    if (!c.fx) {
      put(hint, shown
        ? `Zuletzt gezeigt: ${shown.kind === "mfx" ? "Master" : "Insert"} ${shown.slot}.`
        : "Für diesen Bildschirm gibt es noch keine Felder. MFX TYPE im Menü Pattern und das Fenster IFX TYPE zeigen ihren Effekt hier.");
      return;
    }
    if (emulator.firmware !== firmware) {
      shown = null;
      const next = emulator.firmware;
      const loaded = next ? await fx.loadBytes(next).catch(() => false) : false;
      if (loaded) firmware = next;
      if (!loaded) {
        hint.textContent = "Die Firmware im Emulator ist nicht die vermessene; ihre Effekte kennt der Editor nicht.";
        body.hidden = true;
        return;
      }
    }
    if (shown?.kind !== c.fx.kind || shown?.slot !== c.fx.slot) {
      if (!fx.open(c.fx.kind, c.fx.slot)) {
        hint.textContent = `${c.fx.kind === "mfx" ? "Master" : "Insert"} ${c.fx.slot} gibt es in der geladenen Datei nicht.`;
        body.hidden = true;
        shown = null;
        return;
      }
      shown = c.fx;
    }
    hint.textContent = "";
    body.hidden = false;
  }

  /**
   * The firmware draws a menu page when it opens, not when RAM changes
   * (measure:2026-10-09/menuezustand). EXIT and MENU reopen the same page
   * without touching the pattern. Only ever on the emulator.
   */
  async function redraw(sent) {
    if (!current?.port.emulator || last?.fx?.kind !== sent.kind || last.fx.slot !== sent.slot || last.overlay) return;
    await emulator.button(button("exit"));
    await emulator.button(button("menu"));
    toast("Display neu aufgebaut (EXIT, MENU), damit es den neuen Stand zeigt.", "info");
  }

  setInterval(tick, POLL_MS);
  return { tick, sessionChanged: () => fx.sessionChanged() };
}
