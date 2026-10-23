/**
 * The virtual SD card of the emulator. The card is one fixed folder on this computer, in
 * ~/.gelumpe/sd/card, laid out the way the firmware expects (KORG/...). The page does two things:
 * put the card in or take it out, and show the folder in the file manager. Only the local
 * emulator service can open the file manager, so both go through its routes under /sd
 * (tools/emu/server.py). Formatting is the firmware's own: DATA UTILITY, CARD FORMAT.
 *
 * While the card is in, the folder is write-protected and only the emulated Electribe changes
 * it. The card goes in and out also while the Electribe runs.
 *
 * Mounting: the panel reads the link from `emulator.link` and takes a new one through
 * connect(). `heading: false` leaves out the title when the host already names the block; `bar: true`
 * lays it out for the navbar, the switch and "SD-Karte öffnen" in a row, the state for screen readers only.
 *
 *   const sd = sdcardPanel(node, emulator, { bar: true });
 *   sd.connect(found.link);       // when the link changes later
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";

const STYLE = new URL("./sdcard.css", import.meta.url).href;

/** What the panel shows for a state answered by GET /sd; a pure function so it can be tested. */
export function cardView(state) {
  if (!state?.available) return { available: false, checked: false, canOpen: false, line: "Nicht verbunden", busy: false, error: "" };
  const busy = !!state.busy;
  return {
    available: true,
    checked: !!state.inserted,
    canOpen: true,
    line: busy ? "Schreibt" : state.inserted ? "Eingelegt, schreibgeschützt" : "Nicht eingelegt",
    busy,
    error: state.error || "",
  };
}

export function sdcardPanel(root, emulator = null, { heading = true, bar = false } = {}) {
  if (typeof document !== "undefined" && !document.querySelector("link[data-cee-sd]")) {
    const css = el("link", { rel: "stylesheet", href: STYLE });
    css.setAttribute("data-cee-sd", "");
    document.head.append(css);
  }
  let explicit = null;
  let state = { available: false };
  let working = false;
  let events = null;
  let refreshTimer = null;

  const link = () => explicit ?? emulator?.link ?? null;

  const api = async (method, path) => {
    const l = link();
    if (!l) throw new Error(window.__GELUMPE_APP ? "Der Emulator der App läuft nicht. Starte die App neu; was er meldet, steht in ~/.gelumpe/emu.log." : "Nicht verbunden. Starte npm run emu und öffne den Link, den es ausgibt.");
    let res;
    try {
      res = await fetch(`http://127.0.0.1:${l.port}${path}`, {
        method, body: method === "POST" ? "{}" : undefined, headers: { "X-Emu-Token": l.token, ...(method === "POST" ? { "Content-Type": "application/json" } : {}) },
      });
    } catch {
      throw new Error(window.__GELUMPE_APP ? "Der Emulator der App antwortet nicht. Starte die App neu; was er meldet, steht in ~/.gelumpe/emu.log." : `Der Emulator auf Port ${l.port} antwortet nicht. Läuft npm run emu?`);
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw Object.assign(new Error(data.error || `Emulator antwortet mit ${res.status}.`), { status: res.status });
    return data;
  };

  // ---- parts of the page -------------------------------------------------------
  const status = el("p", { className: "muted", id: "cee-sd-status", role: "status", ariaLive: "polite" });
  const inserted = el("input", { type: "checkbox", id: "cee-sd-inserted" });
  inserted.setAttribute("role", "switch");
  const open = el("button", { type: "button", className: bar ? "btn sm" : "btn", id: "cee-sd-open", textContent: bar ? "SD-Karte öffnen" : "Öffnen" });
  let problem = "";                          // the last error of an action; it takes the place of the line until the next action

  const say = (text) => { problem = text; render(); };

  function render() {
    const view = cardView(state);
    const error = problem || view.error;
    status.textContent = error || view.line;
    status.dataset.tone = error ? "error" : "";
    inserted.checked = view.checked;
    inserted.disabled = !view.available || working;
    open.disabled = !view.canOpen || working;
  }

  // ---- data --------------------------------------------------------------------
  async function load(keepProblem = false) {
    state = await api("GET", "/sd").catch(e => { if (e.status === 404) return { available: false }; throw e; });
    if (!keepProblem) problem = "";
    render();
  }

  /** One action at a time: the controls stay off until it is done, errors take the place of the status line. */
  async function run(action) {
    if (working) return;
    working = true;
    problem = "";
    render();
    try {
      await action();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      working = false;
      try { await load(true); } catch (e) { say(e.message); }
    }
  }

  // ---- events from the service ---------------------------------------------------
  function listen() {
    events?.close();
    const l = link();
    if (!l || typeof EventSource === "undefined") return;
    events = new EventSource(`http://127.0.0.1:${l.port}/events?token=${encodeURIComponent(l.token)}`);
    let seen = null;
    events.addEventListener("status", e => {
      const s = JSON.parse(e.data);
      const now = `${s.state}|${s.card?.name ?? ""}`;
      if (now !== seen) { seen = now; refreshSoon(); }
    });
    events.addEventListener("sd", e => {
      const { busy } = JSON.parse(e.data);
      state = { ...state, busy };
      render();
      if (!busy) refreshSoon();            // the firmware stopped writing: look again
    });
  }

  function refreshSoon() {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => { if (!working) load().catch(e => say(e.message)); }, 400);
  }

  // ---- controls ------------------------------------------------------------------
  inserted.addEventListener("change", () => {
    const want = inserted.checked;
    run(() => api("POST", want ? "/sd/insert" : "/sd/eject"));
  });

  open.addEventListener("click", () => run(() => api("POST", "/sd/open")));

  // ---- layout --------------------------------------------------------------------
  if (bar) {
    status.className = "ui-sr-only";
    root.replaceChildren(
      el("label", { className: "ui-switch cee-sd-switch" }, [inserted, el("span", { className: "ui-switch-track", ariaHidden: "true" }), "Karte eingelegt"]),
      open,
      status,
    );
  } else root.replaceChildren(...[
    heading ? el("div", { className: "ui-section-head" }, [el("h2", { className: "ui-section-title", textContent: "SD-Karte" })]) : null,
    el("div", { className: "actions cee-sd-actions" }, [
      el("label", { className: "ui-switch" }, [inserted, el("span", { className: "ui-switch-track", ariaHidden: "true" }), "Karte einlegen"]),
      open,
    ]),
    status,
  ].filter(Boolean));
  render();
  if (link()) { listen(); load().catch(e => say(e.message)); }

  return {
    /** Use another link to the service, e.g. after the page found it. */
    connect(next) {
      explicit = next;
      listen();
      load().catch(e => say(e.message));
    },
    refresh: () => load(),
  };
}
